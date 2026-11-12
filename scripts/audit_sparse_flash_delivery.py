#!/usr/bin/env python3
"""Bind sparse-capacity/commit checks to the clean candidate; not full install acceptance."""
import hashlib
import json
import os
from pathlib import Path
from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT,TREE,ANDROID,manifest

def sha(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def read(p): return json.loads((ROOT/p).read_text())
def bindings(values):
    for p,h in values.items(): assert sha(ROOT/p)==h,p

def main():
    index=read('simulation-report.json');image=Path(index['image']);digest=sha(image)
    assert image.name=='recovery-dijun-unified-sparse-flash.img' and index['image_sha256']==digest
    evidence=['logs/sparse-flash.json','logs/sparse-flash-before.json',
              'logs/sparse-flash-raw-regression.json','logs/sparse-flash-profile-runtime.json',
              'logs/sparse-flash-module-state.json']
    reports=[read(p) for p in evidence]
    for n,r in zip(evidence,reports):
        for key in ['sources','test_sources','tests']: bindings(r.get(key,{}))
        assert r['status']==('FAIL' if n.endswith('before.json') else 'PASS'),n
    current,before,raw,profile,modules=reports
    assert len(current['cases'])==len(before['cases'])==40
    assert sum(c['status']=='FAIL' for c in before['cases'])==27
    for name in ['tests/sparse_flash_test.py','tests/sparse_flash_test.cpp']:
        assert current['sources'][str(ROOT/name)]==before['sources'][str(ROOT/name)]
    assert all(c['exit']==0 and c['content_ok'] for c in current['cases'])
    for enabled in [False,True]:
        group=[c for c in current['cases'] if c['discard_build']==enabled]
        assert len(group)==20
        required={'expanded-oversize','actual-small','sync-error','close-error','write-late-error','write-eintr','write-short'}
        assert required<={c['case'] for c in group}
        over=next(c for c in group if c['case']=='expanded-oversize')
        assert over['input_size']==44 and over['expanded_size']==65536 and over['target_size']==32768
        for c in group:
            if c['case'] in required-{'write-late-error','write-eintr','write-short'}:
                assert 'result=0' in c['output']
    assert len(raw['cases'])==65 and all(c['status']=='PASS' for c in raw['cases'])
    for r,g,n in [(profile,9,102),(modules,4,24)]:
        assert r['image_sha256']==digest and r['tests_run']==g and len(r['cases'])==n
        assert all(c['actual']==c['expected'] for c in r['cases'])
    prov=read(image.with_name(image.stem+'-sources.json'));bindings(prov['files'])
    assert prov['image_sha256']==digest and len(prov['files'])==747 and prov['jobs']==30
    assert prov['build_command']=='make -j$(nproc) installclean; make -j$(nproc) recoveryimage'
    for p,value in prov['symlinks'].items(): assert os.readlink(p)==value
    log=ROOT/prov['build_log'];assert sha(log)==prov['build_log_sha256']
    assert log.read_text().count('build completed successfully')==2
    assert 'Deleted images and staging directories' in log.read_text()
    assert manifest(TREE)==manifest(ANDROID/'device/xiaomi/O1_asic')
    assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/sparse-flash-final-source-recheck.log').read_text()
    old_image=ROOT/'imgs/built/recovery-dijun-unified-ce-cleanup.img'
    old_prov=read(old_image.with_name(old_image.stem+'-sources.json'))
    assert sha(old_image)==old_prov['image_sha256']
    assert {p for p,h in prov['files'].items() if old_prov['files'].get(p)!=h}=={
        str(ANDROID/'bootable/recovery/partition.cpp'),
        str(ANDROID/'device/xiaomi/O1_asic/patches/0051-sparse-image-capacity-and-commit.patch'),
        str(ANDROID/'device/xiaomi/O1_asic/patches/series.json')}
    assert sha(ROOT/'logs/sparse-flash-before/partition.cpp')==old_prov['files'][str(ANDROID/'bootable/recovery/partition.cpp')]
    meta=read(image.with_suffix('.json'));old_meta=read(old_image.with_suffix('.json'))
    assert meta['sha256']==digest and len(meta['profiles'])==6
    entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
    for p,h in meta['binary_hashes'].items(): assert hashlib.sha256(entries[p]).hexdigest()==h
    for name in ['Sparse image expanded size is empty or exceeds partition size',
                 'Sparse image target is not a block device','Sparse image output sync failed:',
                 'Sparse image output close failed:']:
        assert name.encode() in entries['system/bin/recovery']
    for name in ['system/lib64/libgui2.so','system/lib64/libtwrpminui.so','system/lib64/libtwrpmtp-ffs.so']:
        assert meta['binary_hashes'][name]==old_meta['binary_hashes'][name],name
    for p in evidence:
        checks=[c for c in index['additional_checks'] if c.get('evidence')==p]
        assert checks and all(c['evidence_sha256']==sha(ROOT/p) for c in checks)
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    docs=['ADAPTATION-GOALS.md','MAINTENANCE.md','FEATURE-USAGE.md','simulation-report.md','simulation-report.json','docs/INSTALL-CHAIN-VALIDATION.md']
    result=dict(status='PASS',scope=__doc__,image=str(image),image_sha256=digest,production_sources=747,
                sparse_cases=40,old_failures=27,raw_regression_cases=65,profile_groups=9,module_groups=4,
                evidence={p:sha(ROOT/p) for p in evidence},documents={p:sha(ROOT/p) for p in docs},
                audit_source_sha256=sha(Path(__file__)),
                limitations='Host files with block/ioctl/discard boundaries; no full manager/GUI/slot/ZIP/sideload, CRC authentication, USB, ARM64 sparse execution or physical power-loss proof.')
    (ROOT/'logs/sparse-flash-delivery.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: sparse40/old failures27;raw65;747 sources;profile9/module4. Full12-group goal remains incomplete.')

if __name__=='__main__': main()
