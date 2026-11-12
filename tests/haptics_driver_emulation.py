#!/usr/bin/env python3
"""Execute stock ARM64 Cirrus effect code with captured production FF bytes.

Kernel services, initialized device memory and DSP register access are fixtures.
This is function emulation, not a booted kernel, probe, I2C or motor test.
Unknown imports/instructions and instruction-budget exhaustion fail closed.
"""
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / 'tools/haptics-emulator-python'
sys.path.insert(0, str(DEPS))
sys.path.insert(0, str(ROOT / 'scripts'))
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X30, UC_ARM64_REG_SP, UC_ARM64_REG_PC, UC_ARM64_REG_SP_EL0
from elftools.elf.elffile import ELFFile
from firmware_facts import haptics_module

SOURCE = Path('/root/AAA/twrp/bootable/recovery/twrpminui/force_feedback.cpp')
# Struct fixture layouts are established by disassembly of these exact ELF files.
# A new driver must be analyzed before it can reuse either fixture layout.
LAYOUTS = {
    '7e566e67798d2730fa79dd22899507a6802413f59270105c375efcade1e39a17': 'legacy',
    '0d4b140193c5d45f73a09b83006fffb69ff1a040e4d4063677498a898ee89fe8': 'legacy',
    'c58bfc852d4bbfd2a8d180893005c6b0fa3e3c6fdd94857cf5802951dea5cb38': 'legacy',
    'bca5f8c4f34b721d1a5804393311cfd9b52243183ae1a5342db12a00cadb57de': 'legacy',
    '969a17203bf56c3d5b46e3a3ee1827cb3579aaa423c2fc21508e73d2548650f6': 'modern',
}
MASK = (1 << 64) - 1
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def align(n): return (n + 4095) & ~4095


class Module:
    """Relocate original SHF_ALLOC bytes into a private Unicorn address space."""
    def __init__(self, path):
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.elf = ELFFile(io.BytesIO(path.read_bytes()))
        self.sections = list(self.elf.iter_sections())
        self.bases = {}
        cursor = 0x1000000
        for index, section in enumerate(self.sections):
            if section['sh_flags'] & 2 and section['sh_size']:
                self.bases[index] = cursor
                self.uc.mem_map(cursor, align(section['sh_size']))
                if section['sh_type'] != 'SHT_NOBITS':
                    self.uc.mem_write(cursor, section.data())
                cursor += align(section['sh_size']) + 4096
        self.symtab = self.elf.get_section_by_name('.symtab')
        self.symbols = {s.name: self.bases[s['st_shndx']] + s['st_value']
                        for s in self.symtab.iter_symbols()
                        if isinstance(s['st_shndx'], int) and s['st_shndx'] in self.bases and s.name}
        self.externals = {}
        self.uc.mem_map(0x3000000, 0x10000)
        self.hooks = {}
        for section in self.sections:
            if section['sh_type'] != 'SHT_RELA' or section['sh_info'] not in self.bases:
                continue
            for r in section.iter_relocations():
                symbol = self.symtab.get_symbol(r['r_info_sym'])
                idx = symbol['st_shndx']
                if idx == 'SHN_UNDEF':
                    if symbol.name not in self.externals:
                        self.externals[symbol.name] = 0x3000000 + 16 * len(self.externals)
                    value = self.externals[symbol.name]
                elif idx == 'SHN_ABS': value = symbol['st_value']
                else: value = self.bases[idx] + symbol['st_value']
                target = value + r['r_addend']
                address = self.bases[section['sh_info']] + r['r_offset']
                kind = r['r_info_type']
                word = self.u32(address)
                if kind == 257: self.put64(address, target)
                elif kind == 260: self.put64(address, target - address)
                elif kind == 261: self.put32(address, target - address)
                elif kind in (283, 282):
                    delta = target - address
                    assert delta % 4 == 0 and -(1 << 27) <= delta < (1 << 27)
                    self.put32(address, (word & 0xfc000000) | ((delta >> 2) & 0x3ffffff))
                elif kind == 275:
                    delta = (target >> 12) - (address >> 12)
                    assert -(1 << 20) <= delta < (1 << 20)
                    self.put32(address, (word & ~0x60ffffe0) | ((delta & 3) << 29) | (((delta >> 2) & 0x7ffff) << 5))
                elif kind in (277, 278, 284, 285, 286):
                    scale = {277: 0, 278: 0, 284: 1, 285: 2, 286: 3}[kind]
                    assert (target & ((1 << scale) - 1)) == 0
                    self.put32(address, (word & ~0x3ffc00) | (((target & 4095) >> scale) << 10))
                else: raise AssertionError(('unsupported relocation', kind))
        self.uc.mem_map(0x4000000, 0x200000)
        self.uc.mem_map(0x5000000, 0x20000)
        self.uc.mem_map(0x6000000, 0x1000)
        self.uc.reg_write(UC_ARM64_REG_SP_EL0, 0x5000000)
        self.alloc_cursor = 0x4100000
        self.calls = []
        self.registers = []
        self.messages = []
        self.fail_register = 0
        self.return_address = 0x6000000
        self.uc.hook_add(UC_HOOK_CODE, self.on_code)
        for name, address in self.externals.items():
            self.hooks[address] = name

    def u32(self, a): return struct.unpack('<I', self.uc.mem_read(a, 4))[0]
    def u64(self, a): return struct.unpack('<Q', self.uc.mem_read(a, 8))[0]
    def put32(self, a, v): self.uc.mem_write(a, struct.pack('<I', v & 0xffffffff))
    def put64(self, a, v): self.uc.mem_write(a, struct.pack('<Q', v & MASK))
    def string(self, a):
        return bytes(self.uc.mem_read(a, 128)).split(b'\0')[0].decode()
    def arg(self, i): return self.uc.reg_read(UC_ARM64_REG_X0 + i)
    def intercept(self, name): self.hooks[self.symbols[name]] = name
    def on_code(self, uc, address, size, _):
        if address not in self.hooks: return
        name = self.hooks[address]
        args = [self.arg(i) for i in range(5)]
        self.calls.append(name)
        if name in ('_dev_printk', '_dev_err', 'mutex_lock', 'mutex_unlock', 'kfree', 'devm_kfree', '__pm_runtime_suspend'):
            if name == '_dev_err': self.messages.append(self.string(args[1]))
            result = 0
        elif name == 'cs40l26_pm_enter': result = 0
        elif name == 'ktime_get_mono_fast_ns': result = 123456789
        elif name in ('devm_kmalloc', '__kmalloc', '__kmalloc_noprof'):
            result = self.alloc_cursor
            self.alloc_cursor += align(args[1] if name == 'devm_kmalloc' else args[0])
            assert self.alloc_cursor < 0x4200000
        elif name == 'cl_dsp_get_reg':
            reg = 0x1000 + 4 * len(self.registers)
            self.pending_name = self.string(args[1])
            self.put32(args[4], reg)
            result = 0
        elif name == 'cl_dsp_get_coeff':
            self.pending_name = self.string(args[1])
            result = self.alloc_cursor
            self.alloc_cursor += 4096
            self.put32(result+0x34, 0x1000 + 4 * len(self.registers))
        elif name == 'regmap_write':
            self.registers.append(dict(name=self.pending_name, register=args[1], value=args[2]))
            result = -5 if self.fail_register == len(self.registers) else 0
        elif name == 'queue_work_on':
            self.queue = args
            result = 1
        else: raise AssertionError(('unhandled kernel boundary', name, args))
        uc.reg_write(UC_ARM64_REG_X0, result & MASK)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))

    def run(self, name, *args):
        for i, v in enumerate(args): self.uc.reg_write(UC_ARM64_REG_X0 + i, v & MASK)
        self.uc.reg_write(UC_ARM64_REG_SP, 0x5020000 - 16)
        self.uc.reg_write(UC_ARM64_REG_X30, self.return_address)
        self.uc.emu_start(self.symbols[name], self.return_address, timeout=2000000, count=100000)
        assert self.uc.reg_read(UC_ARM64_REG_PC) == self.return_address, ('emulation budget', name)
        result = self.arg(0) & 0xffffffff
        return result if result < (1 << 31) else result - (1 << 32)


def upload(m, effect):
    ctx, eff, record = 0x4000000, 0x4010000, 0x4020000
    m.uc.mem_write(eff, effect)
    if 'cs40l26_sine_upload' in m.symbols:
        m.intercept('cl_dsp_get_reg')
        rc = m.run('cs40l26_sine_upload', ctx, eff, record)
    else:
        m.intercept('cs40l26_pm_enter')
        m.intercept('cl_dsp_get_coeff')
        m.put64(ctx, 0x4060000)
        m.put64(ctx+0x60, ctx+0x60)
        m.put64(ctx+0x68, ctx+0x60)
        m.uc.mem_write(ctx+0x80, effect)
        m.run('cs40l26_upload_worker', ctx+0x158)
        rc = m.u32(ctx+0x250)
        if rc >= (1 << 31): rc -= 1 << 32
    return rc


def capture(temp):
    input_dir = temp / 'input'
    input_dir.mkdir()
    (input_dir / 'event4').touch()
    (temp / 'cutils').mkdir()
    (temp / 'cutils/properties.h').write_text('#include <stdint.h>\nextern "C" int32_t property_get_int32(const char*,int32_t);\n')
    (temp / 'common.h').write_text('#define LOGI(...) fprintf(stderr,__VA_ARGS__)\n#define LOGE(...) fprintf(stderr,__VA_ARGS__)\n')
    (temp / 'twcommon.h').touch()
    source = temp / 'force_feedback.cpp'
    source.write_text(SOURCE.read_text().replace('/dev/input', str(input_dir)))
    subprocess.run(['g++', '-std=c++17', '-pthread', '-fsanitize=undefined', '-fno-sanitize-recover=all',
                    '-I'+str(temp), '-I'+str(SOURCE.parent), '-DFIXTURE_INPUT="'+str(input_dir)+'"',
                    str(source), str(ROOT/'tests/haptics_driver_capture.cpp'),
                    '-Wl,--wrap=open', '-Wl,--wrap=ioctl', '-Wl,--wrap=write', '-o', str(temp/'capture')], check=True)
    fixtures = []
    for length in (1, 40, 80, 160, 300, 500, 10000, 20000):
        stem = temp / str(length)
        subprocess.run([str(temp/'capture'), str(stem), str(length)], check=True, capture_output=True)
        effect = stem.with_suffix('.effect').read_bytes()
        event = stem.with_suffix('.event').read_bytes()
        assert len(effect) == 48 and len(event) == 24
        fixtures.append((length, effect, event))
    return fixtures


def main():
    results = []
    drivers = {}
    assert (DEPS/'dependencies.json').read_bytes() == (ROOT/'tests/haptics-emulator-dependencies.json').read_bytes()
    with tempfile.TemporaryDirectory(prefix='dijun-ff-driver-') as temporary:
        fixtures = capture(Path(temporary))
        for profile in sorted((ROOT/'dtsrc/O1_asic_dual/profiles').glob('*/profile.json')):
            sample = profile.parent.name
            analysis = ROOT/'firmware/samples'/sample/'analysis'
            module_path, _ = haptics_module(json.loads((analysis/'facts.json').read_text()))
            path = analysis/module_path
            assert sha(path) in LAYOUTS, ('unanalyzed driver layout', sample)
            drivers[sample] = dict(path=str(path.relative_to(ROOT)), sha256=sha(path))
            for length, effect, event in fixtures:
                m = Module(path)
                ctx, eff, record, inp, ff, effects = (0x4000000, 0x4010000, 0x4020000, 0x4030000, 0x4040000, 0x4050000)
                modern = LAYOUTS[sha(path)] == 'modern'
                assert modern == ('cs40l26_sine_upload' in m.symbols)
                rc = upload(m, effect)
                assert rc == 0, (sample, length, rc, m.calls, m.messages)
                if modern:
                    assert m.u32(record) == 7 and m.u32(record+4) == 0x1800081
                values = [r['value'] for r in m.registers]
                assert values == [(min(length, 10000)+3)//4, 125, 64], (sample, length, m.registers)
                results.append(dict(sample=sample, case=f'production-{length}ms', status='PASS', registers=m.registers))
                m.put64(inp+(0x2c0 if modern else 0x2d8), ctx)
                m.put64(inp+0xf8, ff)
                m.put64(ff+(0x78 if modern else 0x80), effects)
                m.uc.mem_write(effects+48*7, effect)
                typ, code, val = struct.unpack_from('<HHi', event, 16)
                assert (typ, code, val) == (21, 7, 1)
                assert m.run('cs40l26_playback_effect', inp, code, val) == 0
                assert m.queue[2] == ctx+(0xc0 if modern else 0xc8)
                assert m.u64(ctx+(0x70 if modern else 0x78)) == effects+48*7
                results.append(dict(sample=sample, case=f'playback-{length}ms', status='PASS'))
            effect = fixtures[2][1]
            for failure in (1, 2, 3):
                m = Module(path)
                m.fail_register = failure
                assert upload(m, effect) == -5, (sample, failure, m.calls)
                assert len(m.registers) == failure
                results.append(dict(sample=sample, case=f'regmap-error-{failure}', status='PASS'))
            m = Module(path)
            data_index = next(i for i, s in enumerate(m.sections) if s.name == '.data')
            slot_base = m.bases[data_index] + (0x3960 if modern else 0xbe8)
            for slot in range(5): m.put32(slot_base+32*slot+24, 100+slot)
            assert upload(m, effect) == -28, (sample, m.calls, m.messages)
            assert not m.registers
            results.append(dict(sample=sample, case='slots-exhausted', status='PASS'))
            drivers[sample]['layout'] = LAYOUTS[sha(path)]
            drivers[sample]['functions'] = {name: hex(m.symbols[name]) for name in
                ['cs40l26_upload_worker', 'cs40l26_playback_effect', 'cs40l26_sine_upload'] if name in m.symbols}
            print('PASS', sample, flush=True)
    report = dict(status='PASS', scope=__doc__.strip(), cases=results, drivers=drivers,
                  sources={str(p): sha(p) for p in [SOURCE, SOURCE.with_suffix('.h')]},
                  tests={str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__), ROOT/'tests/haptics_driver_capture.cpp', ROOT/'scripts/firmware_facts.py', ROOT/'scripts/setup_haptics_emulator.py', ROOT/'tests/haptics-emulator-dependencies.json']},
                  dependencies=json.loads((DEPS/'dependencies.json').read_text()),
                  fixture_bytes=[dict(requested_ms=n, effect_hex=e.hex(), event_hex=v.hex()) for n,e,v in fixtures],
                  emulator_files={str(p.relative_to(ROOT)): sha(p) for p in sorted(DEPS.rglob('*'))
                      if p.is_file() and p.suffix in ('.py', '.so')})
    (ROOT/'logs/haptics-driver-emulation.json').write_text(json.dumps(report, indent=2)+'\n')
    print('PASS', len(results), 'cases')


if __name__ == '__main__': main()
