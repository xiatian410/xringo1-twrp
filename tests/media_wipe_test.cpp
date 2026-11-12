// Production recursive wipe/exclusions and backend run; private ordinary files only.
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
#include "exclude.hpp"
namespace fs=std::filesystem;
#define LOGINFO(...) ((void)0)
#define TW_HAS_DATA_MEDIA "media"
#define TW_EXTERNAL_PATH "external"
static int last_result=-1,done_messages=0;
static bool mount_ok=true;
namespace gui2_console {
 template<class... T>void info(const std::string&message,T...){if(message=="done")++done_messages;}
 template<class... T>void log_error(T...){}
}
namespace twrp_operation_executor {struct executor{std::recursive_mutex m;auto& mutex(){return m;}};executor& instance(){static executor e;return e;}using guard=std::lock_guard<std::recursive_mutex>;}
namespace TWFunc {
 std::string RemoveTrailingSlashes(const std::string&,bool=false);
 std::string GetRootPath(const std::string&p){return p;}
}
struct DataManager {
 static std::string GetStrValue(const std::string&){return "/data;";}
 static std::string GetCurrentStoragePath(){return "/data";}
 static void GetValue(const std::string&,std::string&v){v="/data;";}
 static void GetValue(const std::string&,int&v){v=0;}
 template<class T>static void SetValue(const std::string&,const T&){}
};
void operation_start(const char*){}void operation_end(int v){last_result=v;}
struct TWPartition {
 TWExclude wipe_exclusions;
 std::string mount_point_="/data",symlink_mount_point_,sub_partition_of_,actual_block_device_="fixture";
 bool is_sub_partition_=false;
 std::string GetMountPoint()const{return mount_point_;}
 bool Mount(bool){return mount_ok;}bool Unmount(bool){return true;}
 void FindActualBlockDevice(){}
 // Wipe dispatch boundary: all cases use existing data-media + same-filesystem branch.
 bool Wipe(){return WipeDataWithoutWipingMedia();}
 bool WipeAndSec(){assert(false);return false;}bool WipeDataCache(){assert(false);return false;}
 bool WipeDataWithoutWipingMedia();
#if MEDIA_WIPE_RETAINED
 bool WipeDataWithoutWipingMediaFunc(const fs::path&,bool* = nullptr);
#else
 bool WipeDataWithoutWipingMediaFunc(const fs::path&);
#endif
};
struct TWPartitionManager {
 std::vector<TWPartition*>partitions_;
 static bool MatchesPath(const TWPartition*,const std::string&);
 TWPartition* FindPartitionByPath(const std::string&)const;
 int WipeByPath(const std::string&)const;
 std::string GetAndroidRootPath()const{return "/system_root";}
 bool WipeAndroidSecure(){return false;}bool FactoryReset(){return false;}bool WipeBatteryStats(){return false;}
 bool WipeRotateData(){return false;}bool WipeDalvikCache(){return false;}bool FormatData(){return false;}bool WipeMediaFromData(){return false;}
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
static void put(const fs::path&path){std::ofstream(path)<<"payload preserved or deleted";}
static void dir(const fs::path&p){
 fs::create_directories(p);
 for(auto current=p;current!="/"&&!current.empty();current=current.parent_path())chmod(current.c_str(),0777);
}
int main(int argc,char**argv){
 assert(argc==2);std::string name=argv[1];
 dir("/data");dir("/data/media");put("/data/media/photo");put("/data/delete");
 dir("/outside");put("/outside/keep");
 TWPartition partition;partition.wipe_exclusions.add_absolute_dir("/data/media/");
 bool expected=true;
 if(name=="nested-exclusion"){
  dir("/data/tree/keep");put("/data/tree/keep/file");put("/data/tree/remove");
  partition.wipe_exclusions.add_absolute_dir("/data/tree/keep");
 }
 if(name=="relative-exclusion"){
  dir("/data/tree/lost+found");put("/data/tree/lost+found/file");put("/data/tree/remove");
 }
 if(name=="symlinks"){
  fs::create_directory_symlink("/data/media","/data/media-link");
  fs::create_directory_symlink("/outside","/data/external-link");
  fs::create_symlink("/missing","/data/dangling");
 }
 if(name=="unlink-denied"){chmod("/data",0555);expected=false;}
 if(name=="open-denied"){dir("/data/blocked");put("/data/blocked/file");chmod("/data/blocked",0000);expected=false;}
 if(name=="rmdir-denied"){dir("/data/tree/empty");chmod("/data/tree",0555);expected=false;}
 if(name=="nested-unlink-denied"){
  dir("/data/tree/keep");put("/data/tree/keep/file");put("/data/tree/remove");
  partition.wipe_exclusions.add_absolute_dir("/data/tree/keep");chmod("/data/tree",0555);expected=false;
 }
 if(name=="excluded-unreadable"){chmod("/data/media",0000);}
 if(name=="mount-denied"){mount_ok=false;expected=false;}
 if(name=="missing-root"){partition.mount_point_="/missing";expected=false;}
 if(name=="workaround-directory"){dir("/data/data");put("/data/data/remove");}
 assert(setgroups(0,nullptr)==0&&setgid(65534)==0&&setuid(65534)==0);
 PartitionManager.partitions_={&partition};
 // Missing-root directly executes the production wrapper; other cases traverse manager + LIST/run.
 if(name=="missing-root"){assert(!partition.WipeDataWithoutWipingMedia());return 0;}
 gui2_backend::twrp_wipe_backend backend;backend.run({"LIST"});
 assert(last_result==(expected?0:1));
 assert(backend.status_.state==(expected?gui2_backend::wipe_state::DONE:gui2_backend::wipe_state::FAILED));
 assert(backend.status_.done==(expected?1:0)&&!backend.running_);
 assert(done_messages==(expected?1:0));
 assert(fs::exists("/outside/keep"));
 if(name!="excluded-unreadable")assert(fs::exists("/data/media/photo"));
 if(expected){
  assert(!fs::exists("/data/delete"));
  if(name=="nested-exclusion")assert(fs::exists("/data/tree/keep/file")&&!fs::exists("/data/tree/remove"));
  if(name=="relative-exclusion")assert(fs::exists("/data/tree/lost+found/file")&&!fs::exists("/data/tree/remove"));
  if(name=="symlinks")for(auto path:{"/data/media-link","/data/external-link","/data/dangling"})assert(fs::symlink_status(path).type()==fs::file_type::not_found);
  if(name=="workaround-directory"){
#ifdef TW_WORKAROUND_BACKUP_BUG
   assert(fs::is_directory("/data/data"));
#else
   assert(!fs::exists("/data/data"));
#endif
  }
 }
 puts("PASS: media preserved; removal result -> manager -> backend terminal state");
}
