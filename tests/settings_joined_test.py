#!/usr/bin/env python3
"""Join real LVGL rows/callback, settings adapter, DataManager, partition lookup and InfoManager.

Private host files only. Partition Mount/IsMounted, Android properties/metadata,
page navigation and hardware sinks remain fixtures. No device or actual mount.
"""
import argparse,json,re,subprocess,tempfile
from pathlib import Path
from haptics_ui_test import ROOT,SRC,LVGL,lvgl_library,extract,sha
from nested_partition_path_test import method
CORE=SRC.parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--partition-source',type=Path,default=CORE/'partitionmanager.cpp')
parser.add_argument('--output',type=Path,default=ROOT/'logs/settings-joined.json')
args=parser.parse_args()
version=re.search(r'^#define FILE_VERSION\s+(\S+)',(CORE/'data.cpp').read_text(),re.M).group(1)
cases=['existing-mount','mount-on-save','mount-denied','no-space','short-write','read-only',
       'rename-error','directory-sync-error','uninitialized-backing','constant-key','long-field']
library,lvgl=lvgl_library()
with tempfile.TemporaryDirectory(prefix='settings-joined-') as td:
 t=Path(td);(t/'android-base').mkdir();persist=t/'mnt/vendor/persist/TWRP';persist.mkdir(parents=True)
 headers={
 'android-base/file.h':'''#pragma once
#include <fstream>
#include <iterator>
#include <string>
namespace android::base {inline bool ReadFileToString(const std::string& p,std::string* s){std::ifstream f(p,std::ios::binary);if(!f)return false;*s=std::string(std::istreambuf_iterator<char>(f),{});return !f.bad();}}
''',
 'android-base/parsedouble.h':'''#pragma once
#include <cstdlib>
namespace android::base {inline bool ParseFloat(const std::string&s,float*v){char*e;*v=strtof(s.c_str(),&e);return e==s.c_str()+s.size();}}
''',
 'android-base/scopeguard.h':'''#pragma once
#include <utility>
namespace android::base {template<class F>struct Guard{F f;~Guard(){f();}};template<class F>Guard<F>make_scope_guard(F f){return {std::move(f)};}}
''',
 'set_metadata.h':'#pragma once\n#include <sys/stat.h>\ninline int tw_set_default_metadata(const char*p){return chmod(p,0664);}\n',
 'twcommon.h':'#pragma once\n#include <cstdio>\n#define LOGINFO(...) std::printf(__VA_ARGS__)\n#define LOGERR(...) std::fprintf(stderr,__VA_ARGS__)\n',
 'variables.h':'#pragma once\n#define FIXTURE_ROOT "'+str(t)+'"\n#define FILE_VERSION '+version+'\n#define TW_PERSIST_DIR "/mnt/vendor/persist/TWRP"\n#define TW_SETTINGS_FILE ".twrp_settings"\n'+ '\n'.join(re.findall(r'^#define TW_TIME_ZONE[^\n]+',(CORE/'variables.h').read_text(),re.M))+'\n',
 'twrp_functions.hpp':'''#pragma once
#include <string>
namespace TWFunc {std::string GetRootPath(const std::string&);}
''',
 'partitions.hpp':r'''#pragma once
#include <string>
#include <vector>
#include <mutex>
struct TWPartition {
 std::string mount_point_,symlink_mount_point_,sub_partition_of_;
 bool is_sub_partition_=false,mounted=true,can_mount=true;int mounts=0;
 bool Mount(bool){++mounts;if(can_mount)mounted=true;return mounted;}
 bool IsMounted()const{return mounted;}
};
namespace twrp_operation_executor {
struct Executor {std::recursive_mutex m;std::recursive_mutex& mutex(){return m;}};
inline Executor& instance(){static Executor e;return e;}
struct guard {std::lock_guard<std::recursive_mutex> l;guard(std::recursive_mutex&m):l(m){}};
}
namespace gui2_console {template<class...T>void log_error(T...) {}}
class TWPartitionManager {public:
 std::vector<TWPartition*>partitions_;
 static bool MatchesPath(const TWPartition*,const std::string&);
 TWPartition*FindPartitionByPath(const std::string&)const;
 int IsMountedByPath(const std::string&)const;
 int MountByPath(const std::string&,bool)const;
 std::string GetAndroidRootPath()const{return "/system_root";}
 void UpdateSystemDetails(){}void MountCurrentStorage(bool){}
};
inline TWPartitionManager PartitionManager;
''',
 'data.hpp':r'''#pragma once
#include <string>
#include <map>
#include <pthread.h>
#include "infomanager.hpp"
namespace android::base {inline std::string GetProperty(const std::string&,const std::string& d){return d;}}
inline int property_set(const char*,const char*){return 0;}
#define PROPERTY_VALUE_MAX 92
inline int property_get(const char*,char*o,const char*){*o=0;return 0;}
class DataManager {public:
 inline static bool initialized_=true;
 inline static InfoManager persist_,data_,consts_;
 inline static pthread_mutex_t values_lock_=PTHREAD_RECURSIVE_MUTEX_INITIALIZER_NP;
 inline static std::string kBackingFile;
 static void SetDefaultValues(){}static void SetBackupFolder(){}
 static int GetMagicValue(const std::string&,std::string&){return -1;}
 static int GetValue(const std::string&,std::string&);
 static int GetValue(const std::string&k,int&v){std::string s;int r=GetValue(k,s);if(!r)v=std::stoi(s);return r;}
 static int SetValue(const std::string&,const std::string&,bool=false);
 static int SaveValues();static int Flush();static int ResetDefaults(){return 0;}
 static void UpdateTimezoneEnvironment(){}
};
'''}
 for n,s in headers.items():(t/n).write_text(s)
 info=(CORE/'infomanager.cpp').read_text()
 for n in ['partitions.hpp','set_metadata.h','twcommon.h','twrp_functions.hpp','variables.h']:info=info.replace('#include "'+n+'"','#include <'+n+'>')
 (t/'info.cpp').write_text(info)
 adapter=(SRC/'backend/twrp_settings_store.cpp').read_text()
 for n in ['data.hpp','partitions.hpp','variables.h']:adapter=adapter.replace('#include "'+n+'"','#include <'+n+'>')
 (t/'adapter.cpp').write_text(adapter)
 data=(CORE/'data.cpp').read_text();part=args.partition_source.read_text()
 bodies=[method(data,s) for s in ['int DataManager::GetValue(const std::string& key, std::string& value)',
 'int DataManager::SetValue(const std::string& key, const std::string& value,','int DataManager::Flush()','int DataManager::SaveValues()']]
 bodies += [method(part,s) for s in ['bool TWPartitionManager::MatchesPath(', 'TWPartition* TWPartitionManager::FindPartitionByPath(', 'int TWPartitionManager::MountByPath(', 'int TWPartitionManager::IsMountedByPath(']]
 bodies += [method((CORE/'twrp_functions.cpp').read_text(),'std::string TWFunc::GetRootPath(')]
 (t/'methods.cpp').write_text('#include <algorithm>\n#include <filesystem>\n#include <optional>\n#include <cctype>\n#include <data.hpp>\n#include <partitions.hpp>\n#include <variables.h>\n#include <twcommon.h>\n#include <twrp_functions.hpp>\nnamespace fs=std::filesystem;\n'+'\n'.join(bodies))
 (t/'callback.inc').write_text(extract((SRC/'gui2.cpp').read_text(),'general_setting_event_cb'))
 row=(ROOT/'tests/settings_row_test.cpp').read_text()
 prefix=row[:row.index('struct Settings {')]
 common=row[row.index('gui2_pages::general_setting general_settings_items'):row.index('int main(')]
 harness=prefix+'\n#include <data.hpp>\n#include <variables.h>\n#include <partitions.hpp>\n#include "backend/twrp_settings_store.h"\ngui2_backend::twrp_settings_store store;gui2_backend::settings_store*settings=&store;\n'+common+'\n'+(ROOT/'tests/settings_joined_test.cpp').read_text()
 (t/'test.cpp').write_text(harness)
 sources=[SRC/'components/check_row.cpp',SRC/'core/ui_event_guard.cpp',SRC/'core/ui_helpers.cpp',SRC/'core/ui_metrics.cpp']
 cmd=['g++','-std=c++23','-O1','-g','-fsanitize=undefined','-fno-sanitize-recover=undefined',
 '-DLV_CONF_INCLUDE_SIMPLE','-DLV_LVGL_H_INCLUDE_SIMPLE','-DTW_FRAMERATE=120','-I'+str(t),'-I'+str(CORE),'-I'+str(SRC),'-I'+str(SRC/'backend'),'-I'+str(LVGL),
 str(t/'test.cpp'),str(t/'methods.cpp'),str(t/'info.cpp'),str(t/'adapter.cpp'),*map(str,sources),str(library),'-pthread','-lm',
 '-Wl,--wrap=fwrite','-Wl,--wrap=mkstemp','-Wl,--wrap=rename','-Wl,--wrap=fsync','-o',str(t/'test')]
 subprocess.run(cmd,check=True)
 results=[]
 for kind in ['check','switch']:
  for case in cases:
   r=subprocess.run([str(t/'test'),kind,case],capture_output=True,text=True,timeout=15)
   results.append(dict(kind=kind,case=case,status='PASS' if r.returncode==0 else 'FAIL',returncode=r.returncode,output=r.stdout+r.stderr));print(kind,case,results[-1]['status'],r.stdout+r.stderr,flush=True)
 files=sources+[CORE/n for n in ['data.cpp','infomanager.cpp','infomanager.hpp','twrp_functions.cpp','variables.h']]+[args.partition_source,SRC/'gui2.cpp',SRC/'backend/twrp_settings_store.cpp',SRC/'backend/twrp_settings_store.h',SRC/'backend/settings_store.h',Path(__file__),ROOT/'tests/settings_joined_test.cpp',ROOT/'tests/settings_row_test.cpp']
 report=dict(status='PASS' if all(x['status']=='PASS' for x in results) else 'FAIL',scope=__doc__,cases=results,sources={str(p):sha(p) for p in files},lvgl=lvgl)
 args.output.write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='PASS' else 1)
