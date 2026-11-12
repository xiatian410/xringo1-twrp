#!/usr/bin/env python3
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
A=Path('/root/AAA/twrp');R=A/'bootable/recovery'
with tempfile.TemporaryDirectory(prefix='dijun-touch-') as d:
    d=Path(d);(d/'cutils').mkdir()
    (d/'compat.h').write_text('#include <pthread.h>\n#include <sys/stat.h>\n#define __unused __attribute__((unused))\n')
    (d/'cutils/properties.h').write_text('#pragma once\n#define PROPERTY_VALUE_MAX 92\nint property_get(const char*,char*,const char*);\n')
    subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Wno-sign-compare','-Wno-unused-parameter',
                    '-Wno-unused-function','-Wno-attributes','-include',str(d/'compat.h'),
                    '-I'+str(d),'-I'+str(R),'-I'+str(R/'twrpminui/include'),
                    '-I'+str(R/'twrpinstall/include'),'-I'+str(A/'system/libbase/include'),
                    str(ROOT/'tests/dijun_touch_test.cpp'),'-o',str(d/'test')],check=True)
    subprocess.run([str(d/'test')],check=True,timeout=10)
report=dict(status='PASS',scope='Actual twrp_input.cpp with historical dijun evdev ranges; no physical input/DRM or timing measurement.',
            source_sha256=hashlib.sha256((R/'twrpminui/twrp_input.cpp').read_bytes()).hexdigest(),
            cases=['100x-range','four-rotations-and-corners','outside-and-overflow','historical-swipe-samples','ten-contacts','ten-releases'])
(ROOT/'logs/dijun-touch-regression.json').write_text(json.dumps(report,indent=2)+'\n')
