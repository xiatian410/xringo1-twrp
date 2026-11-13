#!/usr/bin/env python3
"""Run intact ARM64 sideload main/attempter/download against original OS4 ZIP.

BootControl and dynamic mapping are file adapters. Real mounts are refused.
The test expects postinstall block-readonly rejection on an ordinary file AFTER
complete payload download and partition verification, never a full OTA success.
No device is operated. The mount wrapper is a further guard, not a reached step.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

from ota_vabc_session import ROOT, ANDROID, build
sys.path.insert(0, str(ROOT/'scripts'))
from firmware_facts import boot_parts, ramdisk_entries
from acquire_firmware import payload_position


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(8*1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def main():
    index = json.loads((ROOT/'simulation-report.json').read_text())
    image = Path(index['image'])
    assert sha(image) == index['image_sha256']
    source = ROOT/'firmware/samples/os4-stable/original-ota.zip'
    assert sha(source) == 'a1dcfecccf4397943e6836539bea6573ade01c84ef9ee1e360df9c233493f04b'
    with source.open('rb') as f, zipfile.ZipFile(f) as z:
        offset = payload_position(f, z.getinfo('payload.bin'))
        properties = z.read('payload_properties.txt').decode()
    assert offset == 5229
    reference = json.loads((ROOT/'logs/ota-vabc-session.json').read_text())
    qemu = ROOT/'tools/qemu-user/qemu-aarch64'
    assert sha(qemu) == json.loads(qemu.with_name('source.json').read_text())['binary_sha256']
    sources = {str(p): sha(p) for p in [Path(__file__), ROOT/'tests/ota_stock_payload.cpp',
        ROOT/'tests/ota_vabc_session.py', ROOT/'scripts/firmware_facts.py', ROOT/'scripts/acquire_firmware.py']}
    # Reuse only explicit ordinary-file model; no original engine methods changed.
    adapter = (ROOT/'tests/ota_stock_payload.cpp').read_text().split('int main(')[0]
    adapter = adapter.replace('void Cleanup() override { assert(false); }',
                              'void Cleanup() override { printf("BOUNDARY Cleanup file model\\n"); }')
    adapter = adapter.replace('bool ResetUpdate(PrefsInterface*) override { assert(false); return false; }',
                              'bool ResetUpdate(PrefsInterface*) override { return true; }')
    adapter = adapter.replace('override { assert(false); return nullptr; }',
                              'override { return std::make_unique<NoOpAction>(); }', 1)
    adapter = adapter.replace('bool MapAllPartitions() override { ++maps; return true; }', r'''
    bool MapAllPartitions() override {
        ++maps;
        for (const auto& name : dynamic) {
            const auto size = sizes.at(name);
            auto reader = std::make_unique<CowReader>();
            assert(reader->Parse(unique_fd(open(("/work/"+name+".cow").c_str(), O_RDONLY)), kEndOfInstallLabel));
            CompressedSnapshotReader view(std::move(reader), std::nullopt, size);
            unique_fd out(open(("/work/"+name+".bin").c_str(), O_CREAT|O_TRUNC|O_WRONLY, 0600));
            assert(out >= 0);
            std::vector<char> buffer(1024*1024);
            for (uint64_t pos=0; pos<size;) {
                size_t count=std::min(uint64_t(buffer.size()), size-pos);
                assert(view.Read(buffer.data(),count)==ssize_t(count));
                assert(write(out,buffer.data(),count)==ssize_t(count));pos+=count;
            }
            assert(view.Close());
            printf("BOUNDARY mapped COW view %s %llu\n",name.c_str(),(unsigned long long)size);
        }
        fflush(stdout); return true;
    }''')
    adapter += r'''
namespace chromeos_update_engine::boot_control {
std::unique_ptr<BootControlInterface> CreateBootControl() {
    auto boot=std::make_unique<FileBoot>();
    boot->SetDynamicPartitionControl(std::make_unique<FileControl>());
    return boot;
}}
namespace chromeos_update_engine::hardware {
std::unique_ptr<HardwareInterface> CreateHardware() { return std::make_unique<FakeHardware>(); }
}
// Link-time mount boundary: original PostinstallRunnerAction must propagate
// the rejection. No mount syscall or mounted-filesystem success is fabricated.
extern "C" int __wrap_mount(const char*,const char*,const char*,unsigned long,const void*) {
    printf("BOUNDARY denied postinstall mount\n");fflush(stdout);errno=EPERM;return -1;
}
extern "C" int __wrap_umount(const char*) { assert(false);return -1; }
'''
    parent = ROOT/'logs/engine-entry-work'
    parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='run-', dir=parent) as temp:
        work = Path(temp)
        fixture = work/'adapter.cpp'
        fixture.write_text(adapter)
        compile_cmd = reference['compile_command'].copy()
        compile_cmd[compile_cmd.index('-o')+1] = str(work/'adapter.o')
        compile_cmd[compile_cmd.index('-MF')+1] = str(work/'adapter.d')
        compile_cmd[-1] = str(fixture)
        build(compile_cmd)
        for n in shlex.split((work/'adapter.d').read_text().replace('\\\n', ' ').split(':',1)[1]):
            p = ANDROID/n
            if p.is_file() and p != fixture:
                sources[str(p)] = sha(p)
        rsp = ANDROID/'out/soong/.intermediates/system/update_engine/update_engine_sideload/android_recovery_arm64_armv8-a/unstripped/update_engine_sideload.rsp'
        inputs = shlex.split(rsp.read_text())
        original_objects = [n for n in inputs if n.endswith('.o') and not n.endswith('/aosp/hardware_android.o')]
        assert any(n.endswith('/aosp/sideload_main.o') for n in original_objects)
        assert any(n.endswith('/aosp/update_attempter_android.o') for n in original_objects)
        link_cmd = reference['link_command'].copy()
        old = next(n for n in link_cmd if n.endswith('/fixture.o'))
        pos = link_cmd.index(old)
        # Keep original linker flags but use the actual sideload object list.
        link_cmd[pos:pos+1] = [str(work/'adapter.o'), *original_objects]
        link_cmd[link_cmd.index('-o')+1] = str(work/'engine')
        link_cmd += ['-Wl,--wrap=mount', '-Wl,--wrap=umount']
        build(link_cmd)
        elf = (work/'engine').read_bytes()
        assert elf[:6] == b'\x7fELF\x02\x01' and elf[18:20] == b'\xb7\0'
        deps = {str(qemu):sha(qemu),str(rsp):sha(rsp),str(ANDROID/compile_cmd[0]):sha(ANDROID/compile_cmd[0])}
        for n in link_cmd:
            p = ANDROID/n
            if p.is_file() and not p.is_relative_to(work):deps[str(p)]=sha(p)
        for n in original_objects:
            base = n.split('/obj/system/update_engine/',1)[1][:-2]+'.cc'
            p=ANDROID/'system/update_engine'/base
            assert p.is_file();sources[str(p)]=sha(p)
        jail = work/'jail'
        entries = {}
        for name, mode, *rest in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk']):
            if stat.S_ISREG(mode) and (name=='system/bin/linker64' or name=='system/etc/security/otacerts.zip' or
                    (name.startswith('system/lib64/') and name.endswith('.so'))):
                dest=jail/name if name=='system/etc/security/otacerts.zip' else jail/'android'/name
                dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(rest[-1]);dest.chmod(mode&0o777)
                entries[name]=hashlib.sha256(rest[-1]).hexdigest()
        for directory in ['work','dev','proc/sys/kernel/random','postinstall']:
            (jail/directory).mkdir(parents=True,exist_ok=True)
        (jail/'dev/null').touch()
        (jail/'proc/sys/kernel/random/boot_id').write_text('11111111-2222-3333-4444-555555555555\n')
        (jail/'proc/mounts').write_text('')
        os.link(source,jail/'work/source.zip')
        shutil.copyfile(qemu,jail/'qemu');(jail/'qemu').chmod(0o755)
        shutil.copyfile(work/'engine',jail/'engine');(jail/'engine').chmod(0o755)
        def isolate():
            os.chroot(jail);os.chdir('/')
        command=['/qemu','-L','/android','-E','LD_LIBRARY_PATH=/android/system/lib64',
            '/android/system/bin/linker64','/engine','--payload=file:///work/source.zip',
            '--offset='+str(offset),'--headers='+properties,'--status_fd=1']
        stdout=ROOT/'logs/ota-engine-entry.stdout';stderr=ROOT/'logs/ota-engine-entry.stderr'
        with stdout.open('w') as out,stderr.open('w') as err:
            run=subprocess.run(command,preexec_fn=isolate,stdout=out,stderr=err,timeout=1800)
        output=stdout.read_text();errors=stderr.read_text()
        inventory_path=ROOT/'firmware/samples/os4-stable/inventory.json'
        inventory=json.loads(inventory_path.read_text())
        hashes=dict(re.findall(r'Hash of ([A-Za-z0-9_]+): ([A-F0-9]{64})',errors))
        hash_match={n:h.lower() for n,h in hashes.items()}=={n:p['sha256'] for n,p in inventory['partitions'].items()}
        expected=(run.returncode==63 and hash_match and
            'FilesystemVerifierAction with code ErrorCode::kSuccess' in errors and
            'PostinstallRunnerAction with code ErrorCode::kPostInstallMountError' in errors and
            'Marking block device /work/system.bin as read_only=1: Inappropriate ioctl for device' in errors and
            'BOUNDARY denied postinstall mount' not in output and
            'Completed 4933/4933 operations (100%), 7883589123/7883589123 bytes downloaded (100%)' in errors and
            'Payload hash matches value in payload.' in errors)
        report=dict(status='PASS' if expected else 'FAIL',scope=__doc__,returncode=run.returncode,
            image_sha256=sha(image),source_zip_sha256=sha(source),sources=sources,dependencies=deps,
            image_entries=entries,adapter_sha256=hashlib.sha256(adapter.encode()).hexdigest(),
            fixture_elf_machine=183,fixture_sha256=sha(work/'engine'),compile_command=compile_cmd,link_command=link_cmd,
            stdout=output,stderr_sha256=sha(stderr),full_ota_install=False,actual_engine_entry=True,
            actual_download_action=True,snapshot_manager_executed=False,postinstall_mount_reached=False,
            postinstall_block_readonly_rejected=True,partition_hashes=hashes,
            inventory_sha256=sha(inventory_path),stdout_sha256=sha(stdout))
        (ROOT/'logs/ota-engine-entry.json').write_text(json.dumps(report,indent=2)+'\n')
        print(report['status'],'intact engine entry; return',run.returncode,flush=True)
        return 0 if expected else 1


if __name__ == '__main__':
    sys.exit(main())
