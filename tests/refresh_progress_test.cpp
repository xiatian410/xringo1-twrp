// Original state-to-page adapter and actual LVGL. Worker/DRM are explicit boundaries.
#include <cassert>
#include <string>
#include <vector>
#include "lvgl.h"
#include "core/ui_helpers.h"
#include "pages/progress_page.h"
#include "backend/tools_backend.h"
struct Tools {gui2_backend::tool_state state;gui2_backend::tool_state status(){return state;}};
static Tools object;static Tools*tools=&object;
static struct {gui2_pages::progress_page_view tool_progress;}page_state;
static struct {const char*running="Refreshing partition info";const char*done="Refresh complete";}tool_job_request;
namespace gui2_i18n {extern const language_pack kEnglish;}
static const auto&strings(){return gui2_i18n::kEnglish;}
#include "callback.inc"
static unsigned frames=0;
static void flush(lv_display_t*d,const lv_area_t*,uint8_t*){++frames;lv_display_flush_ready(d);}
int main(int argc,char**argv){
 assert(argc==2);bool fail=std::string(argv[1])=="failed";bool immediate=std::string(argv[1])=="immediate";
 lv_init();auto*d=lv_display_create(1440,3200);std::vector<uint32_t>pixels(1440*64);
 lv_display_set_color_format(d,LV_COLOR_FORMAT_XRGB8888);lv_display_set_buffers(d,pixels.data(),nullptr,pixels.size()*4,LV_DISPLAY_RENDER_MODE_PARTIAL);lv_display_set_flush_cb(d,flush);
 auto&ui=gui2_core::ui;static_cast<gui2_core::ui_palette&>(ui)=gui2_core::palette(true);
 ui.width=1440;ui.height=3200;ui.scale=1.2f;ui.status_height=100;ui.outer_margin=48;ui.content_left=48;ui.content_width=1344;ui.nav_height=156;ui.card_gap=24;ui.cards_top_gap=24;ui.heading_height=180;ui.card_height=192;ui.icon_size=100;
 ui.text_font=ui.status_font=ui.brand_font=&lv_font_montserrat_16;
 auto*screen=lv_screen_active();auto*subtitle=lv_label_create(screen);auto*content=lv_obj_create(screen);lv_obj_set_pos(content,0,250);lv_obj_set_size(content,1440,2700);
 gui2_pages::progress_page_options o;o.content=content;o.metrics=&ui;o.strings=&strings();o.subtitle=subtitle;o.console_font=ui.text_font;o.initial_text=tool_job_request.running;
 page_state.tool_progress=gui2_pages::build_progress_page(o);assert(page_state.tool_progress.body&&page_state.tool_progress.bar);
 object.state=immediate?gui2_backend::tool_state::DONE:gui2_backend::tool_state::RUNNING;refresh_tool_progress();
 if(!immediate){assert(std::string(lv_label_get_text(subtitle))==tool_job_request.running);object.state=fail?gui2_backend::tool_state::FAILED:gui2_backend::tool_state::DONE;}
 for(int n=0;n<20;n++){refresh_tool_progress();lv_tick_inc(100);lv_timer_handler();}
 assert(std::string(lv_label_get_text(subtitle))==(fail?strings().operation_failed:tool_job_request.done));
 assert(lv_obj_has_flag(page_state.tool_progress.bar,LV_OBJ_FLAG_HIDDEN));assert(frames>0);
 printf("PASS %s frames=%u subtitle=%s\n",argv[1],frames,lv_label_get_text(subtitle));
}
