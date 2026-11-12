#!/usr/bin/env python3
"""Parse existing user dmesg for Cirrus requests, mailbox completion and faults.

No device commands, synthetic driver execution or electrical/motor inference.
Times are kernel log timestamps; callbacks do not prove physical displacement.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT/'imgs/built/1/touch-after-raw-off.txt'


def main():
    raw = CAPTURE.read_bytes()
    text = raw.decode('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
    records = []
    for line_number, line in enumerate(text.splitlines(), 1):
        match = re.fullmatch(r'\[\s*([\d.]+)\] xring-haptic 0-0043: (.*)', line)
        if match:
            records.append(dict(time=float(match[1]), message=match[2], line=line_number))
    assert records and all(a['time'] <= b['time'] for a,b in zip(records, records[1:]))
    upload_indices = [i for i,r in enumerate(records) if 'cs40l26_upload_effect: effect ID' in r['message']]
    assert len(upload_indices) == 43
    cycles = []
    for number, begin in enumerate(upload_indices):
        end = upload_indices[number+1] if number+1 < len(upload_indices) else len(records)
        chunk = records[begin:end]
        def select(pattern):
            return [r for r in chunk if re.search(pattern, r['message'])]
        def one(pattern):
            values=select(pattern)
            assert len(values)==1,(number,pattern,values)
            return values[0]
        upload = one(r'upload_worker: effect ID = 0 done, cs40l26->upload_ret = 0$')
        sine = one(r'cs40l26_sine_upload: effect->id = 0$')
        play = one(r'cs40l26_playback_effect: effect ID = 0, val = 1$')
        start = one(r'cs40l26_vibe_start_worker: effect ID = 0, duration = \d+$')
        done = one(r'cs40l26_vibe_start_worker: effect ID = 0 done$')
        trigger = one(r'^Mailbox: TRIGGER_CP$')
        complete = one(r'^Mailbox: COMPLETE_MBOX$')
        assert sine['time'] <= upload['time'] <= play['time'] <= start['time'] <= done['time']
        assert start['time'] < trigger['time'] < complete['time']
        duration = int(start['message'].rsplit(' ',1)[1])
        stops = select(r'cs40l26_playback_effect: effect ID = 0, val = 0$')
        brownouts = select(r'^VBST voltage has dropped below brownout threshold$')
        clears = select(r'^Cleared attenuation caused by VBST brownout$')
        assert len(brownouts)==len(clears)
        for flag,clear in zip(brownouts,clears):
            assert flag['time'] < clear['time']
        cycles.append(dict(index=number,upload=upload,play=play,start=start,
            worker_done=done,trigger=trigger,complete=complete,requested_ms=duration,
            trigger_to_complete_ms=round((complete['time']-trigger['time'])*1000,3),
            stop_before_complete=any(r['time'] < complete['time'] for r in stops),
            stops=stops,brownouts=brownouts,attenuation_clears=clears))
    durations = Counter(c['requested_ms'] for c in cycles)
    assert durations == {80:32,106:9,256:2}
    assert sum(bool(c['brownouts']) for c in cycles)==6
    # One rapid re-trigger stops an 80 ms effect near its end; the remaining
    # requests must not be described as all stopped before DSP completion.
    interrupted = [c['index'] for c in cycles if c['stop_before_complete']]
    assert interrupted == [16]
    faults = [r for r in records if 'Failed to write to' in r['message']]
    assert len(faults)==5 and all(r['message']=='Failed to write to 0x13020, attempt(s) = 1' for r in faults)
    assert all(c['trigger_to_complete_ms'] > 0 for c in cycles)
    fault_contexts=[]
    for fault in faults:
        before=[(i,r) for i,r in enumerate(records) if r['line'] < fault['line'] and
                r['message']=='cs40l26_playback_effect: effect ID = 0, val = 0']
        after=[(i,r) for i,r in enumerate(records) if r['line'] > fault['line']]
        assert before and after
        stop=before[-1][1]
        stop_done=next(r for r in records if r['time'] > fault['time'] and r['message']=='cs40l26_vibe_stop_worker: done')
        erase_done=next(r for r in records if r['time'] > fault['time'] and re.fullmatch(
            r'cs40l26_erase_worker: effect ID = 0 done, cs40l26->erase_ret = 0',r['message']))
        next_upload=next(r for r in records if r['time'] > fault['time'] and r['message']=='cs40l26_upload_worker: effect ID = 0 done, cs40l26->upload_ret = 0')
        next_trigger=next(r for r in records if r['time'] > next_upload['time'] and r['message']=='Mailbox: TRIGGER_CP')
        next_complete=next(r for r in records if r['time'] > next_trigger['time'] and r['message']=='Mailbox: COMPLETE_MBOX')
        assert stop['time'] < fault['time'] < stop_done['time'] < erase_done['time'] < next_upload['time'] < next_trigger['time'] < next_complete['time']
        # These are observations in one time window, not transaction IDs.
        # Other PM callers appear between the fault and the state-2 done log.
        pm_events=[r for r in records if stop['line'] < r['line'] < stop_done['line'] and
                   'cs40l26_pm_state_transition:' in r['message']]
        fault_contexts.append(dict(fault=fault,preceding_stop_request=stop,following_stop_worker_done=stop_done,
            erase_worker_done=erase_done,next_upload_done=next_upload,next_trigger=next_trigger,
            next_complete=next_complete,pm_events_in_window=pm_events,
            association='Timestamp/line-order only; capture has no PID/TID or transaction identifier.',
            interpretation='A first-attempt write error lies between a stop request and later PM state-2 done, stop done and erase_ret0 logs. The original stop worker can print done after mailbox failure. The PM state-2 done message is a success-branch observation, but cannot be assigned to this failed write from order alone. Neither final status of this mailbox call nor its causal effect on silence is established.'))
    bindings = [CAPTURE, Path(__file__).resolve(),
        ROOT/'logs/os4-stable-haptics-field-review.disasm',
        ROOT/'logs/os4-stable-haptics-pm-error-review.disasm',
        ROOT/'firmware/samples/os4-stable/analysis/vendor_dlkm/lib/modules/xring_audio_hw_third.ko']
    report = dict(status='OBSERVED',scope=__doc__,capture=str(CAPTURE.relative_to(ROOT)),
        haptics_log_lines=len(records),time_range=[records[0]['time'],records[-1]['time']],
        complete_cycles=len(cycles),duration_counts=dict(durations),cycles=cycles,
        stop_before_complete_cycles=interrupted,mailbox_write_faults=faults,
        fault_time_windows=fault_contexts,
        brownout_cycles=sum(bool(c['brownouts']) for c in cycles),
        normal_duration_cycles_without_brownout=sum(not c['brownouts'] and not c['stop_before_complete'] for c in cycles),
        conclusion='Captured SINE uploads all return0, followed by start-worker completion and paired TRIGGER_CP/COMPLETE_MBOX. This is real driver/mailbox activity, not mere input registration. Six cycles log VBST brownout and subsequent attenuation clear; most cycles show neither brownout nor premature stop.',
        remaining='No electrical voltage/current/displacement, gain/calibration readback, userspace caller identity, kernel-log thread IDs or GUI action correlation. Mailbox completion does not prove perceptible motor vibration. Brownout logs alone cannot establish the cause of all silent effects. The five write errors remain causally unresolved; later logs alone do not establish retry recovery. No new image tested.',
        files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in bindings})
    (ROOT/'logs/haptics-playback-field-observation.json').write_text(json.dumps(report,indent=2)+'\n')
    print('OBSERVED: 43 successful uploads/start+mailbox cycles; 6 brownout cycles; 5 first-attempt mailbox write failures; one early stop')


if __name__=='__main__':main()
