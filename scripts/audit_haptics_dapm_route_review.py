#!/usr/bin/env python3
"""Audit original DAPM topology/event evidence; not a physical vibration verdict."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    path=ROOT/'logs/haptics-dapm-route-review.json'
    report=json.loads(path.read_text())
    assert report['status']=='PASS' and len(report['cases'])==20
    for group in ['sources','tests','emulator_files']:
        assert report[group]
        for name,digest in report[group].items():assert sha(ROOT/name)==digest,name
    for sample in ['os4-current','os4-stable']:
        topology=report['topologies'][sample]
        assert topology['source_values']==['Off','PCM','A2H']
        assert topology['setter']=='snd_soc_dapm_put_enum_double'
        assert topology['register']==0xffffffff and len(topology['routes'])==10
        assert ['Haptics Source','PCM','PCM'] in topology['routes']
        assert ['Haptics Source','A2H','A2H'] in topology['routes']
        assert all('Off'!=route[1] for route in topology['routes'])
        cases={c['case']:c for c in report['cases'] if c['sample']==sample}
        assert len(cases)==10 and all(c['status']=='PASS' for c in cases.values())
        assert all(cases[n]['result']==0 for n in ['A1-up','A1-down','B2-up-SVC0','B2-up-SVC1','B2-down-restore-SVC','B2-down-keep-SVC'])
        assert not cases['A1-up']['reads'] and len(cases['A1-up']['updates'])==3
        zero=cases['B2-up-SVC0'];one=cases['B2-up-SVC1']
        assert len(zero['updates'])==4 and len(one['updates'])==3
        assert zero['SVC_restore_flag']==1 and one['SVC_restore_flag']==0
        flags=zero['reads'][0]['address']
        assert zero['updates'][-1]==dict(address=flags,mask=5,value=5,result=0)
        down=cases['B2-down-restore-SVC']
        assert down['updates'][0]==dict(address=flags,mask=5,value=0,result=0)
        assert down['mailbox']==[dict(value=0x3000003,result=0)]
        for label,count in [('up-first-register-error',1),('up-second-register-error',2)]:
            c=cases[label];assert c['result']==-5 and len(c['updates'])==count
            assert c['updates'][-1]['result']==-5 and not c['mailbox']
        c=cases['down-mailbox-error'];assert c['result']==-5 and not c['updates']
        assert c['mailbox']==[dict(value=0x3000003,result=-5)]
        c=cases['invalid-event'];assert c['result']==-22 and not c['updates'] and not c['mailbox']
    index=json.loads((ROOT/'simulation-report.json').read_text())
    check,=[c for c in index['checks'] if c['name']=='stock-ARM64-OS4-haptics-DAPM-topology']
    assert check['count']==20 and check['evidence_sha256']==sha(path)
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    assert sha(Path(index['image']))==index['image_sha256']
    docs=['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.json','simulation-report.md','docs/HAPTICS-ADAPTATION.md']
    result=dict(status='PASS',scope=__doc__,cases=20,evidence_sha256=sha(path),
                image_sha256=index['image_sha256'],production_change=False,
                documents={n:sha(ROOT/n) for n in docs},audit_script_sha256=sha(Path(__file__)))
    (ROOT/'logs/haptics-dapm-route-review-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS:20 PCM widget cases/ELF routing/hash/index; physical vibration unresolved')

if __name__=='__main__':main()
