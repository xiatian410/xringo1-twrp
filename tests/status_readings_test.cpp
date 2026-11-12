#include <cassert>
#include <atomic>
#include <charconv>
#include <chrono>
#include <ctime>
#include <filesystem>
#include <format>
#include <fstream>
#include <iostream>
#include <latch>
#include <limits>
#include <mutex>
#include <string>
#include <string_view>
#include <thread>
#include <vector>
#include "settings_store.h"
#include "status_backend.h"

namespace fs=std::filesystem;
struct BatteryInfo {bool charging; int32_t capacity;};
static constexpr int kBatteryHiddenSentinelLow=0, kBatteryHiddenSentinelHigh=101;
static std::string temperature;
static bool temperature_readable=true;
static std::atomic<int> reads=0;
static int no_temp=0, military=1;
static bool slow_read=false;
static time_t wall=1794326400;  // 2026-11-10 16:00 UTC
static time_t fixture_time(time_t*) { return wall; }
static bool conversion_failed=false;
static unsigned conversions=0;
static tm* fixture_localtime_r(const time_t* t,tm* result){
 ++conversions;
 if(conversion_failed){
  // An unsuccessful conversion cannot provide a valid tm. Defined poison
  // makes the old unchecked branch fail deterministically without relying on UB.
  *result={};result->tm_hour=99;result->tm_min=99;return nullptr;
 }
 return localtime_r(t,result);
}
struct FixtureClock {
  using time_point=std::chrono::steady_clock::time_point;
  static inline time_point current=time_point(std::chrono::seconds(1));
  static time_point now(){return current;}
};
namespace android::base {
std::string GetProperty(const std::string&, const std::string& fallback) {return fallback;}
bool ReadFileToString(const std::string& path,std::string* result) {
  assert(path=="/sys/class/thermal/thermal_zone0/temp");
  ++reads;
  if(slow_read) std::this_thread::sleep_for(std::chrono::milliseconds(2));
  if(!temperature_readable) return false;
  *result=temperature; return true;
}}
#define TW_MILITARY_TIME "tw_military_time"
struct DataManager {
 static int GetMagicValue(const std::string&,std::string&);
 static int GetValue(const std::string& key,int& value){
   if(key=="tw_no_cpu_temp") value=no_temp;
   else if(key==TW_MILITARY_TIME) value=military;
   else assert(false);
   return 0;
 }
};
namespace TWFunc {void FixupTimeOnBoot(const std::string&);}
// PRODUCTION_METHODS

struct Settings : gui2_backend::settings_store {
 std::string battery,clock="12:00"; int hidden=0;
 std::string get_string(const std::string& key,const std::string&)const override {
  return key=="tw_battery"?battery:key=="tw_time"?clock:"";
 }
 int get_int(const std::string& key,int)const override{return key=="tw_no_battery_percent"?hidden:0;}
 bool set_persistent(const std::string&,const std::string&)override{return false;}
 bool set(const std::string&,const std::string&)override{return false;}
 bool flush()override{return false;}
 bool update_timezone(bool = true)override{return true;}
 bool restore_defaults()override{return false;}
};
static void write_file(const char* name,const std::string& text){
 std::ofstream f(fs::path(TW_CUSTOM_BATTERY_PATH)/name); f<<text; assert(f.good());
}
static void battery(const std::string& cap,const std::string& state="Discharging\n"){
 write_file("capacity",cap);write_file("status",state);
}
static void temp_equals(std::string raw,const std::string& expected){
 temperature=std::move(raw); std::string result;
 assert(DataManager::GetMagicValue("tw_cpu_temp",result)==0); assert(result==expected);
}
int main(int argc,char** argv){
 assert(argc==2); const std::string test=argv[1];
 fs::remove(fs::path(TW_CUSTOM_BATTERY_PATH)/"capacity");
 fs::remove(fs::path(TW_CUSTOM_BATTERY_PATH)/"status");
 if(test=="battery-valid"){
  for(int i=1;i<=100;++i){battery(std::to_string(i)+"\n");assert(ReadLegacyBattery().capacity==i);}
  battery(" \t84\n");assert(ReadLegacyBattery().capacity==84);
 } else if(test=="battery-missing"){
  assert(ReadLegacyBattery().capacity==-1);assert(!ReadLegacyBattery().charging);
 } else if(test=="battery-malformed"){
  for(const auto& cap:{"bad\n","", "84junk\n", "84\n12\n", "84.5\n", "+84\n"}){
   battery(cap);assert(ReadLegacyBattery().capacity==-1);
  }
 } else if(test=="battery-overflow"){
  battery("999999999999999999999999999\n");assert(ReadLegacyBattery().capacity==-1);
 } else if(test=="battery-range"){
  for(const auto& cap:{"-1\n","-100\n","101\n","999\n"}){
   battery(cap);assert(ReadLegacyBattery().capacity==-1);
  }
 } else if(test=="battery-zero"){
  battery("0\n");assert(ReadLegacyBattery().capacity==0);
 } else if(test=="battery-status"){
  for(const auto& st:{"Charging\n","Discharging\n","Full\n","Not charging\n","Unknown\n","bad\n",""}){
   battery("50\n",st);auto r=ReadLegacyBattery();assert(r.capacity==50);
   assert(r.charging==(std::string(st)=="Charging\n"));
  }
 } else if(test=="battery-hotplug"){
  assert(ReadLegacyBattery().capacity==-1);
  battery("34\n","Charging\n");assert(ReadLegacyBattery().capacity==34);
  fs::remove(fs::path(TW_CUSTOM_BATTERY_PATH)/"capacity");assert(ReadLegacyBattery().capacity==-1);
  battery("35\n");assert(ReadLegacyBattery().capacity==35);
 } else if(test.starts_with("UI-")){
  Settings s;gui2_backend::status_backend backend(&s);
  if(test=="UI-valid"){
   for(int n=1;n<=100;++n) for(const auto& suffix:{"%","%+","% "}){
    s.battery=std::to_string(n)+suffix;auto r=backend.snapshot();
    assert(r.battery_valid && r.battery_percentage==n);
    assert(r.charging==(std::string(suffix)=="%+"));assert(r.time_text==s.clock);
   }
  } else if(test=="UI-zero"){
   s.battery="0%";auto r=backend.snapshot();assert(r.battery_valid&&r.battery_percentage==0);
  } else if(test=="UI-hidden"){
   s.battery="84%+";s.hidden=1;assert(!backend.snapshot().battery_valid);
   gui2_backend::status_backend empty(nullptr);assert(!empty.snapshot().battery_valid);
  } else {
   for(const auto& value:{"", "-1%", "101%", "84junk%", "84%junk", "84%++", "84%+junk", "84%%", "%", "abc%", "+84%", " 84%", "999999999999999999%"}){
    s.battery=value;auto r=backend.snapshot();assert(!r.battery_valid);assert(!r.charging);
   }
  }
 } else if(test=="temperature-positive") temp_equals("42000\n","42");
 else if(test=="temperature-negative") temp_equals("-5000\n","-5");
 else if(test=="temperature-small") temp_equals("500\n","0");
 else if(test=="temperature-malformed" || test=="temperature-overflow"){
  const std::string cap=test=="temperature-malformed"?"42000junk\n":"999999999999999999999999999\n";
  temperature=cap;std::string result="stale";assert(DataManager::GetMagicValue("tw_cpu_temp",result)==-1);assert(result.empty());
 } else if(test=="temperature-cache"){
  temp_equals("42000\n","42");temp_equals("43000\n","42");assert(reads==1);
  FixtureClock::current+=std::chrono::seconds(5);temp_equals("43000\n","43");assert(reads==2);
 } else if(test=="temperature-unavailable"){
  temp_equals("42000\n","42");temperature_readable=false;FixtureClock::current+=std::chrono::seconds(6);
  std::string r="stale";assert(DataManager::GetMagicValue("tw_cpu_temp",r)==-1);assert(r.empty());
  temperature_readable=true;FixtureClock::current+=std::chrono::seconds(6);temp_equals("44000\n","44");
 } else if(test=="temperature-disabled"){
  no_temp=1;std::string r;assert(DataManager::GetMagicValue("tw_cpu_temp",r)==-1);assert(reads==0);
 } else if(test=="clock-format"){
  setenv("TZ","CST-8",1);tzset();std::string r;
  assert(DataManager::GetMagicValue("tw_time",r)==0);assert(r=="00:00");
  military=0;assert(DataManager::GetMagicValue("tw_time",r)==0);assert(r=="12:00 AM");
  wall+=12*3600;assert(DataManager::GetMagicValue("tw_time",r)==0);assert(r=="12:00 PM");
 } else if(test=="clock-jump"){
  temp_equals("42000\n","42");wall-=3600*24*365;temp_equals("43000\n","42");
  FixtureClock::current+=std::chrono::seconds(6);temp_equals("43000\n","43");assert(reads==2);
 } else if(test=="clock-read-error"){
  wall=-1;std::string result="stale";
  assert(DataManager::GetMagicValue("tw_time",result)==-1 && result.empty());
  assert(conversions==0);
 } else if(test=="clock-conversion-error"){
  conversion_failed=true;std::string result="stale";
  assert(DataManager::GetMagicValue("tw_time",result)==-1 && result.empty());
  assert(conversions==1);
 } else if(test=="clock-error-recovery"){
  setenv("TZ","CST-8",1);tzset();std::string result="stale";
  conversion_failed=true;
  assert(DataManager::GetMagicValue("tw_time",result)==-1 && result.empty());
  conversion_failed=false;
  assert(DataManager::GetMagicValue("tw_time",result)==0 && result=="00:00");
 } else if(test=="clock-forward-backward"){
  setenv("TZ","CST-8",1);tzset();std::string result;
  const auto initial=wall;
  wall=initial+3600;assert(DataManager::GetMagicValue("tw_time",result)==0 && result=="01:00");
  wall=initial-60;assert(DataManager::GetMagicValue("tw_time",result)==0 && result=="23:59");
  wall=initial;assert(DataManager::GetMagicValue("tw_time",result)==0 && result=="00:00");
 } else if(test=="temperature-concurrent"){
  temperature="42000\n";slow_read=true;
  std::latch ready(16),start(1);std::vector<std::thread> threads;
  for(int i=0;i<16;++i) threads.emplace_back([&]{
   ready.count_down();start.wait();
   for(int j=0;j<100;++j){std::string r;assert(DataManager::GetMagicValue("tw_cpu_temp",r)==0);assert(r=="42");}
  });
  ready.wait();start.count_down();for(auto& t:threads)t.join();assert(reads==1);
 } else if(test=="rtc-policy"){
  // The production function must compile without clock/sysfs/partition shims:
  // dijun does not enable QCOM_RTC_FIX or use arbitrary persisted ATS offsets.
  for(const auto& path:{"", "/absent/rtc", "/unreadable/time", "/invalid/ats"}){
   TWFunc::FixupTimeOnBoot(path);assert(wall==1794326400);assert(reads==0);
  }
 } else assert(false);
 std::cout<<"PASS "<<test<<'\n';
}
