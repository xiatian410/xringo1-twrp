#include <cassert>
#include <cstdio>
#include <cstring>
#include <iterator>
#include <map>
#include <string>
#include "lvgl.h"
#include <data.hpp>
#include "backend/twrp_settings_store.h"
#include "backend/twrp_operation.h"
#include "pages/settings_data.h"
namespace gui2_backend {void operation_start(const std::string&){}void operation_end(int){}}
gui2_backend::twrp_settings_store store;
gui2_backend::settings_store*settings=&store;
using gui2_pages::timezone_values;using gui2_pages::timezone_offsets;
bool pending_military_time=true,pending_dst=false;int pending_timezone_index=19,pending_offset_index=0;
struct Status{int calls=0;void refresh(){++calls;}}status_controller;
enum class page_kind{TIMEZONE};enum class page_transition{REPLACE};
int navigations=0;void navigate_to(page_kind,void*,page_transition){++navigations;}
bool accept_click(lv_event_t*){return true;}
#include "callback.inc"
int main(int argc,char**argv){
 assert(argc==2);const std::string name=argv[1];
 // Deliberately not reconstructible from the saved GUI choices: rollback must
 // preserve the user's exact custom zone rather than synthesizing US Central.
 DataManager::values={{"tw_military_time","0"},{"tw_time_zone_guisel",timezone_values[5]},
 {"tw_time_zone_guioffset","0"},{"tw_time_zone_guidst","0"},{"tw_time_zone","CUSTOM-9:45"}};
 DataManager::disk=DataManager::values;const auto previous=DataManager::values;
 DataManager::UpdateTimezoneEnvironment();
 if(name=="success-offset")pending_offset_index=2;
 if(name=="success-dst"){pending_timezone_index=3;pending_dst=true;}
 if(name=="success-west"){pending_timezone_index=6;pending_offset_index=3;}
 if(name.starts_with("set-failure-"))DataManager::fail_write=name.back()-'0';
 if(name=="flush-failure"||name=="retry")DataManager::flush_ok=false;
 if(name=="zone-low")pending_timezone_index=-1;if(name=="zone-high")pending_timezone_index=24;
 if(name=="offset-low")pending_offset_index=-1;if(name=="offset-high")pending_offset_index=4;
 if(name=="null-store")settings=nullptr;
 lv_init();assert(lv_display_create(480,640));auto*button=lv_obj_create(lv_screen_active());
 lv_obj_add_event_cb(button,apply_timezone_event_cb,LV_EVENT_ALL,nullptr);
 lv_obj_send_event(button,name=="wrong-event"?LV_EVENT_PRESSED:LV_EVENT_CLICKED,nullptr);
 const bool success=name.starts_with("success-");
 if(!success){
  assert(DataManager::values==previous&&DataManager::disk==previous);
  assert(std::string(getenv("TZ"))=="CUSTOM-9:45"&&android::base::zone_property=="CUSTOM-9:45");
  assert(navigations==0&&status_controller.calls==0);
  assert(pending_military_time&&!pending_dst);
 }
 if(name=="retry"){
  DataManager::flush_ok=true;lv_obj_send_event(button,LV_EVENT_CLICKED,nullptr);assert(DataManager::flushes==2);
 }
 if(success||name=="retry"){
  const std::string expected=name=="success-offset"?"TAIST-8:30":name=="success-dst"?"PST8PDT,M3.2.0,M11.1.0":name=="success-west"?"EST5:45":"TAIST-8";
  assert(DataManager::values.at("tw_time_zone")==expected&&std::string(getenv("TZ"))==expected&&android::base::zone_property==expected);
  assert(DataManager::disk==DataManager::values&&navigations==1&&status_controller.calls==1);
  assert(DataManager::values.at("tw_military_time")=="1");
  std::tm tm{};time_t epoch=1794334193;assert(localtime_r(&epoch,&tm));
  assert(tm.tm_gmtoff==(name=="success-offset"?30600:name=="success-dst"?-28800:name=="success-west"?-20700:28800));
 }
 lv_deinit();std::printf("PASS %s: exact zone/choices/environment/disk and routing checked\n",argv[1]);
}
