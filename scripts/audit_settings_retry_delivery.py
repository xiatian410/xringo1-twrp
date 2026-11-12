#!/usr/bin/env python3
"""Bind failed language/theme apply recovery to sources, clean image and profile replay.

This verifies the named software boundaries only, not device settings or haptics.
"""
import hashlib
import json
from pathlib import Path
from firmware_facts import boot_parts,ramdisk_entries
ROOT=Path(__file__).resolve().parents[1]
SRC=Path('/root/AAA/twrp/bootable/recovery')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return json.loads((ROOT/n).read_text())
def verify_sources(report):
    for group in ['sources','test_sources']:
        for name,digest in report.get(group,{}).items():
            p=Path(name) if Path(name).is_absolute() else (ROOT/'tests'/name if group=='test_sources' else ROOT/name if name.startswith('backups/') else SRC/name)
            assert sha(p)==digest,name

def main():
    index=read('simulation-report.json');image=Path(index['image']);digest=sha(image)
    assert image.name=='recovery-dijun-unified-settings-retry.img' and index['image_sha256']==digest
    before=read('logs/settings-retry-before.json');after=read('logs/settings-retry.json')
    matrix={(k,c) for k in ['language','theme'] for c in ['success','write-failure','flush-failure','retry']}|{('language','decrypt')}
    for r in [before,after]:
        assert len(r['cases'])==9 and {(c['kind'],c['case']) for c in r['cases']}==matrix
        verify_sources(r)
        for n,h in r['lvgl']['source_files'].items():assert sha(Path(n))==h,n
    assert before['status']=='FAIL'
    assert {(c['kind'],c['case']) for c in before['cases'] if c['returncode']}=={(k,c) for k in ['language','theme'] for c in ['flush-failure','retry']}
    assert after['status']=='PASS' and all(c['returncode']==0 for c in after['cases'])
    for n,count in [('logs/settings-retry-row-regression.json',20),('logs/settings-retry-storage-regression.json',21),('logs/settings-retry-haptics-ui-regression.json',21)]:
        r=read(n);assert r['status']=='PASS' and len(r['cases'])==count
        assert all(c['returncode']==0 for c in r['cases']);verify_sources(r)
    assert 'assertions=31 failures=0' in (ROOT/'logs/settings-retry-path-regression.log').read_text()
    provenance=json.loads(image.with_name(image.stem+'-sources.json').read_text())
    assert provenance['image_sha256']==digest and len(provenance['files'])==724 and provenance['jobs']==30
    assert provenance['build_command']=='make -j$(nproc) installclean; make -j$(nproc) recoveryimage'
    for n,h in provenance['files'].items():assert sha(Path(n))==h,n
    for n,target in provenance['symlinks'].items():assert str(Path(n).readlink())==target
    assert sha(ROOT/provenance['build_log'])==provenance['build_log_sha256']
    log=(ROOT/provenance['build_log']).read_text()
    assert log.count('build completed successfully')==2 and 'Deleted images and staging directories' in log
    meta=json.loads(image.with_suffix('.json').read_text());assert meta['sha256']==digest and len(meta['profiles'])==6
    entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
    for n,h in meta['binary_hashes'].items():assert hashlib.sha256(entries[n]).hexdigest()==h,n
    old=read('imgs/built/recovery-dijun-unified-temperature-ui.json')
    assert meta['binary_hashes']['system/lib64/libtwrpminui.so']==old['binary_hashes']['system/lib64/libtwrpminui.so']
    assert meta['binary_hashes']['system/lib64/libgui2.so']!=old['binary_hashes']['system/lib64/libgui2.so']
    runtime=read('logs/settings-retry-profile-runtime.json')
    assert runtime['status']=='PASS' and runtime['tests_run']==9 and len(runtime['cases'])==102 and runtime['image_sha256']==digest
    for group in ['sources','test_sources']:
        for n,h in runtime[group].items():assert sha(Path(n) if Path(n).is_absolute() else ROOT/n)==h,n
    names=['logs/settings-retry.json','logs/settings-retry-row-regression.json','logs/settings-retry-storage-regression.json','logs/settings-retry-haptics-ui-regression.json','logs/settings-retry-profile-runtime.json']
    for n in names:
        c,=[c for c in index['checks'] if c['evidence']==n]
        assert c['result']=='pass' and c['evidence_sha256']==sha(ROOT/n)
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    evidence=names+['logs/settings-retry-before.json','logs/settings-retry-path-regression.log','logs/settings-retry-final-source-recheck.log','logs/verify-settings-retry.log']
    result=dict(status='PASS',scope=__doc__,image_sha256=digest,sources=724,callback_cases=9,before_failures=4,row_cases=20,storage_cases=21,path_assertions=31,runtime_groups=9,runtime_calls=102,
        evidence={n:sha(ROOT/n) for n in evidence},documents={n:sha(ROOT/n) for n in ['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.md','simulation-report.json','docs/SETTINGS-ADAPTATION.md','FEATURE-USAGE.md']},audit_script_sha256=sha(Path(__file__)))
    (ROOT/'logs/settings-retry-delivery.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: language/theme retry9; previous4 failures; row20/storage21/path31;724 sources;runtime9/102. Device settings and vibration unresolved.')

if __name__=='__main__':main()
