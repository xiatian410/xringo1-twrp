#!/usr/bin/env python3
"""Audit recording close-error delivery; not acceptance of the whole goal."""
import hashlib
import json
from pathlib import Path

from firmware_facts import boot_parts, ramdisk_entries

ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / 'imgs/built/recovery-dijun-unified-recording-close.img'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def load(name): return json.loads((ROOT / name).read_text())


def main():
    expected = '2773dec6298035e66dcb0b24deb78636207a6bbf24fab6f9490a5ad3151d83c7'
    assert sha(IMAGE) == expected
    provenance = json.loads(IMAGE.with_name(IMAGE.stem + '-sources.json').read_text())
    assert provenance['image_sha256'] == expected and len(provenance['files']) == 714
    assert provenance['jobs'] == 30
    assert 'installclean' in provenance['build_command'] and '-j$(nproc)' in provenance['build_command']
    for name, digest in provenance['files'].items(): assert sha(Path(name)) == digest, name
    for name, target in provenance['symlinks'].items():
        assert Path(name).is_symlink() and str(Path(name).readlink()) == target, name
    assert sha(ROOT / provenance['build_log']) == provenance['build_log_sha256']
    assert 'build completed successfully' in (ROOT / provenance['build_log']).read_text()
    failures = load('logs/video-failure.json')
    assert failures['status'] == 'PASS' and len(failures['cases']) == 6
    for name, digest in failures['sources'].items(): assert sha(Path(name)) == digest, name
    assert {c['case'] for c in failures['cases']} == {'open', 'write', 'flush', 'close', 'codec', 'codec-close'}
    for c in failures['cases']:
        assert c['status'] == 'PASS' and c['returncode'] == 0 and not c['stderr']
        assert 'failure_propagated=1' in c['stdout'] and 'restart=PASS' in c['stdout']
    before = load('logs/video-failure-before.json')
    assert [c['case'] for c in before['cases'] if c['status'] == 'FAIL'] == ['close']
    for name, digest in before['sources'].items(): assert sha(Path(name)) == digest, name
    frames = load('logs/video-frames-delivery.json')
    assert frames['status'] == 'PASS' and frames['cases'] == 18 and frames['image_sha256'] == expected
    assert frames['evidence_sha256'] == sha(ROOT / 'logs/video-frames.json')
    runtime = load('logs/recording-close-profile-runtime.json')
    assert runtime['status'] == 'PASS' and runtime['tests_run'] == 9 and len(runtime['cases']) == 102
    assert runtime['image_sha256'] == expected
    for name, digest in {**runtime['sources'], **runtime['test_sources']}.items():
        p = Path(name) if name.startswith('/') else ROOT / name
        assert sha(p) == digest, name
    metadata = json.loads(IMAGE.with_suffix('.json').read_text())
    assert metadata['sha256'] == expected and len(metadata['profiles']) == 6
    _, parts = boot_parts(IMAGE.read_bytes())
    entries = {e[0]: e[-1] for e in ramdisk_entries(parts['ramdisk'])}
    for name, digest in metadata['binary_hashes'].items():
        assert hashlib.sha256(entries[name]).hexdigest() == digest, name
    assert b'Unable to close WebM recording' in entries['system/lib64/libgui2.so']
    assert b'screenrecord_save_err' in entries['system/lib64/libgui2.so']
    index = load('simulation-report.json')
    assert index['status'] == 'in_progress' and index['image_sha256'] == expected
    for name in ['logs/video-failure.json', 'logs/recording-close-profile-runtime.json']:
        check, = [c for c in index['checks'] if c['evidence'] == name]
        assert check['evidence_sha256'] == sha(ROOT / name)
    evidence = ['logs/video-failure.json', 'logs/video-failure-before.json', 'logs/video-frames.json',
                'logs/video-frames-delivery.json', 'logs/recording-close-profile-runtime.json',
                'logs/verify-recording-close.log', 'logs/recording-close-source-recheck.log']
    docs = ['ADAPTATION-GOALS.md', 'simulation-report.json', 'simulation-report.md',
            'compatibility-matrix.md', 'FEATURE-USAGE.md', 'MAINTENANCE.md',
            'docs/VIDEO-FRAMES-VALIDATION.md']
    result = dict(status='PASS', scope=__doc__, image_sha256=expected, sources=714,
                  failure_cases=6, frames_cases=18, runtime_groups=9, runtime_phase_calls=102,
                  evidence={n: sha(ROOT / n) for n in evidence},
                  documentation={n: sha(ROOT / n) for n in docs}, audit_script_sha256=sha(Path(__file__)))
    (ROOT / 'logs/recording-close-delivery.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: recording close delivery/source/image/fault/frame/runtime checks; full goal incomplete')


if __name__ == '__main__': main()
