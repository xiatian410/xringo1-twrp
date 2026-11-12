#!/usr/bin/env python3
"""Audit haptics provenance against extracted OTA bytes; never run a driver."""
import argparse
import json
from pathlib import Path

from firmware_facts import ROOT, SAMPLES, digest, elf_module, haptics_module
from acquire_firmware import sources

TREE = ROOT / 'dtsrc/O1_asic_dual'
PROPERTIES = {
    'ro.odm.mm.vibrator.resonant_frequency': '130',
    'ro.odm.mm.vibrator.cirrus': 'true',
    'ro.odm.mm.vibrator.manufacturer': 'cirrus',
}
FIRMWARE = {
    'cs40l26-a2h.bin', 'cs40l26-a2h1.bin', 'cs40l26-calib.bin',
    'cs40l26-calib.wmfw', 'cs40l26-dbc.bin', 'cs40l26-dvl.bin',
    'cs40l26-svc.bin', 'cs40l26.bin', 'cs40l26.wmfw',
}


def fingerprint(path):
    return {'path': str(path.relative_to(ROOT)), 'sha256': digest(path.read_bytes())}


def audit(profile_path):
    profile = json.loads(profile_path.read_text())
    sample = profile_path.parent.name
    analysis = SAMPLES / sample / 'analysis'
    prop_path = analysis / 'odm/etc/build.prop'
    properties = {}
    for number, raw in enumerate(prop_path.read_text().splitlines(), 1):
        line = raw.strip()
        if line.startswith('ro.odm.mm.vibrator.') and '=' in line:
            key, value = line.split('=', 1)
            assert key not in properties, (sample, 'duplicate property', key)
            properties[key] = {'value': value, 'line': number}
    for key, expected in PROPERTIES.items():
        assert properties[key]['value'] == expected, (sample, key)
    assert profile['haptics']['resonant_frequency_hz'] == 130

    facts = json.loads((analysis / 'facts.json').read_text())
    path, stock_module = haptics_module(facts)
    name = stock_module['modinfo']['name'][0]
    module_path = analysis / path
    module = elf_module(module_path.read_bytes())
    assert module['modinfo']['name'] == [name]
    assert 'i2c:cs40l26' in module['modinfo']['alias']
    hard_dependencies = sorted({n.replace('-', '_')
        for value in module['modinfo'].get('depends', [])
        for n in value.split(',') if n})
    plan_path = profile_path.parent / 'modules.plan'
    plan = [line.split() for line in plan_path.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith('#')]
    indexes = {row[0]: i for i, row in enumerate(plan)}
    assert len(indexes) == len(plan), (sample, 'duplicate planned module')
    row = plan[indexes[name]]
    assert len(row) == 4
    assert row[1] == digest(module_path.read_bytes())
    assert row[2] == f'/vendor_dlkm/lib/modules/{name}.ko'
    assert sorted(row[3].split(',')) == hard_dependencies
    # xring_i2c is the original pre-dependency in OS2/3 and the I2C bus
    # prerequisite in OS4. This checks plan order, not successful kernel probe.
    for dependency in set(hard_dependencies + ['xring_i2c']):
        assert indexes[dependency] < indexes[name], (sample, dependency)
    candidate = next(c for c in profile['haptics']['module_candidates']
                     if c['path'] == row[2].lstrip('/'))
    assert candidate['sha256'] == row[1]
    assert candidate['imports_sha256'] == module['imports_sha256']

    firmware = {}
    for destination, item in profile['assets'].items():
        if not destination.startswith('lib/firmware/cs40l26'):
            continue
        filename = Path(destination).name
        source = analysis / 'odm/firmware' / filename
        assert ROOT / item['source'] == source
        assert digest(source.read_bytes()) == item['sha256']
        assert (TREE / item['blob']).read_bytes() == source.read_bytes()
        assert item['size'] == source.stat().st_size
        assert profile['assets']['odm/firmware/' + filename]['sha256'] == item['sha256']
        firmware[destination] = {**fingerprint(source), 'blob': item['blob'], 'size': item['size']}
    assert {Path(p).name for p in firmware} == FIRMWARE
    return {
        'profile': fingerprint(profile_path), 'kernel_release': profile['kernel_release'],
        'property_file': fingerprint(prop_path), 'properties': properties,
        'module': {**fingerprint(module_path), 'name': name,
                   'hard_dependencies': hard_dependencies,
                   'vermagic': module['modinfo']['vermagic'],
                   'softdep': module['modinfo'].get('softdep', []),
                   'module_layout_crc': module['module_layout_crc'],
                   'imports_sha256': module['imports_sha256']},
        'module_plan': fingerprint(plan_path), 'prerequisites_precede_module': True,
        'ram_firmware': firmware,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'logs/haptics-profile-audit.json')
    args = parser.parse_args()
    samples = sorted((TREE / 'profiles').glob('*/profile.json'))
    assert {p.parent.name for p in samples} == set(sources())
    result = {
        'status': 'PASS', 'grade': 'S0/S1',
        'scope': 'Original ODM properties, module ELF/plan hashes and dependencies, '
                 'and nine ODM firmware files per profile against CAS bytes. '
                 'No driver probe, calibration, HAL or motor execution.',
        'profiles': {p.parent.name: audit(p) for p in samples},
        'scripts': [fingerprint(Path(__file__).resolve()), fingerprint(ROOT/'scripts/firmware_facts.py')],
    }
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(f'PASS: {len(samples)} firmware profiles, 130 Hz original properties, exact module plans, {len(samples) * len(FIRMWARE)} RAM firmware placements')


if __name__ == '__main__':
    main()
