#!/usr/bin/env python3
"""Check generated touch priority and all accepted stock dependency edges."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from generate_profile_runtime import module_plan

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
cases=[];sources={};tests={}
for profile in sorted((ROOT/'dtsrc/O1_asic_dual/profiles').glob('*/profile.json')):
    sample=profile.parent.name;fact=ROOT/'firmware/samples'/sample/'analysis/facts.json'
    lines,report=module_plan(sample,json.loads(fact.read_text()))
    plan=profile.parent/'modules.plan';details=profile.parent/'module-sources.json'
    assert plan.read_text()=='\n'.join(lines)+'\n'
    stored=json.loads(details.read_text())
    # Optional unavailable-dependency records were collected from sets; their
    # presentation order does not alter the executable module plan.
    for key in report:
        if key=='unavailable_optional_softdeps':
            assert sorted(stored[key],key=str)==sorted(report[key],key=str)
        elif key=='conflicting_optional_order':
            normalize=lambda records: sorted((r['owner'],r['after']) for r in records)
            assert normalize(stored[key])==normalize(report[key])
        else:assert stored[key]==report[key],key
    positions={n:i for i,n in enumerate(report['order'])}
    deferred={(r['owner'],r['after']) for r in report['conflicting_optional_order']}
    for n,m in report['modules'].items():
        for dep in m['hard']:assert positions[dep]<positions[n]
        for dep in m['pre']:
            if dep in positions and (n,dep) not in deferred:assert positions[dep]<positions[n]
        for dep in m['post']:
            if dep in positions and (dep,n) not in deferred:assert positions[n]<positions[dep]
    touch,haptic=report['roots']
    assert positions[touch]<positions[haptic]
    assert all(positions[n]<=positions[touch] for n in report['touch_priority_hard_closure'])
    touch_done=max(positions[n] for n in report['touch_priority_hard_closure'])
    haptics_only=set(report['haptics_priority_hard_closure'])-set(report['touch_priority_hard_closure'])
    haptics_start=min(positions[n] for n in haptics_only)
    assert touch_done<haptics_start
    sources.update({str(p):sha(p) for p in [profile,fact,plan,details]})
    cases.append(dict(sample=sample,status='PASS',touch_position=positions[touch],
                      touch_closure_last=touch_done,haptics_closure_first=haptics_start,
                      optional_haptics_position=positions[haptic],
                      scope='All accepted hard/soft edges preserved; touch dependency closure completes before haptics dependency closure.'))
    print('PASS',sample,touch_done,'<',haptics_start)
tests={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__).resolve(),ROOT/'scripts/generate_profile_runtime.py',ROOT/'scripts/firmware_facts.py']}
(ROOT/'logs/touch-priority-plans.json').write_text(json.dumps(dict(status='PASS',cases=cases,sources=sources,tests=tests),indent=2)+'\n')
