// Original Wipe dispatch + format helpers + manager/backend. No actual mkfs/device.
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <cstdio>
#include <functional>
#include <format>
#include <filesystem>
#include <mutex>
#include <string>
#include <vector>
#include <sys/stat.h>
#include <unistd.h>
#define LOGINFO(...) ((void)0)
#define LOGERR(...) ((void)0)
#define TW_RM_RF_VAR "rmrf"
#define TW_PERSIST_ROOT "/persist"
#define DATA_LOGS_DIR "/data/cache/"
#define TW_IS_ENCRYPTED "encrypted"
#define TW_IS_DECRYPTED "decrypted"
static bool tool_available=true,unmount_ok=true,mounted=false,retain_mount=false;static int command_result=0,rmrf=0,rm_calls=0,recreated=0,last_result=-1;
static std::vector<std::string>commands;
namespace gui2_console {template<class... T>void info(T...){}template<class... T>void warning(T...){}template<class... T>void log_error(T...){} }
namespace twrp_operation_executor {struct executor{std::recursive_mutex m;auto& mutex(){return m;}};executor& instance(){static executor e;return e;}using guard=std::lock_guard<std::recursive_mutex>;}
namespace android::base {bool GetBoolProperty(const char*,bool v){return v;}}
namespace TWFunc {
 bool IsPathExists(const std::string&p){return tool_available&&p!="/system/bin/sload_f2fs";}
 std::string GetRootPath(const std::string&p){return p;}
 std::string GetLogDir(){return DATA_LOGS_DIR;}
 uint64_t GetBlockSizeByIoctl(const char*){return 256ULL<<20;}
 int ExecCmd(const std::string&cmd){commands.push_back(cmd);return command_result;}
 int RemoveDir(const std::string&,bool){assert(false);return -1;}
}
struct DataManager {
 static void GetValue(const std::string&,int&v){v=rmrf;}
 template<class T>static void SetValue(const std::string&,T){}
 static void OutputVersion(){}
};
int tw_get_default_metadata(const char*){return 0;}int tw_set_default_metadata(const char*){return 0;}
// The optional built-in formatter is never really invoked in host checks.
int make_ext4fs(const char*,unsigned long long,const char*,void*){commands.push_back("make_ext4fs");return -1;}
static void*selinux_handle=nullptr;
int selabel_lookup(void*,char**,const char*,int){assert(false);return -1;}void freecon(char*p){free(p);}
struct TWPartition {
 std::string mount_point_="/fixture",symlink_mount_point_,sub_partition_of_,current_file_system_="ext4",display_name_="fixture",actual_block_device_="/fixture/never-open",decrypted_block_device_;
 bool is_sub_partition_=false,can_be_wiped_=true,has_data_media_=false,use_rm_rf_=false,is_present_=true,is_storage_=false,is_fbe_=false,is_encrypted_=false,is_decrypted_=false,needs_metadata_csum_=false,needs_fs_compress_=false;
 unsigned mtp_storage_id_=1;
 std::string GetMountPoint()const{return mount_point_;}
 bool Unmount(bool){if(!unmount_ok)return false;if(!retain_mount)mounted=false;return true;}
 bool IsMounted()const{return mounted;}
 bool Mount(bool){assert(false);return false;}
 void FindActualBlockDevice(){}void SetupFileSystem(bool){}void RecreateAndSecFolder(){++recreated;}
 bool WipeRmrf(){++rm_calls;return true;}
 bool WipeDataWithoutWipingMedia(){assert(false);return false;}bool WipeAndSec(){assert(false);return false;}
 bool Wipe(const std::string&);bool WipeExtfs(const std::string&);bool WipeExt4();bool WipeFat();bool WipeExfat();bool WipeF2fs();bool WipeNtfs();
};
struct TWPartitionManager {
 std::vector<TWPartition*>partitions_;
 static bool MatchesPath(const TWPartition*,const std::string&);
 TWPartition*FindPartitionByPath(const std::string&)const;
 int WipeByPath(const std::string&,const std::string&)const;
 int MountByPath(const std::string&,bool){assert(false);return false;}
 static std::string GetAndroidRootPath(){return "/system_root";}
 static bool RecreateLogsDir(){return true;}static void AddMtpStorage(unsigned){assert(false);}
 void UpdateSystemDetails(){}
}PartitionManager;
void operation_start(const char*){}void operation_end(int v){last_result=v;}
// Explicit GUI policy boundary: target is an allowed ordinary fixture route.
bool partition_tool_target_allowed(const std::string&p){return p=="/fixture";}
#include "methods.inc"
int main(int argc,char**argv){
 assert(argc==2);std::string name=argv[1];TWPartition p;std::string requested="f2fs",prefix="/system/bin/make_f2fs";bool expected=true;bool expect_rm=false;
 if(name.starts_with("exfat")){requested="exfat";prefix="mkfs.exfat";}
 if(name.starts_with("ntfs")){requested="ntfs";prefix="/system/bin/mkntfs";}
 if(name.starts_with("fat")){requested="vfat";prefix="mkfs.fat";}
 if(name.starts_with("ext")){p.current_file_system_="f2fs";requested="ext4";prefix="mke2fs -t ext4";}
 if(name.starts_with("ext2")){requested="ext2";prefix="mke2fs -t ext2";}
 if(name.starts_with("ext3")){requested="ext3";prefix="mke2fs -t ext3";}
 if(name.ends_with("retained")){mounted=true;retain_mount=true;expected=false;}
 if(name.ends_with("mounted"))mounted=true;
 if(name=="same-rmrf-retained"){requested="ext4";rmrf=1;expect_rm=true;expected=true;}
 if(name=="from-tntfs"){p.current_file_system_="tntfs";requested="f2fs";}
 if(name=="from-mifs"){p.current_file_system_="mifs";requested="vfat";prefix="mkfs.fat";}
 if(name=="global-rmrf")rmrf=1;
 if(name=="partition-rmrf")p.use_rm_rf_=true;
 if(name=="same-rmrf"){requested="ext4";rmrf=1;expect_rm=true;}
 if(name.ends_with("missing")){tool_available=false;expected=false;}
 if(name.ends_with("fallback")){p.current_file_system_=requested;tool_available=false;expect_rm=true;}
 if(name.ends_with("failed")){command_result=-1;expected=false;}
 if(name=="unmount-denied"){unmount_ok=false;expected=false;}
 if(name=="not-present"){p.is_present_=false;expected=false;}
 if(name=="not-wipeable"){p.can_be_wiped_=false;expected=false;}
 const auto old=p.current_file_system_;PartitionManager.partitions_={&p};
 int result=changefilesystem("/fixture",requested);
 assert(result==(expected?0:1)&&last_result==result);
 assert(rm_calls==(expect_rm?1:0));
 bool executes=expected&&!expect_rm||name.ends_with("failed");
 assert(commands.size()==(executes?1u:0u));
 if(executes)assert(commands[0].starts_with(prefix));
 assert(p.current_file_system_==(expected&&!expect_rm?requested:old));
 assert(recreated==(expected&&!expect_rm?1:0));
 puts("PASS: requested format -> original helper -> manager -> backend result");
}
