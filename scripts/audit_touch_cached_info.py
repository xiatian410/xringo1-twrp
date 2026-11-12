#!/usr/bin/env python3
"""Inspect original OS4 cached info callbacks before adding them to collection."""
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/haptics-emulator-python'))
from elftools.elf.elffile import ELFFile

OBJDUMP = '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    cases = []
    for sample in ['os4-current', 'os4-stable']:
        path = ROOT/f'firmware/samples/{sample}/analysis/vendor_dlkm/lib/modules/synaptics_tcm2.ko'
        data = path.read_bytes()
        elf = ELFFile(io.BytesIO(data))
        symtab = elf.get_section_by_name('.symtab')
        symbols = {s.name: s for s in symtab.iter_symbols()}
        attr, info = symbols['kobj_attr_info'], symbols['syna_sysfs_info_show']
        relocs = list(elf.get_section_by_name('.rela.data').iter_relocations())
        name = next(r for r in relocs if r['r_offset'] == attr['st_value'])
        name_symbol = symtab.get_symbol(name['r_info_sym'])
        ro = elf.get_section(name_symbol['st_shndx']).data()
        off = name_symbol['st_value'] + name['r_addend']
        assert ro[off:ro.find(b'\0', off)] == b'info'
        show = next(r for r in relocs if r['r_offset'] == attr['st_value'] + 16)
        show_symbol = symtab.get_symbol(show['r_info_sym'])
        assert show_symbol['st_value'] + show['r_addend'] == info['st_value']
        attr_bytes = elf.get_section(attr['st_shndx']).data()[attr['st_value']:attr['st_value']+32]
        assert int.from_bytes(attr_bytes[8:10], 'little') == 0o444
        assert attr_bytes[24:32] == bytes(8)  # no store callback
        calls = {}
        for function in ['syna_sysfs_info_show', 'syna_pal_mem_cpy']:
            disasm = subprocess.check_output([OBJDUMP, '-dr', '--disassemble-symbols='+function,
                                             str(path)], text=True)
            assert not re.search(r'\b(?:blr|br)\s+x\d+', disasm), 'unexpected indirect branch'
            targets = re.findall(r'\b(?:bl|b)\s+(?:0x)?[0-9a-f]+ <([^>]+)>', disasm)
            external = {target for target in targets if not target.startswith(function+'+')}
            # External imports are unresolved self-address branches plus relocation
            # records; same-section local calls may already have resolved offsets.
            imports = set(re.findall(r'R_AARCH64_(?:CALL26|JUMP26)\s+(\S+)', disasm))
            allowed = {'snprintf', '_printk', 'syna_pal_mem_cpy'} if function.endswith('info_show') else {'_printk'}
            assert external <= allowed, external
            assert imports <= allowed, imports
            if function.endswith('info_show'):
                assert 'syna_pal_mem_cpy' in external
            calls[function] = {'resolved_calls': sorted(external), 'imports': sorted(imports)}
        output = ROOT/f'logs/{sample}-touch-cached-info.disasm'
        output.write_bytes(subprocess.check_output([OBJDUMP, '-dr',
            '--disassemble-symbols=syna_sysfs_info_show,syna_pal_mem_cpy,syna_sysfs_create_dir', str(path)]))
        cases.append({'sample': sample, 'module': str(path.relative_to(ROOT)),
                      'module_sha256': sha(data), 'attribute': 'info', 'mode': '0444',
                      'calls': calls, 'disassembly': str(output.relative_to(ROOT)),
                      'disassembly_sha256': sha(output.read_bytes())})
    report = {'status': 'PASS', 'scope': 'Static attribute and disassembly inspection of two original OS4 modules. '
              'No sysfs execution, controller query, state synchronization or hardware readiness proof.',
              'sources': {str(Path(__file__).relative_to(ROOT)): sha(Path(__file__).read_bytes())},
              'count': len(cases), 'cases': cases}
    (ROOT/'logs/touch-cached-info-audit.json').write_text(json.dumps(report, indent=2)+'\n')
    print('PASS: cached info callbacks contain formatting/memory-copy/logging calls only')


if __name__ == '__main__':
    main()
