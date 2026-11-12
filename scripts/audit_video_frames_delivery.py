#!/usr/bin/env python3
"""Validate recorder congestion evidence, artifacts and current image identity."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    path = ROOT / 'logs/video-frames.json'
    report = json.loads(path.read_text())
    assert report['status'] == 'PASS' and len(report['cases']) == 18
    for name, digest in report['sources'].items():
        assert sha(Path(name)) == digest, name
    shapes = {(96, 64, fps) for fps in [15, 24, 30, 45, 60]} | {(97, 65, 30)}
    assert {(c['mode'], c['width'], c['height'], c['fps']) for c in report['cases']} == {
        (mode, *shape) for mode in ['sequential', 'queue-drain', 'queue-resume'] for shape in shapes}
    for c in report['cases']:
        assert c['status'] == 'PASS' and c['returncode'] == 0 and not c['stderr']
        count = {'sequential': 12, 'queue-drain': 3, 'queue-resume': 4}[c['mode']]
        assert f'decoded_frames={count} duration_ns=1500000000' in c['stdout']
        assert 'center_YUV_checked=1' in c['stdout']
        assert sha(ROOT / c['artifact']) == c['sha256']
    index = json.loads((ROOT / 'simulation-report.json').read_text())
    check, = [c for c in index['checks'] if c['name'] == 'video-frames-encode-decode']
    assert check['count'] == 18 and check['evidence_sha256'] == sha(path)
    assert index['status'] == 'in_progress'
    assert sha(Path(index['image'])) == index['image_sha256']
    result = dict(status='PASS', scope=__doc__, cases=18, evidence_sha256=sha(path),
                  image_sha256=index['image_sha256'],
                  production_scope='Tests bind current recorder source; close-error change delivered separately.',
                  documents={n: sha(ROOT / n) for n in ['ADAPTATION-GOALS.md',
                      'MAINTENANCE.md', 'simulation-report.md', 'simulation-report.json',
                      'docs/VIDEO-FRAMES-VALIDATION.md']}, audit_script_sha256=sha(Path(__file__)))
    (ROOT / 'logs/video-frames-delivery.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: 18 recorder cases/source hashes/artifacts/index; no target display or hardware claim')


if __name__ == '__main__': main()
