#!/usr/bin/env python3
"""Actual status provider/controller and LVGL temperature layout; settings/time fixtures, no sensor/DRM."""
import argparse,json,subprocess,tempfile
from pathlib import Path
from haptics_ui_test import ROOT,SRC,LVGL,sha,lvgl_library,save_png

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--status-source',type=Path,default=SRC/'shell/status_bar.cpp');parser.add_argument('--report',type=Path,default=ROOT/'logs/temperature-camera.json');args=parser.parse_args()
 library,provenance=lvgl_library()
 production=['backend/status_backend.cpp','shell/status_bar.cpp','shell/status_bar_controller.cpp','core/ui_helpers.cpp','core/ui_metrics.cpp','components/icon.cpp','gui2_svg_cache.cpp']
 art=sorted((SRC/'image').glob('ic_battery_*.svg'))+[SRC/'image/ic_wifi.svg']
 cases=[];frames=[]
 with tempfile.TemporaryDirectory(prefix='temperature-ui-') as tmp:
  tmp=Path(tmp)
  (tmp/'gui2_svg_assets.h').write_bytes(subprocess.check_output(['python3',str(SRC/'generate_svg_header.py'),*map(str,art)]))
  subprocess.run(['g++','-std=c++20','-O1','-g','-fsanitize=undefined','-fno-sanitize-recover=undefined','-DLV_CONF_INCLUDE_SIMPLE','-DLV_LVGL_H_INCLUDE_SIMPLE','-DTW_FRAMERATE=120','-I'+str(tmp),'-I'+str(SRC),'-I'+str(LVGL),str(ROOT/'tests/temperature_ui_test.cpp'),*[str(args.status_source if n=='shell/status_bar.cpp' else SRC/n) for n in production],str(library),'-lpthread','-lm','-o',str(tmp/'test')],check=True)
  scenarios=[('parser',480,16,1),('pressure',480,24,1),('pressure',480,24,0)]
  for width,font in [(360,16),(480,16),(1440,48),(2560,48)]:
   for dark in [0,1]:scenarios.append(('transitions',width,font,dark))
  for kind,width,font,dark in scenarios:
   label=f'{kind}-{width}-{font}-{dark}';ppm=tmp/(label+'.ppm')
   r=subprocess.run([str(tmp/'test'),kind,str(width),str(font),str(dark),str(ppm)],capture_output=True,text=True,timeout=20)
   cases.append(dict(case=label,returncode=r.returncode,output=r.stdout+r.stderr));print(label,r.returncode,r.stdout+r.stderr,flush=True)
   if ppm.exists():frames.append(save_png(ppm,ROOT/'logs/temperature-ui-frames'/(label+'.png')))
 files=[args.status_source if n=='shell/status_bar.cpp' else SRC/n for n in production]+[SRC/n for n in ['backend/status_backend.h','shell/status_bar.h','shell/status_bar_controller.h','backend/settings_store.h','core/ui_metrics.h','lv_conf.h','generate_svg_header.py']]+art+[Path(__file__).resolve(),ROOT/'tests/temperature_ui_test.cpp',ROOT/'tests/haptics_ui_test.py']
 report=dict(status='PASS' if all(c['returncode']==0 for c in cases) else 'FAIL',scope=__doc__,cases=cases,sources={str(p):sha(p) for p in files},lvgl=provenance,frames=frames)
 args.report.write_text(json.dumps(report,indent=2)+'\n')
 assert report['status']=='PASS'
if __name__=='__main__':main()
