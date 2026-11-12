#!/usr/bin/env python3
"""Bind ZIP queue completion semantics to paired host execution and clean image.

Native private-file ZIP/backend execution with explicit mount/cache/progress
doubles. Separate image-route regression is not a ZIP-to-physical-partition
test. ARM updater, OTA payload, sideload, GUI clicks and hardware remain open.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from sync_device_tree import ROOT,TREE,ANDROID,manifest
from firmware_facts import boot_parts,ramdisk_entries

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads((ROOT/p).read_text())
def bindings(mapping):
 for p,h in mapping.items():assert sha(ROOT/p)==h,p
def main():
 index=read('simulation-report.json');image=Path(index['image']);digest=sha(image)
 assert image.name=='recovery-dijun-unified-zip-queue.img' and index['image_sha256']==digest
 source=read(image.with_name(image.stem+'-sources.json'));bindings(source['files'])
 assert source['image_sha256']==digest and len(source['files'])==753 and source['jobs']==30
 for p,target in source['symlinks'].items():assert os.readlink(p)==target
 log=ROOT/source['build_log'];assert sha(log)==source['build_log_sha256']
 assert log.read_text().count('build completed successfully')==2
 assert 'Deleted images and staging directories' in log.read_text()
 assert 'gui2/backend/twrp_install_backend.cpp' in log.read_text()
 assert manifest(TREE)==manifest(ANDROID/'device/xiaomi/O1_asic')
 assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/zip-queue-final-source-recheck.log').read_text()
 previous=ROOT/'imgs/built/recovery-dijun-unified-nv-mount-policy.img'
 prior=read(previous.with_name(previous.stem+'-sources.json'));assert sha(previous)==prior['image_sha256']
 changed={p for p,h in source['files'].items() if prior['files'].get(p)!=h}
 assert changed=={str(ANDROID/'bootable/recovery/gui2/backend/twrp_install_backend.cpp'),
  str(ANDROID/'device/xiaomi/O1_asic/patches/0055-zip-queue-cache-completion.patch'),
  str(ANDROID/'device/xiaomi/O1_asic/patches/series.json')}
 assert not set(prior['files'])-set(source['files'])
 spec=read(TREE/'patches/series.json')['repositories']['bootable/recovery']
 baseline=subprocess.check_output(['git','-C',str(ANDROID/'bootable/recovery'),'show',spec['commit']+':gui2/backend/twrp_install_backend.cpp'])
 assert hashlib.sha256(baseline).hexdigest()==sha(ROOT/'logs/zip-queue-before/twrp_install_backend.cpp')
 evidence=['logs/zip-queue-chain.json','logs/zip-queue-before.json','logs/zip-queue-image-regression.json',
           'logs/zip-queue-profile-runtime.json','logs/zip-queue-module-state.json']
 reports=[read(p) for p in evidence]
 for p,r in zip(evidence,reports):
  assert r['status']==('FAIL' if p.endswith('before.json') else 'PASS'),p
  for key in ['sources','test_sources','tests','binary_dependencies']:bindings(r.get(key,{}))
 current,before,routes,profile,modules=reports
 assert len(current['cases'])==len(before['cases'])==23
 assert {c['case']:c['input_sha256'] for c in current['cases']}=={c['case']:c['input_sha256'] for c in before['cases']}
 assert {c['case'] for c in before['cases'] if c['status']=='FAIL'}=={
  'wipe-first','wipe-first-then-fail','wipe-first-badprogress','cache-error','cache-error-after-queue'}
 for p in ['tests/zip_queue_chain_test.py','tests/zip_queue_chain_test.cpp','tests/zip_queue_fixture.cpp']:
  assert current['sources'][str(ROOT/p)]==before['sources'][str(ROOT/p)]
 assert current['binary_dependencies']==before['binary_dependencies']
 assert all(c['exit']==0 and c['content_ok'] for c in current['cases'])
 rows={c['case']:c for c in current['cases']}
 for name in ['wipe-first','wipe-last','wipe-both','wipe-first-then-fail','wipe-failing','wipe-first-badprogress','wipe-first-missing']:
  assert rows[name]['cache_marker'],name
 for name in ['cache-error','cache-error-after-queue','single-clean','two-clean']:
  assert not rows[name]['cache_marker'],name
 assert len(routes['cases'])==40 and all(c['exit']==0 and c['content_ok'] and c['order_ok'] for c in routes['cases'])
 for r,groups,calls in [(profile,9,102),(modules,4,24)]:
  assert r['image_sha256']==digest and r['tests_run']==groups and len(r['cases'])==calls
  assert all(c['actual']==c['expected'] for c in r['cases'])
 inherited=['logs/zip-install-chain.json','logs/zip-selection-updater-regression.json','logs/nv-mount-policy.json']
 for p in inherited:
  r=read(p);assert r['status']=='PASS'
  for key in ['sources','binary_dependencies']:bindings(r.get(key,{}))
 metadata=read(image.with_suffix('.json'));old=read(previous.with_suffix('.json'))
 assert metadata['sha256']==digest and len(metadata['profiles'])==6
 entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
 for p,h in metadata['binary_hashes'].items():assert hashlib.sha256(entries[p]).hexdigest()==h
 assert metadata['binary_hashes']['system/bin/recovery']!=old['binary_hashes']['system/bin/recovery']
 for name in ['system/lib64/libgui2.so','system/lib64/libtwrpminui.so','system/lib64/libtwrpmtp-ffs.so']:
  assert metadata['binary_hashes'][name]==old['binary_hashes'][name]
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 for p in evidence:
  checks=[c for c in index['additional_checks'] if c.get('evidence')==p]
  assert checks and all(c['evidence_sha256']==sha(ROOT/p) for c in checks)
 docs=['ADAPTATION-GOALS.md','MAINTENANCE.md','FEATURE-USAGE.md','simulation-report.md','simulation-report.json',
       'docs/INSTALL-CHAIN-VALIDATION.md','docs/CURRENT-VALIDATION.json','README.md']
 result=dict(status='PASS',scope=__doc__,image=str(image),image_sha256=digest,production_sources=753,
  queue_cases=23,old_failures=5,image_route_cases=40,profile_groups=9,module_groups=4,
  evidence={p:sha(ROOT/p) for p in evidence},inherited_evidence={p:sha(ROOT/p) for p in inherited},
  documents={p:sha(ROOT/p) for p in docs},audit_source_sha256=sha(Path(__file__)),
  limitations='Cache wipe is a double, not ext4/physical cleanup. No GUI pointer/ARM updater/AB payload/sideload/device execution. Partial install is not rolled back. Full12-group acceptance and historical full-audit source drift remain open.')
 (ROOT/'logs/zip-queue-delivery.json').write_text(json.dumps(result,indent=2)+'\n')
 print('PASS: queue23/old5 failures;image-route40;753 sources;profile9/module4. Full goal remains in progress.')
if __name__=='__main__':main()
