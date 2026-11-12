#!/usr/bin/env python3
"""Bind date parsing and upload-file evidence to the clean unified image; full goal remains open."""
import hashlib,json
from pathlib import Path
from firmware_facts import boot_parts,ramdisk_entries
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return json.loads((ROOT/n).read_text())
def sources(r):
 for group in ['sources','tests','test_sources','shared_sources']:
  for n,h in r.get(group,{}).items():
   p=Path(n) if Path(n).is_absolute() else ROOT/n
   assert sha(p)==h,n
def main():
 index=read('simulation-report.json');image=Path(index['image']);digest=sha(image)
 assert image.name=='recovery-dijun-unified-mtp-datetime.img' and index['image_sha256']==digest
 before=read('logs/mtp-datetime-before.json');sources(before)
 assert before['status']=='FAIL' and len(before['cases'])==79
 assert sum(c['status']=='FAIL' for c in before['cases'])==48
 evidence=['logs/mtp-datetime.json','logs/mtp-datetime-objects.json','logs/mtp-datetime-transfers.json','logs/mtp-datetime-profile-runtime.json']
 for name,count in zip(evidence[:3],[80,46,48]):
  r=read(name);sources(r);assert r['status']=='PASS' and len(r['cases'])==count
  assert all(c['status']=='PASS' for c in r['cases'])
  if count==80:
   assert sum(c['case']=='explicit-zone' for c in r['cases'])==39
   assert any(c['case']=='null' and not c['accepted'] for c in r['cases'])
  if count==46:assert {c['case'] for c in r['cases'] if c['case'].startswith('upload-date-')}=={'upload-date-east','upload-date-west','upload-date-fraction','upload-date-invalid'}
 provenance=json.loads(image.with_name(image.stem+'-sources.json').read_text())
 assert provenance['image_sha256']==digest and len(provenance['files'])==725 and provenance['jobs']==30
 assert provenance['build_command']=='make -j$(nproc) installclean; make -j$(nproc) recoveryimage'
 for n,h in provenance['files'].items():assert sha(Path(n))==h,n
 for n,t in provenance['symlinks'].items():assert str(Path(n).readlink())==t,n
 log=ROOT/provenance['build_log'];assert sha(log)==provenance['build_log_sha256']
 assert log.read_text().count('build completed successfully')==2 and 'Deleted images and staging directories' in log.read_text()
 meta=json.loads(image.with_suffix('.json').read_text());assert meta['sha256']==digest and len(meta['profiles'])==6
 entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
 for n,h in meta['binary_hashes'].items():assert hashlib.sha256(entries[n]).hexdigest()==h,n
 old=read('imgs/built/recovery-dijun-unified-settings-retry.json')
 for n in ['system/lib64/libgui2.so','system/lib64/libtwrpminui.so']:assert meta['binary_hashes'][n]==old['binary_hashes'][n],n
 assert meta['binary_hashes']['system/lib64/libtwrpmtp-ffs.so']!=old['binary_hashes']['system/lib64/libtwrpmtp-ffs.so']
 runtime=read(evidence[-1]);assert runtime['status']=='PASS' and runtime['tests_run']==9 and len(runtime['cases'])==102 and runtime['image_sha256']==digest;sources(runtime)
 for n in evidence:
  c,=[c for c in index['checks'] if c['evidence']==n];assert c['evidence_sha256']==sha(ROOT/n) and c['result']=='pass'
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 recheck=(ROOT/'logs/mtp-datetime-final-source-recheck.log').read_text();assert 'Pending: 0 source updates, device tree changed=False' in recheck
 names=evidence+['logs/mtp-datetime-before.json','logs/verify-mtp-datetime.log','logs/mtp-datetime-final-source-recheck.log']
 out=dict(status='PASS',scope=__doc__,image_sha256=digest,sources=725,date_cases=80,baseline_cases=79,baseline_failures=48,object_cases=46,transfer_cases=48,runtime_groups=9,runtime_calls=102,evidence={n:sha(ROOT/n) for n in names},documents={n:sha(ROOT/n) for n in ['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.json','simulation-report.md','docs/MTP-DATETIME-ADAPTATION.md','docs/MTP-OBJECTS-ADAPTATION.md','FEATURE-USAGE.md']},audit_script_sha256=sha(Path(__file__)))
 (ROOT/'logs/mtp-datetime-delivery.json').write_text(json.dumps(out,indent=2)+'\n')
 print('PASS: date80/baseline48 failures;objects46/transfers48;725 sources;profile9/102. Physical vibration and full12 groups remain incomplete.')
if __name__=='__main__':main()
