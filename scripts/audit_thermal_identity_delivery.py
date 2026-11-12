#!/usr/bin/env python3
"""Bind dynamic CPU sensor selection to maintained source and same-image runtime."""
import hashlib,json
from pathlib import Path
from firmware_facts import boot_parts,ramdisk_entries
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(n):return json.loads((ROOT/n).read_text())
def sources(r):
 for group in ['sources','test_sources']:
  for n,h in r.get(group,{}).items():
   p=Path(n)
   if not p.is_absolute():
    if p.parts[0] in ['logs','tests','scripts']:p=ROOT/p
    else:p=(ROOT/'tests' if group=='test_sources' else Path('/root/AAA/twrp/bootable/recovery'))/p
   assert sha(p)==h,n

def main():
 index=load('simulation-report.json');image=Path(index['image']);digest=sha(image)
 assert digest==index['image_sha256']=='338a4bf6c4e4563a30e6d26eecfbf6ac0793d5158974753a107eb38674f455db'
 current=load('logs/thermal-identity.json');before=load('logs/thermal-identity-before.json')
 labels={'reordered','late-registration','wrong-type','duplicate','renumbered','bad-temp','read-error','negative-small','name-filter','missing-root','disabled','legacy'}
 for r in [current,before]:
  assert len(r['cases'])==12 and {c['case'] for c in r['cases']}==labels;sources(r)
 assert current['status']=='PASS' and all(c['returncode']==0 for c in current['cases'])
 assert {c['case'] for c in before['cases'] if c['returncode']==0}=={'bad-temp','disabled','legacy'}
 for name,count in [('logs/thermal-status-regression.json',28),('logs/settings-regression.json',21)]:
  r=load(name);assert r['status']=='PASS' and len(r['cases'])==count;sources(r)
 src=json.loads(image.with_name(image.stem+'-sources.json').read_text());assert src['image_sha256']==digest and len(src['files'])==719 and src['jobs']==30
 assert src['build_command']=='make -j$(nproc) installclean; make -j$(nproc) recoveryimage'
 for n,h in src['files'].items():assert sha(Path(n))==h,n
 assert sha(ROOT/src['build_log'])==src['build_log_sha256'] and 'build completed successfully' in (ROOT/src['build_log']).read_text()
 metadata=json.loads(image.with_suffix('.json').read_text());assert metadata['sha256']==digest and len(metadata['profiles'])==6
 assert metadata['status_build_configuration']['cpu_temperature_source']=='thermal class type=cpu-crg (dynamic ordinal)'
 entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
 assert b'ro.twrp.cpu_temp_type=cpu-crg' in entries['prop.default'].splitlines()
 assert b'ro.twrp.cpu_temp_type' in entries['system/bin/recovery']
 for n,h in metadata['binary_hashes'].items():assert hashlib.sha256(entries[n]).hexdigest()==h,n
 old=load('imgs/built/recovery-dijun-unified-otg-selection.json')
 for n in ['system/lib64/libgui2.so','system/lib64/libtwrpminui.so']:assert old['binary_hashes'][n]==metadata['binary_hashes'][n],n
 runtime=load('logs/thermal-identity-profile-runtime.json');assert runtime['status']=='PASS' and runtime['image_sha256']==digest and runtime['tests_run']==9 and len(runtime['cases'])==102
 # Runtime reports use paths relative to workspace, rather than recovery.
 for group in ['sources','test_sources']:
  for n,h in runtime[group].items():
   p=Path(n) if Path(n).is_absolute() else ROOT/n;assert sha(p)==h,n
 evidence=['logs/thermal-identity.json','logs/thermal-status-regression.json','logs/thermal-identity-profile-runtime.json','logs/thermal-topology.json']
 for ev in evidence:
  c,=[c for c in index['checks'] if c['evidence']==ev];assert c['evidence_sha256']==sha(ROOT/ev),ev
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 out=dict(status='PASS',scope=__doc__,image_sha256=digest,source_files=719,identity_cases=12,before_failures=9,status_cases=28,settings_cases=21,runtime_groups=9,runtime_calls=102,evidence={n:sha(ROOT/n) for n in evidence+['logs/thermal-identity-before.json','logs/build-thermal-identity.log','logs/verify-thermal-identity.log','logs/thermal-identity-final-source-recheck.log']},documents={n:sha(ROOT/n) for n in ['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.json','simulation-report.md','docs/STATUS-ADAPTATION.md','FEATURE-USAGE.md']},audit_script_sha256=sha(Path(__file__)),verifier_sha256=sha(ROOT/'scripts/verify_unified_recovery.py'))
 (ROOT/'logs/thermal-identity-delivery.json').write_text(json.dumps(out,indent=2)+'\n');print('PASS:12 CPU identity cases/9 old failures;28 status/21 settings;719 sources;runtime9 groups/102 calls. GUI/motor unverified.')
if __name__=='__main__':main()
