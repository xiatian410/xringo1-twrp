#!/usr/bin/env python3
"""Run real InfoManager and DataManager settings methods on disposable files.

Android mount/property/metadata boundaries are substituted. libc serialization,
filesystem operations, timezone conversion, and injected I/O failures are real
host executions; this is not a phone RTC or Android mount test.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = Path('/root/AAA/twrp/bootable/recovery')


def method(text, signature):
    start = text.index(signature)
    opening = text.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


parser = argparse.ArgumentParser()
parser.add_argument('--report', type=Path, default=ROOT / 'logs/settings-regression.json')
args = parser.parse_args()
info = (SRC / 'infomanager.cpp').read_text()
data = (SRC / 'data.cpp').read_text()
variables = (SRC / 'variables.h').read_text()
methods = '\n'.join(method(data, sig) for sig in [
    'int DataManager::LoadValues(', 'int DataManager::SaveValues()',
    'int DataManager::Flush()', 'void DataManager::UpdateTimezoneEnvironment()'])
cases = ['roundtrip', 'short-write', 'no-space', 'flush-error', 'close-error',
         'sync-error', 'rename-error', 'create-error', 'directory-sync-error',
         'missing-parent', 'interrupted-before-commit', 'malformed', 'limits',
         'version', 'manager-failure', 'mount-failure', 'backup-without-persist', 'timezone-migration', 'timezone-custom',
         'timezone-dst', 'timezone-no-device-default']
with tempfile.TemporaryDirectory(prefix='dijun-settings-') as tmp:
    tmp = Path(tmp)
    (tmp / 'android-base').mkdir()
    (tmp / 'fixture').mkdir()
    stubs = {
        'android-base/file.h': '''#pragma once
#include <fstream>
#include <iterator>
#include <string>
namespace android::base {
inline bool ReadFileToString(const std::string& p, std::string* s) {
 std::ifstream f(p, std::ios::binary); if(!f)return false;
 *s=std::string(std::istreambuf_iterator<char>(f),{});return !f.bad();
}}
''',
        'android-base/parsedouble.h': '''#pragma once
#include <cstdlib>
namespace android::base { inline bool ParseFloat(const std::string& s,float* v) {
 char* e; *v=strtof(s.c_str(),&e);return e==s.c_str()+s.size(); }}
''',
        'android-base/scopeguard.h': '''#pragma once
#include <utility>
namespace android::base {
template<class F> struct Guard {F f; ~Guard(){f();}};
template<class F> Guard<F> make_scope_guard(F f){return {std::move(f)};}
}
''',
        'partitions.hpp': '''#pragma once
#include <string>
struct TWPartition {std::string storage_path_; bool Mount(bool){return false;}};
struct TestPartitions {
 bool mounted=true, can_mount=true;
 bool IsMountedByPath(const std::string&){return mounted;}
 bool MountByPath(const std::string&, bool){mounted=can_mount;return mounted;}
 TWPartition* FindPartitionByPath(const std::string&){return nullptr;}
 TWPartition* GetDefaultStoragePartition(){return nullptr;}
};
inline TestPartitions PartitionManager;
''',
        'set_metadata.h': '''#pragma once
#include <sys/stat.h>
inline int tw_set_default_metadata(const char* p){return chmod(p,0664);}
''',
        'twcommon.h': '#pragma once\n#define LOGINFO(...) ((void)0)\n#define LOGERR(...) ((void)0)\n',
        'twrp_functions.hpp': '''#pragma once
#include <unistd.h>
#include <string>
namespace TWFunc {inline bool IsPathExists(const std::string& p){return access(p.c_str(),F_OK)==0;}}
''',
        'variables.h': '#pragma once\n#define TW_PERSIST_DIR "' + str(tmp / 'fixture') + '"\n'
                        '#define TW_SETTINGS_FILE ".twrp_settings"\n' +
                        '\n'.join(re.findall(r'^#define TW_TIME_ZONE[^\n]+', variables, re.M)) + '\n',
    }
    for name, content in stubs.items():
        (tmp / name).write_text(content)
    # Change only boundary include resolution, never the implementation body.
    for name in ['partitions.hpp', 'set_metadata.h', 'twcommon.h', 'twrp_functions.hpp', 'variables.h']:
        info = info.replace(f'#include "{name}"', f'#include <{name}>')
    (tmp / 'infomanager.cpp').write_text(info)
    harness = (ROOT / 'tests/settings_persistence_test.cpp').read_text()
    harness = harness.replace('// PRODUCTION_METHODS', methods)
    harness = harness.replace('// FILE_VERSION', re.search(r'^#define FILE_VERSION[^\n]+', data, re.M)[0])
    (tmp / 'test.cpp').write_text(harness)
    wrapped = ['fwrite', 'fflush', 'fclose', 'fsync', 'rename', 'mkstemp']
    subprocess.run(['g++', '-std=c++23', '-Wall', '-Wextra', '-Werror', '-Wno-ignored-attributes',
                    '-fsanitize=undefined', '-fno-sanitize-recover=all', '-g',
                    '-I' + str(tmp), '-I' + str(SRC), str(tmp / 'infomanager.cpp'),
                    str(tmp / 'test.cpp'), '-o', str(tmp / 'test'),
                    *['-Wl,--wrap=' + name for name in wrapped]], check=True)
    results = []
    for case in cases:
        result = subprocess.run([str(tmp / 'test'), case], capture_output=True, text=True, timeout=10)
        results.append(dict(case=case, returncode=result.returncode, status='PASS' if result.returncode == 0 else 'FAIL',
                            output=(result.stdout + result.stderr).strip()))
        print(results[-1]['status'], case, results[-1]['output'], flush=True)
    report = dict(status='PASS' if all(r['returncode'] == 0 for r in results) else 'FAIL',
                  scope=__doc__.strip(), cases=results,
                  sources={name: hashlib.sha256((SRC / name).read_bytes()).hexdigest()
                           for name in ['infomanager.cpp', 'infomanager.hpp', 'data.cpp', 'variables.h']},
                  test_sources={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in [Path(__file__), ROOT / 'tests/settings_persistence_test.cpp']})
    args.report.write_text(json.dumps(report, indent=2) + '\n')
raise SystemExit(0 if report['status'] == 'PASS' else 1)
