#!/usr/bin/env python3
"""Validate stock haptics lifecycle evidence independently of a built image."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    report = json.loads((ROOT / 'logs/haptics-lifecycle-emulation.json').read_text())
    assert report['status'] == 'PASS'
    samples = {'os2-final', 'os2-initial', 'os3-final', 'os3-initial',
               'os4-current', 'os4-stable'}
    assert set(report['drivers']) == samples
    assert len(report['cases']) == 90
    for group in (report['sources'], report['tests'], report['emulator_files']):
        for relative, expected in group.items():
            path = Path(relative)
            if not path.is_absolute():
                path = ROOT / path
            assert sha(path) == expected, str(path)
    for sample, record in report['drivers'].items():
        assert sha(ROOT / record['path']) == record['sha256'], sample
        cases = [case for case in report['cases'] if case['sample'] == sample]
        assert len(cases) == (19 if sample.startswith('os4-') else 13), sample
        contract_cases = [case for case in cases
                          if case['case'] == 'input-register-capabilities-callbacks']
        assert len(contract_cases) == 1
        contract_case = contract_cases[0]
        assert contract_case['status'] == 'PASS'
        contract = contract_case['contract']
        assert contract['name'] == 'cs40l26_input'
        assert contract['capabilities'] == [[21, 81], [21, 93], [21, 90], [21, 96]]
        assert contract['ff_max_effects'] == 96
        assert contract['rumble_flag_enabled'] is False
        callbacks = {'cs40l26_upload_effect', 'cs40l26_erase_effect',
                     'cs40l26_playback_effect', 'cs40l26_set_gain'}
        assert set(contract['callbacks']) == callbacks
        assert all(int(address, 16) > 0 for address in contract['callbacks'].values())
    print('PASS: 90 stock ARM64 cases, six exact module inputs and six FF registration contracts.')
    print('LIMIT: input-core ioctl behavior, node permissions, physical IRQ/DSP and motor output are untested.')


if __name__ == '__main__':
    main()
