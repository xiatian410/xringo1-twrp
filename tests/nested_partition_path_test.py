#!/usr/bin/env python3
"""Execute real partition lookup/mount methods and settings mount guard.

Only partition Mount/IsMounted, operation mutex and mkdir are fixtures. No
device, mount syscall, filesystem key or persist content is accessed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = Path('/root/AAA/twrp/bootable/recovery')


def method(text, signature):
    start = text.index(signature); opening = text.index('{', start)
    end = opening + 1; depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}'); end += 1
    return text[start:end]


HARNESS = r'''
#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <filesystem>
#include <mutex>
#include <string>
#include <vector>
#define LOGINFO(...) ((void)0)
#define LOGERR(...) ((void)0)
#define TW_PERSIST_DIR "/mnt/vendor/persist/TWRP"
static unsigned failures=0, assertions=0, mkdir_calls=0;
#define CHECK(x) do { ++assertions; if(!(x)){++failures;std::printf("FAIL line %d: %s\n",__LINE__,#x);} } while(0)
struct TWPartition {
 std::string mount_point_,symlink_mount_point_,sub_partition_of_;
 bool is_sub_partition_=false,mounted=false,can_mount=true;
 mutable unsigned mounts=0,unmounts=0;
 bool Mount(bool){++mounts;if(can_mount)mounted=true;return mounted;}
 bool Unmount(bool,int)const{++unmounts;const_cast<TWPartition*>(this)->mounted=false;return true;}
 bool IsMounted()const{return mounted;}
};
namespace twrp_operation_executor {
struct executor {std::recursive_mutex lock;std::recursive_mutex& mutex(){return lock;}};
executor& instance(){static executor e;return e;}
struct guard {std::lock_guard<std::recursive_mutex> lock;guard(std::recursive_mutex& m):lock(m){}};
}
namespace gui2_console {template<class... A> void log_error(A...) {}}
namespace TWFunc {std::string GetRootPath(const std::string&);}
class TWPartitionManager {
public:
 std::vector<TWPartition*> partitions_;
 static bool MatchesPath(const TWPartition*,const std::string&);
 TWPartition* FindPartitionByPath(const std::string&)const;
 int MountByPath(const std::string&,bool)const;
 bool UnmountByPath(const std::string&,bool,int=0)const;
 int IsMountedByPath(const std::string&)const;
 std::string GetAndroidRootPath()const{return "/system_root";}
} PartitionManager;
static int mkdir(const char* p,int){CHECK(std::string(p)==TW_PERSIST_DIR);++mkdir_calls;return 0;}
// METHODS
int main(){
 TWPartition persist{"/mnt/vendor/persist"}, vendor{"/vendor"},
   mnt{"/mnt"},system{"/system_root"},media{"/data","/sdcard"},
   protect{"/mnt/vendor/protect_f"},child{"/vendor/child"};
 child.is_sub_partition_=true;child.sub_partition_of_="/vendor";
 PartitionManager.partitions_={&mnt,&persist,&protect,&vendor,&system,&media,&child};
 CHECK(PartitionManager.FindPartitionByPath("/mnt/vendor/persist/TWRP/.twrp_settings")==&persist);
 CHECK(PartitionManager.FindPartitionByPath("/mnt/vendor/persist/")==&persist);
 CHECK(PartitionManager.FindPartitionByPath("mnt/vendor/persist/TWRP")==&persist);
 CHECK(PartitionManager.FindPartitionByPath("/mnt/vendor/persist-other")==&mnt);
 CHECK(PartitionManager.FindPartitionByPath("/mnt/vendor/persist/../protect_f/secret")==&protect);
 CHECK(PartitionManager.FindPartitionByPath("/sdcard/TWRP")==&media);
 CHECK(PartitionManager.FindPartitionByPath("/data/media/0")==&media);
 CHECK(PartitionManager.FindPartitionByPath("/system/bin/sh")==&system);
 CHECK(PartitionManager.FindPartitionByPath("/system_ext")==nullptr);
 CHECK(PartitionManager.FindPartitionByPath("/vendor/child/file")==&child);
 CHECK(PartitionManager.FindPartitionByPath("/unknown/path")==nullptr);
 // Settings use the actual guard with an existing mount, then an acquired one.
 persist.mounted=true;
 CHECK(twPersistMount(TW_PERSIST_DIR "/.twrp_settings"));
 CHECK(persist.mounts==0 && mkdir_calls==1 && mnt.mounts==0);
 persist.mounted=false;
 CHECK(twPersistMount(TW_PERSIST_DIR "/.twrp_settings"));
 CHECK(persist.mounts==1 && persist.mounted && mkdir_calls==2 && mnt.mounts==0);
 persist.mounted=false;persist.can_mount=false;
 CHECK(!twPersistMount(TW_PERSIST_DIR "/.twrp_settings"));
 CHECK(mkdir_calls==2 && !persist.mounted);
 CHECK(twPersistMount("/tmp/backup.info"));
 CHECK(PartitionManager.MountByPath("/vendor/file",false));
 CHECK(vendor.mounts==1 && child.mounts==1);
 CHECK(PartitionManager.UnmountByPath("/mnt/vendor/persist/TWRP",false));
 CHECK(persist.unmounts==1 && mnt.unmounts==0);
 CHECK(PartitionManager.MountByPath("/sdcard/file",false));
 CHECK(media.mounts==1);
 CHECK(PartitionManager.MountByPath("/tmp/file",false));
 // Match dijun fstab: persist exists, but no partition is mounted at /mnt.
 PartitionManager.partitions_={&persist};persist.mounted=true;persist.can_mount=true;
 CHECK(PartitionManager.IsMountedByPath(TW_PERSIST_DIR));
 CHECK(twPersistMount(TW_PERSIST_DIR "/.twrp_settings"));
 persist.mounted=false;
 CHECK(PartitionManager.MountByPath(TW_PERSIST_DIR,false) && persist.mounted);
 std::printf("assertions=%u failures=%u\n",assertions,failures);
 return failures?1:0;
}
'''


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=SRC/'partitionmanager.cpp')
    parser.add_argument('--output',type=Path,default=ROOT/'logs/nested-partition-path-test.json')
    args=parser.parse_args()
    text=args.source.read_text()
    signatures=['bool TWPartitionManager::MatchesPath(',
                'TWPartition* TWPartitionManager::FindPartitionByPath(',
                'int TWPartitionManager::MountByPath(',
                'bool TWPartitionManager::UnmountByPath(',
                'int TWPartitionManager::IsMountedByPath(']
    bodies=[method(text,s) for s in signatures]
    bodies += [method((SRC/'twrp_functions.cpp').read_text(),'std::string TWFunc::GetRootPath('),
               method((SRC/'infomanager.cpp').read_text(),'static bool twPersistMount(')]
    with tempfile.TemporaryDirectory(prefix='dijun-nested-path-') as tmp:
        p=Path(tmp);(p/'test.cpp').write_text(HARNESS.replace('// METHODS','\n'.join(bodies)))
        subprocess.run(['g++','-std=c++23','-Wno-missing-field-initializers','-fsanitize=undefined',
                        '-fno-sanitize-recover=all',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
        result=subprocess.run([str(p/'test')],capture_output=True,text=True,timeout=10)
    sources=[args.source,SRC/'twrp_functions.cpp',SRC/'infomanager.cpp',Path(__file__).resolve()]
    report=dict(status='PASS' if result.returncode==0 else 'FAIL',scope=__doc__,
                output=result.stdout+result.stderr,returncode=result.returncode,
                sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    args.output.write_text(json.dumps(report,indent=2)+'\n');print(report['output'])
    raise SystemExit(result.returncode)


if __name__=='__main__':main()
