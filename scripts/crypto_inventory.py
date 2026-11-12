#!/usr/bin/env python3
"""Compare matched MiTEE userspace candidates against the built recovery ABI.

This only reads ELF/props/init/TA files. It neither stages a runtime profile nor
claims a TEE operation succeeded. Firmware facts keep system/vendor identities
separate; the proposed identity must later be tested by the profile machinery.
"""
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from firmware_facts import ROOT, SAMPLES, digest
from stage_mitee import elf

RUNTIME = Path('/root/AAA/twrp/out/target/product/O1_asic/recovery/root')
BINARIES = ['bin/tee-supplicant',
            'bin/hw/android.hardware.security.keymint@3.0-service.mitee',
            'bin/hw/android.hardware.gatekeeper-service.mitee']
inspect = lru_cache(maxsize=None)(elf)


def file_info(path):
    return dict(path=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                sha256=digest(path.read_bytes()), size=path.stat().st_size)


def candidate(sample, facts):
    vendor = SAMPLES / sample / 'analysis/vendor'
    missing_bins = [p for p in BINARIES if not (vendor / p).is_file()]
    if missing_bins:
        return dict(status='pending vendor extraction or different service names', missing_binaries=missing_bins)
    chosen = {}
    pending = set()
    queue = [vendor / p for p in BINARIES]
    visited = set()
    while queue:
        p = queue.pop()
        if p in visited:
            continue
        visited.add(p)
        for dep in inspect(p)[0]:
            if dep in chosen:
                continue
            v = vendor / 'lib64' / dep
            r = RUNTIME / 'system/lib64' / dep
            if dep in ['libbinder.so', 'libbinder_ndk.so'] and r.is_file():
                provider = r  # preserve the paired Binder runtime of this recovery
            elif v.is_file() and not v.is_symlink():
                provider = v
            elif r.is_file():
                provider = r
            else:
                pending.add((str(p), dep))
                continue
            chosen[dep] = provider
            queue.append(provider)
    checks = {}
    for binary in BINARIES:
        queue = [vendor / binary]
        seen, definitions, refs = set(), set(), set()
        while queue:
            p = queue.pop()
            if p in seen:
                continue
            seen.add(p)
            needed, defs, undefined = inspect(p)
            definitions |= defs
            refs |= undefined
            queue.extend(chosen[name] for name in needed if name in chosen)
        checks[binary] = dict(elfs=len(seen), unresolved_strong_symbols=sorted(refs - definitions))
    vendor_props = {k: v for p, props in facts['properties'].items() if p in ['vendor/build.prop', 'vendor/etc/build.prop'] for k, v in props.items()}
    system_release = facts['ota_identity']['post-build'].split(':')[1].split('/')[0]
    identity = {
        'ro.build.version.release': system_release,
        'ro.build.version.security_patch': facts['ota_identity']['post-security-patch-level'],
        'ro.vendor.build.security_patch': vendor_props.get('ro.vendor.build.security_patch'),
    }
    system_evidence = None
    system_report = SAMPLES / sample / 'analysis/system-resources.json'
    if system_report.exists():
        system = json.loads(system_report.read_text())['partitions'].get('system')
        if system:
            properties = system['properties']['system/build.prop']
            resource = system['resources']['system/build.prop']
            source = ROOT / resource['extracted']
            if digest(source.read_bytes()) != resource['sha256']:
                raise ValueError(f'{sample}: changed system identity evidence')
            for key in ['ro.build.version.release', 'ro.build.version.security_patch']:
                if properties.get(key) != identity[key]:
                    raise ValueError(f'{sample}: OTA/system identity conflict for {key}')
                identity[key] = properties[key]
            system_evidence = dict(properties=properties, source=resource)
    assets = {f'vendor/{p}': file_info(vendor / p) for p in BINARIES}
    for p in sorted((vendor / 'mitee/ta').glob('*.ta')):
        assets[f'vendor/mitee/ta/{p.name}'] = file_info(p)
    for p in sorted((vendor / 'etc/vintf/manifest').glob('*mitee*')):
        assets[f'vendor/etc/vintf/manifest/{p.name}'] = file_info(p)
    private = {name: file_info(p) for name, p in sorted(chosen.items()) if p.is_relative_to(vendor)}
    shared = {name: file_info(p) for name, p in sorted(chosen.items()) if not p.is_relative_to(vendor)}
    status = 'S1 dependency/symbol checks passed' if not pending and all(not v['unresolved_strong_symbols'] for v in checks.values()) else 'static dependency conflicts'
    return dict(status=status, kernel=facts['headers']['boot']['kernel_release'],
                observed_system_identity=facts['ota_identity'], system_file_evidence=system_evidence,
                observed_vendor_identity=vendor_props,
                proposed_crypto_identity=identity, assets=assets, private_dsos=private, recovery_dsos=shared,
                missing_needed=sorted(pending), checks=checks,
                limitations=['This inventory does not validate activation; see separate runtime/image reports', 'Actual ARM64 linker namespace execution remains unverified',
                             'TEE/key upgrade/hardware-key success is unverified', 'Selection must use observed system AND vendor identities'])


def main():
    profiles = {}
    for p in sorted(SAMPLES.glob('*/analysis/facts.json')):
        facts = json.loads(p.read_text())
        profiles[facts['sample']] = candidate(facts['sample'], facts)
    all_files = [v for d in profiles.values() for group in ['assets', 'private_dsos'] for v in d.get(group, {}).values()]
    dedup = {v['sha256']: v['size'] for v in all_files}
    report = dict(profiles=profiles, size_budget=dict(raw_sum=sum(v['size'] for v in all_files),
                    unique_content_sum=sum(dedup.values()), unique_blobs=len(dedup),
                    scope='Userspace assets/private DSOs only; no module/ramdisk compression or image fit claim'))
    (ROOT / 'docs/crypto-compatibility.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    for sample, d in profiles.items():
        print(sample, d['status'], 'private DSOs', len(d.get('private_dsos', {})), 'identity', d.get('proposed_crypto_identity'))
    print('Raw/deduplicated byte counts:', report['size_budget'])


if __name__ == '__main__':
    main()
