#!/usr/bin/env python3
"""Execute production manifest begin/commit/restore validation on private files.

Fork-exit cases simulate process interruption, not physical power loss. No codec,
Android filesystem, mount service or device is used.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = Path('/root/AAA/twrp/bootable/recovery')
CASES = ['valid', 'legacy', 'crash-marker', 'crash-partial', 'crash-complete',
         'missing-required', 'missing-tail', 'short-tail', 'extra-file',
         'symlink-payload', 'fifo-payload', 'unknown-version', 'duplicate',
         'traversal', 'truncated-record', 'manifest-symlink', 'legacy-after-delete']

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    with tempfile.TemporaryDirectory(prefix='dijun-manifest-') as temp:
        temp = Path(temp)
        command = ['g++', '-std=c++23', '-O1', '-g', '-Wall', '-Wextra',
                   '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-no-pie',
                   '-I' + str(SRC), '-I/root/AAA/twrp/system/libbase/include',
                   str(ROOT/'tests/backup_manifest_test.cpp'), '-o', str(temp/'test')]
        subprocess.run(command, check=True)
        results = []
        for case in CASES:
            work = temp / case
            work.mkdir()
            run = subprocess.run([str(temp/'test'), case], cwd=work,
                                 capture_output=True, text=True, timeout=5)
            results.append(dict(case=case, status='PASS' if run.returncode == 0 else 'FAIL',
                                returncode=run.returncode, output=run.stdout + run.stderr))
            print(results[-1]['status'], case, flush=True)
    source = SRC/'backup_manifest.hpp'
    report = dict(status='PASS' if all(c['status'] == 'PASS' for c in results) else 'FAIL',
                  scope=__doc__, cases=results, sources={str(source): digest(source)},
                  tests={str(p): digest(p) for p in [Path(__file__).resolve(), ROOT/'tests/backup_manifest_test.cpp']},
                  compile_command=command)
    (ROOT/'logs/backup-manifest-core.json').write_text(json.dumps(report, indent=2) + '\n')
    return report['status'] != 'PASS'

if __name__ == '__main__':
    raise SystemExit(main())
