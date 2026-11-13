#!/usr/bin/env python3
"""Original reboot/slot backend with real storage transaction mutex and threads.

HAL/partition methods, sync, DataManager, capability flags and final reboot are
fixtures; no device, mount, slot, Binder/TEE call or physical reboot is performed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from nested_partition_path_test import ROOT, SRC, method


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    source = (ROOT / 'logs/reboot-storage-before/gui2/backend/twrp_reboot_backend.cpp'
              if args.before else SRC / 'gui2/backend/twrp_reboot_backend.cpp')
    bodies = '\n'.join(method(source.read_text(), sig) for sig in [
        'bool twrp_reboot_backend::set_active_slot(',
        'bool twrp_reboot_backend::is_supported(',
        'const char* twrp_reboot_backend::reboot_argument(',
        'bool twrp_reboot_backend::request_reboot('])
    code = r'''
#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <mutex>
#include <string>
#include <thread>
#include <cstdio>
#include <sys/mount.h>
#include "twrp_operation_executor.h"
#include "twrp_reboot_backend.h"
#define LOGINFO(...) ((void)0)
static int starts=0,ends=0,syncs=0,sets=0,unmounts=0;
static bool enabled=true,write_ok=true;
static std::string argument,slot_set;
struct DataManager { static int SetValue(const char* k,const char* v){assert(std::string(k)=="tw_reboot_arg");++sets;if(!write_ok)return -1;argument=v;return 0;} };
struct Manager {
bool FindPartitionByPath(const char*){return true;}
bool UnmountByPath(const char*,bool,int=0){++unmounts;return true;}
bool SetActiveSlot(const std::string& s){slot_set=s;return true;}
} PartitionManager;
namespace gui2_backend {
twrp_reboot_backend::twrp_reboot_backend()=default;
const reboot_capabilities& twrp_reboot_backend::capabilities()const {capabilities_={enabled,enabled,enabled,enabled,enabled,enabled,enabled,true};return capabilities_;}
std::string twrp_reboot_backend::active_slot()const{return {};}
bool twrp_reboot_backend::take_external_reboot(){return false;}
bool twrp_reboot_backend::usb_fastboot()const{return false;}
void twrp_reboot_backend::set_usb_fastboot(bool){}
bool twrp_reboot_backend::os_installed()const{return true;}
void operation_start(const char*){++starts;}
void operation_end(int){++ends;}
static void fixture_sync(){++syncs;}
#define sync fixture_sync
// METHODS
#undef sync
}
int main(int argc,char**argv){
 assert(argc==2);std::string name=argv[1];using namespace gui2_backend;
 twrp_reboot_backend backend;std::mutex gate;std::condition_variable cv;bool held=false,release=false;
 const bool busy=name.starts_with("busy-");
 std::thread owner;
 if(busy){
  owner=std::thread([&]{std::unique_lock storage(twrp_operation_executor::instance().mutex());std::unique_lock l(gate);held=true;cv.notify_all();cv.wait(l,[&]{return release;});});
  std::unique_lock l(gate);assert(cv.wait_for(l,std::chrono::seconds(2),[&]{return held;}));
 }
 if(name=="unsupported")enabled=false;
 if(name=="write-failed")write_ok=false;
 std::unique_lock<std::recursive_mutex> recursive;
 if(name=="recursive")recursive=std::unique_lock(twrp_operation_executor::instance().mutex());
 bool result=false;auto start=std::chrono::steady_clock::now();
 if(name.ends_with("slot-a")||name.ends_with("slot-b"))result=backend.set_active_slot(name.ends_with("slot-a")?boot_slot::A:boot_slot::B);
 else {
  reboot_target target=reboot_target::SYSTEM;
  if(name.ends_with("poweroff"))target=reboot_target::POWER_OFF;
  if(name.ends_with("recovery"))target=reboot_target::RECOVERY;
  if(name.ends_with("fastboot"))target=reboot_target::FASTBOOT;
  if(name.ends_with("bootloader"))target=reboot_target::BOOTLOADER;
  if(name.ends_with("download"))target=reboot_target::DOWNLOAD;
  if(name.ends_with("edl"))target=reboot_target::EDL;
  result=backend.request_reboot(target);
 }
 auto elapsed=std::chrono::steady_clock::now()-start;
 if(busy){
  // The owner is still holding the lock when the UI call returns.
  assert(!result&&starts==0&&ends==0&&syncs==0&&sets==0&&unmounts==0&&slot_set.empty());
  assert(elapsed<std::chrono::milliseconds(250));
  {std::lock_guard l(gate);release=true;}cv.notify_all();owner.join();
  assert(backend.request_reboot(reboot_target::SYSTEM)&&argument=="system");
 }else if(name=="unsupported")assert(!result&&syncs==0&&sets==0);
 else if(name=="write-failed")assert(!result&&syncs==1&&sets==1&&argument.empty());
 else if(name.starts_with("idle-slot"))assert(result&&starts==1&&ends==1&&unmounts==1&&syncs==0&&slot_set==(name.ends_with("a")?"A":"B"));
 else assert(result&&syncs==1&&sets==1&&!argument.empty());
 std::puts("checked_storage_gate_and_retry=1");
}
'''.replace('// METHODS', bodies)
    cases = []
    names = [state + '-' + target for state in ['busy', 'idle'] for target in [
        'system', 'poweroff', 'recovery', 'fastboot', 'bootloader', 'download', 'edl',
        'slot-a', 'slot-b']] + ['unsupported', 'write-failed', 'recursive']
    with tempfile.TemporaryDirectory(prefix='reboot-storage-') as temp:
        work = Path(temp)
        (work / 'test.cpp').write_text(code)
        binary = work / 'test'
        cmd = ['g++', '-std=c++23', '-O1', '-g', '-pthread', '-fsanitize=address,undefined',
               '-I' + str(SRC), '-I' + str(SRC / 'gui2/backend'), str(work / 'test.cpp'),
               str(SRC / 'twrp_operation_executor.cpp'), '-o', str(binary)]
        subprocess.run(cmd, check=True)
        for name in names:
            run = subprocess.run([str(binary), name], capture_output=True, text=True, timeout=5)
            cases.append(dict(name=name, status='PASS' if run.returncode == 0 else 'FAIL',
                              returncode=run.returncode, output=run.stdout + run.stderr))
            print(name, cases[-1]['status'], flush=True)
    paths = [source, Path(__file__), ROOT / 'tests/nested_partition_path_test.py',
             SRC / 'gui2/backend/twrp_reboot_backend.h', SRC / 'gui2/backend/reboot_backend.h',
             SRC / 'twrp_operation_executor.h', SRC / 'twrp_operation_executor.cpp']
    report = dict(status='PASS' if all(c['status'] == 'PASS' for c in cases) else 'FAIL',
                  scope=__doc__, cases=cases, compile_command=cmd,
                  sources={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    output = ROOT / ('logs/reboot-storage-negative.json' if args.before else 'logs/reboot-storage.json')
    (args.report or output).write_text(json.dumps(report, indent=2) + '\n')
    return report['status'] != 'PASS'


if __name__ == '__main__':
    raise SystemExit(main())
