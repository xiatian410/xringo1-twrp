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
#include <sys/mount.h>
#include <fstream>
#include <unistd.h>
#define LOGINFO(...) ((void)0)
#define LOGERR(...) ((void)0)
#define TW_RM_RF_VAR "rmrf"
#define TW_PERSIST_ROOT "/persist"
#define DATA_LOGS_DIR "/data/cache/"
#define TW_IS_ENCRYPTED "encrypted"
#define TW_IS_DECRYPTED "decrypted"
static bool tool_available=true,unmount_ok=true,mounted=false,retain_mount=false;static int command_result=0,rmrf=0,rm_calls=0,recreated=0,last_result=-1;
static bool persist_case=false,mount_ok=true,cleanup_unmount_ok=true,cleanup_retain=false;
static int remove_result=0,label_result=0,mount_calls=0,unmount_calls=0,delete_calls=0;
static std::string mounted_fs;
static bool andsec_case=false,fail_mkdir=false,fail_bind=false,bound=false;
static int bind_calls=0,alias_mounts=0,alias_unmounts=0;
static bool IsPathMounted(const std::string&){assert(andsec_case);return bound;}
static int test_mkdir(const char*p,mode_t mode){if(fail_mkdir){errno=EACCES;return -1;}return ::mkdir(p,mode);}
static int test_mount(const char*,const char*,const char*,unsigned long flags,const void*){assert(andsec_case&&flags==MS_BIND);++bind_calls;if(fail_bind){errno=EIO;return -1;}return 0;}
static std::vector<std::string>commands;
namespace gui2_console {template<class... T>void info(T...){}template<class... T>void warning(T...){}template<class... T>void log_error(T...){} }
namespace twrp_operation_executor {struct executor{std::recursive_mutex m;auto& mutex(){return m;}};executor& instance(){static executor e;return e;}using guard=std::lock_guard<std::recursive_mutex>;}
namespace android::base {bool GetBoolProperty(const char*,bool v){return v;}}
namespace TWFunc {
 bool IsPathExists(const std::string&p){if(andsec_case&&!p.starts_with("/system/bin/"))return std::filesystem::exists(p);return tool_available&&p!="/system/bin/sload_f2fs";}
 std::string GetRootPath(const std::string&p){return p;}
 std::string GetLogDir(){return DATA_LOGS_DIR;}
 uint64_t GetBlockSizeByIoctl(const char*){return 256ULL<<20;}
 int ExecCmd(const std::string&cmd){commands.push_back(cmd);return command_result;}
 int RemoveDir(const std::string&p,bool retain){if(andsec_case){assert(retain&&mounted);for(const auto&e:std::filesystem::directory_iterator(p))std::filesystem::remove_all(e.path());return 0;}assert(persist_case&&mounted&&p=="/persist/lost+found"&&!retain);++delete_calls;return remove_result;}
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
int selabel_lookup(void*,char**context,const char*,int){assert(persist_case);if(label_result)return label_result;*context=strdup("fixture_context");return 0;}void freecon(char*p){free(p);}
struct TWPartition {
 std::string symlink_path_,backup_display_name_="AndSec",backup_name_="and-sec";bool has_android_secure_=false;
 std::string mount_point_="/fixture",symlink_mount_point_,sub_partition_of_,current_file_system_="ext4",display_name_="fixture",actual_block_device_="/fixture/never-open",decrypted_block_device_;
 bool is_sub_partition_=false,can_be_wiped_=true,has_data_media_=false,use_rm_rf_=false,is_present_=true,is_storage_=false,is_fbe_=false,is_encrypted_=false,is_decrypted_=false,needs_metadata_csum_=false,needs_fs_compress_=false;
 unsigned mtp_storage_id_=1;
 std::string GetMountPoint()const{return mount_point_;}
 bool Unmount(bool){++unmount_calls;if(!unmount_ok)return false;if(persist_case&&unmount_calls>1){if(!cleanup_unmount_ok)return false;if(!cleanup_retain)mounted=false;}else if(!retain_mount)mounted=false;return true;}
 bool IsMounted()const{return mounted;}
 bool Mount(bool){assert(persist_case||andsec_case);++mount_calls;mounted_fs=current_file_system_;if(mount_ok)mounted=true;return mount_ok;}
 void FindActualBlockDevice(){}void SetupFileSystem(bool){}
#ifdef TEST_ANDSEC
#ifdef LEGACY_ANDSEC
 void RecreateAndSecFolder();
#else
 bool RecreateAndSecFolder();
#endif
 bool BindMount() const;bool WipeRmrf();
#else
 bool RecreateAndSecFolder(){++recreated;return true;}
 bool WipeRmrf(){++rm_calls;return true;}
#endif
 bool WipeDataWithoutWipingMedia(){assert(false);return false;}bool WipeAndSec(){assert(false);return false;}
 bool Wipe(const std::string&);bool WipeExtfs(const std::string&);bool WipeExt4();bool WipeFat();bool WipeExfat();bool WipeF2fs();bool WipeNtfs();
};
struct TWPartitionManager {
 std::vector<TWPartition*>partitions_;
 static bool MatchesPath(const TWPartition*,const std::string&);
 TWPartition*FindPartitionByPath(const std::string&)const;
 int WipeByPath(const std::string&,const std::string&)const;
 int MountByPath(const std::string&,bool){assert(andsec_case);++alias_mounts;return true;}
 int UnmountByPath(const std::string&,bool){assert(andsec_case);++alias_unmounts;return true;}
 static void RemoveMtpStorage(unsigned){}
 static std::string GetAndroidRootPath(){return "/system_root";}
 static bool RecreateLogsDir(){return true;}static void AddMtpStorage(unsigned){assert(false);}
 void UpdateSystemDetails(){}
}PartitionManager;
void operation_start(const char*){}void operation_end(int v){last_result=v;}
// Explicit GUI policy boundary: target is an allowed ordinary fixture route.
bool partition_tool_target_allowed(const std::string&p){return andsec_case||p=="/fixture"||p=="/persist";}
#ifdef TEST_ANDSEC
#define mkdir test_mkdir
#define mount test_mount
#endif
#include "methods.inc"
#ifdef TEST_ANDSEC
#undef mkdir
#undef mount
#endif
int main(int argc,char**argv){
 assert(argc==3);std::string name=argv[1];TWPartition p;std::string requested="f2fs",prefix="/system/bin/make_f2fs";bool expected=true;bool expect_rm=false;
 if(name.starts_with("exfat")){requested="exfat";prefix="mkfs.exfat";}
 if(name.starts_with("ntfs")){requested="ntfs";prefix="/system/bin/mkntfs";}
 if(name.starts_with("fat")){requested="vfat";prefix="mkfs.fat";}
 if(name.starts_with("ext")){p.current_file_system_="f2fs";requested="ext4";prefix="mke2fs -t ext4";}
 if(name.starts_with("ext2")){requested="ext2";prefix="mke2fs -t ext2";}
 if(name.starts_with("ext3")){requested="ext3";prefix="mke2fs -t ext3";}
 if(!name.contains("-persist-")&&name.ends_with("retained")){mounted=true;retain_mount=true;expected=false;}
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
#ifdef TEST_ANDSEC
 if(name.contains("-andsec-")){
   andsec_case=true;p.has_android_secure_=true;
   std::string state=name.substr(name.find("-andsec-")+8);
   std::filesystem::path dir=std::filesystem::path(argv[2])/name;std::filesystem::create_directory(dir);
   p.mount_point_=dir;p.symlink_path_=dir/".android_secure";p.symlink_mount_point_="/and-sec";
   if(name.starts_with("rmrf")){requested="ext4";rmrf=1;}
   if(name.starts_with("direct")){
     if(state=="disabled")p.has_android_secure_=false;
     if(state=="existing"||state=="bound")std::filesystem::create_directory(p.symlink_path_);
     bound=state=="bound";
     if(state=="file")std::ofstream(p.symlink_path_)<<"keep";
     if(state=="symlink")std::filesystem::create_directory_symlink(dir,p.symlink_path_);
     expected=state=="disabled"||state=="existing"||state=="bound";
#ifdef LEGACY_ANDSEC
     p.RecreateAndSecFolder();bool ok=true;
#else
     bool ok=p.RecreateAndSecFolder();
#endif
     assert(ok==expected);
     assert(bind_calls==(state=="existing"?1:0));
   }else{
     fail_mkdir=state=="mkdir-error";fail_bind=state=="bind-error";mount_ok=state!="mount-error";
     expected=state=="success";
     PartitionManager.partitions_={&p};int result=changefilesystem(dir,requested);
     assert(result==(expected?0:1)&&last_result==result);
     if(!name.starts_with("rmrf"))assert(p.current_file_system_==requested);
     assert(std::filesystem::is_directory(p.symlink_path_)==(state=="success"||state=="bind-error"));
     assert(bind_calls==(state=="success"||state=="bind-error"?1:0));
   }
   assert(alias_mounts==0&&alias_unmounts==0);
   puts("PASS: directory recreation and bind outcome -> wipe/format backend status");return 0;
 }
#endif
 if(name.contains("-persist-")){
   persist_case=true;selinux_handle=reinterpret_cast<void*>(1);p.mount_point_="/persist";
   mount_ok=name.substr(name.find("-persist-")+9)!="mount-error";remove_result=name.ends_with("delete-error")?-1:0;
   cleanup_unmount_ok=!name.ends_with("unmount-error");cleanup_retain=name.ends_with("retained");
   label_result=name.ends_with("label-error")?-1:0;
   expected=name.ends_with("success")||name.ends_with("label-error");
   PartitionManager.partitions_={&p};
   int result=changefilesystem("/persist",requested);
   assert(result==(expected?0:1)&&last_result==result);
   assert(p.current_file_system_==requested); // mkfs already succeeded, even if cleanup fails.
   const bool label_ok=label_result==0;
   assert(commands.size()==(name.ends_with("success")?2u:1u));
   assert(commands[0].starts_with(prefix));
   if(commands.size()>1)assert(commands[1].starts_with("e2fsdroid "));
   assert(mount_calls==(label_ok?1:0));
   if(mount_calls)assert(mounted_fs==requested);
   assert(delete_calls==(label_ok&&mount_ok?1:0));
   assert(unmount_calls==(label_ok&&mount_ok?2:1));
   assert(mounted==(label_ok&&mount_ok&&(!cleanup_unmount_ok||cleanup_retain)));
   assert(recreated==(expected?1:0));
   puts("PASS: mkfs -> persist temporary mount/delete/unmount -> offline label -> backend status");return 0;
 }
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
