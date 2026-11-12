#!/usr/bin/env python3
"""Bind requested-filesystem conversion correction to the clean-built image.

Checks conversion dispatch/result state; reuses unchanged directory/media evidence.
No hardware, complete format/GUI lifecycle, concurrent writer or power-loss claim.
"""
import hashlib
import json
from pathlib import Path
from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT, ANDROID, TREE, manifest
import sys
sys.path.insert(0, str(ROOT/"tests"))
from nested_partition_path_test import method


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    image=ROOT/'imgs/built/recovery-dijun-unified-format-transition.img'
    sources=json.loads(image.with_name(image.stem+'-sources.json').read_text())
    assert sha(image)==sources['image_sha256']
    assert sources['jobs']==30
    for path,digest in sources['files'].items():
        assert sha(path)==digest,path
    build=ROOT/sources['build_log']
    assert sha(build)==sources['build_log_sha256']
    text=build.read_text()
    assert 'Deleted images and staging directories' in text
    assert text.count('build completed successfully')==2
    assert 'recovery clang++ partition.cpp' in text
    assert manifest(TREE)==manifest(ANDROID/'device/xiaomi/O1_asic')
    assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/format-transition-final-source.log').read_text()
    spec=json.loads((TREE/'patches/series.json').read_text())['repositories']['bootable/recovery']
    patch=spec['patches'][-1]
    assert patch['file']=='0076-filesystem-conversion-dispatch.patch'
    assert sha(TREE/'patches'/patch['file'])==patch['sha256']
    reports={}
    bound={}
    for name,count,failures in [('format-transition',25,0),('format-transition-before',25,10)]:
        path=ROOT/'logs'/f'{name}.json';report=json.loads(path.read_text())
        assert len(report['cases'])==count
        assert sum(c['status']=='FAIL' for c in report['cases'])==failures
        assert report['status']==('FAIL' if failures else 'PASS')
        for file,digest in report['sources'].items():
            assert sha(file)==digest,file
        bound[name]=report
        reports[name]=dict(sha256=sha(path),cases=count,failures=failures,status=report['status'])
    for path,digest in bound['format-transition']['sources'].items():
        if not path.endswith('/partition.cpp'):
            assert bound['format-transition-before']['sources'][path]==digest,path
    old_partition=ROOT/'logs/format-transition-before/partition.cpp'
    reuse_signatures={
        'manager-wipe':['void TWPartition::RecreateMediaFolder()'],
        'media-wipe':['bool TWPartition::WipeDataWithoutWipingMedia()', 'bool TWPartition::WipeDataWithoutWipingMediaFunc('],
    }
    for name,count in [('manager-wipe',16),('media-wipe',13)]:
        path=ROOT/'logs'/f'{name}.json';report=json.loads(path.read_text())
        assert report['status']=='PASS' and len(report['cases'])==count
        for file,digest in report['sources'].items():
            if file==str(ANDROID/'bootable/recovery/partition.cpp'):
                assert sha(old_partition)==digest
                for sig in reuse_signatures[name]:
                    assert method(old_partition.read_text(),sig)==method(Path(file).read_text(),sig)
            elif file==str(ANDROID/'bootable/recovery/partitionmanager.cpp') and name=='media-wipe':
                old_manager=ROOT/'logs/manager-wipe-before/partitionmanager.cpp'
                assert sha(old_manager)==digest
                for sig in ['bool TWPartitionManager::MatchesPath(', 'TWPartition* TWPartitionManager::FindPartitionByPath(', 'int TWPartitionManager::WipeByPath(const std::string& Path) const']:
                    assert method(old_manager.read_text(),sig)==method(Path(file).read_text(),sig)
            else:
                assert sha(file)==digest,file
        reports[name]=dict(sha256=sha(path),cases=count,status='PASS',reused=True,
                           reason='Every executed method in changed source files byte-identical; other bound sources unchanged. Wipe dispatch was explicitly a fixture in those suites.')
    def entries(path):
        return {e[0]:(e[1],e[-1]) for e in ramdisk_entries(boot_parts(path.read_bytes())[1]['ramdisk'])}
    old=entries(ROOT/'imgs/built/recovery-dijun-unified-manager-wipe.img');new=entries(image)
    changed=sorted(n for n in old.keys()|new.keys() if old.get(n)!=new.get(n))
    assert changed==['prop.default','ramdisk-files.sha256sum','system/bin/recovery']
    assert new['system/bin/recovery'][1]==(ANDROID/'out/target/product/O1_asic/recovery/root/system/bin/recovery').read_bytes()
    package=json.loads(image.with_suffix('.json').read_text())
    assert package['sha256']==sha(image) and len(package['profiles'])==6
    index=json.loads((ROOT/'simulation-report.json').read_text())
    assert index['image_sha256']==sha(image) and index['status']=='in_progress'
    assert len(index['not_yet_completed'])==12
    result=dict(status='PASS',scope=__doc__,image=str(image),image_sha256=sha(image),production_sources=len(sources['files']),reports=reports,changed_ramdisk_entries=changed,hardware_testing=False,full_filesystem_lifecycle=False)
    (ROOT/'logs/format-transition-delivery.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: conversion25 / old10 failures; reused unchanged manager16 + media13; clean build /',len(sources['files']),'sources / six profiles')


if __name__=='__main__':main()
