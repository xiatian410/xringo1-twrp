#!/usr/bin/env python3
"""Original Unmount -> Repair/Resize -> manager -> backend result, no mount/device.

The retain-System setting executes its real early-return branch. Mount status,
mount syscalls, MTP, device discovery, size and checker execution are explicit
fixtures. Commands are recorded and never run; no phone or physical I/O.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from nested_partition_path_test import ROOT, SRC, method

HARNESS = r'''
#include <cassert>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <filesystem>
#include <mutex>
#include <string>
#include <vector>
#include <sys/mount.h>
#include <sys/wait.h>
#define LOGINFO(...) ((void)0)
#define LOGERR(...) ((void)0)
#define TW_DONT_UNMOUNT_SYSTEM "keep-system"
static bool mounted=true,unmount_ok=true;
static int keep=0,execs=0,unmounts=0,done=0,ended=-1,starts=0,ends=0,updates=0;
static std::vector<std::string> commands;
namespace gui2_console {
 template<class... A> void info(const char*k,A...){if(std::string(k)=="done")++done;}
 template<class... A> void log_error(A...){}
}
namespace twrp_operation_executor {
 struct executor{std::recursive_mutex m;auto& mutex(){return m;}};
 executor& instance(){static executor e;return e;}
 using guard=std::lock_guard<std::recursive_mutex>;
}
struct DataManager {static void GetValue(const char*,int&v){v=keep;}};
namespace TWFunc {
 bool IsPathExists(const std::string&){return true;}
 std::string GetRootPath(const std::string&p){return p;}
 void KillForUseTargetProcess(const std::string&){}
 int ExecCmd(const std::string&s){++execs;commands.push_back(s);return 0;}
 int ExecCmd(const std::string&s,std::string&out,bool){out="";return ExecCmd(s);}
}
struct TWPartition {
 enum class DeState{READY,NEEDS_RESTORE};DeState de_state_=DeState::READY;
 std::string mount_point_="/system_root",symlink_mount_point_,sub_partition_of_,current_file_system_="ext4",display_name_="fixture",actual_block_device_="/fixture/never-open";
 bool is_sub_partition_=false,mount_read_only_=false,is_storage_=false,is_fbe_=false;
 unsigned mtp_storage_id_=0;int length_=0;
 bool IsMounted()const{return mounted;}
 bool IsPathMounted(const std::string&)const{return false;}
 bool EnsureSubdirectoryUnmounted(const char*)const{return true;}
 bool BindMount()const{assert(false);return false;}
 void StopDataSizeScan()const{}
 void FindActualBlockDevice(){}
 uint64_t IoctlGetBlockSize(){return 64ULL<<20;}
 bool UpdateSize(bool){++updates;return true;}
 std::string GetMountPoint()const{return mount_point_;}
 bool Unmount(bool,int=0)const;bool CanRepair()const;bool Repair();bool Resize();
};
int umount2(const char*,int){++unmounts;if(unmount_ok){mounted=false;return 0;}errno=EPERM;return -1;}
struct TWPartitionManager {
 std::vector<TWPartition*>partitions_;
 static std::string GetAndroidRootPath(){return "/system_root";}
 static void RemoveMtpStorage(unsigned){assert(false);}
 static void AddMtpStorage(unsigned){assert(false);}
 void MarkDataLocked(){assert(false);}
 static bool MatchesPath(const TWPartition*,const std::string&);
 TWPartition*FindPartitionByPath(const std::string&)const;
 int RepairByPath(const std::string&,bool)const;int ResizeByPath(const std::string&,bool)const;
} PartitionManager;
void operation_start(const char*){++starts;}
void operation_end(int s){ended=s;++ends;}
bool partition_tool_target_allowed(const std::string&){return true;}
// METHODS
int main(int argc,char**argv){
 assert(argc==2);std::string name=argv[1];TWPartition p;
 bool resize_job=name.starts_with("resize");bool expected=true;
 if(name.ends_with("kept")){keep=1;expected=false;}
 if(name.ends_with("denied")){unmount_ok=false;expected=false;}
 if(name.ends_with("unmounted"))mounted=false;
 if(name.ends_with("f2fs"))p.current_file_system_="f2fs";
 const bool initially_mounted=mounted;
 PartitionManager.partitions_={&p};
 const int result=resize_job?resize(p.mount_point_):repair(p.mount_point_);
 assert(result==(expected?0:1)&&ended==result&&starts==1&&ends==1);
 assert(execs==(expected?(resize_job?2:1):0));
 assert(done==(expected?(resize_job?2:1):0));
 assert(updates==(expected&&resize_job?1:0));
 if(name.ends_with("kept")){assert(unmounts==0&&mounted);}
 else if(name.ends_with("denied")){assert(unmounts==1&&mounted);}
 else {assert(!mounted&&unmounts==(initially_mounted?1:0));}
 for(const auto&cmd:commands)assert(cmd.find("/fixture/never-open")!=std::string::npos);
 printf("PASS %s result=%d execs=%d unmounts=%d mounted=%d\n",argv[1],result,execs,unmounts,mounted);
}
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, default=SRC/'partition.cpp')
    ap.add_argument('--report', type=Path, default=ROOT/'logs/repair-mounted-current.json')
    args = ap.parse_args()
    selected = {
        args.source: ['bool TWPartition::Unmount(', 'bool TWPartition::CanRepair()',
                      'bool TWPartition::Repair()', 'bool TWPartition::Resize()'],
        SRC/'partitionmanager.cpp': ['bool TWPartitionManager::MatchesPath(',
            'TWPartition* TWPartitionManager::FindPartitionByPath(',
            'int TWPartitionManager::RepairByPath(', 'int TWPartitionManager::ResizeByPath('],
        SRC/'gui2/backend/twrp_tools_backend.cpp': ['int repair(', 'int resize('],
    }
    methods = '\n\n'.join(method(p.read_text(), sig) for p, sigs in selected.items() for sig in sigs)
    names = ['repair-kept', 'resize-kept', 'repair-mounted', 'resize-mounted',
             'repair-unmounted', 'resize-unmounted', 'repair-denied', 'resize-denied', 'repair-f2fs']
    cases = []
    with tempfile.TemporaryDirectory(prefix='repair-mounted-') as temp:
        work = Path(temp)
        (work/'test.cpp').write_text(HARNESS.replace('// METHODS', methods))
        cmd = ['g++', '-std=c++23', '-O1', '-g', '-pthread', '-fsanitize=address,undefined',
               '-fno-sanitize-recover=all', '-fno-pie', '-no-pie', str(work/'test.cpp'), '-o', str(work/'test')]
        subprocess.run(cmd, check=True)
        for name in names:
            run = subprocess.run([str(work/'test'), name], capture_output=True, text=True, timeout=5)
            cases.append(dict(case=name, status='PASS' if run.returncode==0 else 'FAIL',
                              returncode=run.returncode, output=run.stdout+run.stderr))
            print(name, cases[-1]['status'], flush=True)
    paths = [*selected, Path(__file__).resolve(), ROOT/'tests/nested_partition_path_test.py']
    report = dict(status='PASS' if all(c['returncode']==0 for c in cases) else 'FAIL',
                  scope=__doc__, cases=cases,
                  sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    return report['status'] != 'PASS'


if __name__ == '__main__':
    raise SystemExit(main())
