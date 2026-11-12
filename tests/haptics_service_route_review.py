#!/usr/bin/env python3
"""Execute original OS4 mixer routing and the separate ordinary on entry.

XML consumption, constructors, Binder, ALSA, device discovery, calibration,
timer threads, DSP and motor do not execute. XML lists are installed in an
explicit libc++ unordered-set layout fixture. Mixer/FF/PLT calls are recorded
boundaries; successful returns do not prove hardware state or physical output.
Unknown calls and instruction/time budget exhaustion fail closed.
"""
import io
import json
import re
import struct
from pathlib import Path
import xml.etree.ElementTree as ET

from haptics_driver_emulation import ROOT, DEPS, sha
from haptics_service_request_emulation import SERVICE_SHA
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import (
    UC_ARM64_REG_X0, UC_ARM64_REG_X8, UC_ARM64_REG_X30,
    UC_ARM64_REG_PC, UC_ARM64_REG_SP, UC_ARM64_REG_TPIDR_EL0,
)

OBJ = 0x4000000
RETURN = 0x6000000


class Service:
    def __init__(self, path, disassembly, no_dvl, no_svc, enabled=True,
                 cached=(1, 1), failure=None):
        assert sha(path) == SERVICE_SHA
        self.u = u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        elf = ELFFile(io.BytesIO(path.read_bytes()))
        for segment in elf.iter_segments():
            if segment['p_type'] == 'PT_LOAD':
                start = segment['p_vaddr'] & ~4095
                length = (segment['p_vaddr'] - start + segment['p_memsz'] + 4095) & ~4095
                u.mem_map(start, length)
                u.mem_write(segment['p_vaddr'], segment.data())
        for address, length in [(OBJ, 0x20000), (0x5000000, 0x20000), (RETURN, 4096)]:
            u.mem_map(address, length)
        u.reg_write(UC_ARM64_REG_TPIDR_EL0, OBJ + 0x8000)
        self.put64(0x34260, OBJ + 0x9000)  # explicit mixer handle
        self.put32(0x34024, cached[0])  # DVL cache
        self.put32(0x34028, cached[1])  # SVC cache
        u.mem_write(OBJ + 0x54, bytes([enabled]))
        # One-bucket hash-set fixtures follow the loads in the original helper.
        # Nodes contain next/hash/int-key, and the bucket points before its head.
        for header, arena, keys in [(0x342b8, OBJ + 0xa000, no_dvl),
                                     (0x342e0, OBJ + 0xc000, no_svc)]:
            self.put64(header, arena)
            self.put64(header + 8, 1 if keys else 0)
            self.put64(arena, arena + 0x100)
            self.put64(arena + 0x100, arena + 0x200 if keys else 0)
            for i, key in enumerate(keys):
                node = arena + 0x200 + i * 32
                self.put64(node, node + 32 if i + 1 < len(keys) else 0)
                self.put64(node + 8, key)
                self.put32(node + 16, key)
        self.plt = {int(a, 16): n for a, n in re.findall(
            r'^([0-9a-f]+) <([^>]+)@plt>:', disassembly, re.M)}
        self.calls, self.logs = [], []
        self.failure = failure
        self.controls = {}
        u.hook_add(UC_HOOK_CODE, self.hook)

    def put64(self, a, v): self.u.mem_write(a, struct.pack('<Q', v))
    def put32(self, a, v): self.u.mem_write(a, struct.pack('<I', v))
    def arg(self, i): return self.u.reg_read(UC_ARM64_REG_X0 + i)

    def text(self, a):
        data = bytearray()
        for i in range(1024):
            ch = bytes(self.u.mem_read(a + i, 1))
            if ch == b'\0': return data.decode()
            data += ch
        raise AssertionError('unterminated string')

    def hook(self, u, address, size, data):
        if address not in self.plt: return
        name = self.plt[address]
        a = [self.arg(i) for i in range(6)]
        if name == '__android_log_print':
            self.logs.append(dict(format=self.text(a[2]), args=a[3:]))
            result = 0
        elif name in ['_ZN7android7MiEventC1Ej', '_ZN7android7MiEventD1Ev']:
            result = 0
        elif name == 'mixer_get_ctl_by_name':
            assert a[0] == OBJ + 0x9000
            control = self.text(a[1])
            assert control in ['DVL Algo Enable', 'SVC Algo Enable', 'Haptics Source']
            self.calls.append(dict(call=name, control=control))
            result = 0 if self.failure == 'missing-control' else OBJ + 0xe000 + len(self.controls) * 16
            if result: self.controls[result] = control
        elif name == 'mixer_ctl_set_value':
            assert a[0] in self.controls and a[1] == 0
            result = -5 if self.failure == 'set-error' else 0
            self.calls.append(dict(call=name, control=self.controls[a[0]], value=a[2], result=result))
        elif name == 'write':
            assert a[0] == 9 and a[2] == 24
            self.calls.append(dict(call='write', data=bytes(u.mem_read(a[1], 24)).hex()))
            result = 24
        elif name == 'ioctl':
            assert a[:2] == [9, 0x40304580]
            effect = bytes(u.mem_read(a[2], 48))
            count, pointer = struct.unpack_from('<IQ', effect, 36)
            assert count == 2
            self.calls.append(dict(call='upload', effect=effect.hex(),
                                   custom=bytes(u.mem_read(pointer, count * 2)).hex()))
            u.mem_write(a[2] + 2, b'\7\0')
            result = 0
        elif name == 'AStatus_newOk':
            self.calls.append(dict(call=name))
            result = OBJ + 0xf000
        else:
            raise AssertionError(('unreviewed boundary', name, a))
        u.reg_write(UC_ARM64_REG_X0, result & ((1 << 64) - 1))
        u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_X30))

    def run(self, entry, *args):
        for i, value in enumerate(args): self.u.reg_write(UC_ARM64_REG_X0 + i, value)
        self.u.reg_write(UC_ARM64_REG_X8, OBJ + 0x5000)
        self.u.reg_write(UC_ARM64_REG_SP, 0x501fff0)
        self.u.reg_write(UC_ARM64_REG_X30, RETURN)
        self.u.emu_start(entry, RETURN, count=100000, timeout=2000000)
        assert self.u.reg_read(UC_ARM64_REG_PC) == RETURN, 'execution budget exhausted'
        return self.arg(0)


def main():
    cases, sources = [], {}
    for sample in ['os4-current', 'os4-stable']:
        base = ROOT / 'firmware/samples' / sample / 'analysis/odm'
        service = base / 'bin/hw/vendor.xring.hardware.vibratorfeature.service'
        xml = base / 'etc/waveform_conf.xml'
        disasm = ROOT / 'logs' / (sample + '-vibrator-service.disasm')
        tree = ET.fromstring(xml.read_bytes())
        lists = {key: list(map(int, tree.findtext(key + '/data').split(',')))
                 for key in ['no_dvl', 'no_svc']}
        assert int(tree.findtext('long_vib_id/data')) == 31
        for p in [service, xml, disasm]: sources[str(p.relative_to(ROOT))] = sha(p)
        for label, number, enabled, cached, failure, expected in [
            ('wave31', 31, True, (1, 1), None, [('SVC Algo Enable', 0), ('Haptics Source', 0), ('Haptics Source', 1)]),
            ('wave31-cached', 31, True, (1, 0), None, [('Haptics Source', 0), ('Haptics Source', 1)]),
            ('wave0', 0, True, (1, 1), None, [('DVL Algo Enable', 0), ('Haptics Source', 0), ('Haptics Source', 1)]),
            ('wave218', 218, True, (0, 0), None, [('DVL Algo Enable', 1), ('SVC Algo Enable', 1), ('Haptics Source', 0), ('Haptics Source', 1)]),
            ('cirrus-disabled', 31, False, (1, 1), None, [('Haptics Source', 0), ('Haptics Source', 1)]),
            ('missing-control', 31, True, (1, 1), 'missing-control', []),
            ('set-error', 31, True, (1, 1), 'set-error', [('SVC Algo Enable', 0), ('Haptics Source', 0), ('Haptics Source', 1)]),
        ]:
            m = Service(service, disasm.read_text(), lists['no_dvl'], lists['no_svc'], enabled, cached, failure)
            result = m.run(0x1426c, OBJ, number)
            writes = [(c['control'], c['value']) for c in m.calls if c['call'] == 'mixer_ctl_set_value']
            assert writes == expected, (sample, label, writes)
            # Mixer errors are logged; a failed set still returns success to
            # the routing helper and updates cached flags before the call.
            final_log = m.logs[-1]
            assert final_log['args'][0] & 0xffffffff == (0xffffffff if failure == 'missing-control' else 0)
            if failure == 'set-error':
                assert all(c['result'] == -5 for c in m.calls if c['call'] == 'mixer_ctl_set_value')
                assert struct.unpack('<II', bytes(m.u.mem_read(0x34024, 8))) == (1, 0)
            cases.append(dict(sample=sample, case=label, status='PASS', calls=m.calls,
                              logs=m.logs, return_register=result,
                              return_semantics='tail call to log; use final log status, not x0'))
            if failure == 'set-error':
                m.calls, m.logs = [], []
                m.failure = None
                m.run(0x1426c, OBJ, number)
                writes = [(c['control'], c['value']) for c in m.calls if c['call'] == 'mixer_ctl_set_value']
                assert writes == [('Haptics Source', 0), ('Haptics Source', 1)]
                cases.append(dict(sample=sample, case='retry-after-set-error', status='PASS',
                                  calls=m.calls, logs=m.logs,
                                  observation='failed SVC write cached as disabled; retry omits SVC'))
        for duration in [80, 300]:
            m = Service(service, disasm.read_text(), lists['no_dvl'], lists['no_svc'], failure='missing-control')
            m.put32(OBJ + 0x58, 9)
            m.u.mem_write(OBJ + 0x5c, struct.pack('<hH', -1, 32767))
            m.put32(0x3402c, 31)
            m.u.mem_write(0x34308, b'\1')  # calibration restore boundary already complete
            m.run(0x13e04, OBJ, duration, OBJ + 0x4000)
            assert [c['call'] for c in m.calls] == ['write', 'upload', 'write', 'AStatus_newOk']
            assert bytes.fromhex(m.calls[1]['custom']) == struct.pack('<HH', 0, 31)
            assert bytes.fromhex(m.calls[0]['data'])[16:] == struct.pack('<HHi', 21, 96, 100)
            assert bytes.fromhex(m.calls[2]['data'])[16:] == struct.pack('<HHi', 21, 7, 1)
            assert bytes(m.u.mem_read(OBJ + 0x5000, 8)) == struct.pack('<Q', OBJ + 0xf000)
            cases.append(dict(sample=sample, case='ordinary-on-' + str(duration), status='PASS',
                              calls=m.calls, logs=m.logs,
                              boundary='null callback; no timer thread; calibration already restored'))
    tests = [Path(__file__).resolve(), ROOT / 'tests/haptics_driver_emulation.py',
             ROOT / 'tests/haptics_service_request_emulation.py',
             ROOT / 'tests/haptics_playback_emulation.py',
             ROOT / 'tests/haptics_lifecycle_emulation.py',
             ROOT / 'tests/haptics-emulator-dependencies.json',
             ROOT / 'scripts/firmware_facts.py']
    report = dict(status='PASS', scope=__doc__.strip(), cases=cases, sources=sources,
                  tests={str(p.relative_to(ROOT)): sha(p) for p in tests},
                  emulator_files={str(p.relative_to(ROOT)): sha(p) for p in DEPS.rglob('*')
                                  if p.is_file() and (p.suffix in ['.py', '.so'] or '.so.' in p.name)})
    (ROOT / 'logs/haptics-service-route-review.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS:', len(cases), 'original route/on cases; no hardware execution')


if __name__ == '__main__': main()
