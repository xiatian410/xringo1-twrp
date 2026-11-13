// FormatData -> WipeEncryption -> metadata wipe -> backend terminal state.
// All mounts, mkfs, dmctl, hooks, properties and presentation are explicit fixtures.
#include <algorithm>
#include <atomic>
#include <cassert>
#include <chrono>
#include <filesystem>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <vector>
#include <cstdio>
#include <sys/mount.h>
#include "wipe_backend.h"
#include "mount_backend.h"
#define LOGINFO(...) ((void)0)
#define LOGERR(...) ((void)0)
#define TW_HAS_DATA_MEDIA "has_media"
#define TW_EXTERNAL_PATH "external"
#define TW_IS_ENCRYPTED "encrypted"
static std::vector<std::string> calls;
static bool pre_ok=true, post_ok=true, format_ok=true, metadata_ok=true;
static bool unmount_ok=true, force_ok=true, merge_ok=true, present=true;
static bool mapper=false, mapper_stays=false, virtual_ab=true;
static int sleeps=0, result=-1;
namespace gui2_console {
template<class... T> void info(T...) {}
template<class... T> void warning(T...) {}
template<class... T> void log_error(T...) {}
}
namespace twrp_operation_executor {
struct executor { std::recursive_mutex m; auto& mutex(){return m;} };
executor& instance(){static executor e;return e;}
using guard=std::lock_guard<std::recursive_mutex>;
}
namespace android::base {
bool GetBoolProperty(const char* name,bool){assert(std::string(name)=="ro.virtual_ab.enabled");return virtual_ab;}
}
struct DataManager {
static inline std::map<std::string,std::string> values;
static std::string GetStrValue(const std::string& k){return values[k];}
static std::string GetCurrentStoragePath(){return "/data/media";}
static void GetValue(const std::string& k,std::string& v){v=values[k];}
static void GetValue(const std::string&,int& v){v=1;}
static void SetValue(const std::string& k,const std::string& v){values[k]=v;}
static void SetValue(const std::string& k,int v){values[k]=std::to_string(v);}
};
namespace TWFunc {
std::string GetRootPath(const std::string& p){return p;}
void KillForUseTargetProcess(const std::string&){calls.push_back("kill-users");}
bool IsPathExists(const std::string& p){assert(p=="/dev/block/mapper/userdata");return mapper;}
int ExecCmd(const std::string& cmd,bool){assert(cmd=="dmctl delete userdata");calls.push_back("dmctl");if(!mapper_stays)mapper=false;return mapper_stays?1:0;}
void CheckAndRunScript(const std::string& p,const std::string&){assert(p=="/system/bin/formatdata.sh");calls.push_back("script");}
}
struct BasePartition {
virtual ~BasePartition()=default;
virtual bool PreWipeEncryption(){calls.push_back("pre");return pre_ok;}
virtual bool PostWipeEncryption(){calls.push_back("post");return post_ok;}
};
BasePartition* MakePartition(){return new BasePartition;}
static int test_umount2(const char*,int flags){assert(flags==MNT_FORCE);calls.push_back("force");return 0;}
static int test_usleep(unsigned){++sleeps;return 0;}
struct TWPartition {
std::string mount_point_,symlink_mount_point_,actual_block_device_,sub_partition_of_;
std::string display_name_="fixture",key_directory_,fstab_file_system_="f2fs",decrypted_block_device_="old-dm";
bool has_data_media_=true,is_fbe_=true,is_present_=true,is_decrypted_=true,is_encrypted_=true,is_sub_partition_=false;
unsigned mtp_storage_id_=1;
bool mounted=true;
std::string GetMountPoint()const{return mount_point_;}
void FindActualBlockDevice(){is_present_=present;}
bool Unmount(bool show){calls.push_back("unmount:"+mount_point_);if(mount_point_!="/data"|| (show?unmount_ok:force_ok)){mounted=false;return true;}return false;}
bool Mount(bool){calls.push_back("mount:"+mount_point_);mounted=true;return true;}
bool IsMounted()const{return mounted;}
bool Wipe(const std::string& fs){assert(fs==fstab_file_system_&&!has_data_media_&&!is_decrypted_&&!is_encrypted_&&decrypted_block_device_.empty());calls.push_back("format");return format_ok;}
bool Wipe(){assert(mount_point_=="/metadata");calls.push_back("metadata-wipe");return metadata_ok;}
bool WipeEncryption();
bool WipeAndSec(){assert(false);return false;}
bool WipeDataCache(){assert(false);return false;}
};
struct TWPartitionManager {
std::vector<TWPartition*> partitions_;
static std::string GetAndroidRootPath(){return "/system_root";}
static bool MatchesPath(const TWPartition*,const std::string&);
TWPartition* FindPartitionByPath(const std::string&)const;
int WipeByPath(const std::string&)const;
int FormatData();
bool CheckPendingMerges(){calls.push_back("merges");return merge_ok;}
static void AddMtpStorage(unsigned){calls.push_back("mtp");}
void UpdateSystemDetails(){calls.push_back("details");}
bool FactoryReset(){assert(false);return false;}
bool WipeBatteryStats(){assert(false);return false;}
bool WipeRotateData(){assert(false);return false;}
bool WipeDalvikCache(){assert(false);return false;}
bool WipeMediaFromData(){assert(false);return false;}
bool WipeAndroidSecure(){assert(false);return false;}
} PartitionManager;
void operation_start(const char*){calls.push_back("start");}
void operation_end(int r){result=r;calls.push_back("end");}
namespace gui2_backend {
struct twrp_wipe_backend {
std::mutex mutex_;wipe_status status_;std::atomic<bool> running_{true};
std::chrono::steady_clock::time_point started_=std::chrono::steady_clock::now();
void report_item(const std::string&,int,bool);
void run(std::vector<std::string>);
};
}
#define umount2 test_umount2
#define usleep test_usleep
#include "methods.inc"
#undef umount2
#undef usleep
static int count(const std::string& s){return std::count(calls.begin(),calls.end(),s);}
static void before(const std::string&a,const std::string&b){assert(std::find(calls.begin(),calls.end(),a)<std::find(calls.begin(),calls.end(),b));}
int main(int argc,char**argv){
 assert(argc==2);const std::string name=argv[1];
 TWPartition data,metadata;data.mount_point_="/data";data.symlink_mount_point_="/sdcard";data.actual_block_device_="fixture-data";
 data.key_directory_="/metadata/vold/metadata_encryption";metadata.mount_point_="/metadata";metadata.actual_block_device_="fixture-metadata";
 PartitionManager.partitions_={&data,&metadata};
 bool expected=true,formats=true,keys=true,post=true;
 if(name=="legacy-success"){data.is_fbe_=false;virtual_ab=false;}
 if(name=="missing-data"){PartitionManager.partitions_={&metadata};expected=formats=keys=post=false;}
 if(name=="pre-denied"){pre_ok=false;expected=formats=keys=post=false;}
 if(name=="not-present"){present=false;expected=formats=keys=post=false;}
 if(name=="unmount-denied"){unmount_ok=false;force_ok=false;expected=formats=keys=post=false;}
 if(name=="force-unmount-success")unmount_ok=false;
 if(name=="merge-denied"){merge_ok=false;expected=formats=keys=post=false;}
 if(name=="mapper-success"||name=="mapper-denied"){mapper=true;mapper_stays=name=="mapper-denied";if(mapper_stays)expected=formats=keys=post=false;}
 if(name=="format-failed"){format_ok=false;expected=keys=post=false;}
 if(name=="metadata-failed"){metadata_ok=false;expected=post=false;}
 if(name=="post-failed"){post_ok=false;expected=false;}
 if(name=="no-key-directory"){data.key_directory_.clear();keys=false;}
 gui2_backend::twrp_wipe_backend backend;backend.run({"DATAMEDIA"});
 assert(backend.status_.state==(expected?gui2_backend::wipe_state::DONE:gui2_backend::wipe_state::FAILED));
 assert(!backend.running_&&result==(expected?0:1)&&backend.status_.done==(expected?1:0));
 assert(count("format")==formats&&count("metadata-wipe")==keys&&count("post")==post&&count("script")==expected);
 assert(count("details")==1&&count("end")==1&&data.has_data_media_);
 if(formats){before("pre","format");if(keys)before("format","metadata-wipe");if(post)before(keys?"metadata-wipe":"format","post");}
 if(expected){before("post","script");before("script","details");assert(!data.is_decrypted_&&!data.is_encrypted_&&data.decrypted_block_device_.empty());assert(DataManager::values["encrypted"]=="0");}
 if(count("format"))assert(!data.is_decrypted_&&!data.is_encrypted_&&data.decrypted_block_device_.empty());
 else if(name!="missing-data")assert(data.is_decrypted_&&data.is_encrypted_&&data.decrypted_block_device_=="old-dm");
 if(name=="legacy-success")assert(count("mtp")==1);else assert(count("mtp")==0||(name=="format-failed"));
 if(name=="mapper-success")before("dmctl","format");
 assert(sleeps==0);
 for(const auto&call:calls)std::printf("%s ",call.c_str());std::puts("\nchecked_terminal_and_order=1");
}
