#!/usr/bin/env python3
"""Bind directory enumeration failure propagation to patch0107 and clean image."""
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
    assert image.name == 'recovery-dijun-unified-backup-directory-errors.img'
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
    assert patch['file'] == '0107-backup-directory-read-errors.patch'
    assert sha(TREE / 'patches' / patch['file']) == patch['sha256']
    loaded, reports = {}, {}
    for suffix, name, count, failures in [
        ('restore', 'archive-walk-restore', 111, 0),
        ('negative', 'archive-walk-negative', 4, 3),
        ('pipeline', 'archive-walk-pipeline', 184, 0),
        ('pipeline-negative', 'archive-walk-pipeline-negative-final', 32, 21),
    ]:
        path = ROOT / 'logs' / (name + '.json')
        report = read(path)
        assert len(report['cases']) == count
        assert sum(c['status'] == 'FAIL' for c in report['cases']) == failures
        for group in ['sources', 'shared_sources', 'tests', 'test_sources']:
            for name, digest in report.get(group, {}).items():
                source = Path(name)
                assert sha(source if source.is_absolute() else ROOT / source) == digest, name
        item = next(c for c in index['additional_checks'] if c['evidence'] == str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        loaded[suffix] = report
        reports[suffix] = dict(sha256=sha(path), cases=count, failures=failures)
    assert loaded['restore']['tests'] == loaded['negative']['tests']
    assert loaded['pipeline']['test_sources'] == loaded['pipeline-negative']['test_sources']
    for suffix in ['restore', 'pipeline']:
        current = {c['case']: c for c in loaded[suffix]['cases']}
        previous = loaded['negative' if suffix == 'restore' else 'pipeline-negative']['cases']
        for case in previous:
            now = current[case['case']]
            assert now['status'] == 'PASS'
            if suffix == 'restore':
                assert (case['status'] == 'FAIL') == (case['case'] != 'walk-stale')
                assert ('stale errno' if case['case'] == 'walk-stale' else 'closes every directory') in now['output']
            elif not case['case'].endswith('stale-errno'):
                assert 'all directories closed; no info publication' in now['output']
    changed_sources = {'twrpTar.cpp', 'libtar/wrapper.c'}
    before_root = ROOT / 'logs/archive-walk-before'
    for source in before_root.rglob('*'):
        if not source.is_file():
            continue
        relative = str(source.relative_to(before_root))
        if source.suffix not in ['.c', '.cpp', '.h', '.hpp', '.bp']:
            continue
        assert (sha(source) != sha(ANDROID / 'bootable/recovery' / relative)) == (relative in changed_sources), relative
    before = entries(ROOT / 'imgs/built/recovery-dijun-unified-backup-missing-key.img')
    after = entries(image)
    changed = sorted(n for n in set(before) | set(after) if before.get(n) != after.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/bin/recovery'], changed
    assert after['system/bin/recovery'] == (ANDROID / 'out/target/product/O1_asic/recovery/root/system/bin/recovery').read_bytes()
    package = read(image.with_suffix('.json'))
    assert package['sha256'] == sha(image) and len(package['profiles']) == 6
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, image_sha256=sha(image),
                  production_sources=len(provenance['files']), jobs=provenance['jobs'],
                  reports=reports, changed_ramdisk_entries=changed,
                  limits='Host original libtar/tar/pigz/OAES/fork, private files and injected opendir/readdir/closedir errors. '
                         'Directory closure, errno, parent failure/no-info and stale-errno roundtrips checked. '
                         'Not real fscrypt/ARM64 codec/manager/GUI, full source consistency or power-loss proof; '
                         'size estimation and DT_UNKNOWN behavior unchanged.')
    (ROOT / 'logs/archive-walk-delivery-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: patch0107; libtar111; old3/4; codec184; old21/32; clean image/six profiles')


if __name__ == '__main__':
    main()
