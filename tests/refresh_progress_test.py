#!/usr/bin/env python3
"""Actual tool progress adapter + LVGL terminal transition; no Android worker/DRM."""
import json,subprocess,tempfile
from pathlib import Path
from haptics_ui_test import ROOT,SRC,LVGL,lvgl_library,extract,sha

def main():
 lib,prov=lvgl_library();names=['pages/progress_page.cpp','pages/console_page.cpp','components/icon.cpp','core/ui_helpers.cpp','core/ui_metrics.cpp','core/ui_event_guard.cpp','gui2_svg_cache.cpp','i18n/en.cpp'];files=[SRC/n for n in names]
 with tempfile.TemporaryDirectory(prefix='refresh-progress-') as tmp:
  p=Path(tmp);(p/'callback.inc').write_text(extract((SRC/'gui2.cpp').read_text(),'refresh_tool_progress'))
  art=SRC/'image/ic_arrow_right.svg';(p/'gui2_svg_assets.h').write_bytes(subprocess.check_output(['python3',str(SRC/'generate_svg_header.py'),str(art)]))
  cmd=['g++','-std=c++20','-O1','-g','-fsanitize=undefined','-fno-sanitize-recover=undefined','-DLV_CONF_INCLUDE_SIMPLE','-DLV_LVGL_H_INCLUDE_SIMPLE','-DTW_FRAMERATE=120','-I'+str(p),'-I'+str(SRC),'-I'+str(LVGL),str(ROOT/'tests/refresh_progress_test.cpp'),*map(str,files),str(lib),'-lpthread','-lm','-o',str(p/'test')]
  subprocess.run(cmd,check=True);cases=[]
  for n in ['done','failed','immediate']:
   r=subprocess.run([str(p/'test'),n],capture_output=True,text=True,timeout=20);cases.append(dict(case=n,status='PASS' if r.returncode==0 else 'FAIL',output=r.stdout+r.stderr));print(cases[-1],flush=True)
 files += [SRC/'gui2.cpp',art,SRC/'generate_svg_header.py',Path(__file__).resolve(),ROOT/'tests/refresh_progress_test.cpp']+sorted({h for f in files for h in f.parent.glob('*.h')})
 report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,cases=cases,sources={str(f):sha(f) for f in files},lvgl=prov,compile_command=cmd)
 (ROOT/'logs/refresh-progress.json').write_text(json.dumps(report,indent=2)+'\n');return report['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
