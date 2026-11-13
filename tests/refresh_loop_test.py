#!/usr/bin/env python3
"""Original GUI tick/app loop to worker DONE and LVGL, with explicit submit gate.

No Android/device services, input, performance policy or DRM. Other-page pollers
fail on entry. The blocked-present case models a submit wait; it does not claim
that the supplied device incident had a permanent display hang.
"""
import json
import subprocess
import tempfile
from pathlib import Path
from haptics_ui_test import ROOT, SRC, LVGL, lvgl_library, extract, sha
from nested_partition_path_test import method


def main():
    lib, provenance = lvgl_library()
    names = ['pages/progress_page.cpp', 'pages/console_page.cpp', 'components/icon.cpp',
             'core/ui_helpers.cpp', 'core/ui_metrics.cpp', 'core/ui_event_guard.cpp',
             'gui2_svg_cache.cpp', 'i18n/en.cpp', 'shell/page_host.cpp',
             'shell/page_scaffold.cpp', 'shell/navigation_fade.cpp', 'pages/page_router.cpp',
             'app/gui2_loop.cpp']
    files = [SRC / n for n in names]
    worker = SRC / 'backend/twrp_tools_backend.cpp'
    gui = SRC / 'gui2.cpp'
    executor = SRC.parent / 'twrp_operation_executor.cpp'
    signatures = ['int refreshsizes()', 'twrp_tools_backend::~twrp_tools_backend()',
                  'void twrp_tools_backend::join_finished_thread()',
                  'bool twrp_tools_backend::start(', 'void twrp_tools_backend::run(',
                  'tool_state twrp_tools_backend::status()',
                  'void twrp_tools_backend::acknowledge()']
    extra = '''
      uint64_t console_last_poll_ms=0, install_last_poll_ms=0, fastbootd_last_poll_ms=0,
        tool_last_poll_ms=0, sideload_last_poll_ms=0, terminal_last_poll_ms=0,
        wipe_last_poll_ms=0, decrypt_prompt_ms=0, decrypt_last_poll_ms=0,
        restore_last_poll_ms=0, backup_last_poll_ms=0;
      struct { gui2_pages::console_page_view output; } terminal_view;
      gui2_pages::console_page_view console;
    '''
    with tempfile.TemporaryDirectory(prefix='refresh-loop-') as tmp:
        p = Path(tmp)
        (p / 'worker.inc').write_text('\n\n'.join(method(worker.read_text(), s) for s in signatures))
        (p / 'callback.inc').write_text(extract(gui.read_text(), 'refresh_tool_progress'))
        (p / 'loop_tick.inc').write_text(extract(gui.read_text(), 'gui2_loop_tick'))
        fixture = (ROOT / 'tests/refresh_worker_chain_test.cpp').read_text()
        assert fixture.count('}page_state;') == 1
        (p / 'refresh_worker_chain_test.cpp').write_text(fixture.split('int main(int argc,char**argv){', 1)[0].replace('}page_state;', extra + '}page_state;'))
        lifecycle = (ROOT / 'tests/refresh_page_lifecycle_test.cpp').read_text()
        (p / 'loop_lifecycle.inc').write_text(lifecycle.split('int main(int argc,char**argv){', 1)[0])
        perf = p / 'twrpperf'
        perf.mkdir()
        (perf / 'perf_manager.hpp').write_text('''#pragma once
#include <cstdint>
namespace twrp { struct TwrpPerfManager {
static TwrpPerfManager& Get() { static TwrpPerfManager p; return p; }
void Initialize() {} void Update() {} void NotifyInteraction() {} void NotifyFrameActivity() {}
uint32_t ClampTimeoutMs(uint32_t ms) { return ms; }
}; }
''')
        art = SRC / 'image/ic_arrow_right.svg'
        (p / 'gui2_svg_assets.h').write_bytes(subprocess.check_output([
            'python3', str(SRC / 'generate_svg_header.py'), str(art)]))
        cmd = ['g++', '-std=c++20', '-O1', '-g', '-fsanitize=undefined',
               '-fno-sanitize-recover=undefined', '-DLV_CONF_INCLUDE_SIMPLE',
               '-DLV_LVGL_H_INCLUDE_SIMPLE', '-DTW_FRAMERATE=120',
               '-I'+str(p), '-I'+str(SRC), '-I'+str(SRC.parent), '-I'+str(LVGL),
               str(ROOT / 'tests/refresh_loop_test.cpp'), str(executor),
               *map(str, files), str(lib), '-lpthread', '-lm', '-o', str(p / 'test')]
        subprocess.run(cmd, check=True)
        cases = []
        for case in ['running-to-done', 'already-done', 'blocked-present']:
            result = subprocess.run([str(p / 'test'), case], capture_output=True, text=True, timeout=12)
            cases.append(dict(case=case, status='PASS' if result.returncode == 0 else 'FAIL',
                              output=result.stdout + result.stderr))
            print(cases[-1], flush=True)
    files += [worker, gui, executor, executor.with_suffix('.h'), art,
              SRC / 'generate_svg_header.py', Path(__file__).resolve(),
              ROOT / 'tests/refresh_loop_test.cpp', ROOT / 'tests/refresh_worker_chain_test.cpp',
              ROOT / 'tests/refresh_page_lifecycle_test.cpp', ROOT / 'tests/haptics_ui_test.py',
              ROOT / 'tests/nested_partition_path_test.py']
    files += sorted({h for f in files for h in f.parent.glob('*.h')})
    report = dict(status='PASS' if all(c['status'] == 'PASS' for c in cases) else 'FAIL',
                  scope=__doc__, cases=cases, production_fix=False,
                  fixture_boundaries=['scan', 'DataManager/operation presentation', 'fonts/flush',
                                      'input', 'performance policy', 'submit gate',
                                      'unrelated GUI services and console poll', 'route composition'],
                  sources={str(f): sha(f) for f in files}, lvgl=provenance, compile_command=cmd)
    (ROOT / 'logs/refresh-loop.json').write_text(json.dumps(report, indent=2)+'\n')
    return report['status'] != 'PASS'


if __name__ == '__main__':
    raise SystemExit(main())
