"""Selected computation routines from the canonical v4 runtime."""
import hashlib, math, time
import torch
from torch.nn.attention import sdpa_kernel, SDPBackend
from transformers import AttentionInterface
from transformers.integrations.sdpa_attention import sdpa_attention_forward
from accelerate.hooks import remove_hook_from_module
from calibration_headgroup_attention import headgroup_math

def leaf_staging(module):
 handles=[]; counts={'pre':0,'post':0,'maximum_parameter_bytes':0}
 def before(leaf,args):
  own=list(leaf.parameters(recurse=False))
  assert own and all(p.device.type=='cpu' for p in own)
  counts['maximum_parameter_bytes']=max(counts['maximum_parameter_bytes'],sum(p.numel()*p.element_size() for p in own))
  leaf.to('cuda');counts['pre']+=1
 def after(leaf,args,output):
  leaf.to('cpu');counts['post']+=1
 for leaf in module.modules():
  if list(leaf.parameters(recurse=False)):
   assert not list(leaf.children()),'REFERENCE_PARAMETERS_NOT_LEAF'
   handles.extend([leaf.register_forward_pre_hook(before),leaf.register_forward_hook(after,always_call=True)])
 return handles,counts

def standard_math(*args,**kwargs):
 with sdpa_kernel(SDPBackend.MATH):return sdpa_attention_forward(*args,**kwargs)

def blocked_math(*args,**kwargs):
 return headgroup_math(*args,**kwargs)

def install_gpu_leaves(model):
 records=[]
 for idx in [0,1,2,3,4,5]:
  module=model.model.layers[idx];remove_hook_from_module(module,recurse=True)
  if idx<2:
   assert all(p.device.type=='cpu' and p.dtype==torch.bfloat16 for p in module.parameters())
  else:
   def fingerprints():return {name:hashlib.sha256(p.detach().cpu().view(torch.uint8).numpy().tobytes()).hexdigest() for name,p in module.named_parameters()}
   before=fingerprints();module.to('cpu');assert fingerprints()==before,'QUANT_STORAGE_TRANSFER_CHANGED_VALUES'
   assert all(getattr(p,'bnb_quantized',True) for p in module.parameters())
  handles,counts=leaf_staging(module);records.append({'layer':idx,'handles':handles,'counts':counts,'quantized_storage_transfer_verified':idx>=2})
 return records

def raw(model,ids,fn):
 AttentionInterface.register('sdpa',fn)
 tensor=torch.tensor([ids],device='cuda',dtype=torch.long);beg=time.perf_counter()
 with torch.inference_mode():values=model(input_ids=tensor,attention_mask=torch.ones_like(tensor),use_cache=False).logits.detach().float().cpu().reshape(-1).tolist()
 torch.cuda.synchronize();seconds=time.perf_counter()-beg
 assert len(values)==3 and all(math.isfinite(v) for v in values)
 return values,seconds

def maxdelta(a,b):return max(abs(x-y) for x,y in zip(a,b))
