#!/usr/bin/env python3
"""Execute real Repair with private command/mount doubles and real shell exits.

Filesystem/partition access is substituted. The generated repair command is
recorded, never executed; private shell exit/signals supply POSIX wait status.
Separate filesystem_tools_image_test executes the actual ARM64 repair tool.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from nested_partition_path_test import method, ROOT, SRC

HARNESS = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <sys/wait.h>
#include <signal.h>
#define LOGINFO(...) ((void)0)
unsigned checks=0,failures=0,execs=0,done=0,errors=0;
int exit_code=0;bool killed=false,missing=false,spawn_error=false;
std::string last_command;
#define CHECK(x) do{++checks;if(!(x)){++failures;printf("FAIL %d: %s\n",__LINE__,#x);}}while(0)
namespace gui2_console {
template<class... A> void info(const char* key,A...){if(std::string(key)=="done")++done;}
template<class... A> void log_error(A...){++errors;}
}
namespace TWFunc {
bool IsPathExists(const std::string&){return !missing;}
int status(const std::string& cmd){
 ++execs;last_command=cmd;if(spawn_error)return -1;
 // No generated repair command reaches a shell or filesystem.
 return std::system(killed?"kill -TERM $$":("exit "+std::to_string(exit_code)).c_str());
}
int ExecCmd(const std::string& cmd,bool=true){return status(cmd)==0?0:-1;}
int ExecCmd(const std::string& cmd,std::string& out,bool){out="fixture checker output\n";return status(cmd);}
}
struct TWPartition{
 std::string current_file_system_="ext4",display_name_="private",actual_block_device_="/fixture/never-open";
 bool unmount_ok=true;
 bool Unmount(bool){return unmount_ok;}
 void FindActualBlockDevice(){}
 bool Repair();
};
// METHOD
int main(){
 TWPartition p;
 for(const auto& fs:{"ext2","ext3","ext4"}){
  p.current_file_system_=fs;
  for(int code:{0,1,2,3,4,8,16,32,128,255}){
   exit_code=code;auto before_done=done,before_errors=errors;
   bool result=p.Repair();CHECK(result==(code==0||code==1));
   CHECK(done-before_done==(result?1u:0u));CHECK(errors-before_errors==(result?0u:1u));
   CHECK(last_command=="/system/bin/e2fsck -fp /fixture/never-open");
  }
 }
 for(const auto& fs:{"vfat","exfat","f2fs","mifs","ntfs","tntfs"}){
  p.current_file_system_=fs;
  for(int code:{0,1,4}){exit_code=code;CHECK(p.Repair()==(code==0));}
 }
 p.current_file_system_="ext4";killed=true;CHECK(!p.Repair());killed=false;
 spawn_error=true;CHECK(!p.Repair());spawn_error=false;
 missing=true;auto before=execs;CHECK(!p.Repair());CHECK(execs==before);missing=false;
 p.unmount_ok=false;CHECK(!p.Repair());CHECK(execs==before);p.unmount_ok=true;
 p.current_file_system_="erofs";CHECK(!p.Repair());CHECK(execs==before);
 printf("assertions=%u failures=%u\n",checks,failures);return failures?1:0;
}
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, default=SRC/'partition.cpp')
    ap.add_argument('--report', type=Path, default=ROOT/'logs/repair-exit-status.json')
    args = ap.parse_args()
    code = HARNESS.replace('// METHOD', method(args.source.read_text(), 'bool TWPartition::Repair()'))
    with tempfile.TemporaryDirectory(prefix='dijun-repair-result-') as temp:
        p = Path(temp)
        (p/'test.cpp').write_text(code)
        subprocess.run(['g++', '-std=c++23', '-fsanitize=undefined', '-fno-sanitize-recover=all',
                        str(p/'test.cpp'), '-o', str(p/'test')], check=True)
        result = subprocess.run([str(p/'test')], capture_output=True, text=True, timeout=15)
    paths = [args.source, Path(__file__), ROOT/'tests/nested_partition_path_test.py']
    report = dict(status='PASS' if result.returncode == 0 else 'FAIL', scope=__doc__,
                  returncode=result.returncode, output=result.stdout+result.stderr,
                  sources={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    print(report['output'])
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
