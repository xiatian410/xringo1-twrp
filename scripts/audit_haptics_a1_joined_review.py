#!/usr/bin/env python3
"""Bind joined A1 evidence, original inputs and current delivery; no motor claim."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 path=ROOT/'logs/haptics-A1-joined-review.json';r=json.loads(path.read_text())
 assert r['status']=='PASS' and r['count']==len(r['cases'])==16
 for group in ['sources','tests','emulator_files']:
  assert r[group]
  for name,digest in r[group].items():
   p=Path(name) if Path(name).is_absolute() else ROOT/name
   assert sha(p)==digest,name
 assert '0x40A260, Revision: 0xA1' in r['field_identity']
 labels={'A1-probe-selftest','B2-control','A1-stale-PM-state','A1-errata-sequence-error','A1-Q-write-error','A1-firmware-write-error','A1-production-done','A1-production-missing-done'}
 for sample in ['os4-current','os4-stable']:
  cases={c['case']:c for c in r['cases'] if c['sample']==sample};assert set(cases)==labels
  for label,c in cases.items():
   assert c['status']=='PASS'
   assert c['resolved_rom'][0]==(0x2801f98 if label=='B2-control' else 0x2800370)
   failed=label in {'A1-stale-PM-state','A1-errata-sequence-error','A1-Q-write-error','A1-firmware-write-error'}
   assert c['probe_result']==(-22 if label=='A1-stale-PM-state' else -5 if failed else 0)
   assert bool(c['remove_calls'])==failed
   if failed:assert not c['workers'] and 'cs40l26_input_init' not in c['entries']
   else:
    assert c['raw_write_count']==68 and c['bulk_write_count']==25
    assert (dict(address=0x2802150,value=0) in c['writes'])==(label!='B2-control')
   rt=c['runtime']
   if label.startswith('A1-production-'):
    success=label=='A1-production-done';assert rt['erase_result']==(0 if success else -62)
    assert rt['effect_list_empty']==success and len(rt['waits'])==1
    assert rt['waits'][0]['timeout']==580 and rt['waits'][0]['result']==int(success)
    assert rt['mailbox']==[dict(command=0x1800081,result=0)]
    assert [w['value'] for w in rt['writes']]==[20,125,64,80,0]
   else:assert rt is None
 index=json.loads((ROOT/'simulation-report.json').read_text())
 check,=[c for c in index['checks'] if c['name']=='stock-ARM64-OS4-haptics-A1-joined']
 assert check['count']==16 and check['evidence_sha256']==sha(path)
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 assert sha(Path(index['image']))==index['image_sha256']
 docs=['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.json','simulation-report.md','docs/HAPTICS-ADAPTATION.md']
 out=dict(status='PASS',scope=__doc__,cases=16,evidence_sha256=sha(path),production_change=False,
  image_sha256=index['image_sha256'],documents={n:sha(ROOT/n) for n in docs},audit_script_sha256=sha(Path(__file__)))
 (ROOT/'logs/haptics-A1-joined-review-audit.json').write_text(json.dumps(out,indent=2)+'\n')
 print('PASS:16 joined A1/B2 stock cases; physical vibration and complete goal unverified')
if __name__=='__main__':main()
