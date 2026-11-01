#!/usr/bin/env python3
"""Validate a complete self-contained JSONL bundle; no network or side effects."""
import hashlib, json, sys
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

here=Path(__file__).resolve().parent
schema=json.loads((here/'platform-routing.schema.json').read_text(encoding='utf-8'))
Draft202012Validator.check_schema(schema)
validator=Draft202012Validator(schema,format_checker=FormatChecker())
path=Path(sys.argv[1]) if len(sys.argv)>1 and sys.argv[1]!='-' else here/'example-fictional.jsonl'
contents=sys.stdin.read() if len(sys.argv)>1 and sys.argv[1]=='-' else path.read_text(encoding='utf-8')
records=[]
for n,line in enumerate(contents.splitlines(),1):
    if not line.strip(): continue
    x=json.loads(line); errs=list(validator.iter_errors(x))
    if errs: raise ValueError(f'line {n}: schema validation failed: {errs[0].message}')
    records.append(x)
field={'service':'service_id','community':'community_id','mapping':'mapping_id','task':'task_id','result':'result_id','observation':'observation_id','review':'review_id'}
indexes={k:{} for k in field}
for x in records:
    kind=x['record_type']; identifier=x[field[kind]]
    key=(identifier,x.get('version',1))
    if key in indexes[kind]:raise ValueError(f'duplicate {kind} id/version {key}')
    indexes[kind][key]=x
def has(kind,identifier,version=1): return (identifier,version) in indexes[kind]
def digest(s):return hashlib.sha256(s.encode('utf-8')).hexdigest()
for x in records:
    k=x['record_type']
    if k=='community' and not any(i==x['service_id'] for i,v in indexes['service']):raise ValueError('missing service')
    if k=='mapping' and not any(i==x['community_id'] for i,v in indexes['community']):raise ValueError('missing community')
    if k=='task' and (x['exploration_slots']>x['top_k'] or x['candidate_k']<x['top_k']):raise ValueError('invalid candidate/final/exploration limits')
    if k=='result':
        if not has('task',x['task_id']):raise ValueError('missing task')
        task=indexes['task'][(x['task_id'],1)]
        for key in ('run_id','snapshot_id','embedding_model_id','embedding_revision','embedding_input_version'):
            if task[key]!=x[key]:raise ValueError('task/result mismatch: '+key)
        if x['query_text_sha256']!=digest(task['query_text']):raise ValueError('query text hash mismatch')
        if len(x['retrieved'])>task['candidate_k']:raise ValueError('retrieval exceeds candidate_k')
        for r in x['retrieved']:
            m=indexes['mapping'].get((r['mapping_id'],r['mapping_version']))
            if not m or r['vector_text_sha256']!=digest(m['semantic_description']):raise ValueError('invalid retrieved mapping/hash')
        retrieved={(r['mapping_id'],r['mapping_version']) for r in x['retrieved']}
        if x['returned_count']!=len(x['items']) or x['returned_count']>x['requested_k'] or x['requested_k']!=task['top_k']:raise ValueError('result count mismatch')
        if x['filtered_count']!=len(x['excluded']):raise ValueError('filter count mismatch')
        if x['returned_count']<x['requested_k'] and not x['shortfall_reason']:raise ValueError('missing shortfall reason')
        if [a['rank'] for a in x['items']]!=list(range(1,len(x['items'])+1)):raise ValueError('invalid ranks')
        if len({a['community_id'] for a in x['items']})!=len(x['items']):raise ValueError('duplicate community in routed items')
        if sum(a['selection_lane']=='exploration' for a in x['items'])>task['exploration_slots']:raise ValueError('too many exploration slots')
        for a in x['items']:
            if a['selection_lane']=='ranked' and (a['mapping_id'],a['mapping_version']) not in retrieved:raise ValueError('ranked item missing from retrieval')
            mapping=indexes['mapping'].get((a['mapping_id'],a['mapping_version']))
            if not mapping or mapping['community_id']!=a['community_id']:raise ValueError('invalid mapping reference')
            if a['vector_text_sha256']!=digest(mapping['semantic_description']):raise ValueError('vector text hash mismatch')
            sim=a['semantic_similarity']
            if sim is not None and x['similarity_metric']=='cosine' and not -1<=sim<=1:raise ValueError('invalid cosine')
            for oid in a['observation_ids']:
                if not has('observation',oid):raise ValueError('missing result observation')
    if k=='observation':
        if not has('task',x['task_id']) or not has('mapping',x['mapping_id'],x['mapping_version']):raise ValueError('missing observation reference')
        if indexes['mapping'][(x['mapping_id'],x['mapping_version'])]['community_id']!=x['community_id']:raise ValueError('observation community mismatch')
        if x['sample_count']!=len(x['samples']):raise ValueError('sample count mismatch')
        if x['eligible_count'] is not None and x['sample_count']>x['eligible_count']:raise ValueError('sample exceeds eligible count')
        if x['outcome'] in ('blocked','error','unknown') and x['sample_count']!=0:raise ValueError('blocked/error/unknown cannot have samples; use separate observations')
        if x['outcome']=='sampled' and not x['sample_count']:raise ValueError('sampled requires samples')
    if k=='review':
        if not has('mapping',x['target_mapping_id'],x['target_mapping_version']):raise ValueError('missing review mapping')
        if not all(has('observation',oid) for oid in x['observation_ids']):raise ValueError('missing review observation')
print(f'PASS: {len(records)} records; schema, references, counts and hashes checked. Content truth is not verified.')
