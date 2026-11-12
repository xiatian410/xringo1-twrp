#include <atomic>
#include <chrono>
#include <csignal>
#include <cstring>
#include <fcntl.h>
#include <iostream>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <sys/socket.h>
#include <sys/prctl.h>
#include <poll.h>
#include <sys/wait.h>
#include <thread>
#include <unistd.h>
#include <vector>
#include "MtpMessage.hpp"
#include "MtpProcess.h"
#include "TwrpMtp.hpp"
#ifndef TEMP_FAILURE_RETRY
#define TEMP_FAILURE_RETRY(exp) ({ decltype(exp) r; do {r=(exp);} while(r==-1&&errno==EINTR); r; })
#endif
#define TW_HAS_MTP
#define LOGINFO(...) ((void)0)
#define LOGERR(...) ((void)0)
#define MTPI(...) ((void)0)
#define MTPE(...) ((void)0)
#define MTPD(...) ((void)0)
static std::string scenario;
static int forks=0, state_reads=0, sets=0, signals=0;
static pid_t fixture_child=0;
extern "C" int __real_kill(pid_t,int);
static std::map<std::string,std::string> props;
static std::map<std::string,int> values;
static void require(bool ok,const char* s){if(!ok){std::cerr<<"FAIL "<<s<<std::endl;if(fixture_child>1){__real_kill(fixture_child,SIGKILL);while(waitpid(fixture_child,nullptr,0)<0&&errno==EINTR){}}std::exit(1);}}
namespace twrp_operation_executor {
using guard=std::lock_guard<std::recursive_mutex>;
struct instance_type {std::recursive_mutex m;std::recursive_mutex& mutex(){return m;}};
static instance_type& instance(){static instance_type v;return v;}
}
namespace DataManager {
int GetIntValue(const std::string& k){return values[k];}
void SetValue(const std::string& k,int v){values[k]=v;}
}
namespace TWFunc { bool WriteToFile(const std::string&,const std::string&){return true;} }
namespace gui2_console {void log_error(const std::string&){} }
namespace android::base {
std::string GetProperty(const std::string& key,const std::string& fallback){
 if(key=="sys.usb.state") {
  ++state_reads;
  const auto request=props["sys.usb.config"];
  if(request=="mtp,adb"&&forks>0) {
   if(scenario=="superseded"){props["sys.usb.config"]="fastboot";props[key]="fastboot";}
   else if(scenario=="usb-error")props[key]="error";
   else if(scenario!="startup-timeout"&&scenario!="no-ready"&&scenario!="legacy"&&state_reads>=5){props[key]="mtp,adb";props["sys.usb.ffs.mtp.ready"]="1";}
   else if(scenario=="no-ready"||scenario=="legacy")props[key]="mtp,adb";
  }
  if(request=="adb") {
   if(scenario=="adb-error"&&forks>0)props[key]="error";
   else if(scenario!="adb-timeout"||forks==0)props[key]="adb";
  }
 }
 auto i=props.find(key);return i==props.end()?fallback:i->second;
}
bool SetProperty(const std::string& k,const std::string& v){
 ++sets;
 if((scenario=="request-fail"&&k=="sys.usb.config"&&v=="mtp,adb")||
    (scenario=="adb-set-fail"&&forks>0&&k=="sys.usb.config"&&v=="adb")||
    (scenario=="ready-clear-fail"&&k=="sys.usb.ffs.mtp.ready"))return false;
 props[k]=v;
 if(k=="sys.usb.config"){state_reads=0;props["sys.usb.state"]="configuring";}
 return true;
}
}
extern "C" pid_t __real_fork();
extern "C" int __real_kill(pid_t,int);
extern "C" int __real_waitid(idtype_t,id_t,siginfo_t*,int);
extern "C" ssize_t __real_send(int,const void*,size_t,int);
extern "C" int __real_socketpair(int,int,int,int*);
extern "C" pid_t __wrap_fork(){
 if(scenario=="fork-fail"){errno=EAGAIN;return -1;}
 auto child=__real_fork();
 if(child>0){fixture_child=child;++forks;}
 return child;
}
extern "C" int __wrap_kill(pid_t pid,int sig){
 require(pid==fixture_child&&pid>1,"signal only owned unreaped child");++signals;
 if(scenario=="kill-denied"){errno=EPERM;return -1;}
 if(scenario=="stop-timeout")return 0;
 return __real_kill(pid,sig);
}
extern "C" int __wrap_waitid(idtype_t type,id_t pid,siginfo_t* info,int options){
 static bool interrupted=false;
 if(scenario=="wait-eintr"&&!interrupted){interrupted=true;errno=EINTR;return -1;}
 if(scenario=="wait-error"){errno=EIO;return -1;}
 return __real_waitid(type,pid,info,options);
}
extern "C" ssize_t __wrap_send(int fd,const void* p,size_t n,int flags){
 static bool interrupted=false;
 if(scenario=="message-eintr"&&!interrupted){interrupted=true;errno=EINTR;return -1;}
 if(scenario=="message-short")return n-1;
 return __real_send(fd,p,n,flags);
}
extern "C" int __wrap_socketpair(int domain,int type,int protocol,int* p){
 if(scenario=="socket-fail"){errno=EMFILE;return -1;}
 return __real_socketpair(domain,type,protocol,p);
}
struct TWPartition {
 bool is_storage_=true,is_present_=true,mounted=true;
 unsigned mtp_storage_id_=1;
 std::string storage_path_="/fixture/media",storage_name_="Internal",current_file_system_="f2fs";
 bool Mount(bool){return mounted;} bool IsMounted()const{return mounted;}
};
struct TWPartitionManager {
 mutable std::recursive_mutex mtp_mutex_;
 pid_t mtp_pid_=0;int mtp_write_fd=-1;std::vector<TWPartition*> partitions_;
 bool EnableMtp();bool DisableMtp();bool IsMtpEnabled()const;
 void AddAllMtpStorage()const;
 bool AddRemoveMtpStorage(const TWPartition*,int)const;
};
// PRODUCTION_METHODS
static void cleanup(TWPartitionManager& pm){
 scenario="cleanup";if(fixture_child>1){__real_kill(fixture_child,SIGKILL);while(waitpid(fixture_child,nullptr,0)<0&&errno==EINTR){}fixture_child=0;}
 if(pm.mtp_write_fd>=0)close(pm.mtp_write_fd);pm.mtp_write_fd=-1;pm.mtp_pid_=0;
}
int main(int argc,char** argv){
 require(argc==2,"arguments");scenario=argv[1];
 props={{"sys.usb.configfs","1"},{"sys.usb.config","adb"},{"sys.usb.state","adb"},{"sys.usb.ffs.mtp.ready","0"}};
 if(scenario=="parent-death"){
  require(prctl(PR_SET_CHILD_SUBREAPER,1)==0,"subreaper fixture");
  int ids[2],ready[2];require(pipe(ids)==0&&pipe(ready)==0,"fixture pipes");
  pid_t parent=__real_fork();require(parent>=0,"fixture parent fork");
  if(parent==0){close(ids[0]);close(ready[0]);android::test_server_ready_fd=ready[1];int pair[2];if(socketpair(AF_UNIX,SOCK_SEQPACKET,0,pair)!=0)_Exit(3);android::TwrpMtp mtp;pid_t child=mtp.ForkServer(pair);if(child<=1)_Exit(4);if(write(ids[1],&child,sizeof(child))!=sizeof(child))_Exit(5);for(;;)pause();}
  close(ids[1]);close(ready[1]);pollfd fd{ids[0],POLLIN,0};require(poll(&fd,1,3000)==1,"parent publishes child");pid_t child=0;require(read(ids[0],&child,sizeof(child))==sizeof(child)&&child>1,"child identity");
  fd={ready[0],POLLIN,0};require(poll(&fd,1,3000)==1,"actual child armed parent death");char byte;require(read(ready[0],&byte,1)==1,"child started server");
  require(__real_kill(parent,SIGKILL)==0,"terminate fixture parent");waitpid(parent,nullptr,0);int status=0;pid_t ended=0;for(int i=0;i<300&&ended==0;++i){ended=waitpid(child,&status,WNOHANG);if(!ended)usleep(10000);}if(ended==0){__real_kill(child,SIGKILL);waitpid(child,nullptr,0);}require(ended==child&&WIFEXITED(status)&&WEXITSTATUS(status)==1,"actual MTP child dies with parent");close(ids[0]);close(ready[0]);std::cout<<"PASS parent-death\n";return 0;
 }
 if(scenario=="legacy")props["sys.usb.configfs"]="0";
 TWPartitionManager pm;TWPartition storage;pm.partitions_={&storage};
 if(scenario.rfind("message-",0)==0){
  int p[2];require(socketpair(AF_UNIX,SOCK_SEQPACKET,0,p)==0,"message socket");pm.mtp_pid_=999;pm.mtp_write_fd=p[0];
  if(scenario=="message-peer-gone")close(p[1]);
  if(scenario=="message-path-long")storage.storage_path_=std::string(1024,'x');
  if(scenario=="message-name-long")storage.storage_name_=std::string(1024,'x');
  if(scenario=="message-id-zero")storage.mtp_storage_id_=0;
  if(scenario=="message-unmounted")storage.mounted=false;
  if(scenario=="message-vfat")storage.current_file_system_="vfat";
  bool expected=scenario=="message-add"||scenario=="message-remove"||scenario=="message-eintr"||scenario=="message-vfat";
  const int command=scenario=="message-remove"?MTP_MESSAGE_REMOVE_STORAGE:scenario=="message-unknown"?123:MTP_MESSAGE_ADD_STORAGE;
  bool result=pm.AddRemoveMtpStorage(scenario=="message-null"?nullptr:&storage,command);
  require(result==expected,"message result reflects actual send");
  if(expected){MtpMessage msg{};require(recv(p[1],&msg,sizeof(msg),0)==sizeof(msg),"atomic full message");require(msg.storage_id==1&&msg.message_type==command,"message identity");if(scenario=="message-vfat")require(msg.max_file_size==0xffffffff,"vfat size limit");}
  close(p[0]);if(scenario!="message-peer-gone")close(p[1]);pm.mtp_write_fd=-1;pm.mtp_pid_=0;
 }else if(scenario=="queue-full"){
  int p[2];require(socketpair(AF_UNIX,SOCK_SEQPACKET,0,p)==0,"queue socket");pm.mtp_pid_=999;pm.mtp_write_fd=p[0];
  int count=0;while(pm.AddRemoveMtpStorage(&storage,1)&&count<10000)++count;require(count>0&&count<10000,"bounded nonblocking queue");close(p[0]);close(p[1]);pm.mtp_pid_=0;pm.mtp_write_fd=-1;
 }else if(scenario=="read-lock-busy"){
  std::atomic<bool> locked=false,done=false;std::thread worker([&]{std::lock_guard<std::recursive_mutex> lock(pm.mtp_mutex_);locked=true;while(!done)usleep(1000);});while(!locked)usleep(1000);
  auto start=std::chrono::steady_clock::now();require(!pm.IsMtpEnabled(),"busy status unavailable");require(std::chrono::steady_clock::now()-start<std::chrono::milliseconds(50),"GUI never waits for startup");done=true;worker.join();
 }else{
  if(scenario=="child-exit")android::test_server_exit=true;
  bool ok=false;
  if(scenario=="worker-exit"){std::thread worker([&]{ok=pm.EnableMtp();});worker.join();usleep(350000);}
  else ok=pm.EnableMtp();
  bool success=scenario=="worker-exit"||scenario=="legacy"||scenario=="normal"||scenario=="repeat"||scenario=="reconnect"||scenario=="child-dies"||scenario=="ready-lost"||scenario=="wait-eintr"||scenario=="stop-timeout"||scenario=="kill-denied"||scenario=="adb-timeout"||scenario=="adb-error"||scenario=="adb-set-fail"||scenario=="externally-reaped"||scenario=="shutdown-no-fork";
  require(ok==success,"enable requires live child and acknowledged USB state");
  if(!ok){require(values["tw_mtp_enabled"]==0,"failure clears GUI enabled value");if(scenario=="wait-error"){require(pm.mtp_pid_>1&&signals==0,"wait failure retains ownership without unsafe signal");}else require(pm.mtp_pid_==0,"failure reaps child");require(props["sys.usb.config"]=="adb","failure requests ADB recovery");}
  else {
   require(pm.IsMtpEnabled(),"ready live process visible");require(values["tw_mtp_enabled"]==1,"publish only after success");
   if(scenario=="repeat"){int before=forks;require(pm.EnableMtp()&&forks==before,"repeated enable reuses acknowledged child");}
   if(scenario=="child-dies"||scenario=="externally-reaped"){
    __real_kill(fixture_child,SIGKILL);siginfo_t info{};do{require(__real_waitid(P_PID,fixture_child,&info,WEXITED|WNOHANG|WNOWAIT)==0,"observe child exit");if(!info.si_pid)usleep(1000);}while(!info.si_pid);
    require(!pm.IsMtpEnabled(),"dead child never reported enabled");
    if(scenario=="externally-reaped"){waitpid(fixture_child,nullptr,0);int before=signals;require(pm.DisableMtp()&&signals==before,"ECHILD never signals stale PID");}
   }
   if(scenario=="ready-lost"){props["sys.usb.ffs.mtp.ready"]="0";props["sys.usb.state"]="adb";scenario="startup-timeout";require(!pm.IsMtpEnabled(),"ready loss visible without stale GUI bit");scenario="ready-lost";}
   if(scenario!="externally-reaped"){
    int before=forks;bool stopped=pm.DisableMtp();bool expected=scenario!="stop-timeout"&&scenario!="kill-denied"&&scenario!="adb-timeout"&&scenario!="adb-error"&&scenario!="adb-set-fail";
    require(stopped==expected,"disable reports process and ADB recovery outcome");require(forks==before,"shutdown never launches new MTP");require(values["tw_mtp_enabled"]==0,"disabled UI state");
    if(scenario=="stop-timeout"||scenario=="kill-denied"){require(pm.mtp_pid_>1,"retain unreaped child ownership");require(!pm.EnableMtp(),"prevent overlapping generation");}
    if(scenario=="reconnect"){require(pm.EnableMtp()&&forks==before+1,"fresh generation after shutdown");require(pm.DisableMtp(),"second shutdown");}
   }
  }
  cleanup(pm);
 }
 std::cout<<"PASS "<<argv[1]<<std::endl;
}
