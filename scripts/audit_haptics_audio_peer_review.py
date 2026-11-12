#!/usr/bin/env python3
"""Audit the original audio socket notification evidence; no hardware claim."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    evidence = ROOT / 'logs/haptics-audio-peer-review.json'
    report = json.loads(evidence.read_text())
    assert report['status'] == 'PASS' and len(report['cases']) == 34
    for group in ['sources', 'tests', 'emulator_files']:
        assert report[group]
        for name, digest in report[group].items():
            assert sha(ROOT / name) == digest, name
    expected = {'startup', 'off', 'unknown-command', 'short-command', 'short-state',
                'read-eof', 'read-error', 'hangup', 'no-input', 'write-error',
                'feature-disabled', 'expired-stream', 'state-high-byte-only',
                'active-on', 'active-off', 'active-off-app-denied', 'active-unmatched'}
    for sample in ['os4-current', 'os4-stable']:
        cases = {c['case']: c for c in report['cases'] if c['sample'] == sample}
        assert cases.keys() == expected
        for label, case in cases.items():
            assert case['status'] == 'PASS'
            acks = [c for c in case['calls'] if c['call'] == 'write']
            assert len(acks) == int(label not in ['hangup', 'no-input'])
            if acks:
                assert acks[0]['data'] == '0100'
                assert acks[0]['result'] == (-1 if label == 'write-error' else 2)
            entries = case['entries']
            notices = [e for e in entries if 'ResourceManager28note' in e['function']]
            assert len(notices) == int(label not in ['unknown-command', 'read-eof', 'read-error', 'hangup', 'no-input'])
            if notices:
                assert notices[0]['args'][1] == int(label not in ['off', 'short-command', 'state-high-byte-only', 'active-off', 'active-off-app-denied'])
            updates = [e for e in entries if '13updateA2HMode' in e['function']]
            assert len(updates) == int(label in ['active-on', 'active-off', 'active-off-app-denied'])
            parameters = [c for c in case['calls'] if 'setA2HParameter' in c['call']]
            assert all(c['parameter'] == 'Haptics Source' for c in parameters)
            assert [c['value'] for c in parameters] == ([2] if label == 'active-off' else [0] if label == 'active-off-app-denied' else [])
            assert not any('mixer_' in c['call'] or 'pcm_' in c['call'] or c['call'] == 'ioctl' for c in case['calls'])
    index = json.loads((ROOT / 'simulation-report.json').read_text())
    entry, = [c for c in index['checks'] if c['name'] == 'stock-ARM64-OS4-haptics-audio-peer-review']
    assert entry['evidence_sha256'] == sha(evidence) and entry['count'] == 34
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    image = Path(index['image'])
    assert sha(image) == index['image_sha256']
    source = json.loads(image.with_name(image.stem + '-sources.json').read_text())
    assert source['image_sha256'] == index['image_sha256']
    for name, digest in source['files'].items():
        assert sha(Path(name)) == digest, name
    for name, target in source['symlinks'].items():
        assert str(Path(name).readlink()) == target, name
    result = dict(status='PASS', scope=__doc__, cases=34, production_changed=False,
                  field_vibration='unresolved', evidence_sha256=sha(evidence),
                  image_sha256=index['image_sha256'], production_source_files=len(source['files']),
                  documents={n: sha(ROOT / n) for n in ['ADAPTATION-GOALS.md', 'MAINTENANCE.md',
                             'simulation-report.md', 'simulation-report.json', 'docs/HAPTICS-ADAPTATION.md',
                             'docs/HAPTICS-AUDIO-SOCKET-PEER.md']},
                  audit_script_sha256=sha(Path(__file__)))
    (ROOT / 'logs/haptics-audio-peer-review-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS:34 original audio peer cases; current image/source binding; physical vibration unresolved')


if __name__ == '__main__': main()
