#!/usr/bin/env python3
"""Summarize refresh completion and non-atomic task snapshots without operating a device."""
import argparse,hashlib,json,re
from pathlib import Path

def read(path):
 b=path.read_bytes();return b.decode('utf-16') if b.startswith((b'\xff\xfe',b'\xfe\xff')) else b.decode('utf-8-sig',errors='replace')
def main():
 p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--output',type=Path,required=True);args=p.parse_args();directory=args.directory
 sources={};texts={}
 for name in ['recovery.log','recovery-after.log','recovery-stacks.txt','threads.txt','dmesg.txt','logcat.txt']:
  f=directory/name;texts[name]=read(f);sources[name]=hashlib.sha256(f.read_bytes()).hexdigest()
 text=texts['recovery.log'];lines=text.splitlines();starts=[i for i,s in enumerate(lines) if "operation_start: 'Refreshing Sizes'" in s];assert len(starts)==1
 start=starts[0];end=next((i for i in range(start+1,len(lines)) if 'operation_end - status=' in lines[i]),None)
 sizes=[dict(line=i+1,text=s) for i,s in enumerate(lines) if i>start and (end is None or i<end) and 'Data backup size is' in s]
 before=[int(m.group(1)) for s in lines[:start] if (m:=re.search(r'monotonic_ms=(\d+)',s))];after=[int(m.group(1)) for s in lines[end+1:] if (m:=re.search(r'monotonic_ms=(\d+)',s))] if end else []
 tasks=[]
 for block in texts['recovery-stacks.txt'].split('=== THREAD ')[1:]:
  task=re.search(r'/proc/(\d+)/task/(\d+)',block);stack=re.search(r'STACK\n(.*?)\nSYSCALL',block,re.S)
  if not task:continue
  tasks.append(dict(pid=int(task[1]),tid=int(task[2]),stack=stack[1] if stack else None))
 main=next((t for t in tasks if t['pid']==t['tid'] and 'drm_mode_atomic_ioctl' in (t['stack'] or '')),None)
 report=dict(status='analyzed-unresolved-presentation',inputs=sources,refresh_start_line=start+1,refresh_end_line=end+1 if end is not None else None,refresh_end=lines[end] if end is not None else None,sizes=sizes,completion_elapsed_upper_bound_ms=after[0]-before[-1] if before and after else None,logs_identical=texts['recovery.log']==texts['recovery-after.log'],main_drm_snapshot=main,task_count=len(tasks),conclusion='Refresh completed successfully; captured main-thread stack passes through XRING DRM atomic commit. One separately read stack/wchan/syscall sample does not prove a persistent driver hang or identify which frame was submitted. No data-size worker remains identifiable in captured task list. UI terminal-state publication/render and display presentation remain investigation targets.',scope='User-supplied logs only. No live device operation, no root-cause or fix claim.')
 args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['inputs','main_drm_snapshot']},indent=2))
if __name__=='__main__':main()
