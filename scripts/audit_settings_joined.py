#!/usr/bin/env python3
"""Bind joined settings software-path evidence; physical settings and motor remain unresolved."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return json.loads((ROOT/n).read_text())
def main():
 index=read('simulation-report.json');current=read('logs/settings-joined.json');old=read('logs/settings-joined-before.json')
 expected={'existing-mount','mount-on-save','mount-denied','no-space','short-write','read-only','rename-error','directory-sync-error','uninitialized-backing','constant-key','long-field'}
 assert current['status']=='PASS' and old['status']=='FAIL'
 for report in [current,old]:
  assert len(report['cases'])==22
  assert {(c['kind'],c['case']) for c in report['cases']}=={(k,c) for k in ['check','switch'] for c in expected}
  for n,h in report['sources'].items():assert sha(Path(n) if Path(n).is_absolute() else ROOT/n)==h,n
  for n,h in report['lvgl']['source_files'].items():assert sha(Path(n))==h,n
 assert all(c['status']=='PASS' and c['returncode']==0 and 'disk roundtrip, UI rollback/retry' in c['output'] for c in current['cases'])
 assert all(c['status']=='FAIL' and c['returncode']<0 and 'Assertion' in c['output'] and 'persist storage is not mounted' in c['output'] for c in old['cases'])
 before=ROOT/'logs/settings-joined-before/partitionmanager.cpp'
 assert before.read_bytes()==subprocess.check_output(['git','-C','/root/AAA/twrp/bootable/recovery','show','HEAD:partitionmanager.cpp'])
 # Only the selected partition-method source differs between comparison runs.
 c={Path(n).name:h for n,h in current['sources'].items()};b={Path(n).name:h for n,h in old['sources'].items()}
 assert c.keys()==b.keys() and [n for n in c if c[n]!=b[n]]==['partitionmanager.cpp']
 for kind in ['check','switch']:
  rows={c['case']:c for c in current['cases'] if c['kind']==kind}
  assert 'mounts=1' in rows['mount-on-save']['output']
  assert 'mounts=2' in rows['mount-denied']['output']
  assert 'Settings replaced but directory sync failed' in rows['directory-sync-error']['output']
  assert 'Settings field exceeds' in rows['long-field']['output']
  assert 'Failed to save settings' not in rows['constant-key']['output']
 image=Path(index['image']);digest=sha(image);assert index['image_sha256']==digest
 source=json.loads(image.with_name(image.stem+'-sources.json').read_text());assert source['image_sha256']==digest
 for n,h in source['files'].items():assert sha(Path(n))==h,n
 for n,t in source['symlinks'].items():assert str(Path(n).readlink())==t
 for n,h in current['sources'].items():
  if n.startswith('/root/AAA/twrp/bootable/recovery/') and n in source['files']:assert source['files'][n]==h,n
 check,=[x for x in index['checks'] if x['evidence']=='logs/settings-joined.json']
 assert check['evidence_sha256']==sha(ROOT/check['evidence']) and check['count']==22
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 names=['logs/settings-joined.json','logs/settings-joined-before.json','logs/settings-joined.log','logs/settings-joined-before.log']
 result=dict(status='PASS',scope=__doc__,cases=22,old_lookup_failures=22,image_sha256=digest,production_changed=False,
  evidence={n:sha(ROOT/n) for n in names},documents={n:sha(ROOT/n) for n in ['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.md','simulation-report.json','docs/SETTINGS-ADAPTATION.md']},audit_script_sha256=sha(Path(__file__)))
 (ROOT/'logs/settings-joined-audit.json').write_text(json.dumps(result,indent=2)+'\n')
 print('PASS: joined settings22, old lookup22 failures; current image unchanged; field settings and vibration unresolved.')
if __name__=='__main__':main()
