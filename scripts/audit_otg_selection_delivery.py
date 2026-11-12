#!/usr/bin/env python3
"""Bind storage-selection and inherited settings regressions to the current image."""
import hashlib,json
from pathlib import Path
from firmware_facts import boot_parts,ramdisk_entries
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(n):return json.loads((ROOT/n).read_text())
def verify_sources(r):
 for group in ['sources','test_sources']:
  for name,expected in r.get(group,{}).items():
   p=Path(name)
   if not p.is_absolute():
    if 'settings_persistence_test.py' in r.get('test_sources',{}):
     p=(ROOT/'tests' if group=='test_sources' else Path('/root/AAA/twrp/bootable/recovery'))/p
    else:p=ROOT/p
   assert sha(p)==expected,name
def main():
 index=load('simulation-report.json');image=Path(index['image']);digest=sha(image)
 assert digest==index['image_sha256']=='aaa4b25c1bd58a0b61508288a479d824f38701c38d2ed606530b39c503181ef7'
 current=load('logs/otg-selection.json');before=load('logs/otg-selection-before.json')
 labels={'new','mounted','mount-fail','size-fail','mounted-size-fail','removed-before','removed-after-mount','missing','non-storage','subpath','full','df-fallback','rollback-unmount-fail','internal','set-fail'}
 for r in [current,before]:
  assert {c['case'] for c in r['cases']}==labels and len(r['cases'])==15
  verify_sources(r)
 assert current['status']=='PASS' and all(c['returncode']==0 for c in current['cases'])
 assert {c['case'] for c in before['cases'] if c['returncode']==0}=={'mount-fail','missing','internal'}
 cases={c['case']:c for c in current['cases']}
 assert 'failed to undo new mount' in cases['rollback-unmount-fail']['stderr']
 assert 'failed to publish target' in cases['set-fail']['stderr']
 regressions={'logs/mount-mode.json':15,'logs/settings-row.json':20,'logs/settings-regression.json':21}
 for name,count in regressions.items():
  r=load(name);assert r['status']=='PASS' and len(r['cases'])==count;verify_sources(r)
 r=load('logs/nested-partition-path-test.json');assert r['status']=='PASS' and r['output']=='assertions=31 failures=0\n';verify_sources(r)
 src=json.loads(image.with_name(image.stem+'-sources.json').read_text())
 assert src['image_sha256']==digest and len(src['files'])==718 and src['jobs']==30
 assert src['build_command']=='make -j$(nproc) installclean; make -j$(nproc) recoveryimage'
 for name,expected in src['files'].items():assert sha(Path(name))==expected,name
 assert sha(ROOT/src['build_log'])==src['build_log_sha256']
 assert 'build completed successfully' in (ROOT/src['build_log']).read_text()
 metadata=json.loads(image.with_suffix('.json').read_text());assert metadata['sha256']==digest and len(metadata['profiles'])==6
 entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
 for name,expected in metadata['binary_hashes'].items():assert hashlib.sha256(entries[name]).hexdigest()==expected,name
 for marker in [b'Storage selection: target unavailable',b'Storage selection: removable capacity unavailable',b'Storage selection: failed to undo new mount',b'Storage selection: failed to publish target']:
  assert marker in entries['system/bin/recovery']
 old=load('imgs/built/recovery-dijun-unified-mount-mode.json')
 for name in ['system/lib64/libgui2.so','system/lib64/libtwrpminui.so']:
  assert old['binary_hashes'][name]==metadata['binary_hashes'][name],name
 runtime=load('logs/otg-selection-profile-runtime.json')
 assert runtime['status']=='PASS' and runtime['image_sha256']==digest and runtime['tests_run']==9 and len(runtime['cases'])==102
 verify_sources(runtime)
 evidence=['logs/otg-selection.json','logs/mount-mode.json','logs/otg-selection-profile-runtime.json','logs/settings-row.json','logs/settings-regression.json','logs/nested-partition-path-test.json']
 for name in evidence:
  c,=[c for c in index['checks'] if c['evidence']==name];assert c['evidence_sha256']==sha(ROOT/name),name
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 docs=['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.json','simulation-report.md','FEATURE-USAGE.md','docs/MOUNT-LIST-EXPLANATION.md','docs/SETTINGS-ADAPTATION.md']
 report=dict(status='PASS',scope=__doc__,image_sha256=digest,source_files=718,selection_cases=15,before_failed=12,settings_row_cases=20,persistence_cases=21,path_assertions=31,runtime_groups=9,runtime_calls=102,evidence={n:sha(ROOT/n) for n in evidence+['logs/otg-selection-before.json','logs/build-otg-selection.log','logs/verify-otg-selection.log','logs/otg-selection-final-source-recheck.log']},documents={n:sha(ROOT/n) for n in docs},audit_script_sha256=sha(Path(__file__)))
 (ROOT/'logs/otg-selection-delivery.json').write_text(json.dumps(report,indent=2)+'\n')
 print('PASS: selection15/old failures12;settings20/persistence21/path31;718 sources;runtime9 groups/102 calls. No hardware acceptance.')
if __name__=='__main__':main()
