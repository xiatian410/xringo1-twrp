#!/usr/bin/env python3
"""Original slot manager/backend and GUI callbacks with explicit HAL/UI doubles.

No slot, mount, phone or physical reboot. Tests failure state publication and
callback control flow, not a rendered full GUI or durable bootloader state.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from nested_partition_path_test import ROOT, SRC, method


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--before', action='store_true')
    args = ap.parse_args()
    base = ROOT / 'logs/slot-result-before' if args.before else SRC
    manager = base / 'partitionmanager.cpp'
    backend = base / 'gui2/backend/twrp_reboot_backend.cpp'
    gui = base / 'gui2/gui2.cpp'
    signature = ('void' if args.before else 'bool') + ' TWPartitionManager::SetActiveSlot('
    methods = method(manager.read_text(), signature)
    methods += '\nnamespace gui2_backend {\n' + method(backend.read_text(), 'bool twrp_reboot_backend::set_active_slot(') + '\n}\n'
    methods += '\n' + method(gui.read_text(), 'static void backup_set_slot(')
    methods += '\n' + method(gui.read_text(), 'static void reboot_confirmation_complete(void* user_data) {')
    code = r'''
#include <cassert>
#include <cstdio>
#include <string>
#include <memory>
#include <mutex>
#include <type_traits>
#include <sys/mount.h>
#include "twrp_operation_executor.h"
#define LOGERR(...) ((void)0)
#define LOGINFO(...) ((void)0)
static bool service_ok=true,hal_ok=true,processed=true,slots=true;
static int hal_calls=0,publishes=0,updates=0,end_status=-1,starts=0,unmounts=0,errors=0,navigations=0,requests=0;
static std::string published;
namespace gui2_console {template<class... T>void log_error(T...){++errors;}}
struct DataManager {static void SetValue(const char*,const std::string& s){++publishes;published=s;}};
struct BootControlClient {
 static std::shared_ptr<BootControlClient> WaitForService(){return service_ok?std::make_shared<BootControlClient>():nullptr;}
 std::pair<bool,std::string> SetActiveBootSlot(int n){++hal_calls;assert(n==0||n==1);return {hal_ok,"injected"};}
};
struct TWPartitionManager {
 std::string active_slot_display_="A";
 // DECLARATION
 bool FstabProcessed(){return processed;}
 void UpdateSystemDetails(){++updates;}
 bool FindPartitionByPath(const char*){return true;}
 bool UnmountByPath(const char*,bool,int=0){++unmounts;return true;}
} PartitionManager;
namespace gui2_backend {
enum class boot_slot {A,B};enum class reboot_target {SYSTEM};
struct twrp_reboot_backend {
 struct Caps {bool boot_slots;};Caps capabilities(){return {slots};}
 bool set_active_slot(boot_slot);
 bool request_reboot(reboot_target){++requests;return true;}
};
void operation_start(const char*){++starts;}void operation_end(int status){end_status=status;}
}
namespace gui2_pages {struct reboot_page_state {bool target_selected=true,slot_pending=true,has_error=false;gui2_backend::boot_slot pending_slot=gui2_backend::boot_slot::B;gui2_backend::reboot_target selected_target=gui2_backend::reboot_target::SYSTEM;};}
static gui2_backend::twrp_reboot_backend rebooter;static auto* reboot=&rebooter;
struct {struct {void* name_input=nullptr;}backup_view;std::string backup_name;int backup_active_tab=0;}page_state;
static std::string textarea_text(void*){return "keep-name";}
enum class page_kind{BACKUP,REBOOT};enum class page_transition{REPLACE};
static void navigate_to(page_kind,void*,page_transition){++navigations;}
static bool reboot_requested=false;
// METHODS
// Accept historical void core for state comparison; it cannot expose failure.
template<class F>static bool invoke(F f){if constexpr(std::is_void_v<decltype(f())>){f();return true;}else return f();}
int main(int argc,char**argv){
 assert(argc==2);std::string name=argv[1];bool result;
 service_ok=name.find("no-service")==std::string::npos;
 hal_ok=name.find("hal-fail")==std::string::npos;
 if(name=="initial") {PartitionManager.active_slot_display_.clear();processed=false;}
 if(name=="unsupported")slots=false;
 const bool expected_failure=!service_ok||!hal_ok||name=="invalid"||name=="unsupported";
 if(name.starts_with("backup-")){
  backup_set_slot(gui2_backend::boot_slot::B);
  if(expected_failure)assert(errors>0&&navigations==0&&page_state.backup_name=="keep-name"&&page_state.backup_active_tab==0);
  else assert(navigations==1&&page_state.backup_active_tab==1);
 }else if(name.starts_with("reboot-")){
  gui2_pages::reboot_page_state state;reboot_confirmation_complete(&state);
  if(expected_failure)assert(state.has_error&&state.slot_pending&&!reboot_requested&&requests==0&&navigations==1);
  else assert(!state.has_error&&!state.slot_pending&&reboot_requested&&requests==1);
 }else if(name=="backend-hal-fail"||name=="unsupported"){
  result=reboot->set_active_slot(gui2_backend::boot_slot::B);assert(!result);
  if(name=="unsupported")assert(starts==0&&unmounts==0);else assert(end_status==1);
 }else {
  const std::string slot=name=="same"?"A":name=="invalid"?"C":"B";
  result=invoke([&]{return PartitionManager.SetActiveSlot(slot);});
  if(expected_failure)assert(!result);else assert(result);
 }
 if(expected_failure)assert(PartitionManager.active_slot_display_=="A"&&publishes==0&&updates==0);
 else if(name=="same")assert(hal_calls==0&&publishes==0&&updates==0);
 else if(name=="initial")assert(PartitionManager.active_slot_display_=="B"&&hal_calls==0&&publishes==0&&updates==0);
 else assert(PartitionManager.active_slot_display_=="B"&&hal_calls==1&&publishes==1&&published=="B"&&updates==1);
 std::puts("slot_state_and_callback_checked=1");
}
'''
    code = code.replace('// DECLARATION', ('void' if args.before else 'bool') + ' SetActiveSlot(const std::string&);').replace('// METHODS', methods)
    names = ['success','same','initial','invalid','no-service','hal-fail','backend-hal-fail','unsupported',
             'backup-success','backup-no-service','backup-hal-fail','reboot-success','reboot-no-service','reboot-hal-fail']
    rows = []
    with tempfile.TemporaryDirectory(prefix='slot-result-') as temp:
        w = Path(temp); (w/'test.cpp').write_text(code)
        cmd = ['g++','-std=c++23','-O1','-g','-DAB_OTA_UPDATER','-fsanitize=address,undefined','-pthread',
               '-I'+str(SRC),str(w/'test.cpp'),str(SRC/'twrp_operation_executor.cpp'),'-o',str(w/'test')]
        subprocess.run(cmd,check=True)
        for name in names:
            r = subprocess.run([str(w/'test'),name],capture_output=True,text=True,timeout=5)
            rows.append(dict(case=name,status='PASS' if r.returncode==0 else 'FAIL',exit=r.returncode,output=r.stdout+r.stderr))
            print(name,rows[-1]['status'],flush=True)
    paths = [manager,backend,gui,Path(__file__),ROOT/'tests/nested_partition_path_test.py',SRC/'twrp_operation_executor.h',SRC/'twrp_operation_executor.cpp',base/'partitions.hpp']
    report = dict(status='PASS' if all(c['status']=='PASS' for c in rows) else 'FAIL',scope=__doc__,cases=rows,
                  sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    (ROOT/('logs/slot-result-negative.json' if args.before else 'logs/slot-result.json')).write_text(json.dumps(report,indent=2)+'\n')
    return report['status']!='PASS'


if __name__=='__main__':
    raise SystemExit(main())
