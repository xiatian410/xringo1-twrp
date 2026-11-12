#!/usr/bin/env python3
"""Capture stock OS4 Cirrus long-on FF requests and compare Recovery requests.

Executes a hash-pinned service function with explicit Cirrus/open-FD/route-ready
state and XML-derived long_vib_id. Binder, constructor, XML parser, audio/PCM,
calibration, timer/callback thread and device discovery do not execute. PLT
logging/MiEvent/ioctl/write are explicit fixtures. Captured CUSTOM data enters
the original driver upload worker at its post-user-copy boundary. RAM wave
counts and kernel/PM/register/mailbox services are fixtures, not DSP execution
or evidence that a physical waveform exists or that either route vibrates.
"""
import io
import json
import re
import struct
import subprocess
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET

from haptics_playback_emulation import Playback, CTX, INPUT
from haptics_driver_emulation import ROOT, DEPS, SOURCE, sha, capture
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import UC_ARM64_REG_SP, UC_ARM64_REG_TPIDR_EL0

SERVICE_SHA = '0eacb88e11a3402b1551b79cc85e3cfcbbd518c7da44684fc5354829e27be2e7'


def service_request(path, disassembly, long_id, duration):
    assert sha(path) == SERVICE_SHA
    elf = ELFFile(io.BytesIO(path.read_bytes()))
    u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
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
    # Function 0x119b4 receives the FF helper embedded at vibrator+0x50.
    u.mem_write(0x4000004, b'\1')  # Cirrus mode, not generic amplitude scaling.
    u.mem_write(0x4000008, struct.pack('<ihh', 9, -1, 32767))
    u.mem_write(0x3402c, struct.pack('<I', long_id))
    u.mem_write(0x34308, b'\1')  # Route initialization already done; explicit boundary.
    plt = {int(a, 16): n for a, n in re.findall(
        r'^([0-9a-f]+) <([^>]+)@plt>:', disassembly, re.M)}
    operations = []

    def hook(uc, address, size, data):
        if address not in plt:
            return
        name = plt[address]
        a = [uc.reg_read(UC_ARM64_REG_X0 + i) for i in range(4)]
        if name in ['__android_log_print', '_ZN7android7MiEventC1Ej', '_ZN7android7MiEventD1Ev']:
            result = 0
        elif name == 'write':
            assert a[0] == 9 and a[2] == 24
            operations.append(dict(call='write', data=bytes(uc.mem_read(a[1], a[2])).hex()))
            result = a[2]
        elif name == 'ioctl':
            if a[1] == 0x40044581:
                assert a[0] == 9 and a[2] == 7
                operations.append(dict(call='erase', effect_id=7))
                uc.reg_write(UC_ARM64_REG_X0, 0)
                uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))
                return
            assert a[:2] == [9, 0x40304580]
            effect = bytes(uc.mem_read(a[2], 48))
            pointer = int.from_bytes(effect[40:48], 'little')
            length = int.from_bytes(effect[36:40], 'little')
            assert length == 2
            custom = bytes(uc.mem_read(pointer, 2 * length))
            operations.append(dict(call='upload', effect=effect.hex(), custom=custom.hex()))
            uc.mem_write(a[2] + 2, b'\7\0')  # Input core slot allocation fixture.
            result = 0
        else:
            raise AssertionError(('unknown service boundary', name, a))
        uc.reg_write(UC_ARM64_REG_X0, result)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))

    u.hook_add(UC_HOOK_CODE, hook)
    for i, value in enumerate([0x4000000, 0xffffffff, duration, 0]):
        u.reg_write(UC_ARM64_REG_X0 + i, value)
    u.reg_write(UC_ARM64_REG_SP, 0x501fff0)
    u.reg_write(UC_ARM64_REG_X30, 0x6000000)
    u.emu_start(0x119b4, 0x6000000, count=100000, timeout=2000000)
    assert u.reg_read(UC_ARM64_REG_PC) == 0x6000000, 'service execution budget'
    assert u.reg_read(UC_ARM64_REG_X0) == 0
    assert [o['call'] for o in operations] == ['write', 'upload', 'write']
    assert bytes.fromhex(operations[0]['data'])[16:] == struct.pack('<HHi', 21, 96, 100)
    assert bytes.fromhex(operations[2]['data'])[16:] == struct.pack('<HHi', 21, 7, 1)
    assert bytes.fromhex(operations[1]['custom']) == struct.pack('<HH', 0, long_id)
    effect = bytes.fromhex(operations[1]['effect'])
    assert struct.unpack_from('<Hh', effect) == (81, -1)
    assert struct.unpack_from('<H', effect, 16)[0] == 93
    assert struct.unpack_from('<H', effect, 10)[0] == 0
    # Execute the same helper with duration=0, the stop caller's arguments.
    start_operations = operations[:]
    operations.clear()
    for i, value in enumerate([0x4000000, 0xffffffff, 0, 0]):
        u.reg_write(UC_ARM64_REG_X0 + i, value)
    u.reg_write(UC_ARM64_REG_SP, 0x501fff0)
    u.reg_write(UC_ARM64_REG_X30, 0x6000000)
    u.emu_start(0x119b4, 0x6000000, count=100000, timeout=2000000)
    assert u.reg_read(UC_ARM64_REG_PC) == 0x6000000, 'service stop execution budget'
    assert u.reg_read(UC_ARM64_REG_X0) == 0
    assert operations == [dict(call='erase', effect_id=7)]
    return start_operations, operations


class Custom(Playback):
    def on_code(self, u, address, size, data):
        if self.hooks.get(address) == 'cs40l26_num_ram_waves':
            u.reg_write(UC_ARM64_REG_X0, self.ram_count)
            u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_X30))
            return
        return super().on_code(u, address, size, data)


def main():
    cases, sources, drivers = [], {}, {}
    with tempfile.TemporaryDirectory(prefix='dijun-service-FF-') as temp:
        production = {n: (e, v) for n, e, v in capture(Path(temp))}
    for sample in ['os4-current', 'os4-stable']:
        base = ROOT / 'firmware/samples' / sample / 'analysis'
        service = base / 'odm/bin/hw/vendor.xring.hardware.vibratorfeature.service'
        xml = base / 'odm/etc/waveform_conf.xml'
        props = base / 'odm/etc/build.prop'
        long_id = int(ET.fromstring(xml.read_bytes()).findtext('long_vib_id/data'))
        assert long_id == 31 and 'ro.odm.mm.vibrator.cirrus=true' in props.read_text()
        path = base / 'vendor_dlkm/lib/modules/xring_audio_hw_third.ko'
        drivers[sample] = dict(path=str(path.relative_to(ROOT)), sha256=sha(path))
        disasm = ROOT / 'logs' / (sample + '-vibrator-service.disasm')
        disasm.write_bytes(subprocess.check_output([
            '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump', '-d', str(service)]))
        sources.update({str(p.relative_to(ROOT)): sha(p) for p in [service, xml, props, disasm]})
        driver_disasm = ROOT / 'logs' / (sample + '-haptics-custom-request-core.disasm')
        driver_disasm.write_bytes(subprocess.check_output([
            '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump', '-dr',
            '--disassemble-symbols=cs40l26_upload_worker,cs40l26_playback_effect,cs40l26_vibe_start_worker,cs40l26_num_ram_waves',
            str(path)]))
        sources[str(driver_disasm.relative_to(ROOT))] = sha(driver_disasm)
        for duration in [80, 300, 10000]:
            operations, stop_operations = service_request(service, disasm.read_text(), long_id, duration)
            effect = bytearray.fromhex(operations[1]['effect'])
            raw = bytes.fromhex(operations[1]['custom'])
            current, event = production[duration]
            assert struct.unpack_from('<HHh', current, 16) == (90, 8, 64)
            assert int.from_bytes(current[10:12], 'little') == duration
            cases.append(dict(sample=sample, case='service-request-' + str(duration), status='PASS',
                              requested_ms=duration, long_vib_id=long_id, operations=operations,
                              stop_operations=stop_operations,
                              recovery_effect=current.hex(), recovery_event=event.hex()))
            for count in [5, 32]:
                m = Custom(path)
                m.ram_count = count
                m.intercept('cs40l26_num_ram_waves')
                # Explicit post-copy boundary: no privileged user-copy code or
                # real input core is claimed here.
                struct.pack_into('<h', effect, 2, 7)
                m.uc.mem_write(CTX + 0x78, bytes(effect))
                m.put64(CTX + 0xb0, 0x4090000)
                m.put32(CTX + 0xb8, 2)
                m.uc.mem_write(0x4090000, raw)
                m.uc.mem_write(0x4050000 + 7 * 48, bytes(effect))
                m.run('cs40l26_upload_worker', m.upload_work)
                result = m.u32(m.upload_result)
                assert result == (0xffffffea if count == 5 else 0)
                if count == 32:
                    assert m.run('cs40l26_playback_effect', INPUT, 7, 1) == 0
                    m.start()
                    assert m.mailbox == [0x100001f]
                    assert [r['value'] for r in m.registers] == [0, 0]
                else:
                    assert not m.mailbox and not m.registers
                cases.append(dict(sample=sample, case=f'custom-{duration}-RAM-count-{count}', status='PASS',
                                  ram_count_fixture=count, upload_status=result, registers=m.registers,
                                  mailbox=m.mailbox, messages=m.messages))
    tests = [Path(__file__).resolve()] + [ROOT / 'tests' / n for n in [
        'haptics_playback_emulation.py', 'haptics_lifecycle_emulation.py',
        'haptics_driver_emulation.py', 'haptics_driver_capture.cpp', 'haptics-emulator-dependencies.json']]
    tests.append(ROOT / 'scripts/firmware_facts.py')
    dependencies = sorted(p for p in DEPS.rglob('*') if p.is_file() and
                          (p.suffix in ['.py', '.so'] or '.so.' in p.name))
    sources.update({str(p): sha(p) for p in [SOURCE, SOURCE.with_suffix('.h')]})
    report = dict(status='PASS', scope=__doc__.strip(), cases=cases, drivers=drivers, sources=sources,
                  tests={str(p.relative_to(ROOT)): sha(p) for p in tests},
                  emulator_files={str(p.relative_to(ROOT)): sha(p) for p in dependencies})
    (ROOT / 'logs/haptics-service-request-emulation.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS:', len(cases), 'cases; stock CUSTOM index 31 differs from Recovery sine; physical output unverified.')


if __name__ == '__main__':
    main()
