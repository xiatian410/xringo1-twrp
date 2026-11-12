#!/usr/bin/env python3
"""Execute the actual profile branches with partition/property/ExecCmd substitutes.

The branches are extracted unchanged from production source; the complete files
are also compiled by the Android build. This is not a full recovery boot test.
"""
from pathlib import Path
import subprocess
import tempfile

SRC=Path('/root/AAA/twrp/bootable/recovery')


def block(text, start):
    begin=text.index('  if (android::base::GetBoolProperty("ro.twrp.device_profiles"',start)
    opening=text.index('{',begin); depth=1; end=opening+1
    while depth:
        if text[end]=='{':depth+=1
        if text[end]=='}':depth-=1
        end+=1
    return text[begin:end]


loader=(SRC/'kernel_module_loader.cpp').read_text()
part=(SRC/'partitionmanager.cpp').read_text()
cache=block(loader,loader.index('bool KernelModuleLoader::LoadVendorModules()'))
publish=block(part,part.index('  UnmountMainPartitions();'))
decrypt=block(part,part.index('void TWPartitionManager::DecryptData()'))
credential=block(part,part.index('int TWPartitionManager::DecryptDevice('))
# Startup publication follows cleanup and precedes public storage readiness.
assert part.index(publish)>part.index('  UnmountMainPartitions();')
assert part.index(publish)<part.index('SetProperty("twrp.storage.ready", "1")')
HARNESS=r'''
#include <cassert>
#include <map>
#include <string>
#include <vector>
#include <functional>
#include <cstdio>
#define LOGINFO(...) ((void)0)
#define LOGERR(...) ((void)0)
static std::map<std::string,bool> props;
static std::vector<std::string> calls;
static int cache_result=0, module_result=0, publish_result=0, decrypt_calls=0;
static constexpr const char* TW_MODULES_MOUNTED_PROP="modules.loaded";
namespace android::base {
bool GetBoolProperty(const std::string& key,bool fallback) { return props.count(key)?props[key]:fallback; }
bool SetProperty(const std::string& key,const std::string& value) { props[key]=value=="1"||value=="true";return true; }
struct Guard {std::function<void()> fn;~Guard(){fn();}};
Guard make_scope_guard(std::function<void()> fn){return {fn};}
}
struct TWPartition {
 std::string path;bool mounted=false;bool available=true;
 bool IsMounted(){return mounted;}
 bool Mount(bool){calls.push_back("mount "+path);mounted=available;return mounted;}
 bool Unmount(bool){calls.push_back("unmount "+path);mounted=false;return true;}
 std::string GetMountPoint(){return path;}
};
struct Manager {
 std::map<std::string,TWPartition> partitions;
 TWPartition* FindPartitionByPath(const std::string& path){return partitions.count(path)?&partitions.at(path):nullptr;}
} PartitionManager;
namespace TWFunc {
int ExecCmd(const std::string& cmd) {
 calls.push_back(cmd);
 if(cmd.find(" cache")!=std::string::npos) {
  if(!cache_result) for(const auto& name:{"/system_root","/vendor","/odm","/vendor_dlkm"})assert(PartitionManager.partitions.at(name).mounted);
  return cache_result;
 }
 if(cmd.find(" modules")!=std::string::npos)return module_result;
 if(cmd.find(" publish")!=std::string::npos)return publish_result;
 assert(false);return 1;
}
}
bool load(){CACHE;calls.push_back("legacy fallback");return false;}
void publish(){PUBLISH;}
void decrypt(){DECRYPT;++decrypt_calls;}
int credential(){CREDENTIAL;++decrypt_calls;return 0;}
void reset(){
 props.clear();calls.clear();cache_result=module_result=publish_result=decrypt_calls=0;
 PartitionManager.partitions.clear();
 for(const auto& name:{"/system_root","/vendor","/odm","/vendor_dlkm","/system_dlkm"})
  PartitionManager.partitions.emplace(name,TWPartition{name,false,true});
}
int main(){
 for(int failure:{0,1}) {
  reset();props["ro.twrp.device_profiles"]=true;cache_result=failure;
  PartitionManager.partitions.at("/vendor").mounted=true;
  PartitionManager.partitions.at("/odm").mounted=true;
  assert(load()==!failure);
  assert(props[TW_MODULES_MOUNTED_PROP]);
  int cached=0,modules=0;
  for(const auto& call:calls){assert(call!="legacy fallback");if(call.find(" cache")!=std::string::npos)++cached;if(call.find(" modules")!=std::string::npos)++modules;}
  assert(cached==1 && modules==!failure);
  assert(PartitionManager.partitions.at("/vendor").mounted);
  assert(PartitionManager.partitions.at("/odm").mounted);
  assert(!PartitionManager.partitions.at("/system_root").mounted);
  assert(!PartitionManager.partitions.at("/vendor_dlkm").mounted);
 }
 reset();props["ro.twrp.device_profiles"]=true;module_result=1;assert(load());
 reset();assert(!load() && calls.back()=="legacy fallback");
 reset();props["ro.twrp.device_profiles"]=true;props["twrp.crypto.ready"]=true;
 publish_result=1;publish();assert(!props["twrp.crypto.ready"]);
 decrypt();assert(decrypt_calls==0);assert(credential()==-1 && decrypt_calls==0);
 props["twrp.crypto.ready"]=true;decrypt();assert(credential()==0 && decrypt_calls==2);
 reset();decrypt();assert(credential()==0 && decrypt_calls==2);
 std::puts("PASS: no legacy fallback, preserve preexisting mounts, release owned mounts, cache/module failures, publish failure, automatic/manual crypto guards, non-profile behavior");
}
'''
with tempfile.TemporaryDirectory(prefix='dijun-core-test-') as temp:
    temp=Path(temp)
    code=HARNESS.replace('CACHE',cache).replace('PUBLISH',publish).replace('DECRYPT',decrypt).replace('CREDENTIAL',credential)
    (temp/'test.cpp').write_text(code)
    subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror',str(temp/'test.cpp'),'-o',str(temp/'test')],check=True)
    subprocess.run([str(temp/'test')],check=True,timeout=10)
