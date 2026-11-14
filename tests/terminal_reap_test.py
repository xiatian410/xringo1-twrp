#!/usr/bin/env python3
"""Execute original PTY owner with private PTYs and a harmless native child.

Only shell exec and selected syscall failures/wait scheduling are fixtures.
Real getpt/unlockpt/fork/setsid/ioctl/kill/wait/thread are used. No Android
shell commands, physical devices, GUI rendering, process-group cleanup or reboot.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from nested_partition_path_test import ROOT, SRC


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,default=SRC/'gui2/backend/terminal_engine.cpp')
    ap.add_argument('--report',type=Path,required=True)
    ap.add_argument('--admission',action='store_true',help='Check shutdown reservation and final join boundaries')
    ap.add_argument('--engine',action='store_true',help='Execute complete engine and original GUI adapter')
    args=ap.parse_args()
    source=args.source.read_text()
    owner=source[source.index('static int g_pty_fd'):source.index('// UTF-8 decoder')]
    owner=owner.replace('::write(fdMaster, buffer, size)', 'fixture_write(fdMaster, buffer, size)')
    fixture=r'''
#include <atomic>
#include <thread>
#include <chrono>
#include <cassert>
#include <cerrno>
#include <csignal>
#include <cstdlib>
#include <cstdio>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/wait.h>
#include <unistd.h>
#include "twrp_operation_executor.h"
#define LOGERR(...) ((void)0)
#define debug_printf(...) ((void)0)
static std::string scenario;
static std::atomic<bool> allow_wait=false,wait_entered=false;
static int master=-1;static pid_t child=0;static std::atomic<int> reaps=0;
static std::atomic<bool> write_entered=false,allow_write=false;
static std::atomic<int> writes=0;
static int fixture_write(int fd,const char* p,size_t n){
 ++writes;
 if(scenario=="queued-write"){write_entered=true;while(!allow_write.load())std::this_thread::yield();}
 return ::write(fd,p,n);
}
static int fixture_getpt(){master=::getpt();return master;}
static int fixture_unlockpt(int fd){if(scenario=="unlock-failure"){errno=EIO;return -1;}return ::unlockpt(fd);}
static pid_t fixture_fork(){if(scenario=="fork-failure"){errno=EAGAIN;return -1;}child=::fork();return child;}
static int fixture_exec(const char*,const char*,...){
 const char marker='R';::write(STDOUT_FILENO,&marker,1);
 if(scenario=="already-exited")_exit(0);
 for(;;)pause();
}
static pid_t fixture_wait(pid_t pid,int* status,int options){
 wait_entered=true;
 if(scenario=="deferred-reap"&&options==0)while(!allow_wait.load())std::this_thread::yield();
 static bool interrupted=false;
 if(scenario=="wait-eintr"&&!interrupted){interrupted=true;errno=EINTR;return -1;}
 auto ret=::waitpid(pid,status,options);if(ret==pid)++reaps;return ret;
}
#define getpt fixture_getpt
#define unlockpt fixture_unlockpt
#define fork fixture_fork
#define execl fixture_exec
#define waitpid fixture_wait
// OWNER
#undef waitpid
#undef execl
#undef fork
#undef unlockpt
#undef getpt
static bool until(const std::function<bool()>& f){auto end=std::chrono::steady_clock::now()+std::chrono::seconds(2);while(!f()){if(std::chrono::steady_clock::now()>end)return false;std::this_thread::yield();}return true;}
static void ready(){char marker;assert(::read(master,&marker,1)==1&&marker=='R');}
template<class T>void final_shutdown(T& owner){
 if constexpr(requires{owner.shutdown();})owner.shutdown();
 else owner.stop(); // Old final-exit path had only nonblocking stop.
}
int main(int argc,char**argv){assert(argc==2);scenario=argv[1];
 {Pseudoterminal owner;
  auto& executor=twrp_operation_executor::instance();
  if(scenario=="reserved-start"){
   assert(executor.reserve_shutdown());assert(!owner.start());assert(master==-1&&child==0);return 0;
  }
  if(scenario=="unlock-failure"||scenario=="fork-failure"){
   assert(!owner.start());assert(fcntl(master,F_GETFD)==-1&&errno==EBADF);
   owner.stop();puts("failed_start_fd_closed=1");return 0;
  }
  assert(owner.start());ready();
  if(scenario=="reserved-write"){
   assert(executor.reserve_shutdown());assert(owner.write("x",1)==-1);assert(writes==0);
   assert(!owner.start());owner.stop();return 0;
  }
  if(scenario=="queued-write"){
   std::thread input([&]{assert(owner.write("x",1)==1);});
   assert(until([]{return write_entered.load();}));
   bool reserved=executor.reserve_shutdown();allow_write=true;input.join();
   assert(!reserved);assert(executor.reserve_shutdown());owner.stop();return 0;
  }
  if(scenario=="failed-reservation"){
   assert(executor.reserve_shutdown());executor.release_shutdown();
   assert(owner.start()&&owner.write("x",1)==1);owner.stop();return 0;
  }
  if(scenario=="shutdown-wait"){
   scenario="deferred-reap";owner.stop();
   assert(until([]{return wait_entered.load();}));
   std::atomic<bool> finished=false,entered=false;
   std::thread finalizer([&]{entered=true;final_shutdown(owner);finished=true;});
   assert(until([&]{return entered.load();}));
   std::this_thread::sleep_for(std::chrono::milliseconds(30));bool returned=finished.load();
   allow_wait=true;finalizer.join();assert(!returned&&reaps==1);return 0;
  }
  auto start=std::chrono::steady_clock::now();owner.stop();owner.stop();
  assert(std::chrono::steady_clock::now()-start<std::chrono::milliseconds(250));
  assert(!owner.started()&&g_pty_fd==-1);
  if(scenario=="deferred-reap"){
   assert(until([]{return wait_entered.load();}));assert(!owner.start());allow_wait=true;
  }
  assert(until([]{return reaps.load()==1;}));
  if(scenario=="restart"){
   // wait returns just before the owner publishes completion; retry is nonblocking.
   assert(until([&]{return owner.start();}));ready();owner.stop();
   assert(until([]{return reaps.load()==2;}));
  }
 }
 int status;assert(::waitpid(-1,&status,WNOHANG)==-1&&errno==ECHILD);
 puts("nonblocking_stop_owned_child_reaped=1");
}
'''
    if args.engine:
        engine=source
        for header in ['"data.hpp"','"twcommon.h"','"gui2/console/stdio_adapter.h"']:
            engine=engine.replace('#include '+header,'')
        engine=engine.replace('::write(fdMaster, buffer, size)', 'fixture_write(fdMaster, buffer, size)')
        adapter=(SRC/'gui2/backend/twrp_terminal_backend.cpp').read_text()
        fixture=fixture[:fixture.index('// OWNER')]+'''\nstruct DataManager {static void Vibrate(const char*){}};\n'''+engine+'''\n#undef waitpid
#undef execl
#undef fork
#undef unlockpt
#undef getpt
'''+adapter+r'''
static bool until(const std::function<bool()>& f){auto end=std::chrono::steady_clock::now()+std::chrono::seconds(2);while(!f()){if(std::chrono::steady_clock::now()>end)return false;std::this_thread::yield();}return true;}
static void ready(){char marker;assert(::read(master,&marker,1)==1&&marker=='R');}
int main(int argc,char**argv){assert(argc==2);scenario=argv[1];
 auto& executor=twrp_operation_executor::instance();
 if(scenario=="adapter-destructor"){
  {gui2_backend::twrp_terminal_backend adapter;assert(adapter.start());ready();}
  assert(reaps==1);puts("adapter_destructor_reaped=1");return 0;
 }
 gui2_backend::twrp_terminal_backend adapter;
 if(scenario=="engine-reserved-start"){
  assert(executor.reserve_shutdown());assert(!adapter.start());assert(master==-1);return 0;
 }
 assert(adapter.start());ready();
 if(scenario=="engine-reserved-input"){
  assert(executor.reserve_shutdown());assert(!adapter.start());
  adapter.send_line("ignored");adapter.send_byte('x');adapter.send_char('y');adapter.send_key(KEY_UP);
  assert(writes==0);
 }else if(scenario=="engine-normal-input"){
  adapter.send_line("abc");adapter.send_key(KEY_UP);assert(writes==5);
 }else if(scenario=="engine-final-shutdown"){
  scenario="deferred-reap";adapter.stop();
  assert(until([]{return wait_entered.load();}));
  std::atomic<bool> entered=false,finished=false;
  std::thread finalizer([&]{entered=true;adapter.shutdown();finished=true;});
  assert(until([&]{return entered.load();}));
  std::this_thread::sleep_for(std::chrono::milliseconds(30));bool returned=finished.load();
  allow_wait=true;finalizer.join();assert(!returned&&reaps==1);
 }
 adapter.shutdown();adapter.shutdown();assert(!adapter.running()&&reaps==1);
 puts("complete_engine_adapter_boundary=1");
}
'''
    else:
        fixture=fixture.replace('// OWNER',owner)
    fixture=fixture.replace('#include <atomic>','#include <atomic>\n#include <functional>\n#include <string>')
    cases=[]
    with tempfile.TemporaryDirectory(prefix='terminal-reap-') as tmp:
        p=Path(tmp);(p/'test.cpp').write_text(fixture)
        command=['g++','-std=c++23','-pthread','-O1','-g','-fsanitize=address,undefined','-fno-pie','-no-pie','-I'+str(SRC),'-I'+str(SRC/'gui2/backend'),str(p/'test.cpp'),str(SRC/'twrp_operation_executor.cpp'),'-o',str(p/'test')]
        subprocess.run(command,check=True)
        names=['reserved-start','reserved-write','queued-write','failed-reservation','shutdown-wait'] if args.admission else ['unlock-failure','fork-failure','stop','already-exited','wait-eintr','deferred-reap','restart']
        if args.engine:names=['engine-reserved-start','engine-reserved-input','engine-normal-input','engine-final-shutdown','adapter-destructor']
        for name in names:
            r=subprocess.run([str(p/'test'),name],capture_output=True,text=True,timeout=5)
            cases.append(dict(case=name,status='PASS' if r.returncode==0 else 'FAIL',returncode=r.returncode,output=r.stdout+r.stderr))
            print(name,cases[-1]['status'],flush=True)
    sources=[args.source,Path(__file__),ROOT/'tests/nested_partition_path_test.py',SRC/'twrp_operation_executor.h',SRC/'twrp_operation_executor.cpp']
    if args.engine:sources += [SRC/'gui2/backend'/n for n in ['terminal_engine.h','terminal_backend.h','twrp_terminal_backend.h','twrp_terminal_backend.cpp']]
    result=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,cases=cases,sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},compile_command=command)
    args.report.write_text(json.dumps(result,indent=2)+'\n')
    return result['status']!='PASS'


if __name__=='__main__':
    raise SystemExit(main())
