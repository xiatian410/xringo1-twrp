#!/usr/bin/env python3
"""Run whole production exclusion walks on private host files under ASan/UBSan.

Only logging/include boundaries and TWFunc path helpers are supplied by the host.
No manager, mount, fscrypt, allocated-block estimate or device operation is tested.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from nested_partition_path_test import ROOT, SRC, method


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, default=SRC)
    ap.add_argument('--report', type=Path, default=ROOT / 'logs/exclusion-size.json')
    args = ap.parse_args()
    cases = []
    with tempfile.TemporaryDirectory(prefix='exclusion-size-') as tmp:
        work = Path(tmp)
        for name in ['exclude.cpp', 'exclude.hpp']:
            shutil.copyfile(args.source / name, work / name)
        for name, text in {
            'libtar/libtar.h': '',
            'twcommon.h': '#define LOGINFO(...) ((void)0)\n',
            'gui2/console/stdio_adapter.h': 'namespace gui2_console { template<class... T> void log_error(T...) {} }\n',
            'twrp_functions.hpp': '''#include <algorithm>
#include <cstring>
#include <filesystem>
#include <string>
class TWFunc { public:
 static std::string RemoveTrailingSlashes(const std::string&, bool leave_last=false);
 static bool IsPathExists(const std::string& p) { return std::filesystem::exists(p); }
};
''',
        }.items():
            path = work / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        helper = method((SRC / 'twrp_functions.cpp').read_text(), 'std::string TWFunc::RemoveTrailingSlashes(')
        (work / 'main.cpp').write_text('''#include "twrp_functions.hpp"
#include "exclude.hpp"
#include <cstdio>
#include <cstdlib>
namespace fs = std::filesystem;
''' + helper + '''
int main(int argc, char** argv) {
 TWExclude e; std::atomic<bool> cancel{false};
 for (int i=4;i<argc;i++) {
  std::string a=argv[i];
  if(a=="cancel") cancel=true;
  else if(a.starts_with("a:")) e.add_absolute_dir(a.substr(2));
  else if(a.starts_with("r:")) e.add_relative_dir(a.substr(2));
  else return 2;
 }
 auto scanned=e.Get_Folder_Size(argv[1],true,&cancel);
 auto excluded=e.Get_Exclusions_Folder_Size(&cancel);
 printf("scanned=%llu excluded=%llu\\n",(unsigned long long)scanned,(unsigned long long)excluded);
 return scanned==strtoull(argv[2],nullptr,10) && excluded==strtoull(argv[3],nullptr,10) ? 0:1;
}
''')
        command = ['g++', '-std=c++23', '-O1', '-g', '-fno-pie', '-no-pie',
                   '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                   '-I' + str(work), str(work / 'exclude.cpp'), str(work / 'main.cpp'),
                   '-o', str(work / 'test')]
        subprocess.run(command, check=True)
        for name in ['ordinary', 'absolute-file', 'absolute-directory', 'file-link',
                     'directory-link', 'dangling-link', 'relative-file',
                     'relative-directory', 'trailing-slashes', 'missing', 'cancelled']:
            root = work / name
            root.mkdir()
            (root / 'keep').write_bytes(b'keep123')
            (root / 'adb/ksu').mkdir(parents=True)
            (root / 'adb/ksu/modules.img').write_bytes(b'M' * 4097)
            (root / 'sub').mkdir()
            (root / 'sub/keep').write_bytes(b'S' * 13)
            (root / 'file-link').symlink_to('keep')
            (root / 'directory-link').symlink_to('sub', target_is_directory=True)
            (root / 'dangling-link').symlink_to('absent-target')
            os.mkfifo(root / 'fifo')
            # Independent logical-byte inventory: lstat link bytes, never target bytes.
            inventory = {str(p): p.lstat().st_size for p in root.rglob('*')
                         if p.is_symlink() or p.is_file()}
            total = sum(inventory.values())
            excluded = 0
            scanned = total
            options = []
            target = {
                'absolute-file': 'adb/ksu/modules.img', 'absolute-directory': 'adb',
                'file-link': 'file-link', 'directory-link': 'directory-link',
                'dangling-link': 'dangling-link', 'trailing-slashes': 'adb/ksu/modules.img',
            }.get(name)
            if target:
                path = str(root / target)
                excluded = sum(size for p, size in inventory.items() if p == path or p.startswith(path + '/'))
                scanned -= excluded
                options = ['a:' + path + ('///' if name == 'trailing-slashes' else '')]
            if name == 'relative-file':
                options = ['r:keep']
                scanned -= 20
            if name == 'relative-directory':
                options = ['r:sub']
                scanned -= 13
            if name == 'missing':
                options = ['a:' + str(root / 'not-present')]
            if name == 'cancelled':
                options = ['a:' + str(root / 'adb'), 'cancel']
                scanned = 0
            before = {str(p): sha(p) for p in root.rglob('*') if not p.is_symlink() and p.is_file()}
            run = subprocess.run([str(work / 'test'), str(root), str(scanned), str(excluded), *options],
                                 capture_output=True, text=True, timeout=10)
            after = {str(p): sha(p) for p in root.rglob('*') if not p.is_symlink() and p.is_file()}
            assert before == after
            row = dict(case=name, status='PASS' if run.returncode == 0 else 'FAIL',
                       returncode=run.returncode, expected_scanned=scanned,
                       expected_excluded=excluded, output=run.stdout + run.stderr)
            cases.append(row)
            print(name, row['status'], row['output'].strip(), flush=True)
    paths = [args.source / 'exclude.cpp', args.source / 'exclude.hpp',
             SRC / 'twrp_functions.cpp', Path(__file__), ROOT / 'tests/nested_partition_path_test.py']
    result = dict(status='PASS' if all(c['status'] == 'PASS' for c in cases) else 'FAIL',
                  scope=__doc__, cases=cases, sources={str(p): sha(p) for p in paths},
                  compile_command=command)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    return result['status'] != 'PASS'


if __name__ == '__main__':
    raise SystemExit(main())
