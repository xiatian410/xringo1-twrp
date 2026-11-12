#!/usr/bin/env python3
"""Audit MTP file timestamp preservation and its current clean image.

Focused current-source/image audit; host filesystem semantics and memory USB
peer do not establish target USB, directory dates, or power-loss behavior.
"""
import hashlib
import json
import os
from pathlib import Path
from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT,TREE,ANDROID,manifest

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads((ROOT/p).read_text())
def bindings(mapping):
    for p,value in mapping.items():assert sha(ROOT/p)==value,p
def report_sources(r):
    for group in ['sources','test_sources','shared_sources','tests']:bindings(r.get(group,{}))

def main():
    index=read('simulation-report.json');image=Path(index['image']);digest=sha(image)
    assert image.name=='recovery-dijun-unified-mtp-upload-time.img' and index['image_sha256']==digest
    evidence=['logs/mtp-upload-time-objects.json','logs/mtp-upload-time-before.json','logs/mtp-upload-time-transfers.json',
              'logs/mtp-upload-time-profile-runtime.json','logs/mtp-upload-time-module-state.json']
    reports={n:read(n) for n in evidence}
    for name,r in reports.items():
        report_sources(r)
        assert r['status']==('FAIL' if name.endswith('before.json') else 'PASS')
    current=reports[evidence[0]];before=reports[evidence[1]];transfers=reports[evidence[2]]
    assert len(current['cases'])==94 and len(before['cases'])==16 and len(transfers['cases'])==48
    labels={'upload-time-'+kind+'-'+case for kind in ['new','overwrite'] for case in
            ['epoch-zero','epoch-offset','pre-epoch','missing','invalid','time-error','receive-error','sync-error']}
    assert {c['case'] for c in current['cases'] if c['case'].startswith('upload-time-')}==labels
    assert {c['case'] for c in before['cases']}==labels
    failed={c['case'] for c in before['cases'] if c['status']=='FAIL'}
    assert failed=={'upload-time-'+kind+'-'+case for kind in ['new','overwrite'] for case in
                    ['epoch-zero','epoch-offset','time-error','receive-error','sync-error']}
    assert all(c['returncode']==1 and 'FAIL ' in c['output'] for c in before['cases'] if c['case'] in failed)
    assert current['test_sources']==before['test_sources']
    for r in [current,transfers]:
        assert all(c['status']=='PASS' and c['returncode']==c.get('expected_returncode',0) for c in r['cases'])
    for name,groups,calls in [(evidence[3],9,102),(evidence[4],4,24)]:
        r=reports[name];assert r['image_sha256']==digest and r['tests_run']==groups and len(r['cases'])==calls
        assert all(c['actual']==c['expected'] for c in r['cases'])
    provenance=read(image.with_name(image.stem+'-sources.json'))
    assert provenance['image_sha256']==digest and provenance['jobs']==30 and len(provenance['files'])==742
    assert provenance['build_command']=='make -j$(nproc) installclean; make -j$(nproc) recoveryimage'
    bindings(provenance['files'])
    for p,target in provenance['symlinks'].items():assert os.readlink(p)==target
    assert manifest(TREE)==manifest(ANDROID/'device/xiaomi/O1_asic')
    log=ROOT/provenance['build_log'];assert sha(log)==provenance['build_log_sha256']
    text=log.read_text();assert text.count('build completed successfully')==2 and 'Deleted images and staging directories' in text
    assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/mtp-upload-time-final-source-recheck.log').read_text()
    baseline=ROOT/'imgs/built/recovery-dijun-unified-otg-discovery.img'
    old=read(baseline.with_name(baseline.stem+'-sources.json'))
    assert sha(baseline)==old['image_sha256']=='031497e53bf500805a2ba6d74b4bc0a9315fbdbc5e6740ec028df33059d27561'
    changed={n for n,v in provenance['files'].items() if old['files'].get(n)!=v}
    assert changed=={str(ANDROID/'bootable/recovery'/n) for n in ['mtp/MtpServer.cpp','mtp/MtpServer.h']}|{str(ANDROID/'device/xiaomi/O1_asic/patches'/n) for n in ['series.json','0049-mtp-upload-timestamp.patch']}
    assert not set(old['files'])-set(provenance['files'])
    metadata=read(image.with_suffix('.json'));previous=read(baseline.with_suffix('.json'))
    assert metadata['sha256']==digest and len(metadata['profiles'])==6
    entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
    for n,v in metadata['binary_hashes'].items():assert hashlib.sha256(entries[n]).hexdigest()==v,n
    for n in ['system/lib64/libgui2.so','system/lib64/libtwrpminui.so']:
        assert previous['binary_hashes'][n]==metadata['binary_hashes'][n],n
    assert previous['binary_hashes']['system/lib64/libtwrpmtp-ffs.so']!=metadata['binary_hashes']['system/lib64/libtwrpmtp-ffs.so']
    # OTG methods and tests are unchanged; retain their explicit old-image
    # association rather than rebrand them as current-image executions.
    inherited=['logs/otg-discovery.json','logs/otg-discovery-before.json','logs/mount-list-chain.json']
    for n in inherited:
        r=read(n);report_sources(r)
        if 'lvgl' in r:bindings(r['lvgl']['source_files'])
        if 'image_sha256' in r:assert r['image_sha256']==old['image_sha256']
    for name in evidence:
        checks=[c for c in index['checks']+index.get('additional_checks',[]) if c.get('evidence')==name]
        assert checks and all(c['evidence_sha256']==sha(ROOT/name) for c in checks),name
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    docs=['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.md','simulation-report.json','docs/MTP-DATETIME-ADAPTATION.md','docs/MTP-ATOMIC-UPLOAD.md','FEATURE-USAGE.md']
    out=dict(status='PASS',scope=__doc__,image=str(image),image_sha256=digest,production_sources=742,
             object_cases=94,new_timestamp_cases=16,old_failed=10,transfer_cases=48,profile_groups=9,module_groups=4,
             inherited_OTG_evidence={n:sha(ROOT/n) for n in inherited},evidence={n:sha(ROOT/n) for n in evidence},
             documents={n:sha(ROOT/n) for n in docs},audit_source_sha256=sha(Path(__file__)))
    (ROOT/'logs/mtp-upload-time-delivery.json').write_text(json.dumps(out,indent=2)+'\n')
    print('PASS: MTP objects94/timestamp16/old failures10;transfer48;742 sources;profile9/module4. Full12-group goal remains in_progress.')
if __name__=='__main__':main()
