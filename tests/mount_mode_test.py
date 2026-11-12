#!/usr/bin/env python3
"""Execute production mount-mode transaction; partition/storage services are doubles."""
import argparse,hashlib,json,subprocess,tempfile
from pathlib import Path
from backup_session_test import method
ROOT=Path(__file__).resolve().parents[1]
SRC=Path('/root/AAA/twrp/bootable/recovery/gui2/backend/twrp_mount_backend.cpp')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
CASES=['success-rw','success-ro','unmounted','vendor-absent','system-absent','system-unmount','vendor-unmount','system-remount','vendor-remount','rollback-remount','invalid','repeat','mixed-modes','vendor-only-mounted','rollback-unmount']
HARNESS=r'''
#include <cassert>
#include <cstdio>
#include <map>
#include <mutex>
#include <string>
#include <vector>
#include "twrp_operation_executor.h"
#define LOGERR(...) fprintf(stderr,__VA_ARGS__)
struct TWPartition {
 std::string name;bool mounted=true,ro=true;
 int mount_calls=0,unmount_calls=0;int fail_mount=0,fail_unmount_at=0;bool fail_unmount=false;
 bool IsMounted(){return mounted;}
 bool IsReadOnly(){return ro;}
 void ChangeMountReadOnly(bool value){ro=value;}
 bool Mount(bool){++mount_calls;if(mount_calls==fail_mount)return false;mounted=true;return true;}
 bool Unmount(bool){++unmount_calls;if(fail_unmount||unmount_calls==fail_unmount_at)return false;mounted=false;return true;}
};
TWPartition system_part{"system"},vendor_part{"vendor"};
struct PM {
 bool system_exists=true,vendor_exists=true;int refresh=0;
 std::string GetAndroidRootPath(){return "/system_root";}
 TWPartition* FindPartitionByPath(const std::string& p){if(p=="/system_root")return system_exists?&system_part:nullptr;assert(p=="/vendor");return vendor_exists?&vendor_part:nullptr;}
 int IsMountedByPath(const std::string&p){auto*x=FindPartitionByPath(p);return x&&x->IsMounted();}
 bool UnmountByPath(const std::string&p,bool v){auto*x=FindPartitionByPath(p);return x&&x->Unmount(v);}
 void RefreshPartitionListSnapshots(){++refresh;}
}PartitionManager;
struct DataManager {static inline int value=1,writes=0;static int SetValue(const std::string&k,int v){assert(k=="tw_mount_system_ro");value=v;++writes;return 0;}};
namespace android::base {
 template<class F>struct Guard{F f;~Guard(){f();}};
 template<class F>Guard<F> make_scope_guard(F f){return {f};}
}
int starts=0,ends=0,last=-1;
void operation_start(const char*){++starts;}void operation_end(int status){++ends;last=status;}
// METHOD
int main(int argc,char**argv){
 assert(argc==2);std::string test=argv[1];bool success=test=="success-rw"||test=="success-ro"||test=="unmounted"||test=="vendor-absent"||test=="repeat"||test=="mixed-modes"||test=="vendor-only-mounted";
 if(test=="success-ro"){system_part.ro=vendor_part.ro=false;DataManager::value=0;}
 if(test=="mixed-modes")vendor_part.ro=false;
 if(test=="vendor-only-mounted")system_part.mounted=false;
 if(test=="rollback-unmount"){vendor_part.fail_mount=1;system_part.fail_unmount_at=2;}
 if(test=="unmounted")system_part.mounted=vendor_part.mounted=false;
 if(test=="vendor-absent")PartitionManager.vendor_exists=false;
 if(test=="system-absent")PartitionManager.system_exists=false;
 if(test=="system-unmount")system_part.fail_unmount=true;
 if(test=="vendor-unmount")vendor_part.fail_unmount=true;
 if(test=="system-remount")system_part.fail_mount=1;
 if(test=="vendor-remount")vendor_part.fail_mount=1;
 if(test=="rollback-remount"){vendor_part.fail_mount=1;system_part.fail_mount=2;}
 const bool old_system_ro=system_part.ro,old_vendor_ro=vendor_part.ro;
 const int old_value=DataManager::value;
 int rc=mountsystemtoggle(test=="invalid"?"bad":test=="success-ro"?"1":"0");
 assert((rc==0)==success&&starts==1&&ends==1&&last==rc);
 if(success){
  const bool ro=test=="success-ro";assert(system_part.ro==ro&&DataManager::value==int(ro));
  if(PartitionManager.vendor_exists)assert(vendor_part.ro==ro);
  assert(system_part.mounted==(test!="unmounted"&&test!="vendor-only-mounted"));
  if(test=="vendor-only-mounted")assert(vendor_part.unmount_calls==1&&vendor_part.mount_calls==1&&vendor_part.mounted);
  if(test=="repeat"){assert(mountsystemtoggle(ro?"1":"0")==0);assert(DataManager::value==int(ro));}
 }else{
  assert(system_part.ro==(test=="rollback-unmount"?false:old_system_ro)&&vendor_part.ro==old_vendor_ro);
  assert(DataManager::value==old_value&&DataManager::writes==0);
  if(test!="rollback-remount")assert(system_part.mounted&&vendor_part.mounted);
  else assert(!system_part.mounted&&vendor_part.mounted);
 }
 if(test=="unmounted")assert(!system_part.mount_calls&&!vendor_part.mount_calls);
 if(test=="system-absent"||test=="invalid")assert(!system_part.unmount_calls&&!vendor_part.unmount_calls);
 puts("PASS");
}
'''
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,default=SRC);ap.add_argument('--report',type=Path,default=ROOT/'logs/mount-mode.json');a=ap.parse_args()
 cases=[]
 with tempfile.TemporaryDirectory(prefix='dijun-mount-mode-') as temp:
  temp=Path(temp);p=temp/'test.cpp';p.write_text(HARNESS.replace('// METHOD',method(a.source.read_text(),'int mountsystemtoggle(')))
  subprocess.run(['g++','-std=c++17','-O1','-g','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-I/root/AAA/twrp/bootable/recovery',str(p),'/root/AAA/twrp/bootable/recovery/twrp_operation_executor.cpp','-o',str(temp/'test')],check=True)
  for case in CASES:
   r=subprocess.run([str(temp/'test'),case],capture_output=True,text=True,timeout=10);cases.append(dict(case=case,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr));print(case,'PASS' if r.returncode==0 else 'FAIL',flush=True)
 r=dict(status='PASS' if all(c['returncode']==0 for c in cases) else 'FAIL',scope=__doc__,cases=cases,sources={str(p):sha(p) for p in [a.source,Path(__file__).resolve(),ROOT/'tests/backup_session_test.py',Path('/root/AAA/twrp/bootable/recovery/twrp_operation_executor.cpp'),Path('/root/AAA/twrp/bootable/recovery/twrp_operation_executor.h')]})
 a.report.write_text(json.dumps(r,indent=2)+'\n');raise SystemExit(r['status']!='PASS')
if __name__=='__main__':main()
