#!/usr/bin/env python3
"""Production manager MTP enable/disable/readout/messages and actual fork; property/USB/server boundaries."""
import argparse,hashlib,json,os,signal,subprocess,tempfile,concurrent.futures,shutil
from pathlib import Path
from backup_session_test import method
ROOT=Path(__file__).resolve().parents[1]
REC=Path('/root/AAA/twrp/bootable/recovery')
CASES=['worker-exit','legacy','parent-death','normal','repeat','reconnect','child-exit','child-dies','externally-reaped','fork-fail','socket-fail','request-fail','ready-clear-fail','usb-error','superseded','startup-timeout','no-ready','ready-lost','wait-eintr','wait-error','stop-timeout','kill-denied','adb-timeout','adb-error','adb-set-fail','shutdown-no-fork','read-lock-busy','message-add','message-remove','message-eintr','message-short','message-peer-gone','message-path-long','message-name-long','message-id-zero','message-unmounted','message-vfat','message-null','message-unknown','queue-full']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,default=REC);ap.add_argument('--report',type=Path,default=ROOT/'logs/mtp-caller.json');a=ap.parse_args()
 pm=(a.source/'partitionmanager.cpp').read_text()
 signatures=['bool TWPartitionManager::EnableMtp(', 'bool TWPartitionManager::DisableMtp(', 'void TWPartitionManager::AddAllMtpStorage(', 'bool TWPartitionManager::AddRemoveMtpStorage(']
 modern='bool TWPartitionManager::IsMtpEnabled(' in pm
 if modern:signatures.append('bool TWPartitionManager::IsMtpEnabled(')
 code='\n'.join(method(pm,s) for s in signatures)
 if not modern:code+='\nbool TWPartitionManager::IsMtpEnabled() const {return DataManager::GetIntValue("tw_mtp_enabled")!=0;}'
 with tempfile.TemporaryDirectory(prefix='dijun-mtp-caller-') as tmp:
  tmp=Path(tmp);(tmp/'TwrpMtp.cpp').write_bytes((a.source/'mtp/twrp/TwrpMtp.cpp').read_bytes())
  # Header substitutes only the USB server: real production ForkServer and Start execute.
  (tmp/'TwrpMtp.hpp').write_text('''#pragma once
#include <string>
#include <vector>
#include <sys/types.h>
#include <unistd.h>
#include <cstdlib>
namespace android {
inline bool test_server_exit=false;
inline int test_server_ready_fd=-1;
struct Storage {std::string display,mount;int mtp_id;uint64_t max_file_size;};
using Storages=std::vector<Storage>;
struct MtpDebug {static void enableDebug(){}};
class TwrpMtpServer {public:static TwrpMtpServer* Create(){static TwrpMtpServer s;return &s;} void SetStorages(const Storages*){} void SetReadPipe(int){} void Start(){if(test_server_exit)return;if(test_server_ready_fd>=0){char ready=1;(void)write(test_server_ready_fd,&ready,1);}for(;;)pause();}};
class TwrpMtp {public: explicit TwrpMtp(int=0);pid_t ForkServer(int[2]);void AddStorage(const std::string&,const std::string&,int,uint64_t);private:void Start()const;Storages mtp_storages_;int mtp_read_pipe_=-1;};
}
''')
  # Only logging header changes in this compilation copy.
  p=tmp/'TwrpMtp.cpp';p.write_text(p.read_text().replace('#include "../MtpDebug.h"',''))
  h=(ROOT/'tests/mtp_caller_test.cpp').read_text().replace('// PRODUCTION_METHODS',code)
  (tmp/'test.cpp').write_text(h+'\n#include "TwrpMtp.cpp"\n')
  cmd=['g++','-std=c++17','-O1','-g','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer','-fno-pie','-no-pie','-I'+str(tmp),'-I'+str(REC/'mtp'),'-I'+str(REC/'mtp/twrp'),str(tmp/'test.cpp'),*[f'-Wl,--wrap={n}' for n in ['fork','kill','waitid','send','socketpair']],'-o',str(tmp/'test')]
  subprocess.run(cmd,check=True)
  def run(case):
   try:
    p=subprocess.Popen([str(tmp/'test'),case],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:halt_on_error=1'))
    out,err=p.communicate(timeout=22)
    result=dict(case=case,status='PASS' if p.returncode==0 else 'FAIL',returncode=p.returncode,output=out+err)
   except subprocess.TimeoutExpired as e:
    os.killpg(p.pid,signal.SIGKILL);p.communicate()
    result=dict(case=case,status='FAIL',returncode=124,output=str(e))
   print(result['status'],case,flush=True);return result
  # Each process is independent, real timeout cases may run concurrently.
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:cases=list(pool.map(run,CASES))
  names=['partitionmanager.cpp','partitions.hpp','gui2/backend/twrp_mount_backend.cpp','mtp/twrp/TwrpMtp.cpp','mtp/twrp/TwrpMtpServer.cpp']
  sources={str(a.source/n):sha(a.source/n) for n in names}
  shared={str(REC/'mtp/MtpProcess.h'):sha(REC/'mtp/MtpProcess.h'),str(REC/'mtp/twrp/MtpMessage.hpp'):sha(REC/'mtp/twrp/MtpMessage.hpp')}
  report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,sources=sources,shared_sources=shared,test_sources={str(p):sha(p) for p in [Path(__file__).resolve(),ROOT/'tests/mtp_caller_test.cpp',ROOT/'tests/backup_session_test.py']},cases=cases,compile_command=cmd,boundaries=['Actual extracted manager functions, actual production ForkServer/Start and process helper, real sockets/processes/signals/waits. USB server and Android property acknowledgements are substitutes.','No full mount/UI/init integration or Windows enumeration. Receiver method has a separate host harness; actual process-parent death and temporary worker exit use real processes/threads; a subreaper contains the fixture.','Stop timeout simulated by suppressing SIGKILL delivery to this fixture child; no kernel D-state or physical phone.'])
  a.report.write_text(json.dumps(report,indent=2)+'\n')
 return report['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
