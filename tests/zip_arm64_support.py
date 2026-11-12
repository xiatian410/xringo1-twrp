"""Test-only QEMU launch boundary for the production ZIP install chain.

The host parent still executes original extraction, argv construction, pipe,
fork, protocol parser and wait. Its execve boundary launches QEMU/linker with
the extracted ARM64 payload and the unchanged updater arguments. No binfmt,
device, ARM parent process, production updater logic or OTA engine is tested.
"""
import hashlib
import json
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from firmware_facts import boot_parts, ramdisk_entries


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


BRIDGE = r'''
static pid_t target_waitpid(pid_t pid, int* status, int flags) {
  pid_t result=::waitpid(pid,status,flags);
  if(result>0)printf("target_wait_status=%d\n",*status);
  return result;
}
#define waitpid target_waitpid
static int target_execve(const char* path, char* const argv[], char* const envp[]) {
  assert(strcmp(path,"/tmp/updater")==0);
  assert(argv[0] && strcmp(argv[0],path)==0 && argv[1] && argv[2] && argv[3] && !argv[4]);
  std::vector<std::string> args={"/qemu","-L","/android","-E",
    "LD_LIBRARY_PATH=/android/system/lib64","/android/system/bin/linker64",path,
    argv[1],argv[2],argv[3]};
  std::vector<char*> pointers;
  for(auto& s:args)pointers.push_back(s.data());
  pointers.push_back(nullptr);
  return ::execve("/qemu",pointers.data(),envp);
}
#define execve target_execve
'''


class Arm64:
    def __init__(self, android, clang, work):
        clang = clang.parent / 'clang'
        self.image = Path(json.loads((ROOT / 'simulation-report.json').read_text())['image'])
        index = json.loads((ROOT / 'simulation-report.json').read_text())
        assert sha(self.image) == index['image_sha256']
        self.qemu = ROOT / 'tools/qemu-user/qemu-aarch64'
        self.qemu_source = self.qemu.parent / 'source.json'
        assert sha(self.qemu) == json.loads(self.qemu_source.read_text())['binary_sha256']
        self.dependencies = {str(self.qemu): sha(self.qemu)}
        listing = subprocess.run(['ldd', str(self.qemu)], capture_output=True, text=True)
        assert 'statically linked' in listing.stdout + listing.stderr
        for line in (listing.stdout + listing.stderr).splitlines():
            # The pinned qemu is static; refuse silently adding host libraries.
            assert '=>' not in line, line
        self.entries = {}
        _, parts = boot_parts(self.image.read_bytes())
        for name, mode, *rest in ramdisk_entries(parts['ramdisk']):
            if stat.S_ISREG(mode) and (name == 'system/bin/linker64' or
                    (name.startswith('system/lib64/') and name.count('/') == 2 and name.endswith('.so'))):
                self.entries[name] = (rest[-1], mode & 0o777)
        common = work / 'android'; common.mkdir()
        for name, (data, mode) in self.entries.items():
            dest = common / name; dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data); dest.chmod(mode)
        self.files = [self.image, self.qemu, self.qemu_source, Path(__file__), ROOT/'tests/zip_arm64_fixture.c']
        libc = android / 'out/soong/.intermediates/bionic/libc'
        begin = libc / 'crtbegin_dynamic/android_recovery_arm64_armv8-a/crtbegin_dynamic.o'
        end = libc / 'crtend_android/android_recovery_arm64_armv8-a/crtend_android.o'
        self.files += [begin, end, clang, clang.parent/'ld.lld']
        self.binaries = {}
        self.commands = []
        for tag in ['generic', 'arm64', 'undefined']:
            exe = work / ('updater-' + tag)
            command = [str(clang), '--target=aarch64-linux-android35', '-fuse-ld=lld',
                       '-nostdlib', '-fPIE', '-pie', '-Wl,--unresolved-symbols=ignore-all',
                       '-Wl,--dynamic-linker=/system/bin/linker64', str(begin),
                       '-DUPDATER_TAG="'+tag+'"']
            if tag == 'undefined': command += ['-DUNDEFINED_SYMBOL=1']
            command += [str(ROOT/'tests/zip_arm64_fixture.c'), str(common/'system/lib64/libc.so'), str(end), '-o', str(exe)]
            subprocess.run(command, check=True, capture_output=True)
            data = exe.read_bytes()
            assert data[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H', data, 18)[0] == 183
            self.binaries[tag] = data
            self.commands.append(command)

    def stage(self, jail):
        shutil.copyfile(self.qemu, jail/'qemu'); (jail/'qemu').chmod(0o755)
        (jail/'dev').mkdir(); (jail/'dev/null').touch()
        for name, (data, mode) in self.entries.items():
            dest = jail/'android'/name; dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data); dest.chmod(mode)

    def metadata(self):
        return dict(image=str(self.image), image_sha256=sha(self.image),
                    image_entries={p: hashlib.sha256(data).hexdigest() for p,(data,_) in self.entries.items()},
                    payloads={p: hashlib.sha256(data).hexdigest() for p,data in self.binaries.items()},
                    payload_elf_machine={p:struct.unpack_from('<H',data,18)[0] for p,data in self.binaries.items()},
                    compile_commands=self.commands, bridge=BRIDGE, scope=__doc__)
