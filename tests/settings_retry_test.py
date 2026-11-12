#!/usr/bin/env python3
"""Real GUI2 language/theme callbacks with LVGL dispatch and failing storage fixtures.

This checks in-memory rollback and retry after failures before disk publication.
It does not execute DataManager, actual persist, the full shell or a phone.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from haptics_ui_test import ROOT,SRC,extract,lvgl_library,sha

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,default=SRC/'gui2.cpp')
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
library,provenance=lvgl_library()
with tempfile.TemporaryDirectory(prefix='settings-retry-') as temp:
    temp=Path(temp)
    (temp/'callbacks.inc').write_text('\n'.join(extract(args.source.read_text(),name) for name in
        ['apply_language_event_cb','appearance_event_cb']))
    subprocess.run(['g++','-std=c++20','-O1','-g','-fsanitize=undefined',
        '-fno-sanitize-recover=undefined','-DLV_CONF_INCLUDE_SIMPLE','-DLV_LVGL_H_INCLUDE_SIMPLE',
        '-I'+str(temp),'-I'+str(SRC),'-I'+str(Path('/root/AAA/twrp/external/lvgl')),
        str(ROOT/'tests/settings_retry_test.cpp'),str(library),'-lpthread','-lm','-o',str(temp/'test')],check=True)
    cases=[]
    for kind in ['language','theme']:
        for name in ['success','write-failure','flush-failure','retry']+(['decrypt'] if kind=='language' else []):
            r=subprocess.run([str(temp/'test'),kind,name],text=True,capture_output=True,timeout=15)
            cases.append(dict(kind=kind,case=name,returncode=r.returncode,output=r.stdout+r.stderr))
            print(kind,name,'PASS' if r.returncode==0 else 'FAIL',flush=True)
    files=[args.source,Path(__file__).resolve(),ROOT/'tests/settings_retry_test.cpp']
    report=dict(status='PASS' if all(c['returncode']==0 for c in cases) else 'FAIL',
        scope=__doc__,cases=cases,sources={str(p):sha(p) for p in files},lvgl=provenance)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='PASS' else 1)
