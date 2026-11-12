#!/usr/bin/env python3
"""Inspect delivered recovery and stock first-stage inputs, without booting init.

This is a static source/archive audit. It does not execute bootloader ramdisk
merging, init, ueventd or module insertion, and cannot establish actual timing.
"""
import json
from pathlib import Path

from firmware_facts import ROOT, boot_parts, ramdisk_entries, digest


def main():
    image = ROOT/'imgs/built/recovery-dijun-unified-module-state.img'
    entries = {e[0]: e for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
    assert not any(n.startswith('lib/modules/') for n in entries)
    init = entries['system/etc/init/hw/init.rc'][-1].decode()
    assert '/vendor/etc/init/hw/init.O1_asic.rc' not in init
    imports = []
    module_actions = []
    for name, entry in entries.items():
        if not name.endswith('.rc'):
            continue
        for line in entry[-1].decode(errors='strict').splitlines():
            words = line.strip().split()
            if words and words[0] == 'import':
                imports.append(dict(path=name, line=line.strip()))
            if words and (words[0] in ['insmod', 'modprobe'] or 'vendor_dlkm_load' in words):
                module_actions.append(dict(path=name, line=line.strip()))
    assert not module_actions
    source_paths = {
        'init': ROOT.parent/'twrp/system/core/init/first_stage_init.cpp',
        'loader': ROOT.parent/'twrp/bootable/recovery/kernel_module_loader.cpp',
        'runtime': ROOT/'dtsrc/O1_asic_dual/profiles/runtime/dijun-runtime.sh',
    }
    loader = source_paths['loader'].read_text()
    branch = loader[loader.index('if (android::base::GetBoolProperty("ro.twrp.device_profiles"'):loader.index('LOGINFO("Attempting to load modules')]
    assert branch.index('dijun-runtime.sh cache') < branch.index('dijun-runtime.sh modules')
    assert 'return cached == 0;' in branch
    runtime = source_paths['runtime'].read_text()
    assert runtime.index('firmware path unavailable') < runtime.index('modules)') < runtime.index('insmod ')
    cases = []
    for sample in ['os4-current', 'os4-stable']:
        base = ROOT/'firmware/samples'/sample
        vendor_image = base/'vendor_boot.img'
        facts, parts = boot_parts(vendor_image.read_bytes())
        archives = []
        for item in facts['ramdisk_table']:
            index = len(archives)
            archive = ramdisk_entries(parts[f'fragment-{index}'])
            modules = [e[0] for e in archive if e[0].endswith('.ko')]
            touch = [n for n in modules if any(k in Path(n).name for k in ['synaptics', 'xiaomi_touch'])]
            assert not touch
            lists = {e[0]: e[-1].decode() for e in archive if Path(e[0]).name in ['modules.load', 'modules.load.recovery']}
            assert lists and any(n.endswith('modules.load.recovery') for n in lists)
            assert not any('synaptics' in text or 'xiaomi_touch' in text for text in lists.values())
            archives.append(dict(table=item, module_count=len(modules), touch_modules=touch, load_lists=lists))
        stock_init = base/'analysis/vendor/etc/init/hw/init.O1_asic.rc'
        stock_script = base/'analysis/vendor/bin/init.insmod.sh'
        assert 'start vendor_dlkm_load' in stock_init.read_text()
        assert 'service vendor_dlkm_load /vendor/bin/init.insmod.sh' in stock_init.read_text()
        cases.append(dict(sample=sample, status='PASS', vendor_boot_sha256=digest(vendor_image.read_bytes()),
                          archives=archives, stock_second_stage_loader=dict(init=str(stock_init.relative_to(ROOT)),
                          script=str(stock_script.relative_to(ROOT))),
                          stock_second_stage_files={str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in [stock_init, stock_script]}))
    sources = {str(p): digest(p.read_bytes()) for p in [Path(__file__).resolve(), ROOT/'scripts/firmware_facts.py', ROOT/'scripts/acquire_firmware.py', *source_paths.values()]}
    report = dict(status='PASS', scope=__doc__.strip(), image_sha256=digest(image.read_bytes()),
                  sources=sources, cases=cases, recovery_imports=imports, recovery_module_actions=module_actions,
                  conclusion='No Synaptics/Xiaomi touch module in either supplied stock vendor_boot archive; no direct module-load action or stock vendor second-stage init import in delivered recovery RC files. Exact-profile C++ branch orders cache before modules. Actual bootloader merge, init execution, kernel-loaded state and physical timing remain unverified.')
    (ROOT/'logs/touch-load-order-audit.json').write_text(json.dumps(report, indent=2)+'\n')
    print('PASS: two stock vendor_boot archives and current recovery load-order inputs; static inspection only')


if __name__ == '__main__':
    main()
