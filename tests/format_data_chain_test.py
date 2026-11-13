#!/usr/bin/env python3
"""Execute production FormatData/WipeEncryption/metadata routing/backend run.

Mounts, formatter, device mapper, pending-merge policy, device hooks and UI are
explicit fixtures. No mkfs, device, keys, real mounts, GUI/start/thread or rollback.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from nested_partition_path_test import ROOT, SRC, method


def main():
    selected = {
        SRC / 'partition.cpp': ['bool TWPartition::WipeEncryption()'],
        SRC / 'partitionmanager.cpp': [
            'bool TWPartitionManager::MatchesPath(',
            'TWPartition* TWPartitionManager::FindPartitionByPath(',
            'int TWPartitionManager::WipeByPath(const std::string& Path) const',
            'int TWPartitionManager::FormatData()'],
        SRC / 'gui2/backend/twrp_wipe_backend.cpp': [
            'bool wipe_target_allowed(', 'int wipe(',
            'void twrp_wipe_backend::report_item(', 'void twrp_wipe_backend::run('],
    }
    bodies = []
    for path, signatures in selected.items():
        for signature in signatures:
            body = method(path.read_text(), signature)
            if path.name == 'twrp_wipe_backend.cpp':
                body = 'namespace gui2_backend {\n' + body + '\n}'
            bodies.append(body)
    names = ['fbe-success', 'legacy-success', 'missing-data', 'pre-denied',
             'not-present', 'unmount-denied', 'force-unmount-success', 'merge-denied',
             'mapper-success', 'mapper-denied', 'format-failed', 'metadata-failed',
             'post-failed', 'no-key-directory']
    cases = []
    with tempfile.TemporaryDirectory(prefix='format-data-chain-') as temp:
        work = Path(temp)
        (work / 'methods.inc').write_text('\n\n'.join(bodies))
        binary = work / 'test'
        cmd = ['g++', '-std=c++23', '-O1', '-g', '-pthread', '-fsanitize=address,undefined',
               '-DTW_INCLUDE_CRYPTO', '-DTW_USE_DMCTL', '-DTW_EXCLUDE_APEX',
               '-I' + str(work), '-I' + str(SRC / 'gui2/backend'),
               str(ROOT / 'tests/format_data_chain_test.cpp'), '-o', str(binary)]
        subprocess.run(cmd, check=True)
        for name in names:
            run = subprocess.run([str(binary), name], capture_output=True, text=True, timeout=10)
            cases.append(dict(name=name, status='PASS' if run.returncode == 0 else 'FAIL',
                              returncode=run.returncode, stdout=run.stdout, stderr=run.stderr))
            print(name, cases[-1]['status'], flush=True)
    paths = [*selected, Path(__file__), ROOT / 'tests/format_data_chain_test.cpp',
             ROOT / 'tests/nested_partition_path_test.py', SRC / 'gui2/backend/wipe_backend.h',
             SRC / 'gui2/backend/mount_backend.h', ROOT / 'dtsrc/O1_asic_dual/BoardConfig.mk']
    report = dict(status='PASS' if all(c['status'] == 'PASS' for c in cases) else 'FAIL',
                  scope=__doc__, cases=cases, compile_command=cmd,
                  sources={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                  production_changes=False, new_image=False)
    (ROOT / 'logs/format-data-chain.json').write_text(json.dumps(report, indent=2) + '\n')
    return report['status'] != 'PASS'


if __name__ == '__main__':
    raise SystemExit(main())
