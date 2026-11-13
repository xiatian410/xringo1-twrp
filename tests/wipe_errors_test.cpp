// Private chroot only. Mount/device/operation boundaries are fixtures.
#include <algorithm>
#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <functional>
#include <mutex>
#include <string>
#include <vector>
#include <unistd.h>
#include <grp.h>
#include <sys/stat.h>
#include "wipe_backend.h"
#include "mount_backend.h"
namespace fs=std::filesystem;
#define LOGINFO(...) ((void)0)
#define TW_HAS_DATA_MEDIA "media"
#define TW_EXTERNAL_PATH "external"
namespace gui2_console {template<class... T>void info(T...){} template<class... T>void log_error(T...){} }
namespace twrp_operation_executor {struct executor{std::recursive_mutex m;auto& mutex(){return m;}};executor& instance(){static executor e;return e;}using guard=std::lock_guard<std::recursive_mutex>;}
static int recreation=0,removed_mtp=0,last_result=-1;
static bool mount_ok=true;
namespace TWFunc {int RemoveDir(const std::string&,bool);std::string GetRootPath(const std::string&p){return p;} }
struct DataManager {
 static inline std::string list;
 static std::string GetStrValue(const std::string&){return list;}
 static std::string GetCurrentStoragePath(){return "/data";}
 static void GetValue(const std::string&,std::string&v){v=list;}
 static void GetValue(const std::string&,int&v){v=0;}
 template<class T>static void SetValue(const std::string&,const T&){}
};
void operation_start(const char*){} void operation_end(int value){last_result=value;}
struct TWPartition {
 std::string mount_point_,symlink_mount_point_,sub_partition_of_,actual_block_device_,backup_display_name_="fixture";
 bool is_sub_partition_=false,has_android_secure_=true,is_storage_=true;
 unsigned mtp_storage_id_=1;
 std::string GetMountPoint()const{return mount_point_;}
 bool Mount(bool){return mount_ok;}bool Unmount(bool){return true;}
 void FindActualBlockDevice(){}bool RecreateAndSecFolder(){++recreation;return true;}
 bool Wipe(){return WipeRmrf();}bool WipeRmrf();bool WipeAndSec();bool WipeDataCache();
};
struct TWPartitionManager {
 std::vector<TWPartition*>partitions_;
 static void RemoveMtpStorage(unsigned){++removed_mtp;}
 static bool MatchesPath(const TWPartition*,const std::string&);
 TWPartition* FindPartitionByPath(const std::string&)const;
 int WipeByPath(const std::string&)const;
 std::string GetAndroidRootPath()const{return "/system_root";}
 bool WipeAndroidSecure(){return WipeByPath("/and-sec");}
 bool FactoryReset(){return false;}bool WipeBatteryStats(){return false;}bool WipeRotateData(){return false;}
 bool WipeDalvikCache(){return false;}bool FormatData(){return false;}bool WipeMediaFromData(){return false;}
 void UpdateSystemDetails(){}
}PartitionManager;
namespace gui2_backend {
struct twrp_wipe_backend {
 std::mutex mutex_;wipe_status status_;std::atomic<bool>running_{true};
 std::chrono::steady_clock::time_point started_=std::chrono::steady_clock::now();
 void report_item(const std::string&,int,bool);void run(std::vector<std::string>);
};
}
#include "methods.inc"
static void write(const fs::path&p){std::ofstream(p)<<"keep or remove";}
int main(int argc,char**argv){
 assert(argc==2);std::string name=argv[1];
 fs::create_directory("/data");chmod("/data",0777);
 bool secure=name.starts_with("secure"),cache=name.starts_with("cache");
 bool missing=name.ends_with("missing"),denied=name.ends_with("denied"),masked=name=="remove-first-error";
 std::string target=secure?"/data/.android_secure":cache?"/data/cache":"/data";
 if(!missing){fs::create_directories(target);chmod(target.c_str(),0777);}
 if(masked){
  fs::create_directory("/data/one");fs::create_directory("/data/two");
  for(const auto&e:fs::directory_iterator("/data")){chmod(e.path().c_str(),0777);write(e.path()/"file");}
  auto first=fs::directory_iterator("/data")->path();chmod(first.c_str(),0555);
 }else if(!missing){write(fs::path(target)/"file");if(denied)chmod(target.c_str(),0555);}
 if(name=="mount-denied")mount_ok=false;
 if(name=="rm-missing")fs::remove_all("/data");
 // Drop all privilege after setting up private fixtures: EACCES is real.
 assert(setgroups(0,nullptr)==0);assert(setgid(65534)==0);assert(setuid(65534)==0);
 if(masked){int result=TWFunc::RemoveDir("/data",true);assert(result==-1);return 0;}
 TWPartition p;p.mount_point_=secure?"/and-sec":"/data";p.actual_block_device_="fixture-only";
 p.symlink_mount_point_=secure?"/data":"";
 // Secure path is the partition mount in this fixture, not an actual block mount.
 if(secure){p.mount_point_="/data";p.symlink_mount_point_="/and-sec";}
 PartitionManager.partitions_={&p};
 gui2_backend::twrp_wipe_backend backend;
 // /and-sec routes through the production manager to WipeAndSec.
 DataManager::list=(secure?"/and-sec":cache?"/cache":"/data");DataManager::list+=';';
 backend.run({"LIST"});
 bool expected=!(denied||name=="mount-denied"||name=="rm-missing");
 assert(backend.status_.state==(expected?gui2_backend::wipe_state::DONE:gui2_backend::wipe_state::FAILED));
 assert(last_result==(expected?0:1)&&!backend.running_);
 assert(backend.status_.done==(expected?1:0));
 if(!missing&&mount_ok){assert(fs::exists(fs::path(target)/"file")==denied);}
 assert(recreation==(!secure&&!cache&&expected?1:0));
 puts("PASS: removal -> partition -> manager -> wipe run terminal state");
}
