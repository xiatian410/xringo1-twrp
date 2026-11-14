#!/usr/bin/env python3
"""Bind terminal admission/final reaping and finite checks to patch0127 delivery."""
import json
from pathlib import Path
from audit_terminal_reap import entries, read, sha
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def main():
    index = read(ROOT/'simulation-report.json')
    image = Path(index['image'])
    assert image.name == 'recovery-dijun-unified-terminal-shutdown.img'
    assert sha(image) == index['image_sha256']
    provenance = read(image.with_name(image.stem+'-sources.json'))
    assert provenance['image_sha256'] == sha(image)
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    build = ROOT/provenance['build_log']
    assert sha(build) == provenance['build_log_sha256']
    assert build.read_text().count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in build.read_text()
    assert manifest(TREE) == manifest(ANDROID/'device/xiaomi/O1_asic')
    spec = read(TREE/'patches/series.json')['repositories']['bootable/recovery']
    patch = spec['patches'][-1]
    assert patch['file'] == '0127-terminal-shutdown-boundary.patch'
    assert sha(TREE/'patches'/patch['file']) == patch['sha256']
    reports = {}
    for suffix, count, failures in [('current',5,0),('old',5,4),('engine',5,0),('reap',7,0)]:
        path = ROOT/f'logs/terminal-shutdown-{suffix}.json'
        report = read(path)
        assert len(report['cases']) == count
        assert sum(c['status']=='FAIL' for c in report['cases']) == failures
        for name, digest in report['sources'].items():
            assert sha(name) == digest, name
        item = next(c for c in index['additional_checks'] if c['evidence']==str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        assert not any('AddressSanitizer' in c['output'] or 'runtime error:' in c['output'] for c in report['cases'])
        if suffix=='old':
            assert all(c['status']==('PASS' if c['case']=='failed-reservation' else 'FAIL') for c in report['cases'])
        reports[suffix] = dict(cases=count,failures=failures,sha256=sha(path))
    # Static wiring evidence only; the full GUI shutdown body is not executed.
    gui = (ANDROID/'bootable/recovery/gui2/gui2.cpp').read_text()
    shutdown = gui.split('static void shutdown_gui2() {',1)[1].split('static bool gui2_loop_should_exit',1)[0]
    assert 'if (terminal != nullptr) terminal->shutdown();' in shutdown
    assert shutdown.index('terminal->shutdown()') < shutdown.index('gui2_app::shutdown_graphics')
    before = entries(ROOT/'imgs/built/recovery-dijun-unified-digest-preflight.img')
    after = entries(image)
    changed = sorted(n for n in set(before)|set(after) if before.get(n)!=after.get(n))
    assert set(changed) <= {'prop.default','ramdisk-files.sha256sum','system/bin/recovery','system/lib64/libgui2.so'}, changed
    assert 'system/bin/recovery' in changed and 'system/lib64/libgui2.so' in changed
    package = read(image.with_suffix('.json'))
    assert package['sha256']==sha(image) and len(package['profiles'])==6
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    result = dict(status='PASS',scope=__doc__,image_sha256=sha(image),production_sources=len(provenance['files']),jobs=provenance['jobs'],reports=reports,changed_ramdisk_entries=changed,
                  limits='Original PTY owner/full terminal engine/GUI adapter on host with real private PTYs/fork/threads/executor. Shell exec, write scheduling, wait scheduling and selected failures are fixtures. GUI final call statically inspected only. No descendant cleanup, full GUI/Android shell, physical reboot, process-wide quiescence or physical I/O deadline proof. Existing OTA reused.')
    (ROOT/'logs/terminal-shutdown-delivery-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: patch0127; admission5/engine5/reap7; old4/5 failures; clean image/six profiles')


if __name__ == '__main__':
    main()
