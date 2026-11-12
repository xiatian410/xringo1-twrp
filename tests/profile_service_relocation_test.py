#!/usr/bin/env python3
"""Run unmodified ARM64 security-service relocation, stopping before constructors.

Image linker and original six-profile ELF bytes execute via QEMU in a private
chroot. RSP sets one debugger breakpoint at the linker's pre-init call site;
no relocation result is substituted, no service constructor/main/Binder/TEE runs.
Exact image ld.config and init LD_LIBRARY_PATH are staged. Missing /proc and
Android properties remain boundaries; this is not a complete init boot.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from verify_devicefix import entries

ANDROID = Path('/root/AAA/twrp')
BIN = ANDROID / 'prebuilts/clang/host/linux-x86/clang-r547379/bin'
LINK = ANDROID / 'out/soong/.intermediates/bionic/linker/linker.recovery/android_recovery_arm64_armv8-a'
QEMU = ROOT / 'tools/qemu-user/qemu-aarch64'
SERVICES = ['vendor/bin/tee-supplicant',
            'vendor/bin/hw/android.hardware.security.keymint@3.0-service.mitee',
            'vendor/bin/hw/android.hardware.gatekeeper-service.mitee']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def segments(data):
    off = struct.unpack_from('<Q', data, 32)[0]
    size, count = struct.unpack_from('<HH', data, 54)
    result = []
    for i in range(count):
        kind, flags, pos, addr, _, length, memory, _ = struct.unpack_from('<IIQQQQQQ', data, off + i*size)
        if kind == 1:
            result.append((flags, addr, pos, length, memory))
    return result


class Remote:
    def __init__(self, sock):
        self.sock = sock

    def exact(self, count):
        data = b''
        while len(data) < count:
            chunk = self.sock.recv(count-len(data))
            if not chunk:
                raise RuntimeError('QEMU RSP closed')
            data += chunk
        return data

    def cmd(self, command):
        data = command.encode()
        self.sock.sendall(b'$' + data + b'#' + f'{sum(data)%256:02x}'.encode())
        while self.exact(1) != b'$':
            pass
        response = b''
        while (byte := self.exact(1)) != b'#':
            response += byte
        assert int(self.exact(2), 16) == sum(response) % 256
        self.sock.sendall(b'+')
        return response

    def memory(self, address, count):
        data = bytes.fromhex(self.cmd(f'm{address:x},{count:x}').decode())
        assert len(data) == count
        return data

    def u64(self, address):
        return int.from_bytes(self.memory(address, 8), 'little')

    def string(self, address):
        data = b''
        for offset in range(0, 4096, 16):
            chunk = self.memory(address+offset, 16)
            if b'\0' in chunk:
                return (data+chunk.split(b'\0')[0]).decode()
            data += chunk
        raise AssertionError('Unterminated target string')

    def pc(self):
        # AArch64 g packet: x0..x30, sp, pc, cpsr.
        return int.from_bytes(bytes.fromhex(self.cmd('g').decode())[256:264], 'little')


def main():
    index = json.loads((ROOT / 'simulation-report.json').read_text())
    image = Path(index['image'])
    raw, archive = entries(image)
    assert sha(raw) == index['image_sha256']
    unstripped = (LINK / 'unstripped/linker64').read_bytes()
    linker = archive['system/bin/linker64'][-1]
    # Stripping changes ELF headers/symbol sections, not executable/load data.
    load_bindings = []
    for flags, addr, pos, length, memory in segments(linker):
        if flags & 1 or flags & 2:
            other = next(s for s in segments(unstripped) if s[1] == addr)
            assert linker[pos:pos+length] == unstripped[other[2]:other[2]+other[3]]
            load_bindings.append(dict(flags=flags, address=addr, sha256=sha(linker[pos:pos+length])))
    symbols = subprocess.check_output([str(BIN/'llvm-nm'), str(LINK/'unstripped/linker64')], text=True)
    symbol = {line.split()[2]: int(line.split()[0], 16) for line in symbols.splitlines() if len(line.split()) == 3}
    disasm = subprocess.check_output([str(BIN/'llvm-objdump'), '-d', str(LINK/'unstripped/linker64')], text=True)
    calls = re.findall(r'^\s*([0-9a-f]+):.*\bbl\s+0x[0-9a-f]+ <__dl__ZN6soinfo26call_pre_init_constructorsEv>', disasm, re.M)
    assert len(calls) == 1
    stop = int(calls[0], 16)
    entry = struct.unpack_from('<Q', linker, 24)[0]
    ldd = symbol['__dl_g_is_ldd']
    debug = symbol['__dl__r_debug']
    qemu_metadata = json.loads((QEMU.parent/'source.json').read_text())
    assert sha(QEMU.read_bytes()) == qemu_metadata['binary_sha256']
    bound = {}
    def get(name):
        row = archive[name]
        assert stat.S_ISREG(row[1])
        bound[name] = sha(row[-1])
        return row[-1], row[1] & 0o777
    def put(jail, name, data, mode=0o644):
        path = jail / name.lstrip('/')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(mode)
        return path
    common = [n for n, row in archive.items() if stat.S_ISREG(row[1]) and
              (n in ['system/bin/linker64', 'system/etc/ld.config.txt'] or
               (n.startswith('system/lib64/') and n.count('/') == 2 and n.endswith('.so')))]
    init, _ = get('system/etc/init/dijun-mitee.rc')
    paths = re.findall(r'^\s+setenv LD_LIBRARY_PATH (.+)$', init.decode(), re.M)
    assert paths == ['/system/lib64/mitee:/system/lib64'] * 3
    profiles = sorted(n.split('/')[4] for n in archive if n.startswith('system/etc/dijun/profiles/') and n.endswith('/runtime-files.list'))
    assert len(profiles) == 6
    cases = []
    env = {k: v for k, v in os.environ.items() if not k.startswith(('LD_', 'QEMU_'))}
    with tempfile.TemporaryDirectory(prefix='dijun-service-relocation-') as temp:
        base = Path(temp)
        for profile in profiles:
            jail = base/profile
            for name in common:
                data, mode = get(name)
                put(jail, name, data, mode)
            inventory, _ = get(f'system/etc/dijun/profiles/{profile}/runtime-files.list')
            for line in inventory.decode().splitlines():
                digest, mode, name = line.split()
                if name.startswith(('/system/lib64/mitee/', '/vendor/bin/')):
                    data, _ = get('system/etc/dijun/blobs/'+digest)
                    assert sha(data) == digest
                    put(jail, name, data, int(mode, 8))
            shutil.copyfile(QEMU, jail/'qemu')
            (jail/'qemu').chmod(0o755)
            put(jail, 'dev/null', b'')  # ordinary file, never a device
            for service in SERVICES:
                with socket.socket() as probe:
                    probe.bind(('127.0.0.1', 0))
                    port = probe.getsockname()[1]
                log = base/'stderr'
                command = ['chroot', str(jail), '/qemu', '-g', str(port), '-E',
                           'LD_LIBRARY_PATH='+paths[0], '/system/bin/linker64', '/'+service]
                with log.open('wb') as err:
                    proc = subprocess.Popen(command, env=env, stdout=err, stderr=err)
                    sock = None
                    try:
                        deadline = time.monotonic()+5
                        while sock is None:
                            try:
                                sock = socket.create_connection(('127.0.0.1', port), timeout=.5)
                            except ConnectionRefusedError:
                                assert proc.poll() is None and time.monotonic() < deadline
                                time.sleep(.01)
                        sock.settimeout(15)
                        remote = Remote(sock)
                        assert remote.cmd('?').startswith(b'T05')
                        load = remote.pc()-entry
                        # Code at breakpoint is the original BL pre-init call.
                        text = next(s for s in segments(linker) if s[1] <= stop < s[1]+s[3])
                        pos = text[2]+stop-text[1]
                        assert remote.memory(load+stop, 4) == linker[pos:pos+4]
                        assert remote.cmd(f'Z0,{load+stop:x},4') == b'OK'
                        status = remote.cmd('c')
                        assert status.startswith(b'T05') and remote.pc() == load+stop, (profile, service, status)
                        assert remote.memory(load+ldd, 1) == b'\0', '--list must not be active'
                        # Original debugger ABI exposes every loaded object. No
                        # soinfo layout guess, target function call or patching.
                        link = remote.u64(load+debug+8)
                        loaded = []
                        seen = set()
                        while link:
                            assert link not in seen and len(seen) < 128
                            seen.add(link)
                            address, name, dynamic, following, previous = struct.unpack('<QQQQQ', remote.memory(link, 40))
                            path = remote.string(name)
                            if path == '[vdso]':
                                loaded.append(dict(path=path))
                            else:
                                file = jail/path.lstrip('/')
                                assert path.startswith(('/system/', '/vendor/')) and file.is_file(), path
                                loaded.append(dict(path=path, sha256=sha(file.read_bytes())))
                            link = following
                        assert any(row['path'] == '/'+service for row in loaded)
                        for row in loaded:
                            private = jail/'system/lib64/mitee'/Path(row['path']).name
                            if private.is_file():
                                assert row['path'].startswith('/system/lib64/mitee/'), row
                        cases.append(dict(profile=profile, service=service, case='relocated-before-constructors',
                                          status='PASS', stop_offset=stop, g_is_ldd=0, loaded=loaded))
                    finally:
                        if sock is not None:
                            sock.close()
                        if proc.poll() is None:
                            proc.kill()
                        proc.wait(timeout=5)
                cases[-1]['stderr'] = log.read_text()
                print('PASS', profile, service, len(loaded), flush=True)
            # Mutate only the private control copy's undefined-symbol name.
            # The preceding three service runs use exact, unmodified CAS bytes.
            program = jail/SERVICES[0]
            original = program.read_bytes()
            assert original.count(b'\0dump_buffer\0') == 1
            program.write_bytes(original.replace(b'\0dump_buffer\0', b'\0bad_missing\0'))
            result = subprocess.run(['chroot', str(jail), '/qemu', '-E', 'LD_LIBRARY_PATH='+paths[0],
                                     '/system/bin/linker64', '/'+SERVICES[0]], env=env, capture_output=True, text=True, timeout=15)
            assert result.returncode != 0 and 'cannot locate symbol "bad_missing"' in result.stderr
            cases.append(dict(profile=profile, case='undefined-symbol-control', status='PASS',
                              original_sha256=sha(original), control_sha256=sha(program.read_bytes()),
                              mutation='undefined dump_buffer -> bad_missing (equal length)',
                              exit=result.returncode, stderr=result.stderr))
            program.write_bytes(original)
            # Missing-library control runs normally but fails before app code.
            private = jail/'system/lib64/mitee/libteecli.so'
            private.rename(private.with_suffix('.hidden'))
            result = subprocess.run(['chroot', str(jail), '/qemu', '-E', 'LD_LIBRARY_PATH='+paths[0],
                                     '/system/bin/linker64', '/'+SERVICES[0]], env=env, capture_output=True, text=True, timeout=15)
            assert result.returncode != 0 and 'libteecli.so' in result.stderr and 'not found' in result.stderr
            cases.append(dict(profile=profile, case='missing-tee-library', status='PASS', exit=result.returncode, stderr=result.stderr))
    sources = [Path(__file__).resolve(), QEMU, QEMU.parent/'source.json', LINK/'unstripped/linker64',
               BIN/'llvm-nm', BIN/'llvm-objdump', ROOT/'scripts/verify_devicefix.py',
               ANDROID/'bionic/linker/linker_main.cpp', ANDROID/'bionic/linker/linker_relocate.cpp',
               ANDROID/'bionic/linker/linker.cpp', ANDROID/'bionic/libc/include/link.h']
    report = dict(status='PASS', scope=__doc__, image=str(image), image_sha256=sha(raw), cases=cases,
                  count=len(cases), image_entries=bound, breakpoint_offset=stop, load_segments=load_bindings,
                  sources={str(p): sha(p.read_bytes()) for p in sources},
                  boundaries=['No service constructors/main, Binder or TEE; linker own initialization/IFUNCs execute.',
                              'Image ld.config and init paths present; /proc realpath/property/APEX/init namespace behavior incomplete.',
                              'No production edits or binary patch; QEMU debugger breakpoint only.'])
    (ROOT/'logs/profile-service-relocation.json').write_text(json.dumps(report, indent=2)+'\n')
    print('PASS', len(cases), 'original ARM64 service relocation/missing-library cases')


if __name__ == '__main__':
    main()
