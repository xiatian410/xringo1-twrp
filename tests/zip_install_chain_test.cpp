// Native production ZIP/package/signature/digest/updater chain in a private jail.
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
using namespace std;
namespace fs=std::filesystem;
#define LOGINFO(...) printf(__VA_ARGS__)
#define LOGERR(...) printf(__VA_ARGS__)
#define EXPAND(x) "3"
#define RECOVERY_API_VERSION 3
#define TMP_UPDATER_BINARY_PATH "/tmp/updater"
#define AB_OTA "payload_properties.txt"
#define TW_SIGNED_ZIP_VERIFY_VAR "verify"
#define TW_UNMOUNT_SYSTEM "unmount"
#define TW_AUTO_DISABLE_AVB2_VAR "disable_avb"
enum zip_type {UNKNOWN_ZIP_TYPE,UPDATE_BINARY_ZIP_TYPE,AB_OTA_ZIP_TYPE};
static constexpr const char* UPDATE_DYNAMIC_PART_OP_LIST_NAME="dynamic_partitions_op_list";
static constexpr const char* UPDATE_SUPER_IMAGE_ZST="super.img.zst";
static constexpr const char* UPDATE_SUPER_ZST="super.zst";
static string scenario;
static unsigned digest_checks=0;
struct DataManager {
  static void GetValue(const string& key,int& value) {
    value=key=="verify"?(scenario.starts_with("signed-") || scenario=="unsigned-required" || scenario=="no-keys"):
          key=="unmount"?scenario=="unmount-denied":0;
  }
  static int GetIntValue(const string&) {return 0;}
  static void SetProgress(float f,bool=false) {assert(isfinite(f) && f>=0 && f<=1);}
  static void ShowProgress(float f,int s) {assert(isfinite(f) && f>=0 && f<=1 && s>=0);}
};
namespace gui2_console {
template<class...T>void info(T&&...) {}
template<class...T>void log_error(T&&...) {}
template<class...T>void highlight(T&&...) {}
template<class...T>void warning(T&&...) {}
}
struct Manager {
  string GetAndroidRootPath(){return "/system_root";}
  bool UnmountByPath(const string&,bool) {assert(scenario=="unmount-denied");return false;}
  void DisableAvb2(bool){assert(false);}
} PartitionManager;
namespace TWFunc {
int WaitForChild(pid_t,int*,const string&,bool=true);
vector<string> SplitString(const string&,char,bool);
string GetFilename(const string& name){return fs::path(name).filename().string();}
}
int property_get(const char* name,char* value,const char* fallback) {
  string v=fallback;
  bool missing=scenario=="arch-no-properties" || scenario=="generic-no-properties";
  if(string(name)=="ro.product.cpu.abilist" && !missing && scenario!="arch-abi-property")
    v=scenario=="arch-reversed"?"armeabi-v7a,arm64-v8a":
      scenario=="arch-empty-fallback" || scenario=="arch-empty-all"?"":"arm64-v8a,armeabi-v7a";
  if(string(name)=="ro.product.cpu.abi" && !missing)v=scenario=="arch-empty-all"?"":"arm64-v8a";
  strcpy(value,v.c_str());return v.size();
}
void gui_print(const char* fmt,...) {va_list ap;va_start(ap,fmt);vprintf(fmt,ap);va_end(ap);}
int abupdate_binary_command(const char*,int,int,vector<string>*) {assert(false);return INSTALL_ERROR;}
int update_binary_command(const char*,int,int,vector<string>*);
bool verify_package_compatibility(ZipArchiveHandle);
// PRODUCTION_METHODS
int main(int argc,char** argv) {
  assert(argc==3);scenario=argv[1];bool expected=string(argv[2])=="1";
  int wipe=0;
  const char* input=scenario=="missing-file"?"/packages/absent.zip":"/packages/test.zip";
  int result=TWinstall_zip(input,&wipe,scenario.starts_with("digest-"));
  printf("install_result=%d wipe_cache=%d\n",result,wipe);fflush(stdout);
  assert((result==INSTALL_SUCCESS)==expected);
  assert(fs::exists("/packages/result.txt")==expected);
  if(expected)assert(wipe==1);
  int status;errno=0;assert(waitpid(-1,&status,WNOHANG)==-1 && errno==ECHILD);
}
