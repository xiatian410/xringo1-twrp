#!/usr/bin/env python3
"""Check original protection IRQ request sequences; hardware remains unverified."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    path=ROOT/'logs/haptics-protection-irq-review.json';r=json.loads(path.read_text())
    assert r['status']=='PASS' and len(r['cases'])==44
    for group in ['sources','tests','emulator_files']:
        assert r[group]
        for name,digest in r[group].items():assert sha(ROOT/name)==digest,name
    handlers={'cs40l26_bst_ovp_err':3,'cs40l26_bst_uv_err':4,'cs40l26_bst_short':2,'cs40l26_amp_short':1}
    for sample in ['os4-current','os4-stable']:
        cases={(c['handler'],c['case']):c for c in r['cases'] if c['sample']==sample}
        assert len(cases)==22
        for handler,bit in handlers.items():
            for label in ['success','read-error','write1-error','write2-error','write3-error']:
                c=cases[handler,label];assert c['status']=='PASS' and c['result']==int(label=='success')
                assert c['error_release_bit']==bit and len(c['reads'])==1
                value=c['initial_register_fixture'];sequence=[value&~(1<<bit),value|(1<<bit),value&~(1<<bit)]
                length=0 if label=='read-error' else int(label[5]) if label.startswith('write') else 3
                assert [w['value'] for w in c['writes']]==sequence[:length]
                assert all(w['address']==0x2034 for w in c['writes'])
                assert c['reads'][0]['result']==(-5 if label=='read-error' else 0)
                if label.startswith('write'):assert c['writes'][-1]['result']==-5
        for handler in ['cs40l26_vbbr_flag','cs40l26_vbst_att_clr']:
            c=cases[handler,'log-only'];assert c['result']==1 and not c['reads'] and not c['writes']
            assert len(c['logs'])==1
    index=json.loads((ROOT/'simulation-report.json').read_text())
    check,=[c for c in index['checks'] if c['name']=='stock-ARM64-OS4-haptics-protection-IRQ']
    assert check['count']==44 and check['evidence_sha256']==sha(path)
    assert index['status']=='in_progress' and sha(Path(index['image']))==index['image_sha256']
    docs=['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.json','simulation-report.md','docs/HAPTICS-ADAPTATION.md']
    output=dict(status='PASS',scope=__doc__,cases=44,evidence_sha256=sha(path),
                image_sha256=index['image_sha256'],production_change=False,
                documents={n:sha(ROOT/n) for n in docs},audit_script_sha256=sha(Path(__file__)))
    (ROOT/'logs/haptics-protection-irq-review-audit.json').write_text(json.dumps(output,indent=2)+'\n')
    print('PASS:44 original protection handler cases; no brownout root-cause or motor claim')
if __name__=='__main__':main()
