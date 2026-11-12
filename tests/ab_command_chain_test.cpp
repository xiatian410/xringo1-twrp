// Actual ZIP/package A/B command and child lifecycle; no update engine or block I/O.
#include <algorithm>
#include <cassert>
#include <cerrno>
#include <climits>
#include <cmath>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <inttypes.h>
#include <map>
#include <string>
#include <vector>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>
#include <android-base/parseint.h>
#include <android-base/stringprintf.h>
#include <android-base/strings.h>
#include <ziparchive/zip_archive.h>
#include "twinstall/package.h"
#include "twinstall/install.h"
using namespace std;
#define __unused __attribute__((unused))
#define PROPERTY_VALUE_MAX 92
#define LOGINFO(...) printf(__VA_ARGS__)
#define LOGERR(...) printf(__VA_ARGS__)
#define TW_SIGNED_ZIP_VERIFY_VAR "verify"
static constexpr const char* AB_OTA_PAYLOAD_PROPERTIES="payload_properties.txt";
static constexpr const char* AB_OTA_PAYLOAD="payload.bin";
static constexpr const char* METADATA_PATH="META-INF/com/android/metadata";
static string scenario;
static unsigned fork_calls=0;
static pid_t counted_fork(){++fork_calls;return ::fork();}
static unsigned progress=0;
enum zip_type {UPDATE_BINARY_ZIP_TYPE,AB_OTA_ZIP_TYPE};
struct DataManager {
 static void GetValue(const char*,int&v){v=0;}
 static void SetProgress(float f,bool){assert(isfinite(f)&&f>=0&&f<=1);++progress;}
 static void ShowProgress(float f,int s){assert(f==0.5f&&s==1);++progress;}
};
namespace gui2_console {template<class...T>void log_error(T...){} }
namespace TWFunc {int WaitForChild(pid_t,int*,const string&,bool=true);}
static void gui_print(const char*fmt,...){va_list ap;va_start(ap,fmt);vprintf(fmt,ap);va_end(ap);}
static int property_get(const char*k,char*v,const char*d){
 map<string,string>p={{"ro.product.device","dijun"},{"ro.product.model","25042PN24C"},{"ro.product.name","twrp_dijun"},{"ro.serialno","fixture"},{"ro.build.version.incremental","123"},{"ro.build.fingerprint","fixture-fingerprint"}};
 auto i=p.find(k);strcpy(v,i==p.end()?d:i->second.c_str());return strlen(v);
}
static int update_binary_command(const char*,int,int,vector<string>*){return 0;} // explicit empty-generator regression
static int harmless_execve(const char*path,char*const argv[],char*const env[]){
 assert(string(path)=="/system/bin/update_engine_sideload");
 return ::execve("/test",argv,env); // only engine executable redirected; argv remains original
}
#define fork counted_fork
#define execve harmless_execve
// PRODUCTION_METHODS
#undef execve
#undef fork
static int engine(int argc,char**argv){
 assert(argc==5);assert(string(argv[1])=="--payload=file:///packages/test.zip");
 string offset=argv[2],headers=argv[3],fd=argv[4];assert(offset.starts_with("--offset="));
 assert(headers.starts_with("--headers=FILE_HASH=fixture\nFILE_SIZE=2052\n"));
 assert(headers.ends_with("METADATA_SIZE=24\n"));assert(fd.starts_with("--status_fd="));
 ifstream f("/packages/test.zip",ios::binary);f.seekg(stoull(offset.substr(9)));string bytes(2052,'\0');f.read(bytes.data(),bytes.size());assert(f.gcount()==2052&&bytes.substr(0,4)=="CrAU");
 for(int i=4;i<2052;i++)assert((unsigned char)bytes[i]==(i-4)%256);
 ofstream("/packages/engine-entered.txt")<<"offset and bytes verified\n";
 int out=stoi(fd.substr(12));string name;ifstream("/packages/case")>>name;
 if(name=="engine-nonzero")return 7;
 dprintf(out,name=="engine-protocol-error"?"progress nan 1\n":"progress 0.5 1\nset_progress 1\nwipe_cache\n");return 0;
}
int main(int argc,char**argv){
 if(argc==5)return engine(argc,argv);
 assert(argc==3);scenario=argv[1];bool expected=string(argv[2])=="1";
 ofstream("/packages/case")<<scenario;
 vector<string> command;
 if(scenario=="command-reuse-rejection")command={"old-command"};
 if(scenario!="empty-command"){
  int r=abupdate_binary_command("/packages/test.zip",0,99,&command);
  bool valid=scenario=="stored"||scenario=="properties-deflated"||scenario=="engine-nonzero"||scenario=="engine-protocol-error";
  printf("command_result=%d size=%zu\n",r,command.size());fflush(stdout);
  assert((r==INSTALL_SUCCESS)==valid);
  if(!valid)assert(command.empty());else assert(command.size()==5&&command[0]=="/system/bin/update_engine_sideload");
 }
 int wipe=0;int r=Run_Update_Binary("/packages/test.zip",&wipe,scenario=="empty-command"?UPDATE_BINARY_ZIP_TYPE:AB_OTA_ZIP_TYPE);
 printf("run_result=%d progress=%u wipe=%d\n",r,progress,wipe);fflush(stdout);
 assert((r==INSTALL_SUCCESS)==expected);assert(progress==(expected?2u:0u));assert(wipe==int(expected));
 assert(fork_calls==unsigned(expected||scenario=="engine-nonzero"||scenario=="engine-protocol-error"));
 int status;errno=0;assert(waitpid(-1,&status,WNOHANG)==-1&&errno==ECHILD);
}
