#!/usr/bin/env python3
"""Bind failed-decrypt CE cleanup, original vold lifecycle and the clean image.

Host control/cache semantics only: key derivation, filesystem preparation,
install/evict ioctls and mounts are fixtures. No parent-bound profile unlock,
real key eviction, full remount, synchronous Binder cancellation or hardware.
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
def read(n):return json.loads((ROOT/n).read_text())
def bindings(m):
    for n,v in m.items():assert sha(ROOT/n)==v,n
def source_bindings(r):
    for k in ['sources','tests','test_sources','shared_sources']:bindings(r.get(k,{}))

def main():
    index=read('simulation-report.json');image=Path(index['image']);digest=sha(image)
    assert image.name=='recovery-dijun-unified-ce-cleanup.img' and index['image_sha256']==digest
    names=['logs/ce-lifecycle.json','logs/ce-lifecycle-before.json','logs/ce-lifecycle-multiuser-core.json',
           'logs/ce-lifecycle-profile-runtime.json','logs/ce-lifecycle-module-state.json']
    reports={n:read(n) for n in names}
    for n,r in reports.items():
        source_bindings(r);assert r['status']==('FAIL' if n.endswith('before.json') else 'PASS')
    current,before=reports[names[0]],reports[names[1]]
    assert len(current['cases'])==len(before['cases'])==15
    labels={c['case'] for c in current['cases']};assert labels=={c['case'] for c in before['cases']}
    assert {'prepare-failed-owner','prepare-failed-secondary','unmount-reunlock','adoptable-eviction','eviction-failure','cached-policy','unmount-eviction-failure'}<=labels
    assert all(c['returncode']==0 for c in current['cases'])
    failed=[c for c in before['cases'] if c['status']=='FAIL']
    assert {c['case'] for c in failed}=={'prepare-failed-owner','prepare-failed-secondary','eviction-failure'}
    assert all(c['returncode']==-6 and 'Assertion' in c['output'] for c in failed)
    for name in ['tests/ce_lifecycle_test.cpp','tests/ce_lifecycle_test.py']:
        assert current['sources'][str(ROOT/name)]==before['sources'][str(ROOT/name)]
    core=reports[names[2]];assert len(core['cases'])==18 and all(c['exit']==0 for c in core['cases'])
    for n,groups,calls in [(names[3],9,102),(names[4],4,24)]:
        r=reports[n];assert r['image_sha256']==digest and r['tests_run']==groups and len(r['cases'])==calls
        assert all(c['actual']==c['expected'] for c in r['cases'])
    provenance=read(image.with_name(image.stem+'-sources.json'))
    assert provenance['image_sha256']==digest and len(provenance['files'])==746 and provenance['jobs']==30
    assert provenance['build_command']=='make -j$(nproc) installclean; make -j$(nproc) recoveryimage'
    bindings(provenance['files'])
    for n,v in provenance['symlinks'].items():assert os.readlink(n)==v,n
    assert manifest(TREE)==manifest(ANDROID/'device/xiaomi/O1_asic')
    log=ROOT/provenance['build_log'];assert sha(log)==provenance['build_log_sha256']
    assert log.read_text().count('build completed successfully')==2 and 'Deleted images and staging directories' in log.read_text()
    assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/ce-lifecycle-final-source-recheck.log').read_text()
    series=read(TREE/'patches/series.json');vold=ANDROID/'system/vold';spec=series['repositories']['system/vold']
    assert spec['commit']==current['vold_commit']==subprocess.check_output(['git','-C',str(vold),'rev-parse','HEAD'],text=True).strip()
    assert not subprocess.check_output(['git','-C',str(vold),'diff','HEAD','--name-only'],text=True).strip()
    for n,v in spec['result_files'].items():assert provenance['files'][str(vold/n)]==v
    assert '"libvold",' in (ANDROID/'bootable/recovery/Android.bp').read_text()
    vold_bp=(vold/'Android.bp').read_text();assert all('"'+n+'"' in vold_bp for n in ['libvold','Decrypt.cpp','FsCrypt.cpp'])
    baseline=ROOT/'imgs/built/recovery-dijun-unified-mtp-upload-time.img';old=read(baseline.with_name(baseline.stem+'-sources.json'))
    assert sha(baseline)==old['image_sha256']=='57798214bab0d211aa53e5036e46e45c528483aebb3cc16286da86406928484a'
    changed={n for n,v in provenance['files'].items() if old['files'].get(n)!=v}
    assert changed=={str(ANDROID/'bootable/recovery/partitionmanager.cpp')}|{str(vold/n) for n in ['FsCrypt.cpp','Decrypt.cpp','Android.bp']}|{str(ANDROID/'device/xiaomi/O1_asic/patches'/n) for n in ['series.json','0050-decrypt-failure-ce-cleanup.patch']}
    assert not set(old['files'])-set(provenance['files'])
    meta=read(image.with_suffix('.json'));previous=read(baseline.with_suffix('.json'));assert meta['sha256']==digest and len(meta['profiles'])==6
    entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
    for n,v in meta['binary_hashes'].items():assert hashlib.sha256(entries[n]).hexdigest()==v,n
    assert b'Failed to evict CE keys after unsuccessful decrypt for user %d' in entries['system/bin/recovery']
    for n in ['system/lib64/libgui2.so','system/lib64/libtwrpminui.so','system/lib64/libtwrpmtp-ffs.so']:
        assert previous['binary_hashes'][n]==meta['binary_hashes'][n],n
    # Source-unchanged MTP evidence is retained with its own original image;
    # this does not relabel old tests as current-image executions.
    inherited=['logs/mtp-upload-time-objects.json','logs/mtp-upload-time-transfers.json']
    for n in inherited:source_bindings(read(n))
    for n in names:
        checks=[c for c in index['checks']+index.get('additional_checks',[]) if c.get('evidence')==n]
        assert checks and all(c['evidence_sha256']==sha(ROOT/n) for c in checks),n
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    docs=['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.md','simulation-report.json','docs/MULTIUSER-ADAPTATION.md','compatibility-matrix.md','FEATURE-USAGE.md']
    out=dict(status='PASS',scope=__doc__,image=str(image),image_sha256=digest,production_sources=746,
             lifecycle_cases=15,old_failed=3,multiuser_core_cases=18,profile_groups=9,module_groups=4,
             vold_commit=spec['commit'],evidence={n:sha(ROOT/n) for n in names},inherited_MTP_evidence={n:sha(ROOT/n) for n in inherited},
             documents={n:sha(ROOT/n) for n in docs},audit_source_sha256=sha(Path(__file__)))
    (ROOT/'logs/ce-lifecycle-delivery.json').write_text(json.dumps(out,indent=2)+'\n')
    print('PASS: CE lifecycle15/old failures3;multiuser18;746 sources;profile9/module4. Parent-bound protocol and full12-group goal remain incomplete.')
if __name__=='__main__':main()
