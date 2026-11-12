#!/usr/bin/env python3
"""Audit original codec/PCM/FF evidence and current image; no hardware claim."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    evidence = ROOT / 'logs/haptics-pcm-ff-join-review.json'
    report = json.loads(evidence.read_text())
    assert report['status'] == 'PASS' and len(report['cases']) == 12
    for group in ['sources', 'tests', 'emulator_files']:
        assert report[group]
        for name, digest in report[group].items():
            p = Path(name) if Path(name).is_absolute() else ROOT / name
            assert sha(p) == digest, name
    labels = {'no-widgets', 'mono-front-end-shaped-fixture', 'two-channel-backend-fixture',
              'params-all-writes-error', 'rx-first-write-error', 'rx-last-write-error'}
    for sample in ['os4-current', 'os4-stable']:
        cases = {c['case']: c for c in report['cases'] if c['sample'] == sample}
        assert cases.keys() == labels
        for label, case in cases.items():
            assert case['status'] == 'PASS'
            assert all(v == (-5 if k == 'asp_rx' and label.startswith('rx-') else 0) for k, v in case['setup_results'].items())
            cache = case['codec_cache']
            assert cache == {'0x18': 3072000 if label == 'two-channel-backend-fixture' else 1536000,
                             '0x30': 0, '0x34': 0, '0x38': 2, '0x3c': 2, '0x40': 3,
                             '0x4c': 48000, '0x50': 24, '0x54': 32}
            entries = [e['function'] for e in case['PCM_entries']]
            for name in ['cs40l26_codec_driver_probe', 'cs40l26_codec_probe', 'cs40l26_asp_mode_put',
                         'cs40l26_asp_pcm_slot_put', 'cs40l26_set_tdm_slot', 'cs40l26_pcm_hw_params',
                         'cs40l26_component_set_sysclk']:
                assert entries.count(name) == 1
            params = [u for u in case['PCM_updates'] if u['phase'] == 'params']
            rx = [u for u in case['PCM_updates'] if u['phase'] == 'rx']
            if label == 'no-widgets':
                assert not params and not rx
            else:
                assert [(u['address'], u['mask'], u['value']) for u in params] == [
                    (0x4008, 0x10000, 0), (0x4840, 0x3f, 24), (0x4808, 0xff000744, 0x20000000), (0x4820, 0x3f3f, 0x302)]
                assert [u['result'] for u in params] == [-5 if label == 'params-all-writes-error' else 0] * 4
                assert len(rx) == (1 if label == 'rx-first-write-error' else 3)
                assert sum(u['result'] != 0 for u in rx) == int(label.startswith('rx-'))
            assert case['FF_mailbox'] == [dict(command=0x1800081, result=0)]
            assert [(w['address'], w['value'], w['result']) for w in case['FF_writes']] == [
                (0x280701c, 20, 0), (0x2807014, 125, 0), (0x2807018, 64, 0), (0x2802134, 80, 0), (0x28059f0, 0, 0)]
            assert case['final_state'] == dict(vibe_state=0 if label == 'no-widgets' else 2,
                                             count=0, asp_active=int(label != 'no-widgets'))
            assert case['waveform_complete_counter'] == 0xffffffff
    index = json.loads((ROOT / 'simulation-report.json').read_text())
    entry, = [c for c in index['checks'] if c['name'] == 'stock-ARM64-OS4-haptics-PCM-FF-joined']
    assert entry['count'] == 12 and entry['evidence_sha256'] == sha(evidence)
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    image = Path(index['image'])
    assert sha(image) == index['image_sha256']
    source = json.loads(image.with_name(image.stem + '-sources.json').read_text())
    assert source['image_sha256'] == index['image_sha256']
    for name, digest in source['files'].items():
        assert sha(Path(name)) == digest, name
    for name, target in source['symlinks'].items():
        assert str(Path(name).readlink()) == target, name
    result = dict(status='PASS', scope=__doc__, cases=12, production_changed=False,
                  field_vibration='unresolved', evidence_sha256=sha(evidence),
                  image_sha256=index['image_sha256'], production_source_files=len(source['files']),
                  documents={n: sha(ROOT / n) for n in ['ADAPTATION-GOALS.md', 'MAINTENANCE.md',
                             'simulation-report.md', 'simulation-report.json', 'docs/HAPTICS-ADAPTATION.md',
                             'docs/HAPTICS-PCM-FF-STATE.md']}, audit_script_sha256=sha(Path(__file__)))
    (ROOT / 'logs/haptics-pcm-ff-join-review-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS:12 original codec/PCM/FF joined cases; current image/source binding; physical vibration unresolved')


if __name__ == '__main__': main()
