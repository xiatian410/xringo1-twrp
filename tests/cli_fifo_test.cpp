#include <atomic>
#include <cassert>
#include <chrono>
#include <csignal>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <mutex>
#include <string>
#include <sys/stat.h>
#include <thread>
#include <unistd.h>
#include "backend/twrp_background_backend.h"
#include "twrp_operation_executor.h"
static std::string input, output;
#define ORS_INPUT_FILE input.c_str()
#define ORS_OUTPUT_FILE output.c_str()
#define LOGINFO(...) ((void)0)
static std::atomic<int> busy{0}, executions{0};
static std::string executed;
static std::atomic<bool> hold_command{false}, command_entered{false};
static FILE* mirrored=nullptr;
void gui_set_FILE(FILE* file){mirrored=file;}
void operation_start(const char*){}
void operation_end(int){}
struct DataManager {
 static int GetIntValue(const char* name){return std::string(name)=="tw_busy"?busy.load():0;}
 static void SetValue(const char*,int){}
};
struct OpenRecoveryScript {
 static inline void(*callback)()=nullptr;
 static void Call_After_CLI_Command(void(*cb)()){callback=cb;}
 static int Run_CLI_Command(const char* text){executed=text;++executions;command_entered=true;while(hold_command.load())std::this_thread::yield();if(mirrored){
 if(std::string(text)=="saturated"){
  std::string chunk(1024,'z');for(int i=0;i<256;++i)fputs(chunk.c_str(),mirrored);
 }else fputs("fixture completed\n",mirrored);
}if(callback)callback();return 0;}
};
struct PartitionFixture {
 struct {int fd=-1;} uevent_pfd;
 void ProcessPendingUeventDevices(){}
 void RefreshPartitionListSnapshots(){}
 void ResetPendingUeventDevices(){}
 void ReadUevent(bool){}
 void ProcessAsyncDataSize(){}
 uint64_t PartitionListRevision(const std::string&){return 0;}
} PartitionManager;
#include "backend.inc"
static void tick(gui2_backend::twrp_background_backend& backend){
 auto start=std::chrono::steady_clock::now();backend.poll();
 assert(std::chrono::steady_clock::now()-start<std::chrono::milliseconds(200));
}
static void submit(const std::string& text){
 int fd=open(input.c_str(),O_WRONLY|O_NONBLOCK);assert(fd>=0);
 assert(write(fd,text.data(),text.size())==static_cast<ssize_t>(text.size()));close(fd);
}
static std::string response(gui2_backend::twrp_background_backend& backend,int reader){
 std::string result;char bytes[256];
 for(int i=0;i<200;++i){tick(backend);auto n=read(reader,bytes,sizeof(bytes));if(n>0)result.append(bytes,n);if(!result.empty()&&!backend.command_running())break;usleep(1000);}
 return result;
}
int main(int argc,char**argv){
 assert(argc==3);signal(SIGPIPE,SIG_IGN);
 input=std::string(argv[2])+"/orsin";output=std::string(argv[2])+"/orsout";
 std::string name=argv[1];gui2_backend::twrp_background_backend backend;backend.start();
 if(name.starts_with("shutdown-")){
  auto& executor=twrp_operation_executor::instance();
  if(name=="shutdown-active")hold_command=true;
  if(name=="shutdown-reserved"||name=="shutdown-rollback")assert(executor.reserve_shutdown());
  if(name=="shutdown-rollback")executor.release_shutdown();
  if(name=="shutdown-pending"){
   submit("print shutdown");tick(backend);assert(executions==0);
   assert(executor.reserve_shutdown());
  }
  int reader=open(output.c_str(),O_RDONLY|O_NONBLOCK);assert(reader>=0);
  if(name!="shutdown-pending")submit("print shutdown");
  if(name=="shutdown-active"){
   for(int i=0;i<1000&&!command_entered;++i){tick(backend);usleep(1000);}
   assert(command_entered&&!executor.reserve_shutdown());hold_command=false;
  }
  auto data=response(backend,reader);
  if(name=="shutdown-reserved"||name=="shutdown-pending"){
   assert(data=="Failed, shutdown in progress\n"&&executions==0);
  }else{
   assert(data=="fixture completed\n"&&executions==1);
   backend.stop();assert(executor.reserve_shutdown());
  }
  close(reader);puts("shutdown_cli_admission=1");
 } else if(name=="abandoned-reader"||name=="late-reader"||name=="expiry-recovery"||name=="pending-restart"){
  submit("print first");tick(backend);assert(executions==0);
  if(name=="abandoned-reader"){for(int i=0;i<100;++i)tick(backend);}
  else if(name=="pending-restart"){
   backend.stop();backend.start();
   int reader=open(output.c_str(),O_RDONLY|O_NONBLOCK);assert(reader>=0);
   for(int i=0;i<10;++i)tick(backend);assert(executions==0);
   submit("print restart");assert(response(backend,reader)=="fixture completed\n");assert(executed=="print restart");close(reader);
  } else if(name=="late-reader"){
   int reader=open(output.c_str(),O_RDONLY|O_NONBLOCK);assert(reader>=0);
   auto data=response(backend,reader);assert(data=="fixture completed\n");assert(executed=="print first");close(reader);
  } else {
   // Real monotonic timeout, no fake clock. Only this case waits for expiry.
   for(int i=0;i<530;++i){tick(backend);usleep(10000);}
   assert(executions==0);submit("print retry");
   int reader=open(output.c_str(),O_RDONLY|O_NONBLOCK);assert(reader>=0);
   assert(response(backend,reader)=="fixture completed\n");assert(executed=="print retry");close(reader);
  }
 } else {
  std::string command=name=="unsupported"?"reloadtheme":name=="max-command"?std::string(1023,'x'):name=="short-command"?"p":"print hello";
  if(name=="busy"||name=="reader-disappears")busy=1;
  int reader=open(output.c_str(),O_RDONLY|O_NONBLOCK);assert(reader>=0);
  if(name=="normal"||name=="consecutive")command.push_back('\0');
  if(name=="saturated")command="saturated";
  submit(command);
  if(name=="saturated"){
   // Keep the read end connected but never drain; worker/log writes must not
   // strand subsequent GUI polls or teardown on a full FIFO.
   for(int i=0;i<200;++i){tick(backend);if(executions&&!backend.command_running())break;usleep(1000);}
   assert(executions==1&&!backend.command_running());close(reader);
  } else if(name=="reader-disappears"){
   close(reader);tick(backend);assert(executions==0);
  } else {
   auto data=response(backend,reader);
   if(name=="busy")assert(data=="Failed, operation in progress\n"&&executions==0);
   else if(name=="unsupported")assert(data=="Failed, not supported\n"&&executions==0);
   else {assert(data=="fixture completed\n");assert(executed==std::string(command.c_str()));}
   close(reader);
   if(name=="consecutive"){
    reader=open(output.c_str(),O_RDONLY|O_NONBLOCK);assert(reader>=0);submit("print second");
    assert(response(backend,reader)=="fixture completed\n");assert(executed=="print second"&&executions==2);close(reader);
   }
  }
 }
 backend.stop();puts("PASS: bounded original poll and FIFO handshake");
}
