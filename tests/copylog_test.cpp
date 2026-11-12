#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <string>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>
#include "backend/twrp_tools_backend.h"
#include "twrp_operation_executor.h"
namespace fs=std::filesystem;
#define LOGINFO(...) ((void)0)
#define LOGERR(...) ((void)0)
#define TW_BACKUPS_FOLDER_VAR "backups"
#define KLOG_SIZE_BUFFER 10
#define KLOG_READ_ALL 3
static std::string scenario,storage="/storage/usb";
static unsigned mount_calls=0,kernel_calls=0,logcat_calls=0,succeeded=0,ends=0;
static int last_status=-1;
static bool optional=true;
namespace gui2_console {
template<class... A>void log_error(A...){}
template<class... A>void info(const char*,A...){++succeeded;}
}
static void tw_set_default_metadata(const char*){}
// Do not call global sync on host; no durability assertion is made.
static void fixture_sync(){}
#define sync fixture_sync
struct Partitions {
 bool MountCurrentStorage(bool){++mount_calls;return scenario!="mount-fail";}
 void MountByPath(const std::string&,bool){}
} PartitionManager;
namespace DataManager {
static void GetValue(const char*,int&out){out=optional?1:0;}
static std::string GetCurrentStoragePath(){return storage;}
static std::string GetStrValue(const char*){return "/unused/backups";}
}
static int klogctl(int action,char*data,int){
 ++kernel_calls;
 if(scenario=="kernel-size-fail"||scenario=="both-captures-fail")return -1;
 if(action==KLOG_SIZE_BUFFER)return 64;
 if(scenario=="kernel-read-fail")return -1;
 assert(action==KLOG_READ_ALL);std::memcpy(data,"kernel-log\n",11);return 11;
}
struct TWFunc {
 static bool IsPathExists(const std::string&p){return fs::exists(p);}
 static int CopyFile(const std::string&,const std::string&,int,bool=true);
 static bool WriteToFile(const std::string&,const std::string&);
#if LOG_CAPTURE_RETURNS_BOOL
 static bool CopyKernelLog(const std::string&);
 static bool CopyLogcat(const std::string&);
#else
 static void CopyKernelLog(const std::string&);
 static void CopyLogcat(const std::string&);
#endif
 static int ExecCmd(const std::string&cmd,std::string&out,bool){
  assert(cmd=="logcat -d");++logcat_calls;out="android-log\n";
  return scenario=="logcat-capture-fail"||scenario=="both-captures-fail"?256:0;
 }
};
#include "functions.inc"
namespace gui2_backend {
static void operation_start(const std::string&s){assert(s=="Copy Log");}
static void operation_end(int code){last_status=code;++ends;}
static bool partition_tool_target_allowed(const std::string&){assert(false);return false;}
template<class... A>static int unused(A...){assert(false);return 1;}
static int repair(const std::string&s){return unused(s);}
static int resize(const std::string&s){return unused(s);}
static int changefilesystem(const std::string&a,const std::string&b){return unused(a,b);}
static int cmd(const std::string&s){return unused(s);}
static int manage_backup(const std::string&,const std::string&,const std::string&,bool){return unused();}
static int applycustomtwrpfolder(const std::string&s){return unused(s);}
static int fixabrecoverybootloop(){return unused();}
static int mergesnapshots(){return unused();}
static int disableAVB2(){return unused();}
static int refreshsizes(){return unused();}
static int fixcontexts(){return unused();}
static int unmapsuperdevices(){return unused();}
static int reflashtwrp(){return unused();}
static int repackimage(){return unused();}
bool twrp_tools_backend::details(const std::string&,partition_details*){return false;}
tool_availability twrp_tools_backend::availability(){return {};}
std::string twrp_tools_backend::twrp_folder(){return {};}
std::string twrp_tools_backend::storage_path(){return {};}
bool twrp_tools_backend::path_exists(const std::string&){return false;}
bool twrp_tools_backend::users_locked(){return false;}
#include "worker.inc"
}
static bool execute(gui2_backend::twrp_tools_backend&backend){
 assert(backend.start(gui2_backend::tool_job::COPY_LOG,"",""));
 auto end=std::chrono::steady_clock::now()+std::chrono::seconds(3);
 while(backend.status()==gui2_backend::tool_state::RUNNING){assert(std::chrono::steady_clock::now()<end);std::this_thread::yield();}
 const bool ok=backend.status()==gui2_backend::tool_state::DONE;
 backend.acknowledge();return ok;
}
static std::string read(const fs::path&p){std::ifstream f(p);return {std::istreambuf_iterator<char>(f),{}};}
int main(int argc,char**argv){
 assert(argc==2);scenario=argv[1];fs::create_directories("/tmp");fs::create_directories(storage);
 std::ofstream("/tmp/recovery.log")<<"recovery-log\n";
 if(scenario=="recovery-only")optional=false;
 if(scenario=="empty-storage")storage="";
 if(scenario=="recovery-source-missing")fs::remove("/tmp/recovery.log");
 if(scenario=="recovery-copy-fail")fs::create_directory(storage+"/recovery.log");
 if(scenario=="kernel-write-fail")fs::create_directory(storage+"/dmesg.log");
 if(scenario=="logcat-write-fail")fs::create_directory(storage+"/logcat.txt");
 if(scenario=="kernel-size-fail"||scenario=="kernel-read-fail"||scenario=="both-captures-fail")std::ofstream(storage+"/dmesg.log")<<"previous-kernel";
 if(scenario=="logcat-capture-fail"||scenario=="both-captures-fail")std::ofstream(storage+"/logcat.txt")<<"previous-logcat";
 gui2_backend::twrp_tools_backend backend;const bool ok=execute(backend);
 const bool expected=scenario=="all-success"||scenario=="recovery-only"||scenario=="reused-worker";
 assert(ok==expected);assert(last_status==(expected?0:1)&&ends==1);
 if(expected){assert(read(storage+"/recovery.log")=="recovery-log\n");if(optional){assert(read(storage+"/dmesg.log")=="kernel-log\n");assert(read(storage+"/logcat.txt")=="android-log\n");}}
 if(!optional)assert(kernel_calls==0&&logcat_calls==0);
 if(scenario=="mount-fail"||scenario=="empty-storage")assert(kernel_calls==0&&logcat_calls==0&&!fs::exists("/recovery.log"));
 if(scenario=="kernel-size-fail"||scenario=="kernel-read-fail"||scenario=="both-captures-fail")assert(read(storage+"/dmesg.log")=="previous-kernel");
 if(scenario=="logcat-capture-fail"||scenario=="both-captures-fail")assert(read(storage+"/logcat.txt")=="previous-logcat");
 if(scenario=="mount-fail"||scenario=="empty-storage")assert(succeeded==0);
 else if(scenario=="recovery-only")assert(succeeded==1);
 else {
  const bool recovery_bad=scenario=="recovery-copy-fail"||scenario=="recovery-source-missing";
  const bool kernel_bad=scenario=="kernel-size-fail"||scenario=="kernel-read-fail"||scenario=="kernel-write-fail"||scenario=="both-captures-fail";
  const bool logcat_bad=scenario=="logcat-capture-fail"||scenario=="logcat-write-fail"||scenario=="both-captures-fail";
  assert(succeeded==unsigned(3-recovery_bad-kernel_bad-logcat_bad));
  assert(kernel_calls>0&&logcat_calls==1);
  if(!kernel_bad)assert(read(storage+"/dmesg.log")=="kernel-log\n");
  if(!logcat_bad)assert(read(storage+"/logcat.txt")=="android-log\n");
 }
 if(scenario=="reused-worker"){scenario="mount-fail";assert(!execute(backend));scenario="all-success";assert(execute(backend));assert(ends==3);}
 std::printf("PASS %s status=%d mount=%u kernel=%u logcat=%u successful_exports=%u\n",argv[1],last_status,mount_calls,kernel_calls,logcat_calls,succeeded);
}
