#!/usr/bin/env python3
"""Production minui discovery -> parser -> GUI callback with FIFO evdev fixture."""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile
from devicefix_regression import LVGL

ROOT=Path(__file__).resolve().parents[1]
A=Path('/root/AAA/twrp');R=A/'bootable/recovery'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
with tempfile.TemporaryDirectory(prefix='dijun-touch-delivery-') as temporary:
    d=Path(temporary);(d/'input').mkdir();(d/'cutils').mkdir()
    (d/'lvgl.h').write_text(LVGL)
    (d/'common.h').write_text('#include <cstdio>\n#define LOGE(...) fprintf(stderr,__VA_ARGS__)\n#define LOGI(...) fprintf(stderr,__VA_ARGS__)\n')
    (d/'cutils/properties.h').write_text('#pragma once\n#define PROPERTY_VALUE_MAX 92\nint property_get(const char*,char*,const char*);\n')
    (d/'compat.h').write_text('#include <pthread.h>\n#include <sys/stat.h>\n#define __unused __attribute__((unused))\n')
    events=d/'events.cpp'
    events.write_text((R/'twrpminui/events.cpp').read_text().replace('"/dev/input"',json.dumps(str(d/'input'))))
    command=['g++','-std=c++20','-pthread','-ffunction-sections','-fdata-sections',
             '-Wl,--gc-sections','-fsanitize=undefined','-fno-sanitize-recover=all',
             '-include',str(d/'compat.h'),'-I'+str(d),'-I'+str(R),'-I'+str(R/'twrpminui'),
             '-I'+str(R/'twrpminui/include'),'-I'+str(A/'system/libbase/include'),
             str(ROOT/'tests/touch_delivery_test.cpp'),str(events),str(A/'system/libbase/strings.cpp'),
             '-Wl,--wrap=ioctl','-o',str(d/'test')]
    subprocess.run(command,check=True)
    cases=[]
    for mode in ['initial','late']:
        node=d/'input/event3'
        if node.exists():node.unlink()
        p=subprocess.run([str(d/'test'),str(d/'input'),mode],check=True,capture_output=True,text=True,timeout=10)
        print(p.stdout,end='');cases.append(dict(case=mode,status='PASS'))
files=[A/'system/libbase/strings.cpp',A/'system/libbase/include/android-base/strings.h',
       A/'system/libbase/include/android-base/unique_fd.h',
       R/'twrpminui/events.cpp',R/'twrpminui/twrp_input.cpp',R/'twrpminui/twrp_input.h',
       R/'twrpminui/include/twrpminui/minui.h',R/'gui2/gui2_input.cpp',R/'gui2/gui2_input.h']
tests=[Path(__file__).resolve(),ROOT/'tests/touch_delivery_test.cpp',ROOT/'tests/devicefix_regression.py']
report=dict(status='PASS',cases=cases,sources={str(p):sha(p) for p in files},
            tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
            scope='Actual FIFO/inotify/epoll/read, minui registration/parser and GUI callback. ioctl device capabilities and LVGL are fixtures. No kernel driver, SPI, firmware or physical touch.')
(ROOT/'logs/touch-delivery.json').write_text(json.dumps(report,indent=2)+'\n')
