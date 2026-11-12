#!/usr/bin/env python3
"""Compare direct calls made by stock Cirrus probe functions across six OTA ELFs.

This is a relocation/symbol inventory only. It does not execute probe, emulate
kernel services, establish runtime branch order, or claim hardware readiness.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/haptics-emulator-python'))
from elftools.elf.elffile import ELFFile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sample_module(sample):
    module = 'xring_audio_hw_third.ko' if sample.startswith('os4-') else 'xring_smartpa.ko'
    return ROOT / 'firmware/samples' / sample / 'analysis/vendor_dlkm/lib/modules' / module


def inventory(sample, path):
    with path.open('rb') as stream:
        elf = ELFFile(stream)
        symtab = elf.get_section_by_name('.symtab')
        symbols = [s for s in symtab.iter_symbols() if s.name and isinstance(s['st_shndx'], int)]
        by_address = {}
        for symbol in symbols:
            by_address.setdefault((symbol['st_shndx'], symbol['st_value']), []).append(symbol.name)
        probe, = [s for s in symbols if s.name == 'cs40l26_probe']
        direct_calls = []
        for section in elf.iter_sections():
            if section['sh_type'] != 'SHT_RELA' or section['sh_info'] != probe['st_shndx']:
                continue
            for relocation in section.iter_relocations():
                offset = relocation['r_offset']
                if not probe['st_value'] <= offset < probe['st_value'] + probe['st_size']:
                    continue
                if relocation['r_info_type'] not in (282, 283):
                    continue
                symbol = symtab.get_symbol(relocation['r_info_sym'])
                target = symbol['st_value'] + relocation['r_addend']
                if symbol['st_shndx'] == 'SHN_UNDEF':
                    name = symbol.name
                    kind = 'kernel-import'
                else:
                    names = by_address.get((symbol['st_shndx'], target), [])
                    name = next((n for n in names if not n.startswith('$')), '')
                    if not name:
                        containers = [s for s in symbols if s['st_shndx'] == symbol['st_shndx'] and
                                      s['st_value'] <= target < s['st_value'] + max(1, s['st_size'])]
                        name = f'local+0x{target - containers[0]["st_value"]:x}' if containers else f'text+0x{target:x}'
                    kind = 'internal'
                if not direct_calls or direct_calls[-1]['target'] != name:
                    direct_calls.append(dict(offset=offset - probe['st_value'], target=name, kind=kind))
        required = ['cs40l26_probe', 'cs40l26_fw_upload', 'cs40l26_input_init', 'cs40l26_request_irq', 'cs40l26_remove']
        key_symbols = {name: next(s for s in symbols if s.name == name) for name in required}
        call_targets = [call['target'] for call in direct_calls]
        assert all(name in call_targets for name in ['cs40l26_fw_upload', 'cs40l26_input_init', 'cs40l26_request_irq'])
        return dict(sample=sample, module=str(path.relative_to(ROOT)), module_sha256=sha(path),
                    probe_size=probe['st_size'], key_symbols={name: dict(address=s['st_value'], size=s['st_size'])
                                                               for name, s in key_symbols.items()},
                    direct_calls=direct_calls)


def main():
    samples = ['os2-initial', 'os2-final', 'os3-initial', 'os3-final', 'os4-current', 'os4-stable']
    profiles = [inventory(sample, sample_module(sample)) for sample in samples]
    by_sample = {item['sample']: item for item in profiles}
    os23 = by_sample['os2-initial']['direct_calls']
    os3 = by_sample['os3-initial']['direct_calls']
    os4 = by_sample['os4-current']['direct_calls']
    same_plan = lambda sample: by_sample[sample]['direct_calls']
    assert os23 == same_plan('os2-final')
    assert os3 == same_plan('os3-final')
    assert os4 == same_plan('os4-stable')
    def target_list(calls): return [call['target'] for call in calls]
    assert target_list(os23) == target_list(os3)
    assert target_list(os23) != target_list(os4)
    legacy_targets = target_list(os23)
    current_targets = target_list(os4)
    assert 'cs40l26_set_pll_loop' in legacy_targets and 'cs40l26_set_pll_loop' in current_targets
    assert 'regmap_read' in legacy_targets and 'regmap_read' not in current_targets
    assert 'cs40l26_part_num_resolve' not in legacy_targets and 'cs40l26_part_num_resolve' in current_targets
    legacy_selftest = ['cs40l26_upload_effect', 'cs40l26_playback_effect', 'cs40l26_erase_effect']
    assert all(name in legacy_targets for name in legacy_selftest)
    assert not any(name in current_targets for name in legacy_selftest)
    assert 'cs40l26_request_irq' in legacy_targets and 'cs40l26_request_irq' in current_targets
    delta = dict(legacy_only=sorted(set(legacy_targets) - set(current_targets)),
                 os4_only=sorted(set(current_targets) - set(legacy_targets)))
    sources = {item['module']: item['module_sha256'] for item in profiles}
    tests = {'tests/haptics_probe_callgraph.py': sha(Path(__file__))}
    report = dict(status='PASS', scope=__doc__.strip(), profiles=profiles, sources=sources, tests=tests,
                  conclusions=dict(os2_final_equals_initial=True, os3_final_equals_initial=True,
                                   os4_stable_equals_current=True, os2_os3_probe_relocation_sequence_equal=True,
                                   os4_probe_relocation_sequence_differs=True,
                                   os2_os3_to_os4_target_delta=delta,
                                   legacy_probe_direct_selftest_calls=legacy_selftest,
                                   os4_probe_direct_selftest_calls=[],
                                   runtime_execution=False, hardware_result='unverified'))
    out = ROOT / 'logs/haptics-probe-callgraph.json'
    out.write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: six probe relocation inventories; OS2=OS3 ordering, OS4 differs; execution/hardware unverified')


if __name__ == '__main__':
    main()
