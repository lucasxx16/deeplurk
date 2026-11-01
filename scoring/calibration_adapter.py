"""Version 2 deterministic bounded context, complete hypothesis; never tokenizer truncation."""
import ast,hashlib,json,os
from pathlib import Path
CONTEXT_TOKENS=2048
MAX_INPUT_TOKENS=8192
def prompt_constants():
 tree=ast.parse(Path(os.environ['SRM_TEMPLATE']).read_text(encoding='utf-8-sig'));out={}
 for node in tree.body:
  if isinstance(node,ast.Assign):
   for t in node.targets:
    if isinstance(t,ast.Name) and t.id in ['CRITERIA_DEFINITIONS','USER_PROMPT_TEMPLATE']:out[t.id]=ast.literal_eval(node.value)
 return out
def adapt_context(tokenizer,benchmark,context):
 encode=lambda s:tokenizer.encode(s,add_special_tokens=False)
 raw=encode(context)
 if len(raw)<=CONTEXT_TOKENS:return context,{'context_original_tokens':len(raw),'context_used_tokens':len(raw),'context_token_loss_fraction':0.,'reduced':False}
 prefix='';refs=context
 if benchmark=='rino':
  problem,refs=context.split('\n\nProvided related works:\n',1);p=encode(problem);prefix=tokenizer.decode(p[:256],skip_special_tokens=False)+'\n\nProvided related works:\n'
 chunks=refs.split('\n\nTitle: ');chunks=[chunks[0]]+['Title: '+c for c in chunks[1:]];titles=[];abstracts=[]
 for c in chunks:
  title,sep,abstract=c.partition('\nAbstract: ')
  if not sep or not title.startswith('Title: '):raise ValueError('CONTEXT_STRUCTURE_NOT_RECOGNIZED')
  titles.append(title);abstracts.append(encode(abstract))
 def render(cap):return prefix+'\n\n'.join(t+'\nAbstract: '+tokenizer.decode(a[:cap],skip_special_tokens=False) for t,a in zip(titles,abstracts))
 if len(encode(render(0)))>CONTEXT_TOKENS:raise ValueError('ALL_REFERENCE_TITLES_EXCEED_CONTEXT_BUDGET')
 lo=0;hi=max(map(len,abstracts),default=0)
 while lo<hi:
  mid=(lo+hi+1)//2
  if len(encode(render(mid)))<=CONTEXT_TOKENS:lo=mid
  else:hi=mid-1
 final=render(lo);used=len(encode(final));assert used<=CONTEXT_TOKENS
 return final,{'context_original_tokens':len(raw),'context_used_tokens':used,'context_token_loss_fraction':1-used/len(raw),'reduced':True,'references_retained':len(titles),'abstract_prefix_limit_each':lo,'abstracts_truncated':sum(len(a)>lo for a in abstracts),'problem_prefix_cap_if_rino':256,'all_reference_titles_retained':True}
def prepare(tokenizer,benchmark,context,hypothesis):
 bounded,report=adapt_context(tokenizer,benchmark,context);const=prompt_constants();user=const['USER_PROMPT_TEMPLATE'].format(criteria_definitions=const['CRITERIA_DEFINITIONS'],title='',context=bounded,perspectives_based_on_author_idea='')
 messages=[{'role':'user','content':user},{'role':'assistant','content':hypothesis}];ids=tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=False)
 if len(ids)>MAX_INPUT_TOKENS:raise ValueError('COMPLETE_HYPOTHESIS_EXCEEDS_TOTAL_LIMIT')
 text=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=False)
 hypothesis_tokens=len(tokenizer.encode(hypothesis,add_special_tokens=False))
 report.update(protocol='bounded-context-v2',full_hypothesis_preserved=True,hypothesis_original_tokens=hypothesis_tokens,hypothesis_used_tokens=hypothesis_tokens,hypothesis_retention_fraction=1.,total_tokens=len(ids),framing_and_token_boundary_residual=len(ids)-report['context_used_tokens']-hypothesis_tokens,input_sha256=hashlib.sha256(text.encode()).hexdigest(),perspectives='empty',gold_fields_accepted_by_adapter=False)
 return messages,ids,report
