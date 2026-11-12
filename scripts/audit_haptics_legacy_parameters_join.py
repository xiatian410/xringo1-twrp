#!/usr/bin/env python3
"""Bind original OS2/OS3 parameter loader error semantics to exact OTA inputs."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 path=ROOT/'logs/haptics-legacy-parameters-join.json';r=json.loads(path.read_text())
 assert r['status']=='PASS' and r['count']==len(r['cases'])==48
 for group in ['sources','tests','emulator_files']:
  for name,h in r[group].items():
   p=Path(name) if Path(name).is_absolute() else ROOT/name;assert sha(p)==h,name
 labels={'stock-parameters','main-missing','main-header-invalid','main-first-write-error','svc-first-write-error','loader-allocation-error'}
 for sample in ['os2-initial','os2-final','os3-initial','os3-final']:
  for fw in ['cs40l26.wmfw','cs40l26-calib.wmfw']:
   normal=fw=='cs40l26.wmfw';cases={c['case']:c for c in r['cases'] if c['sample']==sample and c['firmware']==fw};assert set(cases)==labels
   names=['cs40l26.bin','cs40l26-svc.bin','cs40l26-dvl.bin']+(['cs40l26-a2h.bin','cs40l26-dbc.bin'] if normal else ['cs40l26-calib.bin'])
   for label,c in cases.items():
    assert c['status']=='PASS' and c['loader_result']==(-12 if label=='loader-allocation-error' else 0)
    assert c['requests']==([] if label=='loader-allocation-error' else names)
    results=[]
    for n in c['requests']:
     if label=='main-missing' and n=='cs40l26.bin':continue
     code=-22 if label=='main-header-invalid' and n=='cs40l26.bin' else -5 if (label=='main-first-write-error' and n=='cs40l26.bin') or (label=='svc-first-write-error' and n=='cs40l26-svc.bin') else 0
     results.append(dict(file=n,result=code))
    assert c['parser_results']==results and len(c['released'])==len(results)
    total=34 if normal else 28
    assert len(c['raw_writes'])==({'stock-parameters':total,'main-missing':total-5,'main-header-invalid':total-5,'main-first-write-error':total-4,'svc-first-write-error':total-20,'loader-allocation-error':0}[label])
    if label in ['main-missing','main-header-invalid','main-first-write-error','svc-first-write-error']:assert any('Continuing' in w for w in c['warnings'])
    if not normal and label=='stock-parameters':assert len(c['warnings'])==3 and all('Coeff. rev.' in w for w in c['warnings'])
 index=json.loads((ROOT/'simulation-report.json').read_text());check,=[c for c in index['checks'] if c['name']=='stock-ARM64-legacy-parameter-loader-join']
 assert check['evidence_sha256']==sha(path) and check['count']==48
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 assert sha(Path(index['image']))==index['image_sha256']
 out=dict(status='PASS',scope=__doc__,cases=48,profiles=4,evidence_sha256=sha(path),image_sha256=index['image_sha256'],production_change=False,documents={n:sha(ROOT/n) for n in ['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.json','simulation-report.md','docs/HAPTICS-ADAPTATION.md']},audit_script_sha256=sha(Path(__file__)))
 (ROOT/'logs/haptics-legacy-parameters-join-audit.json').write_text(json.dumps(out,indent=2)+'\n');print('PASS:48 original legacy loader/parameter cases; loader0 can mask parameter errors; motor unknown')
if __name__=='__main__':main()
