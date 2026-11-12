#!/usr/bin/env python3
"""Real LVGL timezone callback, settings adapter and libc TZ changes; DataManager I/O is a fixture.

No phone, RTC, persist mount, property service, complete GUI route or disk rollback.
"""
import argparse,json,re,subprocess,tempfile
from pathlib import Path
from haptics_ui_test import ROOT,SRC,LVGL,extract,lvgl_library,sha
from nested_partition_path_test import method
CORE=SRC.parent
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--source',type=Path,default=SRC/'gui2.cpp')
ap.add_argument('--output',type=Path,default=ROOT/'logs/timezone-retry.json')
a=ap.parse_args();library,lvgl=lvgl_library()
cases=['success-east','success-offset','success-dst','success-west',
       'set-failure-1','set-failure-2','set-failure-3','set-failure-4','set-failure-5',
       'flush-failure','retry','zone-low','zone-high','offset-low','offset-high','wrong-event','null-store']
with tempfile.TemporaryDirectory(prefix='timezone-retry-') as td:
 t=Path(td)
 (t/'callback.inc').write_text(extract(a.source.read_text(),'apply_timezone_event_cb'))
 (t/'variables.h').write_text('\n'.join(re.findall(r'^#define TW_TIME_ZONE[^\n]+',(CORE/'variables.h').read_text(),re.M))+'\n')
 (t/'data.hpp').write_text(r'''#pragma once
#include <map>
#include <string>
#include <ctime>
#include <cstdlib>
namespace android::base {inline std::string zone_property;inline bool SetProperty(const std::string&,const std::string&v){zone_property=v;return true;}}
class DataManager {public:
 inline static std::map<std::string,std::string> values,disk;
 inline static int writes=0,fail_write=0,flushes=0;
 inline static bool flush_ok=true;
 static int GetValue(const std::string&k,std::string&v){auto i=values.find(k);if(i==values.end())return -1;v=i->second;return 0;}
 static int GetValue(const std::string&k,int&v){std::string s;int r=GetValue(k,s);if(!r)v=std::stoi(s);return r;}
 static std::string GetStrValue(const std::string&k){return values.at(k);}
 static int SetValue(const std::string&k,const std::string&v,bool=false){if(++writes==fail_write)return -1;values[k]=v;return 0;}
 static int Flush(){++flushes;if(!flush_ok)return -1;disk=values;return 0;}
 static int ResetDefaults(){return 0;}
 static void UpdateTimezoneEnvironment();
};
''')
 (t/'partitions.hpp').write_text('#pragma once\nstruct PM{void UpdateSystemDetails(){}void MountCurrentStorage(bool){}};inline PM PartitionManager;\n')
 adapter=(SRC/'backend/twrp_settings_store.cpp').read_text()
 for n in ['data.hpp','variables.h','partitions.hpp']:adapter=adapter.replace('#include "'+n+'"','#include <'+n+'>')
 (t/'adapter.cpp').write_text(adapter)
 (t/'environment.cpp').write_text('#include <data.hpp>\n#include <variables.h>\n'+method((CORE/'data.cpp').read_text(),'void DataManager::UpdateTimezoneEnvironment()'))
 subprocess.run(['g++','-std=c++23','-O1','-g','-fsanitize=undefined','-fno-sanitize-recover=all',
 '-DLV_CONF_INCLUDE_SIMPLE','-DLV_LVGL_H_INCLUDE_SIMPLE','-I'+str(t),'-I'+str(SRC),'-I'+str(SRC/'backend'),'-I'+str(LVGL),
 str(ROOT/'tests/timezone_retry_test.cpp'),str(t/'adapter.cpp'),str(t/'environment.cpp'),str(library),'-lpthread','-lm','-o',str(t/'test')],check=True)
 results=[]
 for name in cases:
  r=subprocess.run([str(t/'test'),name],capture_output=True,text=True,timeout=10)
  results.append(dict(case=name,status='PASS' if r.returncode==0 else 'FAIL',returncode=r.returncode,output=r.stdout+r.stderr));print(name,results[-1]['status'],r.stdout+r.stderr,flush=True)
 files=[a.source,SRC/'backend/twrp_settings_store.cpp',SRC/'backend/twrp_settings_store.h',SRC/'backend/settings_store.h',SRC/'pages/settings_data.h',CORE/'data.cpp',CORE/'variables.h',Path(__file__),ROOT/'tests/timezone_retry_test.cpp']
 report=dict(status='PASS' if all(c['status']=='PASS' for c in results) else 'FAIL',scope=__doc__,cases=results,sources={str(p):sha(p) for p in files},lvgl=lvgl)
 a.output.write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='PASS' else 1)
