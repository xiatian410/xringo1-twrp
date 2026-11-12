#!/usr/bin/env python3
"""Verify atomic SendObject software behavior and clean delivery, not physical USB or motor."""
import hashlib,json
from pathlib import Path
from firmware_facts import boot_parts,ramdisk_entries
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return json.loads((ROOT/n).read_text())
def sources(r):
 for group in ['sources','test_sources','shared_sources']:
  for n,h in r.get(group,{}).items():assert sha(Path(n) if Path(n).is_absolute() else ROOT/n)==h,n

def main():
 index=read('simulation-report.json');image=Path(index['image']);digest=sha(image)
 assert image.name=='recovery-dijun-unified-mtp-atomic-upload.img' and index['image_sha256']==digest
 names=['logs/mtp-atomic-objects.json','logs/mtp-atomic-transfers.json','logs/mtp-atomic-profile-runtime.json']
 objects=read(names[0]);sources(objects)
 assert objects['status']=='PASS' and len(objects['cases'])==68 and all(c['status']=='PASS' for c in objects['cases'])
 atomic={c['case']:c for c in objects['cases'] if c['case'].startswith('atomic-')}
 assert len(atomic)==22
 assert set(atomic)=={'atomic-'+kind+'-'+case for kind in ['overwrite','new'] for case in ['success','receive-error','short-error','sync-error','write-error','rename-error','create-error','close-error','directory-sync','cancel','process-death']}
 for name,c in atomic.items():
  assert c['returncode']==(42 if name.endswith('process-death') else 0)
  if c['returncode']==42:assert 'Parent verified destination unchanged and one partial staging file' in c['output']
 baseline=read('logs/mtp-atomic-before.json');sources(baseline)
 assert baseline['status']=='FAIL' and len(baseline['cases'])==5
 assert all(c['status']=='FAIL' and c['returncode']==1 and 'FAIL ' in c['output'] for c in baseline['cases'])
 assert baseline['test_sources']==objects['test_sources']
 transfers=read(names[1]);sources(transfers)
 assert transfers['status']=='PASS' and len(transfers['cases'])==48 and all(c['returncode']==0 for c in transfers['cases'])
 provenance=json.loads(image.with_name(image.stem+'-sources.json').read_text())
 assert provenance['image_sha256']==digest and len(provenance['files'])==727 and provenance['jobs']==30
 assert provenance['build_command']=='make -j$(nproc) installclean; make -j$(nproc) recoveryimage'
 for n,h in provenance['files'].items():assert sha(Path(n))==h,n
 for n,t in provenance['symlinks'].items():assert str(Path(n).readlink())==t
 log=ROOT/provenance['build_log'];assert sha(log)==provenance['build_log_sha256']
 assert log.read_text().count('build completed successfully')==2 and 'Deleted images and staging directories' in log.read_text()
 meta=json.loads(image.with_suffix('.json').read_text());assert meta['sha256']==digest and len(meta['profiles'])==6
 entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
 for n,h in meta['binary_hashes'].items():assert hashlib.sha256(entries[n]).hexdigest()==h,n
 previous=read('imgs/built/recovery-dijun-unified-haptics-request-trace.json')
 assert [n for n,h in previous['binary_hashes'].items() if meta['binary_hashes'][n]!=h]==['system/lib64/libtwrpmtp-ffs.so']
 assert b'Mtp upload published but directory sync failed' in entries['system/lib64/libtwrpmtp-ffs.so']
 runtime=read(names[2]);sources(runtime)
 assert runtime['status']=='PASS' and runtime['image_sha256']==digest and runtime['tests_run']==9 and len(runtime['cases'])==102
 for n in names:
  c,=[c for c in index['checks'] if c['evidence']==n];assert c['result']=='pass' and c['evidence_sha256']==sha(ROOT/n)
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/mtp-atomic-final-source-recheck.log').read_text()
 result=dict(status='PASS',scope=__doc__,image_sha256=digest,source_files=727,object_cases=68,atomic_cases=22,old_failures=5,transfer_cases=48,runtime_groups=9,runtime_calls=102,
 evidence={n:sha(ROOT/n) for n in names+['logs/mtp-atomic-before.json','logs/verify-mtp-atomic.log','logs/mtp-atomic-final-source-recheck.log']},
 documents={n:sha(ROOT/n) for n in ['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.md','simulation-report.json','docs/MTP-ATOMIC-UPLOAD.md']},audit_script_sha256=sha(Path(__file__)))
 (ROOT/'logs/mtp-atomic-delivery.json').write_text(json.dumps(result,indent=2)+'\n')
 print('PASS: atomic22/objects68/transfers48,old5 fail,727 sources,profile9/102; hardware and full goal unresolved.')
if __name__=='__main__':main()
