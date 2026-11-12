#include <cassert>
#include <cmath>
#include <cerrno>
#include <climits>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dirent.h>
#include <filesystem>
#include <fcntl.h>
#include <signal.h>
#include <string>
#include <vector>
#include <sys/wait.h>
#include <unistd.h>
#define EXPAND(x) "3"
#define RECOVERY_API_VERSION 3
#define TMP_UPDATER_BINARY_PATH "./updater"
#define TW_SIGNED_ZIP_VERIFY_VAR "verify"
#define LOGINFO(...) printf(__VA_ARGS__)
#define LOGERR(...) printf(__VA_ARGS__)
#define INSTALL_SUCCESS 0
#define INSTALL_ERROR 1
#define INSTALL_CORRUPT 2
constexpr float VERIFICATION_PROGRESS_FRACTION=0.25;
enum zip_type {UNKNOWN_ZIP_TYPE,UPDATE_BINARY_ZIP_TYPE,AB_OTA_ZIP_TYPE};
static std::string scenario;
static unsigned shown=0,sets=0;
static float fraction=0;
static int seconds=0;
struct DataManager {
  static void GetValue(const std::string&,int& v){v=scenario=="signed-progress";}
  static void ShowProgress(float f,int s){assert(std::isfinite(f) && f>=0 && f<=1 && s>=0);++shown;fraction=f;seconds=s;}
  static void SetProgress(float f,bool){assert(std::isfinite(f) && f>=0 && f<=1);++sets;fraction=f;}
};
namespace gui2_console {template<class...T>void log_error(T&&...) {}}
namespace TWFunc {int WaitForChild(pid_t,int*,const std::string&,bool=true);}
void gui_print(const char* fmt,...) {va_list ap;va_start(ap,fmt);vprintf(fmt,ap);va_end(ap);}
int abupdate_binary_command(const char*,int,int,std::vector<std::string>*){assert(false);return 1;}
extern "C" int __real_pipe(int*);
extern "C" int __wrap_pipe(int* fds) {
  if(scenario=="pipe-error") {errno=EMFILE;return -1;}return __real_pipe(fds);
}
extern "C" pid_t __real_fork();
extern "C" pid_t __wrap_fork() {
  if(scenario=="fork-error") {errno=EAGAIN;return -1;}return __real_fork();
}
extern "C" FILE* __real_fdopen(int,const char*);
extern "C" FILE* __wrap_fdopen(int fd,const char* mode) {
  if(scenario=="fdopen-error") {errno=ENOMEM;return nullptr;}return __real_fdopen(fd,mode);
}
// PRODUCTION_METHODS
static unsigned fd_count() {
  DIR* d=opendir("/proc/self/fd");assert(d);unsigned n=0;while(readdir(d))++n;closedir(d);return n;
}
int main(int argc,char** argv) {
  assert(argc==3);scenario=argv[1];bool success=std::string(argv[2])=="1";
  unsigned before=fd_count();int wipe=99;
  int result=Run_Update_Binary("./package.fixture",&wipe,scenario=="unknown-type"?UNKNOWN_ZIP_TYPE:UPDATE_BINARY_ZIP_TYPE);
  printf("result=%d wipe=%d shown=%u sets=%u fraction=%g seconds=%d\n",result,wipe,shown,sets,fraction,seconds);fflush(stdout);
  assert((result==INSTALL_SUCCESS)==success);
  assert(fd_count()==before);
  if(scenario=="normal")assert(wipe==1 && shown==1 && sets==1 && fraction==0.75f && seconds==2);
  if(scenario=="signed-progress")assert(shown==1 && sets==0 && fraction==0.375f && seconds==2);
  if(scenario=="empty" || scenario=="log-empty")assert(wipe==0);
  if(scenario=="pipe-error" || scenario=="fork-error" || scenario=="unknown-type")assert(!std::filesystem::exists("child-ran"));
  int status;errno=0;assert(waitpid(-1,&status,WNOHANG)==-1 && errno==ECHILD);
}
