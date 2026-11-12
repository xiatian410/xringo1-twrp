#!/usr/bin/env python3
"""Check production request trace semantics and unchanged FF ABI on syscall fixtures.

No physical motor, driver, kernel scheduling or device log is executed.
"""
import argparse,hashlib,json,re,tempfile
from pathlib import Path
from haptics_driver_emulation import capture,ROOT,SOURCE
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return json.loads((ROOT/n).read_text())
def traces(text,prefix):
 return [dict(re.findall(r'(\w+)=([^\s]+)',l)) for l in text.splitlines() if l.startswith(prefix) and 'phase=' in l]
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--route',default='logs/haptics-request-trace-route.json')
 parser.add_argument('--route-count',type=int,default=24)
 parser.add_argument('--worker-ff',default='logs/haptics-request-trace-worker-ff.json')
 parser.add_argument('--worker-count',type=int,default=4)
 parser.add_argument('--output',default='logs/haptics-request-trace.json')
 args=parser.parse_args()
 reports=[args.route,args.worker_ff,'logs/haptics-worker.json']
 cases=[];sources={}
 for name,count in zip(reports,[args.route_count,args.worker_count,16]):
  r=read(name);assert r['status']=='PASS' and len(r['cases'])==count
  for group in ['sources','shared_sources','test_sources','configuration']:
   for n,h in r.get(group,{}).items():assert sha(Path(n))==h,n;sources[n]=h
 route={c['case']:c for c in read(reports[0])['cases']}
 for label,phase,error in [('ff-upload-error','upload-end',5),('ff-play-error','play-end',19),('ff-erase-error','erase-end',62)]:
  rows=traces(route[label]['output'],'FF haptics:')
  hit,=[e for e in rows if e['phase']==phase and e['result']=='-1']
  assert int(hit['errno'])==error and int(hit['pid'])>0 and int(hit['tid'])>0
  cases.append(dict(case=label,trace=hit,status='PASS'))
 rows=traces(route['ff-play-short']['output'],'FF haptics:');hit,=[e for e in rows if e['phase']=='play-end'];assert hit['result']=='1' and hit['errno']=='0';cases.append(dict(case='short-event-write',trace=hit,status='PASS'))
 for label in ['ff-first','ff-erase-error']:
  rows=traces(route[label]['output'],'FF haptics:')
  for request in {e['request'] for e in rows if e['request']!='0'}:
   seq=[e for e in rows if e['request']==request];times=[int(e['monotonic_ms']) for e in seq];assert times==sorted(times)
 worker={c['case']:c for c in read(reports[2])['cases']}
 for label in ['latest-only','expired']:
  rows=traces(worker[label]['output'],'GUI2 haptics:')
  e,=[e for e in rows if e['request']=='5002' and e['phase'] in ['begin','expired']]
  assert e['replaced']=='5000' and e['duration_ms']=='160'
  assert e['phase']==('expired' if label=='expired' else 'begin')
  cases.append(dict(case=label,trace=e,status='PASS'))
 before=read('logs/haptics-driver-emulation.json');expected={c['requested_ms']:c for c in before['fixture_bytes']}
 with tempfile.TemporaryDirectory(prefix='haptics-trace-abi-') as temp:
  for ms,effect,event in capture(Path(temp)):
   assert effect.hex()==expected[ms]['effect_hex']
   old=bytes.fromhex(expected[ms]['event_hex']);assert event[16:]==old[16:] # timestamps are deliberately not meaningful
   cases.append(dict(case='ABI-'+str(ms),status='PASS',requested_ms=ms,effect_hex=effect.hex(),event_payload_hex=event[16:].hex()))
 for p in [SOURCE,SOURCE.with_suffix('.h'),ROOT/'tests/haptics_driver_capture.cpp',ROOT/'tests/haptics_driver_emulation.py',Path(__file__).resolve()]:sources[str(p)]=sha(p)
 report=dict(status='PASS',scope=__doc__,cases=cases,count=len(cases),sources=sources,input_reports={n:sha(ROOT/n) for n in reports},baseline_report_sha256=sha(ROOT/'logs/haptics-driver-emulation.json'))
 (ROOT/args.output).write_text(json.dumps(report,indent=2)+'\n');print('PASS:',len(cases),'trace/ABI checks; route'+str(args.route_count)+'/worker-FF'+str(args.worker_count)+'/owner16; motor unknown')
if __name__=='__main__':main()
