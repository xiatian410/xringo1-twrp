#!/usr/bin/env python3
"""Parse supplied field capture; never operate a device or infer restored touch."""
import hashlib
import json
from pathlib import Path
import re
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT/'imgs/built/1/touch-v1-debug'


def main():
    files = {p.name:p.read_bytes() for p in DIRECTORY.iterdir() if p.is_file()}
    text = {name:data.decode('utf-16' if data.startswith((b'\xff\xfe',b'\xfe\xff'))
                            else 'utf-8-sig') for name,data in files.items()}
    start = float(text['start-uptime.txt'].split()[0])
    end = float(text['end-uptime.txt'].split()[0])
    assert 0 < end-start < 30
    headers = re.findall(r'\[\s*([\d.]+)\].*syna_tcm_v1_read_message: Status code: '
                         r'(0x[0-9a-f]+), length: (\d+) \(([^)]+)\)',text['dmesg-stream.txt'])
    headers = [h for h in headers if start <= float(h[0]) <= end]
    assert len(headers)==170
    assert {(h[1],h[2],h[3]) for h in headers}=={('0xc0','1664','a5 c0 80 06')}
    assert text['raw-mode.txt'].strip()=='1'
    assert 'Application Firmware, 0x01' in text['controller-info.txt']
    assert 'TouchComm version:  1' in text['controller-info.txt']
    assert text['getevent-exit.txt'].strip() in ('124','137')
    assert text['dmesg-stream-exit.txt'].strip() in ('124','137')
    assert not re.search(r'\bEV_(ABS|KEY|SYN)\b',text['events.txt'])
    assert 'Xiaomi_Touch_Input_0' in text['events.txt']
    levels={}
    for phase in ['before','during','after']:
        match=re.search(r'current xiaomi_touch log_level = (\d+), vendor log_level = (\d+)',
                        text[f'log-level-{phase}.txt'])
        assert match
        levels[phase]=list(map(int,match.groups()))
    assert levels=={'before':[3,1],'during':[3,4],'after':[3,1]}
    deltas={}
    for name in ['spi_dma_irq','xiaomi_tpsynaptics_tcm']:
        counters=[]
        for phase in ['before','after']:
            lines=text[f'interrupts-{phase}.txt'].splitlines()
            cpus=len(next(line.split() for line in lines if re.fullmatch(r'\s*CPU\d+(?:\s+CPU\d+)*\s*',line)))
            line=next(line for line in lines if line.split() and line.split()[-1]==name)
            counters.append(sum(map(int,line.split()[1:cpus+1])))
        assert counters[1]-counters[0]==170
        deltas[name]={'before':counters[0],'after':counters[1],'delta':170}
    review=['logs/os4-stable-touch-isr.disasm','logs/os4-stable-touch-wrapper-core.disasm']
    report={'status':'OBSERVED','scope':__doc__,'capture_start':start,'capture_end':end,
            'header_count':len(headers),'report_counts':dict(Counter(h[1] for h in headers)),
            'payload_lengths':sorted({int(h[2]) for h in headers}),
            'header_time_range':[float(headers[0][0]),float(headers[-1][0])],
            'raw_mode_cached_value':1,'log_levels':levels,'irqs':deltas,
            'saved_input_events':0,'capture_exits':{n:int(text[n].strip()) for n in
                                                  ['getevent-exit.txt','dmesg-stream-exit.txt']},
            'conclusion':'In this capture the v1 driver reads raw report 0xc0 only, while raw-mode sysfs is 1. Original ISR routes c0 to raw-frame handling and only 0x11 to ordinary touch parser/input. This identifies a concrete report-mode mismatch for Recovery.',
            'remaining':'No controller payload dump, no observed switch to 0x11 or restored coordinates, and no identification of what enabled raw. Sysfs store can hide callback errors; reading zero after writing zero is not proof of controller acceptance.',
            'files':{str((DIRECTORY/n).relative_to(ROOT)):hashlib.sha256(data).hexdigest() for n,data in files.items()},
            'sources':{str(Path(__file__).relative_to(ROOT)):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
            'review_sources':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in review}}
    (ROOT/'logs/touch-v1-debug-observation.json').write_text(json.dumps(report,indent=2)+'\n')
    print('OBSERVED: 170 raw c0/1664 headers, +170 touch/SPI IRQ, raw=1, no input; verbosity restored')


if __name__=='__main__':main()
