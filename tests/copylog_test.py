#!/usr/bin/env python3
"""Production copylog and file writers in private chroot, no devices.

Mount/selection, klogctl, logcat capture, metadata and operation presentation
are explicit fixtures; actual CopyFile/WriteToFile, worker thread and terminal
state run. No real kernel buffer, Android log service, GUI or power-loss proof.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from nested_partition_path_test import ROOT, SRC, method


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SRC)
    parser.add_argument('--report', type=Path, default=ROOT/'logs/copylog.json')
    args = parser.parse_args()
    tools = args.source/'gui2/backend/twrp_tools_backend.cpp'
    if not tools.exists():
        tools = args.source/'twrp_tools_backend.cpp'
    functions = args.source/'twrp_functions.cpp'
    header = args.source/'twrp_functions.hpp'
    current = 'static bool CopyKernelLog' in header.read_text()
    signatures = ['int TWFunc::CopyFile(', 'bool TWFunc::WriteToFile(const std::string& fn, const std::string& line)',
                  ('bool' if current else 'void')+' TWFunc::CopyKernelLog(',
                  ('bool' if current else 'void')+' TWFunc::CopyLogcat(']
    ft = functions.read_text()
    ts = tools.read_text()
    worker = ['int copylog()', 'twrp_tools_backend::~twrp_tools_backend()',
              'void twrp_tools_backend::join_finished_thread()', 'bool twrp_tools_backend::start(',
              'void twrp_tools_backend::run(', 'tool_state twrp_tools_backend::status()',
              'void twrp_tools_backend::acknowledge()']
    cases = []
    with tempfile.TemporaryDirectory(prefix='copylog-') as temp:
        work = Path(temp)
        (work/'functions.inc').write_text('\n\n'.join(method(ft, s) for s in signatures))
        (work/'worker.inc').write_text('\n\n'.join(method(ts, s) for s in worker))
        binary = work/'test'
        cmd = ['g++', '-std=c++20', '-O1', '-g', '-static', '-pthread',
               '-DLOG_CAPTURE_RETURNS_BOOL='+str(int(current)), '-I'+str(work),
               '-I'+str(SRC/'gui2'), '-I'+str(SRC),
               str(ROOT/'tests/copylog_test.cpp'), str(SRC/'twrp_operation_executor.cpp'), '-o', str(binary)]
        subprocess.run(cmd, check=True)
        for name in ['all-success', 'recovery-only', 'mount-fail', 'empty-storage',
                     'recovery-copy-fail', 'recovery-source-missing', 'kernel-size-fail',
                     'kernel-read-fail', 'kernel-write-fail', 'logcat-capture-fail',
                     'logcat-write-fail', 'both-captures-fail', 'reused-worker']:
            jail = work/name
            jail.mkdir()
            (jail/'test').write_bytes(binary.read_bytes())
            (jail/'test').chmod(0o755)
            def isolate():
                os.chroot(jail)
                os.chdir('/')
            r = subprocess.run(['/test', name], preexec_fn=isolate, capture_output=True, text=True, timeout=10)
            cases.append(dict(name=name, status='PASS' if r.returncode == 0 else 'FAIL',
                              returncode=r.returncode, stdout=r.stdout, stderr=r.stderr))
            print(name, cases[-1]['status'], flush=True)
    sources = [tools, functions, header, Path(__file__), ROOT/'tests/copylog_test.cpp',
               ROOT/'tests/nested_partition_path_test.py', SRC/'twrp_operation_executor.cpp',
               SRC/'twrp_operation_executor.h', SRC/'gui2/backend/twrp_tools_backend.h',
               SRC/'gui2/backend/tools_backend.h']
    report = dict(status='PASS' if all(c['status'] == 'PASS' for c in cases) else 'FAIL',
                  scope=__doc__, cases=cases, compile_command=cmd,
                  sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    return report['status'] != 'PASS'


if __name__ == '__main__':
    raise SystemExit(main())
