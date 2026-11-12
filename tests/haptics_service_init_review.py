#!/usr/bin/env python3
"""Execute stock OS4 input discovery and the separate FF backend constructor.

The outer constructor stops at 0x13084, before the alternate-device, thread,
XML and playback-backend setup. Calibration restore is a recorded call boundary
(its body has separate tests). The FF constructor is then executed separately
with an explicit global sysfs-path fixture; this is not a full service startup.
Directory entries, ioctl/properties/mixer, allocation, libc++ string append and
custom_wave reads are fixtures. No phone, ALSA, DSP or motor is executed.
"""
import json
import struct
from pathlib import Path

from haptics_service_route_review import Service, OBJ, RETURN
from haptics_driver_emulation import ROOT, DEPS, sha
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X30, UC_ARM64_REG_PC, UC_ARM64_REG_SP

SYS = '/sys/bus/i2c/drivers/xring-smartpa/0-0043'
BACKEND = OBJ + 0x1000


class Startup(Service):
    def __init__(self, path, disasm, case):
        super().__init__(path, disasm, [], [])
        # Do not reuse the initialized Cirrus/mixer state from route tests.
        self.u.mem_write(OBJ, bytes(0x20000))
        self.put64(0x34260, 0)
        self.case = case
        self.entries = iter(['event0', 'event4'] if case == 'skip-non-FF' else ['event4'])
        self.node = 'event4'
        self.alloc = OBJ + 0x12000
        self.retries = set()

    def reply(self, value):
        self.u.reg_write(UC_ARM64_REG_X0, value & ((1 << 64) - 1))
        self.u.reg_write(UC_ARM64_REG_PC, self.u.reg_read(UC_ARM64_REG_X30))

    def hook(self, u, address, size, data):
        a = [self.arg(i) for i in range(8)]
        if address == 0x1190c:
            assert self.text(a[3]) == '%s%s'
            value = self.text(a[4]) + self.text(a[5])
            assert len(value) < a[1]
            u.mem_write(a[0], value.encode() + b'\0')
            self.reply(len(value))
            return
        if address == 0x2bdfc:
            self.calls.append(dict(call='calibration-restore-boundary'))
            self.reply(0)
            return
        if address not in self.plt:
            return
        name = self.plt[address]
        record = dict(call=name)
        if name == '__android_log_print':
            self.logs.append(dict(format=self.text(a[2]), args=a[3:]))
            self.reply(0)
            return
        if name == '_ZN4aidl7android8hardware8vibrator10BnVibratorC2Ev':
            assert a[0] == OBJ
            result = 0
        elif name == 'memset':
            assert a[2] <= 0x1000
            u.mem_write(a[0], bytes([a[1] & 255]) * a[2])
            result = a[0]
        elif name == 'opendir':
            assert self.text(a[0]) == '/dev/input/'
            result = 0 if self.case == 'no-directory' else OBJ + 0x6000
        elif name == 'readdir':
            assert a[0] == OBJ + 0x6000
            self.node = next(self.entries, '')
            result = OBJ + 0x6100 if self.node else 0
            if result:
                u.mem_write(result, bytes(64))
                u.mem_write(result + 19, self.node.encode() + b'\0')
            record['entry'] = self.node
        elif name == '__open_2':
            record.update(path=self.text(a[0]), flags=a[1])
            assert a[1] == 2
            assert record['path'] in ['/dev/input/event0', '/dev/input/event4', SYS + '/custom_wave']
            retry = (name, record['path'])
            if self.case == 'open-EINTR' and retry not in self.retries:
                self.retries.add(retry)
                self.put32(OBJ + 0x7000, 4)
                result = -1
            elif self.case in ['open-denied', 'custom-wave-absent']:
                self.put32(OBJ + 0x7000, 13 if self.case == 'open-denied' else 2)
                result = -1
            else:
                result = 8 if self.node == 'event0' else 9
        elif name == '__errno':
            result = OBJ + 0x7000
        elif name == 'ioctl':
            record.update(fd=a[0], request=a[1])
            assert a[0] in [8, 9]
            assert a[1] in [0x80204506, 0x80104535]
            retry = (name, a[1])
            if self.case == 'name-EINTR' and a[1] == 0x80204506 and retry not in self.retries:
                self.retries.add(retry)
                self.put32(OBJ + 0x7000, 4)
                result = -1
            elif self.case == 'name-error' and a[1] == 0x80204506:
                self.put32(OBJ + 0x7000, 5)
                result = -1
            elif self.case == 'cap-error' and a[1] == 0x80104535:
                self.put32(OBJ + 0x7000, 5)
                result = -1
            elif a[1] == 0x80204506:
                value = 'pwrkey' if self.node == 'event0' else 'cs40l26_input'
                u.mem_write(a[2], value.encode() + b'\0')
                record['name'] = value
                result = len(value) + 1
            else:
                bits = 0 if self.node == 'event0' or self.case == 'no-supported-effect' else ((1 << 81) | (1 << 88))
                u.mem_write(a[2], bits.to_bytes(16, 'little'))
                record['bits'] = hex(bits)
                result = 16
        elif name == 'property_get_bool':
            key = self.text(a[0])
            assert key in ['ro.odm.mm.vibrator.audio_haptic_support', 'ro.odm.mm.vibrator.cirrus']
            result = int(not ((self.case == 'cirrus-disabled' and key.endswith('.cirrus')) or
                              (self.case == 'audio-disabled' and key.endswith('.audio_haptic_support'))))
            record.update(key=key, value=result)
        elif name == 'mixer_open':
            assert a[0] == 0
            result = 0 if self.case == 'mixer-absent' else OBJ + 0x9000
        elif name in ['close', 'closedir']:
            record['fd_or_dir'] = a[0]
            result = 0
        elif name == 'property_get':
            assert self.text(a[0]) == 'ro.odm.mm.vibrator.manufacturer'
            value = 'cirrus'
            u.mem_write(a[1], value.encode() + b'\0')
            record.update(key=self.text(a[0]), value=value)
            result = len(value)
        elif name == 'strlen':
            result = len(self.text(a[0]).encode())
        elif name == '_Znwm':
            assert 0 < a[0] <= 4096
            result = self.alloc
            self.alloc += (a[0] + 15) & ~15
            assert self.alloc < OBJ + 0x18000
            record['size'] = a[0]
        elif name == 'memcpy':
            assert a[2] <= 4096
            u.mem_write(a[0], bytes(u.mem_read(a[1], a[2])))
            result = a[0]
        elif name == '_ZNSt3__112basic_stringIcNS_11char_traitsIcEENS_9allocatorIcEEE6appendEPKcm':
            # Explicit libc++ ABI fixture, no arbitrary append or hidden I/O.
            prefix = self.text(self.u64(a[0] + 16)) if u.mem_read(a[0], 1)[0] & 1 else self.text(a[0] + 1)
            suffix = bytes(u.mem_read(a[1], a[2])).decode()
            assert prefix == SYS and suffix == '/custom_wave'
            value = (prefix + suffix).encode()
            pointer = self.alloc
            self.alloc += 256
            u.mem_write(pointer, value + b'\0')
            u.mem_write(a[0], struct.pack('<QQQ', 257, len(value), pointer))
            result = a[0]
        elif name == '_ZdlPv':
            assert OBJ + 0x12000 <= a[0] < OBJ + 0x18000
            result = 0
        elif name == 'read':
            assert a[0] == 9 and a[2] == 511
            value = b'custom_wave_id=31\n'
            u.mem_write(a[1], value)
            record['bytes'] = value.hex()
            result = len(value)
        elif name == 'str_parms_create_str':
            assert self.text(a[0]) == 'custom_wave_id=31\n'
            result = OBJ + 0xa000
        elif name == 'str_parms_get_int':
            assert a[0] == OBJ + 0xa000 and self.text(a[1]) == 'custom_wave_id'
            self.put32(a[2], 31)
            result = -2 if self.case == 'custom-wave-key-error' else 0
        elif name == 'str_parms_destroy':
            assert a[0] == OBJ + 0xa000
            result = 0
        else:
            raise AssertionError(('unknown initialization boundary', name, a))
        record['result'] = result
        self.calls.append(record)
        self.reply(result)

    def u64(self, address):
        return int.from_bytes(self.u.mem_read(address, 8), 'little')

    def prefix(self):
        self.u.reg_write(UC_ARM64_REG_X0, OBJ)
        self.u.reg_write(UC_ARM64_REG_SP, 0x501fff0)
        self.u.reg_write(UC_ARM64_REG_X30, RETURN)
        self.u.emu_start(0x12ce0, 0x13084, count=100000, timeout=2000000)
        assert self.u.reg_read(UC_ARM64_REG_PC) == 0x13084, 'prefix budget exhausted'
        return dict(fd=struct.unpack('<i', bytes(self.u.mem_read(OBJ + 0x58, 4)))[0],
                    cirrus=int(self.u.mem_read(OBJ + 0x54, 1)[0]), mixer=self.u64(0x34260))


def main():
    cases, sources = [], {}
    labels = ['normal', 'no-directory', 'open-denied', 'name-error', 'cap-error',
              'no-supported-effect', 'cirrus-disabled', 'audio-disabled', 'mixer-absent',
              'skip-non-FF', 'open-EINTR', 'name-EINTR']
    for sample in ['os4-current', 'os4-stable']:
        path = ROOT / 'firmware/samples' / sample / 'analysis/odm/bin/hw/vendor.xring.hardware.vibratorfeature.service'
        disasm = ROOT / 'logs' / (sample + '-vibrator-service.disasm')
        properties = path.parents[2] / 'etc/build.prop'
        props = dict(line.split('=', 1) for line in properties.read_text().splitlines()
                     if line.startswith('ro.odm.mm.vibrator.') and '=' in line)
        assert props['ro.odm.mm.vibrator.cirrus'] == 'true'
        assert props['ro.odm.mm.vibrator.audio_haptic_support'] == 'true'
        assert props['ro.odm.mm.vibrator.manufacturer'] == 'cirrus'
        assert props['ro.odm.mm.vibrator.sys_path'] == SYS
        for p in [path, disasm, properties]: sources[str(p.relative_to(ROOT))] = sha(p)
        for label in labels:
            m = Startup(path, disasm.read_text(), label)
            state = m.prefix()
            names = [c['call'] for c in m.calls]
            accepted = label not in ['no-directory', 'open-denied', 'name-error', 'cap-error', 'no-supported-effect']
            assert state['fd'] == (9 if accepted else -1), (label, state)
            assert state['cirrus'] == int(accepted and label != 'cirrus-disabled')
            state['audio_haptic'] = int(m.u.mem_read(OBJ + 0x52, 1)[0])
            assert state['audio_haptic'] == int(accepted and label != 'audio-disabled')
            state['effect_id'], state['amplitude'] = struct.unpack('<hH', bytes(m.u.mem_read(OBJ + 0x5c, 4)))
            assert (state['effect_id'], state['amplitude']) == (-1, 32767)
            assert bool(state['mixer']) == (accepted and label not in ['cirrus-disabled', 'mixer-absent'])
            restore = label not in ['no-directory', 'open-denied', 'name-error']
            assert names.count('calibration-restore-boundary') == int(restore)
            assert names.count('mixer_open') == int(accepted and label != 'cirrus-disabled')
            if restore:
                r = names.index('calibration-restore-boundary')
                assert m.calls[r + 1]['call'] == 'ioctl' and m.calls[r + 1]['request'] == 0x80104535
            assert not any(c['call'] in ['write', 'mixer_ctl_set_value'] for c in m.calls)
            cases.append(dict(sample=sample, case=label, status='PASS', group='discovery-prefix', state=state, calls=m.calls, logs=m.logs))
        for label in ['custom-wave-present', 'custom-wave-absent', 'custom-wave-key-error']:
            m = Startup(path, disasm.read_text(), label)
            # Explicit global fixture: populated by other startup code, not this constructor.
            m.u.mem_write(0x344e8, SYS.encode() + b'\0')
            m.run(0x26a74, BACKEND, 9)
            state = struct.unpack('<iii', bytes(m.u.mem_read(BACKEND + 8, 12)))
            assert state == (9, -1 if label == 'custom-wave-absent' else 9,
                             31 if label == 'custom-wave-present' else -1), (label, state)
            assert not any(c['call'] in ['ioctl', 'write', 'mixer_ctl_set_value'] for c in m.calls)
            cases.append(dict(sample=sample, case=label, status='PASS', group='separate-FF-constructor', state=state, calls=m.calls, logs=m.logs))
    files = [Path(__file__).resolve(), ROOT / 'tests/haptics_service_route_review.py',
             ROOT / 'tests/haptics_service_request_emulation.py', ROOT / 'tests/haptics_driver_emulation.py',
             ROOT / 'tests/haptics_playback_emulation.py', ROOT / 'tests/haptics_lifecycle_emulation.py',
             ROOT / 'tests/haptics-emulator-dependencies.json', ROOT / 'scripts/firmware_facts.py']
    report = dict(status='PASS', scope=__doc__, cases=cases, sources=sources,
                  tests={str(p.relative_to(ROOT)): sha(p) for p in files},
                  emulator_files={str(p.relative_to(ROOT)): sha(p) for p in DEPS.rglob('*')
                                  if p.is_file() and (p.suffix in ['.py', '.so'] or '.so.' in p.name)})
    (ROOT / 'logs/haptics-service-init-review.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS:', len(cases), 'original discovery/separate FF-constructor cases; no DSP/motor')


if __name__ == '__main__':
    main()
