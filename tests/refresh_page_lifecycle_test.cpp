// Reuse the real worker extraction and declared boundaries from the prior test.
#define main worker_leaf_main
#include "refresh_worker_chain_test.cpp"
#undef main
#include "shell/page_host.h"
#include "pages/page_router.h"
#include "gui2_svg_cache.h"

static gui2_shell::page_host host;
static gui2_pages::page_router router;
static unsigned backs=0,deleted=0;
static void deleted_cb(lv_event_t*){++deleted;}
static void back_cb(lv_event_t*) {
  if(tools->status()==gui2_backend::tool_state::RUNNING)return;
  tools->acknowledge();++backs;
  router.navigate(gui2_pages::page_id::BACKUP,nullptr,gui2_core::page_transition::POP);
}
static void reboot_cb(lv_event_t*){assert(false);}
static void build(const gui2_pages::page_request& request) {
  // Same ownership order as create_page_scaffold: forget old progress pointers,
  // build scaffold, then bind the view to the new page root and subtitle.
  page_state.tool_progress={};
  const bool progress=request.id==gui2_pages::page_id::TOOL_PROGRESS;
  auto scaffold=host.build(progress?"Refresh Sizes":"Backup",progress?tool_job_request.running:"",0,request.transition,!progress);
  if(progress){
    gui2_pages::progress_page_options o;o.content=scaffold.content;o.metrics=&gui2_core::ui;o.strings=&strings();o.subtitle=scaffold.summary;o.console_font=gui2_core::ui.text_font;o.initial_text=tool_job_request.running;o.page_layer=host.current_page();o.left_action={"Back",back_cb};o.right_action={"Reboot",reboot_cb};
    page_state.tool_progress=gui2_pages::build_progress_page(o);
    lv_obj_add_event_cb(page_state.tool_progress.body,deleted_cb,LV_EVENT_DELETE,nullptr);
    refresh_tool_progress();
  }
  host.settle();
}
static void advance(unsigned duration){for(unsigned n=0;n<duration;n+=20){if(page_state.tool_progress.body)refresh_tool_progress();lv_tick_inc(20);lv_timer_handler();}}
int main(int argc,char**argv){
  assert(argc==2);const std::string scenario=argv[1];
  lv_init();auto*d=lv_display_create(1440,3200);std::vector<uint32_t>pixels(1440*64);
  lv_display_set_color_format(d,LV_COLOR_FORMAT_XRGB8888);lv_display_set_buffers(d,pixels.data(),nullptr,pixels.size()*4,LV_DISPLAY_RENDER_MODE_PARTIAL);lv_display_set_flush_cb(d,flush);
  auto&ui=gui2_core::ui;static_cast<gui2_core::ui_palette&>(ui)=gui2_core::palette(true);
  ui.width=1440;ui.height=3200;ui.scale=1.2f;ui.status_height=100;ui.outer_margin=48;ui.content_left=48;ui.content_width=1344;ui.nav_height=156;ui.card_gap=24;ui.cards_top_gap=24;ui.heading_top=48;ui.heading_height=180;ui.card_height=192;ui.icon_size=100;ui.text_font=ui.status_font=ui.brand_font=&lv_font_montserrat_16;
  auto*layer=lv_obj_create(lv_screen_active());lv_obj_remove_style_all(layer);lv_obj_set_size(layer,1440,3100);gui2_core::disable_scrolling(layer);
  host.initialize(layer,ui);router.set_builder(build);router.navigate(gui2_pages::page_id::BACKUP);advance(300);
  const int cycles=scenario=="reuse"?8:1;
  for(int n=0;n<cycles;++n){
    {std::lock_guard lock(PartitionManager.mutex);PartitionManager.release=false;PartitionManager.entered=false;}
    assert(tools->start(gui2_backend::tool_job::REFRESH_SIZES,"",""));PartitionManager.wait();
    if(scenario=="already-done"){PartitionManager.finish();await_done();}
    router.navigate(gui2_pages::page_id::TOOL_PROGRESS);advance(300);
    auto&v=page_state.tool_progress;assert(lv_obj_get_parent(v.actions)==host.current_page());
    assert(lv_obj_get_x(host.current_page())==0);
    if(scenario!="already-done"){
      assert(lv_obj_is_hidden(v.actions));assert(!lv_obj_is_hidden(v.bar));
      back_cb(nullptr);assert(backs==static_cast<unsigned>(n));
      PartitionManager.finish();await_done();
    }
    advance(200);assert(std::string(lv_label_get_text(v.subtitle))==tool_job_request.done);
    assert(!lv_obj_is_hidden(v.actions)&&lv_obj_is_hidden(v.bar)&&!v.sweeping);
    lv_obj_t*back=lv_obj_get_child(v.actions,0);lv_obj_send_event(back,LV_EVENT_CLICKED,nullptr);
    advance(300);assert(router.current()==gui2_pages::page_id::BACKUP);
    assert(tools->status()==gui2_backend::tool_state::IDLE);assert(!page_state.tool_progress.body);
    assert(deleted==static_cast<unsigned>(n+1)&&backs==deleted);
    // One settled page remains; no orphaned action row/transition blocker.
    assert(lv_obj_get_child_count(layer)==1);assert(lv_obj_get_x(host.current_page())==0);
  }
  host.clear();advance(100);assert(lv_obj_get_child_count(layer)==0);gui2_svg_cache_clear();lv_deinit();
  printf("PASS %s cycles=%d deleted=%u backs=%u frames=%u\n",argv[1],cycles,deleted,backs,frames);
}
