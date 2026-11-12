#!/usr/bin/env python3
"""Run the production settings -> haptics router -> FF path on host fixtures.

Actual minui/backend source is compiled. Sysfs/input paths point into a private
temporary directory; ioctl/property/storage boundaries are substitutes. No real
input device, driver, motor, HAL or calibration data is accessed.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SRC=Path('/root/AAA/twrp/bootable/recovery')
parser=argparse.ArgumentParser()
parser.add_argument('--source',type=Path,default=SRC)
parser.add_argument('--report',type=Path,default=ROOT/'logs/haptics-route.json')
parser.add_argument('--worker-io',action='store_true',help='Gate actual minui FF erase and check GUI owner integration')
parser.add_argument('--ff-source',type=Path,help='Override only FF implementation for a controlled baseline')
args=parser.parse_args()
cases=['missing','late-probe','unplug','disabled','channel-durations','persist-clamp',
       'stored-clamp','zero','ff-first','missing-led-duration','led','timed',
       'write-short','flush-fail','close-fail','open-denied','led-duration-error',
       'ff-upload-error','ff-play-error','ff-name-error','ff-unsupported','timeout-bound',
       'ff-erase-error','ff-play-short','ff-probe-eintr','ff-probe-eagain','ff-probe-enodev','ff-probe-ebadf']
if args.worker_io:
    assert args.source.resolve()==SRC.resolve(), 'worker I/O suite requires current owner interface'
    cases=['worker-erase-blocked','worker-release','worker-upload-failure','worker-play-failure',
           'worker-probe-eintr','worker-probe-eagain']
names=['twrpminui/haptics.cpp','twrpminui/force_feedback.cpp','gui2/backend/twrp_hardware_settings.cpp']
with tempfile.TemporaryDirectory(prefix='dijun-haptics-route-') as temp:
    temp=Path(temp)
    for directory in ['input','sys','cutils','twrpminui']:(temp/directory).mkdir()
    paths={
      '/dev/input':str(temp/'input'),
      '/sys/class/leds/vibrator/duration':str(temp/'sys/duration'),
      '/sys/class/leds/vibrator/activate':str(temp/'sys/activate'),
      '/sys/class/timed_output/vibrator/enable':str(temp/'sys/enable')}
    for name in names:
        text=(args.ff_source if name=='twrpminui/force_feedback.cpp' and args.ff_source else args.source/name).read_text()
        for old,new in paths.items():text=text.replace(old,new)
        (temp/Path(name).name).write_text(text)
    backend_header = (ROOT/'backups/haptics-worker-pre-fix/gui2/backend/twrp_hardware_settings.h') if args.source.resolve()!=SRC.resolve() else SRC/'gui2/backend/twrp_hardware_settings.h'
    (temp/'twrp_hardware_settings.h').write_bytes(backend_header.read_bytes())
    stubs={
      'common.h':'#pragma once\n#define LOGI(...) fprintf(stdout,__VA_ARGS__)\n#define LOGE(...) fprintf(stderr,__VA_ARGS__)\n',
      'twcommon.h':'#pragma once\n',
      'twrp_functions.hpp':'#pragma once\n',
      'data.hpp':'''#pragma once
#include <map>
#include <string>
class DataManager {public:
 static inline std::map<std::string,int> values;
 static int GetIntValue(const std::string& key){return values[key];}
 static int GetValue(const std::string& key,int& out){out=GetIntValue(key);return 0;}
 static void Vibrate(const std::string&);
};
''',
      'twrpminui/minui.h':'#pragma once\nint vibrate(int);\nint haptics_available();\n',
      'cutils/properties.h':'#pragma once\n#include <stdint.h>\nextern "C" int32_t property_get_int32(const char*,int32_t);\n'}
    for name,text in stubs.items():(temp/name).write_text(text)
    data=(SRC/'data.cpp').read_text();start=data.index('void DataManager::Vibrate(')
    end=data.index('\n}',start)+2
    harness=(ROOT/'tests/haptics_route_test.cpp').read_text().replace('// PRODUCTION_VIBRATE',data[start:end])
    (temp/'test.cpp').write_text(harness)
    wraps=['open','close','ioctl','write','fopen','fwrite','fflush','fclose','access']
    subprocess.run(['g++','-std=c++23','-Wall','-Wextra','-Werror','-pthread',
                    *(['-DHAPTICS_GUI_OWNER'] if args.source.resolve()==SRC.resolve() else []),
                    '-fsanitize=undefined','-fno-sanitize-recover=all','-g',
                    '-I'+str(temp),'-I'+str(SRC/'gui2/backend'),'-I'+str(SRC/'twrpminui'),
                    '-DFIXTURE_ROOT="'+str(temp)+'"',str(temp/'test.cpp'),
                    *[str(temp/Path(name).name) for name in names],
                    str(SRC/'gui2/backend/haptics_controller.cpp'),
                    *['-Wl,--wrap='+w for w in wraps],'-o',str(temp/'test')],check=True)
    results=[]
    for case in cases:
        r=subprocess.run([str(temp/'test'),case],capture_output=True,text=True,timeout=5)
        results.append(dict(case=case,status='PASS' if r.returncode==0 else 'FAIL',returncode=r.returncode,output=(r.stdout+r.stderr).strip()))
        if r.returncode==0 and args.source.resolve()==SRC.resolve():
            traces=[dict(re.findall(r'(\w+)=([^\s]+)',line)) for line in (r.stdout+r.stderr).splitlines() if line.startswith('FF haptics:') and 'phase=' in line]
            if case in ['ff-first','timeout-bound','ff-upload-error','ff-play-error','ff-erase-error','ff-play-short'] or args.worker_io:
                assert traces,case
                for entry in traces:
                    assert int(entry['monotonic_ms'])>=0
                    if entry['phase'].endswith('-end') and int(entry['result'])<0:assert int(entry['errno'])>0
                def phase(name):return [e for e in traces if e['phase']==name]
                if 'upload' in case and 'error' in case or case=='worker-upload-failure':
                    assert any(e['result']=='-1' and e['errno']=='5' for e in phase('upload-end')),case
                if case in ['ff-play-error','worker-play-failure']:
                    assert any(e['result']=='-1' and e['errno']=='19' for e in phase('play-end')),case
                if case=='ff-erase-error':assert any(e['result']=='-1' and e['errno']=='62' for e in phase('erase-end'))
                if case=='ff-play-short':assert phase('play-end')[0]['result']=='1' and phase('play-end')[0]['errno']=='0'
                if case=='worker-release':assert phase('close-begin') and phase('close-end')
        print(results[-1]['status'],case,results[-1]['output'],flush=True)
    bound=[args.ff_source if n=='twrpminui/force_feedback.cpp' and args.ff_source else args.source/n for n in names]
    report=dict(status='PASS' if all(r['status']=='PASS' for r in results) else 'FAIL',scope=__doc__.strip(),cases=results,
                sources={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in bound},
                shared_sources={str(SRC/n):hashlib.sha256((SRC/n).read_bytes()).hexdigest() for n in ['data.cpp','gui2/backend/hardware_settings.h','gui2/backend/twrp_hardware_settings.h','gui2/backend/settings_store.h','twrpminui/force_feedback.h','gui2/backend/haptics_controller.cpp','gui2/backend/haptics_controller.h']},
                configuration={str(backend_header):hashlib.sha256(backend_header.read_bytes()).hexdigest()},
                test_sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'tests/haptics_route_test.cpp']})
    args.report.write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='PASS' else 1)
