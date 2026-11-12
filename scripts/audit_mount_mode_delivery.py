#!/usr/bin/env python3
"""Bind mount-mode failure coverage to maintained source, build and same-image runtime."""
import hashlib,json
from pathlib import Path
from firmware_facts import boot_parts,ramdisk_entries
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(n):return json.loads((ROOT/n).read_text())
def main():
 index=load('simulation-report.json');image=Path(index['image']);digest=sha(image)
 assert digest==index['image_sha256']=='848096d4b42b41926e2741ba4a34ef1ec4922aaa66036281724e7a2d65b652f1'
 current=load('logs/mount-mode.json');before=load('logs/mount-mode-before.json')
 labels={'success-rw','success-ro','unmounted','vendor-absent','system-absent','system-unmount','vendor-unmount','system-remount','vendor-remount','rollback-remount','invalid','repeat','mixed-modes','vendor-only-mounted','rollback-unmount'}
 for r in [current,before]:
  assert {c['case'] for c in r['cases']}==labels and len(r['cases'])==15
  for name,expected in r['sources'].items():assert sha(Path(name))==expected,name
 assert current['status']=='PASS' and all(c['returncode']==0 for c in current['cases'])
 assert {c['case'] for c in before['cases'] if c['returncode']}=={'vendor-absent','vendor-unmount','system-remount','vendor-remount','rollback-remount','invalid','vendor-only-mounted','rollback-unmount'}
 src=json.loads(image.with_name(image.stem+'-sources.json').read_text());assert src['image_sha256']==digest and len(src['files'])==717
 assert src['jobs']==30 and src['build_command']=='make -j$(nproc) installclean; make -j$(nproc) recoveryimage'
 for name,expected in src['files'].items():assert sha(Path(name))==expected,name
 assert sha(ROOT/src['build_log'])==src['build_log_sha256']
 assert 'build completed successfully' in (ROOT/src['build_log']).read_text()
 metadata=json.loads(image.with_suffix('.json').read_text());assert metadata['sha256']==digest and len(metadata['profiles'])==6
 entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
 for name,expected in metadata['binary_hashes'].items():assert hashlib.sha256(entries[name]).hexdigest()==expected,name
 for marker in [b'System mount mode: unmount failed',b'System mount mode: requested remount failed',b'System mount mode: rollback unmount failed',b'System mount mode: rollback remount failed']:
  assert marker in entries['system/bin/recovery']
 runtime=load('logs/mount-mode-profile-runtime.json');assert runtime['status']=='PASS' and runtime['image_sha256']==digest
 assert runtime['tests_run']==9 and len(runtime['cases'])==102
 for name,expected in {**runtime['sources'],**runtime['test_sources']}.items():
  p=Path(name) if Path(name).is_absolute() else ROOT/name;assert sha(p)==expected,name
 # The mount-only patch must leave the shipped GUI and FF libraries identical.
 old=json.loads((ROOT/'imgs/built/recovery-dijun-unified-settings-row.json').read_text())
 for name in ['system/lib64/libgui2.so','system/lib64/libtwrpminui.so']:
  assert old['binary_hashes'][name]==metadata['binary_hashes'][name],name
 for evidence in ['logs/mount-mode.json','logs/mount-mode-profile-runtime.json']:
  c,=[c for c in index['checks'] if c['evidence']==evidence];assert c['evidence_sha256']==sha(ROOT/evidence)
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 output=dict(status='PASS',scope=__doc__,image_sha256=digest,cases=15,before_failed=8,source_files=717,runtime_groups=9,runtime_calls=102,
  evidence={n:sha(ROOT/n) for n in ['logs/mount-mode.json','logs/mount-mode-before.json','logs/build-mount-mode.log','logs/verify-mount-mode.log','logs/mount-mode-profile-runtime.json','logs/mount-mode-final-source-recheck.log']},
  documents={n:sha(ROOT/n) for n in ['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.json','simulation-report.md','FEATURE-USAGE.md','docs/MOUNT-LIST-EXPLANATION.md']},audit_script_sha256=sha(Path(__file__)))
 (ROOT/'logs/mount-mode-delivery.json').write_text(json.dumps(output,indent=2)+'\n')
 print('PASS:15 mount-mode cases,8 old failures,717 sources,9 runtime groups/102 calls; physical haptics unverified')
if __name__=='__main__':main()
