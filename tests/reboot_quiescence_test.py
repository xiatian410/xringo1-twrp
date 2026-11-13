#!/usr/bin/env python3
"""Execute main's original backend scope and real destructor/CLI joins with threads.

GUI, storage work, controllers, intent and final reboot are explicit fixtures.
No Android GUI, Binder, USB, mount, device or actual reboot is executed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from nested_partition_path_test import ROOT, SRC, method


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, default=SRC)
    ap.add_argument('--report', type=Path, required=True)
    ap.add_argument('--old-main', action='store_true')
    ap.add_argument('--old-background', action='store_true')
    args = ap.parse_args()
    main_source = args.source / 'twrp.cpp'
    background = args.source / 'gui2/backend/twrp_background_backend.cpp'
    if args.old_main: main_source = ROOT / 'logs/reboot-quiescence-before/twrp.cpp'
    if args.old_background: background = ROOT / 'logs/reboot-quiescence-before/gui2/backend/twrp_background_backend.cpp'
    s = main_source.read_text()
    tail = s[s.index('\tconst bool fastboot = startup.GetFastbootMode();'):]
    names = ['backup', 'restore', 'install', 'sideload', 'tools', 'decrypt', 'wipe']
    sources = [main_source, background, Path(__file__), ROOT / 'tests/nested_partition_path_test.py']
    destructors = []
    for name in names:
        path = SRC / f'gui2/backend/twrp_{name}_backend.cpp'
        sources.append(path)
        destructors.append(method(path.read_text(), f'twrp_{name}_backend::~twrp_{name}_backend()'))
    bg_methods = '\n'.join(method(background.read_text(), sig) for sig in [
        'twrp_background_backend::~twrp_background_backend()',
        'void twrp_background_backend::stop()'])
    prelude = r'''
#include <atomic>
#include <cassert>
#include <condition_variable>
#include <cstdio>
#include <mutex>
#include <string>
#include <thread>
#include <chrono>
#include "twrp_operation_executor.h"
static std::mutex gate;
static std::condition_variable cv;
static bool released=false, with_uevent=true;
static int gui_result=0, reboots=0, intents=0;
static std::atomic<int> finished=0, destroyed=0;
static void work(){
 {std::unique_lock l(gate);cv.wait(l,[]{return released;});}
 twrp_operation_executor::guard storage(twrp_operation_executor::instance().mutex());
 ++finished;
}
struct CheckJoined {~CheckJoined(){++destroyed;}};
struct Generic {template<class... T> Generic(T&&...){} void stop(){} bool ShouldSkipDecryption(){return false;}};
struct Startup {bool GetFastbootMode(){return false;} bool ShouldSkipDecryption(){return false;} std::string GetIntent(){return {};}} startup;
struct DM {static std::string GetStrValue(const char*){return {};}};
using DataManager=DM;
struct Manager {void CancelBackup(){}} PartitionManager;
namespace TWFunc {int SetBrightness(std::string){return 0;} void UpdateIntentFile(std::string){assert(destroyed==7);assert(finished==8);++intents;}}
namespace twrpminui {void release_force_feedback(){}}
int haptics_available(){return 1;} int vibrate(int){return 0;}
void startBatteryMonitor(){}
#define LOGERR(...) ((void)0)
static void Reboot(){assert(destroyed==7);assert(finished==8);assert(intents==1);++reboots;}
using twrp_startup_backend=Generic;
namespace gui2_backend {
static std::thread command_thread;
class twrp_background_backend {
 public:
 twrp_background_backend(){command_thread=std::thread(work);if(with_uevent)uevent_thread_=std::thread([this]{while(!uevent_stop_.load())std::this_thread::yield();});}
 ~twrp_background_backend(); void stop();
 private: std::thread uevent_thread_;std::atomic<bool> uevent_stop_{false};
};
// CLASSES
// DESTRUCTORS
// BG
}
struct gui2_context {
// FIELDS
bool fastboot_mode=false;
};
int gui2_start(gui2_context* c){
 // Pending workers do not own the storage lock when GUI exit is accepted.
 {std::lock_guard l(gate);released=true;}cv.notify_all();
 c->background->stop();
 assert(!gui2_backend::command_thread.joinable());
 c->background->stop(); // Idempotent and works even without a hotplug thread.
 return gui_result;
}
int execute(){
// TAIL
int main(int argc,char**argv){
 assert(argc==3);with_uevent=std::string(argv[1])=="hotplug";gui_result=std::stoi(argv[2]);
 int result=execute();assert(result==(gui_result? -1:0));
 assert(destroyed==7&&finished==8);assert(reboots==(gui_result?0:1));
 std::puts("joined_all_workers_before_intent_and_reboot=1 cli_stop_idempotent=1");
}
'''
    classes = []
    for name in names:
        extra = ('std::thread cancel_worker_;' if name == 'backup' else '')
        # CheckJoined is destroyed after the original destructor body has joined.
        classes.append(f'''class twrp_{name}_backend {{
 CheckJoined check_; public:
 template<class... T> twrp_{name}_backend(T&&...):worker_([]{{work();}}){{}}
 ~twrp_{name}_backend();void cancel(){{}}
 private:std::atomic<bool> running_{{false}};std::thread worker_;{extra}
 }};''')
    types = set(re.findall(r'gui2_backend::(\w+)\s+\w+[;(]', tail))
    for name in sorted(types - {f'twrp_{n}_backend' for n in names} - {'twrp_background_backend'}):
        classes.append(f'using {name}=Generic;')
    fields = []
    for field, var in re.findall(r'gui2_context_value\.(\w+) = &(\w+);', tail):
        cls = 'twrp_background_backend' if field == 'background' else None
        fields.append(f'gui2_backend::{cls}* {field}=nullptr;' if cls else f'void* {field}=nullptr;')
    code = prelude.replace('// CLASSES', '\n'.join(classes)).replace('// DESTRUCTORS', '\n'.join(destructors)).replace('// BG', bg_methods).replace('// FIELDS', '\n'.join(fields)).replace('// TAIL', tail)
    cases = []
    with tempfile.TemporaryDirectory(prefix='reboot-quiescence-') as temp:
        p = Path(temp);(p/'test.cpp').write_text(code)
        cmd = ['g++', '-std=c++23', '-pthread', '-O1', '-g', '-fsanitize=address,undefined', '-I'+str(SRC), str(p/'test.cpp'), str(SRC/'twrp_operation_executor.cpp'), '-o', str(p/'test')]
        subprocess.run(cmd, check=True)
        for bg in ['hotplug', 'no-hotplug']:
            for result in [0, 1]:
                r = subprocess.run([str(p/'test'), bg, str(result)], capture_output=True, text=True, timeout=10)
                cases.append(dict(case=f'{bg}-gui-{result}', status='PASS' if r.returncode==0 else 'FAIL', returncode=r.returncode, output=r.stdout+r.stderr))
                print(cases[-1]['case'], cases[-1]['status'], flush=True)
    sources.extend([SRC/'twrp_operation_executor.h', SRC/'twrp_operation_executor.cpp'])
    report = dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL', scope=__doc__, cases=cases, sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    return report['status']!='PASS'

if __name__=='__main__':
    raise SystemExit(main())
