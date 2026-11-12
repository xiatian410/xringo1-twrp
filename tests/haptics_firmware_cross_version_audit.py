#!/usr/bin/env python3
"""Compare stock Cirrus firmware bytes across the six extracted OS samples."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ['os2-initial', 'os2-final', 'os3-initial', 'os3-final',
           'os4-current', 'os4-stable']
FILES = ['cs40l26.wmfw', 'cs40l26-calib.wmfw', 'cs40l26.bin',
         'cs40l26-svc.bin', 'cs40l26-dvl.bin', 'cs40l26-a2h.bin',
         'cs40l26-dbc.bin']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    records = []
    source_hashes = {}
    for sample in SAMPLES:
        base = ROOT / 'firmware/samples' / sample / 'analysis'
        facts = json.loads((base / 'facts.json').read_text())
        candidates = [path for path, record in facts['modules'].items()
                      if path.startswith('vendor_dlkm/') and 'cs40l26_i2c_probe' in record['exports']]
        assert len(candidates) == 1, (sample, candidates)
        module = base / candidates[0]
        files = {}
        for name in FILES:
            entries = {}
            for partition in ['odm', 'vendor']:
                path = base / partition / 'firmware' / name
                if not path.is_file():
                    continue
                entries[partition] = dict(path=str(path.relative_to(ROOT)),
                                          size=path.stat().st_size, sha256=sha(path))
                source_hashes[str(path.relative_to(ROOT))] = entries[partition]['sha256']
            assert 'odm' in entries and 'vendor' in entries, (sample, name, entries)
            files[name] = dict(partitions=entries,
                               odm_vendor_identical=entries['odm']['sha256'] == entries['vendor']['sha256'])
        source_hashes[str(module.relative_to(ROOT))] = sha(module)
        records.append(dict(sample=sample, module=dict(path=str(module.relative_to(ROOT)), sha256=sha(module)),
                            firmware=files))

    cross_version = {}
    for name in FILES:
        hashes = {sample: next(r for r in records if r['sample'] == sample)['firmware'][name]['partitions']['odm']['sha256']
                  for sample in SAMPLES}
        cross_version[name] = dict(sha256_by_sample=hashes, identical_across_samples=len(set(hashes.values())) == 1)

    auditor = ROOT / 'scripts/audit_haptics_firmware_cross_version.py'
    report = dict(status='PASS', scope=__doc__.strip(), samples=records,
                  cross_version= cross_version,
                  conclusion='Extracted ODM/vendor bytes only; this does not prove the running kernel requested, parsed, uploaded, or executed them.',
                  sources=source_hashes, hardware_result='unverified',
                  tests={'tests/haptics_firmware_cross_version_audit.py': sha(Path(__file__)),
                         'scripts/audit_haptics_firmware_cross_version.py': sha(auditor)})
    out = ROOT / 'logs/haptics-firmware-cross-version-audit.json'
    out.write_text(json.dumps(report, indent=2) + '\n')
    print('PASS:', len(SAMPLES), 'samples x', len(FILES), 'firmware files; ODM/vendor and cross-version hashes recorded')


if __name__ == '__main__':
    main()
