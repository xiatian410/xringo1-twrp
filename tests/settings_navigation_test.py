#!/usr/bin/env python3
"""Real LVGL settings index, cards, page host/transition/scroll and original dispatch callback.

Destination navigation is recorded, not executed. Metrics/fonts and hardware are
host fixtures; this does not prove Android touch, persistence or destination pages.
"""
import json
import re
import subprocess
import tempfile
from haptics_ui_test import ROOT, SRC, LVGL, lvgl_library, extract, sha

def main():
    library, provenance = lvgl_library()
    production = ['pages/settings_page.cpp', 'pages/action_page.cpp', 'components/setting_card.cpp',
                  'components/icon.cpp', 'core/ui_event_guard.cpp', 'core/ui_helpers.cpp',
                  'core/ui_metrics.cpp', 'shell/page_host.cpp', 'shell/page_scaffold.cpp',
                  'shell/navigation_fade.cpp', 'gui2_svg_cache.cpp', 'i18n/en.cpp']
    sources = [SRC/name for name in production]
    with tempfile.TemporaryDirectory(prefix='settings-navigation-') as tmp:
        from pathlib import Path
        temp = Path(tmp)
        gui = (SRC/'gui2.cpp').read_text()
        (temp/'callback.inc').write_text(extract(gui, 'settings_option_event_cb'))
        (temp/'targets.inc').write_text(re.search(r'enum class settings_target \{.*?\n\};', gui, re.S)[0])
        artwork = SRC/'image/ic_arrow_right.svg'
        assert artwork.is_file()
        (temp/'gui2_svg_assets.h').write_bytes(subprocess.check_output(
            ['python3', str(SRC/'generate_svg_header.py'), str(artwork)]))
        command = ['g++', '-std=c++20', '-O1', '-g', '-fsanitize=undefined',
                   '-fno-sanitize-recover=undefined', '-DLV_CONF_INCLUDE_SIMPLE',
                   '-DLV_LVGL_H_INCLUDE_SIMPLE', '-DTW_FRAMERATE=120',
                   '-I'+str(temp), '-I'+str(SRC), '-I'+str(LVGL),
                   str(ROOT/'tests/settings_navigation_test.cpp'), *map(str, sources),
                   str(library), '-lpthread', '-lm', '-o', str(temp/'test')]
        subprocess.run(command, check=True)
        cases=[]
        for index in range(9):
            for mode in ['label', 'detail', 'arrow', 'blank', 'drag-out']:
                result = subprocess.run([str(temp/'test'), str(index), mode], capture_output=True,
                                        text=True, timeout=20)
                cases.append(dict(index=index,mode=mode,returncode=result.returncode,
                                  stdout=result.stdout,stderr=result.stderr))
                print(index,mode,'PASS' if result.returncode==0 else 'FAIL',result.stdout+result.stderr,flush=True)
    files=sources+[SRC/'gui2.cpp',artwork,SRC/'generate_svg_header.py',
                   ROOT/'tests/settings_navigation_test.cpp',ROOT/'tests/settings_navigation_test.py']
    # Headers participating in the host compilation are bound separately from LVGL.
    files += sorted({h for p in sources for h in p.parent.glob('*.h')})
    report=dict(status='PASS' if all(c['returncode']==0 for c in cases) else 'FAIL',
                scope=__doc__,cases=cases,sources={str(p):sha(p) for p in files},lvgl=provenance)
    (ROOT/'logs/settings-navigation.json').write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':
    raise SystemExit(main())
