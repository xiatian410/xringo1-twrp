#!/usr/bin/env python3
"""Generate strict, read-only profile preflight manifests from original bytes."""
import json
from pathlib import Path

from firmware_facts import ROOT, SAMPLES, digest, haptics_module

TREE = ROOT / 'dtsrc/O1_asic_dual'


def main():
    for file in sorted((TREE / 'profiles').glob('*/profile.json')):
        profile = json.loads(file.read_text())
        sample = profile['id']
        facts = json.loads((SAMPLES / sample / 'analysis/facts.json').read_text())
        systems = SAMPLES / sample / 'analysis/system-resources.json'
        report = json.loads(systems.read_text()) if systems.exists() else {'partitions': {}}
        if 'system' not in report['partitions']:
            print(sample, 'pending verified system build.prop; no selection manifest generated')
            continue
        system = report['partitions']['system']['resources']['system/build.prop']
        anchors = {'system': ('/system_root/system/build.prop', ROOT / system['extracted'], system['sha256'])}
        haptic, _ = haptics_module(facts)
        for role, path in {'vendor': 'vendor/build.prop', 'odm': 'odm/etc/build.prop',
                           'fstab': 'vendor/etc/fstab.O1_asic',
                           'touch': 'vendor_dlkm/lib/modules/synaptics_tcm2.ko',
                           'haptics': haptic}.items():
            anchors[role] = ('/' + path, SAMPLES / sample / 'analysis' / path, facts['files'][path]['sha256'])
        lines = ['schema 1', 'kernel ' + profile['kernel_release']]
        sources = {}
        for role, (runtime, source, sha) in anchors.items():
            assert digest(source.read_bytes()) == sha, source
            lines.append(f'identity {role} {sha} {runtime}')
            sources[runtime] = dict(source=str(source.relative_to(ROOT)), sha256=sha, role=role)
        blobs = {a['sha256']: a['size'] for a in profile['assets'].values()}
        for sha, size in sorted(blobs.items()):
            blob = TREE / 'prebuilt/common/profile-blobs' / sha
            assert blob.stat().st_size == size and digest(blob.read_bytes()) == sha
            lines.append(f'blob {sha} {size}')
        (file.parent / 'selection.conf').write_text('\n'.join(lines) + '\n')
        (file.parent / 'selection-sources.json').write_text(json.dumps(sources, indent=2) + '\n')
        print(sample, '6 identity/module anchors and', len(blobs), 'blobs; not activated')


if __name__ == '__main__':
    main()
