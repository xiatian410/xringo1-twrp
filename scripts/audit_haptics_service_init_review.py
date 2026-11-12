#!/usr/bin/env python3
"""Audit bounded OS4 discovery and separate backend initialization evidence."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    evidence = ROOT / 'logs/haptics-service-init-review.json'
    report = json.loads(evidence.read_text())
    assert report['status'] == 'PASS' and len(report['cases']) == 30
    for group in ['sources', 'tests', 'emulator_files']:
        assert report[group]
        for name, digest in report[group].items():
            assert sha(ROOT / name) == digest, name
    labels = {'normal', 'no-directory', 'open-denied', 'name-error', 'cap-error',
              'no-supported-effect', 'cirrus-disabled', 'audio-disabled',
              'mixer-absent', 'skip-non-FF', 'open-EINTR', 'name-EINTR',
              'custom-wave-present', 'custom-wave-absent', 'custom-wave-key-error'}
    for sample in ['os4-current', 'os4-stable']:
        cases = {c['case']: c for c in report['cases'] if c['sample'] == sample}
        assert cases.keys() == labels
        for label, case in cases.items():
            assert case['status'] == 'PASS'
            calls = case['calls']
            assert not any(c['call'] in ['write', 'mixer_ctl_set_value'] for c in calls)
            if case['group'] == 'discovery-prefix':
                assert case['state']['amplitude'] == 32767 and case['state']['effect_id'] == -1
                restores = [i for i, c in enumerate(calls) if c['call'] == 'calibration-restore-boundary']
                assert len(restores) == int(label not in ['no-directory', 'open-denied', 'name-error'])
                for i in restores:
                    assert calls[i + 1]['call'] == 'ioctl' and calls[i + 1]['request'] == 0x80104535
                assert all(c['request'] in [0x80204506, 0x80104535] for c in calls if c['call'] == 'ioctl')
            else:
                assert case['group'] == 'separate-FF-constructor'
                assert not any(c['call'] == 'ioctl' for c in calls)
                opens = [c for c in calls if c['call'] == '__open_2']
                assert len(opens) == 1 and opens[0]['path'].endswith('/custom_wave')
                assert case['state'] == [9, -1 if label == 'custom-wave-absent' else 9,
                                         31 if label == 'custom-wave-present' else -1]
        assert cases['cirrus-disabled']['state']['fd'] == 9
        assert cases['cirrus-disabled']['state']['audio_haptic'] == 1
        assert cases['audio-disabled']['state']['cirrus'] == 1
        assert cases['mixer-absent']['state']['fd'] == 9
        assert cases['mixer-absent']['state']['cirrus'] == 1
        assert cases['mixer-absent']['state']['mixer'] == 0
        for label, call, request in [('open-EINTR', '__open_2', None), ('name-EINTR', 'ioctl', 0x80204506)]:
            selected = [c for c in cases[label]['calls'] if c['call'] == call and (request is None or c['request'] == request)]
            assert [c['result'] for c in selected] == [-1, 9 if request is None else 14]
        skip = cases['skip-non-FF']['calls']
        assert [c['fd_or_dir'] for c in skip if c['call'] == 'close'] == [8]
    index = json.loads((ROOT / 'simulation-report.json').read_text())
    entry, = [c for c in index['checks'] if c['name'] == 'stock-ARM64-OS4-haptics-service-init-review']
    assert entry['evidence_sha256'] == sha(evidence) and entry['count'] == 30
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    image = Path(index['image'])
    assert sha(image) == index['image_sha256']
    source = json.loads(image.with_name(image.stem + '-sources.json').read_text())
    assert source['image_sha256'] == index['image_sha256']
    for name, digest in source['files'].items():
        assert sha(Path(name)) == digest, name
    for name, target in source['symlinks'].items():
        assert str(Path(name).readlink()) == target, name
    result = dict(status='PASS', scope=__doc__, cases=30, production_changed=False,
                  field_vibration='unresolved', evidence_sha256=sha(evidence),
                  image_sha256=index['image_sha256'], production_source_files=len(source['files']),
                  documents={n: sha(ROOT / n) for n in ['ADAPTATION-GOALS.md', 'MAINTENANCE.md',
                             'simulation-report.md', 'simulation-report.json', 'docs/HAPTICS-ADAPTATION.md']},
                  audit_script_sha256=sha(Path(__file__)))
    (ROOT / 'logs/haptics-service-init-review-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS:30 bounded original discovery/backend cases; current image/source binding; motor unresolved')


if __name__ == '__main__':
    main()
