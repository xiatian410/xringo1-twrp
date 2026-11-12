#!/usr/bin/env python3
"""Verify FF capability interruption ownership handling; physical vibration remains unresolved."""
import hashlib,json
from pathlib import Path
from firmware_facts import boot_parts,ramdisk_entries
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return json.loads((ROOT/n).read_text())
def sources(r):
 for g in ['sources','shared_sources','test_sources','configuration']:
  for n,h in r.get(g,{}).items():assert sha(Path(n) if Path(n).is_absolute() else ROOT/n)==h,n

def main():
 index=read('simulation-report.json');image=Path(index['image']);digest=sha(image)
 assert image.name=='recovery-dijun-unified-haptics-probe.img' and index['image_sha256']==digest
 names=['logs/haptics-probe-route.json','logs/haptics-probe-worker-ff.json','logs/haptics-probe-trace-abi.json']
 for n,count in zip(names,[28,6,14]):
  r=read(n);sources(r);assert r['status']=='PASS' and len(r['cases'])==count and all(c['status']=='PASS' for c in r['cases'])
  c,=[c for c in index['checks'] if c['evidence']==n];assert c['evidence_sha256']==sha(ROOT/n) and c['count']==count
 before=read('logs/haptics-probe-before.json');sources(before)
 assert before['status']=='FAIL' and len(before['cases'])==28
 assert {c['case'] for c in before['cases'] if c['status']=='FAIL'}=={'ff-probe-eintr','ff-probe-eagain'}
 route=read(names[0]);worker=read(names[1]);detail=read(names[2])
 assert before['test_sources']==route['test_sources']
 assert {c['case'] for c in worker['cases'] if c['case'].startswith('worker-probe-')}=={'worker-probe-eintr','worker-probe-eagain'}
 assert sum(c['case'].startswith('ABI-') for c in detail['cases'])==8
 for n,h in detail['input_reports'].items():assert sha(ROOT/n)==h,n
 assert sha(ROOT/'logs/haptics-driver-emulation.json')==detail['baseline_report_sha256']
 p=json.loads(image.with_name(image.stem+'-sources.json').read_text());assert p['image_sha256']==digest and len(p['files'])==732 and p['jobs']==30
 assert p['build_command']=='make -j$(nproc) installclean; make -j$(nproc) recoveryimage'
 for n,h in p['files'].items():assert sha(Path(n))==h,n
 for n,t in p['symlinks'].items():assert str(Path(n).readlink())==t
 log=ROOT/p['build_log'];assert sha(log)==p['build_log_sha256']
 assert log.read_text().count('build completed successfully')==2 and 'Deleted images and staging directories' in log.read_text()
 meta=json.loads(image.with_suffix('.json').read_text());assert meta['sha256']==digest and len(meta['profiles'])==6
 entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
 for n,h in meta['binary_hashes'].items():assert hashlib.sha256(entries[n]).hexdigest()==h,n
 old=read('imgs/built/recovery-dijun-unified-timezone-retry.json')
 assert {n for n,h in old['binary_hashes'].items() if meta['binary_hashes'][n]!=h}=={'system/lib64/libtwrpminui.so'}
 n='logs/haptics-probe-profile-runtime.json';runtime=read(n);sources(runtime)
 assert runtime['status']=='PASS' and runtime['image_sha256']==digest and runtime['tests_run']==9 and len(runtime['cases'])==102
 c,=[c for c in index['checks'] if c['evidence']==n];assert c['evidence_sha256']==sha(ROOT/n)
 assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/haptics-probe-final-source-recheck.log').read_text()
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 result=dict(status='PASS',scope=__doc__,image_sha256=digest,sources=732,route_cases=28,worker_FF_cases=6,trace_ABI_cases=14,old_query_failures=2,runtime_groups=9,runtime_calls=102,
 evidence={n:sha(ROOT/n) for n in names+[n,'logs/haptics-probe-before.json','logs/verify-haptics-probe.log','logs/haptics-probe-final-source-recheck.log']},documents={n:sha(ROOT/n) for n in ['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.json','simulation-report.md','docs/archive/haptics/HAPTICS-PROBE-ADAPTATION.md','docs/HAPTICS-ADAPTATION.md']},audit_script_sha256=sha(Path(__file__)))
 (ROOT/'logs/haptics-probe-delivery.json').write_text(json.dumps(result,indent=2)+'\n')
 print('PASS: probe route28/workerFF6/traceABI14,old2 fail,732 sources,profile9/102; physical vibration unresolved.')
if __name__=='__main__':main()
