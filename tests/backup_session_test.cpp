#include <algorithm>
#include <atomic>
#include <cassert>
#include <cerrno>
#include <csignal>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <dirent.h>
#include <filesystem>
#include <fstream>
#include <limits>
#include <map>
#include <mutex>
#include <optional>
#include <ranges>
#include <semaphore>
#include "gui2/backend/twrp_backup_backend.h"
#include <string>
#include <thread>
#include <vector>
#include <fcntl.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include <android-base/scopeguard.h>
#include "twrp_operation_executor.h"
#include "backup_manifest.hpp"
#include "variables.h"
using namespace std;
namespace fs=std::filesystem;
#define CHECK(x) do {if(!(x)){fprintf(stderr,"FAIL %d: %s\n",__LINE__,#x);exit(1);}}while(0)
#define LOGINFO(...) printf(__VA_ARGS__)
#define LOGERR(...) printf(__VA_ARGS__)
constexpr uint64_t kMiB=1024*1024;
enum {UNCOMPRESSED,COMPRESSED,ENCRYPTED,COMPRESSED_ENCRYPTED};
static fs::path root;
static string scenario;
static pid_t owner;
static atomic<pid_t> leader{0};
static atomic<int> signal_calls{0},invalid_signals{0};
static vector<string> backups,events;
static int performance=0,completed=0,digests=0,info_creates=0;
static bool mount_ok=true, measured=true,wait_interrupted=false;
static uint64_t progress_total=0;
static map<string,string> settings;
static binary_semaphore gui_entered{0},gui_release{0};
static bool gui_gate=false;
struct DataManager {
 static void GetValue(const string& k,string& v){v=settings[k];}
 template<class T>static void GetValue(const string& k,T& v){v=settings[k].empty()?0:stoull(settings[k]);}
 static void SetValue(const string& k,const string& v){settings[k]=v;}
 template<class T>static void SetValue(const string& k,T v){settings[k]=to_string(v);}
 static void SetValue(const string& k,const char* v){settings[k]=v;}
 static string GetCurrentStoragePath(){return "storage";}
 static void SetProgress(double){}
};
void event(const string&);
namespace gui2_backend {
void operation_start(const char*){if(gui_gate){gui_entered.release();gui_release.acquire();}}
void PartitionManagerLateCancel();
void operation_end(int){if(scenario=="gui-late-cancel")PartitionManagerLateCancel();}
}
namespace gui2_console {
 template<class...T>void info(const string& k,T&&...){event(k);}
 template<class...T>void log_error(const string& k,T&&...){event(k);}
 template<class...T>void highlight(const string& k,T&&...){event(k);}
}
namespace gui2_i18n {bool matches_message(const string& a,const string& b){return a==b;}}
namespace UnitConversion {
 string FormatBytes(uint64_t n){return to_string(n);}
 string FormatBytesPerSecond(uint64_t n){return to_string(n);}
}
namespace TWFunc {
 bool IsPathExists(const string& p){return fs::exists(p);}
 bool RecursiveMkdir(const string& p){error_code ec;fs::create_directories(p,ec);return !ec;}
 string GetCurrentDate(){return "fixture-date";}
 void AutoGenerateBackupName(){settings[TW_BACKUP_NAME]="fixture-auto";}
 void SetPerformanceMode(bool on){performance+=on?1:-1;}
 vector<string> SplitString(const string& s,char delim,bool skip){
  vector<string> v;size_t a=0;for(size_t b=0;b<=s.size();++b)if(b==s.size()||s[b]==delim){if(!skip||b>a)v.push_back(s.substr(a,b-a));a=b+1;}return v;
 }
 int RemoveDir(const string& p,bool){CHECK(fs::path(p).string().starts_with(root.string()+"/"));error_code ec;fs::remove_all(p,ec);return ec?-1:0;}
 int CopyFile(const string&,const string&,int){return 0;}
 int WaitForChild(pid_t p,int* status,const string&){pid_t r=waitpid(p,status,0);return r==p&&WIFEXITED(*status)&&WEXITSTATUS(*status)==0?0:-1;}
}
string gui_lookup(const char*,const char* fallback){return fallback;}
int tw_set_default_metadata(const char*){return 0;}
struct TWExclude {
 uint64_t Get_Folder_Size(const string&){return 12;}
 bool check_skip_dirs(const string&){return false;}
};
struct ProgressTracking {
 explicit ProgressTracking(uint64_t n){progress_total=n;}
 void SetSizeCount(uint64_t,uint64_t){} void UpdateSize(uint64_t){}
 void UpdateSizeCount(uint64_t,uint64_t){} void DisplayFileCount(bool){}
 void UpdateDisplayDetails(bool){}
};
enum class BackupMethod{kFiles,kDD};
enum class PartitionManagerOp{kBackup,kRestore};
struct TWPartition;
struct PartitionSettings {
 TWPartition* part=nullptr;string backup_folder;bool generate_digest=false;
 uint64_t img_bytes_remaining=0,file_bytes_remaining=0,img_bytes=0,file_bytes=0;
 int img_time=0,file_time=0;PartitionManagerOp pm_method=PartitionManagerOp::kBackup;
 ProgressTracking* progress=nullptr;
};
// CHILD_TYPE
struct TWPartition {
 string mount_point_,sub_partition_of_,backup_file_name_;
 uint64_t backup_size_=12,free_=100*kMiB;
 bool can_be_backed_up_=true,is_present_=true,is_sub_partition_=false,has_sub_partition_=false;
 BackupMethod backup_method_=BackupMethod::kFiles;
 bool Mount(bool){return mount_ok;}
 bool UpdateSize(bool,bool,bool){return measured;}
 bool Backup(PartitionSettings*,Child*);
};
struct TWPartitionManager {
 vector<TWPartition*> partitions_;atomic_bool stop_backup=false;
 // CHILD_MEMBER
 // RUN_BACKUP_DECL
 bool BackupPartition(PartitionSettings*);void CleanBackupFolder(const string&);
 bool IsBackupNameValid(const string&,bool,bool);
 int CancelBackup();int CheckBackupCancel()const;
 bool MountCurrentStorage(bool){return true;}
 void UpdateSystemDetails(){if(scenario=="session-cancel-finish"&&!backups.empty())stop_backup=true;}
 void UnmountMainPartitions(){}
 TWPartition* FindPartitionByPath(const string& p){for(auto* x:partitions_)if(x->mount_point_==p)return x;return nullptr;}
} PartitionManager;
twrp_operation_executor& twrp_operation_executor::instance(){static twrp_operation_executor o;return o;}
void event(const string& key){events.push_back(key);if(key=="backup_completed")++completed;}
bool tar_backup_for_gui(PartitionSettings*,Child*);
void write_file(const fs::path& p,const string& text){ofstream f(p);f<<text;CHECK(f.good());}
bool TWPartition::Backup(PartitionSettings* s,Child* child){
 if(scenario=="gui-destroy")return tar_backup_for_gui(s,child);
 backups.push_back(mount_point_);backup_file_name_=mount_point_+".ext4.win";
 write_file(fs::path(s->backup_folder)/(backup_file_name_+"000"),"fixture-data");
 write_file(fs::path(s->backup_folder)/(backup_file_name_+"100"),"fixture-split");
 if(scenario=="session-folder-replaced"){
  fs::rename(s->backup_folder,s->backup_folder+".moved");fs::create_directory(s->backup_folder);
  write_file(fs::path(s->backup_folder)/"sentinel","unrelated");return false;
 }
 if((scenario=="session-cancel-first"&&backups.size()==1)||(scenario=="session-cancel-last"&&mount_point_=="b"))PartitionManager.CancelBackup();
 if((scenario=="session-fail-first"&&backups.size()==1)||(scenario=="session-fail-last"&&mount_point_=="b"))return false;
 return true;
}
struct TwrpDigestDriver {
 static std::optional<std::vector<std::string>> GetBackupFiles(const std::string&);
 static bool MakeDigest(const string&){++digests;if(scenario=="session-digest-cancel")PartitionManager.CancelBackup();return scenario!="session-digest-fail";}
};
struct InfoManager {
 string file_;int file_version_=0;map<string,string> values_;
 explicit InfoManager(const string& s):file_(s){}
 struct Handle {string& value;template<class T>void operator=(T n){value=to_string(n);}};
 Handle operator[](const string& k){return {values_[k]};}
 int SaveValues();
};
bool twPersistMount(const string&){return true;}
namespace android::base {
 bool ReadFully(int fd,void* p,size_t n){size_t off=0;while(off<n){auto count=read(fd,(char*)p+off,n-off);if(count<0&&errno==EINTR)continue;if(count<=0)return false;off+=count;}return true;}
}
struct TarListStruct{string fn;unsigned thread_id;};
struct twrpTar {
 int use_encryption=0,userdata_encryption=0,use_compression=0,split_archives=0,progress_pipe_fd=-1;
 string partition_name="data",backup_folder,tarfn,tardir,password;
 PartitionSettings* part_settings=nullptr;TWExclude* backup_exclusions=nullptr;
 unsigned long long file_count=0,Total_Backup_Size=12,Archive_Current_Size=0;
 vector<TarListStruct>* ItemList=nullptr;unsigned thread_id=0;
 int createTarFork(Child*);
 static void Signal_Kill(int){_exit(255);}
 void setfn(const string& s){tarfn=s;}void setdir(const string& s){tardir=s;}
 void setsize(uint64_t n){Total_Backup_Size=n;}void setpassword(const string& s){password=s;}
 int Generate_TarList(string,vector<TarListStruct>*,unsigned long long*,unsigned*){return scenario=="tar-list-fail"?-1:1;}
 static void* createList(void*);
};
extern "C" pid_t __real_fork();
extern "C" int __real_kill(pid_t,int);
extern "C" pid_t __real_waitpid(pid_t,int*,int);
extern "C" int __real_waitid(idtype_t,id_t,siginfo_t*,int);
extern "C" int __real_mkstemp(char*);
extern "C" int __real_fsync(int);
extern "C" pid_t __wrap_fork(){
 if(scenario=="tar-fork-fail"&&getpid()==owner){errno=EAGAIN;return -1;}
 pid_t p=__real_fork();if(getpid()==owner&&p>0)leader=p;return p;
}
extern "C" int __wrap_kill(pid_t p,int s){
 if(getpid()==owner){
  if(s!=0)++signal_calls;
  pid_t l=leader.load();
  if(l<=1||(p!=l&&p!=-l)){++invalid_signals;errno=ESRCH;return -1;}
  if(p==-l&&getpgid(l)!=l){++invalid_signals;errno=ESRCH;return -1;}
 }
 return __real_kill(p,s);
}
extern "C" pid_t __wrap_waitpid(pid_t p,int* s,int flags){
 if(scenario=="tar-wait-eintr"&&getpid()==owner&&!wait_interrupted){wait_interrupted=true;errno=EINTR;return -1;}
 return __real_waitpid(p,s,flags);
}
extern "C" int __wrap_waitid(idtype_t type,id_t id,siginfo_t* info,int flags){
 if(scenario=="tar-wait-eintr"&&getpid()==owner&&!wait_interrupted){wait_interrupted=true;errno=EINTR;return -1;}
 return __real_waitid(type,id,info,flags);
}
extern "C" int __wrap_mkstemp(char* p){++info_creates;if(scenario=="tar-info-create-fail"){errno=ENOSPC;return -1;}return __real_mkstemp(p);}
extern "C" int __wrap_fsync(int fd){if(scenario=="tar-info-sync-fail"){errno=EIO;return -1;}return __real_fsync(fd);}
extern "C" void __wrap_sync(){}
void* twrpTar::createList(void* arg){
 auto* tar=(twrpTar*)arg;
 if(scenario=="tar-signal-exit")raise(SIGTERM);
 if(scenario=="tar-group-cancel"||scenario=="tar-crash-helper"){
  pid_t helper=fork();if(helper==0){write_file(root/"helper",to_string(getpid()));for(;;)pause();}
  while(!fs::exists(root/"helper"))usleep(1000);
  if(scenario=="tar-crash-helper")_exit(9);
 }
 if(scenario=="tar-no-info-before-exit"){
  close(tar->progress_pipe_fd);write_file(root/"ready","ready");
  while(!fs::exists(root/"release"))usleep(1000);
  return nullptr;
 }
 if(scenario=="tar-cancel"||scenario=="tar-repeat-cancel"||scenario=="tar-group-cancel"||scenario=="tar-cancel-mutable-name"||scenario=="gui-destroy"){
  write_file(root/"ready","ready");for(;;)pause();
 }
 uint64_t n=12;
 if(scenario=="tar-fragmented"){write(tar->progress_pipe_fd,&n,3);usleep(10000);write(tar->progress_pipe_fd,(char*)&n+3,5);}
 else if(scenario=="tar-truncated"){write(tar->progress_pipe_fd,&n,3);return nullptr;}
 else write(tar->progress_pipe_fd,&n,sizeof(n));
 n=0;write(tar->progress_pipe_fd,&n,sizeof(n));
 return scenario=="tar-child-fail"?reinterpret_cast<void*>(1):nullptr;
}
bool tar_backup_for_gui(PartitionSettings* s,Child* child){
 twrpTar tar;TWExclude exclusions;tar.part_settings=s;tar.backup_exclusions=&exclusions;
 tar.backup_folder=s->backup_folder;return tar.createTarFork(child)==0;
}
namespace gui2_backend {
void PartitionManagerLateCancel(){PartitionManager.CancelBackup();}
vector<backup_target> twrp_backup_backend::targets(){return {};}
string twrp_backup_backend::generate_name(){return {};}
string twrp_backup_backend::append_date(const string& s){return s;}
}
// PRODUCTION_METHODS
// GUI_METHODS
int main(int argc,char** argv){
 CHECK(argc==2);scenario=argv[1];root=fs::current_path();CHECK(fs::exists(root/".fixture"));owner=getpid();
 CHECK(prctl(PR_SET_CHILD_SUBREAPER,1)==0);
 fs::create_directory(root/"backups");fs::create_directory(root/"old");write_file(root/"old/sentinel","keep");
 settings[TW_BACKUPS_FOLDER_VAR]=(root/"backups").string();settings[TW_BACKUP_NAME]="fresh";
 if(scenario.starts_with("gui-")){
  using namespace gui2_backend;
  TWPartition a,storage;a.mount_point_="a";storage.mount_point_="storage";
  PartitionManager.partitions_={&a,&storage};settings["tw_backup_list"]="a;";
  auto backend=make_unique<twrp_backup_backend>();
  gui_gate=scenario=="gui-early-cancel"||scenario=="gui-double-start"||scenario=="gui-restart";
  CHECK(backend->start());
  if(gui_gate){gui_entered.acquire();
   if(scenario=="gui-double-start")CHECK(!backend->start());
   else {backend->cancel();while(!PartitionManager.stop_backup.load())usleep(1000);}
   gui_release.release();
  }
  if(scenario=="gui-destroy"){
   while(!fs::exists(root/"ready"))usleep(1000);
   backend.reset();CHECK(!fs::exists(root/"backups/fresh"));
  } else {
   while(backend->status().state==backup_state::RUNNING)usleep(1000);
   auto expected=(scenario=="gui-early-cancel"||scenario=="gui-restart")?backup_state::CANCELLED:backup_state::DONE;
   CHECK(backend->status().state==expected);
   backend->acknowledge();CHECK(backend->status().state==backup_state::IDLE);
   if(scenario=="gui-restart"){
    gui_gate=false;settings[TW_BACKUP_NAME]="second";CHECK(backend->start());
    while(backend->status().state==backup_state::RUNNING)usleep(1000);
    CHECK(backend->status().state==backup_state::DONE);CHECK(fs::exists(root/"backups/second"));
   }
  }
 } else if(scenario.starts_with("session-")){
  TWPartition a,b,storage,child;a.mount_point_="a";b.mount_point_="b";storage.mount_point_="storage";child.mount_point_="child";
  PartitionManager.partitions_={&a,&b,&storage,&child};settings["tw_backup_list"]="a;b;";
  if(scenario=="session-after-cancel"||scenario=="session-early-cancel")PartitionManager.stop_backup=true;
  if(scenario=="session-unknown-first")settings["tw_backup_list"]="missing;a;";
  if(scenario=="session-unknown-last")settings["tw_backup_list"]="a;missing;";
  if(scenario=="session-empty")settings["tw_backup_list"]="";
  if(scenario=="session-no-delimiter")settings["tw_backup_list"]="a;b";
  if(scenario=="session-duplicates")settings["tw_backup_list"]="a;a;b;b;";
  if(scenario=="session-parent-child"||scenario=="session-absent-child"){
   a.has_sub_partition_=true;child.is_sub_partition_=true;child.sub_partition_of_="a";
   if(scenario=="session-parent-child")settings["tw_backup_list"]="a;child;b;";
   else child.is_present_=false;
  }
  if(scenario=="session-absent-selected")b.is_present_=false;
  if(scenario=="session-disabled")b.can_be_backed_up_=false;
  if(scenario=="session-mount-fail")mount_ok=false;
  if(scenario=="session-size-fail")measured=false;
  if(scenario=="session-overflow"){a.backup_size_=numeric_limits<uint64_t>::max()-1;b.backup_size_=12;}
  if(scenario=="session-low-space")storage.free_=1;
  fs::path final=root/"backups/fresh";
  if(scenario=="session-existing"){fs::create_directory(final);write_file(final/"old.win","previous");}
  if(scenario=="session-symlink")fs::create_directory_symlink(root/"old",final);
  if(scenario=="session-name-dot")settings[TW_BACKUP_NAME]=".";
  if(scenario=="session-name-parent")settings[TW_BACKUP_NAME]="..";
  if(scenario=="session-encrypted-external")settings[TW_IS_ENCRYPTED]="1";
  bool ok= // RUN_BACKUP_CALL
  ;
  bool success=scenario=="session-normal"||scenario=="session-after-cancel"||scenario=="session-duplicates"||scenario=="session-parent-child"||scenario=="session-absent-child"||scenario=="session-no-delimiter"||scenario=="session-encrypted-external";
  CHECK(ok==success);CHECK(completed==(success?1:0));CHECK(performance==0);
  if(success){
   CHECK(backups==((scenario=="session-parent-child")?vector<string>{"a","child","b"}:vector<string>{"a","b"}));
   CHECK(digests==(int)backups.size());CHECK(progress_total==backups.size()*12);
   CHECK(twrp_backup_manifest::Validate(final));
   CHECK(fs::exists(final/twrp_backup_manifest::kName));
   CHECK(!fs::exists(final/twrp_backup_manifest::kTemporary));
  }
  else if(scenario=="session-existing")CHECK(fs::exists(final/"old.win"));
  else if(scenario=="session-symlink")CHECK(fs::is_symlink(final));
  else if(scenario=="session-folder-replaced")CHECK(fs::exists(final/"sentinel"));
  else CHECK(!fs::exists(final));
  CHECK(fs::exists(root/"old/sentinel"));
 } else {
  twrpTar tar;TWExclude exclusions;ProgressTracking progress(12);PartitionSettings part;
  part.progress=&progress;tar.part_settings=&part;tar.backup_exclusions=&exclusions;
  tar.backup_folder=(root/"backups/fresh").string();fs::create_directory(tar.backup_folder);
  fs::path info=fs::path(tar.backup_folder)/"data.info";
  Child* child= // CHILD_ARGUMENT
  ;
  bool cancel=scenario=="tar-cancel"||scenario=="tar-repeat-cancel"||scenario=="tar-group-cancel"||scenario=="tar-cancel-mutable-name";
  thread controller;
  if(cancel||scenario=="tar-no-info-before-exit")controller=thread([&]{
   while(!fs::exists(root/"ready"))usleep(1000);
   if(scenario=="tar-no-info-before-exit"){usleep(70000);CHECK(!fs::exists(info));write_file(root/"release","go");}
   else {if(scenario=="tar-cancel-mutable-name"){settings[TW_BACKUPS_FOLDER_VAR]=root.string();settings[TW_BACKUP_NAME]="old";}
    PartitionManager.CancelBackup();if(scenario=="tar-repeat-cancel")PartitionManager.CancelBackup();}
  });
  if(scenario=="tar-pre-cancel")PartitionManager.CancelBackup();
  int result=tar.createTarFork(child);
  if(controller.joinable())controller.join();
  bool success=scenario=="tar-normal"||scenario=="tar-after-reap"||scenario=="tar-second-session"||scenario=="tar-fragmented"||scenario=="tar-wait-eintr"||scenario=="tar-no-info-before-exit";
  CHECK((result==0)==success);CHECK(fs::exists(info)==success);
  if(scenario=="tar-fork-fail"||scenario=="tar-after-reap"){
   int prior=signal_calls.load();PartitionManager.CancelBackup();CHECK(signal_calls==prior);CHECK(invalid_signals==0);
  }
  if(scenario=="tar-second-session"){
   PartitionManager.CancelBackup();PartitionManager.stop_backup=false;CHECK(tar.createTarFork(child)==0);
  }
  CHECK(fs::exists(root/"old/sentinel"));
  if(fs::exists(root/"helper")){
   pid_t h=0;ifstream(root/"helper")>>h;int status=0;CHECK(h>1);CHECK(__real_waitpid(h,&status,0)==h);CHECK(WIFSIGNALED(status)&&WTERMSIG(status)==SIGKILL);
  }
  CHECK(invalid_signals==0);
 }
 puts("PASS");return 0;
}
