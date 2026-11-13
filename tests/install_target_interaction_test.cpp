// Host LVGL navigation fixture. Destination pages, storage and hardware are boundaries.
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>
#include "lvgl.h"
#include "core/ui_helpers.h"
#include "core/ui_event_guard.h"
#include "pages/page_router.h"
#include "shell/page_host.h"
#include "pages/install_confirm_page.h"
#include "i18n/i18n.h"
#include "components/swipe_slider.h"
#include "backend/install_backend.h"
using page_kind=gui2_pages::page_id;
using page_transition=gui2_core::page_transition;
using gui2_core::accept_click;
#include "image-targets.inc"
namespace gui2_i18n { extern const language_pack kEnglish; }
static std::vector<int> target_indices=[] {std::vector<int> v;for(size_t i=0;i<install_targets.size();++i)v.push_back(i);return v;}();
static gui2_shell::page_host host;
static gui2_pages::page_router router;
static lv_obj_t* confirm_track=nullptr;
static struct install_observer final : gui2_backend::install_backend {
  std::string path, target; bool both_slots=false; int calls=0;
  bool start_zip(const std::vector<std::string>&) override {return false;}
  std::vector<gui2_backend::image_target> image_targets() override {return {};}
  std::string image_target_for(const std::string&) override {return {};}
  bool start_image(const std::string& p,const std::string& t,bool both) override {
    path=p;target=t;both_slots=both;++calls;return true;
  }
  gui2_backend::install_status status() override {return {};}
  void acknowledge() override {}
} backend;
static gui2_backend::install_backend* install=&backend;
static struct {
  std::string install_selection="/data/media/0/test.img";
  std::string install_target_mount;
  bool install_both_slots=true;
  bool install_image=true;
  std::vector<std::string> install_queue;
  gui2_components::swipe_slider install_confirm;
  uint64_t install_countdown_start_ms=0;
  bool install_countdown_done=false;
} page_state;
static int navigations=0;
static page_kind last_page=page_kind::HOME;
static page_transition last_transition=page_transition::NONE;
static void install_target_event_cb(lv_event_t* event);
static void install_confirmed(void*);
static void build_routed_page(const gui2_pages::page_request& request) {
  last_page=request.id; last_transition=request.transition; ++navigations;
  if(request.id==page_kind::INSTALL_CONFIRM) {
    auto page=host.build("Install image", "", gui2_core::navigation_safe_area(), request.transition);
    gui2_pages::install_confirm_page_options options;
    options.content=page.content;options.metrics=&gui2_core::ui;options.strings=&gui2_i18n::kEnglish;
    options.image=true;options.folder="/data/media/0";options.file="test.img";
    options.targets=install_targets.data();options.target_count=install_targets.size();
    options.target_indices=target_indices.data();options.selected_target=install_targets.size();
    for(size_t i=0;i<install_targets.size();++i)
      if(install_targets[i].mount_point==page_state.install_target_mount) options.selected_target=i;
    options.target_callback=install_target_event_cb;options.press_guard_callback=gui2_core::press_cancel_guard_cb;
    gui2_pages::build_install_confirm_page(options);
    confirm_track=page_state.install_confirm.create(
        host.current_page(), gui2_core::ui, gui2_core::ui.content_left, 2600,
        gui2_core::ui.content_width, 140, "Swipe", install_confirmed, nullptr);
  } else {
    const char* title=request.id==page_kind::INSTALL_PROGRESS ? "Install progress" : "Install";
    host.build(title, "", gui2_core::navigation_safe_area(), request.transition);
    auto* label=lv_label_create(host.content());lv_label_set_text(label,title);
  }
  host.settle();
}
static void navigate_to(page_kind page,const void* payload,page_transition transition){
  assert(router.navigate(page,payload,transition));
}
#include "callback.inc"
static lv_point_t position;
static bool down;
static lv_indev_t* pointer;
static void read_pointer(lv_indev_t*, lv_indev_data_t* data) {
  data->point = position;
  data->state = down ? LV_INDEV_STATE_PRESSED : LV_INDEV_STATE_RELEASED;
}
static void flush(lv_display_t* display, const lv_area_t*, uint8_t*) {
  lv_display_flush_ready(display);
}
static void advance(unsigned ms) {
  for(unsigned t = 0; t < ms; t += 20) { lv_tick_inc(20); lv_timer_handler(); }
}
static void point(lv_point_t p, bool pressed) {
  position = p; down = pressed; lv_tick_inc(25); lv_indev_read(pointer); lv_timer_handler();
  advance(80);
}
static lv_point_t center(lv_obj_t* object) {
  lv_area_t a; lv_obj_get_coords(object, &a);
  return {(a.x1+a.x2)/2, (a.y1+a.y2)/2};
}
int main(int argc, char** argv) {
  assert(argc == 3);
  const int index = std::atoi(argv[1]); const std::string mode = argv[2];
  assert(index >= 0 && static_cast<size_t>(index) < install_targets.size());
  lv_init(); auto* display = lv_display_create(1440, 3200);
  std::vector<uint32_t> pixels(1440*64);
  lv_display_set_color_format(display, LV_COLOR_FORMAT_XRGB8888);
  lv_display_set_buffers(display, pixels.data(), nullptr, pixels.size()*4, LV_DISPLAY_RENDER_MODE_PARTIAL);
  lv_display_set_flush_cb(display, flush);
  pointer = lv_indev_create(); lv_indev_set_type(pointer, LV_INDEV_TYPE_POINTER);
  lv_indev_set_display(pointer, display); lv_indev_set_read_cb(pointer, read_pointer);
  gui2_core::configure_click_guard(pointer, nullptr);
  auto& ui = gui2_core::ui;
  static_cast<gui2_core::ui_palette&>(ui) = gui2_core::palette(true);
  // Representative phone metrics; Android font/display/physical input are not executed.
  ui.width=1440; ui.height=3200; ui.scale=1.2f; ui.status_height=100;
  ui.outer_margin=48; ui.content_left=48; ui.content_width=1344;
  ui.nav_height=156; ui.card_gap=24; ui.cards_top_gap=24;
  ui.heading_top=48; ui.heading_height=180; ui.card_height=192; ui.icon_size=100;
  ui.text_font=ui.status_font=ui.brand_font=&lv_font_montserrat_16;
  auto* screen=lv_screen_active(); gui2_core::disable_scrolling(screen);
  auto* layer=lv_obj_create(screen); lv_obj_remove_style_all(layer);
  lv_obj_set_size(layer,1440,3100); gui2_core::disable_scrolling(layer);
  host.initialize(layer, ui); router.set_builder(build_routed_page);
  assert(router.navigate(page_kind::INSTALL,nullptr,page_transition::PUSH));
  assert(router.navigate(page_kind::INSTALL_CONFIRM,nullptr,page_transition::PUSH));
  advance(500);
  auto* source_page=host.current_page();
  auto* body=lv_obj_get_child(host.content(),0);
  auto* card=lv_obj_get_child(body,index+2);
  lv_obj_scroll_to_view(card,LV_ANIM_OFF);lv_obj_update_layout(screen);
  auto* text=lv_obj_get_child(card,0);
  lv_point_t target=center(lv_obj_get_child(text,0));
  if(mode=="detail")target=center(lv_obj_get_child(text,1));
  if(mode=="arrow")target=center(lv_obj_get_child(card,1));
  if(mode=="blank"){lv_area_t a;lv_obj_get_coords(card,&a);target={a.x1+4,(a.y1+a.y2)/2};}
  point(target,true);
  if(mode=="drag-out") point({0,0},true);
    point(position,false);
  if(mode=="drag-out") {
    assert(navigations==2 && host.current_page()==source_page);
    assert(router.current()==page_kind::INSTALL_CONFIRM);
  } else {
    assert(navigations==3 && host.current_page()!=source_page);
    assert(router.current()==page_kind::INSTALL_CONFIRM);
    assert(last_page==page_kind::INSTALL_CONFIRM && last_transition==page_transition::REPLACE);
    assert(page_state.install_target_mount==install_targets[index].mount_point);
    auto* rebuilt_body=lv_obj_get_child(host.content(),0);
    auto* rebuilt_card=lv_obj_get_child(rebuilt_body,index+2);
    assert(lv_obj_get_style_border_width(rebuilt_card,LV_PART_MAIN)>0);
    auto* confirmed_page=host.current_page();
    assert(router.navigate(page_kind::INSTALL,nullptr,page_transition::POP));
    assert(router.current()==page_kind::INSTALL && last_transition==page_transition::POP);
    assert(host.current_page()!=confirmed_page);
    assert(router.navigate(page_kind::INSTALL_CONFIRM,nullptr,page_transition::PUSH));
    assert(router.current()==page_kind::INSTALL_CONFIRM && last_transition==page_transition::PUSH);
    assert(page_state.install_target_mount==install_targets[index].mount_point);
    advance(500);
    lv_area_t track_area; lv_obj_get_coords(confirm_track,&track_area);
    lv_area_t knob_area; lv_obj_get_coords(lv_obj_get_child(confirm_track,2),&knob_area);
    lv_point_t knob_center={(knob_area.x1+knob_area.x2)/2,(knob_area.y1+knob_area.y2)/2};
    point(knob_center,true);
    point({track_area.x2-60,knob_center.y},true);
    assert(page_state.install_confirm.progress()==1000);
    point(position,false);
    assert(backend.calls==1);
    assert(backend.path==page_state.install_selection);
    assert(backend.target==install_targets[index].mount_point);
    assert(backend.both_slots==page_state.install_both_slots);
    assert(router.current()==page_kind::INSTALL_PROGRESS);
    assert(last_page==page_kind::INSTALL_PROGRESS&&last_transition==page_transition::PUSH);
  }
  printf("PASS image target %d %s routes=%d destination=%d\n",index,mode.c_str(),navigations,int(router.current()));
  host.clear(); lv_deinit();
}
