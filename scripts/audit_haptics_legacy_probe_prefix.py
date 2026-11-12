#!/usr/bin/env python3
"""Bind OS2/OS3 original probe-prefix execution to stock DT and module bytes."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    report_path = ROOT / 'logs/haptics-legacy-probe-prefix.json'
    report = json.loads(report_path.read_text())
    assert report['status'] == 'PASS' and len(report['profiles']) == 4
    assert report['execution_boundary'] == 'original legacy PLL and probe through the first firmware request; additional original failure paths'
    assert report['hardware_result'] == 'unverified'
    assert len(report['tests']) == 2 and len(report['sources']) == 5
    expected_samples = {'os2-initial', 'os2-final', 'os3-initial', 'os3-final'}
    assert {profile['sample'] for profile in report['profiles']} == expected_samples
    for profile in report['profiles']:
        assert sha(ROOT / profile['module']) == profile['module_sha256']
        assert len(profile['cases']) == 4
        cases = {case['case']: case for case in profile['cases']}
        assert set(cases) == {'pinctrl-select-error', 'pll-error-after-init',
                              'id-read-error-after-pll',
                              'firmware-request-missing-after-stock-PLL-and-ID'}
        for label, case in cases.items():
            assert case['remove_body'] == 'original instructions; kernel teardown services are fixtures'
            assert case['result'] == (-2 if label ==
                'firmware-request-missing-after-stock-PLL-and-ID' else -5)
            assert case.get('no_input_registration', False)
            assert 'cs40l26_input_init' not in case['calls']
            if label != 'firmware-request-missing-after-stock-PLL-and-ID':
                assert case['no_dsp_upload']
            else:
                assert case['no_dsp_execution']
                assert 'cs40l26.wmfw' in case['firmware_requests']
        assert 'cs40l26_set_pll_loop' not in cases['pinctrl-select-error']['calls']
        assert 'regmap_read' not in cases['pinctrl-select-error']['calls']
        assert 'cs40l26_set_pll_loop' in cases['pll-error-after-init']['calls']
        assert cases['pll-error-after-init']['calls'][-1] == 'debugfs_remove'
        read_case = cases['id-read-error-after-pll']
        assert read_case['calls'][-1] == 'debugfs_remove'
        assert read_case['boundaries'][-1]['name'] == 'regmap_read' or any(
            boundary['name'] == 'regmap_read' for boundary in read_case['boundaries'])
        assert read_case['calls'].index('regmap_read') < read_case['calls'].index('disable_irq')
        joined = cases['firmware-request-missing-after-stock-PLL-and-ID']
        assert joined['result'] == -2
        assert joined['firmware_requests'] == ['cs40l26.wmfw']
        assert joined['synthetic_chip_identity'] == {'device': 0x40a270, 'revision': 0xb2}
        assert joined['regmap_reads'] == [dict(address=0, value=0x40a270),
                                          dict(address=4, value=0xb2)]
        assert joined['no_input_registration'] and joined['no_dsp_execution']
    for name, digest in report['sources'].items():
        assert sha(ROOT / name) == digest, name
    for name, digest in report['tests'].items():
        assert sha(ROOT / name) == digest, name
    print('PASS: 4 original OS2/OS3 probe ELFs, 12 failure paths plus 4 joined firmware boundaries; exact source hashes')


if __name__ == '__main__':
    main()
