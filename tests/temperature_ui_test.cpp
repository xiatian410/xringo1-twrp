#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>
#include <vector>
#include "backend/settings_store.h"
#include "backend/status_backend.h"
#include "shell/status_bar.h"
#include "shell/status_bar_controller.h"
#include "core/ui_helpers.h"
#include "gui2_svg_cache.h"

struct Settings : gui2_backend::settings_store {
 std::map<std::string,std::string> values{{"tw_time","12:00"},{"tw_battery","84%+"},{"tw_cpu_temp","42"}};
 std::string get_string(const std::string& k,const std::string& f) const override {
  auto it=values.find(k);return it==values.end()?f:it->second;
 }
 int get_int(const std::string& k,int f) const override {
  auto it=values.find(k);return it==values.end()?f:std::stoi(it->second);
 }
 bool set_persistent(const std::string&,const std::string&) override {assert(false);return false;}
 bool set(const std::string&,const std::string&) override {assert(false);return false;}
 bool flush() override {assert(false);return false;}
 bool update_timezone(bool = true) override {assert(false);return false;}
 bool restore_defaults() override {assert(false);return false;}
};
static void flush(lv_display_t* d,const lv_area_t*,uint8_t*){lv_display_flush_ready(d);}
static bool visible(lv_obj_t* o){return o&&!lv_obj_has_flag(o,LV_OBJ_FLAG_HIDDEN);}
static void check_bounds(const gui2_shell::status_bar_view& v,int width,int height) {
 lv_obj_update_layout(v.root);
 std::vector<lv_area_t> boxes;
 for(auto* o:{v.time_label,v.recording_indicator,v.temperature_label,v.wifi_icon,v.battery_icon,v.battery_value}) {
  if(!visible(o))continue;
  assert(!lv_obj_has_flag(o,LV_OBJ_FLAG_CLICKABLE));
  lv_area_t a;lv_obj_get_coords(o,&a);
  if(!(a.x1>=0&&a.x2<width&&a.y1>=0&&a.y2<height)) fprintf(stderr,"bounds %d %d %d %d width%d obj%p time%p rec%p temp%p\n",a.x1,a.y1,a.x2,a.y2,width,(void*)o,(void*)v.time_label,(void*)v.recording_indicator,(void*)v.temperature_label);
  assert(a.x1>=0&&a.x2<width&&a.y1>=0&&a.y2<height);
  for(auto b:boxes)assert(a.x2<b.x1||b.x2<a.x1||a.y2<b.y1||b.y2<a.y1);
  boxes.push_back(a);
 }
}
int main(int argc,char** argv) {
 assert(argc==6);std::string name=argv[1];int width=atoi(argv[2]),font=atoi(argv[3]);bool dark=atoi(argv[4]);
 Settings s;gui2_backend::status_backend backend(&s);
 if(name=="parser") {
  struct Case {const char* text;bool valid;int value;};
  for(auto c:{Case{"42",true,42},{"0",true,0},{"-12",true,-12},{"-273",true,-273},{"1000",true,1000},
      {"",false,0},{"42junk",false,0},{"42.0",false,0},{" 42",false,0},{"42\n",false,0},
      {"+42",false,0},{"999999999999999999999999",false,0},{"-274",false,0},{"1001",false,0}}) {
   s.values["tw_cpu_temp"]=c.text;auto snap=backend.snapshot();assert(snap.cpu_temperature_valid==c.valid);
   if(c.valid)assert(snap.cpu_temperature_c==c.value);
   assert(snap.battery_valid&&snap.battery_percentage==84&&snap.charging);
  }
  s.values["tw_cpu_temp"]="42";s.values["tw_no_cpu_temp"]="1";assert(!backend.snapshot().cpu_temperature_valid);
  s.values["tw_no_cpu_temp"]="0";s.values["tw_battery"]="";assert(backend.snapshot().cpu_temperature_valid);
  s.values["tw_no_battery_percent"]="1";s.values["tw_battery"]="84%";assert(backend.snapshot().cpu_temperature_valid&&!backend.snapshot().battery_valid);
  gui2_backend::status_backend empty(nullptr);auto snap=empty.snapshot();assert(!snap.cpu_temperature_valid&&!snap.battery_valid);
  puts("PASS strict parser14 values/disabled/independent battery/null provider");return 0;
 }
 lv_init();auto* display=lv_display_create(width,200);std::vector<uint32_t> pixels(width*200);
 lv_display_set_color_format(display,LV_COLOR_FORMAT_XRGB8888);
 lv_display_set_buffers(display,pixels.data(),nullptr,pixels.size()*4,LV_DISPLAY_RENDER_MODE_FULL);
 lv_display_set_flush_cb(display,flush);
 auto& ui=gui2_core::ui;static_cast<gui2_core::ui_palette&>(ui)=gui2_core::palette(dark);
 ui.width=width;ui.height=200;ui.scale=width==1440?1.2f:width==2560?1.0f:.4f;
 ui.status_font=font==48?&lv_font_montserrat_48:font==24?&lv_font_montserrat_24:&lv_font_montserrat_16;
 ui.outer_margin=gui2_core::ui_px(40);ui.status_top_padding=8;ui.status_height=100;
 gui2_core::set_surface_style(lv_screen_active(),ui.background);
 auto v=gui2_shell::create_status_bar(lv_screen_active(),ui,"REC",nullptr);
 assert(!visible(v.temperature_label)&&!visible(v.battery_value));
 gui2_shell::status_bar_controller controller;assert(controller.start(&s,ui,v,nullptr));
 auto verify=[&](){check_bounds(v,width,100);};
 auto tick=[&](){lv_tick_inc(1100);lv_timer_handler();verify();};
 assert(visible(v.temperature_label)&&std::string(lv_label_get_text(v.temperature_label))=="42°C");verify();
 if(name=="transitions") {
  for(auto value:{"", "garbage", "0", "-12", "1000", "42"}) {
   s.values["tw_cpu_temp"]=value;tick();
   bool valid=std::string(value)!=""&&std::string(value)!="garbage";
   assert(visible(v.temperature_label)==valid);
   assert(std::string(lv_label_get_text(v.temperature_label))==(valid?std::string(value)+"°C":""));
  }
  s.values["tw_no_cpu_temp"]="1";tick();assert(!visible(v.temperature_label));
  s.values["tw_no_cpu_temp"]="0";s.values["tw_battery"]="";tick();assert(visible(v.temperature_label)&&!visible(v.battery_value));
  s.values["tw_no_battery_percent"]="1";s.values["tw_battery"]="84%";tick();assert(visible(v.temperature_label)&&!visible(v.battery_value));
  s.values["tw_no_battery_percent"]="0";tick();assert(visible(v.battery_value));
  s.values["tw_time"]="11:59 PM";tick();
  gui2_shell::set_status_bar_wifi(v,true);tick();
  lv_obj_set_hidden(v.recording_indicator,false);gui2_shell::layout_status_bar(v,ui);verify();
  s.values["tw_time"]="23:59";tick();
 } else if(name=="pressure") {
  gui2_shell::set_status_bar_wifi(v,true);
  lv_obj_set_hidden(v.recording_indicator,false);
  lv_label_set_text(v.recording_indicator,"Very long localized recording label");
  s.values["tw_time"]="11:59 PM";controller.refresh();verify();
  assert(!visible(v.temperature_label));
  lv_obj_set_hidden(v.recording_indicator,true);gui2_shell::layout_status_bar(v,ui);verify();
  assert(visible(v.temperature_label));
  s.values["tw_time"]="An unexpectedly long time string overflowing screen";controller.refresh();verify();
  lv_obj_set_hidden(v.recording_indicator,false);gui2_shell::layout_status_bar(v,ui);verify();
 } else assert(name=="render");
 lv_refr_now(display);
 FILE* out=fopen(argv[5],"wb");assert(out);fprintf(out,"P6\n%d 200\n255\n",width);
 for(auto pixel:pixels){unsigned char rgb[]={static_cast<unsigned char>(pixel>>16),static_cast<unsigned char>(pixel>>8),static_cast<unsigned char>(pixel)};assert(fwrite(rgb,1,3,out)==3);}assert(fclose(out)==0);
 controller.stop();gui2_svg_cache_clear();lv_deinit();puts("PASS actual status backend/controller/LVGL layout");
}
