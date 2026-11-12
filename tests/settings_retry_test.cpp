#include <cassert>
#include <map>
#include <string>
#include "lvgl.h"

// Actual callbacks and LVGL event dispatch; storage, page routing and console
// are explicit fixtures. A flush failure represents failure before publication.
struct Store {
  std::map<std::string,std::string> values{{"tw_language","en"},{"tw_gui2_theme","0"}};
  bool write_ok=true, flush_ok=true;
  int flushes=0;
  std::string get_string(const std::string& k,const std::string& fallback) const {
    auto i=values.find(k);return i==values.end()?fallback:i->second;
  }
  int get_int(const std::string& k,int fallback) const {
    auto i=values.find(k);return i==values.end()?fallback:std::stoi(i->second);
  }
  bool set_persistent(const std::string& k,const std::string& v) {
    if(!write_ok)return false;values[k]=v;return true;
  }
  bool flush(){++flushes;return flush_ok;}
} store;
Store* settings=&store;
enum class Lang {EN,ZH};
Lang current_language=Lang::EN,pending_language=Lang::ZH;
const char* language_code(Lang l){return l==Lang::EN?"en":"zh_CN";}
struct Console {int calls=0;void retranslate(const char*){++calls;}} console_fixture;
Console* console=&console_fixture;
struct Status {int calls=0;void refresh(){++calls;}} status_controller;
struct PageState {bool language_from_decrypt=false;} page_state;
enum class page_kind {DECRYPT,ACTION};
enum class page_transition {POP};
enum class action_id {SETTINGS};
namespace gui2_pages {const int* action_definitions(){static int a=0;return &a;}}
int navigations=0,rebuilds=0;
void navigate_to(page_kind,const int*,page_transition){++navigations;}
bool accept_click(lv_event_t*){return true;}
bool theme_is_dark(){return settings==nullptr||settings->get_int("tw_gui2_theme",0)==0;}
void rebuild_for_theme(void*){++rebuilds;}
#include "callbacks.inc"

int main(int argc,char**argv) {
  assert(argc==3);const std::string kind=argv[1],scenario=argv[2];
  const bool language=kind=="language";
  lv_init();auto* display=lv_display_create(480,640);assert(display);
  auto* button=lv_obj_create(lv_screen_active());int light=1;
  lv_obj_add_event_cb(button,language?apply_language_event_cb:appearance_event_cb,
                     LV_EVENT_CLICKED,language?nullptr:&light);
  if(scenario=="write-failure")store.write_ok=false;
  if(scenario=="flush-failure"||scenario=="retry")store.flush_ok=false;
  if(scenario=="decrypt")page_state.language_from_decrypt=true;
  lv_obj_send_event(button,LV_EVENT_CLICKED,nullptr);
  lv_timer_handler();
  if(scenario=="write-failure"||scenario=="flush-failure"||scenario=="retry") {
    assert(store.values.at(language?"tw_language":"tw_gui2_theme")== (language?"en":"0"));
    assert(current_language==Lang::EN&&navigations==0&&rebuilds==0&&status_controller.calls==0);
    if(scenario=="retry") {
      store.flush_ok=true;
      lv_obj_send_event(button,LV_EVENT_CLICKED,nullptr);lv_timer_handler();
      assert(store.flushes==2);
    }
  }
  if(scenario=="success"||scenario=="retry"||scenario=="decrypt") {
    assert(store.values.at(language?"tw_language":"tw_gui2_theme")== (language?"zh_CN":"1"));
    if(language)assert(current_language==Lang::ZH&&navigations==1&&console_fixture.calls==1&&status_controller.calls==1);
    else assert(rebuilds==1&&navigations==0);
    assert(!page_state.language_from_decrypt);
  }
  lv_deinit();
}
