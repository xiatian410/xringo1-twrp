#!/usr/bin/env python3
"""Bind reference FF core/original A1 driver and real field erase evidence."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 path=ROOT/'logs/haptics-ff-core-review.json';r=json.loads(path.read_text());assert r['status']=='PASS' and len(r['cases'])==16
 for group in ['sources','tests','emulator_files']:
  for name,digest in r[group].items():
   p=Path(name) if Path(name).is_absolute() else ROOT/name;assert sha(p)==digest,name
 for sample in ['os4-current','os4-stable']:
  cases={c['case']:c for c in r['cases'] if c['sample']==sample};assert len(cases)==8
  for label,c in cases.items():
   good=label in ['natural-done','stop-then-done','stop-mail-error-done','stop-PM-error-done']
   assert c['core_result']==(-13 if label=='wrong-owner' else 0 if good or label=='close-stop-only' else -62)
   assert c['owner_retained']==(not good) and c['effect_list_empty']==good
   assert c['callbacks']==([] if label=='wrong-owner' else ['playback0','erase'])
   if label in ['stop-completion-only','close-stop-only']:
    assert c['waits'][0]['result']==0 and ['complete',0x4000000+0x208] in c['completions']
 fieldpath=ROOT/'logs/haptics-erase-field-observation.json';field=json.loads(fieldpath.read_text())
 assert field['status']=='OBSERVED' and field['count']==len(field['transactions'])==43
 for name,digest in field['sources'].items():assert sha(ROOT/name)==digest,name
 assert all(t['erase_done']['message'].endswith('erase_ret = 0') for t in field['transactions'])
 index=json.loads((ROOT/'simulation-report.json').read_text());assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 for name,p,count in [('stock-ARM64-OS4-haptics-reference-FF-core',path,16),('field-OS4-haptics-stop-erase',fieldpath,43)]:
  check,=[c for c in index['checks'] if c['name']==name];assert check['evidence_sha256']==sha(p) and check['count']==count
 assert sha(Path(index['image']))==index['image_sha256']
 out=dict(status='PASS',scope=__doc__,reference_driver_cases=16,field_transactions=43,production_change=False,image_sha256=index['image_sha256'],
  evidence={str(p.relative_to(ROOT)):sha(p) for p in [path,fieldpath]},documents={n:sha(ROOT/n) for n in ['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.json','simulation-report.md','docs/HAPTICS-ADAPTATION.md']},audit_script_sha256=sha(Path(__file__)))
 (ROOT/'logs/haptics-ff-core-review-audit.json').write_text(json.dumps(out,indent=2)+'\n');print('PASS:16 reference-core/A1 cases;43 field erases all0; physical vibration unresolved')
if __name__=='__main__':main()
