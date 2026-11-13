#!/usr/bin/env python3
"""Run production storage selection plus real UpdateSize with storage/I/O doubles.

No host or phone mount/block I/O. Real recursive transaction lock and scope
lifetimes execute; statfs/df/media sizes, presence changes and settings are
explicit fixtures. Tests selection failure semantics, not USB host discovery.
"""
import argparse,hashlib,json,subprocess,tempfile
from pathlib import Path
from backup_session_test import method
ROOT=Path(__file__).resolve().parents[1];REC=Path('/root/AAA/twrp/bootable/recovery')
CASES=['new','mounted','mount-fail','size-fail','mounted-size-fail','removed-before','removed-after-mount','missing','non-storage','subpath','full','df-fallback','rollback-unmount-fail','internal','set-fail']
HARNESS=r'''
#include <cassert>
#include <cstdio>
#include <string>
#include <mutex>
#include <utility>
#include "twrp_operation_executor.h"
#define LOGERR(...) fprintf(stderr,__VA_ARGS__)
#define LOGINFO(...) ((void)0)
namespace android::base {template<class F>struct Guard{F f;bool active=true;~Guard(){if(active)f();}void Disable(){active=false;}};template<class F>Guard<F> make_scope_guard(F f){return {f};}}
namespace TWFunc {bool IsPathExists(const std::string&){return true;}}
struct UnitConversion {static std::string FormatBytes(unsigned long long){return "fixture";}};
struct Exclusions {unsigned long long Get_Folder_Size(const std::string&,bool=true,const void* =nullptr,bool* complete=nullptr){if(complete)*complete=true;return 0;}} backup_exclusions;
struct TWPartition {
 std::string mount_point_="/storage/usbotg-1-1",storage_path_="/storage/usbotg-1-1",actual_block_device_="/fixture",backup_path_="/fixture";
 bool removable_=true,is_storage_=true,is_present_=true,mounted=false,mount_read_only_=false,can_be_mounted_=true,is_encrypted_=false,has_data_media_=false,has_android_secure_=false,backup_size_provisional_=false;
 bool mount_ok=true,size_ok=true,df_ok=false,remove_on_mount=false,remove_on_find=false,unmount_ok=true;int mount_calls=0,unmount_calls=0,finds=0,stat_calls=0;
 unsigned long long size_=4096,free_=2048,used_=2048,backup_size_=0;
 bool IsMounted()const{return mounted;}
 bool Mount(bool){++mount_calls;if(!mount_ok)return false;mounted=true;if(remove_on_mount){mount_ok=false;remove_on_find=true;}return true;}
 bool Unmount(bool){++unmount_calls;if(!unmount_ok)return false;mounted=false;return true;}
 void FindActualBlockDevice(){++finds;if(remove_on_find){actual_block_device_.clear();is_present_=false;}}
 bool FindPartitionSize(){return size_ok;}
 bool GetSizeViaStatfs(bool){++stat_calls;return size_ok;}
 bool GetSizeViaDf(bool){return df_ok;}
 void InvalidateDataSizeScan(){}
 bool UpdateSize(bool,bool=false,bool=true);
}part;
struct PM {
 bool exists=true;int refresh=0;
 TWPartition* FindPartitionByPath(const std::string&){return exists?&part:nullptr;}
 void RefreshPartitionListSnapshots(){++refresh;}
}PartitionManager;
struct DataManager {
 static inline std::string storage="/sdcard";static inline int sets=0;static inline bool works=true;
 static int SetValue(const std::string&key,const std::string&value){assert(key=="tw_storage_path");++sets;if(!works)return -1;storage=value;return 0;}
};
struct twrp_mount_backend {bool select_storage(const std::string&);};
// METHODS
int main(int argc,char**argv){
 assert(argc==2);std::string test=argv[1],path=part.storage_path_;bool good=test=="new"||test=="mounted"||test=="full"||test=="df-fallback"||test=="internal";
 if(test=="mounted"||test=="mounted-size-fail")part.mounted=true;
 if(test=="mount-fail")part.mount_ok=false;
 if(test=="size-fail"||test=="mounted-size-fail"||test=="rollback-unmount-fail")part.size_ok=false;
 if(test=="removed-before")part.is_present_=false;
 if(test=="removed-after-mount")part.remove_on_mount=true;
 if(test=="missing")PartitionManager.exists=false;
 if(test=="non-storage")part.is_storage_=false;
 if(test=="subpath")path+="/folder";
 if(test=="full")part.free_=0;
 if(test=="df-fallback"){part.size_ok=false;part.df_ok=true;}
 if(test=="rollback-unmount-fail")part.unmount_ok=false;
 if(test=="internal"){part.removable_=false;part.storage_path_=part.mount_point_="/sdcard";path="/sdcard";}
 if(test=="set-fail")DataManager::works=false;
 const bool original_mounted=part.mounted;
 twrp_mount_backend backend;bool rc=backend.select_storage(path);
 assert(rc==good&&PartitionManager.refresh==1);
 assert(!part.mount_read_only_);
 if(good){assert(part.mounted&&DataManager::sets==1&&DataManager::storage==path);if(part.removable_)assert(part.stat_calls==1&&part.mount_calls==1);}
 else{
  assert(DataManager::storage=="/sdcard");
  if(test!="set-fail")assert(DataManager::sets==0);
  if(test=="rollback-unmount-fail")assert(part.mounted&&part.unmount_calls==1);
  else assert(part.mounted==original_mounted);
 }
 if(test=="removed-before"||test=="missing"||test=="non-storage"||test=="subpath")assert(part.mount_calls==0);
 puts("PASS");
}
'''
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--backend',type=Path,default=REC/'gui2/backend/twrp_mount_backend.cpp');ap.add_argument('--report',type=Path,default=ROOT/'logs/otg-selection.json');a=ap.parse_args()
 sources=[a.backend,REC/'partition.cpp',REC/'partitions.hpp',REC/'twrp_operation_executor.cpp',REC/'twrp_operation_executor.h',Path(__file__).resolve(),ROOT/'tests/backup_session_test.py'];cases=[]
 code=method(a.backend.read_text(),'bool twrp_mount_backend::select_storage(')+'\n'+method((REC/'partition.cpp').read_text(),'bool TWPartition::UpdateSize(')
 with tempfile.TemporaryDirectory(prefix='dijun-otg-select-') as tmp:
  tmp=Path(tmp);(tmp/'test.cpp').write_text(HARNESS.replace('// METHODS',code))
  subprocess.run(['g++','-std=c++17','-O1','-g','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-I'+str(REC),str(tmp/'test.cpp'),str(REC/'twrp_operation_executor.cpp'),'-o',str(tmp/'test')],check=True)
  for case in CASES:
   p=subprocess.run([str(tmp/'test'),case],text=True,capture_output=True,timeout=10);cases.append(dict(case=case,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));print(case,'PASS' if p.returncode==0 else 'FAIL',flush=True)
 report=dict(status='PASS' if all(c['returncode']==0 for c in cases) else 'FAIL',scope=__doc__,cases=cases,sources={str(p):sha(p) for p in sources});a.report.write_text(json.dumps(report,indent=2)+'\n');raise SystemExit(report['status']!='PASS')
if __name__=='__main__':main()
