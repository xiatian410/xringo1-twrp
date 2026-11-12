#!/usr/bin/env python3
"""Verify stock-service/post-probe calibration bridge; preserve motor unknown."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 path=ROOT/'logs/haptics-restore-joined-review.json';r=json.loads(path.read_text())
 assert r['status']=='PASS' and len(r['cases'])==14
 for group in ['sources','tests','emulator_files']:
  for name,h in r[group].items():
   p=Path(name) if Path(name).is_absolute() else ROOT/name;assert sha(p)==h,name
 labels={'A1-valid','B2-q-rejected','A1-f0-out-of-range','A1-q-write-error','A1-PM-error','A1-missing-files','A1-valid-then-production'}
 for sample in ['os4-current','os4-stable']:
  cases={c['case']:c for c in r['cases'] if c['sample']==sample};assert set(cases)==labels
  for label,c in cases.items():
   assert c['status']=='PASS' and c['service']['readiness_flag']=='00'
   writes=c['service']['writes'];results=[w['driver_store_result'] for w in writes]
   expected=[] if label=='A1-missing-files' else [-5,-5,-5] if label=='A1-PM-error' else [6,-22,5] if label=='A1-f0-out-of-range' else [6,7,-1] if label=='B2-q-rejected' else [6,7,-5] if label=='A1-q-write-error' else [6,7,5]
   assert results==expected
   assert [w['result'] for w in writes]==[-1 if v<0 else v for v in results]
   if label=='A1-PM-error':assert not c['driver_writes'] and len(c['driver_pm'])==3
   if label=='A1-q-write-error':assert c['driver_writes'][-1]==dict(address=0x2802150,value=0xa000,result=-5)
   if label=='A1-valid-then-production':
    assert c['production']['erase_result']==0 and c['production']['effect_list_empty']
    assert [w['value'] for w in c['production']['writes']]==[20,125,64,80,0]
   else:assert c['production'] is None
 index=json.loads((ROOT/'simulation-report.json').read_text());check,=[c for c in index['checks'] if c['name']=='stock-ARM64-OS4-haptics-restore-joined']
 assert check['count']==14 and check['evidence_sha256']==sha(path)
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 assert sha(Path(index['image']))==index['image_sha256']
 out=dict(status='PASS',scope=__doc__,cases=14,evidence_sha256=sha(path),production_change=False,image_sha256=index['image_sha256'],documents={n:sha(ROOT/n) for n in ['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.json','simulation-report.md','docs/HAPTICS-ADAPTATION.md']},audit_script_sha256=sha(Path(__file__)))
 (ROOT/'logs/haptics-restore-joined-review-audit.json').write_text(json.dumps(out,indent=2)+'\n')
 print('PASS:14 stock-service/store joins; no device calibration or physical motor evidence')
if __name__=='__main__':main()
