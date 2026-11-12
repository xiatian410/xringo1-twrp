#!/usr/bin/env python3
"""Execute stock OS4 regmap IRQ pre-callback and its registered mailbox child.

Actual relocated chip data supplies the callback and context; no post callback
is installed. PM and regmap services remain fixtures. The explicitly selected
child is invoked after pre according to the saved upstream v6.18 contract,
which ignores the pre return; this does not execute the kernel regmap IRQ core,
status/mask dispatch, concurrent PM, physical interrupts or a motor. Every child
message is synthetic. Direct pre results and optional child results are separate.
"""
import json
from pathlib import Path
import subprocess
from haptics_irq_completion_emulation import IRQ, ROOT, CTX, sha


def exercise(path, blobs, props):
    cases = []
    for label in ['status-bit-set', 'status-bit-clear', 'status-read-error', 'PM-resume-error',
                  'pre-error-selected-child', 'status-clear-selected-child']:
        m = IRQ(path, blobs, props)
        assert m.run('cs40l26_probe', CTX) == 0 and not m.locked
        chip, = [s['args'][5] for s in m.irq_services if s['name']=='devm_regmap_add_irq_chip']
        assert chip == m.symbols['cs40l26_regmap_irq_chip']
        assert m.u64(chip+0x68) == m.symbols['cs40l26_handle_pre_irq']
        assert m.u64(chip+0x70) == 0 and m.u64(chip+0x90) == CTX
        assert m.u32(chip+0x58) == 27
        m.hardware[0x10004] = int(label == 'status-bit-set')
        if label in ['status-read-error', 'pre-error-selected-child']:
            m.read_errors[0x10004] = -5
        if label == 'PM-resume-error':
            m.pm_error = -5
        first_read, first_pm, first_message = len(m.reads), len(m.pm_services), len(m.messages)
        rc = m.run('cs40l26_handle_pre_irq', m.u64(chip+0x90))
        reads, pm, messages = m.reads[first_read:], m.pm_services[first_pm:], m.messages[first_message:]
        assert rc == (-5 if label in ['status-read-error', 'pre-error-selected-child', 'PM-resume-error'] else 0)
        if label == 'PM-resume-error':
            assert not reads
            assert [s['name'] for s in pm] == ['__pm_runtime_resume','__pm_runtime_set_status','__pm_runtime_suspend']
            assert pm[0]['result'] == -5
        else:
            assert len(reads) == 1 and reads[0]['address'] == 0x10004
            assert reads[0]['result'] == (-5 if label in ['status-read-error', 'pre-error-selected-child'] else 0)
            assert [s['name'] for s in pm] == ['__pm_runtime_resume','__pm_runtime_suspend']
        child = None
        if label.endswith('selected-child'):
            # Deliberate host scheduling contract: original regmap IRQ core
            # is not executed and no claim about real status selection follows.
            m.put32(CTX+0x200, 1); m.put32(CTX+0x1d0, 1)
            m.supply([0x01000000])
            child = m.dispatch()
            assert child == 1 and m.completed[-1] == ['complete_all',CTX+0x228]
            assert m.u32(CTX+0x200) == m.u32(CTX+0x1d0) == 0
        assert not m.locked
        print('PASS',label,rc,'child',child,flush=True)
        cases.append(dict(case=label,status='PASS',pre_result=rc,child_result=child,
            chip=dict(pre=m.u64(chip+0x68),post=m.u64(chip+0x70),context=m.u64(chip+0x90),children=m.u32(chip+0x58)),
            pre_reads=reads,pre_PM=pm,pre_messages=messages,completions=m.completed,
            state=m.u32(CTX+0x1d0),event_count=m.u32(CTX+0x200),ack_writes=m.acks))
    return cases


def main():
    path = ROOT/'logs/haptics-irq-completion-emulation.json'
    previous = json.loads(path.read_text())
    sources = dict(previous['sources']);sources[str(path.relative_to(ROOT))]=sha(path)
    upstream = ROOT/'logs/upstream-linux-v6.18-regmap-irq.c'
    body=upstream.read_text()
    assert 'chip->handle_pre_irq(chip->irq_drv_data);' in body
    assert 'if (chip->handle_post_irq)' in body
    sources[str(upstream.relative_to(ROOT))]=sha(upstream)
    tests=dict(previous['tests'])
    tests['tests/haptics_irq_completion_emulation.py']=sha(ROOT/'tests/haptics_irq_completion_emulation.py')
    tests[str(Path(__file__).resolve().relative_to(ROOT))]=sha(Path(__file__))
    for mapping in [sources,tests,previous['emulator_files']]:
        for name,expected in mapping.items():
            p=Path(name) if Path(name).is_absolute() else ROOT/name
            assert sha(p)==expected
    dt=json.loads((ROOT/'logs/haptics-devicetree-audit.json').read_text());cases=[]
    for sample,record in previous['drivers'].items():
        module=ROOT/record['path'];assert sha(module)==record['sha256']
        props=next(c for c in dt['cases'] if c['sample']==sample and c['case']=='overlay-5')['haptics']['/soc/i2c@EC100000/cs40l26@43']['properties']
        blobs={p.name:p.read_bytes() for p in (ROOT/'firmware/samples'/sample/'analysis/odm/firmware').glob('cs40l26*')}
        disasm=ROOT/'logs'/f'{sample}-haptics-pre-irq-core.disasm'
        tool='/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump'
        disasm.write_bytes(subprocess.check_output([tool,'-dr','--disassemble-symbols=cs40l26_request_irq,cs40l26_handle_pre_irq,cs40l26_pm_enter,cs40l26_pm_exit',str(module)]))
        sources[str(disasm.relative_to(ROOT))]=sha(disasm)
        cases.extend(dict(sample=sample,**c) for c in exercise(module,blobs,props))
    (ROOT/'logs/haptics-pre-irq-emulation.json').write_text(json.dumps(dict(status='PASS',scope=__doc__.strip(),
        cases=cases,drivers=previous['drivers'],sources=sources,tests=tests,emulator_files=previous['emulator_files']),indent=2)+'\n')
    print('PASS',len(cases),'cases',flush=True)


if __name__=='__main__':main()
