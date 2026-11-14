#include "pages/page_router.h"
#include "pages/action_definitions.h"
#include "pages/tool_pages.h"
#include "shell/page_host.h"
#include "gui2_svg_cache.h"
using page_kind = gui2_pages::page_id;
using action_id = gui2_pages::action_id;
using action_definition = gui2_pages::action_definition;
using page_transition = gui2_core::page_transition;
#include "worker_base.inc"

static gui2_shell::page_host host;
static gui2_pages::page_router page_router;
static unsigned backup_builds=0, progress_builds=0;
static bool allow_click=true;
static bool accept_click(lv_event_t*) { return allow_click; }
static void build_page(const gui2_pages::page_request&);
static void navigate_to(page_kind id, const void* payload=nullptr,
                        page_transition transition=page_transition::PUSH) {
  page_router.navigate(id,payload,transition);
}
static std::string textarea_text(lv_obj_t* input) {
  return input ? lv_textarea_get_text(input) : "";
}

static void reset_views() {
  page_state.tool_progress={};
  page_state.backup_view={};
}
static void show_backup_page(page_transition transition) {
  reset_views(); ++backup_builds;
  auto scaffold=host.build("Backup","",0,transition,true);
  page_state.backup_view.name_input=lv_textarea_create(scaffold.content);
  lv_textarea_set_one_line(page_state.backup_view.name_input,true);
  lv_textarea_set_text(page_state.backup_view.name_input,page_state.backup_name.c_str());
}
static void show_action_page(const action_definition& definition, page_transition transition) {
  assert(definition.id==action_id::BACKUP);
  show_backup_page(transition);
}
#include "back.inc"
#include "entry.inc"
static void show_tool_progress_page(page_transition transition) {
  reset_views(); ++progress_builds;
  auto scaffold=host.build(tool_job_request.title.c_str(),tool_job_request.running,0,transition,false);
  gui2_pages::progress_page_options options;
  options.content=scaffold.content; options.metrics=&gui2_core::ui; options.strings=&strings();
  options.subtitle=scaffold.summary; options.console_font=gui2_core::ui.text_font;
  options.initial_text=tool_job_request.running; options.page_layer=host.current_page();
  options.left_action={"Back",progress_back_cb};
  options.right_action={"Reboot",nullptr};
  page_state.tool_progress=gui2_pages::build_progress_page(options);
  refresh_tool_progress();
}
#include "routes.inc"
static void route(const gui2_pages::page_request& request) {
  if (request.id==page_kind::SELECT_STORAGE) {
    reset_views(); host.build("Select Storage","",0,request.transition,true);
  } else build_page(request);
  host.settle();
}
static void advance(unsigned duration) {
  for(unsigned n=0;n<duration;n+=20) {
    if(page_state.tool_progress.body) refresh_tool_progress();
    lv_tick_inc(20); lv_timer_handler();
  }
}
static lv_obj_t* button(lv_event_cb_t callback, void* data=nullptr) {
  auto* obj=lv_button_create(lv_layer_top());
  lv_obj_add_event_cb(obj,callback,LV_EVENT_CLICKED,data);
  return obj;
}
int main(int argc,char** argv) {
  assert(argc==2); std::string scenario=argv[1];
  lv_init();auto* display=lv_display_create(1440,3200);
  std::vector<uint32_t> pixels(1440*64);
  lv_display_set_color_format(display,LV_COLOR_FORMAT_XRGB8888);
  lv_display_set_buffers(display,pixels.data(),nullptr,pixels.size()*4,LV_DISPLAY_RENDER_MODE_PARTIAL);
  lv_display_set_flush_cb(display,flush);
  auto& ui=gui2_core::ui;static_cast<gui2_core::ui_palette&>(ui)=gui2_core::palette(true);
  ui.width=1440;ui.height=3200;ui.scale=1.2f;ui.status_height=100;ui.outer_margin=48;
  ui.content_left=48;ui.content_width=1344;ui.nav_height=156;ui.card_gap=24;ui.cards_top_gap=24;
  ui.heading_top=48;ui.heading_height=180;ui.card_height=192;ui.icon_size=100;
  ui.text_font=ui.status_font=ui.brand_font=&lv_font_montserrat_16;
  auto* layer=lv_obj_create(lv_screen_active());lv_obj_remove_style_all(layer);
  lv_obj_set_size(layer,1440,3100);gui2_core::disable_scrolling(layer);
  host.initialize(layer,ui);page_router.set_builder(route);
  action_definition definition{}; definition.id=action_id::BACKUP;
  auto* home=button(action_card_event_cb,&definition);
  auto* refresh=button(backup_refresh_sizes_cb);
  auto* storage=button(backup_select_storage_cb);
  if(scenario=="direct-backup") navigate_to(page_kind::BACKUP);
  else lv_obj_send_event(home,LV_EVENT_CLICKED,nullptr);
  if(scenario=="storage-return") {
    lv_obj_send_event(storage,LV_EVENT_CLICKED,nullptr);
    assert(page_router.current()==page_kind::SELECT_STORAGE);
    navigate_back(); // The production return from this page normalizes to BACKUP.
    assert(page_router.current()==page_kind::BACKUP);
  }
  advance(300);
  const int cycles=scenario=="home-repeated" ? 5 : 1;
  for(int cycle=0;cycle<cycles;++cycle) {
    const auto origin=page_router.current_request();
    const auto before=backup_builds;
    std::string name=scenario=="home-custom-name" ? "my backup" : "";
    lv_textarea_set_text(page_state.backup_view.name_input,name.c_str());
    {std::lock_guard lock(PartitionManager.mutex);PartitionManager.release=false;PartitionManager.entered=false;}
    // Rejected clicks neither start a worker nor change the route.
    allow_click=false;lv_obj_send_event(refresh,LV_EVENT_CLICKED,nullptr);allow_click=true;
    assert(page_router.current()==origin.id && starts==static_cast<unsigned>(cycle));
    lv_obj_send_event(refresh,LV_EVENT_CLICKED,nullptr);PartitionManager.wait();
    assert(page_router.current()==page_kind::TOOL_PROGRESS);
    assert(tool_job_request.back.id==origin.id && tool_job_request.after.id==origin.id);
    if(scenario=="home-precompleted") {PartitionManager.finish();await_done();}
    advance(300);
    if(scenario!="home-precompleted") {
      assert(lv_obj_is_hidden(page_state.tool_progress.actions));
      navigate_back();assert(page_router.current()==page_kind::TOOL_PROGRESS);
      PartitionManager.finish();await_done();
    }
    advance(200);
    auto* actions=page_state.tool_progress.actions;
    assert(!lv_obj_is_hidden(actions) && lv_obj_is_hidden(page_state.tool_progress.bar));
    assert(!page_state.tool_progress.sweeping);
    lv_obj_send_event(lv_obj_get_child(actions,0),LV_EVENT_CLICKED,nullptr);
    advance(300);
    bool restored=backup_builds==before+1 && page_state.backup_view.name_input &&
        !page_state.tool_progress.body && page_router.current_request().id==origin.id &&
        page_router.current_request().payload==origin.payload;
    if(!restored) {
      fprintf(stderr,"RETURN_BROKEN origin=%d payload=%p returned=%d payload=%p backup_builds=%u expected=%u stale_progress=%d worker_idle=%d\n",
              int(origin.id),origin.payload,int(page_router.current()),page_router.current_request().payload,
              backup_builds,before+1,page_state.tool_progress.body!=nullptr,
              tools->status()==gui2_backend::tool_state::IDLE);
      return 1;
    }
    assert(textarea_text(page_state.backup_view.name_input)==name);
    assert(tools->status()==gui2_backend::tool_state::IDLE);
    assert(lv_obj_get_child_count(layer)==1 && lv_obj_get_x(host.current_page())==0);
  }
  assert(starts==ends && progress_builds==static_cast<unsigned>(cycles));
  host.clear();advance(100);gui2_svg_cache_clear();lv_deinit();
  printf("PASS %s cycles=%d complete_route_restored=1 no_stale_progress=1 worker_idle=1\n",argv[1],cycles);
}
