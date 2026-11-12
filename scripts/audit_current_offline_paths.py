#!/usr/bin/env python3
"""Bind current-image mount presentation, settings navigation and repair tool evidence.

This verifies evidence identity and the specific host boundaries, not full
task completion, real mounting, device settings, touch or motor output.
"""
import hashlib
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads((ROOT/path).read_text())

def verify_map(mapping):
    for name,expected in mapping.items():
        path=Path(name)
        if not path.is_absolute():path=ROOT/path
        assert sha(path)==expected,name

def main():
    index=read('simulation-report.json');image=Path(index['image'])
    assert sha(image)==index['image_sha256']
    provenance=json.loads(image.with_name(image.stem+'-sources.json').read_text())
    assert provenance['image_sha256']==index['image_sha256']
    verify_map(provenance['files'])
    for name,target in provenance['symlinks'].items():assert os.readlink(name)==target,name
    reports={}
    for name,count in [('logs/settings-navigation.json',45),('logs/mount-list-chain.json',5),
                       ('logs/repair-tool-chain.json',7)]:
        report=read(name);reports[name]=report
        assert report['status']=='PASS' and len(report['cases'])==count,name
        if 'image_sha256' in report:assert report['image_sha256']==index['image_sha256']
        verify_map(report['sources'])
        if 'lvgl' in report:verify_map(report['lvgl']['source_files'])
        for source,digest in report['sources'].items():
            if source in provenance['files']:assert digest==provenance['files'][source],source
    navigation=reports['logs/settings-navigation.json']
    assert {(c['index'],c['mode']) for c in navigation['cases']}=={
        (i,m) for i in range(9) for m in ['label','detail','arrow','blank','drag-out']}
    assert all(c['returncode']==0 for c in navigation['cases'])
    mount=reports['logs/mount-list-chain.json']
    assert {c['case'] for c in mount['cases']}=={'normal','absent-nv','duplicate-input-names','data-absent','remove-readd'}
    assert all(c['returncode']==0 for c in mount['cases'])
    rows={c['case']:c for c in mount['cases']}
    assert 'mount_rows=20 storage_rows=3 internal_labels=1' in rows['normal']['stdout']
    assert 'mount_rows=20 storage_rows=3 internal_labels=19' in rows['duplicate-input-names']['stdout']
    assert 'mount_rows=19 storage_rows=2 internal_labels=1' in rows['data-absent']['stdout']
    repair=reports['logs/repair-tool-chain.json']
    cases={c['case']:c for c in repair['cases']}
    assert set(cases)=={'clean','corrected','invalid','missing-checker','unmount-denied','unknown-target','child-invalid'}
    assert all(c['status']=='PASS' and all(c['checks'].values()) for c in cases.values())
    assert cases['corrected']['actual_wait_status']==[256]
    assert cases['child-invalid']['actual_wait_status']==[0,2048]
    assert cases['corrected']['checks']['independent_content_readback']
    inventory=read('logs/shipped-mount-inventory.json')
    assert inventory['image_sha256']==index['image_sha256']
    assert [inventory[k] for k in ['declarations','unique_mount_points','alternate_filesystem_groups','non_raw_mount_declarations']]==[32,22,10,19]
    verify_map(inventory['sources'])
    stock_nv=read('logs/stock-nv-fstab-audit.json')
    assert stock_nv['status']=='PASS' and len(stock_nv['cases'])==12
    verify_map(stock_nv['sources'])
    assert {(c['sample'],c['kind']) for c in stock_nv['cases']}=={
        (s,k) for s in ['os2-initial','os2-final','os3-initial','os3-final','os4-current','os4-stable']
        for k in ['recovery','vendor_boot']}
    assert all(c['status']=='PASS' and c['exact_maintained_field_match'] and len(c['rows'])==6
               for c in stock_nv['cases'])
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    paths=[*reports,'logs/shipped-mount-inventory.json','logs/stock-nv-fstab-audit.json']
    checks={c['evidence']:c for c in index['additional_checks']}
    for name,count in [('logs/settings-navigation.json',45),('logs/mount-list-chain.json',5),('logs/repair-tool-chain.json',7)]:
        assert checks[name]['count']==count and checks[name]['evidence_sha256']==sha(ROOT/name)
    assert checks['logs/stock-nv-fstab-audit.json']['count']==12
    assert checks['logs/stock-nv-fstab-audit.json']['evidence_sha256']==sha(ROOT/'logs/stock-nv-fstab-audit.json')
    result=dict(status='PASS',scope=__doc__,image_sha256=index['image_sha256'],
                production_source_files=len(provenance['files']),production_changed=False,
                evidence={n:sha(ROOT/n) for n in paths},
                index_sha256=sha(ROOT/'simulation-report.json'),audit_script_sha256=sha(Path(__file__)))
    (ROOT/'logs/current-offline-paths-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: current image/source bindings; settings-navigation45, mount-list5, repair-tool7, stock-NV12; hardware/full goal unverified.')

if __name__=='__main__':main()
