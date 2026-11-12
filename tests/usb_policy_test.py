#!/usr/bin/env python3
"""Query the candidate's compiled USB helper policy without loading it."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
AOSP = Path('/root/AAA/twrp')
sys.path.insert(0, str(ROOT/'scripts'))
from verify_devicefix import entries

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('image', type=Path)
ap.add_argument('--output', type=Path, required=True)
args = ap.parse_args()
data, cpio = entries(args.image)
sha = lambda b: hashlib.sha256(b).hexdigest()
policy = cpio['sepolicy'][11]
checks = []
library = AOSP/'out/soong/.intermediates/external/selinux/libsepol/libsepol/linux_glibc_x86_64_static/libsepol.a'
with tempfile.TemporaryDirectory(prefix='dijun-usb-policy-') as tmp:
    tmp = Path(tmp)
    (tmp/'sepolicy').write_bytes(policy)
    # Platform recovery executables retain rootfs labels. No restorecon to an
    # exec_type (forbidden for init) is needed; the rc explicitly sets the domain.
    usb_rc = cpio['init.recovery.usb.rc'][11]
    assert b'exec u:r:dijun_usb:s0 root shell usb -- /system/bin/dijun-usb-config' in usb_rc
    assert b'restorecon /system/bin/dijun-usb-config' not in usb_rc
    property_contexts = b'\n'.join(e[11] for name,e in cpio.items() if name.endswith('property_contexts'))
    for name, kind, match in [('sys.recovery.usb.', 'dijun_usb_prop', 'prefix'),
                              ('ctl.start$fastbootd', 'dijun_usb_ctl_prop', 'exact'),
                              ('ctl.stop$fastbootd', 'dijun_usb_ctl_prop', 'exact')]:
        assert f'{name} u:object_r:{kind}:s0 {match} string'.encode() in property_contexts
    subprocess.run(['gcc', '-Wall', '-Wextra', f'-I{AOSP}/external/selinux/libsepol/include',
                    str(ROOT/'tests/usb_policy_access.c'), str(library), '-o', str(tmp/'query')], check=True)
    def query(src, dst, cls, perm, allowed=True):
        run = subprocess.run([str(tmp/'query'), str(tmp/'sepolicy'), src, dst, cls, perm], capture_output=True, text=True)
        item = dict(source=src, target=dst, object_class=cls, permission=perm,
                    expected_exit=0 if allowed else 1, actual_exit=run.returncode, output=run.stdout+run.stderr)
        checks.append(item)
        assert run.returncode == item['expected_exit'], item
        assert 'DOMAIN dijun_usb enforcing' in run.stdout, item
    helper = 'u:r:dijun_usb:s0'
    for cls, perms in [('dir', 'search read open getattr write add_name remove_name'),
                       ('file', 'open read write getattr'), ('lnk_file', 'create read getattr unlink')]:
        for perm in perms.split(): query(helper, 'u:object_r:configfs:s0', cls, perm)
    for prop in ['usb_control_prop', 'ffs_control_prop', 'dijun_usb_prop', 'ctl_adbd_prop', 'dijun_usb_ctl_prop']:
        query(helper, f'u:object_r:{prop}:s0', 'property_service', 'set')
    for prop in ['init_service_status_prop', 'init_service_status_private_prop', 'recovery_usb_config_prop']:
        for perm in ['read', 'open', 'map']: query(helper, f'u:object_r:{prop}:s0', 'file', perm)
    query('u:r:init:s0', helper, 'process', 'transition')
    for perm in ['entrypoint', 'open', 'read', 'execute', 'getattr', 'map']:
        query(helper, 'u:object_r:rootfs:s0', 'file', perm)
    query(helper, 'u:object_r:rootfs:s0', 'file', 'execute_no_trans', False)
    query(helper, 'u:r:init:s0', 'unix_stream_socket', 'connectto')
    query(helper, 'u:object_r:rootfs:s0', 'dir', 'search')
    for target, cls, perm in [('ctl_start_prop', 'property_service', 'set'),
                              ('ctl_stop_prop', 'property_service', 'set'),
                              ('powerctl_prop', 'property_service', 'set'),
                              ('app_data_file', 'file', 'read'),
                              ('block_device', 'blk_file', 'write')]:
        query(helper, f'u:object_r:{target}:s0', cls, perm, False)
    query(helper, 'u:r:recovery:s0', 'process', 'sigkill', False)
    # AF_UNIX SOCK_SEQPACKET uses the unix_stream_socket SELinux class.
    for perm in ['create', 'read', 'write', 'getattr', 'shutdown']:
        query('u:r:recovery:s0', 'u:r:recovery:s0', 'unix_stream_socket', perm)
    for perm in ['fork', 'sigkill', 'sigchld']:
        query('u:r:recovery:s0', 'u:r:recovery:s0', 'process', perm)

report = dict(status='PASS', image=str(args.image.resolve()), image_sha256=sha(data),
              policy_sha256=sha(policy), checks=checks,
              helper_entrypoint='rootfs with explicit dijun_usb process label; platform recovery convention',
              property_labels_checked=True,
              scope='Compiled policy decisions, enforcing helper domain. No host policy load or phone execution.',
              test_sources={str(p):sha(p.read_bytes()) for p in [Path(__file__).resolve(), ROOT/'tests/usb_policy_access.c', library]})
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(f'PASS: {len(checks)} USB helper policy decisions; domain enforcing.')
