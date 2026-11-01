"""Checks validation rejects representative broken records; synthetic only."""
import copy,json,subprocess,sys
from pathlib import Path
p=Path(__file__).resolve().parent
original=[json.loads(x) for x in (p/'example-fictional.jsonl').read_text(encoding='utf-8').splitlines()]
cases={
 'missing sampling rule': lambda r:r[5].pop('sampling_rule'),
 'bad entry URL': lambda r:r[1].update(entry_url='not-a-url'),
 'bad result count': lambda r:r[4].update(returned_count=2),
 'bad text hash': lambda r:r[4].update(query_text_sha256='0'*64),
 'missing mapping reference': lambda r:r[5].update(mapping_id='EX-ABSENT'),
 'excess exploration slots': lambda r:r[3].update(exploration_slots=4),
}
for name,change in cases.items():
 rows=copy.deepcopy(original);change(rows);data=''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows)
 r=subprocess.run([sys.executable,'-X','utf8',str(p/'validate_bundle.py'),'-'],input=data,capture_output=True,text=True,encoding='utf-8',errors='replace')
 assert r.returncode!=0, name
 print('PASS reject:',name)
