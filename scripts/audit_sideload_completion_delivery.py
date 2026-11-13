#!/usr/bin/env python3
"""Bind sideload lifecycle regression to maintained source and clean image.

Native fixture subprocesses only; USB/FUSE/mount/MTP/cache doubles; real ZIP/updater execution. This
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
 assert image.name=='recovery-dijun-unified-sideload-completion.img' and digest==index['image_sha256']
 source=read(image.with_name(image.stem+'-sources.json'));bindings(source['files'])
 assert source['image_sha256']==digest and len(source['files'])==760 and source['jobs']==30
 for p,target in source['symlinks'].items():assert os.readlink(p)==target
 log=ROOT/source['build_log'];assert sha(log)==source['build_log_sha256']
 text=log.read_text();assert text.count('build completed successfully')==2 and 'Deleted images and staging directories' in text
 for p in ['twrpinstall/adb_install.cpp','gui2/backend/twrp_sideload_backend.cpp']:assert p.split('/')[-1] in text
 assert manifest(TREE)==manifest(ANDROID/'device/xiaomi/O1_asic')
 assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/sideload-completion-final-source-recheck.log').read_text()
 previous=ROOT/'imgs/built/recovery-dijun-unified-sideload-lifecycle.img';prior=read(previous.with_name(previous.stem+'-sources.json'))
 assert sha(previous)==prior['image_sha256']
 changed={p for p,h in source['files'].items() if prior['files'].get(p)!=h}
 names=['twrpinstall/adb_install.cpp','gui2/backend/twrp_sideload_backend.cpp','openrecoveryscript.cpp']
 assert changed=={str(ANDROID/'bootable/recovery'/p) for p in names}|{str(ANDROID/'device/xiaomi/O1_asic/patches'/p) for p in ['0057-sideload-package-completion.patch','series.json']}
 assert not set(prior['files'])-set(source['files'])
 evidence=['logs/sideload-completion-lifecycle.json','logs/sideload-package-chain.json','logs/sideload-package-chain-before.json','logs/sideload-completion-profile-runtime.json','logs/sideload-completion-module-state.json']
 reports=[read(p) for p in evidence]
 for p,r in zip(evidence,reports):
  assert r['status']==('FAIL' if p.endswith('before.json') else 'PASS')
  for key in ['sources','test_sources','tests','binary_dependencies']:bindings(r.get(key,{}))
 lifecycle,current,before,profile,modules=reports
 assert len(lifecycle['cases'])==33 and all(c['status']=='PASS' for c in lifecycle['cases'])
 assert len(current['cases'])==27 and len(before['cases'])==27
 assert sum(c['status']=='FAIL' for c in before['cases'])==19
 assert {c['case']:c['input_sha256'] for c in current['cases']}=={c['case']:c['input_sha256'] for c in before['cases']}
 assert all(c['status']=='PASS' for c in current['cases'])
 for case in current['cases']:
  assert case['acknowledged_cache_attempts']==case['expected_cache_attempts_at_ack']
 for p in ['tests/sideload_package_chain_test.py','tests/sideload_package_chain_test.cpp','tests/sideload_package_fixture.cpp','tests/zip_queue_fixture.cpp']:
  assert current['sources'][str(ROOT/p)]==before['sources'][str(ROOT/p)]
 assert current['binary_dependencies']==before['binary_dependencies']
 rows={c['case']:c for c in lifecycle['cases']}
 for c in rows.values():assert c['exit']==0 and 'unsafe=0' in c['output'] and 'failures=0' in c['output']
 for name in ['cancel','destructor']:assert 'waits=1' in rows[name]['output']
 assert 'forks=0' in rows['cancel-before-spawn']['output']
 assert 'waits=2' in rows['wait-eintr']['output']
 for name in ['usb-fail','property-fail']:assert 'waits=1' in rows[name]['output']
 for name in names:
  backup=ROOT/'logs/sideload-completion-before'/Path(name).name
  key=str(ANDROID/'bootable/recovery'/name)
  baseline=prior['files'].get(key)
  if baseline is None:
   baseline=hashlib.sha256(subprocess.check_output(['git','-C',str(ANDROID/'bootable/recovery'),'show','HEAD:'+name])).hexdigest()
  assert baseline==sha(backup)
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
 result=dict(status='PASS',scope=__doc__,image=str(image),image_sha256=digest,production_sources=760,package_cases=27,old_failed_cases=19,lifecycle_cases=33,profile_groups=9,module_groups=4,evidence={p:sha(ROOT/p) for p in evidence},documents={p:sha(ROOT/p) for p in docs},audit_source_sha256=sha(Path(__file__)),limitations='Real private process/socket lifecycle; property/FUSE/mount/MTP/cache doubles, not USB package installation. Full goal12 groups and historical source drift remain open.')
 (ROOT/'logs/sideload-completion-delivery.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS: sideload-package27/old19 failures;lifecycle33;760 sources;six profiles;profile9/module4. Full goal remains in progress.')
if __name__=='__main__':main()
