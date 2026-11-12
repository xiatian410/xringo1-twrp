#!/usr/bin/env python3
"""Validate bounded multi-cluster recordings, frame IDs and native decoder seeks."""
import hashlib
import json
from pathlib import Path
import sys
import subprocess

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from video_timeline_test import elements

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    path=ROOT/'logs/video-timeline.json'
    report=json.loads(path.read_text())
    assert report['status']=='PASS' and len(report['cases'])==3
    for name,digest in {**report['sources'],**report['tools']['linked_files']}.items():
        assert sha(Path(name))==digest,name
    assert report['tools']==json.loads((ROOT/'tools/ffmpeg-host/source.json').read_text())
    for item in report['tools']['packages'].values():
        assert sha(ROOT/item['file'])==item['sha256']
        assert 'SHA256: '+item['sha256'] in item['apt_metadata']
    assert {c['fps'] for c in report['cases']}=={15,30,60}
    for c in report['cases']:
        fps=c['fps'];count=(12500*fps+999)//1000
        assert c['status']=='PASS' and c['duration_seconds']==12.5
        assert c['frames']==c['frame_ids_checked']==count
        assert c['pts_ms']==[i*1000//fps for i in range(count)]
        assert c['keyframe_ids']==[0,5*fps,10*fps]
        blob=(ROOT/c['artifact']).read_bytes()
        assert hashlib.sha256(blob).hexdigest()==c['sha256']
        segment,=[(a,b) for kind,a,b,_ in elements(blob,0,len(blob)) if kind==0x18538067]
        children=list(elements(blob,*segment))
        clusters=[dict(position=p,length=b-a) for k,a,b,p in children if k==0x1f43b675]
        assert c['clusters']==clusters and len(clusters)==3
        assert c['cues'] is False and not any(k==0x1c53bb6b for k,*_ in children)
        assert [s['target_seconds'] for s in c['seeks']]==[0,4.95,5,5.05,9.95,10,10.05,12.4,12.49,12.6]
        for seek in c['seeks']:
            index=next((i for i,t in enumerate(c['pts_ms']) if t+.001>=1000*seek['target_seconds']),None)
            assert seek['frame_id']==index
            assert seek['pts_ms']==(None if index is None else c['pts_ms'][index])
            command=seek['command']
            assert command[command.index('-c:v')+1]=='vp8' and '-copyts' in command
            assert command[command.index('-ss')+1]==str(seek['target_seconds'])
            if index is None:assert seek['decoded_sha256']==hashlib.sha256(b'').hexdigest()
            else:assert '(vp8 (native) -> rawvideo (native))' in seek['log']
    index=json.loads((ROOT/'simulation-report.json').read_text())
    check,=[c for c in index['checks'] if c['name']=='video-multicluster-timeline-and-seek']
    assert check['count']==3 and check['evidence_sha256']==sha(path)
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    image=Path(index['image']);assert sha(image)==index['image_sha256']
    production=json.loads(image.with_name(image.stem+'-sources.json').read_text())
    for name,digest in report['sources'].items():
        if name.startswith('/root/AAA/twrp/bootable/recovery/'):
            if name.endswith('.cpp'):
                if name in production['files']:
                    assert production['files'][name]==digest
                else:
                    relative=name.removeprefix('/root/AAA/twrp/bootable/recovery/')
                    head=production['source_repositories']['bootable/recovery']['head']
                    baseline=subprocess.check_output(['git','-C','/root/AAA/twrp/bootable/recovery',
                                                      'show',head+':'+relative])
                    assert hashlib.sha256(baseline).hexdigest()==digest
    docs=['ADAPTATION-GOALS.md','simulation-report.md','simulation-report.json','MAINTENANCE.md',
          'FEATURE-USAGE.md','docs/VIDEO-FRAMES-VALIDATION.md']
    output=dict(status='PASS',scope=__doc__,files=3,decoded_frame_ids=1313,seeks=30,
                evidence_sha256=sha(path),image_sha256=index['image_sha256'],production_change=False,
                documents={n:sha(ROOT/n) for n in docs},audit_script_sha256=sha(Path(__file__)))
    (ROOT/'logs/video-timeline-delivery.json').write_text(json.dumps(output,indent=2)+'\n')
    print('PASS:3 files/1313 frame IDs/30 seeks/3 clusters and keyframes each; no target performance claim')

if __name__=='__main__':main()
