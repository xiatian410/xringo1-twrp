#!/usr/bin/env python3
"""Report module ELF CRC facts; a module_layout match is not ABI approval.

The former byte-search heuristic could mistake arbitrary kernel/module data
for a version record. Use firmware_facts.py and compare_firmware.py for complete
per-symbol import comparisons and explicit unresolved kernel-export coverage.
Usage: abi_check.py boot.img module_directory [...]
"""
from collections import Counter
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from firmware_facts import boot_parts, elf_module


def main(argv):
    facts, _ = boot_parts(Path(argv[1]).read_bytes())
    print('Kernel release:', facts.get('kernel_release'))
    print('Kernel exported CRC table: not obtained by this command; no compatibility verdict')
    for directory in argv[2:]:
        modules = [elf_module(p.read_bytes()) for p in sorted(Path(directory).rglob('*.ko'))]
        print(json.dumps(dict(directory=directory, modules=len(modules),
            module_layout_crcs=dict(Counter(str(m['module_layout_crc']) for m in modules)),
            versioned_imports=sum(len(m['imports']) for m in modules))))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
