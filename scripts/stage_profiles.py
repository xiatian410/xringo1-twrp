#!/usr/bin/env python3
"""Stage provenance-checked, content-addressed crypto profiles for integration.

Profiles are packaged by device.mk and selected by dijun-runtime.sh. This
generator only stages provenance-checked inputs; execution/image validation is
reported separately. Historical OS4 runtime files are never overwritten here.
"""
import json
from pathlib import Path
import stat

from firmware_facts import ROOT, SAMPLES, digest

TREE = ROOT / 'dtsrc/O1_asic_dual'


def stage(sample, crypto):
    facts = json.loads((SAMPLES / sample / 'analysis/facts.json').read_text())
    profile = dict(id=sample, schema_version=1, status='prepared-runtime-profile',
                   kernel_release=facts['headers']['boot']['kernel_release'],
                   ota_identity=facts['ota_identity'], crypto_identity=crypto['proposed_crypto_identity'],
                   system_file_evidence=crypto.get('system_file_evidence'),
                   properties={k: v for k, v in facts['properties'].items() if k.startswith(('vendor/', 'odm/')) and k.endswith('build.prop')},
                   assets={}, firmware_path='/lib/firmware', dependency_check=crypto['checks'],
                   limitations=crypto['limitations'])
    if any(value is None for value in profile['crypto_identity'].values()):
        raise ValueError(f'{sample}: incomplete crypto identity')
    def add(dest, source, expected, mode):
        src = Path(source)
        if not src.is_absolute():
            src = ROOT / src
        if not src.resolve().is_relative_to(SAMPLES / sample / 'analysis') or src.is_symlink():
            raise ValueError(f'profile asset must come from this sample: {src}')
        data = src.read_bytes()
        if digest(data) != expected:
            raise ValueError(f'asset source hash mismatch: {src}')
        if dest in profile['assets'] and profile['assets'][dest]['sha256'] != expected:
            raise ValueError(f'conflicting assets for {dest}')
        blob = TREE / 'prebuilt/common/profile-blobs' / expected
        blob.parent.mkdir(parents=True, exist_ok=True)
        if blob.is_symlink() or (blob.exists() and digest(blob.read_bytes()) != expected):
            raise ValueError(f'corrupt existing blob: {blob}')
        if not blob.exists():
            blob.write_bytes(data)
            blob.chmod(0o644)
        profile['assets'][dest] = dict(blob=str(blob.relative_to(TREE)), sha256=expected,
                                      size=len(data), mode=oct(mode), source=str(src.relative_to(ROOT)))
    for path, item in crypto['assets'].items():
        dest = path.replace('vendor/etc/vintf/manifest/', 'system/etc/vintf/manifest/')
        add(dest, item['path'], item['sha256'], 0o755 if path.startswith('vendor/bin/') else 0o644)
    for name, item in crypto['private_dsos'].items():
        add('system/lib64/mitee/' + name, item['path'], item['sha256'], 0o644)
    for path, item in facts['files'].items():
        if path.startswith(('vendor/firmware/', 'odm/firmware/')) and (Path(path).name.startswith('cs40l26') or
                Path(path).name in ['synaptics_spi_dijun.img', 'dijun_syna_thp_config.ini']):
            add(path, SAMPLES / sample / 'analysis' / path, item['sha256'], 0o644)
            if path.startswith('odm/firmware/'):
                add('lib/firmware/' + Path(path).name,
                    SAMPLES / sample / 'analysis' / path, item['sha256'], 0o644)
    profile['haptics'] = dict(resonant_frequency_hz=None, module_candidates=[])
    for path, properties in facts['properties'].items():
        if path.startswith('odm/'):
            value = properties.get('ro.odm.mm.vibrator.resonant_frequency')
            if value:
                profile['haptics']['resonant_frequency_hz'] = int(value)
    for path, module in facts['modules'].items():
        if 'cs40l26_i2c_probe' in module['exports']:
            profile['haptics']['module_candidates'].append(dict(path=path,
                sha256=facts['files'][path]['sha256'], imports_sha256=module['imports_sha256'],
                dependencies=module['modinfo'].get('depends', [])))
    dest = TREE / 'profiles' / sample / 'profile.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + '\n')
    return profile


def main():
    data = json.loads((ROOT / 'docs/crypto-compatibility.json').read_text())
    staged = {}
    for sample, crypto in data['profiles'].items():
        if crypto['status'] != 'S1 dependency/symbol checks passed':
            print(f'{sample}: not staged: {crypto["status"]}')
            continue
        profile = stage(sample, crypto)
        staged[sample] = profile
        print(f'{sample}: {len(profile["assets"])} assets staged; validate activation separately')
    assets = [a for p in staged.values() for a in p['assets'].values()]
    unique = {a['sha256']: a['size'] for a in assets}
    report = dict(status='prepared-runtime-profiles', profiles=list(staged),
                  repeated_bytes=sum(a['size'] for a in assets),
                  unique_blob_bytes=sum(unique.values()), unique_blobs=len(unique),
                  scope='Crypto plus haptic/touch firmware assets. Module plans/activation code generated separately; image and runtime results are separate evidence.')
    (TREE / 'profiles/inventory.json').write_text(json.dumps(report, indent=2) + '\n')
    print(report)


if __name__ == '__main__':
    main()
