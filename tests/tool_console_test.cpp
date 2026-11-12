// Original worker + progress UI methods. Scan, console producer and flush are fixtures.
#define main original_worker_main
#include "refresh_worker_chain_test.cpp"
#undef main
#include "pages/console_window.h"
#include "backend/console_backend.h"

static auto& ui = gui2_core::ui;
struct History : gui2_backend::console_backend {
  size_t total=5000, generation=1, reads=0, unbounded=0;
  bool busy=false;
  size_t fetch(size_t from,std::vector<gui2_backend::console_line>* out) override {
    ++unbounded;
    for(size_t i=from;i<total;++i)out->push_back({"history "+std::to_string(i),{},i});
    return total;
  }
  gui2_backend::console_read_result fetch_bounded(const gui2_backend::console_cursor& c,
      const gui2_backend::console_read_limits& lim,std::vector<gui2_backend::console_line>* out) override {
    ++reads;
    if(busy)return {c,0,false,true};
    auto next=c;next.generation=generation;
    if(c.generation!=generation)return {next,total,true,false};
    size_t n=0,bytes=0;
    while(next.line<total && n<lim.max_lines && n<lim.max_messages){
      const auto text="history "+std::to_string(next.line);
      if(bytes+text.size()>lim.max_bytes)break;
      if(out)out->push_back({text,{},next.line});
      ++next.line;++n;bytes+=text.size();
    }
    return {next,total,next.line<total,false};
  }
  void set_language(const std::string&) override {}
  void retranslate(const std::string&) override {}
} history;
static gui2_backend::console_backend* console=&history;
static bool shell_ready=true;
static size_t page_sequence=1,rendered_page_sequence=0;
static bool rendered_install_page=false,rendered_decrypt_page=false,rendered_tool_page=false;
static bool rendered_backup_page=false,rendered_restore_page=false,rendered_wipe_page=false,rendered_sideload_page=false,rendered_fastbootd_page=false;
enum class page_kind { INSTALL_PROGRESS, DECRYPT_PROGRESS, TOOL_PROGRESS, BACKUP, BACKUP_PROGRESS, RESTORE_PROGRESS, WIPE_PROGRESS, SIDELOAD_PROGRESS, FASTBOOTD };
static struct {page_kind id=page_kind::TOOL_PROGRESS;page_kind current(){return id;}} page_router;
static struct {void process_after_present(){}} screen_actions;
#include "console_callbacks.inc"
#ifdef PROGRESS_PAGE_TEST
#include "selected_console.inc"
#endif

#ifdef PROGRESS_PAGE_TEST
static auto& tested_window=page_state.SELECTED_WINDOW;
static auto& tested_armed=page_state.SELECTED_ARMED;
#else
static auto& tested_window=page_state.tool_console;
static auto& tested_armed=page_state.tool_console_armed;
#endif
static void tick_console() {
  const auto prior=history.reads;
  refresh_tool_progress();
#ifdef PROGRESS_PAGE_TEST
  selected_poll();
#else
  poll_tool_console();
#endif
  assert(history.reads-prior<=1 && history.unbounded==0);
  assert(tested_window.rows.size()<=160);
  lv_tick_inc(100);lv_timer_handler();
}
int main(int argc,char**argv){
  assert(argc==2);const std::string scenario=argv[1];
  lv_init();auto*d=lv_display_create(1440,3200);std::vector<uint32_t> pixels(1440*64);
  lv_display_set_color_format(d,LV_COLOR_FORMAT_XRGB8888);lv_display_set_buffers(d,pixels.data(),nullptr,pixels.size()*4,LV_DISPLAY_RENDER_MODE_PARTIAL);lv_display_set_flush_cb(d,flush);
  static_cast<gui2_core::ui_palette&>(ui)=gui2_core::palette(true);
  ui.width=1440;ui.height=3200;ui.scale=1.2f;ui.status_height=100;ui.outer_margin=48;ui.content_left=48;ui.content_width=1344;ui.nav_height=156;ui.card_gap=24;ui.cards_top_gap=24;ui.heading_height=180;ui.card_height=192;ui.icon_size=100;
  ui.text_font=ui.status_font=ui.brand_font=&lv_font_montserrat_16;
  auto*sub=lv_label_create(lv_screen_active());auto*content=lv_obj_create(lv_screen_active());lv_obj_set_size(content,1440,2700);
  auto build=[&]{
    gui2_pages::progress_page_options o;o.content=content;o.metrics=&ui;o.strings=&strings();o.subtitle=sub;o.console_font=ui.text_font;o.initial_text=tool_job_request.running;
    page_state.tool_progress=gui2_pages::build_progress_page(o);
    gui2_pages::console_window_reset(&tested_window);tested_armed=false;
#ifdef PROGRESS_PAGE_TEST
    page_state.SELECTED_VIEW=page_state.tool_progress.SELECTED_SUFFIX;
    page_router.id=page_kind::SELECTED_KIND;
#endif
  };
  build();assert(tools->start(gui2_backend::tool_job::REFRESH_SIZES,"",""));PartitionManager.wait();
  if(scenario=="already-done"){PartitionManager.finish();await_done();}
  // Opening poll must not translate/copy/render historical output before first present.
  tick_console();assert(history.reads==0 && history.unbounded==0);
  assert(!gui2_pages::console_window_frame_arms(false,true,true));
  assert(!gui2_pages::console_window_frame_arms(true,false,true));
  assert(!gui2_pages::console_window_frame_arms(true,true,false));
  gui2_loop_before_render(nullptr);
  gui2_loop_after_present(nullptr,false);assert(!tested_armed);
  ++page_sequence;gui2_loop_after_present(nullptr,true);assert(!tested_armed);
  gui2_loop_before_render(nullptr);gui2_loop_after_present(nullptr,true);
  assert(tested_armed);
  if(scenario=="busy")history.busy=true;
  if(scenario!="already-done"){PartitionManager.finish();await_done();}
  tick_console();assert(std::string(lv_label_get_text(sub))==tool_job_request.done);
  assert(lv_obj_is_hidden(page_state.tool_progress.bar));
  history.busy=false;
  for(int i=0;i<16;++i)tick_console();
  assert(!tested_window.rows.empty());
  assert(tested_window.rows.front().line_index>=4840);
  assert(tested_window.rows.back().line_index==4999);
  if(scenario=="history"){
    const auto old=tested_window.rows.front().line_index;
    lv_obj_scroll_to_y(page_state.tool_progress.console.body,0,LV_ANIM_OFF);
    for(int i=0;i<12;++i)tick_console();
    assert(tested_window.rows.front().line_index<old);
  }
  if(scenario=="generation"){
    ++history.generation;history.total=20;
    for(int i=0;i<20;++i)tick_console();
    assert(tested_window.generation==history.generation);
    assert(tested_window.rows.back().line_index==19);
  }
  if(scenario=="reentry"){
    lv_obj_delete(page_state.tool_progress.body);page_state.tool_progress={};
#ifdef PROGRESS_PAGE_TEST
    #include "selected_reset.inc"
    const auto deleted_reads=history.reads;selected_poll();assert(history.reads==deleted_reads);
#endif
    build();const auto before=history.reads;tick_console();assert(history.reads==before);
    assert(tested_window.rows.empty());tested_armed=true;
    for(int i=0;i<16;++i)tick_console();assert(tested_window.rows.back().line_index==4999);
  }
  tools->acknowledge();
  printf("PASS %s: unbounded=%zu bounded=%zu retained=%zu frames=%u\n",argv[1],history.unbounded,history.reads,tested_window.rows.size(),frames);
  lv_deinit();
}
