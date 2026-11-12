#!/usr/bin/env python3
"""Bind actual-image firmware publication evidence to original ODM parameters."""
import hashlib
import json
from pathlib import Path
from firmware_facts import boot_parts,ramdisk_entries
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    path=ROOT/'logs/haptics-firmware-publication.json';r=json.loads(path.read_text())
    assert r['status']=='PASS' and len(r['cases'])==12
    for group in ['sources','tests','emulator_files']:
        assert r[group]
        for name,digest in r[group].items():assert sha(ROOT/name)==digest,name
    index=json.loads((ROOT/'simulation-report.json').read_text());image=Path(index['image'])
    assert sha(image)==index['image_sha256']==r['image_sha256']
    entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
    for name,digest in r['shipped_scripts'].items():assert hashlib.sha256(entries[name]).hexdigest()==digest
    samples={p.parent.name for p in (ROOT/'dtsrc/O1_asic_dual/profiles').glob('*/profile.json')}
    assert {(c['sample'],c['slot']) for c in r['cases']}=={(s,slot) for s in samples for slot in ['_a','_b']}
    for c in r['cases']:
        assert c['status']=='PASS' and c['stock_firmware_removed'] and c['firmware_path']=='/lib/firmware'
        assert len(c['verified_files'])==9
        prefix='system/etc/dijun/profiles/'+c['sample']+'/'
        plan=[line.split()[0] for line in entries[prefix+'modules.plan'].decode().splitlines() if line.strip()]
        observations=c['module_boundary_observations']
        assert [o['module'] for o in observations]==plan
        for observation in observations:assert observation['files']==c['verified_files']
        for name,digest in c['verified_files'].items():
            assert hashlib.sha256(entries['system/etc/dijun/blobs/'+digest]).hexdigest()==digest
            assert sha(ROOT/'firmware/samples'/c['sample']/'analysis/odm/firmware'/name)==digest
    for sample in ['os4-current','os4-stable']:
        d=r['parameter_differences'][sample];order=d['firmware_directories']
        assert order.index('/odm/firmware/')<order.index('/vendor/firmware/')
        assert len(d['differences']['cs40l26-a2h.bin'])==8
        dbc=d['differences']['cs40l26-dbc.bin'];assert len(dbc)==2
        assert {x['coefficient_names'][0] for x in dbc}=={'DBC_RISE_HEADROOM','DBC_FALL_HEADROOM'}
    check,=[c for c in index['checks'] if c['name']=='haptics-actual-image-firmware-publication']
    assert check['count']==12 and check['evidence_sha256']==sha(path)
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    docs=['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.json','simulation-report.md','docs/HAPTICS-ADAPTATION.md']
    output=dict(status='PASS',scope=__doc__,activations=12,
                module_boundaries=sum(len(c['module_boundary_observations']) for c in r['cases']),
                evidence_sha256=sha(path),image_sha256=r['image_sha256'],production_change=False,
                documentation={n:sha(ROOT/n) for n in docs},audit_script_sha256=sha(Path(__file__)))
    (ROOT/'logs/haptics-firmware-publication-audit.json').write_text(json.dumps(output,indent=2)+'\n')
    print('PASS:12 actual-image profile/slot firmware activations; all nine ODM files at insertion boundaries; motor unverified')
if __name__=='__main__':main()
