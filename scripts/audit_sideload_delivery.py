#!/usr/bin/env python3
"""Bind sideload lifecycle regression to maintained source and clean image.

Native fixture subprocesses only; USB/FUSE/install/MTP/cache doubles. This
focused audit is not full USB installation acceptance or historical audit repair.
"""
import hashlib,json,os,subprocess
from pathlib import Path
from sync_device_tree import ROOT,TREE,ANDROID,manifest
from firmware_facts import boot_parts,ramdisk_entries

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads((ROOT/p).read_text())
def bindings(files):
 for p,h in files.items():assert sha(ROOT/p)==h,p

def main():
 index=read('simulation-report.json');image=Path(index['image']);digest=sha(image)
 assert image.name=='recovery-dijun-unified-sideload-lifecycle.img' and digest==index['image_sha256']
 source=read(image.with_name(image.stem+'-sources.json'));bindings(source['files'])
 assert source['image_sha256']==digest and len(source['files'])==758 and source['jobs']==30
 for p,target in source['symlinks'].items():assert os.readlink(p)==target
 log=ROOT/source['build_log'];assert sha(log)==source['build_log_sha256']
 text=log.read_text();assert text.count('build completed successfully')==2 and 'Deleted images and staging directories' in text
 for p in ['twrpinstall/adb_install.cpp','gui2/backend/twrp_sideload_backend.cpp']:assert p.split('/')[-1] in text
 assert manifest(TREE)==manifest(ANDROID/'device/xiaomi/O1_asic')
 assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/sideload-final-source-recheck.log').read_text()
 previous=ROOT/'imgs/built/recovery-dijun-unified-zip-queue.img';prior=read(previous.with_name(previous.stem+'-sources.json'))
 assert sha(previous)==prior['image_sha256']
 changed={p for p,h in source['files'].items() if prior['files'].get(p)!=h}
 names=['twrpinstall/adb_install.cpp','twrpinstall/include/twinstall/adb_install.h','gui2/backend/twrp_sideload_backend.cpp','gui2/backend/twrp_sideload_backend.h']
 assert changed=={str(ANDROID/'bootable/recovery'/p) for p in names}|{str(ANDROID/'device/xiaomi/O1_asic/patches'/p) for p in ['0056-sideload-child-lifecycle.patch','series.json']}
 assert not set(prior['files'])-set(source['files'])
 evidence=['logs/sideload-lifecycle.json','logs/sideload-lifecycle-before.json','logs/sideload-profile-runtime.json','logs/sideload-module-state.json']
 reports=[read(p) for p in evidence]
 for p,r in zip(evidence,reports):
  assert r['status']==('FAIL' if p.endswith('before.json') else 'PASS')
  for key in ['sources','test_sources','tests','binary_dependencies']:bindings(r.get(key,{}))
 current,before,profile,modules=reports
 assert len(current['cases'])==33 and len(before['cases'])==31
 assert sum(c['status']=='FAIL' for c in before['cases'])==29
 for p in ['tests/sideload_lifecycle_test.py','tests/sideload_lifecycle_test.cpp']:
  assert current['sources'][str(ROOT/p)]==before['sources'][str(ROOT/p)]
 assert current['binary_dependencies']==before['binary_dependencies']
 rows={c['case']:c for c in current['cases']}
 for c in rows.values():assert c['exit']==0 and 'unsafe=0' in c['output'] and 'failures=0' in c['output']
 for name in ['cancel','destructor']:assert 'waits=1' in rows[name]['output']
 assert 'forks=0' in rows['cancel-before-spawn']['output']
 assert 'waits=2' in rows['wait-eintr']['output']
 for name in ['usb-fail','property-fail']:assert 'waits=1' in rows[name]['output']
 for name in names:
  backup=ROOT/'logs/sideload-before'/Path(name).name
  baseline=subprocess.check_output(['git','-C',str(ANDROID/'bootable/recovery'),'show','HEAD:'+name])
  assert hashlib.sha256(baseline).hexdigest()==sha(backup)
 for r,groups,calls in [(profile,9,102),(modules,4,24)]:
  assert r['image_sha256']==digest and r['tests_run']==groups and len(r['cases'])==calls
  assert all(c['actual']==c['expected'] for c in r['cases'])
 metadata=read(image.with_suffix('.json'));old=read(previous.with_suffix('.json'))
 assert metadata['sha256']==digest and len(metadata['profiles'])==6
 entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
 for p,h in metadata['binary_hashes'].items():assert hashlib.sha256(entries[p]).hexdigest()==h
 assert metadata['binary_hashes']['system/bin/recovery']!=old['binary_hashes']['system/bin/recovery']
 for p in ['system/lib64/libgui2.so','system/lib64/libtwrpminui.so','system/lib64/libtwrpmtp-ffs.so']:assert metadata['binary_hashes'][p]==old['binary_hashes'][p]
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 for p in evidence:
  checks=[c for c in index['additional_checks'] if c.get('evidence')==p];assert checks and all(c['evidence_sha256']==sha(ROOT/p) for c in checks)
 inherited=['logs/sideload-zip-queue-regression.json','logs/nv-mount-policy.json']
 for p in inherited:
  r=read(p);assert r['status']=='PASS';bindings(r['sources'])
 docs=['ADAPTATION-GOALS.md','MAINTENANCE.md','FEATURE-USAGE.md','simulation-report.json','simulation-report.md','README.md','docs/INSTALL-CHAIN-VALIDATION.md','docs/CURRENT-VALIDATION.json']
 result=dict(status='PASS',scope=__doc__,image=str(image),image_sha256=digest,production_sources=758,cases=33,old_failed_cases=29,profile_groups=9,module_groups=4,evidence={p:sha(ROOT/p) for p in evidence},documents={p:sha(ROOT/p) for p in docs},audit_source_sha256=sha(Path(__file__)),limitations='Real private process/socket lifecycle; property/FUSE/install/MTP/cache doubles, not USB package installation. Full goal12 groups and historical source drift remain open.')
 (ROOT/'logs/sideload-delivery.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS: sideload33/old29 failures;758 sources;six profiles;profile9/module4. Full goal remains in progress.')
if __name__=='__main__':main()
