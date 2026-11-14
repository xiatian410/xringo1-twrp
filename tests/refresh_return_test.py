#!/usr/bin/env python3
"""Exercise refresh return from the home ACTION payload and direct BACKUP route.

Original entry/refresh/storage/progress callbacks, relevant build/back branches,
router, tools worker and LVGL page host/progress. Backup/storage bodies, scan,
settings, fonts and display are explicit fixtures. No phone, mount or DRM access.
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from haptics_ui_test import ROOT, SRC, LVGL, extract, lvgl_library, sha
from nested_partition_path_test import method


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SRC/'gui2.cpp')
    parser.add_argument('--report', type=Path, default=ROOT/'logs/refresh-return-current.json')
    args = parser.parse_args()
    gui = args.source.read_text()
    worker = SRC/'backend/twrp_tools_backend.cpp'
    library, provenance = lvgl_library()
    production = ['pages/progress_page.cpp', 'pages/console_page.cpp', 'components/icon.cpp',
                  'core/ui_helpers.cpp', 'core/ui_metrics.cpp', 'core/ui_event_guard.cpp',
                  'gui2_svg_cache.cpp', 'i18n/en.cpp', 'shell/page_host.cpp',
                  'shell/page_scaffold.cpp', 'shell/navigation_fade.cpp', 'pages/page_router.cpp']
    files = [SRC/name for name in production]
    executor = SRC.parent/'twrp_operation_executor.cpp'
    signatures = ['int refreshsizes()', 'twrp_tools_backend::~twrp_tools_backend()',
                  'void twrp_tools_backend::join_finished_thread()',
                  'bool twrp_tools_backend::start(', 'void twrp_tools_backend::run(',
                  'tool_state twrp_tools_backend::status()',
                  'void twrp_tools_backend::acknowledge()']
    with tempfile.TemporaryDirectory(prefix='refresh-return-') as temp:
        work = Path(temp)
        (work/'worker.inc').write_text('\n\n'.join(method(worker.read_text(), s) for s in signatures))
        (work/'callback.inc').write_text(extract(gui, 'refresh_tool_progress'))
        fixture = (ROOT/'tests/refresh_worker_chain_test.cpp').read_text().split('int main(int argc,char**argv){', 1)[0]
        fixture = fixture.replace('}page_state;', '''
          std::string backup_name;
          struct { lv_obj_t* name_input=nullptr; } backup_view;
          gui2_pages::page_id select_storage_back=gui2_pages::page_id::HOME;
          std::vector<std::string> install_queue;
          bool install_from_file_manager=false, install_repack=false;
        }page_state;''')
        a = fixture.index('static struct {const char*running=')
        b = fixture.index('namespace gui2_i18n', a)
        request = method(gui, 'struct tool_request {') + ';\nstatic tool_request tool_job_request;\n'
        fixture = fixture[:a] + request + fixture[b:]
        (work/'worker_base.inc').write_text(fixture)
        callbacks = '\n\n'.join(extract(gui, name) for name in [
            'action_card_event_cb', 'backup_select_storage_cb', 'backup_refresh_sizes_cb',
            'progress_back_cb'])
        (work/'entry.inc').write_text(callbacks)
        # Keep exact production predicates and bodies for these two return routes.
        back = extract(gui, 'navigate_back')
        branches = [method(back, 'else if (page_router.current() == page_kind::'+name+')')
                    for name in ['SELECT_STORAGE', 'TOOL_PROGRESS']]
        (work/'back.inc').write_text('static void navigate_back() {\n' +
                                    branches[0][5:] + ' ' + branches[1] +
                                    ' else { assert(false); }\n}\n')
        build = extract(gui, 'build_page')
        cases = []
        for name in ['ACTION', 'BACKUP', 'TOOL_PROGRESS']:
            start = build.index('case page_kind::'+name+':')
            end = build.index('\n    case ', start)
            cases.append(build[start:end])
        (work/'routes.inc').write_text('static void build_page(const gui2_pages::page_request& request) {\n'
                                      'switch (request.id) {\n'+'\n'.join(cases)+
                                      '\ndefault: assert(false);\n}\n}\n')
        artwork = SRC/'image/ic_arrow_right.svg'
        (work/'gui2_svg_assets.h').write_bytes(subprocess.check_output([
            'python3', str(SRC/'generate_svg_header.py'), str(artwork)]))
        command = ['g++', '-std=c++20', '-O1', '-g', '-fsanitize=undefined',
                   '-fno-sanitize-recover=undefined', '-DLV_CONF_INCLUDE_SIMPLE',
                   '-DLV_LVGL_H_INCLUDE_SIMPLE', '-DTW_FRAMERATE=120',
                   '-I'+str(work), '-I'+str(SRC), '-I'+str(SRC.parent), '-I'+str(LVGL),
                   str(ROOT/'tests/refresh_return_test.cpp'), str(executor),
                   *map(str, files), str(library), '-lpthread', '-lm', '-o', str(work/'test')]
        subprocess.run(command, check=True)
        results = []
        for name in ['home-first', 'home-precompleted', 'home-custom-name',
                     'storage-return', 'direct-backup', 'home-repeated']:
            result = subprocess.run([str(work/'test'), name], capture_output=True,
                                    text=True, timeout=20)
            results.append(dict(case=name, status='PASS' if result.returncode == 0 else 'FAIL',
                                returncode=result.returncode, output=result.stdout+result.stderr))
            print(results[-1], flush=True)
    files += [args.source, worker, executor, executor.with_suffix('.h'), artwork,
              SRC/'generate_svg_header.py', ROOT/'tests/refresh_return_test.cpp', Path(__file__),
              ROOT/'tests/refresh_worker_chain_test.cpp', ROOT/'tests/haptics_ui_test.py',
              ROOT/'tests/nested_partition_path_test.py']
    files += sorted({h for f in files for h in f.parent.glob('*.h')})
    report = dict(status='PASS' if all(c['status']=='PASS' for c in results) else 'FAIL',
                  scope=__doc__, cases=results, sources={str(f):sha(f) for f in files},
                  lvgl=provenance, compile_command=command,
                  route_scope='Exact production ACTION/BACKUP/TOOL_PROGRESS dispatch and SELECT_STORAGE/TOOL_PROGRESS back branches; unrelated branches excluded.')
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    return report['status'] != 'PASS'


if __name__ == '__main__':
    raise SystemExit(main())
