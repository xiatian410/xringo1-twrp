// Real tools worker and progress adapter; scan and display output are fixtures.
#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <mutex>
#include <string>
#include <vector>
#include "lvgl.h"
#include "core/ui_helpers.h"
#include "pages/progress_page.h"
#include "backend/twrp_tools_backend.h"
#include "twrp_operation_executor.h"

static struct Scan {
  std::mutex mutex;
  std::condition_variable cv;
  bool entered=false, release=false;
  unsigned calls=0;
  void UpdateSystemDetails() {
    std::unique_lock lock(mutex); entered=true; ++calls; cv.notify_all();
    assert(cv.wait_for(lock,std::chrono::seconds(3),[&]{return release;}));
  }
  void wait() {
    std::unique_lock lock(mutex);
    assert(cv.wait_for(lock,std::chrono::seconds(3),[&]{return entered;}));
  }
  void finish(){std::lock_guard lock(mutex);release=true;cv.notify_all();}
} PartitionManager;
static std::atomic<unsigned> starts=0, ends=0;
namespace DataManager {static std::string GetStrValue(const char*) {return "/fixtures/backups";}}
#define TW_BACKUPS_FOLDER_VAR "tw_backups_folder"
namespace gui2_backend {
static void operation_start(const std::string& s){assert(s=="Refreshing Sizes");++starts;}
static void operation_end(int code){assert(code==0);++ends;}
static bool partition_tool_target_allowed(const std::string&){assert(false);return false;}
template<class... A> static int unused(A...){assert(false);return 1;}
static int repair(const std::string&s){return unused(s);}
static int resize(const std::string&s){return unused(s);}
static int changefilesystem(const std::string&a,const std::string&b){return unused(a,b);}
static int manage_backup(const std::string&,const std::string&,const std::string&,bool){assert(false);return 1;}
static int cmd(const std::string&s){return unused(s);}
static int applycustomtwrpfolder(const std::string&s){return unused(s);}
static int fixabrecoverybootloop(){return unused();}
static int mergesnapshots(){return unused();}
static int disableAVB2(){return unused();}
static int copylog(){return unused();}
static int fixcontexts(){return unused();}
static int unmapsuperdevices(){return unused();}
static int reflashtwrp(){return unused();}
static int repackimage(){return unused();}
// Vtable methods outside the refresh path must never run.
bool twrp_tools_backend::details(const std::string&,partition_details*){assert(false);return false;}
tool_availability twrp_tools_backend::availability(){assert(false);return {};}
std::string twrp_tools_backend::twrp_folder(){assert(false);return {};}
std::string twrp_tools_backend::storage_path(){assert(false);return {};}
bool twrp_tools_backend::path_exists(const std::string&){assert(false);return false;}
bool twrp_tools_backend::users_locked(){assert(false);return false;}
#include "worker.inc"
}
static gui2_backend::twrp_tools_backend object;
static gui2_backend::tools_backend*tools=&object;
static struct {gui2_pages::progress_page_view tool_progress;}page_state;
static struct {const char*running="Refreshing partition info";const char*done="Refresh complete";}tool_job_request;
namespace gui2_i18n {extern const language_pack kEnglish;}
static const auto&strings(){return gui2_i18n::kEnglish;}
#include "callback.inc"
static unsigned frames=0;
static void flush(lv_display_t*d,const lv_area_t*,uint8_t*){++frames;lv_display_flush_ready(d);}
static void await_done(){
  auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(3);
  while(tools->status()!=gui2_backend::tool_state::DONE){
    assert(std::chrono::steady_clock::now()<deadline);std::this_thread::yield();
  }
}
int main(int argc,char**argv){
  assert(argc==2);const std::string scenario=argv[1];
  const bool immediate=scenario=="already-done";
  lv_init();auto*d=lv_display_create(1440,3200);std::vector<uint32_t>pixels(1440*64);
  lv_display_set_color_format(d,LV_COLOR_FORMAT_XRGB8888);lv_display_set_buffers(d,pixels.data(),nullptr,pixels.size()*4,LV_DISPLAY_RENDER_MODE_PARTIAL);lv_display_set_flush_cb(d,flush);
  auto&ui=gui2_core::ui;static_cast<gui2_core::ui_palette&>(ui)=gui2_core::palette(true);
  ui.width=1440;ui.height=3200;ui.scale=1.2f;ui.status_height=100;ui.outer_margin=48;ui.content_left=48;ui.content_width=1344;ui.nav_height=156;ui.card_gap=24;ui.cards_top_gap=24;ui.heading_height=180;ui.card_height=192;ui.icon_size=100;
  ui.text_font=ui.status_font=ui.brand_font=&lv_font_montserrat_16;
  assert(tools->status()==gui2_backend::tool_state::IDLE);
  assert(tools->start(gui2_backend::tool_job::REFRESH_SIZES,"",""));PartitionManager.wait();
  assert(!tools->start(gui2_backend::tool_job::REFRESH_SIZES,"",""));
  tools->acknowledge();assert(tools->status()==gui2_backend::tool_state::RUNNING);
  if(immediate){PartitionManager.finish();await_done();}
  auto*screen=lv_screen_active();auto*subtitle=lv_label_create(screen);auto*content=lv_obj_create(screen);lv_obj_set_pos(content,0,250);lv_obj_set_size(content,1440,2700);
  gui2_pages::progress_page_options o;o.content=content;o.metrics=&ui;o.strings=&strings();o.subtitle=subtitle;o.console_font=ui.text_font;o.initial_text=tool_job_request.running;
  page_state.tool_progress=gui2_pages::build_progress_page(o);refresh_tool_progress();
  if(!immediate){assert(std::string(lv_label_get_text(subtitle))==tool_job_request.running);PartitionManager.finish();await_done();}
  for(int n=0;n<20;n++){refresh_tool_progress();lv_tick_inc(100);lv_timer_handler();}
  assert(std::string(lv_label_get_text(subtitle))==tool_job_request.done);
  assert(lv_obj_has_flag(page_state.tool_progress.bar,LV_OBJ_FLAG_HIDDEN));assert(frames>0);
  if(scenario=="reuse"){
    tools->acknowledge();assert(tools->status()==gui2_backend::tool_state::IDLE);
    {std::lock_guard lock(PartitionManager.mutex);PartitionManager.release=false;PartitionManager.entered=false;}
    assert(tools->start(gui2_backend::tool_job::REFRESH_SIZES,"",""));PartitionManager.wait();
    refresh_tool_progress();assert(std::string(lv_label_get_text(subtitle))==tool_job_request.running);
    PartitionManager.finish();await_done();refresh_tool_progress();
    assert(std::string(lv_label_get_text(subtitle))==tool_job_request.done);
  }
  tools->acknowledge();assert(tools->status()==gui2_backend::tool_state::IDLE);
  assert(starts==ends&&ends==PartitionManager.calls&&ends==(scenario=="reuse"?2u:1u));
  printf("PASS %s scans=%u starts=%u ends=%u frames=%u subtitle=%s\n",argv[1],PartitionManager.calls,starts.load(),ends.load(),frames,lv_label_get_text(subtitle));
}
