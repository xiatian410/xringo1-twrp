#!/usr/bin/env python3
"""Reconstruct pinned patches, then synchronize the maintained tree to AOSP.

Only explicitly listed patched files may differ from the pinned repository
baseline. Unrecognized changes are refused, never silently overwritten. A
changed generated device copy is retained in backups before replacement.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
TREE = ROOT / 'dtsrc/O1_asic_dual'
ANDROID = Path('/root/AAA/twrp')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def manifest(tree):
    out = {}
    for p in sorted(tree.rglob('*')):
        if '.git' in p.relative_to(tree).parts:
            continue
        if p.is_symlink():
            value = ['link', os.readlink(p)]
        elif p.is_file():
            value = ['file', p.stat().st_mode & 0o777, sha(p.read_bytes())]
        else:
            continue
        out[str(p.relative_to(tree))] = value
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sync', action='store_true', help='apply verified changes; default only checks')
    args = parser.parse_args()
    series = json.loads((TREE / 'patches/series.json').read_text())
    pending = []
    for repo, spec in series['repositories'].items():
        src = ANDROID / repo
        head = subprocess.check_output(['git', '-C', str(src), 'rev-parse', 'HEAD'], text=True).strip()
        if head != spec['commit']:
            raise ValueError(f'{repo}: baseline changed: {head}')
        changed = set(subprocess.check_output(['git', '-C', str(src), 'diff', 'HEAD', '--name-only'], text=True).splitlines())
        if changed - spec['result_files'].keys():
            raise ValueError(f'unlisted tracked source changes: {repo}: {sorted(changed - spec["result_files"].keys())}')
        with tempfile.TemporaryDirectory(prefix='dijun-patches-') as temp:
            stage = Path(temp)
            for name in spec['result_files']:
                p = stage / name
                p.parent.mkdir(parents=True, exist_ok=True)
                entry = subprocess.check_output(['git', '-C', str(src), 'ls-tree', head, '--', name], text=True).split()
                # A patch may introduce a new source file. Leave it absent in
                # the baseline so git apply verifies its creation explicitly.
                if entry:
                    p.write_bytes(subprocess.check_output(['git', '-C', str(src), 'show', f'{head}:{name}']))
                    p.chmod(int(entry[0], 8) & 0o777)
            for item in spec['patches']:
                patch = (TREE / 'patches' / item['file']).resolve()
                if not patch.is_relative_to(TREE) or sha(patch.read_bytes()) != item['sha256']:
                    raise ValueError(f'patch hash mismatch: {patch}')
                subprocess.run(['git', 'apply', '--check', str(patch)], cwd=stage, check=True)
                subprocess.run(['git', 'apply', str(patch)], cwd=stage, check=True)
            for name, expected in spec['result_files'].items():
                data = (stage / name).read_bytes()
                if sha(data) != expected:
                    raise ValueError(f'patch result mismatch: {repo}/{name}')
                existing = src / name
                if existing.is_symlink():
                    raise ValueError('refusing a source symlink')
                old = existing.read_bytes() if existing.exists() else None
                if old is not None and sha(old) == expected:
                    continue
                entry = subprocess.check_output(['git', '-C', str(src), 'ls-tree', head, '--', name], text=True).strip()
                base = subprocess.check_output(['git', '-C', str(src), 'show', f'{head}:{name}']) if entry else None
                if old != base:
                    raise ValueError(f'unrecognized local changes: {existing}')
                pending.append((existing, data))
        print(f'PASS: {repo}: patches reproduce {len(spec["result_files"])} expected files from {head}')
    dest = ANDROID / 'device/xiaomi/O1_asic'
    if dest.is_symlink():
        raise ValueError('refusing a generated device-tree symlink')
    wanted = manifest(TREE)
    changed = not dest.exists() or manifest(dest) != wanted
    if not args.sync:
        print(f'Pending: {len(pending)} source updates, device tree changed={changed}')
        return
    for p, data in pending:
        p.write_bytes(data)
    if changed:
        with tempfile.TemporaryDirectory(prefix='.dijun-sync-', dir=dest.parent) as temp:
            stage = Path(temp) / 'tree'
            shutil.copytree(TREE, stage, symlinks=True, ignore=shutil.ignore_patterns('.git'))
            if manifest(stage) != wanted:
                raise ValueError('staged tree changed during synchronization')
            if dest.exists():
                backup = ROOT / 'backups' / f'device-tree-{time.time_ns()}'
                backup.parent.mkdir(exist_ok=True)
                dest.rename(backup)
                try:
                    stage.rename(dest)
                except BaseException:
                    backup.rename(dest)
                    raise
                print(f'Previous generated tree retained: {backup}')
            else:
                stage.rename(dest)
    print(f'PASS: maintained tree synchronized ({len(wanted)} entries)')


if __name__ == '__main__':
    main()
