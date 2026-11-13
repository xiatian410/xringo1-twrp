// Original page callbacks/builders and asynchronous worker; manager is a fixture.
#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include "lvgl.h"
#include "backend/twrp_tools_backend.h"
#include "components/swipe_slider.h"
#include "components/check_row.h"
#include "core/ui_helpers.h"
#include "core/ui_event_guard.h"
#include "pages/page_router.h"
#include "pages/progress_page.h"
#include "pages/console_window.h"
#include "pages/tool_pages.h"
#include "pages/wipe_page.h"
#include "shell/page_host.h"
#include "gui2_svg_cache.h"
#include "twrp_operation_executor.h"

using page_kind=gui2_pages::page_id;
using page_transition=gui2_core::page_transition;
using gui2_core::accept_click;
using gui2_core::press_cancel_guard_cb;
static auto&ui=gui2_core::ui;
namespace gui2_i18n {extern const language_pack kEnglish;}
static const auto&strings(){return gui2_i18n::kEnglish;}
namespace gui2_pages {
#include "wipe_height.inc"
}
static struct Manager {
 std::mutex mutex;std::condition_variable cv;bool entered=false,release=false,success=true;
 unsigned calls=0,updates=0,details=0;std::string target,value,job,fs="f2fs";
 bool perform(const std::string&t,const std::string&v,const char*j){
  std::unique_lock lock(mutex);target=t;value=v;job=j;++calls;entered=true;cv.notify_all();
  assert(cv.wait_for(lock,std::chrono::seconds(10),[&]{return release;}));
  if(job=="format")fs=v;return success;
 }
 bool RepairByPath(const std::string&t,bool){return perform(t,"","repair");}
 bool ResizeByPath(const std::string&t,bool){return perform(t,"","resize");}
 bool WipeByPath(const std::string&t,const std::string&v){return perform(t,v,"format");}
 void UpdateSystemDetails(){++updates;}
 void wait(){std::unique_lock l(mutex);assert(cv.wait_for(l,std::chrono::seconds(3),[&]{return entered;}));}
 void finish(){std::lock_guard l(mutex);release=true;cv.notify_all();}
}PartitionManager;
static std::atomic<unsigned>starts=0,ends=0;static bool allowed=true;
static int last_result=-1;
namespace DataManager {static std::string GetStrValue(const char*){return "/fixture/backups";}}
#define TW_BACKUPS_FOLDER_VAR "backups"
namespace gui2_console {template<class...T>void log_error(T...) {}}
namespace gui2_backend {
static bool partition_tool_target_allowed(const std::string&p){return allowed&&p=="/fixture";}
static void operation_start(const char*){++starts;}
static void operation_end(int v){last_result=v;++ends;}
template<class...T>static int unused(T...){assert(false);return 1;}
static int manage_backup(const std::string&,const std::string&,const std::string&,bool){return unused();}
static int applycustomtwrpfolder(const std::string&){return unused();}
static int cmd(const std::string&){return unused();}
static int refreshsizes(){return unused();}static int fixabrecoverybootloop(){return unused();}
static int mergesnapshots(){return unused();}static int disableAVB2(){return unused();}
static int copylog(){return unused();}static int fixcontexts(){return unused();}
static int unmapsuperdevices(){return unused();}static int reflashtwrp(){return unused();}
static int repackimage(){return unused();}
bool twrp_tools_backend::details(const std::string&t,partition_details*out){
 assert(t=="/fixture"&&status()!=tool_state::RUNNING);++PartitionManager.details;
 *out={};out->name="Fixture";out->mount_point=t;out->file_system=PartitionManager.fs;
 out->present=out->can_repair=out->can_resize=true;out->file_systems={"ext4","f2fs"};return true;
}
tool_availability twrp_tools_backend::availability(){assert(false);return {};}
std::string twrp_tools_backend::twrp_folder(){assert(false);return {};}
std::string twrp_tools_backend::storage_path(){assert(false);return {};}
bool twrp_tools_backend::path_exists(const std::string&){assert(false);return false;}
bool twrp_tools_backend::users_locked(){assert(false);return false;}
#include "worker.inc"
}
static gui2_backend::twrp_tools_backend backend;
static gui2_backend::tools_backend*tools=&backend;
static gui2_backend::hardware_settings*hardware=nullptr;
struct Settings {void set(const char*,const char*){assert(false);}std::string get_string(const char*,const char*){assert(false);return {};}
 int get_int(const char*,int){assert(false);return 0;}};
static Settings*settings=nullptr;
static struct {
 std::string partition_mount_point="/fixture";int change_fs_selected=-1,console_font_index=0;
 gui2_components::swipe_slider change_fs_confirm,tool_confirm;
 gui2_pages::progress_page_view tool_progress;gui2_pages::console_window tool_console;
 bool tool_console_armed=false;unsigned tool_last_poll_ms=0;
}page_state;
static gui2_shell::page_host host;
static gui2_pages::page_router page_router;
static lv_obj_t*page_layer=nullptr,*main_content=nullptr,*page_summary=nullptr;
static const lv_font_t*runtime_console_fonts[3]={&lv_font_montserrat_16,&lv_font_montserrat_16,&lv_font_montserrat_16};
#include "request.inc"
static tool_request tool_job_request;
#include "partition_state.inc"
static void build(const gui2_pages::page_request&);
static void navigate_to(page_kind p,const void*data=nullptr,page_transition t=page_transition::PUSH){assert(page_router.navigate(p,data,t));}
static std::string format_text(const char*,const std::string&,const std::string& = std::string());
static gui2_pages::page_request page_at(page_kind,const void* =nullptr);
static int bottom_swipe_reserved();
static void tool_confirmed(void*);
static void tool_check_event_cb(lv_event_t*);
static void progress_back_cb(lv_event_t*);
static void progress_reboot_system_cb(lv_event_t*){assert(false);}
static void add_progress_actions(gui2_pages::progress_page_options*);
static void poll_tool_console(){} // Console pagination is separate existing evidence.
static void create_page_scaffold(page_kind,bool,const char*title,const char*summary,int reserve=0,page_transition t=page_transition::NONE){
#include "reset.inc"
 auto scaffold=host.build(title,summary,reserve,t,true);page_layer=host.current_page();main_content=scaffold.content;page_summary=scaffold.summary;
}
#include "back.inc"
#include "callbacks.inc"
static void build(const gui2_pages::page_request&r){
 switch(r.id){
 case page_kind::PARTITION_OPTIONS:show_partition_options_page(r.transition);break;
 case page_kind::CHANGE_FS:show_change_fs_page(r.transition);break;
 case page_kind::TOOL_CONFIRM:show_tool_confirm_page(r.transition);break;
 case page_kind::TOOL_PROGRESS:show_tool_progress_page(r.transition);break;
 default:assert(false);
 }host.settle();
}
static lv_point_t pointer_position;static bool pointer_down=false;static unsigned frames=0;
static void read_pointer(lv_indev_t*,lv_indev_data_t*d){d->point=pointer_position;d->state=pointer_down?LV_INDEV_STATE_PRESSED:LV_INDEV_STATE_RELEASED;}
static void flush(lv_display_t*d,const lv_area_t*,uint8_t*){++frames;lv_display_flush_ready(d);}
static void advance(unsigned ms){for(unsigned n=0;n<ms;n+=10){if(page_state.tool_progress.body)refresh_tool_progress();lv_tick_inc(10);lv_timer_handler();}}
static lv_point_t center(lv_obj_t*o){lv_area_t a;lv_obj_get_coords(o,&a);return {(a.x1+a.x2)/2,(a.y1+a.y2)/2};}
static void point(lv_point_t p,bool down){pointer_position=p;pointer_down=down;advance(50);}
static void click(lv_obj_t*o){lv_obj_scroll_to_view(o,LV_ANIM_OFF);lv_obj_update_layout(lv_screen_active());point(center(o),true);point(pointer_position,false);advance(300);}
static void swipe(){
 auto*track=lv_obj_get_child(page_layer,-1);auto*knob=lv_obj_get_child(track,2);
 auto start=center(knob);lv_area_t bounds;lv_obj_get_coords(track,&bounds);
 point(start,true);for(int i=1;i<=8;++i)point({start.x+(bounds.x2-start.x)*i/8,start.y},true);
 point(pointer_position,false);advance(300);
}
int main(int argc,char**argv){
 assert(argc==2);const std::string name=argv[1];
 lv_init();auto*display=lv_display_create(480,960);std::vector<uint32_t>pixels(480*64);
 lv_display_set_color_format(display,LV_COLOR_FORMAT_XRGB8888);lv_display_set_buffers(display,pixels.data(),nullptr,pixels.size()*4,LV_DISPLAY_RENDER_MODE_PARTIAL);lv_display_set_flush_cb(display,flush);
 auto*pointer=lv_indev_create();lv_indev_set_type(pointer,LV_INDEV_TYPE_POINTER);lv_indev_set_read_cb(pointer,read_pointer);gui2_core::configure_click_guard(pointer,nullptr);
 static_cast<gui2_core::ui_palette&>(ui)=gui2_core::palette(true);ui.width=480;ui.height=960;ui.scale=.4f;ui.status_height=30;ui.outer_margin=16;ui.content_left=16;ui.content_width=448;ui.nav_height=52;ui.card_gap=8;ui.cards_top_gap=8;ui.heading_top=16;ui.heading_height=60;ui.card_height=64;ui.icon_size=32;ui.text_font=ui.status_font=ui.brand_font=&lv_font_montserrat_16;
 auto*layer=lv_obj_create(lv_screen_active());lv_obj_remove_style_all(layer);lv_obj_set_size(layer,480,930);gui2_core::disable_scrolling(layer);host.initialize(layer,ui);page_router.set_builder(build);
 const bool format=name.starts_with("format"),resize=name.starts_with("resize");
 const int cycles=name=="format-reuse"?2:1;
 for(int cycle=0;cycle<cycles;++cycle){
  navigate_to(page_kind::PARTITION_OPTIONS,nullptr,page_transition::NONE);advance(300);
  auto*body=lv_obj_get_child(main_content,0);auto*action=lv_obj_get_child(body,format?3:resize?2:1);click(lv_obj_get_child(lv_obj_get_child(action,0),0));
  assert(page_router.current()==(format?page_kind::CHANGE_FS:page_kind::TOOL_CONFIRM));
  if(name=="confirm-back"){navigate_back();advance(300);assert(page_router.current()==page_kind::PARTITION_OPTIONS&&PartitionManager.calls==0);break;}
  if(format){
   assert(page_state.change_fs_selected==-1);swipe();assert(PartitionManager.calls==static_cast<unsigned>(cycle));
   if(name=="format-unselected")break;
   auto*choices=lv_obj_get_child(main_content,0);click(lv_obj_get_child(lv_obj_get_child(choices,2),0));
   assert(page_state.change_fs_selected==0&&page_router.current()==page_kind::CHANGE_FS);
  }
  if(name=="format-rejected"){
   allowed=false;swipe();assert(page_router.current()==page_kind::CHANGE_FS&&tools->status()==gui2_backend::tool_state::IDLE&&PartitionManager.calls==0&&page_state.change_fs_confirm.progress()==0);allowed=true;
  }
  {std::lock_guard l(PartitionManager.mutex);PartitionManager.entered=false;PartitionManager.release=false;PartitionManager.success=!name.ends_with("failure");}
  swipe();PartitionManager.wait();assert(page_router.current()==page_kind::TOOL_PROGRESS);
  assert(tools->status()==gui2_backend::tool_state::RUNNING);assert(lv_obj_is_hidden(page_state.tool_progress.actions));
  assert(tool_job_request.target=="/fixture"&&tool_job_request.value==(format?"ext4":""));
  assert(!tools->start(tool_job_request.job,"/other","wrong"));navigate_back();assert(page_router.current()==page_kind::TOOL_PROGRESS);
  PartitionManager.finish();auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(3);
  while(tools->status()==gui2_backend::tool_state::RUNNING){assert(std::chrono::steady_clock::now()<deadline);std::this_thread::yield();}
  advance(100);assert(tools->status()==(PartitionManager.success?gui2_backend::tool_state::DONE:gui2_backend::tool_state::FAILED));
  assert(last_result==(PartitionManager.success?0:1));assert(!lv_obj_is_hidden(page_state.tool_progress.actions));assert(lv_obj_is_hidden(page_state.tool_progress.bar));
  assert(std::string(lv_label_get_text(page_state.tool_progress.subtitle))==(PartitionManager.success?tool_job_request.done:strings().operation_failed));
  assert(PartitionManager.target=="/fixture"&&PartitionManager.value==(format?"ext4":""));
  const auto details=PartitionManager.details;click(lv_obj_get_child(page_state.tool_progress.actions,0));
  assert(page_router.current()==page_kind::PARTITION_OPTIONS&&tools->status()==gui2_backend::tool_state::IDLE);
  assert(PartitionManager.details==details+1&&partition_info.file_system==(format?"ext4":"f2fs"));
  assert(!page_state.tool_progress.body&&lv_obj_get_child_count(layer)==1);
 }
 assert(starts==ends&&ends==PartitionManager.calls&&frames>0);
 host.clear();gui2_svg_cache_clear();lv_deinit();
 printf("PASS %s calls=%u updates=%u details=%u starts=%u ends=%u frames=%u\n",name.c_str(),PartitionManager.calls,PartitionManager.updates,PartitionManager.details,starts.load(),ends.load(),frames);
}
