#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <map>
#include <mutex>
#include <semaphore>
#include <string>
#include <thread>
#include <vector>
#include "data.hpp"
#include "variables.h"
#include "twrp_operation.h"
#include "twrpperf/perf_manager.hpp"
#include "backup_backend.h"
#include "restore_backend.h"
#include "install_backend.h"
#include "backlight_controller.h"

static std::atomic<int64_t> monotonic_ns{0};
static std::atomic<time_t> wall_seconds{1000};
namespace std::chrono {
steady_clock::time_point steady_clock::now() noexcept {
  return time_point(duration(monotonic_ns.load()));
}
}
extern "C" time_t __wrap_time(time_t* out) {
  const auto t=wall_seconds.load(); if(out)*out=t; return t;
}
static void advance(int64_t ms, int64_t wall_delta=0) {
  monotonic_ns+=ms*1000000; wall_seconds+=wall_delta ? wall_delta : ms/1000;
}
static std::mutex fixture_mutex;
static std::map<std::string,std::string> values;
static std::vector<int> vibrations;
static std::vector<std::string> properties;
static int begins=0, ends=0;
void DataManager::SetValue(const std::string& key,int value) {SetValue(key,std::to_string(value));}
void DataManager::SetValue(const std::string& key,const std::string& value) {
  std::lock_guard lock(fixture_mutex);values[key]=value;
}
void DataManager::GetValue(const std::string& key,std::string& value) {
  std::lock_guard lock(fixture_mutex);value=values[key];
}
void DataManager::GetValue(const std::string& key,int& value) {
  std::string s;GetValue(key,s);value=s.empty()?0:std::stoi(s);
}
static int value(const std::string& key) {int v;DataManager::GetValue(key,v);return v;}
int DataManager::GetIntValue(const std::string& key) {return value(key);}
static bool device_present=true;
int haptics_available() {return device_present;}
namespace gui2_backend {
bool backlight_controller::set_user(int) {assert(false);return false;}
bool backlight_controller::consume_error() {assert(false);return false;}
void backlight_controller::stop() {assert(false);}
}
int vibrate(int ms) {std::lock_guard lock(fixture_mutex);vibrations.push_back(ms);return 0;}
int property_set(const char* key,const char* val) {
  assert(std::string(key) == "twrp.action_complete");
  std::lock_guard lock(fixture_mutex);properties.emplace_back(val);return 0;
}
twrp::TwrpPerfManager& twrp::TwrpPerfManager::Get() {static TwrpPerfManager p;return p;}
void twrp::TwrpPerfManager::BeginWorkload() {std::lock_guard lock(fixture_mutex);++begins;}
void twrp::TwrpPerfManager::EndWorkload() {std::lock_guard lock(fixture_mutex);++ends;}
namespace gui2_console {
template<class... Args> void info(const char*,Args&&...) {}
template<class... Args> void log_error(const char*,Args&&...) {}
}
namespace gui2_i18n {bool matches_message(const char*,const std::string&) {return false;}}
static std::string gui_lookup(const char*,const char* fallback) {return fallback;}
namespace TWFunc {void SetPerformanceMode(bool) {}}
static bool job_ok=true,cancel_backup=false,name_ok=true;
static int job_calls=0, fail_zip=-1;
struct PartitionManagerFixture {
  std::atomic<bool> stop_backup{false};
  bool IsBackupNameValid(const std::string&,bool,bool) {return name_ok;}
  bool RunBackup(bool = true) {++job_calls;advance(12000);stop_backup=cancel_backup;return job_ok && !cancel_backup;}
  bool RunRestore(const std::string& path) {assert(path=="/fixture/backup");++job_calls;advance(12000);return job_ok;}
  void InvalidateAsyncDataSize() {}
  void UpdateSystemDetails(bool) {}
  bool WipeByPath(const char*) {assert(false);return false;}
} PartitionManager;
namespace gui2_backend {
struct twrp_screen_backend {
  uint64_t last_tick_ms_=0;int wakes=0, timeout_checks=0;
  void tick(uint64_t);
  void resetTimerAndUnblank() {++wakes;}
  void checkForTimeout() {++timeout_checks;}
};
struct twrp_backup_backend {
  std::mutex mutex_;backup_state state_=backup_state::RUNNING;
  std::atomic<bool> running_{true};void run();
};
struct twrp_restore_backend {
  std::mutex mutex_;restore_state state_=restore_state::RUNNING;
  std::atomic<bool> running_{true};void run(std::string);
};
struct twrp_install_backend {
  std::mutex mutex_;install_state state_=install_state::RUNNING;install_status status_;
  std::atomic<bool> running_{true};std::chrono::steady_clock::time_point started_{};
  void run_zip(std::vector<std::string>);
  int flash_zip(const std::string&,int*) {advance(6000);return job_calls++==fail_zip?1:0;}
};
}
// PRODUCTION_METHODS

static void expect_vibrations(int n,int duration=160) {
#ifdef TW_NO_HAPTICS
  n=0;
#endif
  assert(vibrations==std::vector<int>(n,duration));
}
static void finished(int expected_begins=1) {
  assert(value(TW_ACTION_BUSY)==0);
  assert(value("ui_progress")==100);
  assert(begins==expected_begins&&ends==expected_begins);
  assert(!properties.empty()&&properties.back()=="1");
}
int main(int argc,char**argv) {
  assert(argc==2);std::string c=argv[1];
  using namespace gui2_backend;
  DataManager::SetValue("tw_action_vibrate",160);
  DataManager::SetValue(TW_BACKUP_NAME,"fixture");
  if(c=="late-device"||c=="unplug") {
    device_present=c=="unplug";
    operation_start("first");advance(12000);operation_end(0);
    expect_vibrations(device_present?1:0);
    device_present=!device_present;
    operation_start("second");advance(12000);operation_end(0);
    expect_vibrations(1);finished(2);return 0;
  }
  if(c=="unmatched-end") {
    operation_end(0);expect_vibrations(0);assert(!take_operation_ended());
    assert(properties.empty()&&begins==0&&ends==0);return 0;
  }
  if(c.starts_with("backup-")) {
    job_ok=c!="backup-failure";cancel_backup=c=="backup-cancel";name_ok=c!="backup-invalid-name";
    twrp_backup_backend b;std::thread t([&]{b.run();});t.join();
    auto expected=!name_ok||!job_ok?backup_state::FAILED:cancel_backup?backup_state::CANCELLED:backup_state::DONE;
    assert(b.state_==expected&&!b.running_);
    assert(job_calls==(name_ok?1:0));expect_vibrations(name_ok?1:0);finished();return 0;
  }
  if(c.starts_with("restore-")) {
    job_ok=c=="restore-success";twrp_restore_backend b;
    std::thread t([&]{b.run("/fixture/backup");});t.join();
    assert(b.state_==(job_ok?restore_state::DONE:restore_state::FAILED)&&!b.running_);
    assert(job_calls==1);expect_vibrations(1);finished();return 0;
  }
  if(c.starts_with("zip-")) {
    fail_zip=c=="zip-failure"?1:-1;twrp_install_backend b;
    std::thread t([&]{b.run_zip({"a.zip","b.zip","c.zip"});});t.join();
    assert(b.state_==(fail_zip>=0?install_state::FAILED:install_state::DONE)&&!b.running_);
    assert(job_calls==(fail_zip>=0?2:3));assert(b.status_.done==(fail_zip>=0?1:3));
    expect_vibrations(1);finished();return 0;
  }
  if(c=="concurrent"||c=="foreign-end") {
    std::binary_semaphore started(0),finish(0);
    std::thread worker([&]{operation_start("worker");started.release();finish.acquire();operation_end(0);});
    started.acquire();assert(value(TW_ACTION_BUSY)==1);
    if(c=="foreign-end") {
      operation_end(1);assert(value(TW_ACTION_BUSY)==1&&!take_operation_ended());
    } else {
      advance(8000);operation_start("overlap");advance(1000);operation_end(0);
      assert(value(TW_ACTION_BUSY)==1&&value("ui_progress")==0);
      assert(ends==0&&take_operation_ended());expect_vibrations(0);
    }
    advance(12000);finish.release();worker.join();expect_vibrations(1);finished();return 0;
  }
  if(c=="completion-reset") {
    operation_start("first");operation_end(0);assert(properties.back()=="1");
    operation_start("next");assert(properties.back()=="0");operation_end(0);finished(2);return 0;
  }
  if(c=="sequential") {
    operation_start("first");advance(12000);operation_end(0);assert(take_operation_ended());
    operation_start("short next");advance(1000);operation_end(1);expect_vibrations(1);finished(2);return 0;
  }
  if(c=="wake-once"||c=="wake-coalesced") {
    twrp_screen_backend screen;screen.tick(1);assert(screen.wakes==0);
    operation_start("first");advance(12000);operation_end(0);
    if(c=="wake-coalesced") {operation_start("second");advance(12000);operation_end(1);}
    screen.tick(24000);screen.tick(25000);assert(screen.wakes==1&&screen.timeout_checks==3);
    expect_vibrations(c=="wake-once"?1:2);finished(c=="wake-once"?1:2);return 0;
  }
  operation_start("fixture");assert(value(TW_ACTION_BUSY)==1&&value("ui_progress")==0);
  assert(value("tw_ab_device")==1);
  int expected=1,duration=160;
  if(c=="short") {advance(1000);expected=0;}
  else if(c=="threshold") {advance(10000);expected=0;}
  else if(c=="above-threshold") advance(10001);
  else if(c=="wall-forward") {advance(1000,86400);expected=0;}
  else if(c=="wall-backward") advance(12000,-86400);
  else if(c=="repeated-start") {advance(6000);operation_start("next ZIP");advance(6000);}
  else {advance(12000);}
  if(c=="disabled") {DataManager::SetValue("tw_action_vibrate",0);expected=0;}
  if(c=="duration-setting") {DataManager::SetValue("tw_action_vibrate",235);duration=235;}
  if(c=="oversized-setting") {DataManager::SetValue("tw_action_vibrate",99999);duration=500;}
  if(c=="negative-setting") {DataManager::SetValue("tw_action_vibrate",-100);expected=0;}
  if(c=="global-disabled") {DataManager::SetValue("tw_disable_haptics",1);expected=0;}
  if(c=="missing-device") {device_present=false;expected=0;}
  operation_end(c=="failed"?1:0);
  if(c=="duplicate-end") {assert(take_operation_ended());operation_end(0);assert(!take_operation_ended());}
  else {assert(take_operation_ended());assert(!take_operation_ended());}
  expect_vibrations(expected,duration);finished();
  std::puts("PASS: production completion state, timing and feedback");
}
