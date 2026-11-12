#include <cassert>
#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <vector>
#include "lvgl.h"
#include "components/check_row.h"
#include "core/ui_event_guard.h"
#include "core/ui_helpers.h"
#include "pages/general_settings_page.h"

struct Hardware final : gui2_backend::hardware_settings {
  int calls=0;
  bool has_brightness() const override {return false;}
  int brightness_percent() const override {return 0;}
  bool set_brightness_percent(int) override {return false;}
  bool has_haptics() const override {return true;}
  int haptic_duration_ms(gui2_backend::haptic_channel) const override {return 80;}
  bool set_haptic_duration_ms(gui2_backend::haptic_channel,int) override {return true;}
  void vibrate(gui2_backend::haptic_channel) override {++calls;}
} hw;
gui2_backend::hardware_settings* hardware=&hw;
struct Settings {
  bool works=true;
  int flushes=0;
  std::map<std::string,std::string> values;
  bool set_persistent(const std::string& k,const std::string& v) {values[k]=v;return true;}
  bool flush(){++flushes;return works;}
} store;
Settings* settings=&store;
gui2_pages::general_setting general_settings_items[1]={{nullptr,"Swap navigation","tw_gui2_swap_navigation",false}};
size_t general_settings_count=1;
auto& ui=gui2_core::ui;
int navigation_view=0, navigation_calls=0;
namespace gui2_shell {
void set_bottom_navigation_swapped(int&,const gui2_core::ui_metrics&,bool){++navigation_calls;}
}
#include "callback.inc"
static lv_point_t pos;
static bool pressed=false;
static void read_pointer(lv_indev_t*,lv_indev_data_t* d){d->point=pos;d->state=pressed?LV_INDEV_STATE_PRESSED:LV_INDEV_STATE_RELEASED;}
static void flush(lv_display_t* d,const lv_area_t*,uint8_t*){lv_display_flush_ready(d);}
static lv_indev_t* pointer;
static void point(lv_point_t p,bool down) {
  pos=p;pressed=down;lv_tick_inc(25);lv_indev_read(pointer);lv_timer_handler();
}
static lv_point_t center(lv_obj_t* o) {
  lv_obj_update_layout(o);lv_area_t a;lv_obj_get_coords(o,&a);return {(a.x1+a.x2)/2,(a.y1+a.y2)/2};
}
int main(int argc,char**argv){
  assert(argc==3);std::string kind=argv[1],name=argv[2];
  lv_init();auto* display=lv_display_create(480,640);
  std::vector<uint32_t> pixels(480*640);
  lv_display_set_color_format(display,LV_COLOR_FORMAT_XRGB8888);
  lv_display_set_buffers(display,pixels.data(),nullptr,pixels.size()*4,LV_DISPLAY_RENDER_MODE_FULL);
  lv_display_set_flush_cb(display,flush);
  pointer=lv_indev_create();lv_indev_set_type(pointer,LV_INDEV_TYPE_POINTER);
  lv_indev_set_display(pointer,display);lv_indev_set_read_cb(pointer,read_pointer);
  gui2_core::configure_click_guard(pointer,hardware);
  static_cast<gui2_core::ui_palette&>(ui)=gui2_core::palette(true);
  ui.width=480;ui.height=640;ui.scale=.4f;ui.outer_margin=16;ui.content_width=448;
  ui.text_font=&lv_font_montserrat_16;
  auto* screen=lv_screen_active();gui2_core::disable_scrolling(screen);
  lv_obj_t* parent=screen;
  if(name=="scroll"){
    parent=lv_obj_create(screen);lv_obj_set_pos(parent,0,40);lv_obj_set_size(parent,480,220);
    lv_obj_set_style_pad_all(parent,0,0);lv_obj_set_scroll_dir(parent,LV_DIR_VER);
    auto* tail=lv_obj_create(parent);lv_obj_set_pos(tail,0,700);lv_obj_set_size(tail,1,1);
  }
  int index=0;
  auto create=kind=="check"?gui2_components::create_check_row:gui2_components::create_switch_row;
  auto* toggle=create(parent,ui,"Swap navigation",false,general_setting_event_cb,&index);
  auto* card=lv_obj_get_parent(toggle);lv_obj_set_pos(card,16,60);
  lv_obj_update_layout(screen);
  auto target=center(lv_obj_get_child(card,0));
  if(name=="indicator")target=center(toggle);
  if(name=="blank") {lv_area_t a;lv_obj_get_coords(card,&a);target={a.x1+3,(a.y1+a.y2)/2};}
  if(name=="disabled")lv_obj_add_state(toggle,LV_STATE_DISABLED);
  if(name=="rollback")store.works=false;
  point(target,true);
  if(name=="drag-out"||name=="drag-back"){
    point({0,0},true);if(name=="drag-back")point(target,true);
  }
  if(name=="press-lost")lv_obj_send_event(card,LV_EVENT_PRESS_LOST,pointer);
  if(name=="scroll"){
    for(int step=1;step<=5;++step)point({target.x,target.y-step*8},true);
  }
  point(pos,false);
  bool cancelled=name=="drag-out"||name=="drag-back"||name=="disabled"||name=="press-lost"||name=="scroll";
  if(cancelled){assert(store.flushes==0&&hw.calls==0&&!lv_obj_has_state(toggle,LV_STATE_CHECKED));}
  else if(name=="rollback") {
    assert(store.flushes==1&&hw.calls==0&&!lv_obj_has_state(toggle,LV_STATE_CHECKED));
    assert(store.values["tw_gui2_swap_navigation"]=="0"&&!general_settings_items[0].value);
    store.works=true;point(target,true);point(target,false);
    assert(store.flushes==2&&hw.calls==1&&general_settings_items[0].value);
  } else {
    assert(store.flushes==1&&hw.calls==1&&navigation_calls==1);
    assert(lv_obj_has_state(toggle,LV_STATE_CHECKED)&&general_settings_items[0].value);
    if(name=="double") {
      point(target,true);point(target,false);
      assert(store.flushes==2&&hw.calls==2&&navigation_calls==2);
      assert(!lv_obj_has_state(toggle,LV_STATE_CHECKED)&&!general_settings_items[0].value);
    }
  }
  if(name=="scroll")assert(lv_obj_get_scroll_y(parent)>0);
  printf("PASS %s/%s flushes=%d feedback=%d\n",argv[1],argv[2],store.flushes,hw.calls);
  gui2_core::configure_click_guard(nullptr,nullptr);lv_deinit();
}
