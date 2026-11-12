#!/usr/bin/env python3
"""Check current-image security-service relocation evidence without hardware claims."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from verify_devicefix import entries


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    index = json.loads((ROOT/'simulation-report.json').read_text())
    report_path = ROOT/'logs/profile-service-relocation.json'
    report = json.loads(report_path.read_text())
    assert report['status'] == 'PASS' and report['count'] == 30
    image = Path(index['image'])
    raw, archive = entries(image)
    assert sha(raw) == index['image_sha256'] == report['image_sha256']
    production = json.loads(image.with_name(image.stem+'-sources.json').read_text())
    assert production['image_sha256'] == sha(raw) and len(production['files']) == 765
    for name, digest in production['files'].items():
        assert sha(Path(name).read_bytes()) == digest, name
    for name, digest in report['sources'].items():
        assert sha(Path(name).read_bytes()) == digest, name
    for name, digest in report['image_entries'].items():
        assert sha(archive[name][-1]) == digest, name
    profiles = sorted(n.split('/')[4] for n in archive if
                      n.startswith('system/etc/dijun/profiles/') and n.endswith('/runtime-files.list'))
    assert len(profiles) == 6
    for profile in profiles:
        cases = [c for c in report['cases'] if c['profile'] == profile]
        assert len(cases) == 5 and all(c['status'] == 'PASS' for c in cases)
        inventory = {}
        for line in archive[f'system/etc/dijun/profiles/{profile}/runtime-files.list'][-1].decode().splitlines():
            digest, mode, name = line.split()
            inventory[name] = digest
        positive = [c for c in cases if c['case'] == 'relocated-before-constructors']
        assert len(positive) == 3
        for case in positive:
            assert case['g_is_ldd'] == 0 and case['stop_offset'] == report['breakpoint_offset']
            assert len(case['loaded']) > 6
            for library in case['loaded']:
                if library['path'] == '[vdso]':
                    continue
                name = library['path']
                if name in inventory:
                    assert library['sha256'] == inventory[name]
                else:
                    assert library['sha256'] == sha(archive[name.lstrip('/')][-1])
        negative = next(c for c in cases if c['case'] == 'undefined-symbol-control')
        assert negative['original_sha256'] == inventory['/vendor/bin/tee-supplicant']
        assert negative['control_sha256'] != negative['original_sha256']
        assert negative['exit'] != 0 and 'cannot locate symbol "bad_missing"' in negative['stderr']
        missing = next(c for c in cases if c['case'] == 'missing-tee-library')
        assert missing['exit'] != 0 and 'libteecli.so' in missing['stderr'] and 'not found' in missing['stderr']
    assert any(c.get('evidence') == 'logs/profile-service-relocation.json' and
               c['evidence_sha256'] == sha(report_path.read_bytes()) for c in index['additional_checks'])
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', image_sha256=index['image_sha256'], production_sources=765,
                  original_service_relocations=18, undefined_symbol_controls=6, missing_library_controls=6,
                  evidence_sha256=sha(report_path.read_bytes()), audit_source_sha256=sha(Path(__file__).read_bytes()),
                  scope='Unmodified service relocation before constructors via image ARM64 linker; '
                  'no service initialization, Binder/TEE/key results, full namespace/init or physical testing.')
    (ROOT/'logs/profile-service-relocation-audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: six profiles/original service relocation18/symbol rejection6/missing-library6;765 sources. Full12 open.')


if __name__ == '__main__':
    main()
