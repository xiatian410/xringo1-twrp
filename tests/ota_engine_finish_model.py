"""Explicit file/metadata/mount model for joined stock OTA finalization.

Original postinstall script and SnapshotManager completion execute. No actual
block readonly, filesystem mount, snapshot allocation, slot switch or merge.
Initiated/snapshot protobufs model allocation at PreparePartitionsForUpdate.
"""
import hashlib
import shutil
import subprocess
from pathlib import Path

from ota_vabc_session import ROOT, ANDROID
from zip_stock_support import sha

RO_SYMBOL='_ZN22chromeos_update_engine5utils22SetBlockDeviceReadOnlyERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEEb'
MOUNT_SYMBOL='_ZN22chromeos_update_engine5utils15MountFilesystemERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEES9_mS9_S9_'
UNMOUNT_SYMBOL='_ZN22chromeos_update_engine5utils17UnmountFilesystemERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEE'
IS_MOUNT_SYMBOL='_ZN22chromeos_update_engine5utils12IsMountpointERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEE'


def extend(adapter, sources):
    for p in [Path(__file__), ROOT/'tests/ota_snapshot_finish.cpp',
              ANDROID/'system/update_engine/aosp/dynamic_partition_control_android.cc',
              ANDROID/'system/core/fs_mgr/libsnapshot/snapshot.cpp',
              ANDROID/'system/core/fs_mgr/libsnapshot/utility.cpp']:
        sources[str(p)]=sha(p)
    prefix=r'''
#define main snapshot_leaf_main
#include "ota_snapshot_finish.cpp"
#undef main
#include "update_engine/aosp/dynamic_partition_control_android.h"
struct ModelMetadataToken final:AutoDevice {
 ModelMetadataToken():AutoDevice("model-already-mounted"){}
};
namespace chromeos_update_engine {
class DynamicPartitionControlAndroidTest {
 public:static void Inject(DynamicPartitionControlAndroid& c){
  c.snapshot_=SnapshotManager::New(new Info);
  c.metadata_device_=std::make_unique<ModelMetadataToken>();
 }
};
}
class ModelCompletion final:public chromeos_update_engine::DynamicPartitionControlAndroid {
 public:ModelCompletion():DynamicPartitionControlAndroid(0){chromeos_update_engine::DynamicPartitionControlAndroidTest::Inject(*this);}
 chromeos_update_engine::FeatureFlag GetVirtualAbFeatureFlag()override {
  return chromeos_update_engine::FeatureFlag(chromeos_update_engine::FeatureFlag::Value::LAUNCH);
 }
 protected:bool IsRecovery()override{return true;}
};
static void model_prepare(const std::set<std::string>& names) {
 fs::create_directories("/work/meta/snapshots");
 SnapshotUpdateStatus state;state.set_state(UpdateState::Initiated);
 state.set_using_snapuserd(true);state.set_userspace_snapshots(true);
 write("/work/meta/state",state.SerializeAsString());
 for(const auto& n:names){SnapshotStatus s;s.set_name(n+"_b");s.set_using_snapuserd(true);
  write("/work/meta/snapshots/"+n+"_b",s.SerializeAsString());}
 printf("MODEL allocation metadata seeded snapshots=%zu\n",names.size());fflush(stdout);
}
static bool model_finish(bool wipe) {
 assert(!wipe);ModelCompletion control;
 bool ok=control.FinishUpdate(wipe);
 SnapshotUpdateStatus state;assert(state.ParseFromString(read("/work/meta/state")));
 printf("MODEL actual FinishedSnapshotWrites result=%d state=%d merges=%u\n",ok,int(state.state()),merge_calls);fflush(stdout);
 assert(ok&&state.state()==UpdateState::Unverified&&merge_calls==1);
 assert(read("/work/meta/snapshot-boot")=="_a");
 return ok;
}
static void model_slot() {
 SnapshotUpdateStatus state;assert(state.ParseFromString(read("/work/meta/state")));
 assert(state.state()==UpdateState::Unverified);
 write("/work/model-active-slot","1");puts("MODEL active slot=1 after Unverified");fflush(stdout);
}
'''
    # Prefix needs these STL types before the existing adapter's includes.
    prefix='#include <set>\n#include <string>\n'+prefix
    adapter=adapter.replace('++prepares;','model_prepare(dynamic);\n        ++prepares;')
    old='assert(!powerwash); ++finishes; final_events.push_back("finish"); return finish_ok;'
    assert old in adapter
    adapter=adapter.replace(old,'assert(!powerwash); ++finishes; final_events.push_back("finish"); return model_finish(powerwash);')
    old='assert(slot == 1); ++switches; final_events.push_back("slot"); return slot_ok;'
    assert old in adapter
    adapter=adapter.replace(old,'assert(slot == 1); model_slot(); ++switches; final_events.push_back("slot"); return slot_ok;')
    wrappers=r'''
static bool model_mounted=false;
#define MODEL_WRAP(name,symbol,params) extern "C" bool name params __asm__("__wrap_" symbol);extern "C" bool name params
MODEL_WRAP(model_ro,"RO_SYMBOL",(const std::string& p,bool ro)){
 assert(p.starts_with("/work/")&&p.ends_with(".bin"));
 printf("MODEL block readonly=%d %s\n",ro,p.c_str());return true;
}
MODEL_WRAP(model_mount,"MOUNT_SYMBOL",(const std::string& p,const std::string& target,unsigned long,const std::string&,const std::string&)){
 assert(p=="/work/system.bin"&&target=="/postinstall"&&!model_mounted);
 model_mounted=true;puts("MODEL mount system at /postinstall; staged exact script only");fflush(stdout);return true;
}
MODEL_WRAP(model_unmount,"UNMOUNT_SYMBOL",(const std::string& p)){
 assert(p=="/postinstall"&&model_mounted);model_mounted=false;puts("MODEL unmount postinstall");fflush(stdout);return true;
}
MODEL_WRAP(model_is_mount,"IS_MOUNT_SYMBOL",(const std::string& p)){
 assert(p=="/postinstall");return model_mounted;
}
extern "C" int __real_execv(const char*,char*const[]);
extern "C" int __wrap_execv(const char* p,char*const argv[]){
 assert(std::string(p)=="/postinstall/system/bin/otapreopt_script");
 assert(argv[0]&&argv[1]&&std::string(argv[1])=="1"&&argv[2]&&std::string(argv[2])=="3"&&!argv[3]);
 std::vector<std::string> args={"/qemu","-L","/android","-E","LD_LIBRARY_PATH=/android/system/lib64",
  "-E","PATH=/fixture","/android/system/bin/linker64","/android/system/bin/sh",p,argv[1],argv[2]};
 std::vector<char*> ptrs;for(auto& s:args)ptrs.push_back(s.data());ptrs.push_back(nullptr);
 return __real_execv("/qemu",ptrs.data());
}
'''
    for n in ['IS_MOUNT_SYMBOL','UNMOUNT_SYMBOL','MOUNT_SYMBOL','RO_SYMBOL']:
        wrappers=wrappers.replace(n,globals()[n])
    return prefix+adapter+wrappers


def stage(jail, sources, dependencies):
    system=ROOT/'firmware/samples/os4-stable/system.img'
    import json
    inventory=json.loads(system.with_name('inventory.json').read_text())
    assert sha(system)==inventory['partitions']['system']['sha256']
    tool=Path(shutil.which('dump.erofs')).resolve()
    script=subprocess.check_output([str(tool),'--cat','--path=/system/bin/otapreopt_script',str(system)])
    dependencies[str(tool)]=sha(tool)
    dest=jail/'postinstall/system/bin/otapreopt_script'
    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(script);dest.chmod(0o755)
    from firmware_facts import boot_parts,ramdisk_entries
    image=Path(json.loads((ROOT/'simulation-report.json').read_text())['image'])
    entries={}
    for n,m,*rest in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk']):
        if n in ['system/bin/sh','system/bin/toolbox']:
            dest=jail/'android'/n;dest.write_bytes(rest[-1]);dest.chmod(m&0o777)
            entries[n]=hashlib.sha256(rest[-1]).hexdigest()
    # Host static command bridge executes actual delivered ARM64 getprop.
    # No supplied "boot complete" value, no ART or device command.
    c=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
int main(int argc,char**argv){
 assert(argc==2&&!strcmp(argv[1],"dev.bootcomplete"));
 FILE*f=fopen("/work/getprop-called","w");assert(f);fputs(argv[1],f);assert(!fclose(f));
 char*args[]={"/qemu","-L","/android","-E","LD_LIBRARY_PATH=/android/system/lib64",
 "/android/system/bin/linker64","/android/system/bin/toolbox","getprop",argv[1],0};
 execv("/qemu",args);return 99;
}
'''
    source=jail.parent/'getprop-adapter.c';source.write_text(c)
    (jail/'fixture').mkdir()
    cc=Path(shutil.which('cc')).resolve();dependencies[str(cc)]=sha(cc)
    subprocess.run([str(cc),'-static','-O2',str(source),'-o',str(jail/'fixture/getprop')],check=True)
    return dict(script_sha256=hashlib.sha256(script).hexdigest(),system_sha256=inventory['partitions']['system']['sha256'],
                image_entries=entries,getprop_bridge_sha256=sha(jail/'fixture/getprop'))
