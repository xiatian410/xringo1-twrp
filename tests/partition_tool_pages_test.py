#!/usr/bin/env python3
"""Join partition tool pages/callbacks, LVGL pointer input and actual tool worker.

Original repair/resize/changefilesystem wrappers call a condition-variable
PartitionManager boundary, not mkfs/fsck. The router dispatches the original
selected page functions; scaffold ownership uses page_host and relevant original
detach/reset statements. Three partition/confirmation/progress back branches
execute unchanged. Other routing, details/storage, settings, fonts, console and
display submission are explicit fixtures. No phone, physical mount or reboot.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile

from haptics_ui_test import ROOT, SRC, LVGL, lvgl_library, extract, sha
from nested_partition_path_test import method


def leaf(text, signature):
    definition = re.search(re.escape(signature) + r'[^;{]*\)\s*\{', text)
    assert definition, signature
    return method(text[definition.start():], signature)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=ROOT/'logs/partition-tool-pages.json')
    args = parser.parse_args()
    library, lvgl = lvgl_library()
    gui = SRC/'gui2.cpp'
    text = gui.read_text()
    worker = SRC/'backend/twrp_tools_backend.cpp'
    backend = worker.read_text()
    production = ['pages/tool_pages.cpp', 'pages/progress_page.cpp', 'pages/console_page.cpp',
                  'pages/page_router.cpp', 'shell/page_host.cpp', 'shell/page_scaffold.cpp',
                  'shell/navigation_fade.cpp', 'components/swipe_slider.cpp',
                  'components/check_row.cpp', 'components/setting_card.cpp',
                  'components/tip_card.cpp', 'components/section_label.cpp',
                  'components/icon.cpp', 'core/ui_helpers.cpp', 'core/ui_metrics.cpp',
                  'core/ui_event_guard.cpp', 'gui2_svg_cache.cpp', 'i18n/en.cpp']
    files = [SRC/name for name in production]
    executor = SRC.parent/'twrp_operation_executor.cpp'
    selected = ['open_tool_confirm', 'create_bottom_swipe', 'start_tool_job',
                'tool_confirmed', 'tool_check_event_cb', 'show_tool_confirm_page',
                'refresh_tool_progress', 'show_tool_progress_page',
                'partition_action_event_cb', 'show_partition_options_page',
                'change_fs_choice_event_cb', 'change_fs_confirmed', 'show_change_fs_page',
                'progress_back_cb', 'add_progress_actions']
    cases = []
    with tempfile.TemporaryDirectory(prefix='partition-tool-pages-') as tmp:
        work = Path(tmp)
        start = text.index('struct tool_request {')
        (work/'request.inc').write_text(text[start:text.index('\n};', start)+3])
        start = text.index('static gui2_backend::partition_details partition_info;')
        end = text.index('// checkpartitionlist:', start)
        (work/'partition_state.inc').write_text(text[start:end])
        callbacks = '\n\n'.join(extract(text, name) for name in selected)
        callbacks += '\n'+leaf(text, 'static int bottom_swipe_reserved(')
        callbacks += '\n'+leaf(text, 'static std::string format_text(')
        callbacks += '\n'+leaf(text, 'static gui2_pages::page_request page_at(').replace(
            'const void* payload = nullptr', 'const void* payload')
        (work/'callbacks.inc').write_text(callbacks)
        back = extract(text, 'navigate_back')
        start = back.index('else if (page_router.current() == page_kind::PARTITION_OPTIONS)')
        end = back.index(' else if (page_router.current() == page_kind::TOOL_INPUT)', start)
        (work/'back.inc').write_text('static void navigate_back(){\n'+back[start:end].replace('else if', 'if', 1)+'\n}')
        scaffold = extract(text, 'create_page_scaffold')
        lines = [line for line in scaffold.splitlines() if any(part in line for part in [
            'page_state.change_fs_confirm.detach()', 'page_state.tool_confirm.detach()',
            'page_state.tool_progress = {}', 'console_window_reset(&page_state.tool_console)',
            'page_state.tool_console_armed = false'])]
        assert len(lines) == 5
        (work/'reset.inc').write_text('\n'.join(lines))
        signatures = ['int repair(', 'int resize(', 'int changefilesystem(',
                      'twrp_tools_backend::~twrp_tools_backend()',
                      'void twrp_tools_backend::join_finished_thread()',
                      'bool twrp_tools_backend::start(', 'void twrp_tools_backend::run(',
                      'tool_state twrp_tools_backend::status()', 'void twrp_tools_backend::acknowledge()']
        (work/'worker.inc').write_text('\n\n'.join(method(backend, s) for s in signatures))
        wipe = SRC/'pages/wipe_page.cpp'
        (work/'wipe_height.inc').write_text(method(wipe.read_text(), 'int wipe_track_height()'))
        artwork = [SRC/'image/ic_arrow_right.svg', SRC/'image/ic_slider_arrow.svg']
        (work/'gui2_svg_assets.h').write_bytes(subprocess.check_output([
            'python3', str(SRC/'generate_svg_header.py'), *map(str, artwork)]))
        command = ['g++', '-std=c++20', '-O1', '-g', '-fsanitize=undefined',
                   '-fno-sanitize-recover=undefined', '-DLV_CONF_INCLUDE_SIMPLE',
                   '-DLV_LVGL_H_INCLUDE_SIMPLE', '-DTW_FRAMERATE=120',
                   '-I'+str(work), '-I'+str(SRC), '-I'+str(SRC.parent), '-I'+str(LVGL),
                   str(ROOT/'tests/partition_tool_pages_test.cpp'), str(executor),
                   *map(str, files), str(library), '-lpthread', '-lm', '-o', str(work/'test')]
        subprocess.run(command, check=True)
        for name in ['repair-success', 'repair-failure', 'resize-success', 'resize-failure',
                     'format-success', 'format-failure', 'format-rejected',
                     'format-unselected', 'confirm-back', 'format-reuse']:
            result = subprocess.run([str(work/'test'), name], capture_output=True, text=True, timeout=25)
            cases.append(dict(name=name, status='PASS' if result.returncode == 0 else 'FAIL',
                              returncode=result.returncode, stdout=result.stdout, stderr=result.stderr))
            print(name, cases[-1]['status'], flush=True)
    files += [gui, worker, executor, executor.with_suffix('.h'), wipe,
              SRC/'backend/twrp_tools_backend.h', SRC/'backend/tools_backend.h',
              SRC/'generate_svg_header.py', *artwork, Path(__file__),
              ROOT/'tests/partition_tool_pages_test.cpp', ROOT/'tests/haptics_ui_test.py',
              ROOT/'tests/nested_partition_path_test.py']
    files += sorted({h for f in files if f.is_file() for h in f.parent.glob('*.h')})
    report = dict(status='PASS' if all(c['status'] == 'PASS' for c in cases) else 'FAIL',
                  scope=__doc__, cases=cases, sources={str(p): sha(p) for p in files},
                  lvgl=lvgl, compile_command=command, production_changed=False,
                  full_filesystem_lifecycle=False, hardware_testing=False)
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
