#!/usr/bin/env python3
"""Run the actual decrypt backend and its threads with a substitute CE provider."""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SRC=Path('/root/AAA/twrp/bootable/recovery')
BACK=SRC/'gui2/backend'
with tempfile.TemporaryDirectory(prefix='dijun-decrypt-backend-') as tmp:
    tmp=Path(tmp);(tmp/'twrpinstall/include').mkdir(parents=True)
    fixture=r'''
#pragma once
#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <map>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include "twrp_operation_executor.h"
#define TW_IS_FBE "fbe"
#define TW_IS_ENCRYPTED "encrypted"
#define TW_CRYPTO_PWTYPE "pwtype"
#define TW_HAS_DATA_MEDIA "datamedia"
#define LOGINFO(...) ((void)0)
inline std::mutex data_mutex,gate_mutex;
inline std::condition_variable gate_cv;
inline bool hold=false;
inline std::atomic<bool> entered=false;
inline std::atomic<int> requested=-1,mtp=0,folders=0,refreshes=0,completed=-1;
inline bool succeed=true;
inline std::map<std::string,std::string> values{{"fbe","1"},{"encrypted","1"}};
struct DataManager {
 static int GetIntValue(const std::string& k){std::lock_guard l(data_mutex);return values[k].empty()?0:std::stoi(values[k]);}
 static std::string GetStrValue(const std::string& k){std::lock_guard l(data_mutex);return values[k];}
 static int GetValue(const std::string& k,std::string& v){v=GetStrValue(k);return 0;}
 static int GetValue(const std::string& k,int& v){v=GetIntValue(k);return 0;}
 static void SetValue(const std::string& k,const std::string& v){std::lock_guard l(data_mutex);values[k]=v;}
 static void SetValue(const std::string& k,int v){SetValue(k,std::to_string(v));}
 static void SetBackupFolder(){++folders;}
 static std::string GetCurrentStoragePath(){return "/fixture/media/0";}
};
struct UsersStruct{int user_id;std::string user_name;int type;bool is_decrypted;};
struct TWPartition{static bool DataIsLocked(){return DataManager::GetIntValue(TW_IS_ENCRYPTED);}};
struct Manager {
 std::vector<UsersStruct> users{{0,"Owner",3,false},{10,"Work",1,false},{999,"Clone",0,false}};
 auto* GetUsersList(){return &users;}
 void UpdateSystemDetails(bool){++refreshes;}
 void AddMtpStorage(const std::string&){++mtp;}
 int DecryptDevice(const std::string& password,int id=0){
  twrp_operation_executor::guard transaction(twrp_operation_executor::instance().mutex());
  requested=id;assert(password=="fixture-credential");entered=true;gate_cv.notify_all();
  {std::unique_lock l(gate_mutex);gate_cv.wait(l,[]{return !hold;});}
  if(!succeed)return -1;
  for(auto& u:users)if(u.user_id==id){u.is_decrypted=true;return 0;}
  return -1;
 }
} inline PartitionManager;
inline int tw_get_default_metadata(const char*){return 0;}
'''
    (tmp/'fixture.h').write_text(fixture)
    for name in ['data.hpp','partitions.hpp','twcommon.h','variables.h','twrpinstall/include/set_metadata.h']:
        (tmp/name).write_text('#include <fixture.h>\n')
    source=(BACK/'twrp_decrypt_backend.cpp').read_text()
    for name in ['data.hpp','partitions.hpp','twcommon.h','variables.h','twrpinstall/include/set_metadata.h']:
        source=source.replace('#include "'+name+'"','#include <'+name+'>')
    (tmp/'backend.cpp').write_text(source)
    harness=r'''
#include <fixture.h>
#include "twrp_decrypt_backend.h"
#include "twrp_operation.h"
namespace gui2_backend {
void operation_start(const std::string&){}
void operation_end(int status){completed=status;}
}
using namespace gui2_backend;
void finish(twrp_decrypt_backend& b,decrypt_state expected){
 for(int i=0;i<1000 && b.state()==decrypt_state::RUNNING;++i)std::this_thread::sleep_for(std::chrono::milliseconds(1));
 assert(b.state()==expected);b.acknowledge();assert(b.state()==decrypt_state::IDLE);
}
int main(){
 twrp_decrypt_backend b;
 auto users=b.users();assert(users.size()==3 && users[1].id==10 && users[1].kind==lock_kind::PASSWORD);
 PartitionManager.users[1].type=2;assert(b.select_user(10) && b.kind()==lock_kind::PATTERN);
 PartitionManager.users[1].type=1;
 assert(b.select_user(999) && b.kind()==lock_kind::DEFAULT && b.selected_user_name()=="Clone");
 assert(!b.select_user(-1) && !b.select_user(11) && !b.select_user(10000));
 // Freeze a real backend worker after it reaches the substitute provider.
 {std::lock_guard l(gate_mutex);hold=true;}
 assert(b.start("fixture-credential"));
 {std::unique_lock l(gate_mutex);assert(gate_cv.wait_for(l,std::chrono::seconds(2),[]{return entered.load();}));}
 assert(requested==999 && b.state()==decrypt_state::RUNNING);
 DataManager::SetValue("tw_crypto_user_id","0");
 assert(!b.select_user(10) && !b.start("fixture-credential") && !b.start_refresh());
 assert(b.users().empty()); // does not wait for the held storage transaction
 {std::lock_guard l(gate_mutex);hold=false;}gate_cv.notify_all();finish(b,decrypt_state::DONE);
 assert(requested==999 && mtp==0 && folders==0 && DataManager::GetIntValue(TW_IS_ENCRYPTED)==1);
 assert(PartitionManager.users[2].is_decrypted && !PartitionManager.users[0].is_decrypted);
 // A mode refresh after selection must not redirect the credential to owner 0.
 DataManager::SetValue(TW_IS_FBE,0);
 assert(b.start("fixture-credential"));finish(b,decrypt_state::DONE);
 assert(requested==999 && !PartitionManager.users[0].is_decrypted && mtp==0);
 DataManager::SetValue(TW_IS_FBE,1);
 assert(b.select_user(10) && b.kind()==lock_kind::PASSWORD);succeed=false;
 assert(b.start("fixture-credential"));finish(b,decrypt_state::FAILED);
 assert(requested==10 && !PartitionManager.users[1].is_decrypted && mtp==0);
 succeed=true;b.select_user();assert(b.kind()==lock_kind::PIN && b.selected_user_name()=="Owner");
 assert(b.start("fixture-credential"));finish(b,decrypt_state::DONE);
 assert(requested==0 && mtp==1 && folders==1 && DataManager::GetIntValue(TW_IS_ENCRYPTED)==0);
 assert(!PartitionManager.users[1].is_decrypted);
 assert(b.start_refresh());finish(b,decrypt_state::DONE);assert(refreshes==1);
 PartitionManager.users.clear();b.select_user();assert(!b.start("fixture-credential"));
 DataManager::SetValue(TW_IS_FBE,0);DataManager::SetValue("tw_crypto_pwtype_0",1);
 assert(b.select_user(0) && b.kind()==lock_kind::PASSWORD && !b.select_user(10));
 puts("PASS: user snapshot/PIN/password/pattern/default/name, invalid IDs, captured ID, busy rejection, nonblocking list, secondary isolation, mode-change identity, failed credential, owner storage update, refresh, missing owner, non-FBE selection");
}
'''
    (tmp/'test.cpp').write_text(harness)
    subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror','-pthread',
                    '-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(tmp),'-I'+str(SRC),'-I'+str(BACK),
                    str(tmp/'backend.cpp'),str(tmp/'test.cpp'),str(SRC/'twrp_operation_executor.cpp'),'-o',str(tmp/'test')],check=True)
    subprocess.run([str(tmp/'test')],check=True,timeout=10)
report=dict(status='PASS',scope=__doc__,cases=['snapshot-types','invalid-ids','captured-id','busy-rejection',
             'nonblocking-list','secondary-isolation','mode-change-keeps-id','wrong-credential','owner-storage-update','refresh','missing-owner','non-fbe'],
            sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [BACK/'decrypt_backend.h',BACK/'twrp_decrypt_backend.h',BACK/'twrp_decrypt_backend.cpp',Path(__file__)]})
(ROOT/'logs/multiuser-backend.json').write_text(json.dumps(report,indent=2)+'\n')
