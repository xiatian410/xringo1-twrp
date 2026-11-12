#!/usr/bin/env python3
"""Execute production MTP storage receiver over real sequenced-packet sockets; no USB device."""
import argparse,hashlib,json,os,subprocess,tempfile
from pathlib import Path
from backup_session_test import method
ROOT=Path(__file__).resolve().parents[1]
REC=Path('/root/AAA/twrp/bootable/recovery')
CASES=['no-fd','eof','add','remove','eintr','short','oversized','bad-path','bad-display','zero-id','unknown']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,default=REC);ap.add_argument('--report',type=Path,default=ROOT/'logs/mtp-receiver.json');a=ap.parse_args()
 src=a.source/'mtp/twrp/TwrpMtpServer.cpp'
 code=method(src.read_text(),'int TwrpMtpServer::MtpPipeThread(')
 harness=ROOT/'tests/mtp_receiver_test.cpp'
 with tempfile.TemporaryDirectory(prefix='dijun-mtp-receiver-') as tmp:
  tmp=Path(tmp);(tmp/'test.cpp').write_text(harness.read_text().replace('// PRODUCTION_METHOD',code))
  cmd=['g++','-std=gnu++17','-O1','-g','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-I'+str(REC/'mtp/twrp'),str(tmp/'test.cpp'),'-Wl,--wrap=recv','-Wl,--wrap=read','-o',str(tmp/'test')]
  subprocess.run(cmd,check=True);cases=[]
  for case in CASES:
   try:
    p=subprocess.run([str(tmp/'test'),case],capture_output=True,text=True,timeout=5,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:halt_on_error=1'))
    r=dict(case=case,status='PASS' if p.returncode==0 else 'FAIL',returncode=p.returncode,output=p.stdout+p.stderr)
   except subprocess.TimeoutExpired as e:r=dict(case=case,status='FAIL',returncode=124,output=str(e))
   cases.append(r);print(r['status'],case,flush=True)
 report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,sources={str(src):sha(src)},shared_sources={str(REC/'mtp/twrp/MtpMessage.hpp'):sha(REC/'mtp/twrp/MtpMessage.hpp')},test_sources={str(p):sha(p) for p in [Path(__file__).resolve(),harness,ROOT/'tests/backup_session_test.py']},cases=cases,compile_command=cmd,boundaries=['Actual receiver loop; storage add/remove implementation is a substitute that records arguments.','Real sockets, framing, EOF and EINTR. No full database, mount or decrypted-storage integration.'])
 a.report.write_text(json.dumps(report,indent=2)+'\n');return report['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
