#!/usr/bin/env python3
"""Check independent FFmpeg evidence, pinned inputs and current delivery."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    path = ROOT / 'logs/video-ffmpeg.json'
    report = json.loads(path.read_text())
    assert report['status'] == 'PASS' and len(report['cases']) == 18
    producer_path = ROOT / report['producer_report']
    assert sha(producer_path) == report['producer_report_sha256']
    producer = json.loads(producer_path.read_text())
    for name, digest in {**producer['sources'], **report['sources'],
                         **report['tools']['linked_files']}.items():
        assert sha(Path(name)) == digest, name
    assert json.loads((ROOT / 'tools/ffmpeg-host/source.json').read_text()) == report['tools']
    for name, package in report['tools']['packages'].items():
        assert sha(ROOT / package['file']) == package['sha256']
        assert 'SHA256: ' + package['sha256'] in package['apt_metadata']
    shapes = {(96, 64, fps) for fps in [15, 24, 30, 45, 60]} | {(97, 65, 30)}
    assert {(c['mode'], c['width'], c['height'], c['fps']) for c in report['cases']} == {
        (mode, *shape) for mode in ['sequential', 'queue-drain', 'queue-resume'] for shape in shapes}
    for case in report['cases']:
        assert case['status'] == 'PASS' and sha(ROOT / case['artifact']) == case['sha256']
        assert case['duration_seconds'] == 1.5
        assert '(vp8 (native) -> rawvideo (native))' in case['decode_log']
        expected = ([i * 1000 // case['fps'] for i in range(12)] if case['mode'] == 'sequential'
                    else [0, 100, 200] + ([1000] if case['mode'] == 'queue-resume' else []))
        assert case['pts_ms'] == expected and case['decoded_frames'] == len(expected)
        assert len(case['seeks']) == 4
        assert [s['target_seconds'] for s in case['seeks']] == [0, 0.15, 0.5, 1.2]
        for seek in case['seeks']:
            result = next((t for t in expected if t >= seek['target_seconds'] * 1000), None)
            assert seek['expected_pts_ms'] == result
            if result is None: assert seek['output_bytes'] == 0
            else: assert seek['output_bytes'] > 0
    index = json.loads((ROOT / 'simulation-report.json').read_text())
    check, = [c for c in index['checks'] if c['name'] == 'video-ffmpeg-native-decode-and-seek']
    assert check['count'] == 18 and check['evidence_sha256'] == sha(path)
    assert index['status'] == 'in_progress' and sha(Path(index['image'])) == index['image_sha256']
    output = dict(status='PASS', scope=__doc__, files=18, input_seeks=72,
                  evidence_sha256=sha(path), image_sha256=index['image_sha256'],
                  production_change=False,
                  documents={n: sha(ROOT / n) for n in ['ADAPTATION-GOALS.md',
                      'MAINTENANCE.md', 'simulation-report.json', 'simulation-report.md',
                      'FEATURE-USAGE.md', 'docs/VIDEO-FRAMES-VALIDATION.md']},
                  audit_script_sha256=sha(Path(__file__)))
    (ROOT / 'logs/video-ffmpeg-delivery.json').write_text(json.dumps(output, indent=2) + '\n')
    print('PASS:18 independent native-decoded files/72 short input seeks/source/package/image hashes')


if __name__ == '__main__': main()
