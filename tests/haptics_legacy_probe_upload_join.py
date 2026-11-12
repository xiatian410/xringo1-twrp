#!/usr/bin/env python3
"""Join original OS2/OS3 probe to stock firmware/parameter upload in one context.

DT properties and firmware bytes come from each stock sample. Chip identity,
ROM/algorithm register reads, mailbox acknowledgements, allocation, power/reset,
kernel services and sleeps are explicit fixtures. Writes do not execute DSP code.
Every path deliberately fails before DSP configuration completes. This cannot
establish physical vibration, a successful probe, input registration or playback.
Unknown imports/reads and finite execution-budget exhaustion fail closed.
"""
import inspect
import json
from pathlib import Path
import subprocess

from haptics_firmware_emulation import Firmware, inventory
from haptics_legacy_probe_prefix import LegacyRunthrough, ROOT, CTX, REG
from haptics_coefficients_emulation import table, bin_writes
from haptics_driver_emulation import (DEPS, MASK, sha, UC_ARM64_REG_X0,
                                      UC_ARM64_REG_PC, UC_ARM64_REG_X30)

SAMPLES = ['os2-initial', 'os2-final', 'os3-initial', 'os3-final']
LABELS = ['config-MEM_RDY-error', 'pre-state2-config-MEM_RDY-error',
          'pre-state3-stuck', 'firmware-first-write-error', 'main-bin-missing']


class Joined(Firmware, LegacyRunthrough):
    def __init__(self, path, properties, blobs, label):
        # Start with the original probe's empty context, not a standalone DSP.
        LegacyRunthrough.__init__(self, path, properties)
        self.label = label
        self.raw = []
        self.reads = []
        self.frees = []
        self.read_error = 0
        self.read_failure = 0
        self.raw_failure = 1 if label == 'firmware-first-write-error' else 0
        self.hardware = {0: 0x40a270, 4: 0xb2, **table(blobs['cs40l26.wmfw'])[0]}
        self.rom = []
        self.states = [3, 2 if label == 'pre-state2-config-MEM_RDY-error' else 1]
        if label == 'pre-state3-stuck':
            self.states = [3] * 11
        self.writes = []
        self.updates = []
        self.mailbox = []
        self.sleeps = []
        self.entries = []
        self.releases = []
        self.fwmap = {}
        self.watch = ['cs40l26_probe', 'cs40l26_set_pll_loop',
                      'cs40l26_fw_upload', 'cs40l26_dsp_pre_config',
                      'cs40l26_pm_state_transition', 'cl_dsp_firmware_parse',
                      'cs40l26_coeff_load', 'cl_dsp_coeff_file_parse',
                      'cs40l26_dsp_config', 'cs40l26_input_init', 'cs40l26_remove']
        self.intercept('cs40l26_mailbox_write')
        cursor = 0x40b0000
        for name, blob in sorted(blobs.items()):
            self.put64(cursor, len(blob))
            self.put64(cursor + 8, cursor + 32)
            self.uc.mem_write(cursor + 32, blob)
            self.fwmap[name] = cursor
            cursor += ((len(blob) + 4095) & ~4095) + 4096
        assert cursor < 0x4100000

    def on_code(self, uc, address, size, data):
        for symbol in self.watch:
            if address == self.symbols[symbol]:
                self.entries.append(symbol)
        name = self.hooks.get(address)
        if name is None:
            return
        args = [self.arg(i) for i in range(7)]
        if name == 'regmap_read':
            assert args[0] == REG
            rom_pointer = self.u64(CTX + 0x1b60)
            if rom_pointer and not self.rom:
                self.rom = [self.u32(rom_pointer + 4 * i) for i in range(8)]
                self.hardware.update({self.rom[0]: 1, self.rom[1] + 8: 2,
                                      self.rom[3]: 2, self.rom[2] + 24: 1})
            if self.rom and args[1] == self.rom[0] and self.states:
                self.hardware[args[1]] = self.states.pop(0)
            assert args[1] in self.hardware, ('unknown joined read', hex(args[1]))
            value = self.hardware[args[1]]
            self.put32(args[2], value)
            self.reads.append(dict(address=args[1], value=value, result=0))
            result = 0
        elif name == 'regmap_write':
            assert args[0] == REG
            self.writes.append(dict(address=args[1], value=args[2], result=0))
            result = 0
        elif name == 'regmap_update_bits_base':
            assert args[0] == REG
            assert args[1] in [0x2c04, 0x7404, 0x2900], hex(args[1])
            result = -5 if args[1] == 0x2900 else 0
            self.updates.append(dict(address=args[1], mask=args[2],
                                     value=args[3], result=result))
        elif name == 'cs40l26_mailbox_write':
            self.mailbox.append(dict(command=args[1], result=0))
            result = 0
        elif name == 'usleep_range_state':
            self.sleeps.append(args[:3])
            result = 0
        elif name in ['kvmalloc_node', '__kmalloc', 'kmalloc_trace']:
            length = args[2] if name == 'kmalloc_trace' else args[0]
            assert 0 < length <= 0x20000
            result = self.alloc_cursor
            self.alloc_cursor += (length + 15) & ~15
            assert self.alloc_cursor < 0x4200000
            self.allocations.append(dict(address=result, length=length, api=name))
        elif name == 'request_firmware':
            filename = self.string(args[1])
            assert filename in self.fwmap, filename
            self.firmware_requests.append(filename)
            missing = self.label == 'main-bin-missing' and filename == 'cs40l26.bin'
            self.put64(args[0], 0 if missing else self.fwmap[filename])
            result = -2 if missing else 0
        elif name == 'release_firmware':
            self.releases.append(args[0])
            result = 0
        elif name in ['_dev_err', '_dev_warn']:
            self.messages.append(self.string(args[1]))
            result = 0
        else:
            return super().on_code(uc, address, size, data)
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0, result & MASK)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))


def exercise(sample, dt):
    base = ROOT / 'firmware/samples' / sample / 'analysis'
    driver = base / 'vendor_dlkm/lib/modules/xring_smartpa.ko'
    files = sorted((base / 'odm/firmware').glob('cs40l26*'))
    blobs = {path.name: path.read_bytes() for path in files}
    properties = next(case for case in dt['cases'] if case['sample'] == sample and
                      case['case'] == 'overlay-5')['haptics'][
                          '/soc/i2c@EC100000/cs40l26@43']['properties']
    cases = []
    firmware_writes = inventory(blobs['cs40l26.wmfw'])['writes']
    rows = table(blobs['cs40l26.wmfw'])[1]
    expected_names = ['cs40l26.wmfw', 'cs40l26.bin', 'cs40l26-svc.bin',
                      'cs40l26-dvl.bin', 'cs40l26-a2h.bin', 'cs40l26-dbc.bin']
    for label in LABELS:
        m = Joined(driver, properties, blobs, label)
        result = m.run_probe()
        expected_result = -22 if label == 'pre-state3-stuck' else -5
        assert result == expected_result, (sample, label, result, m.messages)
        assert m.entries[0] == 'cs40l26_probe'
        assert 'cs40l26_set_pll_loop' in m.entries
        assert 'cs40l26_fw_upload' in m.entries
        assert 'cs40l26_input_init' not in m.entries
        assert m.entries.count('cs40l26_remove') == 1
        assert m.symbols['cs40l26_remove'] not in m.hooks
        assert m.mailbox == [dict(command=0x02000003, result=0)]
        assert bytes(m.uc.mem_read(CTX + 0x222, 1)) == b'\0'
        states = [r['value'] for r in m.reads if r['address'] == m.rom[0]]
        assert states == ([3] * 11 if label == 'pre-state3-stuck' else
                          [3, 2 if label == 'pre-state2-config-MEM_RDY-error' else 1])
        assert m.updates[:2] == [dict(address=0x2c04, mask=0x800, value=0x800, result=0),
                                dict(address=0x7404, mask=0x10000000, value=0x10000000, result=0)]
        if label == 'pre-state3-stuck':
            assert m.firmware_requests == ['cs40l26.wmfw'] and not m.releases
            assert not m.raw and 'cl_dsp_firmware_parse' not in m.entries
            assert len([r for r in m.reads if r['address'] == m.rom[0]]) == 11
        elif label == 'firmware-first-write-error':
            assert m.raw == firmware_writes[:1]
            assert m.firmware_requests == ['cs40l26.wmfw']
            assert m.releases == [m.fwmap['cs40l26.wmfw']]
            assert 'cs40l26_coeff_load' not in m.entries
        else:
            assert m.firmware_requests == expected_names, (sample, label, m.firmware_requests)
            expected_writes = list(firmware_writes)
            for name in expected_names[1:]:
                if label == 'main-bin-missing' and name == 'cs40l26.bin':
                    continue
                expected_writes.extend(bin_writes(blobs[name], rows))
            assert m.raw == expected_writes, (sample, label, len(m.raw), len(expected_writes))
            assert m.releases == [m.fwmap[name] for name in expected_names if not
                                 (label == 'main-bin-missing' and name == 'cs40l26.bin')]
            assert 'cs40l26_dsp_config' in m.entries
            assert m.updates[-1] == dict(address=0x2900, mask=2, value=2, result=-5)
        assert m.calls[-1] == 'debugfs_remove'
        cases.append(dict(sample=sample, case=label, status='PASS', result=result,
                          requests=m.firmware_requests, releases=m.releases,
                          raw_writes=m.raw, reads=m.reads, writes=m.writes,
                          updates=m.updates, mailbox=m.mailbox, sleeps=m.sleeps,
                          entries=m.entries, messages=m.messages, fw_loaded=0,
                          teardown=m.calls[-10:], rom=m.rom,
                          remove_body='original instructions; kernel teardown services are fixtures',
                          no_input_registration=True, no_dsp_execution=True))
        print(sample, label, result, 'raw', len(m.raw), flush=True)
    objdump = '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump'
    disasm = ROOT / 'logs' / f'{sample}-haptics-legacy-probe-upload.disasm'
    disasm.write_bytes(subprocess.check_output([
        objdump, '-dr', '--disassemble-symbols=' + ','.join(m.watch), str(driver)]))
    return cases, {str(path.relative_to(ROOT)): sha(path) for path in files + [driver, disasm]}


def main():
    dt_path = ROOT / 'logs/haptics-devicetree-audit.json'
    dt = json.loads(dt_path.read_text())
    cases, sources = [], {str(dt_path.relative_to(ROOT)): sha(dt_path)}
    for sample in SAMPLES:
        current, fingerprints = exercise(sample, dt)
        cases.extend(current)
        sources.update(fingerprints)
    tests = {}
    for cls in Joined.mro():
        if cls is object:
            continue
        path = Path(inspect.getfile(cls)).resolve()
        tests[str(path.relative_to(ROOT))] = sha(path)
    for name in ['tests/haptics_coefficients_emulation.py', 'tests/haptics_upload_emulation.py',
                 'scripts/firmware_facts.py', 'tests/haptics-emulator-dependencies.json']:
        tests[name] = sha(ROOT / name)
    report = dict(status='PASS', scope=__doc__, count=len(cases), cases=cases,
                  sources=sources, tests=tests, hardware_result='unverified',
                  emulator_files={str(path.relative_to(ROOT)): sha(path) for path in
                                  DEPS.rglob('*') if path.is_file() and
                                  (path.suffix in ['.py', '.so'] or '.so.' in path.name)})
    (ROOT / 'logs/haptics-legacy-probe-upload-join.json').write_text(
        json.dumps(report, indent=2) + '\n')
    print('PASS', len(cases), 'legacy probe-to-upload joins; no physical output result')


if __name__ == '__main__':
    main()
