"""Preserve full matrix dimensions while batching independent heads in groups of two."""
import torch
from torch.nn.attention import sdpa_kernel,SDPBackend
HEAD_BLOCK=2
def headgroup_math(module,query,key,value,attention_mask,dropout=0.,scaling=None,is_causal=None,**kwargs):
 block=kwargs.pop('_probe_head_block',HEAD_BLOCK)
 assert dropout==0 and query.shape[-2]==key.shape[-2] and kwargs.get('sliding_window') is None
 groups=query.shape[1]//key.shape[1];assert groups*key.shape[1]==query.shape[1]
 if is_causal is None:is_causal=query.shape[-2]>1 and attention_mask is None and getattr(module,'is_causal',True)
 out=torch.empty((query.shape[0],query.shape[-2],query.shape[1],query.shape[-1]),device=query.device,dtype=query.dtype)
 with sdpa_kernel(SDPBackend.MATH):
  for start in range(0,query.shape[1],block):
   end=min(start+block,query.shape[1]);idx=torch.arange(start,end,device=key.device)//groups
   mask=attention_mask
   if mask is not None and mask.ndim==4:
    mask=mask[:,:,:,:key.shape[-2]]
    if mask.shape[1]>1:mask=mask[:,start:end]
   z=torch.nn.functional.scaled_dot_product_attention(query[:,start:end],key.index_select(1,idx),value.index_select(1,idx),attn_mask=mask,dropout_p=0.,scale=scaling,is_causal=is_causal,enable_gqa=False)
   out[:,:,start:end,:]=z.transpose(1,2)
 return out,None
