#!/usr/bin/env python3
"""Bind independent stock wave inventory to original parser and CUSTOM worker."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 path=ROOT/'logs/haptics-stock-wave-review.json';r=json.loads(path.read_text());assert r['status']=='PASS' and len(r['cases'])==10
 for group in ['sources','tests','emulator_files']:
  for name,h in r[group].items():
   p=Path(name) if Path(name).is_absolute() else ROOT/name;assert sha(p)==h,name
 labels={'stock-long31','last-wave42','outside43','empty-count','count-read-error'}
 for sample in ['os4-current','os4-stable']:
  cases={c['case']:c for c in r['cases'] if c['sample']==sample};assert set(cases)==labels
  for label,c in cases.items():
   assert c['status']=='PASS' and c['stock_wave_count']==43 and c['long_id']==31
   inv=c['wave_inventory'];assert inv['payload_size']==8104 and inv['terminator_index']==43 and inv['records']==c['parsed_records'] and len(inv['records'])==43
   assert inv['records'][31]['type']==12 and inv['records'][31]['offset']==1916 and inv['records'][31]['length']==7
   reads=c['count_reads'];assert len(reads)==(20 if label=='count-read-error' else 2 if label in ['stock-long31','last-wave42'] else 1)
   assert all(v['address']==0x2802140 and v['result']==(-5 if label=='count-read-error' else 0) for v in reads)
   expected={'stock-long31':0,'last-wave42':0,'outside43':-22,'empty-count':-61,'count-read-error':-62}[label];assert c['upload_result']==expected
   if expected==0:
    selected=31 if label=='stock-long31' else 42
    assert c['selected']==selected and c['mailbox']==[dict(command=0x1000000+selected,result=0)]
    assert [(w['address'],w['value'],w['result']) for w in c['writes']]==[(0x2802134,0,0),(0x28059f0,0,0)]
   else:assert not c['mailbox'] and not c['writes']
 index=json.loads((ROOT/'simulation-report.json').read_text());check,=[c for c in index['checks'] if c['name']=='stock-ARM64-OS4-haptics-stock-wave-table']
 assert check['count']==10 and check['evidence_sha256']==sha(path)
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 assert sha(Path(index['image']))==index['image_sha256']
 out=dict(status='PASS',scope=__doc__,cases=10,evidence_sha256=sha(path),production_change=False,image_sha256=index['image_sha256'],documents={n:sha(ROOT/n) for n in ['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.json','simulation-report.md','docs/HAPTICS-ADAPTATION.md']},audit_script_sha256=sha(Path(__file__)))
 (ROOT/'logs/haptics-stock-wave-review-audit.json').write_text(json.dumps(out,indent=2)+'\n');print('PASS:10 stock43-wave/parser/CUSTOM cases; no DSP or motor result')
if __name__=='__main__':main()
