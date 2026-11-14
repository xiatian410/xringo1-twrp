#!/usr/bin/env python3
"""Battery and Android Secure deletion to original backend run terminal result.

Actual original manager/partition/RemoveDir methods, private chroot regular
files, unprivileged permission failures. Mounts, settings, console, executor
and other manager routes are fixtures; no phone, physical device, full GUI,
thread-start, fscrypt or concurrent pathname/physical I/O proof.
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
    parser.add_argument('--before', action='store_true')
    args = parser.parse_args()
    manager = ROOT/'logs/aux-wipe-before/partitionmanager.cpp' if args.before else SRC/'partitionmanager.cpp'
    selected = {
        manager: ['int TWPartitionManager::WipeBatteryStats()', 'int TWPartitionManager::WipeAndroidSecure()'],
        SRC/'partition.cpp': ['bool TWPartition::WipeAndSec()'],
        SRC/'twrp_functions.cpp': ['int TWFunc::RemoveDir('],
        SRC/'gui2/backend/twrp_wipe_backend.cpp': ['bool wipe_target_allowed(', 'int wipe(', 'void twrp_wipe_backend::report_item(', 'void twrp_wipe_backend::run('],
    }
    bodies = []
    for path, signatures in selected.items():
        for signature in signatures:
            body = method(path.read_text(), signature)
            if path.name == 'twrp_wipe_backend.cpp':
                body = 'namespace gui2_backend {\n'+body+'\n}'
            bodies.append(body)
    names = ['battery-'+v for v in ['success', 'missing', 'delete-denied', 'lookup-denied', 'directory', 'link', 'mount-denied']]
    names += ['secure-'+v for v in ['success', 'first-denied', 'first-denied-list', 'second-denied', 'all-denied', 'missing', 'none', 'mount-denied']]
    cases = []
    with tempfile.TemporaryDirectory(prefix='aux-wipe-') as temp:
        work = Path(temp)
        (work/'methods.inc').write_text('\n\n'.join(bodies))
        binary = work/'test'
        command = ['g++', '-std=c++23', '-O1', '-g', '-static', '-pthread', '-I'+str(work), '-I'+str(SRC/'gui2/backend'), str(ROOT/'tests/aux_wipe_test.cpp'), '-o', str(binary)]
        subprocess.run(command, check=True)
        for name in names:
            jail = work/name
            jail.mkdir(mode=0o755)
            (jail/'test').write_bytes(binary.read_bytes())
            (jail/'test').chmod(0o755)

            def isolate():
                os.chroot(jail)
                os.chdir('/')

            run = subprocess.run(['/test', name], preexec_fn=isolate, capture_output=True, text=True, timeout=10)
            cases.append(dict(case=name, status='PASS' if run.returncode == 0 else 'FAIL', returncode=run.returncode, output=run.stdout+run.stderr))
            print(name, cases[-1]['status'], flush=True)
    paths = [*selected, Path(__file__), ROOT/'tests/aux_wipe_test.cpp', ROOT/'tests/nested_partition_path_test.py', SRC/'gui2/backend/wipe_backend.h', SRC/'gui2/backend/mount_backend.h']
    report = dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL', scope=__doc__, before=args.before, cases=cases, compile_command=command, sources={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    (ROOT/'logs'/('aux-wipe-old.json' if args.before else 'aux-wipe-current.json')).write_text(json.dumps(report, indent=2)+'\n')
    return report['status'] != 'PASS'


if __name__ == '__main__':
    raise SystemExit(main())
