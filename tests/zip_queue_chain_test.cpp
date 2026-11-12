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
#include "twrp_digest_driver.hpp"
#include "twrp_digest.hpp"
#include "twrp_install_backend.h"
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
 void UpdateSystemDetails(bool async){assert(async);++refreshes;events.push_back("refresh");}
 bool WipeByPath(const string&path){
  assert(path=="/cache");++wipes;events.push_back("wipe");
  if(scenario.starts_with("cache-error"))return false;
  FILE*f=fopen("/packages/cache-cleared","w");assert(f);fclose(f);return true;
 }
}PartitionManager;
namespace TWFunc {
int WaitForChild(pid_t,int*,const string&,bool=true);
vector<string> SplitString(const string&,char,bool);
string GetFilename(const string&name){return fs::path(name).filename().string();}
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
namespace gui2_backend {
void operation_start(const string&){++starts;}
void operation_end(int result){++operation_ends;op_result=result;events.push_back("end");}
// Image-only virtual members are explicit unexecuted boundaries.
vector<image_target> twrp_install_backend::image_targets(){assert(false);return {};}
string twrp_install_backend::image_target_for(const string&){assert(false);return {};}
bool twrp_install_backend::start_image(const string&,const string&,bool){assert(false);return false;}
}
// PRODUCTION_METHODS
static gui2_backend::install_status wait_done(gui2_backend::twrp_install_backend&backend){
 auto deadline=chrono::steady_clock::now()+chrono::seconds(8);
 for(;;){auto s=backend.status();if(s.state!=gui2_backend::install_state::RUNNING)return s;
  assert(chrono::steady_clock::now()<deadline);this_thread::sleep_for(chrono::milliseconds(2));}
}
int main(int argc,char**argv){
 assert(argc==2);scenario=argv[1];using namespace gui2_backend;
 vector<string> queue={"/packages/first.zip"};
 if(fs::exists("/packages/second.zip"))queue.push_back("/packages/second.zip");
 if(scenario=="empty-item")queue={""};
 DataManager::SetValue("skip_digest",scenario=="digest-skip"?1:0);
 DataManager::SetValue("verify",scenario=="signature-reject"?1:0);
 if(scenario=="empty-queue"){
  twrp_install_backend b;assert(!b.start_zip({}));assert(b.status().state==install_state::IDLE);
  assert(!invalidates&&!starts&&!operation_ends);return 0;
 }
 bool expected_failure=scenario=="cache-error"||scenario=="cache-error-after-queue"||scenario=="updater-fail"||
  scenario=="protocol-error"||scenario=="wipe-first-then-fail"||scenario=="wipe-failing"||scenario=="wipe-first-badprogress"||
  scenario=="wipe-first-missing"||scenario=="missing-first"||scenario=="empty-item"||scenario=="digest-reject"||scenario=="signature-reject"||scenario=="reuse";
 int expected_done=expected_failure?0:queue.size();
 if(scenario.starts_with("cache-error"))expected_done=queue.size();
 if(scenario.starts_with("wipe-first-")||scenario=="wipe-first-missing")expected_done=1;
 unsigned expected_wipes=(scenario=="single-wipe"||scenario.starts_with("wipe-")||scenario.starts_with("cache-error"))?1:0;
 if(scenario=="destructor-join"){
  {twrp_install_backend b;assert(b.start_zip(queue));}
  assert(operation_ends==1&&op_result==0&&refreshes==1&&perf_on==queue.size()&&perf_on==perf_off);
  return 0;
 }
 {
  twrp_install_backend b;assert(b.start_zip(queue));
  if(scenario=="busy"){
   auto deadline=chrono::steady_clock::now()+chrono::seconds(5);
   while(!fs::exists("/packages/entered")){assert(chrono::steady_clock::now()<deadline);this_thread::sleep_for(chrono::milliseconds(2));}
   assert(b.status().state==install_state::RUNNING);b.acknowledge();assert(b.status().state==install_state::RUNNING);
   assert(!b.start_zip({"/packages/second.zip"}));
   FILE*f=fopen("/packages/release","w");assert(f);fclose(f);
  }
  auto status=wait_done(b);
  assert(status.state==(expected_failure?install_state::FAILED:install_state::DONE));
  assert(status.items==queue&&status.done==expected_done);
  assert(status.current==(expected_failure?expected_done==int(queue.size())?int(queue.size())-1:expected_done:int(queue.size())-1));
  // Acknowledge joins the finished worker before counters are inspected.
  b.acknowledge();assert(b.status().state==install_state::IDLE);
  assert(wipes==expected_wipes);assert(operation_ends==1&&op_result==(expected_failure?1:0));
  assert(refreshes==1&&invalidates==1&&events.front()=="invalidate"&&events.back()=="end");
  assert(DataManager::GetIntValue(TW_ZIP_QUEUE_COUNT)==0&&perf_on==perf_off);
  if(scenario=="reuse"){
   assert(b.start_zip({"/packages/second.zip"}));auto next=wait_done(b);
   assert(next.state==install_state::DONE&&next.items.size()==1&&next.done==1&&next.current==0);
   b.acknowledge();assert(refreshes==2&&invalidates==2&&operation_ends==2);
  }
 }
 int status;errno=0;assert(waitpid(-1,&status,WNOHANG)==-1&&errno==ECHILD);
 printf("PASS queue=%zu done=%d wipe=%u result=%d perf=%u/%u unlock=%u mount=%u\n",queue.size(),expected_done,wipes,op_result,perf_on,perf_off,unlocks,mounts);
}
