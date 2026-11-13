#!/usr/bin/env python3
"""Bind complete size-scan error propagation to patch0117 and a clean image."""
import hashlib
import json
from pathlib import Path

from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def entries(path):
    return {e[0]: e[-1] for e in ramdisk_entries(boot_parts(path.read_bytes())[1]['ramdisk'])}


def main():
    index = read(ROOT / 'simulation-report.json')
    image = Path(index['image'])
    assert image.name == 'recovery-dijun-unified-size-scan-errors.img'
    assert sha(image) == index['image_sha256']
    provenance = read(image.with_name(image.stem + '-sources.json'))
    assert provenance['image_sha256'] == sha(image)
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    build = ROOT / provenance['build_log']
    assert sha(build) == provenance['build_log_sha256']
    assert build.read_text().count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in build.read_text()
    assert manifest(TREE) == manifest(ANDROID / 'device/xiaomi/O1_asic')
    spec = read(TREE / 'patches/series.json')['repositories']['bootable/recovery']
    patch = spec['patches'][-1]
    assert patch['file'] == '0117-size-scan-error-propagation.patch'
    assert sha(TREE / 'patches' / patch['file']) == patch['sha256']
    reports, loaded = {}, {}
    specs = [('exclusion-errors', 16, 0), ('exclusion-errors-old', 16, 12),
             ('exclusion-errors-regression', 19, 0), ('data-size-errors', 14, 0),
             ('data-size-errors-old', 14, 11), ('exclusion-errors-session', 5, 0),
             ('exclusion-errors-codec-final', 18, 0), ('exclusion-errors-codec-old', 4, 1),
             ('exclusion-errors-otg', 15, 0)]
    for name, count, failures in specs:
        path = ROOT / ('logs/' + name + '.json')
        report = read(path)
        assert len(report['cases']) == count
        assert sum(c['returncode'] != 0 for c in report['cases']) == failures
        for group in ['sources', 'shared_sources', 'test_sources']:
            for filename, digest in report.get(group, {}).items():
                source = Path(filename)
                assert sha(source if source.is_absolute() else ROOT / source) == digest, filename
        item = next(c for c in index['additional_checks'] if c['evidence'] == str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        reports[name] = dict(sha256=sha(path), cases=count, failures=failures)
        loaded[name] = report
    for key in ['exclusion-errors', 'data-size-errors', 'exclusion-errors-codec']:
        new = loaded[key if key != 'exclusion-errors-codec' else key + '-final']
        old = loaded[key + '-old']
        if 'test_sources' in new:
            assert new['test_sources'] == old['test_sources']
        else:
            for name, digest in old['sources'].items():
                if str(name).startswith(str(ROOT / 'tests')):
                    assert new['sources'][name] == digest
    for case in loaded['data-size-errors']['cases']:
        assert 'consumer_error_propagated=1 partial_not_final=1 lifecycle_closed=1' in case['output']
    for case in loaded['exclusion-errors']['cases']:
        assert 'complete_status=1 no_partial_publication=1 directories_closed=1' in case['output']
    assert any(c['case'] == 'session-final-size-fail' for c in loaded['exclusion-errors-session']['cases'])
    before = entries(ROOT / 'imgs/built/recovery-dijun-unified-mtp-staging-create.img')
    after = entries(image)
    changed = sorted(n for n in set(before) | set(after) if before.get(n) != after.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/bin/recovery'], changed
    library = 'system/bin/recovery'
    assert after[library] == (ANDROID / 'out/target/product/O1_asic/recovery/root' / library).read_bytes()
    package = read(image.with_suffix('.json'))
    assert package['sha256'] == sha(image) and len(package['profiles']) == 6
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, image_sha256=sha(image),
                  production_sources=len(provenance['files']), jobs=provenance['jobs'],
                  reports=reports, changed_ramdisk_entries=changed,
                  limits='Ordinary-file host scans/threads and codec chroots with ASan/UBSan; named I/O faults. '
                         'Mount/statfs/df/commands/GUI are fixtures. Session completion test substitutes size result; '
                         'underlying walkers and production UpdateSize/background consumers are tested separately. '
                         'No physical mount/fscrypt/DRM, allocated-block estimate or full concurrent source consistency.')
    (ROOT / 'logs/exclusion-errors-delivery-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: patch0117; walks16/regression19; consumers14; session5; codec18; OTG15; clean image/six profiles')


if __name__ == '__main__':
    main()
