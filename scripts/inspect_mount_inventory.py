#!/usr/bin/env python3
"""Inspect shipped fstab declarations, not the runtime partition or GUI list."""
import hashlib
import json
from pathlib import Path
from firmware_facts import boot_parts, ramdisk_entries

ROOT = Path(__file__).resolve().parents[1]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    index=json.loads((ROOT/'simulation-report.json').read_text())
    image=Path(index['image'])
    assert image.is_file() and digest(image)==index['image_sha256']
    _,parts=boot_parts(image.read_bytes())
    entries=ramdisk_entries(parts['ramdisk'])
    fstabs=[rest[-1] for name,mode,*rest in entries if name=='system/etc/recovery.fstab']
    assert len(fstabs)==1
    grouped={}; rows=[]
    for line in fstabs[0].decode().splitlines():
        if not line.strip() or line.lstrip().startswith('#'): continue
        fields=line.split(); assert len(fields)==5
        source,mount,fs,options,flags=fields
        row=dict(source=source,mount_point=mount,filesystem=fs,options=options,flags=flags)
        rows.append(row); grouped.setdefault(mount,[]).append(row)
    raw={'emmc','mtd','bml'}
    groups=[dict(mount_point=mount,filesystems=[r['filesystem'] for r in group],
                 source=group[0]['source'],raw_image=all(r['filesystem'] in raw for r in group),
                 removable_template=any('voldmanaged=' in r['flags'] for r in group))
            for mount,group in grouped.items()]
    report=dict(scope=__doc__,image=str(image),image_sha256=index['image_sha256'],
                status='INSPECTED',fstab_sha256=hashlib.sha256(fstabs[0]).hexdigest(),
                declarations=len(rows),unique_mount_points=len(groups),
                alternate_filesystem_groups=sum(len(g['filesystems'])>1 for g in groups),
                non_raw_mount_declarations=sum(not g['raw_image'] for g in groups),
                groups=groups,rows=rows,
                limitations=['Availability depends on runtime partition presence and parser classification.',
                             'Alternate filesystem rows are declarations, not independent storage devices.',
                             'Removable template can expand at runtime; this is not an exact GUI row count.',
                             'No runtime snapshot, mount, storage selection or phone operation executed.'],
                sources={str(p):digest(p) for p in [Path(__file__).resolve(),ROOT/'scripts/firmware_facts.py',
                    ROOT/'scripts/acquire_firmware.py',Path('/root/AAA/twrp/bootable/recovery/partition.cpp'),
                    Path('/root/AAA/twrp/bootable/recovery/partitionmanager.cpp'),
                    Path('/root/AAA/twrp/bootable/recovery/gui2/backend/twrp_mount_backend.cpp')]})
    output=ROOT/'logs/shipped-mount-inventory.json'
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['declarations','unique_mount_points',
          'alternate_filesystem_groups','non_raw_mount_declarations']},indent=2))

if __name__=='__main__': main()
