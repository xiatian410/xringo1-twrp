#!/usr/bin/env python3
"""Bind bounded original PCM/AAC initialization evidence to the current delivery.

This checks recorded software boundaries and source identity, not hardware.
"""
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    evidence = ROOT / 'logs/haptics-pcm-init-review.json'
    report = json.loads(evidence.read_text())
    assert report['status'] == 'PASS' and len(report['cases']) == 26
    for group in ['sources', 'tests', 'emulator_files']:
        assert report[group]
        for name, digest in report[group].items():
            assert sha(ROOT / name) == digest, name
    labels = {'normal', 'mixer-absent', 'f0-absent', 'f0-low-edge', 'f0-high-edge',
              'f0-too-low', 'f0-too-high', 'fallback-library', 'all-libraries-absent',
              'init-symbol-absent', 'aac-allocation-error', 'aac-semaphore-error', 'aac-thread-error'}
    for sample in ['os4-current', 'os4-stable']:
        cases = {c['case']: c for c in report['cases'] if c['sample'] == sample}
        assert cases.keys() == labels
        for label, case in cases.items():
            assert case['status'] == 'PASS'
            state = case['state']
            assert state['selector'] == 1 and state['sample_rate'] == 48000
            assert state['backend_vptr'] == 0x30670 and state['port'] == 'XR_TDM7_RX'
            assert state['pcm_config'] == [48000, 0, 24, 0, 4, 0]
            assert state['discovery']['fd'] == 9 and state['discovery']['cirrus'] == 1
            assert bool(state['mixer']) == (label != 'mixer-absent')
            assert state['libraries'] == ['/odm/lib64/libaachaptics.so', '/odm/lib64/vendor.awa.wavelib.so']
            ordinary = case['ordinary_on']
            assert [c['call'] for c in ordinary] == ['write', 'upload', 'write', 'AStatus_newOk']
            assert bytes.fromhex(ordinary[1]['custom']) == struct.pack('<HH', 0, 31)
            assert bytes.fromhex(ordinary[0]['data'])[16:] == struct.pack('<HHi', 21, 96, 100)
            assert bytes.fromhex(ordinary[2]['data'])[16:] == struct.pack('<HHi', 21, 7, 1)
            assert not any(c['call'] in ['write', 'ioctl', 'pcm_open', 'mixer_ctl_set_value']
                           for c in case['calls'] if c.get('phase') == 'pcm')
            plugin = case['plugin_boundaries']
            assert not any(c['call'] in ['write', 'ioctl', 'open', 'pcm_open', 'mixer_ctl_set_value'] for c in plugin)
            workers = [c for c in plugin if c['call'] == 'pthread_create']
            assert all(c['entry'] == 0x100f558 and c['executed'] is False for c in workers)
            if label == 'fallback-library':
                assert case['plugin_calls'] == [dict(plugin='awa', frequency=130)] and not plugin
                assert state['library_index'] == 1
            elif label in ['all-libraries-absent', 'init-symbol-absent']:
                assert not case['plugin_calls'] and not plugin and case['plugin_return'] is None
            else:
                expected = {'aac-allocation-error': -2, 'aac-semaphore-error': -1, 'aac-thread-error': 11}.get(label, 0)
                assert case['plugin_return'] == expected
                assert case['plugin_calls'] == [dict(plugin='aac', values=[512, 48000, 1,
                    {'f0-low-edge': 120, 'f0-high-edge': 140}.get(label, 130)])]
                if label not in ['aac-allocation-error', 'aac-semaphore-error']:
                    assert len(workers) == 1
                    assert sum(c['call'] == 'sin' for c in plugin) > 100
                else:
                    assert not workers
            if label == 'aac-thread-error':
                assert workers[0]['result'] == 11
                assert [c['thread'] for c in plugin if c['call'] == 'pthread_detach'] == [0]
        assert cases['f0-absent']['plugin_calls'] == cases['normal']['plugin_calls']
        assert cases['f0-too-low']['plugin_calls'] == cases['normal']['plugin_calls']
        assert cases['f0-too-high']['plugin_calls'] == cases['normal']['plugin_calls']
    index = json.loads((ROOT / 'simulation-report.json').read_text())
    entry, = [c for c in index['checks'] if c['name'] == 'stock-ARM64-OS4-haptics-pcm-init-review']
    assert entry['evidence_sha256'] == sha(evidence) and entry['count'] == 26
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    image = Path(index['image'])
    assert sha(image) == index['image_sha256']
    source = json.loads(image.with_name(image.stem + '-sources.json').read_text())
    assert source['image_sha256'] == index['image_sha256']
    for name, digest in source['files'].items():
        assert sha(Path(name)) == digest, name
    for name, target in source['symlinks'].items():
        assert str(Path(name).readlink()) == target, name
    result = dict(status='PASS', scope=__doc__, cases=26, production_changed=False,
                  field_vibration='unresolved', evidence_sha256=sha(evidence),
                  image_sha256=index['image_sha256'], production_source_files=len(source['files']),
                  documents={n: sha(ROOT / n) for n in ['ADAPTATION-GOALS.md', 'MAINTENANCE.md',
                             'simulation-report.md', 'simulation-report.json', 'docs/HAPTICS-ADAPTATION.md',
                             'docs/HAPTICS-PCM-INITIALIZATION.md']}, audit_script_sha256=sha(Path(__file__)))
    (ROOT / 'logs/haptics-pcm-init-review-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS:26 bounded original PCM/AAC init + ordinary-on cases; current image/source binding; motor unresolved')


if __name__ == '__main__':
    main()
