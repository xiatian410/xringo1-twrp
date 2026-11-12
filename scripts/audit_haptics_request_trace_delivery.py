#!/usr/bin/env python3
"""Verify request instrumentation, unchanged effect bytes and clean image provenance; motor unverified."""
import hashlib,json
from pathlib import Path
from firmware_facts import boot_parts,ramdisk_entries
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return json.loads((ROOT/n).read_text())
def main():
 index=read('simulation-report.json');image=Path(index['image']);digest=sha(image)
 assert image.name=='recovery-dijun-unified-haptics-request-trace.img' and index['image_sha256']==digest
 names=['logs/haptics-request-trace.json','logs/haptics-request-trace-route.json','logs/haptics-request-trace-worker-ff.json','logs/haptics-worker.json']
 for name,count in zip(names,[14,24,4,16]):
  r=read(name);assert r['status']=='PASS' and len(r['cases'])==count and all(c['status']=='PASS' for c in r['cases'])
  for group in ['sources','shared_sources','test_sources','configuration']:
   for n,h in r.get(group,{}).items():assert sha(Path(n) if Path(n).is_absolute() else ROOT/n)==h,n
  c,=[c for c in index['checks'] if c['evidence']==name];assert c['result']=='pass' and c['evidence_sha256']==sha(ROOT/name)
 detail=read(names[0]);assert sum(c['case'].startswith('ABI-') for c in detail['cases'])==8
 for n,h in detail['input_reports'].items():assert sha(ROOT/n)==h,n
 assert sha(ROOT/'logs/haptics-driver-emulation.json')==detail['baseline_report_sha256']
 provenance=json.loads(image.with_name(image.stem+'-sources.json').read_text())
 assert provenance['image_sha256']==digest and len(provenance['files'])==726 and provenance['jobs']==30
 assert provenance['build_command']=='make -j$(nproc) installclean; make -j$(nproc) recoveryimage'
 for n,h in provenance['files'].items():assert sha(Path(n))==h,n
 for n,t in provenance['symlinks'].items():assert str(Path(n).readlink())==t
 log=ROOT/provenance['build_log'];assert sha(log)==provenance['build_log_sha256']
 assert log.read_text().count('build completed successfully')==2 and 'Deleted images and staging directories' in log.read_text()
 meta=json.loads(image.with_suffix('.json').read_text());assert meta['sha256']==digest and len(meta['profiles'])==6
 entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
 for n,h in meta['binary_hashes'].items():assert hashlib.sha256(entries[n]).hexdigest()==h,n
 # The backend owner is linked into recovery; LVGL GUI code is in libgui2.
 assert b'GUI2 haptics: request=' in entries['system/bin/recovery']
 assert b'FF haptics: request=' in entries['system/lib64/libtwrpminui.so']
 old=read('imgs/built/recovery-dijun-unified-mtp-datetime.json')
 assert meta['binary_hashes']['system/lib64/libtwrpmtp-ffs.so']==old['binary_hashes']['system/lib64/libtwrpmtp-ffs.so']
 runtime_name='logs/haptics-request-trace-profile-runtime.json';runtime=read(runtime_name)
 assert runtime['status']=='PASS' and runtime['image_sha256']==digest and runtime['tests_run']==9 and len(runtime['cases'])==102
 for group in ['sources','test_sources']:
  for n,h in runtime[group].items():assert sha(Path(n) if Path(n).is_absolute() else ROOT/n)==h,n
 c,=[c for c in index['checks'] if c['evidence']==runtime_name];assert c['evidence_sha256']==sha(ROOT/runtime_name)
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/haptics-request-trace-final-source-recheck.log').read_text()
 evidence=names+[runtime_name,'logs/verify-haptics-request-trace.log','logs/haptics-request-trace-final-source-recheck.log']
 result=dict(status='PASS',scope=__doc__,image_sha256=digest,source_files=726,trace_ABI_cases=14,route_cases=24,worker_FF_cases=4,owner_cases=16,runtime_groups=9,runtime_calls=102,
  evidence={n:sha(ROOT/n) for n in evidence},documents={n:sha(ROOT/n) for n in ['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.json','simulation-report.md','docs/archive/haptics/HAPTICS-REQUEST-TRACE.md','docs/HAPTICS-ADAPTATION.md','FEATURE-USAGE.md']},audit_script_sha256=sha(Path(__file__)))
 (ROOT/'logs/haptics-request-trace-delivery.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS: trace14/route24/workerFF4/owner16;726 sources;profile9/102;motor unresolved.')
if __name__=='__main__':main()
