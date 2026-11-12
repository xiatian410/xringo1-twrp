#!/usr/bin/env python3
"""Bind updater IPC hardening and image-route checks to the clean candidate.

Focused host/thread/IPC and source delivery; full ZIP/OTA/sideload and hardware
acceptance remain incomplete. Independent tests are not one end-to-end install.
"""
import hashlib
import json
import os
import subprocess
from pathlib import Path
from firmware_facts import boot_parts,ramdisk_entries
from sync_device_tree import ROOT,TREE,ANDROID,manifest

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads((ROOT/p).read_text())
def bindings(values):
    for p,h in values.items():assert sha(ROOT/p)==h,p

def main():
    index=read('simulation-report.json');image=Path(index['image']);digest=sha(image)
    assert image.name=='recovery-dijun-unified-updater-protocol.img' and index['image_sha256']==digest
    evidence=['logs/image-install-chain.json','logs/zip-updater.json','logs/zip-updater-before.json',
              'logs/updater-protocol-profile-runtime.json','logs/updater-protocol-module-state.json']
    reports=[read(p) for p in evidence]
    for p,r in zip(evidence,reports):
        assert r['status']==('FAIL' if p.endswith('before.json') else 'PASS')
        for key in ['sources','tests','test_sources']:bindings(r.get(key,{}))
    chain,current,before,profile,module=reports
    assert len(chain['cases'])==40 and all(c['exit']==0 and c['content_ok'] and c['order_ok'] for c in chain['cases'])
    for ab in [False,True]:
        rows={c['case']:c for c in chain['cases'] if c['ab_build']==ab};assert len(rows)==20
        assert rows['initial-B']['expected_written']==(['boot_b','boot_a'] if ab else ['boot_b'])
        assert rows['first-write-error']['expected_written']==[]
        assert rows['second-write-error']['expected_written']==(['boot_a'] if ab else ['boot_a'])
        assert rows['second-sync-error']['expected_written']==(['boot_a','boot_b'] if ab else ['boot_a'])
        assert rows['unknown-target']['expected_written']==[] and rows['multiple-targets']['expected_written']==[]
    assert len(current['cases'])==len(before['cases'])==22
    failed={c['case'] for c in before['cases'] if c['status']=='FAIL'}
    assert failed=={'missing-fraction','missing-seconds','missing-set','nan','infinite','negative','too-large',
                    'bad-number','bad-seconds','negative-seconds','huge-seconds','log-empty','pipe-error','fdopen-error'}
    assert all(c['exit']==0 for c in current['cases'])
    for n in ['tests/zip_updater_test.py','tests/zip_updater_test.cpp','tests/zip_updater_fixture.cpp']:
        assert current['sources'][str(ROOT/n)]==before['sources'][str(ROOT/n)]
    for r,g,n in [(profile,9,102),(module,4,24)]:
        assert r['image_sha256']==digest and r['tests_run']==g and len(r['cases'])==n
        assert all(c['actual']==c['expected'] for c in r['cases'])
    provenance=read(image.with_name(image.stem+'-sources.json'));bindings(provenance['files'])
    assert provenance['image_sha256']==digest and len(provenance['files'])==749 and provenance['jobs']==30
    assert provenance['build_command']=='make -j$(nproc) installclean; make -j$(nproc) recoveryimage'
    for p,value in provenance['symlinks'].items():assert os.readlink(p)==value
    log=ROOT/provenance['build_log'];assert sha(log)==provenance['build_log_sha256']
    assert log.read_text().count('build completed successfully')==2
    assert 'Deleted images and staging directories' in log.read_text()
    assert manifest(TREE)==manifest(ANDROID/'device/xiaomi/O1_asic')
    assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/updater-protocol-final-source-recheck.log').read_text()
    previous=ROOT/'imgs/built/recovery-dijun-unified-sparse-flash.img'
    prior=read(previous.with_name(previous.stem+'-sources.json'));assert sha(previous)==prior['image_sha256']
    assert {p for p,h in provenance['files'].items() if prior['files'].get(p)!=h}=={
        str(ANDROID/'bootable/recovery/twrpinstall/twinstall.cpp'),
        str(ANDROID/'device/xiaomi/O1_asic/patches/0052-updater-protocol-validation.patch'),
        str(ANDROID/'device/xiaomi/O1_asic/patches/series.json')}
    spec=read(TREE/'patches/series.json')['repositories']['bootable/recovery']
    original=subprocess.check_output(['git','-C',str(ANDROID/'bootable/recovery'),'show',spec['commit']+':twrpinstall/twinstall.cpp'])
    assert hashlib.sha256(original).hexdigest()==sha(ROOT/'logs/zip-updater-before/twinstall.cpp')
    metadata=read(image.with_suffix('.json'));old_meta=read(previous.with_suffix('.json'))
    assert metadata['sha256']==digest and len(metadata['profiles'])==6
    entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
    for p,h in metadata['binary_hashes'].items():assert hashlib.sha256(entries[p]).hexdigest()==h
    for n in ['Invalid updater progress command','Invalid updater set_progress command',
              'Unable to create updater pipe:','Unable to open updater output stream:']:
        assert n.encode() in entries['system/bin/recovery']
    for n in ['system/lib64/libgui2.so','system/lib64/libtwrpminui.so','system/lib64/libtwrpmtp-ffs.so']:
        assert metadata['binary_hashes'][n]==old_meta['binary_hashes'][n],n
    inherited=['logs/sparse-flash.json','logs/sparse-flash-raw-regression.json']
    for p in inherited:
        r=read(p);assert r['status']=='PASS'
        for k in ['sources','test_sources']:bindings(r.get(k,{}))
    for p in evidence:
        checks=[c for c in index['additional_checks'] if c.get('evidence')==p]
        assert checks and all(c['evidence_sha256']==sha(ROOT/p) for c in checks)
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    docs=['ADAPTATION-GOALS.md','MAINTENANCE.md','FEATURE-USAGE.md','simulation-report.md',
          'simulation-report.json','docs/INSTALL-CHAIN-VALIDATION.md']
    result=dict(status='PASS',scope=__doc__,image=str(image),image_sha256=digest,production_sources=749,
                image_route_cases=40,updater_cases=22,old_failures=14,profile_groups=9,module_groups=4,
                evidence={p:sha(ROOT/p) for p in evidence},inherited_sources_verified={p:sha(ROOT/p) for p in inherited},
                documents={p:sha(ROOT/p) for p in docs},audit_source_sha256=sha(Path(__file__)),
                limitations='Separate host suites; no full ZIP/signature/digest/OTA payload/sideload/FUSE/USB/GUI/physical-slot or power-loss acceptance.')
    (ROOT/'logs/updater-protocol-delivery.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: image-route40;updater22/old failures14;749 sources;profile9/module4. Full12-group goal remains incomplete.')

if __name__=='__main__':main()
