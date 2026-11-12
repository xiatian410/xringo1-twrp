#!/usr/bin/env python3
"""Execute GUI2 completion lifecycle and worker bodies with controlled clocks.

Production operation.cpp, hardware settings, DataManager::Vibrate, screen tick, backup/restore/ZIP
worker bodies execute on the host. Storage jobs, properties, performance hooks,
screen wake and the final vibration device are substitutes. No device is used.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = Path('/root/AAA/twrp/bootable/recovery')
CASES = ['short', 'threshold', 'above-threshold', 'long', 'wall-forward',
         'wall-backward', 'duration-setting', 'disabled', 'failed', 'duplicate-end',
         'unmatched-end', 'repeated-start', 'sequential', 'completion-reset',
         'wake-once', 'wake-coalesced', 'concurrent', 'foreign-end',
         'backup-success', 'backup-failure', 'backup-cancel', 'backup-invalid-name',
         'restore-success', 'restore-failure', 'zip-queue', 'zip-failure',
         'global-disabled', 'oversized-setting', 'negative-setting', 'missing-device',
         'late-device', 'unplug']


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def method(source, signature):
    text = source.read_text()
    start = text.index(signature)
    opening = text.index('{', start)
    end, depth = opening + 1, 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SRC)
    parser.add_argument('--report', type=Path, default=ROOT/'logs/operation-feedback.json')
    args = parser.parse_args()
    production = args.source/'gui2/backend/twrp_operation.cpp'
    extract = {
        'data.cpp': 'void DataManager::Vibrate(',
        'gui2/backend/twrp_screen_backend.cpp': 'void twrp_screen_backend::tick(',
        'gui2/backend/twrp_backup_backend.cpp': 'void twrp_backup_backend::run(',
        'gui2/backend/twrp_restore_backend.cpp': 'void twrp_restore_backend::run(',
        'gui2/backend/twrp_install_backend.cpp': 'void twrp_install_backend::run_zip(',
    }
    with tempfile.TemporaryDirectory(prefix='dijun-operation-feedback-') as temp:
        temp = Path(temp)
        for folder in ['cutils', 'twrpperf', 'twrpminui']:
            (temp/folder).mkdir()
        (temp/'operation.cpp').write_bytes(production.read_bytes())
        (temp/'hardware.cpp').write_bytes((SRC/'gui2/backend/twrp_hardware_settings.cpp').read_bytes())
        (temp/'twrp_functions.hpp').write_text('#pragma once\n')
        (temp/'twrpminui/minui.h').write_text('#pragma once\nint vibrate(int);\nint haptics_available();\n')
        (temp/'data.hpp').write_text('''#pragma once
#include <string>
class DataManager {public:
 static void SetValue(const std::string&,int);
 static void SetValue(const std::string&,const std::string&);
 static void GetValue(const std::string&,int&);
 static void GetValue(const std::string&,std::string&);
 static int GetIntValue(const std::string&);
 static void Vibrate(const std::string&);
};
''')
        (temp/'twcommon.h').write_text('#pragma once\n#include <cstdio>\n#define LOGINFO(...) std::printf(__VA_ARGS__)\n')
        (temp/'cutils/properties.h').write_text('#pragma once\nint property_set(const char*,const char*);\n')
        (temp/'twrpperf/perf_manager.hpp').write_text('''#pragma once
namespace twrp {class TwrpPerfManager {public:
 static TwrpPerfManager& Get(); void BeginWorkload(); void EndWorkload();
};}
''')
        bodies = []
        for name, signature in extract.items():
            body = method(SRC/name, signature)
            if name != 'data.cpp':
                body = 'namespace gui2_backend {\n' + body + '\n}'
            bodies.append(body)
        harness = (ROOT/'tests/operation_feedback_test.cpp').read_text()
        (temp/'test.cpp').write_text(harness.replace('// PRODUCTION_METHODS', '\n'.join(bodies)))
        cases = []
        for no_haptics in [False, True]:
            exe = temp/('no-haptics' if no_haptics else 'test')
            command = ['g++', '-std=c++23', '-Wall', '-Wextra', '-Werror',
                       '-Wno-unused-parameter', '-pthread', '-fsanitize=address,undefined',
                       '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-no-pie', '-g',
                       '-DAB_OTA_UPDATER', '-I'+str(temp), '-I'+str(SRC/'gui2/backend'),
                       '-I'+str(SRC), str(temp/'operation.cpp'), str(temp/'hardware.cpp'), str(temp/'test.cpp'),
                       str(SRC/'gui2/backend/haptics_controller.cpp'),
                       '-Wl,--wrap=time', '-o', str(exe)]
            if no_haptics:
                command.insert(1, '-DTW_NO_HAPTICS')
            subprocess.run(command, check=True)
            for case in CASES:
                run = subprocess.run([str(exe), case], capture_output=True, text=True, timeout=10)
                record = dict(case=case, no_haptics=no_haptics, status='PASS' if run.returncode==0 else 'FAIL',
                              returncode=run.returncode, output=(run.stdout+run.stderr).strip())
                cases.append(record)
                print(record['status'], 'no-haptics' if no_haptics else 'default', case, flush=True)
        shared = list(extract) + ['variables.h', 'gui2/backend/twrp_operation.h',
                                 'gui2/backend/backup_backend.h', 'gui2/backend/restore_backend.h',
                                 'gui2/backend/install_backend.h', 'gui2/backend/twrp_hardware_settings.cpp',
                                 'gui2/backend/twrp_hardware_settings.h', 'gui2/backend/hardware_settings.h',
                                 'gui2/backend/settings_store.h', 'gui2/backend/backlight_controller.h',
                                 'gui2/backend/haptics_controller.cpp','gui2/backend/haptics_controller.h']
        report = dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',
                      scope=__doc__.strip(), cases=cases, sources={str(production):sha(production)},
                      shared_sources={str(SRC/n):sha(SRC/n) for n in shared},
                      test_sources={str(p):sha(p) for p in [Path(__file__).resolve(), ROOT/'tests/operation_feedback_test.cpp']},
                      boundaries=['No real partition/archive operation, motor, display, Android property service or performance governor.',
                                  'Full worker bodies execute, but start/acknowledge and partition-manager sessions are not covered.',
                                  'Monotonic and wall clocks are controlled independently; concurrency uses real threads and semaphores.',
                                  'Wake events intentionally coalesce until the UI tick; completion is not a success indicator.'])
        args.report.write_text(json.dumps(report, indent=2)+'\n')
    return 0 if report['status']=='PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
