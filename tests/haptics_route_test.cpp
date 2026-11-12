#include <cassert>
#include <cerrno>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <string>
#include <vector>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <future>
#include <mutex>
#include <thread>
#include <fcntl.h>
#include <linux/input.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include "data.hpp"
#include "settings_store.h"
#include "backlight_controller.h"
#include "twrp_hardware_settings.h"
#include "haptics_controller.h"
#include "force_feedback.h"
#include "twrpminui/minui.h"

// PRODUCTION_VIBRATE
namespace fs=std::filesystem;
static const fs::path root=FIXTURE_ROOT;
static bool live=false,unsupported=false,name_error=false,upload_error=false,play_error=false,erase_error=false,play_short=false;
static bool short_write=false,flush_error=false,close_error=false,open_error=false;
static std::atomic<int> probe_error=0,probe_calls=0,erases=0;
static std::map<int,std::string> input_fds;
static FILE* sysfs_stream=nullptr;
static std::atomic<int> uploads=0,plays=0,closed_inputs=0;
static std::atomic<bool> gate_erase=false;
static std::mutex gate_mutex;
static std::condition_variable gate_changed;
static bool erase_entered=false,erase_released=false;
static std::vector<int> lengths;
extern "C" int __real_open(const char*,int,...);
extern "C" int __real_close(int);
extern "C" ssize_t __real_write(int,const void*,size_t);
extern "C" FILE* __real_fopen(const char*,const char*);
extern "C" size_t __real_fwrite(const void*,size_t,size_t,FILE*);
extern "C" int __real_fflush(FILE*);
extern "C" int __real_fclose(FILE*);
extern "C" int __real_access(const char*,int);
extern "C" int32_t property_get_int32(const char* key,int32_t){
 assert(std::string(key)=="ro.twrp.haptics_frequency");return 130;
}
extern "C" int __wrap_open(const char* path,int flags,...){
 mode_t mode=0;if(flags&O_CREAT){va_list ap;va_start(ap,flags);mode=va_arg(ap,int);va_end(ap);}
 int fd=__real_open(path,flags,mode);
 if(fd>=0 && std::string(path).starts_with((root/"input").string()))input_fds[fd]=path;
 return fd;
}
extern "C" int __wrap_close(int fd){if(input_fds.erase(fd))++closed_inputs;return __real_close(fd);}
extern "C" int __wrap_ioctl(int fd,unsigned long req,...){
 assert(input_fds.contains(fd));
 if(!live){errno=ENODEV;return -1;}
 va_list ap;va_start(ap,req);
 if(req==EVIOCRMFF){int id=va_arg(ap,int);va_end(ap);assert(id==7);
  ++erases;
  if(erase_error){errno=ETIME;return -1;}
  if(gate_erase){std::unique_lock lock(gate_mutex);erase_entered=true;gate_changed.notify_all();
   assert(gate_changed.wait_for(lock,std::chrono::seconds(3),[]{return erase_released;}));}
  return 0;}
 void* p=va_arg(ap,void*);va_end(ap);
 if(_IOC_NR(req)==_IOC_NR(EVIOCGNAME(1))){
  // A failed ioctl must not make a partially filled name authoritative.
  std::strcpy(static_cast<char*>(p),"cs40l26_input");
  if(name_error){errno=EIO;return -1;}return 15;
 }
 if(_IOC_NR(req)==_IOC_NR(EVIOCGBIT(EV_FF,1))){
  std::memset(p,0,_IOC_SIZE(req));auto b=static_cast<unsigned long*>(p);
  auto set=[&](int bit){b[bit/(8*sizeof(long))]|=1UL<<(bit%(8*sizeof(long)));};
  if(!unsupported){set(FF_PERIODIC);set(FF_SINE);}return _IOC_SIZE(req);
 }
 if(_IOC_NR(req)==_IOC_NR(EVIOCGBIT(0,1))){
  ++probe_calls;
  if(probe_error){errno=probe_error.load();return -1;}
  std::memset(p,0,_IOC_SIZE(req));*static_cast<unsigned long*>(p)=1UL<<EV_FF;return _IOC_SIZE(req);
 }
 if(req==EVIOCSFF){
  if(upload_error){errno=EIO;return -1;}
  auto e=static_cast<ff_effect*>(p);assert(e->type==FF_PERIODIC);
  assert(e->u.periodic.waveform==FF_SINE && e->u.periodic.period==8);
  assert(e->u.periodic.magnitude==64 && e->u.periodic.custom_len==0);
  lengths.push_back(e->replay.length);e->id=7;++uploads;return 0;
 }
 assert(false);return -1;
}
extern "C" ssize_t __wrap_write(int fd,const void* p,size_t size){
 if(input_fds.contains(fd)){
  const auto& e=*static_cast<const input_event*>(p);assert(size==sizeof(e));
  assert(e.type==EV_FF && e.code==7 && e.value==1);
  if(play_error){errno=ENODEV;return -1;}++plays;
  if(play_short)return 1;
 }
 return __real_write(fd,p,size);
}
extern "C" int __wrap_access(const char* p,int mode){return __real_access(p,mode);}
extern "C" FILE* __wrap_fopen(const char* path,const char* mode){
 const bool sysfs=std::string(path).starts_with((root/"sys").string());
 if(sysfs&&open_error){errno=EACCES;return nullptr;}
 FILE* f=__real_fopen(path,mode);if(sysfs)sysfs_stream=f;return f;
}
extern "C" size_t __wrap_fwrite(const void* p,size_t size,size_t n,FILE* f){
 if(f==sysfs_stream && short_write){errno=ENOSPC;return 0;}
 return __real_fwrite(p,size,n,f);
}
extern "C" int __wrap_fflush(FILE* f){
 if(f==sysfs_stream && flush_error){errno=EIO;return EOF;}
 return __real_fflush(f);
}
extern "C" int __wrap_fclose(FILE* f){
 bool fail=f==sysfs_stream&&close_error;int rc=__real_fclose(f);
 if(f==sysfs_stream)sysfs_stream=nullptr;
 if(fail){errno=EIO;return EOF;}return rc;
}
namespace gui2_backend {
bool backlight_controller::set_user(int){return false;}
bool backlight_controller::consume_error(){return false;}
void backlight_controller::stop(){}
}
struct Store : gui2_backend::settings_store {
 std::string get_string(const std::string& key,const std::string& fallback)const override{
  auto i=DataManager::values.find(key);return i==DataManager::values.end()?fallback:std::to_string(i->second);
 }
 int get_int(const std::string& key,int fallback)const override{
  auto i=DataManager::values.find(key);return i==DataManager::values.end()?fallback:i->second;
 }
 bool set_persistent(const std::string& key,const std::string& value)override{DataManager::values[key]=std::stoi(value);return true;}
 bool set(const std::string& key,const std::string& value)override{return set_persistent(key,value);}
 bool flush()override{return true;}
 bool update_timezone(bool = true)override{return true;}
 bool restore_defaults()override{return false;}
};
static void file(const fs::path& p,const std::string& value){std::ofstream f(p);f<<value;assert(f.good());}
static std::string read(const char* name){std::ifstream f(root/"sys"/name);return {std::istreambuf_iterator<char>(f),{}};}
static void enable_ff(){file(root/"input/event4","");live=true;}
static void enable_led(){file(root/"sys/duration","");file(root/"sys/activate","");}
template<class F> static void eventually(F f){
 const auto end=std::chrono::steady_clock::now()+std::chrono::seconds(2);
 while(!f()){assert(std::chrono::steady_clock::now()<end);std::this_thread::yield();}
}
#ifdef HAPTICS_GUI_OWNER
static void worker_io(const std::string& test,Store& store){
 using namespace std::chrono_literals;
 enable_ff();
 gui2_backend::haptics_controller c([]{return haptics_available()!=0;},
  [](int ms){return vibrate(ms)==0;},[]{twrpminui::release_force_feedback();});
 gui2_backend::twrp_hardware_settings hw(&store,nullptr,&c);
 using C=gui2_backend::haptic_channel;
 eventually([&]{return hw.has_haptics();});
 if(test=="worker-probe-eintr"||test=="worker-probe-eagain"){
  // Actual owner performs the repeated 500ms capability queries. The main
  // thread only controls atomics; it never reads worker-owned fd maps live.
  hw.vibrate(C::BUTTON);eventually([]{return plays==1;});
  const int closed=closed_inputs,queries=probe_calls;
  probe_error=test=="worker-probe-eintr"?EINTR:EAGAIN;
  eventually([&]{return probe_calls>=queries+3;});
  assert(hw.has_haptics()&&!hw.take_haptics_error());
  assert(closed_inputs==closed&&uploads==1&&plays==1&&erases==0);
  c.stop();assert(closed_inputs==closed+1);
 }else if(test=="worker-upload-failure" || test=="worker-play-failure"){
  if(test=="worker-upload-failure")upload_error=true;else play_error=true;
  hw.vibrate(C::BUTTON);eventually([&]{return hw.take_haptics_error();});
  assert(!hw.take_haptics_error());c.stop();
  assert(plays==0);assert(uploads==(test=="worker-upload-failure"?0:1));
 }else if(test=="worker-release" || test=="worker-erase-blocked"){
  hw.vibrate(C::BUTTON);eventually([]{return plays==1;});
  if(test=="worker-erase-blocked"){
   gate_erase=true;hw.vibrate(C::ACTION);
   {std::unique_lock lock(gate_mutex);assert(gate_changed.wait_for(lock,2s,[]{return erase_entered;}));}
   auto gui=std::async(std::launch::async,[&]{assert(hw.has_haptics());
    for(int n=0;n<5000;++n)hw.vibrate(C::KEYBOARD);
    assert(!hw.take_haptics_error());});
   assert(gui.wait_for(1s)==std::future_status::ready);gui.get();assert(plays==1);
   auto stopping=std::async(std::launch::async,[&]{hw.stop_haptics();});
   eventually([&]{return !c.available();});assert(stopping.wait_for(30ms)==std::future_status::timeout);
   {std::lock_guard lock(gate_mutex);erase_released=true;gate_changed.notify_all();}
   stopping.get();assert(plays==2);assert((lengths==std::vector<int>{80,160}));
  }
  c.stop();assert(!hw.take_haptics_error());
 }else assert(false);
 c.stop();assert(input_fds.empty());assert(closed_inputs>=1);
 const int closed=closed_inputs;c.stop();assert(closed_inputs==closed);
}
#endif
int main(int argc,char** argv){
 assert(argc==2);std::string test=argv[1];
 for(const auto& dir:{root/"input",root/"sys"})for(const auto& p:fs::directory_iterator(dir))fs::remove(p);
 Store store;gui2_backend::twrp_hardware_settings hardware(&store,nullptr);
 using Channel=gui2_backend::haptic_channel;
 DataManager::values={{"tw_disable_haptics",0},{"tw_button_vibrate",80},{"tw_keyboard_vibrate",40},{"tw_action_vibrate",160}};
#ifdef HAPTICS_GUI_OWNER
 if(test.starts_with("worker-")){worker_io(test,store);return 0;}
#endif
 if(test=="ff-probe-eintr"||test=="ff-probe-eagain"||test=="ff-probe-enodev"||test=="ff-probe-ebadf"){
  enable_ff();assert(vibrate(500)==0);assert(uploads==1&&plays==1&&input_fds.size()==1);
  const int closed=closed_inputs,oldcalls=probe_calls;
  probe_error=test=="ff-probe-eintr"?EINTR:test=="ff-probe-eagain"?EAGAIN:test=="ff-probe-enodev"?ENODEV:EBADF;
  if(probe_error==EINTR||probe_error==EAGAIN){
   for(int n=0;n<3;++n)assert(twrpminui::force_feedback_available());
   assert(closed_inputs==closed&&input_fds.size()==1&&uploads==1&&plays==1&&erases==0);
   assert(probe_calls-oldcalls==3); // bounded: no retry loop on a signal storm
   probe_error=0;assert(vibrate(80)==0);assert(erases==1&&uploads==2&&plays==2);
  }else{
   // A stale descriptor is closed and immediately reprobed, with no playback.
   assert(twrpminui::force_feedback_available());assert(closed_inputs==closed+1);
   assert(uploads==1&&plays==1&&erases==0);probe_error=0;
  }
  twrpminui::release_force_feedback();assert(input_fds.empty());
 }else if(test=="missing"){
  assert(!hardware.has_haptics());assert(!hardware.set_haptic_duration_ms(Channel::BUTTON,100));
  hardware.vibrate(Channel::BUTTON);assert(plays==0);
 } else if(test=="late-probe"){
  assert(!hardware.has_haptics());enable_ff();assert(hardware.has_haptics());
  hardware.vibrate(Channel::BUTTON);assert(plays==1);
 } else if(test=="unplug"){
  enable_ff();assert(hardware.has_haptics());hardware.vibrate(Channel::BUTTON);
  live=false;fs::remove(root/"input/event4");assert(!hardware.has_haptics());
  assert(!hardware.set_haptic_duration_ms(Channel::BUTTON,100));assert(DataManager::values["tw_button_vibrate"]==80);
  enable_ff();hardware.vibrate(Channel::BUTTON);assert(plays==2);
 } else if(test=="disabled"){
  enable_ff();DataManager::values["tw_disable_haptics"]=1;
  assert(!hardware.has_haptics());hardware.vibrate(Channel::BUTTON);assert(input_fds.empty()&&plays==0);
 } else if(test=="channel-durations"){
  enable_ff();for(auto c:{Channel::BUTTON,Channel::KEYBOARD,Channel::ACTION})hardware.vibrate(c);
  assert((lengths==std::vector<int>{80,40,160}));assert(plays==3);
 } else if(test=="persist-clamp"){
  enable_ff();assert(hardware.set_haptic_duration_ms(Channel::BUTTON,999));
  assert(hardware.set_haptic_duration_ms(Channel::KEYBOARD,-4));assert(hardware.set_haptic_duration_ms(Channel::ACTION,999));
  assert(DataManager::values["tw_button_vibrate"]==300);assert(DataManager::values["tw_keyboard_vibrate"]==0);
  assert(DataManager::values["tw_action_vibrate"]==500);
 } else if(test=="stored-clamp"){
  enable_ff();DataManager::values["tw_button_vibrate"]=20000;DataManager::values["tw_action_vibrate"]=20000;
  hardware.vibrate(Channel::BUTTON);hardware.vibrate(Channel::ACTION);
  assert((lengths==std::vector<int>{300,500}));
 } else if(test=="zero"){
  enable_ff();DataManager::values["tw_button_vibrate"]=0;hardware.vibrate(Channel::BUTTON);assert(plays==0);
 } else if(test=="ff-first"){
  enable_ff();enable_led();hardware.vibrate(Channel::BUTTON);
  assert(plays==1);assert(read("duration").empty()&&read("activate").empty());
 } else if(test=="missing-led-duration"){
  file(root/"sys/activate","");assert(!haptics_available());assert(vibrate(80)==-1);
  assert(!fs::exists(root/"sys/duration"));assert(read("activate").empty());
 } else if(test=="led"){
  enable_led();assert(hardware.has_haptics());hardware.vibrate(Channel::BUTTON);
  assert(read("duration")=="80"&&read("activate")=="1");assert(plays==0);
 } else if(test=="timed"){
  file(root/"sys/enable","");assert(hardware.has_haptics());hardware.vibrate(Channel::KEYBOARD);
  assert(read("enable")=="40");assert(plays==0);
 } else if(test=="write-short" || test=="flush-fail" || test=="close-fail" || test=="open-denied"){
  file(root/"sys/enable","");short_write=test=="write-short";flush_error=test=="flush-fail";
  close_error=test=="close-fail";open_error=test=="open-denied";assert(vibrate(80)==-1);assert(plays==0);
 } else if(test=="led-duration-error"){
  enable_led();short_write=true;assert(vibrate(80)==-1);assert(read("activate").empty());
 } else if(test=="ff-erase-error"){
  enable_ff();assert(vibrate(80)==0);erase_error=true;assert(vibrate(160)==-1);
  assert(input_fds.empty()&&plays==1&&uploads==1);erase_error=false;assert(vibrate(80)==0);assert(plays==2);
 } else if(test=="ff-play-short"){
  enable_ff();play_short=true;assert(vibrate(80)==-1);assert(input_fds.empty()&&plays==1);
 } else if(test=="ff-upload-error" || test=="ff-play-error"){
  enable_ff();enable_led();upload_error=test=="ff-upload-error";play_error=test=="ff-play-error";
  assert(vibrate(80)==-1);assert(read("activate").empty());assert(input_fds.empty());
  upload_error=play_error=false;assert(vibrate(80)==0);assert(plays==1);
 } else if(test=="ff-name-error" || test=="ff-unsupported"){
  enable_ff();name_error=test=="ff-name-error";unsupported=test=="ff-unsupported";
  assert(!haptics_available());assert(vibrate(80)==-1);assert(plays==0&&input_fds.empty());
 } else if(test=="timeout-bound"){
  enable_ff();assert(vibrate(20000)==0);assert(lengths.back()==10000);
  assert(vibrate(0)==-1);assert(vibrate(-1)==-1);
 } else assert(false);
 assert(uploads>=plays);
}
