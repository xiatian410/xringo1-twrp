#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <functional>
#include <iostream>
#include <map>
#include <mutex>
#include <signal.h>
#include <string>
#include <sys/epoll.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <thread>
#include <unistd.h>
#include <vector>
#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/memory.h>
#include <android-base/properties.h>
#include <android-base/scopeguard.h>
#include <android-base/strings.h>
#include <android-base/unique_fd.h>
#include "minadbd/types.h"
#include "sideload_backend.h"
// FIXED
static std::string scenario;
static std::atomic<int> forks=0,waits=0,kills=0,unsafe_kills=0,installs=0,exit_stats=0,wait_interrupts=0,operation_result=-1;
static std::atomic<pid_t> owned=0;
static std::atomic<bool> gate=false,entered=false;
static bool mtp=true;
static std::map<std::string,int> values;
static std::mutex values_mutex;
static int failures=0;
static volatile sig_atomic_t pipe_signals=0;
static std::atomic<int> send_calls=0;
#undef CHECK
#define CHECK(x) do {if(!(x)){++failures;std::cerr<<"FAIL "<<__LINE__<<": "<<#x<<"\n";}}while(0)
#define LOGINFO(...) ((void)0)
#define LOGERR(...) ((void)0)
#define FUSE_SIDELOAD_HOST_PATHNAME "/fixture/fuse/package.zip"
#define FUSE_SIDELOAD_HOST_EXIT_PATHNAME "/fixture/fuse/exit"
constexpr int INSTALL_SUCCESS=0,INSTALL_ERROR=1,INSTALL_REBOOT=5;
struct Device {enum BuiltinAction {REBOOT_BOOTLOADER,REBOOT_FASTBOOT,REBOOT_RECOVERY,REBOOT_RESCUE,REBOOT};};
struct DataManager {
 static void SetValue(const std::string& k,int v){std::lock_guard<std::mutex> l(values_mutex);values[k]=v;}
 static void SetValue(const std::string& k,const char* v){SetValue(k,std::atoi(v));}
 static int GetIntValue(const std::string& k){std::lock_guard<std::mutex> l(values_mutex);return values[k];}
 static void GetValue(const std::string& k,int& v){v=GetIntValue(k);}
 static std::string GetStrValue(const std::string& k){return std::to_string(GetIntValue(k));}
};
namespace gui2_console {template<class... T> void info(T...){} template<class... T> void log_error(T...){} }
struct PartitionManagerFixture {bool WipeByPath(const char*){return true;}int WipeDalvikCache(){return 1;}} PartitionManager;
namespace TWFunc {bool ToggleMtp(bool enabled){bool old=mtp;mtp=enabled;if(!enabled&&scenario=="cancel-before-spawn"){entered=true;while(!gate)std::this_thread::yield();}return old;}}
static void operation_start(const char*){}
static void operation_end(int ret){operation_result=ret;}
static int TWinstall_zip(const char* path,int* wipe){++installs;*wipe=0;return scenario=="install-fail"?INSTALL_ERROR:INSTALL_SUCCESS;}
static std::vector<char*> StringVectorToNullTerminatedArray(std::vector<std::string>& v){std::vector<char*> r;for(auto& s:v)r.push_back(s.data());r.push_back(nullptr);return r;}
namespace android::base {
// Property service is absent on host. Preserve the actual call ordering.
bool SetProperty(const std::string&,const std::string& value){return !(scenario=="property-fail"&&value=="sideload");}
bool WaitForProperty(const std::string&,const std::string& value,std::chrono::milliseconds = std::chrono::milliseconds::max()){
 if(scenario=="buffered-close"&&value=="sideload"){siginfo_t info{};if(::waitid(P_PID,owned.load(),&info,WEXITED|WNOWAIT)!=0)std::abort();}
 return !(scenario=="usb-fail"&&value=="sideload");
}
std::string GetProperty(const std::string&,const std::string& fallback){return "adb";}
}
static pid_t fixture_fork(){++forks;if(scenario=="fork-fail"){errno=EAGAIN;return -1;}auto p=::fork();if(p>0)owned=p;return p;}
static int fixture_execv(const char* path,char* const args[]){if(scenario=="exec-fail"){errno=ENOENT;return -1;}if(std::string(path)!="/system/bin/minadbd")::_exit(99);return ::execv("/proc/self/exe",args);}
static int fixture_kill(pid_t p,int sig){if(p<=0||p!=owned.load()){++unsafe_kills;errno=ESRCH;return -1;}++kills;return ::kill(p,sig);}
static pid_t fixture_waitpid(pid_t p,int* status,int flags){if(p<=0||p!=owned.load()){++unsafe_kills;errno=ECHILD;return -1;}++waits;if(scenario=="wait-eintr"&&wait_interrupts++==0){errno=EINTR;return -1;}return ::waitpid(p,status,flags);}
static int fixture_stat(const char* path,struct stat* st){if(std::string(path)==FUSE_SIDELOAD_HOST_EXIT_PATHNAME){++exit_stats;return 0;}if(scenario=="fuse-missing"||scenario=="fuse-error"){errno=scenario=="fuse-missing"?ENOENT:EIO;return -1;}std::memset(st,0,sizeof(*st));return 0;}
static ssize_t fixture_send(int fd,const void* buf,size_t len,int flags){
 int call=send_calls++;
 if(scenario=="status-eintr"&&call==0){errno=EINTR;return -1;}
 if(scenario=="status-zero")return 0;
 if(scenario=="status-error"){errno=EIO;return -1;}
 return ::send(fd,buf,scenario=="status-partial"?std::min(len,size_t(2)):len,flags);
}
static unsigned fixture_sleep(unsigned){return 0;}
static int fixture_epoll_create1(int flags){if(scenario=="epoll-create-fail"){errno=EMFILE;return -1;}return ::epoll_create1(flags);}
static int fixture_epoll_ctl(int ep,int op,int fd,epoll_event* ev){if(scenario=="epoll-add-fail"){errno=EBADF;return -1;}return ::epoll_ctl(ep,op,fd,ev);}
static int fixture_epoll_wait(int ep,epoll_event* ev,int n,int ms){if(scenario=="epoll-wait-fail"){errno=EINVAL;return -1;}if(scenario=="epoll-timeout")return 0;return ::epoll_wait(ep,ev,n,3000);}
// Socketpair is an inline libbase helper; its actual socket syscall is wrapped.
extern "C" int __real_socketpair(int,int,int,int*);
extern "C" int __wrap_socketpair(int a,int b,int c,int* d){if(scenario=="socket-fail"){errno=EMFILE;return -1;}return __real_socketpair(a,b,c,d);}
#define send fixture_send
#define fork fixture_fork
#define execv fixture_execv
#define kill fixture_kill
#define waitpid fixture_waitpid
#define stat(...) fixture_stat(__VA_ARGS__)
#define sleep fixture_sleep
#define epoll_create1 fixture_epoll_create1
#define epoll_ctl fixture_epoll_ctl
#define epoll_wait fixture_epoll_wait
// CORE_HEADER
// CORE
#undef send
#undef fork
#undef execv
#undef kill
#undef waitpid
#undef stat
#undef sleep
#undef epoll_create1
#undef epoll_ctl
#undef epoll_wait
#define kill fixture_kill
#define waitpid fixture_waitpid
#define stat(...) fixture_stat(__VA_ARGS__)
#define sleep fixture_sleep
// BACKEND_HEADER
// BACKEND
#undef kill
#undef waitpid
#undef stat
#undef sleep
static void pipe_handler(int){pipe_signals=1;}
static int fixture_child(int fd){
 const char* mode=std::getenv("SIDELOAD_FIXTURE");std::string s=mode?mode:"";
 if(s=="cancel"||s=="destructor"||s=="busy"||s=="foreign-cancel"||s=="cancel-before-spawn"||s=="usb-fail"||s=="property-fail") {::usleep(500000);return 0;}
 std::string msg="COMD";uint32_t cmd=0;
 if(s=="malformed")msg="BAD!";
 if(s=="unsupported")cmd=9;
 if(s=="reboot-command")cmd=3;
 msg.append(reinterpret_cast<char*>(&cmd),4);
 if(s=="short-command"){msg.resize(5);::write(fd,msg.data(),msg.size());return 0;}
 if(s=="buffered-close"||s=="broken-status") {::write(fd,msg.data(),msg.size());::shutdown(fd,SHUT_RDWR);return 0;}
 ::write(fd,msg.data(),msg.size());char reply[8];::read(fd,reply,sizeof(reply));return 0;
}
static bool wait_until(const std::function<bool()>& fn){auto end=std::chrono::steady_clock::now()+std::chrono::seconds(4);while(!fn()){if(std::chrono::steady_clock::now()>end)return false;std::this_thread::yield();}return true;}
int main(int argc,char** argv){
 if(argc==3&&std::string(argv[1])=="--socket_fd")return fixture_child(std::atoi(argv[2]));
 scenario=argv[1];::setenv("SIDELOAD_FIXTURE",scenario.c_str(),1);::signal(SIGPIPE,pipe_handler);
 if(scenario.starts_with("status-")){
  int pair[2];CHECK(::socketpair(AF_UNIX,SOCK_STREAM,0,pair)==0);
  bool ok=WriteStatusToFd(MinadbdCommandStatus::kSuccess,pair[0]);
  CHECK(ok==(scenario=="status-eintr"||scenario=="status-partial"));::close(pair[0]);
  char bytes[9]={};ssize_t count=::read(pair[1],bytes,sizeof(bytes));CHECK(count==(ok?8:0));
  if(ok){const char expected[8]={'S','T','A','T',0,0,0,0};CHECK(std::memcmp(bytes,expected,8)==0);}
  ::close(pair[1]);
 }else if(scenario=="parser-short"||scenario=="parser-long"){
  std::string msg="COMD";uint32_t val=0;msg.append(reinterpret_cast<char*>(&val),4);if(scenario=="parser-short")msg.resize(4);else msg+="x";
  CHECK(ParseMinadbdCommand(msg)==MinadbdCommand::kError);
 }else if(scenario=="broken-status"){
  int pair[2];CHECK(::socketpair(AF_UNIX,SOCK_STREAM,0,pair)==0);::close(pair[1]);CHECK(!WriteStatusToFd(MinadbdCommandStatus::kSuccess,pair[0]));::close(pair[0]);
 }else if(scenario=="reboot-command"||scenario=="buffered-close"){
  Device::BuiltinAction action=Device::REBOOT;auto result=twrp_sideload("/",&action);
  CHECK(result==(scenario=="reboot-command"?INSTALL_REBOOT:INSTALL_SUCCESS));
  if(scenario=="reboot-command")CHECK(action==Device::REBOOT_BOOTLOADER);
 }else{
  auto backend=std::make_unique<gui2_backend::twrp_sideload_backend>();CHECK(backend->start(false,false));
  if(scenario=="cancel-before-spawn") {CHECK(wait_until([]{return entered.load();}));backend->cancel();gate=true;}
  if(scenario=="cancel"||scenario=="destructor"||scenario=="busy"||scenario=="foreign-cancel"){
   CHECK(wait_until([]{return GetMiniAdbdPid()>0;}));
   if(scenario=="foreign-cancel"){
#ifdef FIXED_CORE
    std::atomic<bool> other=true;int prior=kills;RequestMiniAdbdExit(&other);CHECK(kills==prior);CHECK(GetMiniAdbdPid()>0);
#endif
   }
   if(scenario=="busy") {CHECK(!backend->start(false,false));Device::BuiltinAction a=Device::REBOOT;
#ifdef FIXED_CORE
    CHECK(twrp_sideload("/",&a)==INSTALL_ERROR);
#endif
   }
   if(scenario=="destructor")backend.reset();else {backend->cancel();backend->cancel();}
  }
  if(backend){CHECK(wait_until([&]{return backend->status().state!=gui2_backend::sideload_state::RUNNING;}));auto state=backend->status().state;
   bool cancel=scenario=="cancel"||scenario=="cancel-before-spawn"||scenario=="busy"||scenario=="foreign-cancel";
   bool success=scenario=="install-success"||scenario=="wait-eintr"||scenario=="reuse"||scenario=="signal-preserved";
   CHECK(state==(cancel?gui2_backend::sideload_state::CANCELLED:success?gui2_backend::sideload_state::DONE:gui2_backend::sideload_state::FAILED));backend->acknowledge();CHECK(backend->status().state==gui2_backend::sideload_state::IDLE);
   if(scenario=="reuse"){CHECK(backend->start(false,false));CHECK(wait_until([&]{return backend->status().state!=gui2_backend::sideload_state::RUNNING;}));CHECK(backend->status().state==gui2_backend::sideload_state::DONE);backend->acknowledge();CHECK(installs==2);}
  }
  CHECK(mtp);
  if(scenario=="cancel-before-spawn")CHECK(forks==0);
 }
 struct sigaction disposition{};::sigaction(SIGPIPE,nullptr,&disposition);CHECK(disposition.sa_handler==pipe_handler);
 CHECK(GetMiniAdbdPid()==0);CHECK(unsafe_kills==0);CHECK(pipe_signals==0);
 if(scenario=="cancel"||scenario=="destructor")CHECK(waits==1);
 // Verify owner reaped: waitpid must find no child. Clean old-source leftovers
 // only after recording assertions; signalling is restricted to our fork PID.
 if(owned>0){int status=0;pid_t left=::waitpid(owned,&status,WNOHANG);CHECK(left==-1&&errno==ECHILD);if(left==0){::kill(owned,SIGKILL);::waitpid(owned,&status,0);}}
 std::cout<<"forks="<<forks<<" waits="<<waits<<" signals="<<kills<<" unsafe="<<unsafe_kills<<" installs="<<installs<<" failures="<<failures<<"\n";
 return failures?1:0;
}
