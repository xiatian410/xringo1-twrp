#!/usr/bin/env python3
"""Bind manual NV mount policy to actual source, regression and clean image.

UI/backend policy only: core mounts remain available. Host filesystem/device
state and LVGL metrics are fixtures, not real NV content or phone operations.
"""
import hashlib
import json
import os
from pathlib import Path
from sync_device_tree import ROOT,TREE,ANDROID,manifest
from firmware_facts import boot_parts,ramdisk_entries

def sha(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads((ROOT/p).read_text())
def bindings(mapping):
 for path,value in mapping.items():assert sha(ROOT/path)==value,path
def main():
 index=read('simulation-report.json');image=Path(index['image']);digest=sha(image)
 assert image.name=='recovery-dijun-unified-nv-mount-policy.img' and digest==index['image_sha256']
 source=read(image.with_name(image.stem+'-sources.json'));bindings(source['files'])
 assert source['image_sha256']==digest and len(source['files'])==751 and source['jobs']==30
 for path,target in source['symlinks'].items():assert os.readlink(path)==target
 log=ROOT/source['build_log'];assert sha(log)==source['build_log_sha256']
 assert log.read_text().count('build completed successfully')==2
 assert 'Deleted images and staging directories' in log.read_text()
 assert manifest(TREE)==manifest(ANDROID/'device/xiaomi/O1_asic')
 assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/nv-mount-policy-final-source-recheck.log').read_text()
 previous=ROOT/'imgs/built/recovery-dijun-unified-zip-selection.img'
 prior=read(previous.with_name(previous.stem+'-sources.json'));assert sha(previous)==prior['image_sha256']
 changed={p for p,h in source['files'].items() if prior['files'].get(p)!=h}
 assert changed=={str(ANDROID/'bootable/recovery/gui2/backend'/n) for n in ['mount_backend.h','twrp_mount_backend.cpp']}|{
  str(ANDROID/'device/xiaomi/O1_asic/patches'/n) for n in ['0054-restrict-manual-nv-mounts.patch','series.json']}
 for name in ['mount_backend.h','twrp_mount_backend.cpp']:
  assert sha(ROOT/'logs/nv-mount-before'/name)==prior['files'][str(ANDROID/'bootable/recovery/gui2/backend'/name)]
 assert source['files'][str(ANDROID/'device/xiaomi/O1_asic/recovery.fstab')]==prior['files'][str(ANDROID/'device/xiaomi/O1_asic/recovery.fstab')]
 evidence=['logs/nv-mount-policy.json','logs/nv-mount-policy-before.json','logs/nv-mount-list-chain.json',
           'logs/nv-policy-profile-runtime.json','logs/nv-policy-module-state.json']
 reports=[read(p) for p in evidence]
 for path,r in zip(evidence,reports):
  assert r['status']==('FAIL' if path.endswith('before.json') else 'PASS'),path
  for key in ['sources','test_sources','tests']:bindings(r.get(key,{}))
  if 'lvgl' in r:bindings(r['lvgl']['source_files'])
 current,before,lists,profile,modules=reports
 assert len(current['cases'])==len(before['cases'])==26
 assert sum(c['status']=='FAIL' for c in before['cases'])==17
 assert all(c['exit']==0 for c in current['cases'])
 assert [c['path'] for c in current['cases']]==[c['path'] for c in before['cases']]
 for path in ['tests/nv_mount_policy_test.cpp','tests/nv_mount_policy_test.py']:
  assert current['sources'][str(ROOT/path)]==before['sources'][str(ROOT/path)]
 assert len(lists['cases'])==6 and lists['image_sha256']==prior['image_sha256']
 assert all(c['returncode']==0 for c in lists['cases'])
 for r,g,n in [(profile,9,102),(modules,4,24)]:
  assert r['image_sha256']==digest and r['tests_run']==g and len(r['cases'])==n
  assert all(c['actual']==c['expected'] for c in r['cases'])
 metadata=read(image.with_suffix('.json'));assert metadata['sha256']==digest and len(metadata['profiles'])==6
 entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
 for name,value in metadata['binary_hashes'].items():assert hashlib.sha256(entries[name]).hexdigest()==value
 # Android backend objects are linked into recovery, shared libgui2 holds widgets.
 assert b'Manual mount changes are disabled for NV/protection partitions' in entries['system/bin/recovery']
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 for path in evidence:
  checks=[c for c in index['additional_checks'] if c.get('evidence')==path]
  assert checks and all(c['evidence_sha256']==sha(ROOT/path) for c in checks)
 docs=['ADAPTATION-GOALS.md','MAINTENANCE.md','README.md','FEATURE-USAGE.md','simulation-report.json',
       'simulation-report.md','docs/MOUNT-LIST-EXPLANATION.md']
 output=dict(status='PASS',scope=__doc__,image=str(image),image_sha256=digest,production_sources=751,
  policy_cases=26,old_failures=17,lvgl_list_cases=6,list_fixture_image_sha256=prior['image_sha256'],
  profile_groups=9,module_groups=4,evidence={p:sha(ROOT/p) for p in evidence},
  documents={p:sha(ROOT/p) for p in docs},audit_source_sha256=sha(Path(__file__)),
  limitations='GUI manual mount restrictions only; not a security boundary against privileged shell or core operations. No device/NV content accessed. List fstab fixtures from preceding image; unchanged fstab verified. Full goal and historical audit drift remain incomplete.')
 (ROOT/'logs/nv-mount-policy-delivery.json').write_text(json.dumps(output,indent=2)+'\n')
 print('PASS: NV policy26/old17failures;LVGL6;751 sources;profile9/module4. Full goal remains active.')
if __name__=='__main__':main()
