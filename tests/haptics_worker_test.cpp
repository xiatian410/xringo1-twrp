#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <future>
#include <map>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include "haptics_controller.h"
#include "twrp_hardware_settings.h"
#include "backlight_controller.h"
#include "settings_store.h"
#include "data.hpp"

using namespace std::chrono_literals;
using gui2_backend::haptics_controller;
using gui2_backend::haptic_channel;
static const auto caller = std::this_thread::get_id();
static int synchronous_probes = 0, synchronous_plays = 0;
int haptics_available() { ++synchronous_probes; return 1; }
int vibrate(int) { ++synchronous_plays; return 0; }
namespace gui2_backend {
bool backlight_controller::set_user(int) { assert(false); return false; }
bool backlight_controller::consume_error() { assert(false); return false; }
void backlight_controller::stop() { assert(false); }
}
struct Store : gui2_backend::settings_store {
  std::string get_string(const std::string&,const std::string& d) const override { return d; }
  int get_int(const std::string& k,int d) const override {
    auto it=DataManager::values.find(k);return it==DataManager::values.end()?d:it->second;
  }
  bool set(const std::string& k,const std::string& v) override { DataManager::values[k]=std::stoi(v);return true; }
  bool set_persistent(const std::string& k,const std::string& v) override { return set(k,v); }
  bool flush() override { return true; }
  bool update_timezone(bool = true) override {return true;}
  bool restore_defaults() override { return true; }
};

struct Gate {
  std::mutex mutex;
  std::condition_variable changed;
  bool entered=false, released=false;
  void block() {
    std::unique_lock lock(mutex);entered=true;changed.notify_all();
    assert(changed.wait_for(lock,3s,[&]{return released;}));
  }
  void wait() {
    std::unique_lock lock(mutex);assert(changed.wait_for(lock,2s,[&]{return entered;}));
  }
  void open() { std::lock_guard lock(mutex);released=true;changed.notify_all(); }
};
template<class F> void eventually(F f) {
  const auto end=std::chrono::steady_clock::now()+2s;
  while(!f()) { assert(std::chrono::steady_clock::now()<end); std::this_thread::yield(); }
}
template<class F> void responsive(F f) {
  // Gate is deliberately still closed: finishing this future proves that the
  // caller does not wait for the active device callback. No tiny time threshold.
  auto future=std::async(std::launch::async,f);
  assert(future.wait_for(1s)==std::future_status::ready);future.get();
}

int main(int argc,char** argv) {
  assert(argc==2);const std::string test=argv[1];
  DataManager::values={{"tw_disable_haptics",0},{"tw_button_vibrate",80},
                       {"tw_keyboard_vibrate",40},{"tw_action_vibrate",160}};
  std::atomic<int> probes=0,plays=0,releases=0;
  std::atomic<bool> present=true,fail=false;
  if(test=="late-device")present=false;
  std::mutex records_mutex;std::vector<int> durations;
  Gate gate;
  const bool blocked_probe=test=="probe-nonblocking" || test=="probe-stop";
  const bool blocked_play=test=="play-nonblocking" || test=="latest-only" ||
      test=="expired" || test=="stop-discards" || test=="concurrent-stop";
  haptics_controller c([&] {
    assert(std::this_thread::get_id()!=caller);++probes;
    if(blocked_probe)gate.block();return present.load();
  },[&](int ms) {
    assert(std::this_thread::get_id()!=caller);
    {std::lock_guard lock(records_mutex);durations.push_back(ms);}
    const int n=++plays;if(blocked_play && n==1)gate.block();return !fail.load();
  },[&] {assert(std::this_thread::get_id()!=caller);++releases;});
  Store store;gui2_backend::twrp_hardware_settings hw(&store,nullptr,&c);
  if(blocked_probe) {
    gate.wait();responsive([&] { assert(!hw.has_haptics());hw.vibrate(haptic_channel::BUTTON); });
    if(test=="probe-stop") {
      auto stopped=std::async(std::launch::async,[&]{hw.stop_haptics();});
      eventually([&]{return !c.submit(80);});
      assert(stopped.wait_for(30ms)==std::future_status::timeout);
      gate.open();stopped.get();
    } else {gate.open();eventually([&]{return hw.has_haptics();});}
  } else {
    if(test=="late-device") {
      eventually([&]{return probes>0;});assert(!hw.has_haptics());
      hw.vibrate(haptic_channel::BUTTON);assert(plays==0);
      present=true;
    }
    eventually([&]{return hw.has_haptics();});
    if(blocked_play) {
      hw.vibrate(haptic_channel::BUTTON);gate.wait();
      responsive([&] { assert(hw.has_haptics());
        for(int n=0;n<5000;++n)hw.vibrate(haptic_channel::KEYBOARD);
        hw.vibrate(haptic_channel::ACTION);
        assert(!hw.take_haptics_error());
        assert(hw.set_haptic_duration_ms(haptic_channel::BUTTON,123)); });
      assert(plays==1);
      if(test=="expired")std::this_thread::sleep_for(300ms);
      if(test=="stop-discards" || test=="concurrent-stop") {
        auto stopped=std::async(std::launch::async,[&]{hw.stop_haptics();});
        eventually([&]{return !c.available();});assert(!c.submit(80));
        assert(stopped.wait_for(30ms)==std::future_status::timeout);
        auto second=std::async(std::launch::async,[&]{if(test=="concurrent-stop")c.stop();});
        gate.open();stopped.get();second.get();assert(plays==1);
      } else {
        const int previous_probes=probes;
        gate.open();
        if(test!="expired")eventually([&]{return plays==2;});
        else eventually([&]{return probes>previous_probes;});
        c.stop();
        assert(plays==(test=="expired"?1:2));
        if(test!="expired")assert(durations.back()==160);
      }
    } else if(test=="failure" || test=="recovery") {
      fail=true;hw.vibrate(haptic_channel::BUTTON);eventually([&]{return hw.take_haptics_error();});
      assert(!hw.take_haptics_error());
      if(test=="recovery") {fail=false;eventually([&]{return hw.has_haptics();});
        hw.vibrate(haptic_channel::ACTION);eventually([&]{return plays==2;});}
    } else if(test=="late-device" || test=="unplug") {
      present=false;eventually([&]{return !hw.has_haptics();});
      assert(!hw.set_haptic_duration_ms(haptic_channel::BUTTON,99));
      hw.vibrate(haptic_channel::BUTTON);assert(plays==0);
      if(test=="late-device") {present=true;eventually([&]{return hw.has_haptics();});
        hw.vibrate(haptic_channel::BUTTON);eventually([&]{return plays==1;});}
    } else if(test=="durations") {
      for(auto channel:{haptic_channel::BUTTON,haptic_channel::KEYBOARD,haptic_channel::ACTION}) {
        const int before=plays;hw.vibrate(channel);eventually([&]{return plays>before;});
      }
      c.stop();assert((durations==std::vector<int>{80,40,160}));
    } else if(test=="disabled" || test=="zero" || test=="invalid") {
      if(test=="disabled")DataManager::values["tw_disable_haptics"]=1;
      if(test=="zero")DataManager::values["tw_button_vibrate"]=0;
      if(test=="invalid") {assert(!c.submit(0));assert(!c.submit(-1));assert(!c.submit(10001));}
      else hw.vibrate(haptic_channel::BUTTON);
      c.stop();assert(plays==0);
    } else if(test=="idle-stop") {c.stop();assert(!hw.has_haptics());hw.vibrate(haptic_channel::BUTTON);assert(plays==0);}
    else assert(false);
  }
  c.stop();c.stop();assert(releases==1);assert(synchronous_probes==0 && synchronous_plays==0);
  assert(!c.available() && !c.submit(80));
}
