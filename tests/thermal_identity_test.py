#!/usr/bin/env python3
"""Execute production temperature lookup/cache and initialization with private sysfs.

Actual filesystem enumeration, type matching and integer parsing execute on
ordinary temporary files; property/clock/read boundaries are fixtures. No real
sysfs, thermal driver, hardware clock or GUI is used.
"""
import argparse,hashlib,json,subprocess,tempfile
from pathlib import Path
from backup_session_test import method
ROOT=Path(__file__).resolve().parents[1];REC=Path('/root/AAA/twrp/bootable/recovery')
CASES=['reordered','late-registration','wrong-type','duplicate','renumbered','bad-temp','read-error','negative-small','name-filter','missing-root','disabled','legacy']
HARNESS=r'''
#include <cassert>
#include <charconv>
#include <chrono>
#include <ctime>
#include <filesystem>
#include <format>
#include <fstream>
#include <map>
#include <mutex>
#include <string>
#include <string_view>
namespace fs=std::filesystem;
static std::string root,sensor="cpu-crg";
static bool no_temp=false;
struct FixtureClock {using time_point=std::chrono::steady_clock::time_point;static inline time_point current=time_point(std::chrono::seconds(1));static time_point now(){return current;}};
namespace android::base {
std::string GetProperty(const std::string& key,const std::string& fallback){assert(key=="ro.twrp.cpu_temp_type");return sensor;}
bool ReadFileToString(const std::string& path,std::string*out){std::string mapped=path;if(mapped.starts_with("/sys/class/thermal/"))mapped=root+mapped.substr(18);std::ifstream f(mapped);if(!f)return false;*out=std::string(std::istreambuf_iterator<char>(f),{});return !f.bad();}
}
#define TW_MILITARY_TIME "military"
#define LOGINFO(...) ((void)0)
struct DataManager{static int GetMagicValue(const std::string&,std::string&);static int GetValue(const std::string&,int&v){v=no_temp;return 0;}};
// METHODS
static bool initialize(){std::map<std::string,bool>consts_;
// INIT
return consts_["tw_no_cpu_temp"];}
static void zone(const std::string&name,const std::string&type,const std::string&temp){fs::create_directories(fs::path(root)/name);std::ofstream(fs::path(root)/name/"type")<<type;std::ofstream(fs::path(root)/name/"temp")<<temp;}
static std::string read(bool ok){std::string value="stale";int rc=DataManager::GetMagicValue("tw_cpu_temp",value);assert(rc==(ok?0:-1));if(!ok)assert(value.empty());return value;}
static void next(){FixtureClock::current+=std::chrono::seconds(6);}
int main(int argc,char**argv){assert(argc==3);std::string test=argv[1];root=argv[2];fs::create_directories(root);
// The initialization assertion belongs to the late-registration scenario.
if(test=="reordered"){zone("thermal_zone0","battery\n","99000\n");zone("thermal_zone17","cpu-crg\n","42000\n");assert(read(true)=="42");}
else if(test=="late-registration"){assert(!initialize());read(false);zone("thermal_zone7","cpu-crg\n","43000\n");read(false);next();assert(read(true)=="43");}
else if(test=="wrong-type"){zone("thermal_zone0","cpu-top\n","42000\n");read(false);}
else if(test=="duplicate"){zone("thermal_zone1","cpu-crg\n","42000\n");zone("thermal_zone2","cpu-crg\n","43000\n");read(false);fs::remove_all(fs::path(root)/"thermal_zone1");next();assert(read(true)=="43");}
else if(test=="renumbered"){zone("thermal_zone0","cpu-crg\n","42000\n");assert(read(true)=="42");zone("thermal_zone0","battery\n","99000\n");zone("thermal_zone19","cpu-crg\n","44000\n");assert(read(true)=="42");next();assert(read(true)=="44");}
else if(test=="bad-temp"){zone("thermal_zone3","cpu-crg\n","42000junk\n");read(false);zone("thermal_zone3","cpu-crg\n","99999999999999999999999\n");next();read(false);zone("thermal_zone3","cpu-crg\n","1000001\n");next();read(false);}
else if(test=="read-error"){zone("thermal_zone3","cpu-crg\n","42000\n");assert(read(true)=="42");fs::remove(fs::path(root)/"thermal_zone3"/"temp");next();read(false);zone("thermal_zone3","cpu-crg\n","45000\n");next();assert(read(true)=="45");}
else if(test=="negative-small"){zone("thermal_zone3"," \tcpu-crg\r\n","-5000\n");assert(read(true)=="-5");zone("thermal_zone3","cpu-crg\n","500\n");next();assert(read(true)=="0");}
else if(test=="name-filter"){zone("thermal_zone","cpu-crg\n","99000\n");zone("thermal_zone1x","cpu-crg\n","99000\n");zone("cooling_device0","cpu-crg\n","99000\n");zone("thermal_zone6","cpu-crg-extra\n","99000\n");read(false);zone("thermal_zone8","cpu-crg\n","46000\n");next();assert(read(true)=="46");}
else if(test=="missing-root"){fs::remove_all(root);read(false);zone("thermal_zone3","cpu-crg\n","42000\n");next();assert(read(true)=="42");}
else if(test=="disabled"){no_temp=true;zone("thermal_zone3","cpu-crg\n","42000\n");read(false);}
else if(test=="legacy"){sensor.clear();zone("thermal_zone0","battery\n","47000\n");assert(read(true)=="47");}
else assert(false);
}
'''
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=REC/'data.cpp');ap.add_argument('--report',type=Path,default=ROOT/'logs/thermal-identity.json');a=ap.parse_args();text=a.source.read_text()
 code=method(text,'int DataManager::GetMagicValue(').replace('std::chrono::steady_clock','FixtureClock').replace('fs::directory_iterator entry("/sys/class/thermal", ec)','fs::directory_iterator entry(root, ec)')
 start=text.index('#ifdef TW_NO_CPU_TEMP');end=text.index('#ifdef TW_CUSTOM_POWER_BUTTON',start);init=text[start:end]
 cases=[]
 with tempfile.TemporaryDirectory(prefix='dijun-thermal-identity-') as tmp:
  tmp=Path(tmp);(tmp/'test.cpp').write_text(HARNESS.replace('// METHODS',code).replace('// INIT',init))
  subprocess.run(['g++','-std=c++23','-g','-O1','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-pthread',str(tmp/'test.cpp'),'-o',str(tmp/'test')],check=True)
  for case in CASES:
   r=subprocess.run([str(tmp/'test'),case,str(tmp/case)],capture_output=True,text=True,timeout=10);cases.append(dict(case=case,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr));print(case,'PASS' if not r.returncode else 'FAIL',flush=True)
 report=dict(status='PASS' if all(not c['returncode'] for c in cases) else 'FAIL',scope=__doc__,cases=cases,sources={str(p):sha(p) for p in [a.source,Path(__file__).resolve(),ROOT/'tests/backup_session_test.py']});a.report.write_text(json.dumps(report,indent=2)+'\n');raise SystemExit(report['status']!='PASS')
if __name__=='__main__':main()
