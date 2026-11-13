#!/usr/bin/env python3
"""Bind missing source keys across codecs/fork, patch0106 and the clean image."""
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
    assert image.name == 'recovery-dijun-unified-backup-missing-key.img'
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
    assert patch['file'] == '0106-backup-missing-source-key.patch'
    assert sha(TREE / 'patches' / patch['file']) == patch['sha256']
    loaded, reports = {}, {}
    paths = {
        'restore': ('logs/archive-key-restore.json', 107, 0),
        'negative': ('logs/archive-key-negative.json', 6, 4),
        'pipeline': ('logs/archive-key-pipeline.json', 152, 0),
        'pipeline-negative': ('logs/archive-key-pipeline-negative.json', 12, 4),
    }
    for suffix, (name, count, failures) in paths.items():
        path = ROOT / name
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
    current = {c['case']: c for c in loaded['restore']['cases']}
    for case in loaded['negative']['cases']:
        assert current[case['case']]['status'] == 'PASS'
    expected_failures = {'append-key-enokey', 'append-key-enokey-empty',
                         'append-key-symlink', 'append-key-hardlink'}
    for case in loaded['negative']['cases']:
        assert (case['status'] == 'FAIL') == (case['case'] in expected_failures)
        if 'symlink' in case['case'] or 'hardlink' in case['case']:
            assert 'link metadata archived without opening' in current[case['case']]['output']
        else:
            assert 'original errno' in current[case['case']]['output']
    pipeline = {c['case']: c for c in loaded['pipeline']['cases']}
    for case in loaded['pipeline-negative']['cases']:
        assert (case['status'] == 'FAIL') == case['case'].endswith('enokey')
        now = pipeline[case['case']]
        assert now['status'] == 'PASS'
        assert 'inaccessible source failure reaches backup parent; no info publication' in now['output']
    old_source = ROOT / 'logs/archive-key-before/libtar/append.c'
    current_source = ANDROID / 'bootable/recovery/libtar/append.c'
    assert sha(old_source) != sha(current_source)
    for name, digest in loaded['pipeline-negative']['sources'].items():
        assert sha(name) == digest
        relative = Path(name).relative_to('logs/archive-key-before')
        assert sha(ANDROID / 'bootable/recovery' / relative) == digest, relative
    for source in (ROOT / 'logs/archive-key-before/libtar').glob('*'):
        if source.suffix in ['.c', '.h', '.go', '.bp'] and source.name != 'append.c':
            assert sha(source) == sha(current_source.parent / source.name), source
    before = entries(ROOT / 'imgs/built/recovery-dijun-unified-backup-source-read.img')
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
                  limits='Host libtar/codecs/fork and ordinary files; ENOKEY/EKEYREVOKED/EACCES open failures '
                         'are injected at selected fixture source only. Real link metadata/restore content and '
                         'no-info parent failure checked. No real fscrypt, TEE, ARM64 codec, full manager/GUI '
                         'or concurrent source snapshot/power-loss proof.')
    (ROOT / 'logs/archive-key-delivery-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: patch0106; libtar107; old4/6; codec152; old4/12; clean image/six profiles')


if __name__ == '__main__':
    main()
