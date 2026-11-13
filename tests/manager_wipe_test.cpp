// Real manager deletion + backend publication; mount/MTP/metadata are fixtures.
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
#include <sys/mount.h>
#include <sys/xattr.h>
#include "wipe_backend.h"
#include "mount_backend.h"
namespace fs=std::filesystem;
#define LOGINFO(...) ((void)0)
#define LOGERR(...) ((void)0)
#define CACHE_LOGS_DIR "/cache/"
#define TW_HAS_DATA_MEDIA "media"
#define TW_EXTERNAL_PATH "external"
static bool mount_data=true,mount_cache=true,mount_sd=true;
static int mtp_removed=0,mtp_added=0,last_result=-1,completed=0,cleaned=0;
static bool recreate_case=false,already_bound=false,bind_ok=true,metadata_ok=true;
static int errors=0,mount_calls=0,bind_calls=0,metadata_calls=0,alias_mounts=0,alias_unmounts=0;
static std::string internal_path="/data/media/0";
static bool IsPathMounted(const std::string&){assert(recreate_case);return already_bound;}
static int fake_bind(const char*src,const char*dst,const char*,unsigned long flags,const void*){assert(recreate_case&&std::string(src)=="/data/media/0"&&std::string(dst)=="/sdcard"&&flags==MS_BIND);++bind_calls;if(!bind_ok){errno=EIO;return -1;}return 0;}
static std::string logdir="/data/cache/",target;
namespace gui2_console {
 template<class... T>void info(const std::string&message,T...){
  if(message=="dalvik_done"||message=="cache_dalvik_done")++completed;
  if(message=="cleaned")++cleaned;
 }
 template<class... T>void log_error(T...){++errors;}
}
namespace twrp_operation_executor {struct executor{std::recursive_mutex m;auto& mutex(){return m;}};executor& instance(){static executor e;return e;}using guard=std::lock_guard<std::recursive_mutex>;}
namespace TWFunc {
 int RemoveDir(const std::string&,bool);
 bool IsPathExists(const std::string&p){std::error_code ec;return fs::exists(p,ec);}
 std::string GetLogDir(){return logdir;}
}
struct DataManager {
 static std::string GetStrValue(const std::string&name){return name=="tw_internal_path"?internal_path:name=="tw_wipe_list"?target+";":"";}
 static std::string GetCurrentStoragePath(){return "/data/media";}
 static void GetValue(const std::string&,std::string&v){v=target+";";}
 static void GetValue(const std::string&,int&v){v=1;}
 template<class T>static void SetValue(const std::string&,const T&){}
};
void operation_start(const char*){}void operation_end(int v){last_result=v;}
int tw_set_default_metadata(const char*){++metadata_calls;return metadata_ok?0:-1;}
struct TWPartition {
 std::string mount_point_,symlink_mount_point_,symlink_path_;
 bool has_data_media_=true,is_present_=true,is_fbe_=true;
 unsigned mtp_storage_id_=1;
 std::string GetMountPoint()const{return mount_point_;}
 bool Mount(bool){++mount_calls;return mount_point_=="/sd-ext"?mount_sd:mount_data;}
 bool BindMount() const;
 void RecreateMediaFolder();
};
struct TWPartitionManager {
 TWPartition*data=nullptr,*sd=nullptr;
 TWPartition*FindPartitionByPath(const std::string&p)const{return p=="/data"?data:p=="/sd-ext"?sd:nullptr;}
 int MountByPath(const std::string&p,bool)const{++alias_mounts;return p=="/data"?mount_data:p==CACHE_LOGS_DIR?mount_cache:true;}
 bool UnmountByPath(const std::string&,bool){++alias_unmounts;return true;}
 int WipeDalvikCache()const;int WipeMediaFromData()const;
 static void RemoveMtpStorage(unsigned){++mtp_removed;}static void AddMtpStorage(unsigned){++mtp_added;}
 bool WipeAndroidSecure(){assert(false);return false;}bool FactoryReset(){assert(false);return false;}
 bool WipeBatteryStats(){assert(false);return false;}bool WipeRotateData(){assert(false);return false;}
 bool FormatData(){assert(false);return false;}bool WipeByPath(const std::string&){assert(false);return false;}
 void UpdateSystemDetails(){}
}PartitionManager;
namespace gui2_backend {
struct twrp_wipe_backend {
 std::mutex mutex_;wipe_status status_;std::atomic<bool>running_{true};
 std::chrono::steady_clock::time_point started_=std::chrono::steady_clock::now();
 void report_item(const std::string&,int,bool);void run(std::vector<std::string>);
};
}
#ifdef TEST_RECREATE
#define mount fake_bind
#endif
#include "methods.inc"
#ifdef TEST_RECREATE
#undef mount
#endif
static void dir(const fs::path&p){fs::create_directories(p);for(auto c=p;c!="/"&&!c.empty();c=c.parent_path())chmod(c.c_str(),0777);}
static void put(const fs::path&p){std::ofstream(p)<<"content";}
#ifdef TEST_RECREATE
static int test_recreate(const std::string&name){
 recreate_case=true;TWPartition data;data.mount_point_="/data";data.symlink_path_="/data/media/0";data.symlink_mount_point_="/sdcard";data.is_fbe_=name=="recreate-fbe";
 dir("/data");dir("/outside");put("/outside/keep");
 const bool existing=name=="recreate-existing"||name=="recreate-bound"||name=="recreate-bind-failed";
 if(existing)dir("/data/media/0");
 if(name=="recreate-media-file")put("/data/media");
 if(name=="recreate-media-symlink")fs::create_directory_symlink("/outside","/data/media");
 if(name=="recreate-internal-file"||name=="recreate-internal-symlink"||name=="recreate-internal-denied")dir("/data/media");
 if(name=="recreate-internal-file")put("/data/media/0");
 if(name=="recreate-internal-symlink")fs::create_directory_symlink("/outside","/data/media/0");
 if(name=="recreate-media-denied")chmod("/data",0555);
 if(name=="recreate-internal-denied")chmod("/data/media",0555);
 mount_data=name!="recreate-mount-denied";already_bound=name=="recreate-bound";
 bind_ok=name!="recreate-bind-failed";metadata_ok=name!="recreate-metadata-failed";
 assert(setgroups(0,nullptr)==0&&setgid(65534)==0&&setuid(65534)==0);
 data.RecreateMediaFolder();
 const bool ok=name=="recreate-success"||existing||name=="recreate-metadata-failed";
 assert(errors==(!ok&&name!="recreate-fbe"||!bind_ok?1:0));
 assert(mount_calls==(data.is_fbe_?0:1));
 assert(alias_mounts==0&&alias_unmounts==0);
 assert(bind_calls==(ok&&!already_bound?1:0));
 if(ok)assert(fs::is_directory("/data/media/0"));
 assert(metadata_calls==((name=="recreate-success"||name=="recreate-metadata-failed")?2:0));
 assert(fs::exists("/outside/keep"));
 puts("PASS: media directory lifecycle stops on failure, binds after readiness and never toggles parent mount");return 0;
}
#endif
int main(int argc,char**argv){
#ifdef TEST_RECREATE
 assert(argc==2);return test_recreate(argv[1]);
#else
 assert(argc==2);std::string name=argv[1];bool media=name.starts_with("media");target=media?"INTERNAL":"DALVIK";
 dir("/data");dir("/cache");dir("/sd-ext");dir("/outside");put("/outside/keep");
 TWPartition data;data.mount_point_="/data";TWPartition sd;sd.mount_point_="/sd-ext";
 PartitionManager.data=&data;PartitionManager.sd=&sd;
 bool expected=true;int expected_mtp=0;
 ino_t media_inode=0;
 if(media){
  dir("/data/media");put("/data/media/file");
  // Ordinary user.* marker, NOT a real fscrypt policy ioctl/key test.
  assert(setxattr("/data/media","user.wipe-root","marker",6,0)==0);
  struct stat st{};assert(stat("/data/media",&st)==0);media_inode=st.st_ino;
  expected_mtp=1;
  if(name=="media-legacy")data.is_fbe_=false;
  if(name=="media-delete-denied"){chmod("/data/media",0555);expected=false;}
  if(name=="media-missing"){fs::remove_all("/data/media");expected=false;expected_mtp=0;}
  if(name=="media-symlink"){fs::remove_all("/data/media");fs::create_directory_symlink("/outside","/data/media");expected=false;expected_mtp=0;}
  if(name=="media-mount-denied"){mount_data=false;expected=false;expected_mtp=0;}
  if(name=="media-unsupported"){data.has_data_media_=false;expected=false;expected_mtp=0;}
  if(name=="media-no-data"){PartitionManager.data=nullptr;expected=false;expected_mtp=0;}
 }else{
  dir("/data/dalvik-cache");put("/data/dalvik-cache/file");
  dir("/cache/dalvik-cache");put("/cache/dalvik-cache/file");dir("/cache/dc");put("/cache/dc/file");
  dir("/sd-ext/dalvik-cache");put("/sd-ext/dalvik-cache/file");
  if(name=="dalvik-cache"||name=="dalvik-cache-mount-denied")logdir=CACHE_LOGS_DIR;
  if(name=="dalvik-missing"){fs::remove_all("/data/dalvik-cache");fs::remove_all("/sd-ext/dalvik-cache");}
  if(name=="dalvik-delete-denied"){chmod("/data/dalvik-cache",0555);expected=false;}
  if(name=="dalvik-query-denied"){chmod("/data",0000);expected=false;}
  if(name=="dalvik-data-mount-denied"){mount_data=false;expected=false;}
  if(name=="dalvik-cache-mount-denied"){mount_cache=false;expected=false;}
  if(name=="dalvik-sd-mount-denied"){mount_sd=false;expected=false;}
 }
 assert(setgroups(0,nullptr)==0&&setgid(65534)==0&&setuid(65534)==0);
 gui2_backend::twrp_wipe_backend backend;backend.run({"LIST"});
 assert(last_result==(expected?0:1));assert(!backend.running_);
 assert(backend.status_.state==(expected?gui2_backend::wipe_state::DONE:gui2_backend::wipe_state::FAILED));
 assert(backend.status_.done==(expected?1:0));
 assert(fs::exists("/outside/keep"));
 if(media){
  assert(mtp_removed==expected_mtp&&mtp_added==expected_mtp);
  if(expected||name=="media-delete-denied"){
   struct stat st{};assert(stat("/data/media",&st)==0&&st.st_ino==media_inode);
   char value[8]{};assert(getxattr("/data/media","user.wipe-root",value,8)==6&&std::string(value,6)=="marker");
   assert(fs::exists("/data/media/file")==!expected);
  }
 }else{
  assert(completed==(expected?1:0));
  if(!expected)assert(cleaned==0);
  if(expected){assert(!fs::exists("/data/dalvik-cache"));assert(!fs::exists("/sd-ext/dalvik-cache"));}
  if(expected&&logdir==CACHE_LOGS_DIR)assert(!fs::exists("/cache/dc")&&!fs::exists("/cache/dalvik-cache"));
 }
 puts("PASS: manager wipe actual deletion -> backend terminal state");
#endif
}
