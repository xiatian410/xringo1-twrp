#!/usr/bin/env python3
"""Generate activation manifests and ordered module plans from verified OTA bytes.

No modules are bundled: runtime copies only this profile's unloaded modules
from its mounted partitions or inherited vendor_boot. Hard dependencies and
available soft-dependency ordering are checked before emitting a plan.
"""
import json
from pathlib import Path
import re
from graphlib import TopologicalSorter, CycleError

from firmware_facts import ROOT, SAMPLES, digest, haptics_module

TREE = ROOT / 'dtsrc/O1_asic_dual'


def canonical(name):
    return name.removesuffix('.ko').replace('-', '_')


def module_plan(sample, facts):
    modules = {}
    # Prefer a mounted partition to an inherited ramdisk duplicate.
    for prefix in ['vendor_boot/', 'system_dlkm/', 'vendor_dlkm/']:
        for path, item in facts['modules'].items():
            if path.startswith(prefix):
                name = item['modinfo']['name'][0]
                modules[name] = (path, item)
    _, haptic = haptics_module(facts)
    roots = ['synaptics_tcm2', haptic['modinfo']['name'][0]]
    hard, pre, post, unknown, ignored = {}, {}, {}, [], []
    for name, (path, item) in modules.items():
        hard[name] = {canonical(dep) for value in item['modinfo'].get('depends', [])
                      for dep in value.split(',') if dep}
        pre[name], post[name] = set(), set()
        for value in item['modinfo'].get('softdep', []):
            if re.search(r'(?:pre|post):\S', value):
                # Android libmodprobe requires a separate pre:/post: token.
                # Do not reinterpret a vendor typo into a new dependency cycle.
                ignored.append({'owner': name, 'malformed_softdep': value})
                continue
            target = None
            for token in value.split():
                if token == 'pre:': target = pre[name]
                elif token == 'post:': target = post[name]
                elif target is None: raise ValueError(f'{name}: malformed softdep')
                else: target.add(canonical(token))
    # Include the stock depmod softdep files as well as ELF .modinfo.
    for path, record in facts['files'].items():
        if not path.endswith('/modules.softdep'):
            continue
        source = SAMPLES / sample / 'analysis' / path
        assert digest(source.read_bytes()) == record['sha256']
        for line in source.read_text().splitlines():
            tokens = line.split()
            if not tokens or tokens[0].startswith('#'): continue
            if re.search(r'(?:pre|post):\S', line):
                ignored.append({'file': path, 'malformed_softdep': line})
                continue
            assert tokens[0] == 'softdep' and len(tokens) >= 4
            name = canonical(tokens[1])
            if name not in modules: continue
            target = None
            for token in tokens[2:]:
                if token == 'pre:': target = pre[name]
                elif token == 'post:': target = post[name]
                elif target is None: raise ValueError(line)
                else: target.add(canonical(token))
    selected = set()
    def visit(name):
        if name in selected: return
        if name not in modules: raise ValueError(f'{sample}: missing hard dependency {name}')
        selected.add(name)
        for dep in hard[name]: visit(dep)
        for dep in pre[name] | post[name]:
            if dep in modules: visit(dep)
            else: unknown.append({'owner': name, 'optional_softdep': dep})
    for name in roots: visit(name)
    graph = {name: set(hard[name]) for name in selected}
    list(TopologicalSorter(graph).static_order())  # Hard cycles are fatal.
    deferred_soft_order = []
    edges = []
    for name in sorted(selected):
        edges += [(name, dep) for dep in sorted(pre[name] & selected)]
        edges += [(dep, name) for dep in sorted(post[name] & selected)]
    for owner, dep in edges:
        if dep in graph[owner]: continue
        graph[owner].add(dep)
        try:
            list(TopologicalSorter(graph).static_order())
        except CycleError as error:
            graph[owner].remove(dep)
            # Stock softdeps are optional. Keep both modules in the closure,
            # load according to hard dependencies, and record the impossible
            # soft ordering explicitly instead of recursively looping.
            deferred_soft_order.append(dict(owner=owner, after=dep, cycle=error.args[1]))
    # A slow optional haptic/audio probe must not consume the shared module
    # deadline before the touchscreen has even been attempted. Honor every
    # accepted graph edge, choosing the touch hard closure first when ready.
    touch_required = set()
    def touch_visit(name):
        if name in touch_required: return
        touch_required.add(name)
        for dep in hard[name]: touch_visit(dep)
    touch_visit('synaptics_tcm2')
    haptics_required = set()
    def haptics_visit(name):
        if name in haptics_required: return
        haptics_required.add(name)
        for dep in hard[name]: haptics_visit(dep)
    haptics_visit(roots[1])
    sorter = TopologicalSorter({k: sorted(v) for k, v in sorted(graph.items())})
    sorter.prepare()
    ready, order = set(), []
    while sorter.is_active():
        ready.update(sorter.get_ready())
        touch_pending = bool(touch_required - set(order))
        name = min(ready, key=lambda n: (
            0 if n in touch_required else
            1 if n in haptics_required and not touch_pending else 2, n))
        ready.remove(name)
        order.append(name)
        sorter.done(name)
    lines, records = [], {}
    for name in order:
        assert re.fullmatch(r'[a-zA-Z0-9_]+', name), name
        path, item = modules[name]
        sha = facts['files'][path]['sha256']
        source = SAMPLES / sample / 'analysis' / path
        assert digest(source.read_bytes()) == sha
        runtime = '/' + path.removeprefix('vendor_boot/fragment-0/')
        deps = ','.join(sorted(hard[name])) or '-'
        lines.append(f'{name} {sha} {runtime} {deps}')
        records[name] = dict(source=str(source.relative_to(ROOT)), runtime=runtime,
                             sha256=sha, hard=sorted(hard[name]),
                             pre=sorted(pre[name]), post=sorted(post[name]))
    for path in facts['files']:
        if path.endswith('/modules.options'):
            text = (SAMPLES / sample / 'analysis' / path).read_text()
            if any(line.strip() and not line.lstrip().startswith('#') for line in text.splitlines()):
                raise ValueError(f'{sample}: review nonempty module options before generating plan')
    return lines, dict(roots=roots, order=order, modules=records,
                       touch_priority_hard_closure=sorted(touch_required),
                       haptics_priority_hard_closure=sorted(haptics_required),
                       unavailable_optional_softdeps=unknown, ignored_vendor_syntax=ignored,
                       conflicting_optional_order=deferred_soft_order)


def main():
    common = {}
    for file in sorted((TREE / 'profiles').glob('*/profile.json')):
        profile = json.loads(file.read_text())
        sample = profile['id']
        facts = json.loads((SAMPLES / sample / 'analysis/facts.json').read_text())
        lines = []
        for dest, item in sorted(profile['assets'].items()):
            if dest.startswith('system/etc/vintf/manifest/'):
                if dest in common and common[dest] != item['sha256']:
                    raise ValueError(f'VINTF differs across profiles: {dest}')
                common[dest] = item['sha256']
                continue
            # The preferred ODM firmware is already represented at lib/firmware.
            # /odm/firmware on Android is a symlink into /vendor/odm/firmware.
            if dest.startswith('odm/firmware/'): continue
            assert dest.startswith(('vendor/bin/', 'vendor/mitee/ta/', 'vendor/firmware/',
                                    'system/lib64/mitee/', 'lib/firmware/'))
            assert re.fullmatch(r'[a-zA-Z0-9_./@+-]+', dest) and '..' not in dest.split('/')
            lines.append(f'{item["sha256"]} {int(item["mode"], 8):04o} /{dest}')
        (file.parent / 'runtime-files.list').write_text('\n'.join(lines) + '\n')
        identity = profile['crypto_identity']
        assert set(identity) == {'ro.build.version.release', 'ro.build.version.security_patch',
                                 'ro.vendor.build.security_patch'}, identity
        (file.parent / 'crypto.prop').write_text(''.join(f'{k}={v}\n' for k, v in sorted(identity.items())))
        lines, report = module_plan(sample, facts)
        (file.parent / 'modules.plan').write_text('\n'.join(lines) + '\n')
        (file.parent / 'module-sources.json').write_text(json.dumps(report, indent=2) + '\n')
        print(sample, len(lines), 'modules in ordered closure;', len(report['unavailable_optional_softdeps']), 'unavailable softdeps')
    for dest, sha in common.items():
        target = TREE / 'profiles/common/root' / dest
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((TREE / 'prebuilt/common/profile-blobs' / sha).read_bytes())


if __name__ == '__main__':
    main()
