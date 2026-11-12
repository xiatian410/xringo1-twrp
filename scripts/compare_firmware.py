#!/usr/bin/env python3
"""Build an evidence-led compatibility report from firmware_facts.py output.

Compare every versioned import, not just module_layout. No kernel exports are
invented from consumer requirements: unresolved kernel symbols remain explicit.
"""
from collections import defaultdict
from itertools import combinations
import json
from pathlib import Path

from firmware_facts import ROOT, SAMPLES, elf_module, digest


def modules(facts):
    result = {}
    for path, facts_mod in sorted(facts['modules'].items()):
        name = facts_mod['modinfo'].get('name', [Path(path).stem])[0].replace('-', '_')
        item = result.setdefault(name, dict(paths=[], hashes=[], facts={**facts_mod,
            'imports': dict(facts_mod['imports']), 'exports': dict(facts_mod['exports'])}, different_symbol_sets=False))
        item['paths'].append(path)
        item['hashes'].append(facts['files'][path]['sha256'])
        # Firmware duplicates must not be assumed identical based on name alone.
        if (crc_delta(item['facts']['imports'], facts_mod['imports']) or
                crc_delta(item['facts']['exports'], facts_mod['exports'])):
            raise ValueError(f'{facts["sample"]}: conflicting copies of module {name}')
        item['different_symbol_sets'] |= (item['facts']['imports'].keys() != facts_mod['imports'].keys() or
                                          item['facts']['exports'].keys() != facts_mod['exports'].keys())
        # Union for static requirements only. The original per-path facts remain
        # available; this union is never emitted as a loadable module/profile.
        item['facts']['imports'].update(facts_mod['imports'])
        item['facts']['exports'].update(facts_mod['exports'])
    return result


def crc_delta(a, b):
    return {s: [a[s], b[s]] for s in sorted(a.keys() & b.keys()) if a[s] != b[s]}


def module_links(items):
    providers = defaultdict(list)
    for name, item in items.items():
        for symbol, crc in item['facts']['exports'].items():
            providers[symbol].append((name, crc))
    matched = 0
    conflicts = []
    unresolved = set()
    for name, item in items.items():
        for symbol, expected in item['facts']['imports'].items():
            if symbol not in providers:
                unresolved.add(symbol)
            elif any(crc == expected for _, crc in providers[symbol]):
                matched += 1
            else:
                conflicts.append(dict(module=name, symbol=symbol, expected=expected, providers=providers[symbol]))
    return dict(module_imports_with_matching_module_export=matched, conflicts=conflicts,
                unresolved_symbols_count=len(unresolved), unresolved_symbols=sorted(unresolved),
                scope='module-to-module CRC only; kernel exports and load order not proven here')


def main():
    facts = {p.parent.parent.name: json.loads(p.read_text()) for p in sorted(SAMPLES.glob('*/analysis/facts.json'))}
    mods = {name: modules(f) for name, f in facts.items()}
    report = dict(samples={}, comparisons={}, current_tree={}, status='analysis in progress; no unified release yet')
    for name, f in facts.items():
        report['samples'][name] = dict(kernel=f['headers']['boot']['kernel_release'],
            ota_identity=f['ota_identity'], unique_module_count=len(mods[name]),
            duplicate_module_names_with_different_bytes=[k for k, v in mods[name].items() if len(set(v['hashes'])) > 1],
            duplicate_module_names_with_different_symbol_sets=[k for k,v in mods[name].items() if v['different_symbol_sets']],
            module_links=module_links(mods[name]), pending=f['pending'], recovery=f['headers']['recovery'])
    for a, b in combinations(facts, 2):
        common = mods[a].keys() & mods[b].keys()
        changed = {}
        different_import_set = []
        for name in sorted(common):
            am = mods[a][name]['facts']['imports']; bm = mods[b][name]['facts']['imports']
            delta = crc_delta(am, bm)
            if delta:
                changed[name] = delta
            if am.keys() != bm.keys():
                different_import_set.append(name)
        report['comparisons'][a + '--' + b] = dict(common_modules=len(common),
            modules_with_conflicting_import_crcs=changed, different_import_set=different_import_set,
            interpretation='Any CRC conflict rules out blind interchange; absence of conflict does not prove compatibility')
    tree = ROOT / 'dtsrc/O1_asic_dual'
    for gen in ['6.6', '6.18']:
        for p in sorted((tree / 'recovery/root/lib/modules' / gen).glob('*.ko')):
            m = elf_module(p.read_bytes())
            name = m['modinfo'].get('name', [p.stem])[0].replace('-', '_')
            checks = {}
            for sample, source in mods.items():
                if name not in source:
                    checks[sample] = {'status': 'absent from available stock module sets'}
                    continue
                original = source[name]
                delta = crc_delta(m['imports'], original['facts']['imports'])
                checks[sample] = dict(status='conflict' if delta else 'no shared-import CRC conflict',
                    byte_identical=digest(p.read_bytes()) in original['hashes'], conflicts=delta,
                    extra_imports=sorted(m['imports'].keys() - original['facts']['imports'].keys()))
            report['current_tree'][str(p.relative_to(tree))] = checks
    out = ROOT / 'docs'
    out.mkdir(exist_ok=True)
    (out / 'firmware-compatibility.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    rows = ['# 固件兼容性分析（离线阶段）', '',
            '这是固件证据与静态冲突报告，不是单镜像兼容完成声明。'
            '完整导出符号、运行时选择、解密组合及功能模拟尚在补齐。', '',
            '| 样本 | 包内 Android / SDK | 内核 release | 去重模块数 | recovery |',
            '|---|---|---|---:|---|']
    for name, s in report['samples'].items():
        ident = s['ota_identity']; h = s['recovery']
        rows.append(f'| {name} | {ident["post-build"].split(":")[1].split("/")[0]} / {ident["post-sdk-level"]} | '
                    f'`{s["kernel"]}` | {s["unique_module_count"]} | v{h["header_version"]}, kernel={h["kernel_size"]}, {h["image_size"]} B |')
    hashes = {s['recovery']['header_without_ramdisk_size_sha256'] for s in report['samples'].values()}
    rows += ['', f'{len(facts)} 份 recovery 的头页（仅清零 ramdisk 长度后）共 {len(hashes)} 种哈希。'
             '各样本的头格式、内核长度和容量见上表；同一镜像封装仍需逐包验证。', '',
             '| 对比样本 | 共同模块名 | 存在导入 CRC 冲突的模块数 |', '|---|---:|---:|']
    for pair, c in report['comparisons'].items():
        rows.append(f'| {pair} | {c["common_modules"]} | {len(c["modules_with_conflicting_import_crcs"])} |')
    rows += ['', '同为 6.6 并不代表模块可互换。OS2/OS3 的 `module_layout` CRC 相同，'
             '但触摸、USB 或其他厂商符号仍存在版本差异。额外模块必须按精确 profile 选择，不能把 `lib/modules/6.6` 目录当作跨版本兼容依据。', '',
             '以上比较读取 ELF `__versions` / 扩展版本节和 `__crc_*` 符号。'
             '机器报告保留每个冲突的符号名与两个 CRC，并检查原厂模块之间可解析的导入/导出关系。'
             '缺失的内核导出表明确记为 unresolved，不能据此声称全依赖通过。', '',
             '包内身份以每份 `analysis/facts.json` 为准。尤其 OS3 末版下载名与包内 `16OS3.1.260921…` 不同。', '',
             '数据：[机器报告](firmware-compatibility.json)；来源：[获取清单](../firmware-inventory.json)。', '']
    (out / 'firmware-compatibility.md').write_text('\n'.join(rows))
    for sample, s in report['samples'].items():
        print(sample, s['unique_module_count'], 'modules,', len(s['module_links']['conflicts']), 'module-link CRC conflicts,',
              s['module_links']['unresolved_symbols_count'], 'kernel/other exports unresolved')


if __name__ == '__main__':
    main()
