# dijun MiTEE recovery integration

Current unified-runtime status: see [profile activation](../../docs/PROFILE-SELECTION.md) and [multi-user control](../../docs/MULTIUSER-ADAPTATION.md). The sections below retain historical OS4 integration and device evidence. The current pinned source does not consume `TW_SKIP_SECONDARY_FBE_USERS`; GUI selection, rather than that legacy variable, previously restricted access to user 0. New per-user control is offline-tested; actual secondary/work-profile key unwrapping is not verified.

Status: **device-verified metadata and user-0 CE decryption** on the 6.18 boot path.
Verified image: `twrp-recovery-mitee-bootfix.img`, MD5
`5819f969bceb558cf734d5ae5608e211`. Secondary user 999 and the 6.6 path
remain unverified. Earlier candidates and audits below are historical.
Target firmware: `OS4.0.0.19.XODCNXM`, Android 17, kernel 6.18.21.
Recovery does not ship a custom first-stage load list; the matching stock
vendor_boot owns that stage. See the boot-regression audit below. The 6.6 boot path is retained; its MiTEE userspace compatibility is not validated,
and the preparation script therefore skips this OTA runtime on 6.6.

## Evidence

`logs/recovery-until-reboot.txt` contains:
`critical process 'keystore2' exited 4 times before boot completed`, followed by
`InitFatalReboot: signal 6`. Removing recovery keystore2's `critical` directive
addresses that reboot trigger; it does not supply a KeyMint provider.

The OTA vendor partition supplies:

- `/vendor/bin/tee-supplicant`
- `/vendor/bin/hw/android.hardware.security.keymint@3.0-service.mitee`
- `/vendor/bin/hw/android.hardware.gatekeeper-service.mitee`
- AIDL KeyMint v3, shared-secret v1, secure-clock v1, gatekeeper v1 manifests
- `/vendor/mitee/ta/*.ta`

The KeyMint executable contains UUID `dba51a17-0563-11e7-93b16fa7b0071a51`,
matching the vendor TA of that name. All ten vendor TAs are included without
modification. ODM also contains TAs; they are not bundled in this candidate.
A request for a missing ODM TA would require another extraction/staging pass.

Stock `tee-supplicant.rc` prepares `/dev/tee0`, `/dev/teepriv0`, RPMB/BSG nodes,
`/mnt/vendor/persist/data`, `/mnt/vendor/persist/fdsd`, and then enables KeyMint.
The recovery version preserves those storage locations and starts the three
services explicitly during `fs`. It uses the existing permissive recovery domain,
rather than claiming complete MiTEE SELinux policy integration.

## Maintained tree files

`prebuilt/dijun/mitee/root/` is copied only for `TARGET_PRODUCT=twrp_dijun`:

- `vendor/bin/tee-supplicant` and `vendor/bin/hw/*mitee`: original OTA executables
- `system/lib64/mitee/*.so`: 26 private vendor DSOs, visible only through the
  service's `LD_LIBRARY_PATH`; no replacement of TWRP's global libraries
- `system/etc/init/dijun-mitee.rc`: service definitions and start trigger
- `system/bin/dijun-prepare-mitee.sh`: bounded node checks and persist mount
- `system/etc/vintf/manifest/*mitee.xml`: original OTA declarations
- `vendor/mitee/ta/*.ta`: original TA images

Binder and Binder NDK use recovery's own library pair. Mixing OTA libbinder with
recovery libbinder_ndk produced unresolved `LIBBINDER` imports; the selected
closure passes strong dynamic-symbol checks including symbol versions.
This static check cannot prove Binder protocol, secure-world, or wrapped-key
compatibility. No key blobs are modified, replaced, or synthesized.
The preparation stage mounts the actual persist partition read/write, as the
stock supplicant expects; normal secure-world requests may update secure storage.

## Reproduction

From the workspace root, extract the matching `vendor` partition with
`scripts/extract_payload_partition.py`, then use `fsck.erofs --extract=` to
populate `imgs/firmware/vendor`. Run:

```sh
python3 -B scripts/stage_mitee.py
python3 -B scripts/build_mitee.py
```

The staging script writes `mitee-inventory.json` (SHA-256, origin, ELF checks).
The image script rebuilds the ramdisk over `twrp-recovery-keystorefix.img`.
This is not a full AOSP source compile. `device.mk` also stages these files in
future source builds. Generated image: `imgs/built/twrp-recovery-mitee-vendorpath.img`.

Checks completed: dependency closure/imports of all three executables, init
syntax via `host_init_verifier`, shell syntax, unique device AIDL declarations,
file modes, cpio roundtrip, preservation of baseline entries and partition size.

## Device validation

After booting the candidate, collect:

```powershell
adb shell cat /tmp/dijun-mitee-prepare.log
adb shell ps -A | Select-String 'tee-supplicant|keymint|gatekeeper|keystore2|recovery'
adb shell service list | Select-String 'keymint|sharedsecret|secureclock|gatekeeper|keystore'
adb logcat -b all -d > .\mitee-logcat.txt
adb pull /tmp/recovery.log .\mitee-recovery.log
```

`/tmp/dijun-mitee-prepare.log` must show genuine persist mounted and TEE nodes
available; processes must survive and register their AIDL services. Only then
check `/dev/block/mapper` and whether `/data` mounts through decrypted metadata.
Registration alone is not successful decryption. File-based CE unlocking and
Android 17 wrapped-key handling require separate real-device verification.

## Latest supplied logs

`logs/recovery-after-fix.log` stops at fstab-processing entry, whereas earlier
logs reached metadata decryption. The matching logcat continues for roughly two
minutes with keystore2 crashes. It also repeatedly fails to resolve
`android.hardware.boot.IBootControl/default`: the boot HAL rc is at the ramdisk
root and is never imported. This candidate stages its service declaration under
`system/etc/init` with an `on fs` start and the matching AIDL interface. This
addresses the observed service-discovery wait; device confirmation is pending.

Candidate MD5: `e0cd5ca2cc19b9d0fa6dafc61cb29ab8`, 104857600 bytes.

## MiTEE executable-path correction

The first runtime candidate reached the decrypt UI, but its three vendor
processes exited. `logs/mitee-logcat.txt` shows `auth_d_path` rejecting
`/system/bin/tee-supplicant` and `auth_ca_name` rejecting both `/system/bin/hw/`
KeyMint and Gatekeeper executables. These are kernel MiTEE path checks, distinct
from the non-enforcing SELinux audit messages (`permissive=1`). ELF loading and
`TEEC_InitializeContext` succeeded before session creation failed.

The next candidate keeps the original OTA bytes at their exact original
`/vendor/bin/` paths; these are regular executable files, not symlinks back to
`/system`. `system/etc/ld.config.txt` additionally maps `/vendor/bin` onto the
existing recovery linker section; library isolation still uses each service's
private `LD_LIBRARY_PATH`. The linker parser was checked to support multiple
`dir.recovery` entries. No kernel authentication check or TA is changed.

`build_mitee.py` now checks the original paths, ELF bytes and executable modes,
absence of the rejected `/system/bin` copies, and the vendor linker mapping.
Keep the first candidate for comparison. Device validation should look for the
absence of `path auth failed` / `fail to auth ca path`, persistent MiTEE process
lifetimes, successful AIDL registrations, then metadata and CE unlock results.
A fixed pathname alone does not prove successful TEE sessions or decryption.

## Metadata key failures after service registration

`logs/mitee-vendorpath-logcat.txt` confirms `path auth success`, Gatekeeper
`Connected`, KeyMint `connect to mitee keymaster success`, and successful AIDL
registrations. The remaining failure is during metadata-key use: KeyMint error
`-62` (`KEY_REQUIRES_UPGRADE`), then secure-world storage errors and
`0xffff3024`, followed by `INVALID_OPERATION_HANDLE` (`-28`). These later errors
must not be mistaken for missing HALs or an incorrect PIN.

Two concrete mismatches are corrected in the source-build candidate:

1. The maintained tree had `PLATFORM_VERSION=99.87.36` and OS/vendor/boot SPL
   `2099-12-31`. The extracted OTA `system/system/build.prop` specifies OS 17,
   SPL 2026-09-01; vendor `build.prop` specifies vendor SPL 2026-09-01 and
   shipping API 35. `mitee-build-profile.json` records source hashes and values.
   BoardConfig now advertises those OS/SPL values. The Android 16 source tree's
   `PLATFORM_VERSION_LAST_STABLE=16` and actual SDK remain the build/API basis.
2. TWRP `TWPartition::MountPersistRootIfNeeded()` unconditionally unmounted
   persist after using its time files, including when device init had already
   mounted it for tee-supplicant. The log contains `EXT4-fs (sdd2): unmounting`
   before decryption and the supplicant reports a 7.8 GiB empty filesystem at
   `/mnt/vendor/persist` instead of the actual 128 MiB partition. Patch
   `0002-preserve-preexisting-persist-mount.patch` makes time fixup preserve a
   preexisting mount and still release a mount it acquired itself.

The on-disk metadata key blobs are not replaced or upgraded by this work. A full
recovery source build is required for the persist fix; use
`scripts/compile_recovery.sh`, which invokes `make -j$(nproc) recoveryimage`.
Service startup and matching version values alone do not establish successful
metadata or CE decryption; confirm those results on the device.

The Android 16 build property generator uses `Platform_version_last_stable`
for `ro.build.version.release`, independently of `PLATFORM_VERSION`.
`system/etc/dijun-crypto-profile.prop` therefore carries the OTA crypto identity
explicitly; `dijun-prepare-mitee.sh` applies it with the existing recovery
`resetprop -n` and verifies every value **before** setting prepared=1 and starting
any MiTEE HAL. SDK 36 is retained for the recovery userspace/API build. This
profile is for the matching OS4.0.0.19 Android 17 system, not arbitrary firmware.

Source-build candidate: `imgs/built/twrp-recovery-mitee-keyprofile.img`, MD5
`2c229b9e97db5ebce7ab38f671bb69fc`, 104857600 bytes. Built with
`make -j$(nproc) recoveryimage` (30 jobs); final build log is
`logs/build-mitee-keyprofile-final.log`. Inspection via
`scripts/verify_source_recovery.py` passed. MiTEE provider connectivity is
verified on the preceding vendorpath candidate; decryption on this new
persist/identity candidate remains to be tested.

## Source-build boot regression audit

The keyprofile source build (MD5 2c229b9e97db5ebce7ab38f671bb69fc) returned to
Android before ADB could be captured. It is not a verified-booting candidate.
Comparing its cpio to the successful vendorpath ramdisk found that the latter's
`lib/modules/6.18/modules.load.recovery` had mode **040755** (directory), despite
containing list bytes. The generic repacker had inherited the parent directory
inode type. Init therefore had not used that file as the intended strict list.
The source build created it as a regular file (0100644), activating a different,
unvalidated first-stage loading path. Earlier claims that the list behavior
had been validated were incorrect. The precise reboot cause still needs a
boot-time trace; the cpio difference establishes a material regression risk.

The next source build removes custom load lists from both versioned ramdisk
directories and defers to the full stock vendor_boot module tree. It also uses
stock ramdisk-only recovery header OS/SPL=0 (the failed source build encoded
16/2026-09); the runtime KeyMint identity remains the OTA profile. The generic
repacker now creates regular files with source permissions, and the old list
image generator is retired. `gen_loadrecovery.py` now emits diagnostic
`modules.load.reference` files, which init never treats as load lists.

Checks must validate inode type, header fields, and first-stage load ownership,
not merely list contents or file counts. This audit does not claim that the
header difference or first-stage override alone caused the reboot.

Boot-regression candidate: `imgs/built/twrp-recovery-mitee-bootfix.img`, MD5
`5819f969bceb558cf734d5ae5608e211`, 104857600 bytes. Source build with 30 jobs
succeeded; stock header comparison and updated source-image checks passed.
Actual boot and decryption are pending device validation.

## Verified baseline: 2026-11-11

Latest device logs prove both layers of decryption:

- `logs/bootfix-recovery.log:985`: metadata decryption succeeds with
  `/dev/block/mapper/userdata`.
- `logs/bootfix-recovery.log:1561`: `User 0 Decrypted Successfully!`.
- `logs/bootfix-recovery.log:1565`: `Data successfully decrypted`.
- `logs/bootfix-recovery.log:1567`: storage switches to `/data/media/0`.
- Properties report `ro.crypto.metadata.enabled=true` and persist on `sdd2`;
  the decrypted partition table reports `Is_Decrypted`.
- Later UI MTP start/stop operations complete successfully; these logs do not
  establish PC file-transfer or backup/restore correctness.

Keep this image and its recorded build/profile changes as the stable baseline.
User 999 is not decrypted; `TW_SKIP_SECONDARY_FBE_USERS=true` is set. Do not
claim multi-user unlocking, 6.6 decryption, or backup/restore validation from
this user-0 result. Raw logfile SHA-256 hashes and scope are recorded in
`imgs/built/twrp-recovery-mitee-bootfix.json` at the workspace root.

## Device-fix candidate: MTP, timezone, vibration, rapid power presses

The user-0 decryption baseline is also retained under
`imgs/verified/twrp-recovery-mitee-bootfix.img` (MD5
`5819f969bceb558cf734d5ae5608e211`). The next candidate keeps its MiTEE
executables, private libraries, TA files, crypto profile, persist handling and
first-stage module-loading ownership. Current work is offline-only; hardware effects remain unverified.

- Runtime RTC and `date -u` agree; `rtc0/hctosys=1`. The displayed 14-hour error
  comes from the inherited US Central `CST6CDT` default. Device properties now
  select `CST-8` (UTC+8), with a one-time migration of the unchanged legacy US
  defaults. Deliberately customized zones remain intact. No RTC correction is
  applied. Source patch: `0003-device-timezone-default.patch`.
- MTP previously fell back to absent `/dev/mtp_usb`. Replace the default legacy
  USB rc with configfs/FunctionFS initialization from the original XRing USB
  layout. Bind MTP+ADB only after **both** servers publish descriptor readiness;
  keep generic recovery ADB/sideload/fastbootd actions. Firmware IDs for MTP+ADB
  are `2717:FF48`; switching back resets the recovery vendor ID.
- Original `vendor_dlkm/lib/modules/xring_audio_hw_third.ko` contains the haptic
  drivers; its vermagic and module_layout CRC match the 6.18 module set. Add it
  to optional TWRP loading, flatten its stock dependency paths, and retain stock
  soft dependencies/aliases. No first-stage list is created. The 6.6 set is not
  supplied with this 6.18 binary.
- Stock DTB contains `cirrus,cs40l26a`. The module's `cs40l26_input_init`
  advertises FF_PERIODIC, FF_CUSTOM, FF_SINE and FF_GAIN, not FF_CONSTANT/RUMBLE.
  Add capability-gated FF_PERIODIC/FF_SINE playback and Cirrus input-name
  detection (`0005-cirrus-sine-haptics.patch`). The initial candidate used 5 ms / 200 Hz. The haptics-policy candidate now
  reads dijun's 130 Hz property and rounds to 8 ms / 125 Hz; see
  ../../docs/HAPTICS-ADAPTATION.md. The driver clamps magnitude to 0..255, so
  recovery UI feedback retains 64.
  Package the nine original vendor `cs40l26*` firmware files (about 117 KiB).
  Correct the kernel custom firmware lookup to the single directory
  `/vendor/firmware`; the stock comma-separated parameter is not a path list.
- Preserve each queued power-key short press; a second toggle cancels an
  unpresented off request. Reset screenshot-chord consumption for a new press.
  The host regression exercises the actual production source and reproduces
  both failures on the unpatched source (`0004-rapid-power-screen-toggle.patch`).
  This establishes those state defects, not a measured hardware wake latency.

Validation: `python3 tests/devicefix_regression.py`, `host_init_verifier` for
both device USB/hardware rc files, `git diff --check` in the recovery source,
and source build after `make -j$(nproc) installclean`, then
`make -j$(nproc) recoveryimage`. `scripts/verify_devicefix.py` compares the
packaged crypto files with the device-verified baseline, checks current GUI
binaries, original firmware/module bytes, dependency closure and USB readiness
conditions. Actual Windows MTP transfers, vibration, and rapid wake latency are
unverified; no new device checks are part of this task. Static/host checks do not establish these outcomes.
