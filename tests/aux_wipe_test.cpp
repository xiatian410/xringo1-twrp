// Private chroot files and real permission failures; mount and UI are fixtures.
#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <functional>
#include <mutex>
#include <string>
#include <vector>
#include <grp.h>
#include <sys/stat.h>
#include <unistd.h>
#include "wipe_backend.h"
#include "mount_backend.h"
namespace fs = std::filesystem;
#define LOGINFO(...) ((void)0)
#define TW_HAS_DATA_MEDIA "media"
#define TW_EXTERNAL_PATH "external"
static bool mount_ok=true;
static int last_result=-1, success_messages=0, errors=0;
static std::string target;
namespace gui2_console {
template<class... T>void info(T...) {}
template<class... T>void log_error(T...) {++errors;}
}
static void gui_print(const char*message) {
  if (std::string(message)=="Cleared battery stats.\n") ++success_messages;
}
namespace twrp_operation_executor {
struct executor { std::recursive_mutex m; auto& mutex(){return m;} };
executor& instance(){static executor e;return e;}
using guard=std::lock_guard<std::recursive_mutex>;
}
namespace TWFunc {
bool IsPathExists(const std::string&p){std::error_code ec;return fs::exists(p,ec);}
int RemoveDir(const std::string&, bool);
}
struct DataManager {
static std::string GetStrValue(const std::string&){return target+";";}
static std::string GetCurrentStoragePath(){return "/data/media";}
static void GetValue(const std::string&,std::string&v){v=target+";";}
static void GetValue(const std::string&,int&v){v=1;}
template<class T>static void SetValue(const std::string&,const T&){}
};
void operation_start(const char*){}
void operation_end(int v){last_result=v;}
struct TWPartition {
std::string mount_point_,backup_display_name_;
bool has_android_secure_=true;
int calls=0;
std::string GetMountPoint()const{return mount_point_;}
bool Mount(bool){++calls;return mount_ok;}
bool WipeAndSec();
};
struct TWPartitionManager {
std::vector<TWPartition*> partitions_;
int MountByPath(const std::string&p,bool)const{assert(p=="/data");return mount_ok;}
TWPartition* FindPartitionByPath(const std::string&)const{return nullptr;}
int WipeBatteryStats()const;
int WipeAndroidSecure()const;
bool FactoryReset(){assert(false);return false;}
bool WipeRotateData(){assert(false);return false;}
bool WipeDalvikCache(){assert(false);return false;}
bool FormatData(){assert(false);return false;}
bool WipeMediaFromData(){assert(false);return false;}
bool WipeByPath(const std::string&){assert(false);return false;}
void UpdateSystemDetails(){}
} PartitionManager;
namespace gui2_backend {
struct twrp_wipe_backend {
std::mutex mutex_;
wipe_status status_;
std::atomic<bool>running_{true};
std::chrono::steady_clock::time_point started_=std::chrono::steady_clock::now();
void report_item(const std::string&,int,bool);
void run(std::vector<std::string>);
};
}
#include "methods.inc"
static void dir(const fs::path&p){fs::create_directories(p);chmod(p.c_str(),0777);}
static void put(const fs::path&p){std::ofstream(p)<<"keep";}
int main(int argc,char**argv){
assert(argc==2);std::string name=argv[1];
const bool battery=name.starts_with("battery-");
const bool list=name.ends_with("-list");
bool expected=true;
int expected_calls=0;
TWPartition first,second,ignored;
first.mount_point_="/first";second.mount_point_="/second";
ignored.mount_point_="/ignored";ignored.has_android_secure_=false;
dir("/data");dir("/data/system");dir("/outside");put("/outside/keep");
if(battery){
  target="battery";
  if(name!="battery-missing")put("/data/system/batterystats.bin");
  if(name=="battery-delete-denied"){chmod("/data/system",0555);expected=false;}
  if(name=="battery-lookup-denied"){chmod("/data",0000);expected=false;}
  if(name=="battery-directory"){fs::remove("/data/system/batterystats.bin");dir("/data/system/batterystats.bin");expected=false;}
  if(name=="battery-link"){fs::remove("/data/system/batterystats.bin");fs::create_symlink("/outside/keep","/data/system/batterystats.bin");}
  if(name=="battery-mount-denied"){mount_ok=false;expected=false;}
}else{
  target=list?"/and-sec":"ANDROIDSECURE";
  dir("/first");dir("/second");dir("/first/.android_secure");dir("/second/.android_secure");
  put("/first/.android_secure/file");put("/second/.android_secure/file");
  PartitionManager.partitions_={&ignored,&first,&second};expected_calls=2;
  if(name=="secure-first-denied"||name=="secure-first-denied-list"){
    chmod("/first/.android_secure",0555);expected=false;expected_calls=1;
  }
  if(name=="secure-second-denied"){chmod("/second/.android_secure",0555);expected=false;}
  if(name=="secure-all-denied"){chmod("/first/.android_secure",0555);chmod("/second/.android_secure",0555);expected=false;expected_calls=1;}
  if(name=="secure-missing")fs::remove_all("/first/.android_secure");
  if(name=="secure-none"){PartitionManager.partitions_={&ignored};expected=false;expected_calls=0;}
  if(name=="secure-mount-denied"){mount_ok=false;expected=false;expected_calls=1;}
}
assert(setgroups(0,nullptr)==0&&setgid(65534)==0&&setuid(65534)==0);
gui2_backend::twrp_wipe_backend backend;backend.run({list?"LIST":target});
printf("result=%d done=%d first=%d second=%d success=%d\n",last_result,backend.status_.done,first.calls,second.calls,success_messages);fflush(stdout);
assert(last_result==(expected?0:1)&&!backend.running_);
assert(backend.status_.state==(expected?gui2_backend::wipe_state::DONE:gui2_backend::wipe_state::FAILED));
assert(backend.status_.done==(expected?1:0));
assert(fs::exists("/outside/keep"));
if(battery){
  assert(success_messages==(expected&&name!="battery-missing"?1:0));
  if(expected)assert(!fs::exists(fs::symlink_status("/data/system/batterystats.bin")));
}else{
  assert(first.calls+second.calls==expected_calls&&ignored.calls==0);
  if(!expected&&expected_calls==1)assert(fs::exists("/second/.android_secure/file"));
  if(expected)assert(!fs::exists("/first/.android_secure/file")&&!fs::exists("/second/.android_secure/file"));
}
puts("PASS: actual private-file deletion result reaches backend terminal state");
}
