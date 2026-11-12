#!/usr/bin/env python3
"""Verify original ARM64 DSP-config boundary cases and their bound inputs."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_map(mapping):
    for name, digest in mapping.items():
        assert sha(ROOT / name) == digest, name


def main():
    report = json.loads((ROOT / 'logs/haptics-config-emulation.json').read_text())
    cases = report['cases']
    assert report['status'] == 'PASS' and len(cases) == 36
    assert set(report['drivers']) == {'os4-current', 'os4-stable'}
    check_map(report['sources'])
    check_map(report['tests'])
    check_map(report['emulator_files'])
    labels = {
        'call-ram-write-exhausted', 'active-sequence-read-error',
        'power-sequence-read-error', 'first-sequence-write-error',
        'second-sequence-write-error', 'HALO-read-error',
        'HALO-invalid-state', 'IRQ-mask-read-error', 'GPIO-read-error',
    }
    for sample, driver in report['drivers'].items():
        assert sha(ROOT / driver['path']) == driver['sha256']
        for firmware in ['cs40l26.wmfw', 'cs40l26-calib.wmfw']:
            subset = {c['case']: c for c in cases
                      if c['sample'] == sample and c['firmware'] == firmware}
            assert set(subset) == labels
            for label, case in subset.items():
                assert case['status'] == 'PASS'
                assert case['result'] == (-22 if label == 'HALO-invalid-state' else
                                          -62 if label == 'call-ram-write-exhausted' else -5)
                if label == 'call-ram-write-exhausted':
                    assert case['fw_loaded'] == 0 and len(case['sleeps']) == 20
                    assert sum(w['address'] == 0x2800ff8 for w in case['writes']) == 20
                    assert not case['raw_reads'] and not case['bulk_writes'] and not case['debugfs']
                else:
                    assert case['fw_loaded'] == 1 and len(case['debugfs']) == 1
                    assert all(r['fixture'] == 'all-FF-immediate-terminator'
                               for r in case['raw_reads'])
            assert len(subset['first-sequence-write-error']['bulk_writes']) == 1
            assert len(subset['second-sequence-write-error']['bulk_writes']) == 2
            gpio = subset['GPIO-read-error']
            assert len(gpio['bulk_writes']) == 5
            assert 'cs40l26_gpio_config' in gpio['entries']
    print('PASS: 36 original ARM64 config cases, 4 driver/firmware combinations, bound inputs and failure boundaries')


if __name__ == '__main__':
    main()
