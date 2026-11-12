// Production worker -> flash_zip -> TWinstall_zip -> real ZIP/digest/fork/exec.
#include <algorithm>
#include <array>
#include <cassert>
#include <cerrno>
#include <climits>
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <functional>
#include <map>
#include <optional>
#include <ranges>
#include <string>
#include <vector>
#include <fcntl.h>
#include <signal.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include <android-base/file.h>
#include <android-base/strings.h>
#include <android-base/unique_fd.h>
#include <ziparchive/zip_archive.h>
#include "twinstall/install.h"
#include "twinstall.h"
#include "otautil/sysutil.h"
#include "twrp_digest_driver.hpp"
#include "twrp_digest.hpp"
#include <atomic>
#include <mutex>
#include <thread>
#include <chrono>
#include <sys/epoll.h>
#include <sys/socket.h>
#include <android-base/logging.h>
#include <android-base/memory.h>
#include <android-base/properties.h>
#include <android-base/scopeguard.h>
#include "minadbd/types.h"
#include "twrp_sideload_backend.h"
using namespace std;
namespace fs=std::filesystem;
#define LOGINFO(...) printf(__VA_ARGS__)
#define LOGERR(...) printf(__VA_ARGS__)
#define PROPERTY_VALUE_MAX 92
#define EXPAND(x) "3"
#define RECOVERY_API_VERSION 3
#define TMP_UPDATER_BINARY_PATH "/tmp/updater"
#define AB_OTA "payload_properties.txt"
#define TW_SIGNED_ZIP_VERIFY_VAR "verify"
#define TW_UNMOUNT_SYSTEM "unmount"
#define TW_AUTO_DISABLE_AVB2_VAR "disable_avb"
#define TW_SKIP_DIGEST_CHECK_ZIP_VAR "skip_digest"
#define TW_ZIP_INDEX "zip_index"
#define TW_ZIP_QUEUE_COUNT "zip_count"
enum zip_type {UNKNOWN_ZIP_TYPE,UPDATE_BINARY_ZIP_TYPE,AB_OTA_ZIP_TYPE};
static constexpr const char* UPDATE_DYNAMIC_PART_OP_LIST_NAME="dynamic_partitions_op_list";
static constexpr const char* UPDATE_SUPER_IMAGE_ZST="super.img.zst";
static constexpr const char* UPDATE_SUPER_ZST="super.zst";
static string scenario;
struct DataManager {
 inline static mutex lock;
 inline static map<string,string> values;
 static void SetValue(const string&k,const string&v){lock_guard<mutex>g(lock);values[k]=v;}
 static void SetValue(const string&k,int v){SetValue(k,to_string(v));}
 static string GetStrValue(const string&k){lock_guard<mutex>g(lock);return values[k];}
 static int GetIntValue(const string&k){return atoi(GetStrValue(k).c_str());}
 static void GetValue(const string&k,int&v){v=GetIntValue(k);}
 static void SetProgress(float f,bool=false){assert(isfinite(f)&&f>=0&&f<=1);SetValue("ui_progress",int(f*100));}
 static void ShowProgress(float f,int s){assert(isfinite(f)&&f>=0&&f<=1&&s>=0);}
};
namespace gui2_console {
string text(const string& s){return s;}
template<class...T>void info(T&&...){}
template<class...T>void log_error(T&&...){}
template<class...T>void highlight(T&&...){}
template<class...T>void warning(T&&...){}
}
static vector<string> events;
static unsigned wipes=0,unlocks=0,mounts=0,refreshes=0,invalidates=0,starts=0,operation_ends=0,perf_on=0,perf_off=0;
static int op_result=-1;
struct Manager {
 string GetAndroidRootPath(){return "/system_root";}
 bool UnmountByPath(const string&,bool){assert(false);return false;}
 bool MountByPath(const string&,bool){++mounts;return false;}
 void DisableAvb2(bool){assert(false);}
 void UnlockBlockPartitions(){++unlocks;}
 void InvalidateAsyncDataSize(){++invalidates;events.push_back("invalidate");}
 void UpdateSystemDetails(bool async=false){++refreshes;events.push_back("refresh");}
 bool WipeByPath(const string&path){
  assert(path=="/cache");++wipes;events.push_back("wipe");
  FILE* record=fopen("/packages/cache-events","a");assert(record);fputs("attempt\n",record);fclose(record);
  if(scenario.find("cache-error")!=string::npos||scenario=="both-cleanup-errors")return false;
  FILE*f=fopen("/packages/cache-cleared","w");assert(f);fclose(f);return true;
 }
 int WipeDalvikCache(){++dalviks;return scenario.find("dalvik-error")==string::npos;}
 inline static unsigned dalviks=0;
}PartitionManager;
namespace TWFunc {
int WaitForChild(pid_t,int*,const string&,bool=true);
vector<string> SplitString(const string&,char,bool);
string GetFilename(const string&name){return fs::path(name).filename().string();}
bool ToggleMtp(bool enabled){static bool state=true;bool old=state;state=enabled;events.push_back(enabled?"mtp-on":"mtp-off");return old;}
bool IsPathExists(const string&p){return fs::exists(p);}
int ExecCmd(const string&){assert(false);return -1;}
void SetPerformanceMode(bool on){if(on)++perf_on;else ++perf_off;}
}
int property_get(const char*name,char*value,const char*fallback){
 string v=string(name)=="ro.product.cpu.abilist"?"arm64-v8a,armeabi-v7a":fallback;
 strcpy(value,v.c_str());return v.size();
}
int umount(const char*){assert(false);return -1;}
void gui_print(const char*fmt,...){va_list ap;va_start(ap,fmt);vprintf(fmt,ap);va_end(ap);}
int abupdate_binary_command(const char*,int,int,vector<string>*){assert(false);return INSTALL_ERROR;}
int update_binary_command(const char*,int,int,vector<string>*);
bool verify_package_compatibility(ZipArchiveHandle);

namespace android::base {
bool SetProperty(const string&,const string&){return true;}
bool WaitForProperty(const string&,const string&,chrono::milliseconds = chrono::milliseconds::max()){return true;}
string GetProperty(const string&,const string&){return "adb";}
}
namespace gui2_backend {
void operation_start(const string&){++starts;}
void operation_end(int result){++operation_ends;op_result=result;events.push_back("end");}
}
struct Device {enum BuiltinAction {NO_ACTION,REBOOT,REBOOT_BOOTLOADER,REBOOT_FASTBOOT,REBOOT_RECOVERY,REBOOT_RESCUE};};
#define FUSE_SIDELOAD_HOST_PATHNAME "/sideload/package.zip"
#define FUSE_SIDELOAD_HOST_EXIT_PATHNAME "/sideload/exit"
static int exit_stats=0;
static int sideload_stat(const char* p,struct stat* st){
 if(string(p)==FUSE_SIDELOAD_HOST_EXIT_PATHNAME){++exit_stats;errno=ENOENT;return -1;}return ::stat(p,st);
}
// CORE_HEADER
// ZIP_METHODS
#define stat(...) sideload_stat(__VA_ARGS__)
// SIDELOAD_CORE
#undef stat
// SIDELOAD_BACKEND
static int property_set(const char* name,const char* value){assert(string(name)=="ctl.start"&&string(value)=="adbd");return 0;}
// This is the actual ORS sideload branch, not the rest of the script parser.
static int script_sideload(){
 int install_cmd=0,ret_val=0,sideload=0;
 // ORS_BRANCH
 assert(install_cmd==-1&&sideload==1);return ret_val;
}
static void wait_done(gui2_backend::twrp_sideload_backend& backend){
 auto end=chrono::steady_clock::now()+chrono::seconds(8);
 while(backend.status().state==gui2_backend::sideload_state::RUNNING){assert(chrono::steady_clock::now()<end);this_thread::sleep_for(chrono::milliseconds(1));}
}
int main(int argc,char**argv){
 assert(argc==3);scenario=argv[1];string expected=argv[2];bool fail=expected=="fail";
 DataManager::SetValue("skip_digest",scenario=="digest-skip");DataManager::SetValue("verify",scenario=="signature-reject");
 if(scenario.starts_with("script-"))assert(script_sideload()==(fail?1:0));
 else {
  gui2_backend::twrp_sideload_backend b;
  bool cache=scenario=="user-cache"||scenario=="user-cache-error"||scenario=="package-and-user-cache";
  bool dalvik=scenario=="user-dalvik"||scenario=="user-dalvik-error"||scenario=="both-cleanup-errors";
  if(scenario=="both-cleanup-errors")cache=true;
  assert(b.start(dalvik,cache));wait_done(b);
  assert(b.status().state==(fail?gui2_backend::sideload_state::FAILED:gui2_backend::sideload_state::DONE));b.acknowledge();
  assert(operation_ends==1&&op_result==(fail?1:0));
  assert(events.front()=="mtp-off"&&events[events.size()-2]=="mtp-on");
  assert(Manager::dalviks==(dalvik?1u:0u));
 }
 int status=0;errno=0;assert(waitpid(-1,&status,WNOHANG)==-1&&errno==ECHILD);assert(GetMiniAdbdPid()==0);
 FILE* f=fopen("/packages/counts","w");assert(f);fprintf(f,"wipes=%u dalviks=%u exit_stats=%d\n",wipes,Manager::dalviks,exit_stats);fclose(f);
 return 0;
}
