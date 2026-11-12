#!/usr/bin/env python3
"""Audit OS2/OS3 exact-firmware parser/resolver/production FF join evidence."""
import hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 path=ROOT/'logs/haptics-legacy-firmware-join.json';r=json.loads(path.read_text())
 assert r['status']=='PASS' and r['count']==len(r['cases'])==60
 for group in ['sources','tests','emulator_files']:
  for n,h in r[group].items():
   p=Path(n) if Path(n).is_absolute() else ROOT/n;assert sha(p)==h,n
 effect=bytes.fromhex(r['production_effect']);assert len(effect)==48
 assert struct.unpack_from('<Hh',effect)==(81,7)
 assert struct.unpack_from('<H',effect,10)==(80,)
 assert struct.unpack_from('<HHh',effect,16)==(90,8,64)
 labels={'stock-parser','parser-only','table-read-error','firmware-write-error','invalid-header'}
 joined={'production-upload','first-coefficient-write-error','second-coefficient-write-error','third-coefficient-write-error','missing-buzz-coefficient'}
 for sample in ['os2-initial','os2-final','os3-initial','os3-final']:
  for fw in ['cs40l26.wmfw','cs40l26-calib.wmfw']:
   cases={c['case']:c for c in r['cases'] if c['sample']==sample and c['firmware']==fw}
   assert set(cases)==(labels|joined if fw=='cs40l26.wmfw' else labels)
   for label,c in cases.items():
    assert c['status']=='PASS'
    assert c['parser_result']==(-5 if label in ['table-read-error','firmware-write-error'] else -22 if label=='invalid-header' else 0)
    assert c['coefficient_count']==(0 if label in ['invalid-header','firmware-write-error'] else 525 if fw=='cs40l26.wmfw' else 428)
    assert len(c['raw_writes'])==(0 if label in ['parser-only','invalid-header'] else 1 if label=='firmware-write-error' else 34 if fw=='cs40l26.wmfw' else 35)
    if label not in joined:assert c['joined'] is None;continue
    j=c['joined'];assert j['coefficient_registers']==[0x280701c,0x2807014,0x2807018]
    n={'first-coefficient-write-error':1,'second-coefficient-write-error':2,'third-coefficient-write-error':3}.get(label,0)
    assert j['result']==(-14 if label=='missing-buzz-coefficient' else -5 if n else 0)
    assert j['resolver_calls']==(1 if label=='missing-buzz-coefficient' else n or 3)
    expected=[dict(address=a,value=v,result=-5 if i==n else 0) for i,(a,v) in enumerate(zip(j['coefficient_registers'],[20,125,64]),1)]
    assert j['writes']==([] if label=='missing-buzz-coefficient' else expected[:n or None])
    assert j['pm_fixture_calls']==1
 index=json.loads((ROOT/'simulation-report.json').read_text());check,=[c for c in index['checks'] if c['name']=='stock-ARM64-legacy-firmware-resolver-FF-join']
 assert check['count']==60 and check['evidence_sha256']==sha(path)
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 image=Path(index['image']);assert sha(image)==index['image_sha256']
 out=dict(status='PASS',scope=__doc__,cases=60,profiles=4,evidence_sha256=sha(path),image_sha256=index['image_sha256'],production_change=False,documents={n:sha(ROOT/n) for n in ['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.json','simulation-report.md','docs/HAPTICS-ADAPTATION.md']},audit_script_sha256=sha(Path(__file__)))
 (ROOT/'logs/haptics-legacy-firmware-join-audit.json').write_text(json.dumps(out,indent=2)+'\n')
 print('PASS:60 legacy firmware/parser/resolver/upload joins; no DSP/physical motor result')
if __name__=='__main__':main()
