#!/usr/bin/env python3
"""Run actual GUI user-selection callbacks with backend/LVGL boundary substitutes.

This checks navigation and request identity, not rendered page geometry.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path('/root/AAA/twrp/bootable/recovery/gui2/gui2.cpp')
text=SOURCE.read_text()

def extract(signature):
    start=text.index(signature);opening=text.index('{',start);end=opening+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]

methods='\n'.join(extract(s) for s in [
    'static void enter_decrypt_flow(page_transition transition) {',
    'static void decrypt_user_event_cb(lv_event_t* event) {',
    'static void show_decrypt_users_page(page_transition transition) {'])
code=r'''
#include <algorithm>
#include <cassert>
#include <string>
#include <vector>
#include "backend/decrypt_backend.h"
enum class page_transition {NONE,PUSH,POP,REPLACE};
enum class page_kind {HOME,DECRYPT,DECRYPT_USERS};
using lv_obj_t=int;
constexpr int LV_EVENT_CLICKED=1;
struct lv_event_t{int code;bool click;const void* data;};
int lv_event_get_code(lv_event_t* e){return e->code;}
const void* lv_event_get_user_data(lv_event_t* e){return e->data;}
bool accept_click(lv_event_t* e){return e->click;}
void press_cancel_guard_cb(lv_event_t*){}
struct Backend {
 std::vector<gui2_backend::decrypt_user> items;bool busy=false;int selected=-1;
 auto users(){return items;}
 bool select_user(int id){if(busy)return false;for(auto& u:items)if(u.id==id){selected=id;return true;}return false;}
} backend;
Backend* decrypt=&backend;
struct State{bool decrypt_during_startup=false,decrypt_from_users=false,decrypt_failed=true;
 std::vector<gui2_backend::decrypt_user> decrypt_users;} page_state;
page_kind navigated=page_kind::HOME;
void navigate_to(page_kind p,const void*,page_transition){navigated=p;}
int ui=0;lv_obj_t* main_content=&ui;
struct Strings {const char* decrypt_users_title="Users";const char* decrypt_users_summary="Choose user";};
const Strings& strings(){static Strings s;return s;}
namespace gui2_core{int navigation_safe_area(){return 10;}}
void create_page_scaffold(page_kind,bool,const char*,const char*,int,page_transition){}
namespace gui2_pages {
struct decrypt_users_page_options{lv_obj_t* content=nullptr;const int* metrics=nullptr;const Strings* strings=nullptr;
 const std::vector<gui2_backend::decrypt_user>* users=nullptr;void(*select_callback)(lv_event_t*)=nullptr;
 void(*press_guard_callback)(lv_event_t*)=nullptr;};
inline std::vector<gui2_backend::decrypt_user> displayed;
void build_decrypt_users_page(const decrypt_users_page_options& o){assert(o.content&&o.metrics&&o.strings&&o.select_callback&&o.press_guard_callback);displayed=*o.users;}
}
// METHODS
int main(){
 using gui2_backend::lock_kind;
 backend.items={{0,"Owner",lock_kind::PIN,true},{10,"Work",lock_kind::PASSWORD,false},{999,"Clone",lock_kind::DEFAULT,false}};
 enter_decrypt_flow(page_transition::PUSH);assert(navigated==page_kind::DECRYPT_USERS && !page_state.decrypt_from_users);
 show_decrypt_users_page(page_transition::PUSH);assert(gui2_pages::displayed.size()==3 && gui2_pages::displayed[0].unlocked);
 int id=999;lv_event_t event{LV_EVENT_CLICKED,true,&id};decrypt_user_event_cb(&event);
 assert(navigated==page_kind::DECRYPT && backend.selected==999 && page_state.decrypt_from_users && !page_state.decrypt_failed);
 navigated=page_kind::HOME;backend.busy=true;decrypt_user_event_cb(&event);assert(navigated==page_kind::HOME);
 backend.busy=false;event.click=false;decrypt_user_event_cb(&event);assert(navigated==page_kind::HOME);
 event.click=true;id=11;decrypt_user_event_cb(&event);assert(navigated==page_kind::HOME);
 page_state.decrypt_during_startup=true;enter_decrypt_flow(page_transition::PUSH);assert(navigated==page_kind::DECRYPT);
 page_state.decrypt_during_startup=false;enter_decrypt_flow(page_transition::NONE);assert(navigated==page_kind::DECRYPT);
 backend.items={{999,"Clone",lock_kind::DEFAULT,false}};enter_decrypt_flow(page_transition::PUSH);assert(navigated==page_kind::DECRYPT_USERS);
 backend.items={{0,"Owner",lock_kind::PIN,false}};enter_decrypt_flow(page_transition::PUSH);assert(navigated==page_kind::DECRYPT);
 decrypt=nullptr;navigated=page_kind::HOME;enter_decrypt_flow(page_transition::PUSH);assert(navigated==page_kind::HOME);
 puts("PASS: manual multi-user routing, snapshot/locked states, selected ID, rejected/busy click, startup owner path, single-secondary and single-owner, missing backend");
}
'''.replace('// METHODS',methods)
with tempfile.TemporaryDirectory(prefix='dijun-user-routes-') as tmp:
    tmp=Path(tmp);(tmp/'test.cpp').write_text(code)
    subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror','-I'+str(SOURCE.parent),
                    str(tmp/'test.cpp'),'-o',str(tmp/'test')],check=True)
    subprocess.run([str(tmp/'test')],check=True,timeout=5)
# Static integration checks complement callback execution. Full files are Android-built.
for fragment in ['case page_kind::DECRYPT_USERS:', 'options.has_decrypt = data_locked() ||',
                 'page_state.decrypt_from_users ? page_kind::DECRYPT_USERS : page_kind::HOME']:
    assert fragment in text
report=dict(status='PASS',scope=__doc__,source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            cases=['manual-routing','snapshot','selected-id','busy-or-rejected-click','startup','single-secondary','single-owner','missing-backend'])
(ROOT/'logs/multiuser-routes.json').write_text(json.dumps(report,indent=2)+'\n')
