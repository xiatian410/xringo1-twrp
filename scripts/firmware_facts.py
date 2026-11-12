#!/usr/bin/env python3
"""Inspect verified OTA partitions without mounting them or executing target code.

Read boot structures from AOSP bootimg.h and module facts from ELF sections;
never infer a module CRC by searching arbitrary bytes for a symbol name.
Reports are evidence, not an assertion that a given module can load on hardware.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import subprocess

from acquire_firmware import ROOT, SAMPLES, sha256_file


def digest(data):
    return hashlib.sha256(data).hexdigest()


def haptics_module(facts):
    """Select the mounted stock driver by its probe export, not an OS label."""
    candidates = [(path, item) for path, item in facts['modules'].items()
                  if path.startswith('vendor_dlkm/') and
                  'cs40l26_i2c_probe' in item['exports']]
    if len(candidates) != 1:
        raise ValueError(f'{facts["sample"]}: expected one stock cs40l26 driver, got {len(candidates)}')
    return candidates[0]


def take(data, offset, size):
    if offset < 0 or size < 0 or offset + size > len(data):
        raise ValueError(f'truncated structure: {offset}+{size} > {len(data)}')
    return data[offset:offset + size]


def cstr(data):
    return data.split(b'\0', 1)[0].decode('utf-8', 'strict')


def align(n, page=4096):
    return (n + page - 1) // page * page


def boot_parts(data):
    """Return structured header facts and named components (v3/v4 only)."""
    if data[:8] == b'ANDROID!':
        ks, rs, osv, hs = struct.unpack_from('<4I', take(data, 8, 16))
        version, = struct.unpack_from('<I', take(data, 40, 4))
        if version not in (3, 4) or hs != (1580 if version == 3 else 1584):
            raise ValueError(f'unsupported Android boot header {version}/{hs}')
        sigsize = struct.unpack_from('<I', data, 1580)[0] if version == 4 else 0
        parts = {'kernel': take(data, 4096, ks), 'ramdisk': take(data, 4096 + align(ks), rs)}
        parts['boot_signature'] = take(data, 4096 + align(ks) + align(rs), sigsize)
        normalized = bytearray(data[:4096])
        struct.pack_into('<I', normalized, 12, 0)  # compare recovery layout except ramdisk length
        facts = dict(format='ANDROID', header_version=version, header_size=hs,
                     page_size=4096, kernel_size=ks, ramdisk_size=rs,
                     os_version_raw=osv, signature_size=sigsize, cmdline=cstr(data[44:1580]),
                     header_without_ramdisk_size_sha256=digest(normalized))
        if ks:
            banner = re.search(rb'Linux version [^\x00\n]+', parts['kernel'])
            facts['kernel_banner'] = banner.group().decode() if banner else None
            facts['kernel_release'] = banner.group().decode().split()[2] if banner else None
            facts['kernel_sha256'] = digest(parts['kernel'])
        return facts, parts
    if data[:8] != b'VNDRBOOT':
        raise ValueError('unrecognized boot image')
    version, page = struct.unpack_from('<II', take(data, 8, 8))
    if version not in (3, 4) or page not in (2048, 4096, 8192, 16384):
        raise ValueError('unsupported vendor boot header')
    rs, = struct.unpack_from('<I', data, 24)
    hs, dtbs = struct.unpack_from('<II', take(data, 2096, 8))
    if hs != (2112 if version == 3 else 2128):
        raise ValueError('incorrect vendor header size')
    start = align(hs, page)
    parts = {'vendor_ramdisk': take(data, start, rs)}
    pos = start + align(rs, page)
    parts['dtb'] = take(data, pos, dtbs)
    pos += align(dtbs, page)
    facts = dict(format='VNDRBOOT', header_version=version, header_size=hs,
                 page_size=page, ramdisk_size=rs, dtb_size=dtbs, cmdline=cstr(data[28:2076]))
    if version == 4:
        ts, count, entrysize, bcs = struct.unpack_from('<4I', data, 2112)
        if entrysize < 108 or ts != count * entrysize:
            raise ValueError('invalid vendor ramdisk table')
        table = take(data, pos, ts)
        parts['bootconfig'] = take(data, pos + align(ts, page), bcs)
        facts['bootconfig'] = parts['bootconfig'].decode()
        facts['ramdisk_table'] = []
        for i in range(count):
            entry = take(table, i * entrysize, entrysize)
            size, offset, kind = struct.unpack_from('<3I', entry)
            name = cstr(entry[12:44])
            facts['ramdisk_table'].append(dict(size=size, offset=offset, type=kind, name=name,
                                                board_id=list(struct.unpack_from('<16I', entry, 44))))
            parts[f'fragment-{i}'] = take(parts['vendor_ramdisk'], offset, size)
    return facts, parts


def ramdisk_entries(blob):
    if not blob:
        return []
    if blob[:4] in (b'\x02\x21\x4c\x18', b'\x04\x22\x4d\x18'):
        blob = subprocess.run(['lz4', '-d', '-c'], input=blob, capture_output=True, check=True).stdout
    elif blob[:2] == b'\x1f\x8b':
        blob = gzip.decompress(blob)
    entries = []
    pos = 0
    while pos < len(blob):
        if blob[pos] == 0:
            pos += 1
            continue
        hdr = take(blob, pos, 110)
        if hdr[:6] not in (b'070701', b'070702'):
            raise ValueError(f'unsupported cpio at {pos}')
        fields = [int(hdr[6 + 8*i:14 + 8*i], 16) for i in range(13)]
        _, mode, uid, gid, nlink, _, size, _, _, _, _, namesize, check = fields
        name = take(blob, pos + 110, namesize)
        if not namesize or name[-1:] != b'\0':
            raise ValueError('invalid cpio name')
        name = cstr(name)
        pos = align(pos + 110 + namesize, 4)
        data = take(blob, pos, size)
        pos = align(pos + size, 4)
        if hdr[:6] == b'070702' and (sum(data) & 0xffffffff) != check:
            raise ValueError('cpio checksum mismatch')
        if name == 'TRAILER!!!':
            continue
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('unsafe cpio path')
        entries.append((str(path), mode, uid, gid, nlink, data))
    return entries


def elf_module(data):
    """ELF64 AArch64 modinfo, all imported CRCs, and available exported CRCs."""
    if data[:6] != b'\x7fELF\x02\x01':
        raise ValueError('expected little-endian ELF64 module')
    if struct.unpack_from('<HH', data, 16) != (1, 183):
        raise ValueError('expected AArch64 relocatable module')
    shoff, = struct.unpack_from('<Q', data, 40)
    shentsize, count, stridx = struct.unpack_from('<HHH', data, 58)
    if shentsize != 64 or not count or stridx >= count:
        raise ValueError('unsupported ELF section table')
    sections = [struct.unpack('<IIQQQQIIQQ', take(data, shoff + i*64, 64)) for i in range(count)]
    def secdata(i):
        s = sections[i]
        return b'' if s[1] == 8 else take(data, s[4], s[5])
    strings = secdata(stridx)
    names = {cstr(strings[s[0]:]): i for i, s in enumerate(sections)}
    info = {}
    for field in secdata(names['.modinfo']).split(b'\0'):
        if b'=' in field:
            k, v = field.decode().split('=', 1)
            info.setdefault(k, []).append(v)
    imports = {}
    if '__versions' in names:
        versions = secdata(names['__versions'])
        if len(versions) % 64:
            raise ValueError('invalid modversion_info records')
        for pos in range(0, len(versions), 64):
            crc, = struct.unpack_from('<Q', versions, pos)
            name = cstr(versions[pos+8:pos+64])
            if not name or name in imports or crc > 0xffffffff:
                raise ValueError('invalid/duplicate versioned symbol')
            imports[name] = crc
    elif '__version_ext_names' in names and '__version_ext_crcs' in names:
        version_names = secdata(names['__version_ext_names']).rstrip(b'\0').split(b'\0')
        crcs = secdata(names['__version_ext_crcs'])
        if len(crcs) != 4 * len(version_names):
            raise ValueError('invalid extended modversions')
        imports = {n.decode(): c[0] for n, c in zip(version_names, struct.iter_unpack('<I', crcs))}
    exports = {}
    undefined = []
    if '.symtab' in names:
        idx = names['.symtab']
        symbols = secdata(idx)
        st = secdata(sections[idx][6])
        if sections[idx][9] != 24 or len(symbols) % 24:
            raise ValueError('invalid symbol table')
        for nameoff, kind, other, shndx, value, size in struct.iter_unpack('<IBBHQQ', symbols):
            name = cstr(st[nameoff:])
            if shndx == 0 and kind >> 4 == 1:
                undefined.append(name)
            if not name.startswith('__crc_'):
                continue
            if shndx == 0xfff1:
                exports[name[6:]] = value
            elif 0 < shndx < count:
                exports[name[6:]] = struct.unpack('<I', take(secdata(shndx), value, 4))[0]
            else:
                raise ValueError(f'unresolved exported CRC: {name}')
    return dict(modinfo=info, imports=imports, exports=exports,
                undefined_global=sorted(undefined), module_layout_crc=imports.get('module_layout'),
                imports_sha256=digest(json.dumps(imports, sort_keys=True).encode()))


def props(data):
    return dict(line.split('=', 1) for line in data.decode(errors='replace').splitlines()
                if line and not line.startswith('#') and '=' in line)


def analyze(sample):
    base = SAMPLES / sample
    inventory = json.loads((base / 'inventory.json').read_text())
    out = base / 'analysis'
    out.mkdir(exist_ok=True)
    result = dict(sample=sample, manifest_sha256=inventory['manifest_sha256'],
                  ota_identity=inventory['ota_identity'], groups=inventory['groups'],
                  headers={}, modules={}, files={}, properties={}, texts={}, pending=[],
                  evidence='S0/S1: offline static facts; not a load/decryption success claim')
    def record(path, data, mode=0o100644, source=''):
        result['files'][path] = dict(sha256=digest(data), size=len(data), mode=oct(mode), source=source)
        if path.endswith('.ko'):
            result['modules'][path] = elf_module(data)
        elif path.endswith(('.prop', 'prop.default')):
            result['properties'][path] = props(data)
        if ('fstab' in path or path.rsplit('/', 1)[-1].startswith('modules.') or
                ('/etc/' in path and any(x in path.lower() for x in ['mitee', 'keymint', 'gatekeeper', 'vibrator']))):
            try:
                result['texts'][path] = data.decode()
            except UnicodeError:
                pass
    for part in ['boot', 'init_boot', 'vendor_boot', 'recovery', 'dtbo', 'vendor_dlkm', 'system_dlkm', 'odm_dlkm', 'vendor', 'odm']:
        if part not in inventory['partitions']:
            result['pending'].append(dict(partition=part, reason='absent from manifest'))
            continue
        p = base / (part + '.img')
        expected = inventory['partitions'][part]['sha256']
        if not p.is_file():
            result['pending'].append(dict(partition=part, reason='not yet acquired'))
            continue
        if p.is_symlink() or sha256_file(p) != expected:
            raise ValueError(f'{sample}/{part}: unverified image')
        if part in ['boot', 'init_boot', 'vendor_boot', 'recovery']:
            header, pieces = boot_parts(p.read_bytes())
            result['headers'][part] = header
            header['image_sha256'] = expected
            header['image_size'] = p.stat().st_size
            if part == 'boot':
                continue
            # Fragments have separate compression and CPIO streams. Keep names separate
            # until a subsequent ramdisk-merge analysis explicitly resolves collisions.
            streams = {k: v for k, v in pieces.items() if k.startswith('fragment-')}
            if not streams:
                streams = {k: v for k, v in pieces.items() if k in ['ramdisk', 'vendor_ramdisk']}
            for name, stream in streams.items():
                dest = out / part / name
                dest.mkdir(parents=True, exist_ok=True)
                for path, mode, uid, gid, links, data in ramdisk_entries(stream):
                    key = f'{part}/{name}/{path}'
                    if not stat.S_ISREG(mode):
                        continue  # do not create device nodes or symlinks on the host
                    record(key, data, mode, f'{part}.img:{name}')
                    target = dest / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.is_symlink():
                        raise ValueError('symlink in extraction output')
                    target.write_bytes(data)
            for k in ['dtb', 'bootconfig']:
                if k in pieces:
                    (out / part / k).write_bytes(pieces[k])
        elif part == 'dtbo':
            result['headers'][part] = dict(image_sha256=expected, image_size=p.stat().st_size)
        else:
            dest = out / part
            marker = out / (part + '.source-sha256')
            if not marker.exists() or marker.read_text().strip() != expected:
                if dest.exists():
                    raise ValueError(f'incomplete/unverified existing output {dest}; keep for inspection')
                with (out / (part + '.extract.log')).open('w') as log:
                    subprocess.run(['fsck.erofs', f'--extract={dest}', str(p)], stdout=log, stderr=log, check=True)
                marker.write_text(expected + '\n')
            for f in sorted(dest.rglob('*')):
                if f.is_file() and not f.is_symlink():
                    record(f'{part}/{f.relative_to(dest)}', f.read_bytes(), f.stat().st_mode, f'{part}.img')
    counts = Counter(path.split('/')[0] for path in result['modules'])
    result['module_counts'] = dict(counts)
    result['module_layout_crcs'] = dict(Counter(str(m['module_layout_crc']) for m in result['modules'].values()))
    report = out / 'facts.json'
    temp = report.with_suffix('.partial')
    temp.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    temp.replace(report)
    print(f'{sample}: {dict(counts)}, {len(result["files"])} files, {len(result["pending"])} pending/absent partitions', flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', nargs='+', default=[p.name for p in sorted(SAMPLES.iterdir()) if p.is_dir()])
    args = parser.parse_args()
    for sample in args.samples:
        if sample not in {p.name for p in SAMPLES.iterdir() if p.is_dir()}:
            raise ValueError('unknown sample')
        analyze(sample)


if __name__ == '__main__':
    main()
