#!/usr/bin/env python3
"""Run the production input/screen/FF code against deterministic host backends."""
from pathlib import Path
import subprocess, tempfile, sys
RECOVERY=Path('/root/AAA/twrp/bootable/recovery')
LVGL=r'''
#pragma once
#include <cstdint>
#define __unused __attribute__((unused))
#define LV_USE_GESTURE_RECOGNITION 0
struct lv_point_t { int x,y; };
enum lv_indev_state_t { LV_INDEV_STATE_RELEASED, LV_INDEV_STATE_PRESSED };
struct lv_indev_t {};
struct lv_obj_t {};
struct lv_indev_data_t { lv_point_t point; lv_indev_state_t state; uint32_t timestamp; bool continue_reading; };
struct lv_indev_touch_data_t { uint8_t id; lv_point_t point; lv_indev_state_t state; uint32_t timestamp; };
constexpr int LV_INDEV_TYPE_POINTER=1;
inline lv_indev_t* lv_indev_create(){static lv_indev_t d;return &d;}
inline void lv_indev_set_type(lv_indev_t*,int){}
inline void lv_indev_set_read_cb(lv_indev_t*,void(*)(lv_indev_t*,lv_indev_data_t*)){}
inline void lv_indev_reset(lv_indev_t*,lv_obj_t*){}
inline uint32_t lv_tick_get(){return 0;}
inline lv_obj_t* lv_screen_active(){return nullptr;}
inline void lv_obj_invalidate(lv_obj_t*){}
'''
MINUI=r'''
#pragma once
#include <linux/input.h>
constexpr int TWRP_MAX_TOUCH_EVENTS=10;
constexpr int TWRP_ABS_MOUSE_POSITION=32;
struct TWRPTouchPoint {int id,x,y;bool pressed;};
inline int gr_fb_width(){return 1440;} inline int gr_fb_height(){return 3200;}
inline int twrp_input_take_touch_events(TWRPTouchPoint*,int){return 0;}
inline int twrp_input_get(input_event*,int){return -2;}
inline bool ev_input_is_keyboard(){return false;}
inline bool ev_has_mouse(){return false;}
'''
SCREEN=r'''
#include <cassert>
#include <string>
#include INPUT_SOURCE
#include SCREEN_SOURCE
void gui2_shell::screen_feedback::show_screenshot(uint64_t) {}
struct Screen final:gui2_backend::screen_backend {
 bool off=false;int offs=0,ons=0;
 bool has_screenshot()const override{return false;}
 gui2_backend::capture_result save_screenshot()override{return {};}
 bool has_screen_off()const override{return true;}
 bool is_screen_off()const override{return off;}
 bool screen_off()override{off=true;++offs;return true;}
 bool screen_on()override{off=false;++ons;return true;}
 void set_before_screen_off_callback(void(*)(void*),void*)override{}
 void on_input_activity()override{} void tick(uint64_t)override{}
 bool has_recording()const override{return false;}
 int max_recording_fps()const override{return 0;} int recording_fps()const override{return 0;}
 bool set_recording_fps(int)override{return false;} bool is_recording()const override{return false;}
 gui2_backend::capture_result start_recording()override{return {};}
 gui2_backend::capture_result stop_recording()override{return {};}
 void submit_frame(const gui2_backend::frame_view&,uint64_t)override{}
};
static void key(int code,int value){input_event e={};e.type=EV_KEY;e.code=code;e.value=value;process_key_event(e);}
static void press(){key(KEY_POWER,1);key(KEY_POWER,0);}
int main(int argc,char**argv){
 gui2_input_init();gui2_key_action action;
 Screen s;gui2_app::screen_actions a;a.initialize(&s,nullptr,nullptr,nullptr);
 if(argc>1 && std::string(argv[1])=="pending"){
  a.toggle_screen();a.toggle_screen();a.process_after_present();assert(!s.off && s.offs==0);return 0;
 }
 // Two complete presses can accumulate while the render thread is busy.
 press();press();unsigned n=0;
 while(gui2_input_take_key_action(&action)){assert(action==gui2_key_action::TOGGLE_SCREEN);++n;a.toggle_screen();}
 assert(n==2);a.process_after_present();assert(!s.off);
 // Across frame boundaries off/on must restore input immediately.
 a.toggle_screen();a.process_after_present();assert(s.off && screen_off_input);
 assert(a.toggle_screen());assert(!s.off && !screen_off_input);
 // Screenshot chords in either key order must never turn the screen off.
 for(bool power_first:{false,true}){
  gui2_input_init();key(power_first?KEY_POWER:KEY_VOLUMEDOWN,1);
  key(power_first?KEY_VOLUMEDOWN:KEY_POWER,1);key(KEY_POWER,0);key(KEY_VOLUMEDOWN,0);
  assert(gui2_input_take_key_action(&action)&&action==gui2_key_action::SCREENSHOT);
  assert(!gui2_input_take_key_action(&action));
  press();assert(gui2_input_take_key_action(&action)&&action==gui2_key_action::TOGGLE_SCREEN);
 }
 gui2_input_init();key(KEY_POWER,1);key(KEY_POWER,2);key(KEY_POWER,0);key(KEY_POWER,0);
 assert(gui2_input_take_key_action(&action));assert(!gui2_input_take_key_action(&action));
}
'''
FF=r'''
#include <cassert>
#include <cstdarg>
#include <cstring>
#include <cstdio>
#include <dirent.h>
#include <linux/input.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include FF_SOURCE
static int selected=FF_PERIODIC;static unsigned uploads=0,plays=0;static int directory_index=0;
static int frequency=130;
static bool fail_open=false,fail_upload=false,fail_remove=false,short_write=false,with_sine=true;
static int expected_length=80,closes=0;
extern "C" int32_t property_get_int32(const char* key,int32_t fallback){assert(!strcmp(key,"ro.twrp.haptics_frequency"));return frequency?frequency:fallback;}
extern "C" DIR* __wrap_opendir(const char*){directory_index=0;return reinterpret_cast<DIR*>(1);}
extern "C" dirent* __wrap_readdir(DIR*){static dirent e={};if(directory_index++%2)return nullptr;strcpy(e.d_name,"event4");return &e;}
extern "C" int __wrap_closedir(DIR*){return 0;}
extern "C" int __wrap_open(const char*,int,...){return fail_open?-1:100;}
extern "C" int __wrap_close(int){++closes;return 0;}
extern "C" int __wrap_ioctl(int,unsigned long req,...){
 va_list ap;va_start(ap,req);
 if(req==EVIOCRMFF){(void)va_arg(ap,int);va_end(ap);return fail_remove?-1:0;}
 void* p=va_arg(ap,void*);va_end(ap);
 if(_IOC_NR(req)==_IOC_NR(EVIOCGNAME(1))){strcpy(static_cast<char*>(p),selected==FF_PERIODIC?"cs40l26_input":"haptic");return 0;}
 if(_IOC_NR(req)==_IOC_NR(EVIOCGBIT(EV_FF,1))){
  auto bits=static_cast<unsigned long*>(p);memset(p,0,_IOC_SIZE(req));
  auto set=[&](int b){bits[b/(8*sizeof(unsigned long))]|=1UL<<(b%(8*sizeof(unsigned long)));};
  if(selected>=0){set(selected);}
  if(selected==FF_PERIODIC&&with_sine){set(FF_SINE);}
  return 0;
 }
 if(req==EVIOCSFF){if(fail_upload)return -1;auto e=static_cast<ff_effect*>(p);assert(e->type==selected);assert(e->replay.length==expected_length);
  if(selected==FF_PERIODIC){assert(e->u.periodic.waveform==FF_SINE);assert(e->u.periodic.period==(frequency==130?8:5));assert(e->u.periodic.magnitude==64);assert(e->u.periodic.custom_len==0);}
  e->id=7;++uploads;return 0;}
 return -1;
}
extern "C" ssize_t __wrap_write(int,const void* p,size_t n){auto e=static_cast<const input_event*>(p);assert(e->type==EV_FF&&e->code==7&&e->value==1);++plays;return short_write?n-1:n;}
int main(){for(int type:{FF_PERIODIC,FF_CONSTANT,FF_RUMBLE}){selected=type;twrpminui::reset_ff();assert(twrpminui::play_force_feedback(80)==0);assert(twrpminui::play_force_feedback(80)==0);}assert(uploads==6&&plays==6);
 selected=FF_PERIODIC;for(int f:{0,99,251}){frequency=f;twrpminui::reset_ff();assert(twrpminui::play_force_feedback(80)==0);}assert(uploads==9&&plays==9);
 frequency=130;twrpminui::reset_ff();
 fail_open=true;assert(twrpminui::play_force_feedback(80)==-1);fail_open=false;
 selected=-1;assert(twrpminui::play_force_feedback(80)==-1);selected=FF_PERIODIC;
 with_sine=false;assert(twrpminui::play_force_feedback(80)==-1);with_sine=true;
 assert(uploads==9&&plays==9); // unsupported/missing devices never receive an effect
 fail_upload=true;int before=closes;assert(twrpminui::play_force_feedback(80)==-1);
 assert(closes>before&&twrpminui::ff_haptics_fd==-1);fail_upload=false;
 short_write=true;before=closes;assert(twrpminui::play_force_feedback(80)==-1);
 assert(closes>before&&twrpminui::ff_haptics_fd==-1);short_write=false;
 assert(twrpminui::play_force_feedback(80)==0);fail_remove=true;before=closes;
 assert(twrpminui::play_force_feedback(80)==-1);assert(closes>before&&twrpminui::ff_haptics_fd==-1);fail_remove=false;
 assert(twrpminui::play_force_feedback(0)==-1);assert(twrpminui::play_force_feedback(-1)==-1);
 expected_length=10000;assert(twrpminui::play_force_feedback(20000)==0);
}
'''

def run():
 with tempfile.TemporaryDirectory(prefix='dijun-regression-') as temp:
  d=Path(temp);(d/'twrpminui').mkdir();(d/'lvgl.h').write_text(LVGL);(d/'twrpminui/minui.h').write_text(MINUI)
  (d/'common.h').write_text('#pragma once\n#define LOGI(...) fprintf(stdout,__VA_ARGS__)\n#define LOGE(...) fprintf(stderr,__VA_ARGS__)\n')
  (d/'twcommon.h').write_text('#pragma once\n')
  (d/'cutils').mkdir();(d/'cutils/properties.h').write_text('#pragma once\n#include <stdint.h>\nextern "C" int32_t property_get_int32(const char*, int32_t);\n')
  (d/'screen.cpp').write_text(SCREEN);(d/'ff.cpp').write_text(FF)
  common=['g++','-std=c++17','-Wall','-Wextra','-Wno-unused-but-set-variable',f'-I{d}',f'-I{RECOVERY}/gui2',f'-I{RECOVERY}/twrpminui']
  src=[f'-DINPUT_SOURCE="{RECOVERY}/gui2/gui2_input.cpp"',f'-DSCREEN_SOURCE="{RECOVERY}/gui2/app/screen_actions.cpp"']
  subprocess.run(common+src+[str(d/'screen.cpp'),'-o',str(d/'screen')],check=True)
  for scenario in ['keys','pending']:subprocess.run([str(d/'screen'),scenario],check=True)
  print('PASS: rapid queued presses, deferred-off cancellation, wake input, screenshot chords, repeat suppression')
  subprocess.run(common+[f'-DFF_SOURCE="{RECOVERY}/twrpminui/force_feedback.cpp"',str(d/'ff.cpp'),'-Wl,--wrap=open,--wrap=close,--wrap=ioctl,--wrap=write,--wrap=opendir,--wrap=readdir,--wrap=closedir','-o',str(d/'ff')],check=True)
  subprocess.run([str(d/'ff')],check=True)
  print('PASS: Cirrus sine, constant/rumble, reuse, missing/unsupported hardware, upload/remove/short-write failures, duration clamp')
  previous_ff=Path(__file__).resolve().parent/'fixtures/devicefix-force-feedback.cpp'
  subprocess.run(common+[f'-DFF_SOURCE="{previous_ff}"',str(d/'ff.cpp'),'-Wl,--wrap=open,--wrap=close,--wrap=ioctl,--wrap=write,--wrap=opendir,--wrap=readdir,--wrap=closedir','-o',str(d/'old-ff')],check=True)
  result=subprocess.run([str(d/'old-ff')],capture_output=True)
  assert result.returncode!=0 and b'period' in result.stderr, 'previous candidate must fail the resonance-period regression'
  print('PASS: previous devicefix FF source fails the 130 Hz period regression')
  # Verify each rapid-press test reproduces a failure on the unpatched sources.
  for filename in ['gui2/gui2_input.cpp','gui2/app/screen_actions.cpp']:
   (d/Path(filename).name).write_bytes(subprocess.check_output(['git','-C',str(RECOVERY),'show',f'HEAD:{filename}']))
  old=[f'-DINPUT_SOURCE="{d}/gui2_input.cpp"',f'-DSCREEN_SOURCE="{d}/screen_actions.cpp"']
  subprocess.run(common+old+[str(d/'screen.cpp'),'-o',str(d/'old')],check=True)
  for scenario in ['keys','pending']:
   result=subprocess.run([str(d/'old'),scenario],capture_output=True)
   assert result.returncode!=0, f'baseline unexpectedly passes {scenario}'
  print('PASS: both rapid-power regression cases fail on the unpatched baseline')
if __name__=='__main__':run()
