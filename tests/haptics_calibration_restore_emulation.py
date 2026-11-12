#!/usr/bin/env python3
"""Execute stock OS4 calibration restore and file read/write helpers.

Properties, filesystem, libc formatting/hex conversion and logs are explicit
fixtures. No persist data, driver sysfs, DSP or hardware is accessed. Tests
establish original service request semantics, not the cause of silent motors.
"""
import io
import json
import re
import struct
import subprocess
from pathlib import Path

from haptics_driver_emulation import ROOT, DEPS, sha
from haptics_service_request_emulation import SERVICE_SHA
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import (
    UC_ARM64_REG_X0, UC_ARM64_REG_X30, UC_ARM64_REG_PC,
    UC_ARM64_REG_SP, UC_ARM64_REG_TPIDR_EL0,
)

SYS = '/sys/bus/i2c/drivers/xring-smartpa/0-0043'
PERSIST = '/mnt/vendor/persist/haptics/'


def restore(path, disassembly, values, available=True, input_number=4, write_error=False,
            write_callback=None):
    assert sha(path) == SERVICE_SHA
    u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    elf = ELFFile(io.BytesIO(path.read_bytes()))
    for segment in elf.iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            start = segment['p_vaddr'] & ~4095
            length = (segment['p_vaddr'] - start + segment['p_memsz'] + 4095) & ~4095
            u.mem_map(start, length)
            u.mem_write(segment['p_vaddr'], segment.data())
    u.mem_map(0x4000000, 0x10000)
    u.mem_map(0x5000000, 0x20000)
    u.mem_map(0x6000000, 4096)
    u.reg_write(UC_ARM64_REG_TPIDR_EL0, 0x4008000)
    # Explicit resolved stderr pointer, since no dynamic linker is executed.
    u.mem_write(0x30dc0, struct.pack('<Q', 0x4001000))
    u.mem_write(0x4001000, struct.pack('<Q', 0x4002000))
    plt = {int(a, 16): n for a, n in re.findall(
        r'^([0-9a-f]+) <([^>]+)@plt>:', disassembly, re.M)}
    opened, reads, writes, formats = {}, [], [], []

    def text(address):
        data = bytearray()
        for i in range(1024):
            ch = bytes(u.mem_read(address + i, 1))
            if ch == b'\0':
                return data.decode()
            data += ch
        raise AssertionError('unterminated string')

    def hook(uc, address, size, data):
        a = [uc.reg_read(UC_ARM64_REG_X0 + i) for i in range(8)]
        if address == 0x2bd54:
            # Formatting-only boundary: wrapper forwards varargs to libc.
            fmt = text(a[3])
            if fmt == '%s%s%d%s':
                result_text = text(a[4]) + text(a[5]) + str(a[6]) + text(a[7])
            elif fmt == '%s/%s':
                result_text = text(a[4]) + '/' + text(a[5])
            else:
                raise AssertionError(('unknown path format', fmt))
            assert len(result_text.encode()) < a[1]
            uc.mem_write(a[0], result_text.encode() + b'\0')
            formats.append(result_text)
            result = len(result_text)
        elif address == 0x2bc00:
            # Original Cirrus write helper formats its integer as hexadecimal.
            result_text = format(a[3] & 0xffffffff, 'x')
            uc.mem_write(a[0], result_text.encode() + b'\0')
            result = len(result_text)
        elif address not in plt:
            return
        else:
            name = plt[address]
            if name == 'property_get':
                key = text(a[0])
                value = {'ro.odm.mm.vibrator.sys_path': SYS,
                         'ro.odm.mm.vibrator.manufacturer': 'cirrus'}[key]
                uc.mem_write(a[1], value.encode() + b'\0')
                result = len(value)
            elif name == 'access':
                assert text(a[0]) == SYS
                result = 0 if available else -1
            elif name == 'fopen':
                filename, mode = text(a[0]), text(a[1])
                if mode == 'r':
                    if filename in values or filename == SYS + f'/input/input{input_number}/calibration/redc_stored':
                        result = 0x4003000 + 16 * len(opened)
                        opened[result] = (filename, mode)
                    else:
                        result = 0
                else:
                    assert mode == 'w+'
                    result = 0x4003000 + 16 * len(opened)
                    opened[result] = (filename, mode)
            elif name == 'fgets':
                filename, mode = opened[a[2]]
                assert mode == 'r' and filename in values
                value = values[filename].encode()
                assert len(value) < a[1]
                uc.mem_write(a[0], value + b'\0')
                reads.append(filename)
                result = a[0]
            elif name == 'sscanf':
                assert text(a[1]) == '%x'
                value = text(a[0]).strip()
                try:
                    parsed = int(value, 16)
                except ValueError:
                    result = 0
                else:
                    assert 0 <= parsed <= 0xffffffff
                    uc.mem_write(a[2], struct.pack('<I', parsed))
                    result = 1
            elif name == 'fprintf':
                if a[0] in opened and opened[a[0]][1] == 'w+':
                    assert text(a[1]) == '%s\n'
                    writes.append(dict(path=opened[a[0]][0], value=text(a[2]),
                                       result=-1 if write_error else len(text(a[2])) + 1))
                    if write_callback is not None:
                        # Explicit sysfs boundary bridge; callback returns the
                        # driver store result, translated to stdio success/error.
                        store_result = write_callback(writes[-1]['path'], text(a[2]) + '\n')
                        writes[-1]['driver_store_result'] = store_result
                        writes[-1]['result'] = -1 if store_result < 0 else len(text(a[2])) + 1
                    result = writes[-1]['result']
                else:
                    result = 0
            elif name in ['__android_log_print', 'fclose', 'fwrite']:
                result = 0
            else:
                raise AssertionError(('unknown boundary', name, a))
        uc.reg_write(UC_ARM64_REG_X0, result & ((1 << 64) - 1))
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))

    u.hook_add(UC_HOOK_CODE, hook)
    u.reg_write(UC_ARM64_REG_SP, 0x501fff0)
    u.reg_write(UC_ARM64_REG_X30, 0x6000000)
    u.emu_start(0x2bdfc, 0x6000000, count=100000, timeout=2000000)
    assert u.reg_read(UC_ARM64_REG_PC) == 0x6000000, 'restore execution budget exhausted'
    return dict(reads=reads, writes=writes, probed_paths=formats,
                readiness_flag=bytes(u.mem_read(0x34308, 1)).hex())


def main():
    cases, sources = [], {}
    for sample in ['os4-current', 'os4-stable']:
        base = ROOT / 'firmware/samples' / sample / 'analysis'
        service = base / 'odm/bin/hw/vendor.xring.hardware.vibratorfeature.service'
        disassembly = ROOT / 'logs' / (sample + '-vibrator-service.disasm')
        props = base / 'odm/etc/build.prop'
        assert f'ro.odm.mm.vibrator.sys_path={SYS}' in props.read_text()
        assert 'ro.odm.mm.vibrator.manufacturer=cirrus' in props.read_text()
        sources.update({str(p.relative_to(ROOT)): sha(p) for p in [service, props, disassembly]})
        if sample == 'os4-stable':
            driver = base / 'vendor_dlkm/lib/modules/xring_audio_hw_third.ko'
            stores = ROOT / 'logs/os4-stable-haptics-calibration-stores.disasm'
            stores.write_bytes(subprocess.check_output([
                '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump',
                '-dr', '--disassemble-symbols=f0_stored_store,q_stored_store,redc_stored_store',
                str(driver.relative_to(ROOT))], cwd=ROOT))
            sources.update({str(p.relative_to(ROOT)): sha(p) for p in [driver, stores]})
        stock = {PERSIST + 'vib_cal_' + key: value for key, value in
                 [('z', '28000\n'), ('f0', '208000\n'), ('q', 'a000\n')]}
        for label in ['valid-input4', 'valid-input9', 'missing-all', 'missing-f0',
                      'invalid-f0', 'nonpositive-z-q', 'sys-path-absent', 'sysfs-write-failure']:
            values = stock.copy()
            if label == 'missing-all':
                values = {}
            if label == 'missing-f0':
                values.pop(PERSIST + 'vib_cal_f0')
            if label == 'invalid-f0':
                values[PERSIST + 'vib_cal_f0'] = 'garbage\n'
            if label == 'nonpositive-z-q':
                values[PERSIST + 'vib_cal_z'] = '0\n'
                values[PERSIST + 'vib_cal_q'] = 'ffffffff\n'
            result = restore(service, disassembly.read_text(), values,
                             available=label != 'sys-path-absent',
                             input_number=9 if label == 'valid-input9' else 4,
                             write_error=label == 'sysfs-write-failure')
            expected = ['redc_stored', 'f0_stored', 'q_stored']
            if label in ['missing-all', 'sys-path-absent']:
                expected = []
            if label in ['missing-f0', 'invalid-f0']:
                expected.remove('f0_stored')
            if label == 'nonpositive-z-q':
                expected = ['f0_stored']
            assert [Path(w['path']).name for w in result['writes']] == expected, (label, result)
            if label.startswith('valid') or label == 'sysfs-write-failure':
                assert [w['value'] for w in result['writes']] == ['28000', '208000', 'a000']
            assert result['readiness_flag'] == '00'  # caller sets flag, not loader
            cases.append(dict(sample=sample, case=label, status='PASS', **result))
    tests = [Path(__file__).resolve(), ROOT / 'tests/haptics_service_request_emulation.py',
             ROOT / 'tests/haptics_driver_emulation.py']
    dependencies = sorted(p for p in DEPS.rglob('*') if p.is_file() and
                          (p.suffix in ['.py', '.so'] or '.so.' in p.name))
    report = dict(status='PASS', scope=__doc__.strip(), sources=sources,
                  tests={str(p.relative_to(ROOT)): sha(p) for p in tests}, cases=cases)
    report['emulator_files'] = {str(p.relative_to(ROOT)): sha(p) for p in dependencies}
    (ROOT / 'logs/haptics-calibration-restore-emulation.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS:', len(cases), 'stock restore cases; physical calibration/DSP/output unverified')


if __name__ == '__main__':
    main()
