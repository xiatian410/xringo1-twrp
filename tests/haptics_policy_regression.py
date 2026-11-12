#!/usr/bin/env python3
"""Compare SELinux decisions in old/new *image* policies, without loading either.

Firmware reads run with kernel credentials, even when requested by a permissive
recovery process. Exercise this distinction and retain negative policy tests.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ANDROID = Path('/root/AAA/twrp')
sys.path.insert(0, str(ROOT / 'scripts'))
from verify_devicefix import entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'logs/haptics-audit/policy-regression.json')
    args = parser.parse_args()
    image, cpio = entries(args.image)
    policy = cpio['sepolicy'][11]
    assert policy == (ANDROID / 'out/target/product/O1_asic/recovery/root/sepolicy').read_bytes()
    assert b'ro.twrp.haptics_frequency=130\n' in cpio['prop.default'][11]
    baseline = ROOT / 'logs/haptics-audit/devicefix.sepolicy'
    checks = []
    with tempfile.TemporaryDirectory(prefix='dijun-policy-') as temp:
        temp = Path(temp)
        current = temp / 'sepolicy'
        current.write_bytes(policy)
        query = temp / 'policy_access'
        library = ANDROID / 'out/soong/.intermediates/external/selinux/libsepol/libsepol/linux_glibc_x86_64_static/libsepol.a'
        subprocess.run(['gcc', '-Wall', '-Wextra', f'-I{ANDROID}/external/selinux/libsepol/include',
                        str(ROOT / 'tests/policy_access.c'), str(library), '-o', str(query)], check=True)
        def check(label, policy_path, src, dst, cls, perm, expected):
            result = subprocess.run([str(query), str(policy_path), src, dst, cls, perm],
                                    capture_output=True, text=True)
            record = dict(case=label, source=src, target=dst, object_class=cls, permission=perm,
                          expected_exit=expected, actual_exit=result.returncode,
                          decision=result.stdout.strip(), diagnostic=result.stderr.strip())
            checks.append(record)
            assert result.returncode == expected, record
            assert 'DOMAIN kernel enforcing' in result.stdout, record
        kernel = 'u:r:kernel:s0'
        check('previous-policy-cannot-express-firmware-load', baseline, kernel,
              'u:object_r:rootfs:s0', 'system', 'firmware_load', 2)
        for target in ['u:object_r:rootfs:s0', 'u:object_r:vendor_file:s0', kernel]:
            check('allow-firmware-' + target, current, kernel, target, 'system', 'firmware_load', 0)
        for perm in ['read', 'open', 'getattr']:
            check('allow-vendor-file-' + perm, current, kernel,
                  'u:object_r:vendor_file:s0', 'file', perm, 0)
        check('deny-app-data-as-firmware', current, kernel,
              'u:object_r:app_data_file:s0', 'system', 'firmware_load', 1)
        check('deny-shell-firmware-permission', current, 'u:r:shell:s0',
              'u:object_r:vendor_file:s0', 'system', 'firmware_load', 1)
        # Backup cancellation creates a private group and signals/reaps children
        # with the same recovery context. Query the final binary policy too.
        for perm in ['setpgid', 'sigkill', 'sigchld']:
            check('allow-backup-child-' + perm, current, 'u:r:recovery:s0',
                  'u:r:recovery:s0', 'process', perm, 0)
    report = dict(result='PASS', evidence='S1 actual binary policy decisions; S3 image content',
                  image=str(args.image.resolve()), image_sha256=hashlib.sha256(image).hexdigest(),
                  policy_sha256=hashlib.sha256(policy).hexdigest(),
                  baseline_policy_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),
                  frequency_property_hz=130, hardware_result='U: offline only; motor not exercised', checks=checks,
                  test_sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                      [Path(__file__).resolve(), ROOT/'tests/policy_access.c', library]})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(f'PASS: {len(checks)} binary policy cases, kernel enforcing, image policy and 130 Hz property verified')


if __name__ == '__main__':
    main()
