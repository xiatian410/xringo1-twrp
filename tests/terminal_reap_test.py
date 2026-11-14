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
    args=ap.parse_args()
    source=args.source.read_text()
    owner=source[source.index('static int g_pty_fd'):source.index('// UTF-8 decoder')]
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
#define LOGERR(...) ((void)0)
#define debug_printf(...) ((void)0)
static std::string scenario;
static std::atomic<bool> allow_wait=false,wait_entered=false;
static int master=-1;static pid_t child=0;static std::atomic<int> reaps=0;
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
int main(int argc,char**argv){assert(argc==2);scenario=argv[1];
 {Pseudoterminal owner;
  if(scenario=="unlock-failure"||scenario=="fork-failure"){
   assert(!owner.start());assert(fcntl(master,F_GETFD)==-1&&errno==EBADF);
   owner.stop();puts("failed_start_fd_closed=1");return 0;
  }
  assert(owner.start());ready();
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
    fixture=fixture.replace('#include <atomic>','#include <atomic>\n#include <functional>\n#include <string>').replace('// OWNER',owner)
    cases=[]
    with tempfile.TemporaryDirectory(prefix='terminal-reap-') as tmp:
        p=Path(tmp);(p/'test.cpp').write_text(fixture)
        command=['g++','-std=c++23','-pthread','-O1','-g','-fsanitize=address,undefined','-fno-pie','-no-pie',str(p/'test.cpp'),'-o',str(p/'test')]
        subprocess.run(command,check=True)
        for name in ['unlock-failure','fork-failure','stop','already-exited','wait-eintr','deferred-reap','restart']:
            r=subprocess.run([str(p/'test'),name],capture_output=True,text=True,timeout=5)
            cases.append(dict(case=name,status='PASS' if r.returncode==0 else 'FAIL',returncode=r.returncode,output=r.stdout+r.stderr))
            print(name,cases[-1]['status'],flush=True)
    sources=[args.source,Path(__file__),ROOT/'tests/nested_partition_path_test.py']
    result=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,cases=cases,sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},compile_command=command)
    args.report.write_text(json.dumps(result,indent=2)+'\n')
    return result['status']!='PASS'


if __name__=='__main__':
    raise SystemExit(main())
