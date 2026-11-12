#!/usr/bin/env python3
"""Pair existing field FF stop/erase transactions; no new phone or motor evidence."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 capture=ROOT/'imgs/built/1/touch-after-raw-off.txt';records=[]
 for n,line in enumerate(capture.read_bytes().decode('utf-16').splitlines(),1):
  m=re.fullmatch(r'\[\s*([\d.]+)\] xring-haptic 0-0043: (.*)',line)
  if m:records.append(dict(time=float(m[1]),message=m[2],line=n))
 starts=[i for i,r in enumerate(records) if r['message']=='cs40l26_playback_effect: effect ID = 0, val = 0']
 assert len(starts)==43
 transactions=[]
 for number,start in enumerate(starts):
  end=starts[number+1] if number+1<len(starts) else len(records);chunk=records[start:end]
  def one(text):
   rs=[r for r in chunk if r['message']==text];assert len(rs)==1,(number,text,rs);return rs[0]
  erase=one('cs40l26_erase_effect: effect ID = 0');stopdone=one('cs40l26_vibe_stop_worker: done')
  worker=one('cs40l26_erase_worker: effect ID = 0');done=one('cs40l26_erase_worker: effect ID = 0 done, cs40l26->erase_ret = 0')
  stopindex=next(i for i,r in enumerate(chunk) if r['message']=='cs40l26_vibe_stop_worker:')
  assert records[start]['time']<=erase['time']<=chunk[stopindex]['time']<=stopdone['time']<=worker['time']<=done['time']
  transactions.append(dict(index=number,stop_request=records[start],erase_request=erase,stop_worker=chunk[stopindex],stop_done=stopdone,erase_worker=worker,erase_done=done,request_to_done_ms=round((done['time']-records[start]['time'])*1000,3)))
 allreturns=[r for r in records if 'cs40l26->erase_ret =' in r['message']]
 assert len(allreturns)==43 and all(r['message'].endswith('erase_ret = 0') for r in allreturns)
 report=dict(status='OBSERVED',scope=__doc__,transactions=transactions,count=43,
  max_request_to_done_ms=max(t['request_to_done_ms'] for t in transactions),
  conclusion='All43 observed stop0 requests are followed by original stop-worker completion and erase_ret0 before the next stop request. No erase timeout is visible in this capture; synthetic stop-only timeout is not established as this field fault.',
  limitations='No userspace ioctl return trace, caller identity, exact vendor ff-core source, electrical output or physical motor proof. No claim about later images or unlogged transactions.',
  sources={str(p.relative_to(ROOT)):sha(p) for p in [capture,Path(__file__)]})
 (ROOT/'logs/haptics-erase-field-observation.json').write_text(json.dumps(report,indent=2)+'\n')
 print('OBSERVED:43 stop/erase transactions, all erase_ret0; max ms',report['max_request_to_done_ms'])
if __name__=='__main__':main()
