#!/usr/bin/env python3
"""Run original background poll/CLI listener against private real FIFOs.

DataManager, partition work, console mirror and CLI execution are explicit
fixtures. Original listener/thread/callback uses host read/open/stdio/select;
no Android GUI, device, real CLI command, mounts or physical block access.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from nested_partition_path_test import ROOT, SRC


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SRC/'gui2/backend/twrp_background_backend.cpp')
    parser.add_argument('--report', type=Path, default=ROOT/'logs/cli-fifo.json')
    args = parser.parse_args()
    harness = ROOT/'tests/cli_fifo_test.cpp'
    with tempfile.TemporaryDirectory(prefix='dijun-cli-fifo-') as tmp:
        work = Path(tmp)
        # Keep the actual listener source complete, substitute only external services.
        text = args.source.read_text()
        for include in ['twrp_background_backend.h', 'data.hpp', 'openrecoveryscript.hpp', 'orscmd/orscmd.h', 'partitions.hpp', 'twcommon.h', 'twrp_operation.h']:
            text = text.replace('#include "'+include+'"', '')
        (work/'backend.inc').write_text(text)
        command = ['g++', '-std=c++20', '-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-I'+str(work), '-I'+str(SRC/'gui2'), '-I'+str(SRC), str(harness), str(SRC/'twrp_operation_executor.cpp'), '-pthread', '-o', str(work/'test')]
        subprocess.run(command, check=True)
        cases = []
        for name in ['abandoned-reader', 'late-reader', 'normal', 'busy', 'unsupported', 'short-command', 'max-command', 'reader-disappears', 'expiry-recovery', 'consecutive', 'saturated', 'pending-restart', 'shutdown-reserved', 'shutdown-pending', 'shutdown-active', 'shutdown-rollback']:
            folder = work/name
            folder.mkdir()
            try:
                run = subprocess.run([str(work/'test'), name, str(folder)], capture_output=True, text=True, timeout=8)
                result = dict(name=name, status='PASS' if run.returncode==0 else 'FAIL', returncode=run.returncode, output=run.stdout+run.stderr)
            except subprocess.TimeoutExpired as error:
                result = dict(name=name, status='FAIL', reason='listener blocked for eight seconds', output=str(error.stdout))
            cases.append(result)
            print(name, result['status'], flush=True)
    sources = [args.source, harness, Path(__file__), ROOT/'tests/nested_partition_path_test.py', SRC/'gui2/backend/twrp_background_backend.h', SRC/'gui2/backend/background_backend.h', SRC/'twrp_operation_executor.h', SRC/'twrp_operation_executor.cpp']
    report = dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL', scope=__doc__, cases=cases, compile_command=command, sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    return report['status']!='PASS'

if __name__=='__main__':
    raise SystemExit(main())
