// Host production caller -> real ExecCmd -> delivered ARM64 tools in private chroot.
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstdio>
#include <functional>
#include <format>
#include <filesystem>
#include <mutex>
#include <memory>
#include <unistd.h>
#include <sys/wait.h>
#include <cstring>
namespace fs=std::filesystem;
#include <string>
#include <vector>
#include <sys/stat.h>
#define LOGINFO(...) ((void)0)
#define LOGERR(...) ((void)0)
#define TW_RM_RF_VAR "rmrf"
#define TW_PERSIST_ROOT "/persist"
#define DATA_LOGS_DIR "/data/cache/"
#define TW_IS_ENCRYPTED "encrypted"
#define TW_IS_DECRYPTED "decrypted"
static bool tool_available=true,unmount_ok=true;static int command_result=0,rmrf=0,rm_calls=0,recreated=0,last_result=-1;
static std::vector<std::string>commands;
namespace gui2_console {template<class... T>void info(T...){}template<class... T>void warning(T...){}template<class... T>void log_error(T...){} }
namespace twrp_operation_executor {struct executor{std::recursive_mutex m;auto& mutex(){return m;}};executor& instance(){static executor e;return e;}using guard=std::lock_guard<std::recursive_mutex>;}
namespace android::base {bool GetBoolProperty(const char*,bool v){return v;}}
namespace TWFunc {
 bool IsPathExists(const std::string&);
 std::string GetRootPath(const std::string&);
 std::string GetLogDir(){return DATA_LOGS_DIR;}
 // Explicit block ioctl boundary; targets are newly created ordinary files.
 uint64_t GetBlockSizeByIoctl(const char* p){struct stat st{};assert(stat(p,&st)==0&&S_ISREG(st.st_mode));return st.st_size;}
 int ExecCmd(const std::string&,bool=true);
 int ExecCmd(const std::string&,std::string&,bool);
 int WaitForChild(pid_t,int*,const std::string&,bool);
 int RemoveDir(const std::string&,bool){assert(false);return -1;}
}

struct DataManager {
 static void GetValue(const std::string&,int&v){v=rmrf;}
 template<class T>static void SetValue(const std::string&,T){}
 static void OutputVersion(){}
};
int tw_get_default_metadata(const char*){return 0;}int tw_set_default_metadata(const char*){return 0;}
static void*selinux_handle=nullptr;
int selabel_lookup(void*,char**,const char*,int){assert(false);return -1;}void freecon(char*p){free(p);}
struct TWPartition {
 std::string mount_point_="/fixture",symlink_mount_point_,sub_partition_of_,current_file_system_="ext4",display_name_="fixture",actual_block_device_="/fixture/never-open",decrypted_block_device_;
 bool mount_read_only_=false,is_sub_partition_=false,can_be_wiped_=true,has_data_media_=false,use_rm_rf_=false,is_present_=true,is_storage_=false,is_fbe_=false,is_encrypted_=false,is_decrypted_=false,needs_metadata_csum_=false,needs_fs_compress_=false;
 unsigned mtp_storage_id_=1;
 std::string GetMountPoint()const{return mount_point_;}
 bool Unmount(bool){return unmount_ok;}bool Mount(bool){assert(false);return false;}
 bool IsMounted()const{return false;} // This chroot contains no mounted target.
 void FindActualBlockDevice(){}void SetupFileSystem(bool){}bool RecreateAndSecFolder(){++recreated;return true;}
 bool WipeRmrf(){++rm_calls;return true;}
 bool WipeDataWithoutWipingMedia(){assert(false);return false;}bool WipeAndSec(){assert(false);return false;}
 bool Repair();bool Wipe(const std::string&);bool WipeExtfs(const std::string&);bool WipeExt4();bool WipeFat();bool WipeExfat();bool WipeF2fs();bool WipeNtfs();
};
struct TWPartitionManager {
 std::vector<TWPartition*>partitions_;
 static bool MatchesPath(const TWPartition*,const std::string&);
 TWPartition*FindPartitionByPath(const std::string&)const;
 int WipeByPath(const std::string&,const std::string&)const;
 static std::string GetAndroidRootPath(){return "/system_root";}
 static bool RecreateLogsDir(){return true;}static void AddMtpStorage(unsigned){assert(false);}
 void UpdateSystemDetails(){}
}PartitionManager;
void operation_start(const char*){}void operation_end(int v){last_result=v;}
// Explicit GUI policy boundary: target is an allowed ordinary fixture route.
bool partition_tool_target_allowed(const std::string&p){return p=="/fixture";}
#include "methods.inc"
int main(int argc,char**argv){
 assert(argc==2);const std::string scenario=argv[1];TWPartition p;
 p.actual_block_device_="/fixtures/target.img";p.needs_metadata_csum_=true;
 p.current_file_system_=scenario.starts_with("to-ext")?"f2fs":"ext4";
 const std::string requested=scenario.starts_with("to-ext")?"ext4":"f2fs";
 if(scenario=="global-rmrf")rmrf=1;
 if(scenario=="partition-rmrf")p.use_rm_rf_=true;
 PartitionManager.partitions_={&p};
 const bool expected=scenario!="too-small"&&scenario!="missing-tool";
 const std::string previous=p.current_file_system_;
 const int result=changefilesystem("/fixture",requested);
 assert(result==(expected?0:1)&&last_result==result&&rm_calls==0);
 assert(p.current_file_system_==(expected?requested:previous));
 assert(recreated==(expected?1:0));
 if(expected){assert(p.Repair());}
 std::printf("RESULT status=%d filesystem=%s repair=%d\n",result,p.current_file_system_.c_str(),expected);
}
