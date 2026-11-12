#!/usr/bin/env python3
"""Join original OS4 A1 probe, ASP clock callback and production FF in one VM.

Stock DT/firmware, original clk_en/asp_start/swap_ext_clk/set_pll_loop and FF
upload/play/start/mailbox IRQ run. Codec topology, 3072000Hz BCLK, PLL read0,
13-jiffy stop timeout, register I/O/mailbox ACK, kernel PM/locks and serialized
queues are explicit fixtures. No actual ALSA dispatcher, DAPM scheduling, clock,
DSP, input core, electrical output or motor is executed. Writes never invent
readback. Failure scenarios test control flow, not working or silent hardware.
"""
import inspect
import json
from pathlib import Path
import subprocess
import tempfile

from haptics_a1_joined_review import Joined, ROOT, CTX, INPUT, EFFECT, EFFECTS
from haptics_driver_emulation import (MASK, SOURCE, DEPS, sha, capture,
                                      UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30)

WIDGET, COMPONENT, DEVICE, CODEC = 0x40c0000, 0x40c1000, 0x40c2000, 0x40c3000


class ASP(Joined):
    def __init__(self, *args):
        self.asp_runtime = False
        self.asp_mail, self.asp_waits, self.asp_updates, self.asp_entries = [], [], [], []
        self.scenario = 'no-ASP'
        super().__init__(*args)

    def on_code(self, u, address, size, data):
        if not self.asp_runtime:
            return super().on_code(u, address, size, data)
        for name in ['cs40l26_clk_en', 'cs40l26_asp_start', 'cs40l26_swap_ext_clk', 'cs40l26_set_pll_loop']:
            if address == self.symbols[name]:
                self.asp_entries.append(dict(function=name, args=[self.arg(i) for i in range(3)]))
        name = self.hooks.get(address)
        a = [self.arg(i) for i in range(7)] if name else []
        if name == 'snd_soc_dapm_to_component':
            assert a[0] == WIDGET + 0x4000
            result = COMPONENT
        elif name == 'cs40l26_mailbox_write' and self.current_worker is None:
            assert a[0] == CTX and a[1] in [0x5000000, 0x3000002]
            failed = (self.scenario == 'ASP-stop-command-error' and a[1] == 0x5000000 or
                      self.scenario == 'ASP-start-command-error' and a[1] == 0x3000002)
            result = -5 if failed else 0
            self.asp_mail.append(dict(command=a[1], result=result))
        elif name == 'completion_done':
            assert a[0] == CTX + 0x208
            result = int(self.u32(a[0]) != 0)
        elif name == 'wait_for_completion_timeout' and a[0] == CTX + 0x208:
            assert a[1] == 13 and not self.locked
            self.asp_waits.append(dict(pointer=a[0], timeout=a[1], result=0))
            result = 0  # Explicit no STOP IRQ; no synthetic completion added.
        elif name == 'regmap_update_bits_base':
            assert a[0] == 0x4070000 and a[1] == 0x2c04
            result = -5 if self.scenario == 'ASP-clock-update-error' else 0
            self.asp_updates.append(dict(address=a[1], mask=a[2], value=a[3], result=result))
        else:
            return super().on_code(u, address, size, data)
        self.calls.append(name)
        u.reg_write(UC_ARM64_REG_X0, result & MASK)
        u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_X30))

    def activate(self, scenario):
        self.asp_runtime = self.runtime = True
        self.scenario = scenario
        self.put64(WIDGET + 0x28, WIDGET + 0x4000)
        self.put64(COMPONENT + 0x10, DEVICE)
        self.put64(DEVICE + 0x98, CODEC)
        self.put64(CODEC, CTX)
        self.put64(CODEC + 8, 0x4060000)
        self.put64(CODEC + 0x10, 0x4070000)
        self.put32(CODEC + 0x18, 0 if scenario == 'ASP-invalid-BCLK' else 3072000)
        self.hardware[0x2c04] = 0
        if scenario == 'ASP-PLL-read-error': self.read_errors[0x2c04] = -5
        # Reset only state left by the prior synthetic probe self-test, as in
        # the existing A1 joined fixture; these are not measured phone values.
        self.put32(CTX + 0x200, 0)
        self.put32(CTX + 0x1d0, 0)
        self.completed.clear()
        self.selftest_writes.clear()
        self.selftest_mail.clear()
        assert self.u32(CTX + 0x1bb0) == 100  # Original probe gain default.
        assert self.uc.mem_read(CTX + 0x1d5, 1) == b'\0'
        return None if scenario == 'no-ASP' else self.runtime_call('cs40l26_clk_en', WIDGET, 0, 2)

    def state(self):
        return dict(vibe_state=self.u32(CTX + 0x1d0), count=self.u32(CTX + 0x200),
                    asp_active=int.from_bytes(self.uc.mem_read(CTX + 0x1d5, 1), 'little'))


def main():
    dtpath = ROOT / 'logs/haptics-devicetree-audit.json'
    dt = json.loads(dtpath.read_text())
    sources = {str(dtpath.relative_to(ROOT)): sha(dtpath)}
    for group in ['sources', 'libfdt_sources']:
        for name, digest in dt[group].items():
            p = Path(name) if Path(name).is_absolute() else ROOT / name
            assert sha(p) == digest
            sources[str(p)] = digest
    cases = []
    labels = ['no-ASP', 'ASP-stop-timeout', 'ASP-stop-command-error', 'ASP-start-command-error',
              'ASP-PLL-read-error', 'ASP-invalid-BCLK', 'ASP-clock-update-error']
    with tempfile.TemporaryDirectory(prefix='dijun-asp-ff-') as temp:
        effect = next(e for n, e, event in capture(Path(temp)) if n == 80)
    for sample in ['os4-current', 'os4-stable']:
        base = ROOT / 'firmware/samples' / sample / 'analysis'
        driver = base / 'vendor_dlkm/lib/modules/xring_audio_hw_third.ko'
        assert sha(driver) == '969a17203bf56c3d5b46e3a3ee1827cb3579aaa423c2fc21508e73d2548650f6'
        files = sorted((base / 'odm/firmware').glob('cs40l26*'))
        blobs = {p.name: p.read_bytes() for p in files}
        props = next(c for c in dt['cases'] if c['sample'] == sample and c['case'] == 'overlay-5')['haptics']['/soc/i2c@EC100000/cs40l26@43']['properties']
        ds = ROOT / 'logs' / (sample + '-haptics-asp-ff-core.disasm')
        ds.write_bytes(subprocess.check_output([
            '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump', '-dr',
            '--disassemble-symbols=cs40l26_clk_en,cs40l26_asp_start,cs40l26_swap_ext_clk,cs40l26_set_pll_loop,cs40l26_vibe_state_update,cs40l26_vibe_start_worker', str(driver)]))
        for p in files + [driver, ds]: sources[str(p.relative_to(ROOT))] = sha(p)
        for label in labels:
            m = ASP(driver, blobs, props, 'A1')
            assert m.run('cs40l26_probe', CTX) == 0
            enabled_result = m.activate(label)
            expected_result = None if label == 'no-ASP' else 0 if label == 'ASP-stop-timeout' else -22 if label == 'ASP-invalid-BCLK' else -110 if label == 'ASP-clock-update-error' else -5
            assert enabled_result == expected_result, (sample, label, enabled_result)
            before = m.state()
            assert before == dict(vibe_state=0 if label == 'no-ASP' else 2, count=0, asp_active=int(label != 'no-ASP'))
            initial_mail = m.asp_mail[:]
            expected_mail = [] if label == 'no-ASP' else [dict(command=0x5000000, result=-5 if label == 'ASP-stop-command-error' else 0)]
            if label not in ['no-ASP', 'ASP-stop-command-error', 'ASP-PLL-read-error']:
                expected_mail.append(dict(command=0x3000002, result=-5 if label == 'ASP-start-command-error' else 0))
            assert initial_mail == expected_mail
            assert len(m.asp_waits) == int(label in ['ASP-stop-timeout', 'ASP-invalid-BCLK', 'ASP-clock-update-error'])
            expected_clock = ([(0x800, 0x800, 0), (0x7e7, 0x420, 0), (0x800, 0, 0)] if label == 'ASP-stop-timeout' else
                              [(0x800, 0x800, -5)] * 5 if label == 'ASP-clock-update-error' else [])
            assert [(w['mask'], w['value'], w['result']) for w in m.asp_updates] == expected_clock
            m.uc.mem_write(EFFECT, effect)
            m.uc.mem_write(EFFECTS + 7 * 48, effect)
            assert m.runtime_call('cs40l26_upload_effect', INPUT, EFFECT, 0) == 0
            assert m.runtime_call('cs40l26_playback_effect', INPUT, 7, 1) == 0
            m.flush_until(CTX + 0xc0)
            assert m.state() == before and not m.queue and not m.locked
            assert m.selftest_mail == [dict(command=0x1800081, result=0)]
            assert [(w['address'], w['value'], w['result']) for w in m.selftest_writes] == [
                (0x280701c, 20, 0), (0x2807014, 125, 0), (0x2807018, 64, 0),
                (0x2802134, 80, 0), (0x28059f0, 0, 0)]
            m.supply([0x01000010])
            assert m.runtime_call('cs40l26_handle_mbox_buffer', 123, CTX) == 1
            triggered = m.state()
            assert triggered == dict(vibe_state=1, count=1, asp_active=int(label != 'no-ASP'))
            m.supply([0x01000000])
            assert m.runtime_call('cs40l26_handle_mbox_buffer', 123, CTX) == 1
            finished = m.state()
            stale = label in ['ASP-stop-command-error', 'ASP-start-command-error', 'ASP-PLL-read-error']
            assert finished == dict(vibe_state=0 if label == 'no-ASP' else 1 if stale else 2,
                                    count=0, asp_active=int(label != 'no-ASP')), (label, finished)
            assert m.u32(CTX + 0x228) == 0xffffffff and not m.queue and not m.locked
            assert len([e for e in m.asp_entries if e['function'] == 'cs40l26_asp_start']) == (0 if label == 'no-ASP' else 2)
            assert m.asp_mail == expected_mail * 2
            cases.append(dict(sample=sample, case=label, status='PASS', enable_result=enabled_result,
                              before_FF=before, triggered=triggered, finished=finished, initial_ASP_mailbox=initial_mail,
                              ASP_mailbox=m.asp_mail, ASP_waits=m.asp_waits, clock_updates=m.asp_updates,
                              ASP_entries=m.asp_entries, FF_writes=m.selftest_writes, FF_mailbox=m.selftest_mail,
                              completions=m.completed, notifications=m.notifications,
                              waveform_complete_counter=m.u32(CTX + 0x228)))
            print(sample, label, enabled_result, 'FF mailbox accepted; final', finished, flush=True)
    for p in [SOURCE, SOURCE.with_suffix('.h'), ROOT / 'tests/haptics_driver_capture.cpp']:
        sources[str(p)] = sha(p)
    tests = {str(Path(__file__).resolve().relative_to(ROOT)): sha(Path(__file__))}
    for cls in ASP.mro():
        if cls is object: continue
        p = Path(inspect.getfile(cls)).resolve()
        tests[str(p.relative_to(ROOT))] = sha(p)
    for name in ['haptics_coefficients_emulation.py', 'haptics-emulator-dependencies.json']:
        p = ROOT / 'tests' / name
        tests[str(p.relative_to(ROOT))] = sha(p)
    p = ROOT / 'scripts/firmware_facts.py'
    tests[str(p.relative_to(ROOT))] = sha(p)
    report = dict(status='PASS', scope=__doc__, cases=cases, production_effect=effect.hex(),
                  sources=sources, tests=tests,
                  emulator_files={str(p.relative_to(ROOT)): sha(p) for p in DEPS.rglob('*')
                                  if p.is_file() and (p.suffix in ['.py', '.so'] or '.so.' in p.name)})
    (ROOT / 'logs/haptics-asp-ff-join-review.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS:', len(cases), 'original ASP/FF joined cases; physical output unverified')


if __name__ == '__main__': main()
