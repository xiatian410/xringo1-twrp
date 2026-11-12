#!/usr/bin/env python3
"""Check the missing-FF_GAIN hypothesis against original OS4 instructions.

Original probe, gain callback and gain worker execute with the existing explicit
kernel/PM/register/mailbox fixtures. DSP does not execute. Firmware defaults
are decoded independently from packed WMFW and all later WMDR parameter writes.
No input write, DSP readiness or motor operation is asserted by PASS.
"""
import json
import struct
import subprocess
from pathlib import Path

from haptics_probe_selftest_emulation import SelfTest, ROOT, DEPS, CTX, sha
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30
from haptics_coefficients_emulation import table


class Gain(SelfTest):
    def __init__(self, *args):
        super().__init__(*args)
        self.watch += ['cs40l26_set_gain', 'cs40l26_set_gain_worker']

    def on_code(self, u, address, size, data):
        if self.hooks.get(address) == 'queue_work_on' and self.arg(2) == CTX + 0x100:
            assert self.arg(1) == 0x4080000 and not self.queue
            self.queue.append(self.arg(2))
            self.calls.append('queue_work_on')
            u.reg_write(UC_ARM64_REG_X0, 1)
            u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_X30))
            return
        return super().on_code(u, address, size, data)


def firmware_default(blobs, address):
    """Track the last supplied value at this unpacked X-memory word."""
    blob = blobs['cs40l26.wmfw']
    offset = 40
    history = []
    while offset < len(blob):
        tag, length = struct.unpack_from('<II', blob, offset)
        payload = blob[offset + 8:offset + 8 + length]
        kind, word = tag >> 24, tag & 0xffffff
        if kind == 17:
            # Packed X data: reverse bus-order four-byte groups, then decode
            # three-byte little-endian DSP words, as for the algorithm table.
            assert length % 4 == 0
            stream = b''.join(payload[i:i + 4][::-1] for i in range(0, length, 4))
            assert len(stream) % 3 == 0
            index = (address - 0x2800000) // 4 - word
            if 0 <= index < len(stream) // 3:
                value = int.from_bytes(stream[index * 3:index * 3 + 3], 'little')
                history.append(dict(file='cs40l26.wmfw', region_offset=offset,
                                    word_index=index, value=value))
        elif kind == 5:
            index = address - (0x2800000 + word * 4)
            if 0 <= index <= length - 4:
                history.append(dict(file='cs40l26.wmfw', region_offset=offset,
                                    value=int.from_bytes(payload[index:index + 4], 'big')))
        offset += 8 + ((length + 3) & ~3)
    rows = table(blob)[1]
    for name in ['cs40l26.bin', 'cs40l26-svc.bin', 'cs40l26-dvl.bin',
                 'cs40l26-a2h.bin', 'cs40l26-dbc.bin']:
        blob = blobs[name]
        offset = 16
        while offset < len(blob):
            delta, kind, algorithm, rev, rate, length = struct.unpack_from('<HHIIII', blob, offset)
            if kind == 5:
                row = next(r for r in rows if r[0] & 0xffff == algorithm & 0xffff)
                assert row[1] == rev >> 8
                index = address - (0x2800000 + row[2] * 4 + delta)
                if 0 <= index <= length - 4:
                    value = int.from_bytes(blob[offset + 20 + index:offset + 24 + index], 'big')
                    history.append(dict(file=name, region_offset=offset, value=value))
            offset += 20 + ((length + 3) & ~3)
    assert history and history[-1]['value'] == 0, history
    return history


def main():
    dtpath = ROOT / 'logs/haptics-devicetree-audit.json'
    dt = json.loads(dtpath.read_text())
    cases, drivers, sources = [], {}, {str(dtpath.relative_to(ROOT)): sha(dtpath)}
    for sample in ['os4-current', 'os4-stable']:
        base = ROOT / 'firmware/samples' / sample / 'analysis'
        path = base / 'vendor_dlkm/lib/modules/xring_audio_hw_third.ko'
        drivers[sample] = dict(path=str(path.relative_to(ROOT)), sha256=sha(path))
        files = sorted((base / 'odm/firmware').glob('cs40l26*'))
        blobs = {p.name: p.read_bytes() for p in files}
        sources.update({str(p.relative_to(ROOT)): sha(p) for p in files})
        properties = next(c for c in dt['cases'] if c['sample'] == sample and
                          c['case'] == 'overlay-5')['haptics']['/soc/i2c@EC100000/cs40l26@43']['properties']
        m = Gain(path, blobs, properties)
        assert m.run('cs40l26_probe', CTX) == 0 and not m.queue
        initial = struct.unpack('<HH', m.uc.mem_read(CTX + 0x1dc, 4))
        assert initial == (100, 100)
        m.dsp = m.u64(CTX + 0x50)
        coefficient = next(r for r in m.records() if r['name'] == 'SOURCE_ATTENUATION')
        assert coefficient['register'] == 0x28059e8 and coefficient['algorithm'] == 0x4013c
        history = firmware_default(blobs, coefficient['register'])
        cases.append(dict(sample=sample, case='probe-and-firmware-default', status='PASS',
                          initial_gain=list(initial), coefficient=coefficient, firmware_default_history=history,
                          probe_selftest_gain_callback_called='cs40l26_set_gain' in m.entries))
        # Callbacks are void. The original register write and queued work, not
        # residual x0 or successful evdev write, establish software acceptance.
        for gain, expected in [(0, 400), (50, 24), (100, 0), (101, None), (65535, None)]:
            before = len(m.writes)
            m.run('cs40l26_set_gain', 0x40a8000, gain)
            queued = list(m.queue)
            assert queued == ([] if expected is None else [CTX + 0x100])
            while m.queue:
                m.run('cs40l26_set_gain_worker', m.queue.pop(0))
            writes = m.writes[before:]
            assert writes == ([] if expected is None else [dict(address=0x28059e8, value=expected)])
            stored = int.from_bytes(m.uc.mem_read(CTX + 0x1dc, 2), 'little')
            assert stored == (gain if expected is not None else 100)
            cases.append(dict(sample=sample, case='gain-' + str(gain), status='PASS',
                              requested_gain=gain, queued=queued, writes=writes, stored_gain=stored))
        disasm = ROOT / 'logs' / (sample + '-haptics-gain-core.disasm')
        disasm.write_bytes(subprocess.check_output([
            '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump', '-dr',
            '--disassemble-symbols=cs40l26_probe,cs40l26_set_gain,cs40l26_set_gain_worker', str(path)]))
        sources[str(disasm.relative_to(ROOT))] = sha(disasm)
    tests = [Path(__file__).resolve()] + [ROOT / 'tests' / n for n in [
        'haptics_probe_selftest_emulation.py', 'haptics_wave_irq_emulation.py',
        'haptics_runtime_config_emulation.py', 'haptics_postboost_emulation.py',
        'haptics_probe_upload_emulation.py', 'haptics_config_emulation.py',
        'haptics_coefficients_emulation.py', 'haptics_upload_emulation.py',
        'haptics_firmware_emulation.py', 'haptics_driver_emulation.py', 'haptics-emulator-dependencies.json']]
    tests.append(ROOT / 'scripts/firmware_facts.py')
    dependencies = sorted(p for p in DEPS.rglob('*') if p.is_file() and
                          (p.suffix in ['.py', '.so'] or '.so.' in p.name))
    result = dict(status='PASS', scope=__doc__.strip(), cases=cases, drivers=drivers, sources=sources,
                  tests={str(p.relative_to(ROOT)): sha(p) for p in tests},
                  emulator_files={str(p.relative_to(ROOT)): sha(p) for p in dependencies})
    (ROOT / 'logs/haptics-gain-emulation.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS:', len(cases), 'cases; initial gain 100, stock attenuation 0, gain >100 rejected.')


if __name__ == '__main__':
    main()
