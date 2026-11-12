#!/usr/bin/env python3
"""Inventory verified system-family EROFS images without mounts or APK extraction.

Directory entries are walked by inode. Only identity/init/VINTF/linker/fstab
resources are read, hashed and saved. Unread payloads are explicitly recorded as
directory inventory only; this is not a test of arbitrary apps/framework code.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

from acquire_firmware import ROOT, SAMPLES, sha256_file
from firmware_facts import digest

PARTITIONS = ['system', 'system_ext', 'product', 'mi_ext', 'mi_product']


def dump(image, *options):
    return subprocess.run(['dump.erofs', *options, str(image)], check=True,
                          capture_output=True, timeout=120).stdout


def selected(path):
    p = PurePosixPath(path)
    return (p.name in ['build.prop', 'default.prop', 'prop.default'] or
            p.name.startswith(('fstab.', 'linker.config.')) or p.suffix == '.rc' or
            '/vintf/' in '/' + path or '/linkerconfig/' in '/' + path or
            ('/etc/' in '/' + path and p.suffix == '.prop'))


def inspect(sample, partition, item):
    base = SAMPLES / sample
    image = base / (partition + '.img')
    if image.is_symlink() or not image.is_file():
        raise ValueError('requires a regular, verified image')
    if sha256_file(image) != item['sha256']:
        raise ValueError(f'{sample}/{partition}: partition hash mismatch')
    output = base / 'analysis' / 'system-resources' / partition
    output.mkdir(parents=True, exist_ok=True)
    report = dict(source=f'{partition}.img', sha256=item['sha256'],
                  size=image.stat().st_size, entries={}, resources={}, properties={},
                  scope='All directory entries; selected identity/init/VINTF/linker/fstab bytes only')
    queue = [('', None)]
    visited = set()
    while queue:
        parent, inode = queue.pop()
        if len(visited) > 100000:
            raise ValueError('directory traversal bound exceeded')
        option = '--path=/' if inode is None else f'--nid={inode}'
        listing = dump(image, '--ls', option).decode('utf-8')
        if inode is None:
            inode = int(re.search(r'NID: (\d+)', listing).group(1))
        if inode in visited:
            raise ValueError(f'directory cycle/alias at {parent}')
        visited.add(inode)
        for line in listing.splitlines():
            match = re.fullmatch(r'\s+(\d+)\s+(\d+)\s+(.+)', line)
            if not match:
                continue
            nid, kind, name = match.groups()
            if name in ['.', '..']:
                continue
            if '/' in name or '\x00' in name or '\n' in name:
                raise ValueError('unsafe entry name')
            path = str(PurePosixPath(parent) / name)
            if path in report['entries']:
                raise ValueError('duplicate path')
            report['entries'][path] = dict(nid=int(nid), type=int(kind))
            if kind == '2':
                queue.append((path, int(nid)))
            elif kind == '1' and selected(path):
                metadata = dump(image, f'--nid={nid}').decode()
                size = int(re.search(r'Size: (\d+)', metadata).group(1))
                if size > 8 * 1024 * 1024:
                    raise ValueError(f'oversized configuration file: {path}')
                data = dump(image, '--cat', f'--nid={nid}')
                if len(data) != size:
                    raise ValueError(f'content size mismatch: {path}')
                uid, gid, mode = re.search(r'Uid:\s+(\d+)\s+Gid:\s+(\d+)\s+Access:\s+([0-7]+)', metadata).groups()
                target = output / path
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.is_symlink():
                    raise ValueError('symlink output')
                target.write_bytes(data)
                entry = dict(nid=int(nid), size=size, sha256=digest(data), uid=int(uid),
                             gid=int(gid), mode=mode, extracted=str(target.relative_to(ROOT)))
                report['resources'][path] = entry
                if PurePosixPath(path).name in ['build.prop', 'default.prop', 'prop.default']:
                    props = {}
                    for line in data.decode().splitlines():
                        if '=' in line and not line.lstrip().startswith('#'):
                            key, value = line.split('=', 1)
                            if key in props and props[key] != value:
                                raise ValueError(f'conflicting property: {path}/{key}')
                            props[key] = value
                    report['properties'][path] = props
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', nargs='+', default=[p.name for p in sorted(SAMPLES.iterdir()) if p.is_dir()])
    args = parser.parse_args()
    for sample in args.samples:
        if sample not in {p.name for p in SAMPLES.iterdir() if p.is_dir()}:
            raise ValueError('unknown sample')
        base = SAMPLES / sample
        inventory = json.loads((base / 'inventory.json').read_text())
        dest = base / 'analysis/system-resources.json'
        result = dict(sample=sample, partitions={}, pending=[], absent=[])
        previous = json.loads(dest.read_text()) if dest.exists() else {'partitions': {}}
        for partition in PARTITIONS:
            if partition not in inventory['partitions']:
                result['absent'].append(partition)
                continue
            if not (base / (partition + '.img')).is_file():
                result['pending'].append(partition)
                continue
            expected = inventory['partitions'][partition]
            cached = previous['partitions'].get(partition)
            if cached and cached['sha256'] == expected['sha256']:
                # Do not trust a stale report or changed extracted resource.
                assert sha256_file(base / (partition + '.img')) == expected['sha256']
                for resource in cached['resources'].values():
                    assert sha256_file(ROOT / resource['extracted']) == resource['sha256']
                report = cached
            else:
                report = inspect(sample, partition, expected)
            result['partitions'][partition] = report
            print(f'{sample}/{partition}: {len(report["entries"])} entries, {len(report["resources"])} resources', flush=True)
        temp = dest.with_suffix('.partial')
        temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        temp.replace(dest)


if __name__ == '__main__':
    main()
