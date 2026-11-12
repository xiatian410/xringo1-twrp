#!/usr/bin/env python3
"""Actual LVGL pointer dispatch and general-settings callback; storage/hardware substituted."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from haptics_ui_test import ROOT, SRC, LVGL, lvgl_library, extract, sha

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--component',type=Path,default=SRC/'components/check_row.cpp')
parser.add_argument('--output',type=Path,default=ROOT/'logs/settings-row.json')
args=parser.parse_args()
library, provenance=lvgl_library()
sources=[args.component,SRC/'core/ui_event_guard.cpp',SRC/'core/ui_helpers.cpp',SRC/'core/ui_metrics.cpp']
with tempfile.TemporaryDirectory(prefix='settings-row-') as temp:
    temp=Path(temp)
    (temp/'callback.inc').write_text(extract((SRC/'gui2.cpp').read_text(),'general_setting_event_cb'))
    command=['g++','-std=c++20','-O1','-g','-fsanitize=undefined','-fno-sanitize-recover=undefined',
             '-DLV_CONF_INCLUDE_SIMPLE','-DLV_LVGL_H_INCLUDE_SIMPLE','-DTW_FRAMERATE=120',
             '-I'+str(temp),'-I'+str(SRC),'-I'+str(LVGL),str(ROOT/'tests/settings_row_test.cpp'),
             *map(str,sources),str(library),'-lpthread','-lm','-o',str(temp/'test')]
    subprocess.run(command,check=True)
    cases=[]
    for kind in ['check','switch']:
        for case in ['label','indicator','blank','double','drag-out','drag-back','press-lost','scroll','disabled','rollback']:
            r=subprocess.run([str(temp/'test'),kind,case],capture_output=True,text=True,timeout=15)
            cases.append(dict(kind=kind,case=case,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
            print(kind,case,'PASS' if r.returncode==0 else 'FAIL',r.stdout+r.stderr,flush=True)
    files=sources+[SRC/'gui2.cpp',SRC/'components/check_row.h',SRC/'pages/general_settings_page.h',
                   ROOT/'tests/settings_row_test.cpp',Path(__file__).resolve()]
    report=dict(status='PASS' if all(c['returncode']==0 for c in cases) else 'FAIL',scope=__doc__,
                cases=cases,sources={str(p):sha(p) for p in files},lvgl=provenance)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='PASS' else 1)
