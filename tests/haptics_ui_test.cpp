#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <vector>
#include "lvgl.h"
#include "backend/hardware_settings.h"
#include "core/ui_event_guard.h"
#include "core/ui_metrics.h"
#include "core/ui_helpers.h"
#include "components/flat_button.h"
#include "components/keyboard.h"
#include "components/swipe_slider.h"
#include "gui2_svg_cache.h"

using gui2_backend::haptic_channel;
using gui2_core::accept_click;
struct Hardware final : gui2_backend::hardware_settings {
  std::vector<haptic_channel> calls;
  bool has_brightness() const override { return false; }
  int brightness_percent() const override { return 0; }
  bool set_brightness_percent(int) override { return false; }
  bool has_haptics() const override { return true; }
  int haptic_duration_ms(haptic_channel) const override { return 80; }
  bool set_haptic_duration_ms(haptic_channel,int) override { return true; }
  void vibrate(haptic_channel c) override { calls.push_back(c); }
} hardware_fixture;
gui2_backend::hardware_settings* hardware=&hardware_fixture;
struct Cancel { int count=0; void cancel(){++count;} } sideload_fixture,backup_fixture;
Cancel* sideload=&sideload_fixture;
Cancel* backup=&backup_fixture;
struct Settings {
  std::map<std::string,std::string> values;
  int flushes=0;
  bool set_persistent(const std::string& k,const std::string& v){values[k]=v;return true;}
  bool flush(){++flushes;return true;}
} settings_fixture;
Settings* settings=&settings_fixture;
struct Progress {lv_obj_t* running_action=nullptr;};
struct PageState {Progress sideload_progress,install_progress;
  bool install_countdown_done=false,sideload_wipe_dalvik=false,sideload_wipe_cache=false;
  int change_fs_selected=-1;
} page_state;
int refreshes=0,rebuilds=0,navigations=0;
void refresh_install_progress(){++refreshes;}
void rebuild_file_list(){++rebuilds;}
void close_open_sort_menu(bool){}
const char* sort_key_label(int){return "Sort";}
constexpr int kSortOrders[]={0,1,2,3,4,5};
struct Toolbar{lv_obj_t* sort_label=nullptr;} file_manager_toolbar;
int file_manager_view=0;
namespace gui2_pages { void fade_file_list(int){} }
enum class page_kind {CHANGE_FS};
enum class page_transition {NONE};
void navigate_to(page_kind,const void*,page_transition){++navigations;}
#include "callbacks.inc"

constexpr int width=480,height=960;
static std::vector<uint32_t> frame(width*height),pixels(width*height);
static lv_indev_t* pointer;
static lv_point_t position{0,0};
static lv_indev_state_t input_state=LV_INDEV_STATE_RELEASED;
static int flushes=0;
static bool nonblank_rendered=false;
static void read_pointer(lv_indev_t*,lv_indev_data_t* data) {
  data->point=position;data->state=input_state;
}
static void flush(lv_display_t* display,const lv_area_t* area,uint8_t* data) {
  const auto* source=reinterpret_cast<const uint32_t*>(data);
  const int span=lv_area_get_width(area);
  for(int y=area->y1;y<=area->y2;++y)
    std::copy_n(source+(y-area->y1)*span,span,pixels.begin()+y*width+area->x1);
  nonblank_rendered |= std::any_of(pixels.begin(),pixels.end(),[](uint32_t p){return (p&0xffffff)!=0;});
  ++flushes;lv_display_flush_ready(display);
}
static void render() {lv_tick_inc(16);lv_timer_handler();lv_refr_now(nullptr);}
static void save_frame(const char* path) {
  FILE* file=std::fopen(path,"wb");assert(file!=nullptr);
  std::fprintf(file,"P6\n%d %d\n255\n",width,height);
  for(uint32_t p:pixels) {
    const unsigned char rgb[]={static_cast<unsigned char>(p>>16),static_cast<unsigned char>(p>>8),static_cast<unsigned char>(p)};
    assert(std::fwrite(rgb,1,3,file)==3);
  }
  assert(std::fclose(file)==0);
}
static void point(int x,int y,bool pressed) {
  position={x,y};input_state=pressed?LV_INDEV_STATE_PRESSED:LV_INDEV_STATE_RELEASED;
  lv_tick_inc(20);lv_indev_read(pointer);render();
}
static lv_point_t center(lv_obj_t* obj) {
  lv_obj_update_layout(obj);lv_area_t a;lv_obj_get_coords(obj,&a);
  return {(a.x1+a.x2)/2,(a.y1+a.y2)/2};
}
static void tap(lv_obj_t* obj) {auto p=center(obj);point(p.x,p.y,true);point(p.x,p.y,false);}
static void once(haptic_channel c= haptic_channel::BUTTON) {
  if(hardware_fixture.calls!=std::vector<haptic_channel>{c}) {
    std::fprintf(stderr,"Expected one haptic request; got %zu\n",hardware_fixture.calls.size());
    std::abort();
  }
}
static lv_obj_t* find_label(lv_obj_t* root,const char* wanted) {
  if(lv_obj_check_type(root,&lv_label_class)&&std::strcmp(lv_label_get_text(root),wanted)==0)
    return lv_obj_get_parent(root);
  for(uint32_t i=0;i<lv_obj_get_child_count(root);++i)
    if(auto* result=find_label(lv_obj_get_child(root,i),wanted))return result;
  return nullptr;
}
static int swipe_actions=0;
static void swiped(void*){++swipe_actions;}

int main(int argc,char** argv) {
  assert(argc==3);std::string name=argv[1];
  lv_init();
  auto* display=lv_display_create(width,height);
  lv_display_set_color_format(display,LV_COLOR_FORMAT_XRGB8888);
  lv_display_set_buffers(display,frame.data(),nullptr,frame.size()*4,LV_DISPLAY_RENDER_MODE_FULL);
  lv_display_set_flush_cb(display,flush);
  pointer=lv_indev_create();lv_indev_set_type(pointer,LV_INDEV_TYPE_POINTER);
  lv_indev_set_display(pointer,display);lv_indev_set_read_cb(pointer,read_pointer);
  gui2_core::configure_click_guard(pointer,hardware);
  auto& ui=gui2_core::ui;
  static_cast<gui2_core::ui_palette&>(ui)=gui2_core::palette(true);
  ui.width=width;ui.height=height;ui.scale=0.4f;ui.card_height=150;
  ui.outer_margin=16;ui.content_width=width-32;ui.card_gap=8;
  ui.text_font=ui.keyboard_font=&lv_font_montserrat_16;
  auto* screen=lv_screen_active();gui2_core::disable_scrolling(screen);
  gui2_core::set_surface_style(screen,ui.background);

  if(name.starts_with("keyboard")) {
    auto* textarea=lv_textarea_create(screen);lv_obj_set_size(textarea,400,80);lv_obj_set_pos(textarea,20,20);
    lv_textarea_set_text(textarea,"");
    gui2_components::keyboard keyboard;
    gui2_components::keyboard_options options;
    options.parent=screen;options.metrics=&ui;options.textarea=textarea;
    options.key_callback=keyboard_feedback_cb;options.layout=gui2_components::keyboard_layout::NUMBER;
    options.pin_entry=true;options.show_hide_key=false;
    keyboard.create(options);
    // As on production pages, the caller positions the fixed keyboard viewport.
    lv_obj_update_layout(keyboard.root());
    lv_obj_set_pos(keyboard.root(),0,height-lv_obj_get_height(keyboard.root())-20);
    render();
    auto* key=find_label(keyboard.root(),"1");assert(key!=nullptr);
    if(name=="keyboard-disabled") lv_obj_add_state(textarea,LV_STATE_DISABLED);
    if(name=="keyboard-cancel"||name=="keyboard-drag-out-back") {
      auto p=center(key);point(p.x,p.y,true);point(0,0,true);
      if(name=="keyboard-drag-out-back")point(p.x,p.y,true);
      point(position.x,position.y,false);
      assert(hardware_fixture.calls.empty());assert(std::string(lv_textarea_get_text(textarea)).empty());
    } else {
      tap(key);
      if(name=="keyboard-disabled") {assert(hardware_fixture.calls.empty());assert(std::string(lv_textarea_get_text(textarea)).empty());}
      else {
        once(haptic_channel::KEYBOARD);assert(std::string(lv_textarea_get_text(textarea))=="1");
        if(name=="keyboard-two-taps") {
          tap(key);assert(hardware_fixture.calls==std::vector<haptic_channel>(2,haptic_channel::KEYBOARD));
          assert(std::string(lv_textarea_get_text(textarea))=="11");
        }
      }
    }
    if(name=="keyboard")save_frame(argv[2]);
    keyboard.dismiss();
  } else if(name.starts_with("swipe")) {
    gui2_components::swipe_slider slider;
    auto* track=slider.create(screen,ui,20,160,440,90,"Confirm",swiped,nullptr);
    render();auto* knob=lv_obj_get_child(track,2);auto p=center(knob);
    point(p.x,p.y,true);
    if(name=="swipe-short") {
      point(p.x+30,p.y,true);point(p.x+30,p.y,false);
      assert(swipe_actions==0&&hardware_fixture.calls.empty()&&slider.progress()==0);
    } else {
      point(430,p.y,true);assert(slider.progress()==1000);
      if(name=="swipe-disabled-mid-drag"||name=="swipe-reenable") slider.set_enabled(false);
      point(430,p.y,false);
      if(name=="swipe-stray-release")lv_obj_send_event(knob,LV_EVENT_RELEASED,pointer);
      if(name=="swipe-disabled-mid-drag"||name=="swipe-reenable") {
        assert(swipe_actions==0&&hardware_fixture.calls.empty()&&slider.progress()==0);
        if(name=="swipe-reenable") {
          slider.set_enabled(true);render();auto start=center(knob);
          point(start.x,start.y,true);point(430,start.y,true);point(430,start.y,false);
          assert(swipe_actions==1);once();
        }
      }
      else {assert(swipe_actions==1);once();}
    }
    if(name=="swipe-complete")save_frame(argv[2]);
    slider.detach();
  } else if(name=="toggle") {
    auto* toggle=lv_switch_create(screen);lv_obj_set_pos(toggle,40,60);lv_obj_set_size(toggle,80,40);
    int index=0;lv_obj_add_event_cb(toggle,sideload_option_cb,LV_EVENT_VALUE_CHANGED,&index);
    render();tap(toggle);once();assert(page_state.sideload_wipe_dalvik);
  } else {
    lv_event_cb_t callback=backup_cancel_cb;
    if(name=="sideload")callback=sideload_cancel_cb;
    if(name=="sort")callback=sort_choice_cb;
    if(name=="countdown")callback=install_countdown_cancel_cb;
    if(name=="filesystem")callback=change_fs_choice_event_cb;
    auto* button=gui2_components::create_flat_button(screen,ui,360,"Action",nullptr,gui2_core::press_cancel_guard_cb);
    lv_obj_set_pos(button,40,100);int choice=2;
    lv_obj_add_event_cb(button,callback,LV_EVENT_CLICKED,&choice);
    page_state.sideload_progress.running_action=button;page_state.install_progress.running_action=button;
    render();auto p=center(button);
    if(name=="no-hardware") {hardware=nullptr;gui2_core::configure_click_guard(pointer,nullptr);}
    if(name=="drag-out"||name=="drag-out-back"||name=="press-lost") {
      point(p.x,p.y,true);
      if(name=="press-lost")lv_obj_send_event(button,LV_EVENT_PRESS_LOST,pointer);
      else point(0,0,true);
      if(name=="drag-out-back")point(p.x,p.y,true);
      point(position.x,position.y,false);
      assert(hardware_fixture.calls.empty()&&backup_fixture.count==0);
    } else {
      tap(button);
      if(name=="two-taps") {tap(button);assert(hardware_fixture.calls.size()==2&&backup_fixture.count==2);}
      else if(name=="no-hardware")assert(hardware_fixture.calls.empty()&&backup_fixture.count==1);
      else once();
      if(name=="sideload")assert(sideload_fixture.count==1&&lv_obj_is_hidden(button));
      if(name=="sort")assert(settings_fixture.flushes==1&&settings_fixture.values["tw_gui_sort_order"]=="2"&&rebuilds==1);
      if(name=="countdown")assert(page_state.install_countdown_done&&refreshes==1&&lv_obj_is_hidden(button));
      if(name=="filesystem")assert(page_state.change_fs_selected==2&&navigations==1);
      if(name=="backup")assert(backup_fixture.count==1);
    }
  }
  assert(flushes>0&&nonblank_rendered);
  std::printf("PASS %s: real LVGL pointer dispatch and nonblank framebuffer; flushes=%d\n",name.c_str(),flushes);
  gui2_core::configure_click_guard(nullptr,nullptr);gui2_svg_cache_clear();lv_deinit();
}
