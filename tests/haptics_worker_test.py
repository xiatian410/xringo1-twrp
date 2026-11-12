#!/usr/bin/env python3
"""Run the actual GUI hardware backend and haptics owner against gated I/O.

Real threads execute; probe/play/release are device boundary substitutes. Closed
gates prove GUI-facing methods return independently of active I/O. No device,
kernel worker, physical motor or uninterruptible syscall is executed.
"""
import hashlib
import json
import re
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SRC=Path('/root/AAA/twrp/bootable/recovery')
NAMES=['gui2/backend/haptics_controller.cpp','gui2/backend/haptics_controller.h',
       'gui2/backend/twrp_hardware_settings.cpp','gui2/backend/twrp_hardware_settings.h',
       'gui2/backend/hardware_settings.h','gui2/backend/backlight_controller.h',
       'gui2/backend/settings_store.h']
CASES=['probe-nonblocking','probe-stop','play-nonblocking','latest-only','expired',
       'stop-discards','concurrent-stop','failure','recovery','late-device','unplug',
       'durations','disabled','zero','invalid','idle-stop']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    results=[]
    with tempfile.TemporaryDirectory(prefix='dijun-haptics-worker-') as tmp:
        tmp=Path(tmp);(tmp/'twrpminui').mkdir()
        (tmp/'data.hpp').write_text('''#pragma once
#include <map>
#include <string>
class DataManager {public:
 static inline std::map<std::string,int> values;
 static int GetIntValue(const std::string& key){return values[key];}
};
''')
        (tmp/'twrp_functions.hpp').write_text('#pragma once\n')
        (tmp/'twrpminui/minui.h').write_text('#pragma once\nint vibrate(int);\nint haptics_available();\n')
        exe=tmp/'test'
        subprocess.run(['g++','-std=c++23','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
                        '-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-no-pie','-g',
                        '-I'+str(tmp),'-I'+str(SRC/'gui2/backend'),str(ROOT/'tests/haptics_worker_test.cpp'),
                        str(SRC/NAMES[0]),str(SRC/NAMES[2]),'-o',str(exe)],check=True)
        for case in CASES:
            run=subprocess.run([str(exe),case],capture_output=True,text=True,timeout=10)
            results.append(dict(case=case,status='PASS' if run.returncode==0 else 'FAIL',
                                output=(run.stdout+run.stderr).strip(),returncode=run.returncode))
            if run.returncode==0:
                trace=[dict(re.findall(r'(\w+)=([^\s]+)',line)) for line in run.stderr.splitlines() if line.startswith('GUI2 haptics: request=')]
                if case=='latest-only':
                    begin=[e for e in trace if e['phase']=='begin']
                    assert [int(e['duration_ms']) for e in begin]==[80,160]
                    assert begin[1]['request']=='5002' and begin[1]['replaced']=='5000'
                if case=='expired':
                    expired=[e for e in trace if e['phase']=='expired']
                    assert len(expired)==1 and expired[0]['request']=='5002' and expired[0]['replaced']=='5000' and int(expired[0]['age_ms'])>=250
                if case in ['failure','recovery']:assert any(e['phase']=='end' and e['accepted']=='0' for e in trace)
            print(results[-1]['status'],case,results[-1]['output'],flush=True)
    report=dict(status='PASS' if all(c['status']=='PASS' for c in results) else 'FAIL',scope=__doc__.strip(),
                cases=results,sources={str(SRC/n):sha(SRC/n) for n in NAMES},
                test_sources={str(p):sha(p) for p in [Path(__file__).resolve(),ROOT/'tests/haptics_worker_test.cpp']})
    (ROOT/'logs/haptics-worker.json').write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
