#!/usr/bin/env python3
"""Bounded tool console + actual worker/progress LVGL, large history and reentry.

UpdateSystemDetails is a condition-variable scan boundary, operation presentation
and DataManager are explicit doubles; unrelated vtable/jobs assert if reached.
No Android worker runtime, actual directory scan, GUI tick routing or DRM output.
"""
import argparse,json,subprocess,tempfile
from pathlib import Path
from haptics_ui_test import ROOT,SRC,LVGL,lvgl_library,extract,sha
from nested_partition_path_test import method

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--before',action='store_true');args=parser.parse_args()
 lib,prov=lvgl_library()
 names=['pages/progress_page.cpp','pages/console_page.cpp','components/icon.cpp','core/ui_helpers.cpp','core/ui_metrics.cpp','core/ui_event_guard.cpp','gui2_svg_cache.cpp','i18n/en.cpp']
 files=[SRC/n for n in names];worker=SRC/'backend/twrp_tools_backend.cpp';text=worker.read_text()
 harness=ROOT/'tests/tool_console_test.cpp'
 signatures=['int refreshsizes()', 'twrp_tools_backend::~twrp_tools_backend()', 'void twrp_tools_backend::join_finished_thread()', 'bool twrp_tools_backend::start(', 'void twrp_tools_backend::run(', 'tool_state twrp_tools_backend::status()', 'void twrp_tools_backend::acknowledge()']
 with tempfile.TemporaryDirectory(prefix='refresh-worker-') as tmp:
  p=Path(tmp);(p/'worker.inc').write_text('\n\n'.join(method(text,s) for s in signatures))
  gui=(ROOT/'backups/tool-console-pre-fix/gui2/gui2.cpp') if args.before else SRC/'gui2.cpp'
  gui_text=gui.read_text()
  (p/'callback.inc').write_text(extract(gui_text,'refresh_tool_progress'))
  (p/'console_callbacks.inc').write_text('\n'.join(extract(gui_text,n) for n in ['apply_progress_console_delta','poll_progress_console','poll_tool_console','gui2_loop_before_render','gui2_loop_after_present']))
  art=SRC/'image/ic_arrow_right.svg';(p/'gui2_svg_assets.h').write_bytes(subprocess.check_output(['python3',str(SRC/'generate_svg_header.py'),str(art)]))
  executor=SRC.parent/'twrp_operation_executor.cpp'
  cmd=['g++','-std=c++20','-O1','-g','-fsanitize=undefined','-fno-sanitize-recover=undefined','-DLV_CONF_INCLUDE_SIMPLE','-DLV_LVGL_H_INCLUDE_SIMPLE','-DTW_FRAMERATE=120','-I'+str(p),'-I'+str(SRC),'-I'+str(SRC.parent),'-I'+str(LVGL),str(harness),str(executor),*map(str,files),str(lib),'-lpthread','-lm','-o',str(p/'test')]
  subprocess.run(cmd,check=True);cases=[]
  for n in ['large-history','already-done','busy','history','generation','reentry']:
   r=subprocess.run([str(p/'test'),n],capture_output=True,text=True,timeout=20)
   cases.append(dict(case=n,status='PASS' if r.returncode==0 else 'FAIL',output=r.stdout+r.stderr));print(cases[-1],flush=True)
 files += [gui,harness,worker,executor,executor.with_suffix('.h'),SRC/'backend/twrp_tools_backend.h',SRC/'backend/tools_backend.h',SRC/'gui2.cpp',art,SRC/'generate_svg_header.py',Path(__file__).resolve(),ROOT/'tests/refresh_worker_chain_test.cpp',ROOT/'tests/haptics_ui_test.py',ROOT/'tests/nested_partition_path_test.py']+sorted({h for f in files for h in f.parent.glob('*.h')})
 report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,cases=cases,sources={str(f):sha(f) for f in files},lvgl=prov,compile_command=cmd,production_fix=True,baseline=args.before)
 (ROOT/'logs'/('tool-console-before.json' if args.before else 'tool-console.json')).write_text(json.dumps(report,indent=2)+'\n');return report['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
