#!/usr/bin/env python3
"""Execute original launch/reboot methods with real executor tickets and threads.

For --source old launch/reboot methods, the current executor is deliberately
retained to isolate missing launch/publication wiring. Worker bodies, GUI
status/partition data, sync and reboot target publication are
fixtures. No GUI/USB/TEE/slot/device or final reboot; no shell access restriction.
"""
import argparse, hashlib, json, subprocess, tempfile
from pathlib import Path
from nested_partition_path_test import ROOT, SRC, method

ENTRIES = {
 'backup': [('start()', 'start()')],
 'restore': [('start(const std::vector<std::string>& mount_points)', 'start({"/data"})')],
 'install': [('start_zip(const std::vector<std::string>& paths)', 'start_zip({"/fixture.zip"})'),
             ('start_image(const std::string& path, const std::string& mount_point,', 'start_image("/fixture.img","/boot",false)')],
 'wipe': [('start(std::vector<std::string> args)', 'start({"data"})')],
 'decrypt': [('start(const std::string& password)', 'start("fixture")'), ('start_refresh()', 'start_refresh()')],
 'tools': [('start(tool_job job, const std::string& target, const std::string& value)', 'start(tool_job::REPAIR,"/data","")')],
 'sideload': [('start(bool wipe_dalvik, bool wipe_cache)', 'start(false,false)')],
}

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,default=SRC);ap.add_argument('--report',type=Path,required=True);a=ap.parse_args()
 sources=[Path(__file__),ROOT/'tests/nested_partition_path_test.py',SRC/'twrp_operation_executor.h',SRC/'twrp_operation_executor.cpp']
 runs = {
  'backup': 'void run(){wait();}',
  'restore': 'void run(std::string){wait();}',
  'install': 'void run_zip(std::vector<std::string>){wait();} void run_image(std::string,std::string,bool){wait();}',
  'wipe': 'void run(std::vector<std::string>){wait();}',
  'decrypt': 'void run(std::string,int){wait();} void run_refresh(){wait();}',
  'tools': 'void run(tool_job,std::string,std::string){wait();}',
  'sideload': 'void run(){wait();}',
 }
 classes=[];dispatch=[]
 for name,entries in ENTRIES.items():
  p=a.source/f'gui2/backend/twrp_{name}_backend.cpp';sources.append(p)
  bodies=[];decl=[]
  for num,(sig,call) in enumerate(entries):
   body=method(p.read_text(),f'bool twrp_{name}_backend::{sig}');bodies.append(body)
   declaration=body[:body.index('{')].replace(f'twrp_{name}_backend::','')+';';decl.append(declaration)
   dispatch.append(f'if(label=="{name}-{num}"){{twrp_{name}_backend b;execute([&]{{return b.{call};}},b);}}')
  classes.append(f'''class twrp_{name}_backend {{ public:
 std::atomic<bool> running_{{false}},cancelled_{{false}};
 std::thread worker_,cancel_worker_;std::mutex mutex_;int state_=0,selected_id_=0;
 std::string opened_="/backup";Status status_;std::chrono::steady_clock::time_point started_;
 void join_finished_thread(){{if(worker_.joinable())worker_.join();}}
 void join_threads(){{join_finished_thread();}}
 bool partition_tool_target_allowed(const std::string&){{return true;}}
 ~twrp_{name}_backend(){{join_finished_thread();}}
 void wait(){{++entered;while(!release_worker.load())std::this_thread::yield();}}
 {runs[name]}
 {''.join(decl)}
 }};
 {''.join(bodies)}''')
 reboot=a.source/'gui2/backend/twrp_reboot_backend.cpp';sources.append(reboot)
 reboot_methods='\n'.join(method(reboot.read_text(),s) for s in ['bool twrp_reboot_backend::is_supported(', 'const char* twrp_reboot_backend::reboot_argument(', 'bool twrp_reboot_backend::request_reboot('])
 code=r'''
#include <atomic>
#include <cassert>
#include <chrono>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include <cstdio>
#include "twrp_operation_executor.h"
#include "reboot_backend.h"
static std::atomic<int> entered=0,mutations=0;static std::atomic<bool> release_worker=false;
static bool write_ok=true,enabled=true;static int syncs=0;static std::string target;
struct DataManager {
 static int SetValue(const char* k,const char* v){++mutations;if(std::string(k)=="tw_reboot_arg"){if(!write_ok)return -1;target=v;}return 0;}
 template<class T> static int SetValue(const char*,T){++mutations;return 0;}
 static std::string GetStrValue(const char*){return {};}
};
struct Part {std::string GetMountPoint(){return "/boot";}};using TWPartition=Part;
struct Manager {bool stop_backup=false;Part* FindPartitionByPath(const std::string&){return nullptr;}} PartitionManager;
#define TW_MAX 1
#define LOGINFO(...) ((void)0)
#define TW_BACKUP_NAME "name"
struct Status {int state=0,total=0;std::vector<std::string> items;};
struct backup_state {enum{RUNNING};};struct restore_state {enum{RUNNING};};
struct install_state {enum{RUNNING};};struct wipe_state {enum{RUNNING};};
struct decrypt_state {enum{RUNNING};};struct tool_state {enum{RUNNING};};
struct sideload_state {enum{RUNNING};};enum class tool_job{REPAIR,RESIZE,CHANGE_FILE_SYSTEM};
bool is_restricted_mount_path(const std::string&){return false;}
namespace gui2_backend {
class twrp_reboot_backend { public:
 reboot_capabilities cap{true,true,true,true,true,true,true,true};
 const reboot_capabilities& capabilities()const {auto* self=const_cast<twrp_reboot_backend*>(this);self->cap.system=enabled;return cap;}
 bool is_supported(reboot_target)const;const char* reboot_argument(reboot_target)const;bool request_reboot(reboot_target);
};
static void fixture_sync(){++syncs;}
#define sync fixture_sync
// REBOOT
#undef sync
// CLASSES
static std::string mode;
template<class F,class B> void execute(F start,B& backend){
 twrp_reboot_backend reboot;
 if(mode=="reserved"){
  assert(reboot.request_reboot(reboot_target::SYSTEM));int before=mutations;
  assert(!start());assert(mutations==before&&entered==0&&!backend.worker_.joinable());
 }else if(mode=="queued"){
  assert(start());assert(!reboot.request_reboot(reboot_target::SYSTEM));
  assert(target.empty()&&syncs==0);release_worker=true;backend.worker_.join();
  assert(entered==1);assert(reboot.request_reboot(reboot_target::SYSTEM));
  assert(!start());
 }else if(mode=="failed-publication"){
  write_ok=false;assert(!reboot.request_reboot(reboot_target::SYSTEM));write_ok=true;
  assert(start());release_worker=true;backend.worker_.join();assert(entered==1);
  assert(reboot.request_reboot(reboot_target::SYSTEM));
 }
 std::puts("launch_admission_and_shutdown_order=1");
}
}
int main(int argc,char**argv){assert(argc==3);using namespace gui2_backend;
 std::string label=argv[1];mode=argv[2];
 auto& executor=twrp_operation_executor::instance();
 if(label=="executor-race"){
  for(int i=0;i<128;++i){
   std::atomic<bool> go=false;bool reserved=false;twrp_operation_executor::admission ticket;
   std::thread job([&]{while(!go.load())std::this_thread::yield();ticket=executor.admit_job();});
   std::thread stop([&]{while(!go.load())std::this_thread::yield();reserved=executor.reserve_shutdown();});
   go=true;job.join();stop.join();assert(reserved!=bool(ticket));
   ticket.reset();if(reserved)executor.release_shutdown();
  }
  std::puts("atomic_admission_reservation_race=128");return 0;
 }
 if(label=="ticket-release"){
  {auto ticket=executor.admit_job();assert(ticket&&!executor.reserve_shutdown());}
  assert(executor.reserve_shutdown());assert(!executor.admit_job());executor.release_shutdown();
  auto ticket=executor.admit_job();auto worker=executor.worker(std::move(ticket),[]{++entered;});
  worker.join();assert(entered==1&&executor.reserve_shutdown());
  std::puts("ticket_scope_and_worker_release=1");return 0;
 }
 // DISPATCH
}
'''.replace('// REBOOT',reboot_methods).replace('// CLASSES','\n'.join(classes)).replace('// DISPATCH','\n'.join(dispatch))
 rows=[]
 with tempfile.TemporaryDirectory(prefix='shutdown-admission-') as tmp:
  p=Path(tmp);(p/'test.cpp').write_text(code)
  cmd=['g++','-std=c++23','-pthread','-O1','-g','-fsanitize=address,undefined','-fno-pie','-no-pie','-I'+str(SRC),'-I'+str(SRC/'gui2/backend'),str(p/'test.cpp'),str(SRC/'twrp_operation_executor.cpp'),'-o',str(p/'test')]
  subprocess.run(cmd,check=True)
  for name,entries in ENTRIES.items():
   for i,_ in enumerate(entries):
    for mode in ['reserved','queued','failed-publication']:
     label=f'{name}-{i}';r=subprocess.run([str(p/'test'),label,mode],capture_output=True,text=True,timeout=8)
     rows.append(dict(case=f'{label}-{mode}',status='PASS' if r.returncode==0 else 'FAIL',output=r.stdout+r.stderr,returncode=r.returncode));print(rows[-1]['case'],rows[-1]['status'],flush=True)
  for label in ['executor-race','ticket-release']:
   r=subprocess.run([str(p/'test'),label,'executor'],capture_output=True,text=True,timeout=8)
   rows.append(dict(case=label,status='PASS' if r.returncode==0 else 'FAIL',output=r.stdout+r.stderr,returncode=r.returncode))
   print(label,rows[-1]['status'],flush=True)
 report=dict(status='PASS' if all(c['status']=='PASS' for c in rows) else 'FAIL',scope=__doc__,cases=rows,sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
 a.report.write_text(json.dumps(report,indent=2)+'\n');return report['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
