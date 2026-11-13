#!/usr/bin/env python3
"""Run production synchronous and asynchronous size consumers with real exclusion walks.

Statfs/mount/df/commands/DataManager are explicit fixtures. Original worker,
generation/pending result and ApplyAsyncDataSize execute with real host threads;
real ordinary-file directory walks get named I/O faults. No device/GUI/DRM.
"""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from backup_session_test import ROOT, SRC, method
from exclusion_errors_test import MAIN
from otg_selection_test import HARNESS

CASES=['async-normal', 'async-root-open', 'async-nested-open', 'async-stat',
       'async-read', 'async-close', 'sync-normal', 'sync-root-open',
       'sync-nested-open', 'sync-stat', 'sync-read', 'sync-close',
       'secure-normal', 'secure-read']
PREFIX=r'''
#include <atomic>
#include <condition_variable>
#include <memory>
#include <thread>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include "exclude.hpp"
#include "twrp_functions.hpp"
using namespace std;
#define TW_BACKUP_DATA_SIZE "backup-size"
template<class T>T ParseOrZero(const std::string&){return 0;}
namespace TWFunc {
 bool IsPathExists(const std::string&){return true;}
 int ExecCmd(const std::string&,std::string&,bool){return -1;}
}
struct UnitConversion {static std::string FormatBytes(uint64_t){return "fixture";}};
struct DataManager {static inline int writes=0;static void SetValue(const char*,uint64_t){++writes;}};
'''
MAIN_TEST=r'''
int main(int argc,char**argv){
 string name=argv[1];bool async=name.starts_with("async-");bool secure=name.starts_with("secure-");
 fault=name.substr(name.find('-')+1);base=argv[2];fs::create_directories(base+"/sub");
 std::ofstream(base+"/keep")<<"1234567";std::ofstream(base+"/sub/file")<<"1234567890123";
 TWPartition p;p.mount_point_=p.backup_path_=base;p.has_data_media_=!secure;p.has_android_secure_=secure;
 bool good=fault=="normal";
 if(async){
  p.mounted=true;p.backup_size_provisional_=true;p.UpdateDataSizeAsync();
  auto& state=GetAsyncSizeState();{
   unique_lock lock(state.lock);
   if(!state.finished.wait_for(lock,chrono::seconds(2),[&]{return state.active_workers==0;}))return 8;
  }
  p.ApplyAsyncDataSize();
  if(good){if(p.backup_size_provisional_||p.backup_size_!=20||DataManager::writes!=1)return 1;}
  else if(!p.backup_size_provisional_||p.backup_size_!=333||DataManager::writes!=0)return 2;
 }else{
  bool rc=p.UpdateSize(false,false,true);
  if(rc!=good||p.mounted||p.mount_read_only_)return 3;
  if(good&&p.backup_size_!=20)return 4;
  if(!good&&(p.backup_size_!=333||(!secure&&!p.backup_size_provisional_)))return 5;
 }
 if(!good&&!fired)return 6;
 if(!dirs.empty())return 7;
 puts("consumer_error_propagated=1 partial_not_final=1 lifecycle_closed=1");
}
'''

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,default=SRC);ap.add_argument('--report',type=Path,default=ROOT/'logs/data-size-errors.json');a=ap.parse_args();rows=[]
 with tempfile.TemporaryDirectory(prefix='data-size-errors-') as tmp:
  w=Path(tmp)
  for n in ['exclude.cpp','exclude.hpp']:(w/n).write_bytes((a.source/n).read_bytes())
  for n,t in {'libtar/libtar.h':'','twcommon.h':'#define LOGINFO(...) ((void)0)\n','gui2/console/stdio_adapter.h':'namespace gui2_console {template<class... T>void log_error(T...) {}}\n',
     'twrp_functions.hpp':'#pragma once\n#include <cstring>\n#include <string>\n#include <filesystem>\n#include <dirent.h>\n#include <sys/stat.h>\nnamespace TWFunc {std::string RemoveTrailingSlashes(const std::string&,bool=false);}\n'}.items():
   p=w/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t)
  decl=HARNESS[HARNESS.index('struct TWPartition {'):HARNESS.index('}part;')+1]
  decl=decl.replace('unsigned long long size_=4096,free_=2048,used_=2048,backup_size_=0;','unsigned long long size_=4096,free_=2048,used_=2048,backup_size_=333;')
  decl=decl.replace(' void InvalidateDataSizeScan(){}','').replace(' bool UpdateSize(', ' TWExclude backup_exclusions;\n std::string decrypted_block_device_;\n ~TWPartition();\n void UpdateDataSizeAsync();void ApplyAsyncDataSize();static void StopDataSizeScan();\n bool UpdateSize(')
  source=(a.source/'partition.cpp').read_text()
  code=source[source.index('struct AsyncSizeState {'):source.index('bool TWPartition::FindWildcardBlockDevices(')]
  wrappers=MAIN[MAIN.index('namespace fs='):MAIN.index('// HELPER')]
  helper=method((SRC/'twrp_functions.cpp').read_text(),'std::string TWFunc::RemoveTrailingSlashes(')
  guard=HARNESS[HARNESS.index('#define LOGERR'):HARNESS.index('namespace TWFunc')]
  (w/'test.cpp').write_text(PREFIX+guard+';\n'+decl+';\n'+wrappers+helper+'\n'+code+'\n'+MAIN_TEST)
  cmd=['g++','-std=c++23','-O1','-g','-pthread','-no-pie','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(w),'-I'+str(SRC),str(w/'exclude.cpp'),str(w/'test.cpp'),str(SRC/'twrp_operation_executor.cpp'),'-include',str(SRC/'twrp_operation_executor.h'),'-o',str(w/'test'),*['-Wl,--wrap='+f for f in ['opendir','readdir','closedir','lstat']]]
  subprocess.run(cmd,check=True)
  for name in CASES:
   r=subprocess.run([str(w/'test'),name,str(w/name)],capture_output=True,text=True,timeout=5);rows.append(dict(case=name,status='PASS' if r.returncode==0 else 'FAIL',returncode=r.returncode,output=r.stdout+r.stderr));print(name,rows[-1]['status'],flush=True)
 paths=[a.source/n for n in ['exclude.cpp','exclude.hpp','partition.cpp']]+[SRC/n for n in ['twrp_functions.cpp','twrp_operation_executor.cpp','twrp_operation_executor.h']]+[Path(__file__).resolve(),ROOT/'tests/exclusion_errors_test.py',ROOT/'tests/otg_selection_test.py',ROOT/'tests/backup_session_test.py']
 result=dict(status='PASS' if all(c['status']=='PASS' for c in rows) else 'FAIL',scope=__doc__,cases=rows,sources={str(p):sha(p) for p in paths},compile_command=cmd);a.report.write_text(json.dumps(result,indent=2)+'\n');return result['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
