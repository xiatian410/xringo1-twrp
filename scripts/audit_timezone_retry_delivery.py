#!/usr/bin/env python3
"""Bind timezone rollback/retry software evidence to a clean image; device settings and motor unresolved."""
import hashlib,json
from pathlib import Path
from firmware_facts import boot_parts,ramdisk_entries
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return json.loads((ROOT/n).read_text())
def sources(r):
 for g in ['sources','test_sources','shared_sources','configuration']:
  for n,h in r.get(g,{}).items():
   p=Path(n)
   if not p.is_absolute():p=ROOT/p if (ROOT/p).exists() else Path('/root/AAA/twrp/bootable/recovery')/p
   assert sha(p)==h,n

def main():
 index=read('simulation-report.json');image=Path(index['image']);digest=sha(image)
 assert image.name=='recovery-dijun-unified-timezone-retry.img' and index['image_sha256']==digest
 names=['logs/timezone-retry.json','logs/timezone-settings-joined.json','logs/timezone-settings-row.json','logs/timezone-haptics-route.json','logs/timezone-language-theme.json','logs/haptics-worker.json','logs/timezone-status-regression.json','logs/temperature-ui.json']
 for n,count in zip(names,[17,22,20,24,9,16,28,11]):
  r=read(n);sources(r);assert r['status']=='PASS' and len(r['cases'])==count
  assert all(c['returncode']==0 for c in r['cases'])
  c,=[x for x in index['checks'] if x['evidence']==n];assert c['evidence_sha256']==sha(ROOT/n) and c['result']=='pass'
 before=read('logs/timezone-retry-before.json');sources(before)
 assert before['status']=='FAIL' and len(before['cases'])==17
 failed={c['case'] for c in before['cases'] if c['status']=='FAIL'}
 assert failed=={'set-failure-'+str(i) for i in range(1,6)}|{'flush-failure','retry','zone-low','zone-high','offset-low','offset-high'}
 detail=read(names[0]);assert {c['case'] for c in detail['cases']}=={c['case'] for c in before['cases']}
 assert all('exact zone/choices/environment/disk and routing checked' in c['output'] for c in detail['cases'])
 provenance=json.loads(image.with_name(image.stem+'-sources.json').read_text())
 assert provenance['image_sha256']==digest and provenance['jobs']==30 and len(provenance['files'])==731
 assert provenance['build_command']=='make -j$(nproc) installclean; make -j$(nproc) recoveryimage'
 for n,h in provenance['files'].items():assert sha(Path(n))==h,n
 for n,t in provenance['symlinks'].items():assert str(Path(n).readlink())==t
 log=ROOT/provenance['build_log'];assert sha(log)==provenance['build_log_sha256']
 assert log.read_text().count('build completed successfully')==2 and 'Deleted images and staging directories' in log.read_text()
 meta=json.loads(image.with_suffix('.json').read_text());assert meta['sha256']==digest and len(meta['profiles'])==6
 entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
 for n,h in meta['binary_hashes'].items():assert hashlib.sha256(entries[n]).hexdigest()==h,n
 old=read('imgs/built/recovery-dijun-unified-mtp-atomic-upload.json')
 assert {n for n,h in old['binary_hashes'].items() if meta['binary_hashes'][n]!=h}=={'system/bin/recovery','system/lib64/libgui2.so'}
 n='logs/timezone-profile-runtime.json';runtime=read(n);sources(runtime)
 assert runtime['status']=='PASS' and runtime['image_sha256']==digest and runtime['tests_run']==9 and len(runtime['cases'])==102
 c,=[c for c in index['checks'] if c['evidence']==n];assert c['evidence_sha256']==sha(ROOT/n)
 assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/timezone-final-source-recheck.log').read_text()
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 names+=[n,'logs/timezone-retry-before.json','logs/verify-timezone-retry.log','logs/timezone-final-source-recheck.log']
 result=dict(status='PASS',scope=__doc__,image_sha256=digest,source_files=731,timezone_cases=17,old_callback_failures=11,joined_settings=22,row=20,route=24,language_theme=9,owner=16,status_cases=28,temperature_ui=11,runtime_groups=9,runtime_calls=102,
 evidence={n:sha(ROOT/n) for n in names},documents={n:sha(ROOT/n) for n in ['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.md','simulation-report.json','docs/TIMEZONE-SAVE-ADAPTATION.md','docs/SETTINGS-ADAPTATION.md']},audit_script_sha256=sha(Path(__file__)))
 (ROOT/'logs/timezone-retry-delivery.json').write_text(json.dumps(result,indent=2)+'\n')
 print('PASS: timezone17/old11 fail; joined22,row20,route24,language9,owner16,status28,temp11;731 sources;profile9/102. Device and motor unresolved.')
if __name__=='__main__':main()
