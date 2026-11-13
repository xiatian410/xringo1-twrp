// Original tools worker, LVGL/page host and GUI tick + app loop.
// Device services, input, performance policy and display submission are fixtures.
#include "loop_lifecycle.inc"
#include "app/gui2_loop.h"
#include "components/keyboard.h"
using page_kind = gui2_pages::page_id;
using page_transition = gui2_core::page_transition;
#include "backend/hardware_settings.h"
#include "backend/decrypt_backend.h"
#include "backend/background_backend.h"
#include <thread>

static bool shell_ready = true, splash_dismiss_pending = false, reboot_requested = false;
static bool mount_pending = false;
static std::string mount_feedback;
static uint32_t mount_feedback_finished_ms = 0;
static uint64_t storage_last_poll_ms = 0;
static std::string storage_snapshot;
static lv_obj_t* main_content = nullptr;
static lv_obj_t* mouse_cursor = nullptr;
static lv_indev_t* pointer_indev = nullptr;
static auto& ui = gui2_core::ui;
static auto& page_router = router;
static gui2_backend::hardware_settings* hardware = nullptr;
static gui2_backend::decrypt_backend* decrypt = nullptr;
static std::atomic<unsigned> tick_count = 0, background_polls = 0;
static void unexpected() { assert(false && "unrelated GUI branch reached"); }
static void poll_startup(uint64_t) {} // Startup has completed before this fixture.
static void poll_external_reboot() {} // No external reboot request.
namespace gui2_shell {
static bool splash_intro_finished() { unexpected(); return false; }
static void dismiss_splash(int*) { unexpected(); }
static lv_obj_t* create_mouse_cursor(lv_indev_t*, bool, const gui2_core::ui_metrics&) {
  unexpected(); return nullptr;
}
}
static int splash_view;
static int ev_has_mouse() { return 0; }
static void show_hardware_error(const char*) { unexpected(); }
static void set_quick_feedback(const char*) { unexpected(); }
static void complete_mount_request() {} // No mount job; exact polling is out of scope.
static void refresh_partition_list() {
  // Original refresh_partition_list returns immediately on TOOL_PROGRESS.
  assert(router.current() == gui2_pages::page_id::TOOL_PROGRESS);
}
static void refresh_mount_rows() { unexpected(); }
static std::string current_storage_snapshot() { unexpected(); return {}; }
static void navigate_to(gui2_pages::page_id, std::nullptr_t, gui2_core::page_transition) {
  unexpected();
}
static void poll_cli_command() {} // No CLI command; FIFO behavior has separate evidence.
static void advance_wheel_scroll(uint64_t) {}
static struct { void update(uint64_t) {} } screen_feedback;
static void poll_console(bool) { unexpected(); }
static void poll_install_console() { unexpected(); }
static void refresh_install_progress() { unexpected(); }
static void poll_wifi(uint64_t) {} // Wi-Fi is disabled in this configuration.
static void poll_fastbootd_console() { unexpected(); }
static unsigned console_polls = 0;
static void poll_tool_console() { ++console_polls; } // Console window checked separately.
static void refresh_sideload_progress() { unexpected(); }
static void poll_sideload_console() { unexpected(); }
static void poll_terminal() { unexpected(); }
static void refresh_wipe_progress() { unexpected(); }
static void poll_wipe_console() { unexpected(); }
static void refresh_decrypt_progress() { unexpected(); }
static void poll_decrypt_console() { unexpected(); }
static void refresh_restore_progress() { unexpected(); }
static void poll_restore_console() { unexpected(); }
static void refresh_backup_progress() { unexpected(); }
static void poll_backup_console() { unexpected(); }
class Background final : public gui2_backend::background_backend {
 public:
  void start() override { unexpected(); }
  void stop() override { unexpected(); }
  void poll() override { ++background_polls; }
  uint64_t partition_list_revision(const std::string&) override { unexpected(); return 0; }
  bool command_running() override { unexpected(); return false; }
} background_fixture;
static gui2_backend::background_backend* background = &background_fixture;
#include "loop_tick.inc"

// No actual input devices or performance service are opened.
bool gui2_input_take_activity() { return false; }
void gui2_input_set_screen_off(bool off) { assert(!off); }
bool gui2_input_take_hardware_keyboard_input() { return false; }
bool gui2_input_take_key_action(gui2_key_action*) { return false; }
int gui2_input_take_wheel() { return 0; }
bool gui2_input_take_char(int*) { return false; }
bool gui2_input_take_key(int*) { return false; }
void gui2_components::keyboard::notify_hardware_keyboard_input() { unexpected(); }
class Screen final : public gui2_backend::screen_backend {
 public:
  bool has_screenshot() const override { return false; }
  gui2_backend::capture_result save_screenshot() override { unexpected(); return {}; }
  bool has_screen_off() const override { return false; }
  bool is_screen_off() const override { return false; }
  bool screen_off() override { unexpected(); return false; }
  bool screen_on() override { unexpected(); return false; }
  void set_before_screen_off_callback(void (*)(void*), void*) override { unexpected(); }
  void on_input_activity() override { unexpected(); }
  void tick(uint64_t) override {}
  bool has_recording() const override { return false; }
  int max_recording_fps() const override { return 0; }
  int recording_fps() const override { return 0; }
  bool set_recording_fps(int) override { unexpected(); return false; }
  bool is_recording() const override { return false; }
  gui2_backend::capture_result start_recording() override { unexpected(); return {}; }
  gui2_backend::capture_result stop_recording() override { unexpected(); return {}; }
  void submit_frame(const gui2_backend::frame_view&, uint64_t) override { unexpected(); }
} screen_fixture;
static std::string scenario;
static std::atomic<bool> present_waiting = false, unblock_present = false;
static bool complete_frame = false;
static unsigned presents = 0;
static unsigned polls_during_block = 0;
static unsigned polls_after_release = 0;
static std::chrono::steady_clock::time_point started;

bool gui2_display_present(gui2_backend::screen_backend*, uint64_t) {
  ++presents;
  if (presents == 1 && scenario != "already-done") {
    assert(std::string(lv_label_get_text(page_state.tool_progress.subtitle)) == tool_job_request.running);
    PartitionManager.finish();
    if (scenario == "blocked-present") {
      present_waiting.store(true);
      while (!unblock_present.load()) std::this_thread::yield();
      // Worker is finished but no GUI tick ran inside display submission.
      assert(tools->status() == gui2_backend::tool_state::DONE);
      assert(std::string(lv_label_get_text(page_state.tool_progress.subtitle)) == tool_job_request.running);
      polls_after_release = tick_count.load();
    }
  }
  if (std::string(lv_label_get_text(page_state.tool_progress.subtitle)) == tool_job_request.done) {
    auto& v = page_state.tool_progress;
    assert(lv_obj_is_hidden(v.bar) && !v.sweeping && !lv_obj_is_hidden(v.actions));
    complete_frame = true;
  }
  return true; // Records a submission boundary, never claims DRM scanout.
}
static bool stop(void*) {
  assert(std::chrono::steady_clock::now() - started < std::chrono::seconds(5));
  return complete_frame;
}
static void tick(void* data, uint64_t now) {
  ++tick_count;
  lv_tick_inc(static_cast<uint32_t>(now) - lv_tick_get());
  gui2_loop_tick(data, now);
}
int main(int argc, char** argv) {
  assert(argc == 2);
  scenario = argv[1];
  assert(scenario == "running-to-done" || scenario == "already-done" || scenario == "blocked-present");
  lv_init();
  auto* d = lv_display_create(1440, 3200);
  std::vector<uint32_t> pixels(1440 * 64);
  lv_display_set_color_format(d, LV_COLOR_FORMAT_XRGB8888);
  lv_display_set_buffers(d, pixels.data(), nullptr, pixels.size() * 4, LV_DISPLAY_RENDER_MODE_PARTIAL);
  lv_display_set_flush_cb(d, flush);
  static_cast<gui2_core::ui_palette&>(ui) = gui2_core::palette(true);
  ui.width=1440; ui.height=3200; ui.scale=1.2f; ui.status_height=100;
  ui.outer_margin=48; ui.content_left=48; ui.content_width=1344; ui.nav_height=156;
  ui.card_gap=24; ui.cards_top_gap=24; ui.heading_top=48; ui.heading_height=180;
  ui.card_height=192; ui.icon_size=100;
  ui.text_font=ui.status_font=ui.brand_font=&lv_font_montserrat_16;
  auto* layer = lv_obj_create(lv_screen_active());
  lv_obj_remove_style_all(layer); lv_obj_set_size(layer,1440,3100);
  gui2_core::disable_scrolling(layer);
  host.initialize(layer,ui); router.set_builder(build);
  pointer_indev = lv_indev_create();
  lv_indev_set_type(pointer_indev, LV_INDEV_TYPE_POINTER);
  assert(tools->start(gui2_backend::tool_job::REFRESH_SIZES,"",""));
  PartitionManager.wait();
  if (scenario == "already-done") { PartitionManager.finish(); await_done(); }
  router.navigate(gui2_pages::page_id::TOOL_PROGRESS);
  std::thread observer;
  if (scenario == "blocked-present") {
    observer = std::thread([] {
      while (!present_waiting.load()) std::this_thread::yield();
      await_done();
      const auto before = tick_count.load();
      std::this_thread::sleep_for(std::chrono::milliseconds(220));
      assert(tick_count.load() == before);
      polls_during_block = before;
      unblock_present.store(true);
    });
  }
  started = std::chrono::steady_clock::now();
  gui2_app::loop_callbacks callbacks;
  callbacks.on_tick=tick; callbacks.should_exit=stop;
  gui2_app::run_gui2_loop(&screen_fixture,pointer_indev,nullptr,callbacks);
  if (observer.joinable()) observer.join();
  assert(complete_frame && console_polls > 0 && background_polls == tick_count);
  if (scenario == "blocked-present") {
    assert(polls_during_block == 1 && polls_after_release == 1 && tick_count > 1);
  }
  assert(starts == 1 && ends == 1 && frames > 0);
  tools->acknowledge(); host.clear(); lv_indev_delete(pointer_indev);
  gui2_svg_cache_clear(); lv_deinit();
  printf("PASS %s ticks=%u background=%u console=%u presents=%u blocked_ticks=%u resumed_ticks=%u\n",
         scenario.c_str(),tick_count.load(),background_polls.load(),console_polls,presents,
         polls_during_block,tick_count.load()-polls_after_release);
}
