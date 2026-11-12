# TWRP device tree for Xiaomi O1_asic

## Current multi-version adaptation goal

See [ADAPTATION-GOALS.md](../../ADAPTATION-GOALS.md) for the OS3/OS4-first,
single-image compatibility target and offline-only acceptance criteria.
Historical feature checkboxes below are not a per-firmware validation matrix.

## Dual-kernel support (6.6 + 6.18)

This tree carries **two kernel generations at once** and picks the right one at
runtime, because the same recovery ramdisk has to boot on both firmware lines:

| Firmware                     | Kernel                        | Modules in ramdisk      |
| ---------------------------- | ----------------------------- | ----------------------- |
| HyperOS A15 (tree default)   | 6.6.77-android15-8-4k         | `/lib/modules/6.6/`     |
| OS4.0 / Android 17           | 6.18.21-android17-5-...-4k    | `/lib/modules/6.18/`    |

How the selection works: TWRP's `KernelModuleLoader` builds its search path as
`/lib/modules`, then `/lib/modules/$(uname major).$(minor)` (see
`bootable/recovery/kernel_module_loader.cpp`), and only writes a
`modules.load.twrp` entry for a module name that exists in the directory it is
scanning. Both version directories therefore coexist in one ramdisk with no
build-time switch and no runtime detection code of our own.

`TW_LOAD_VENDOR_MODULES` in `BoardConfig.mk` is the **union** of both load sets.
Names a given generation does not ship are simply skipped.

`TWRP_PREBUILT_KERNEL_VERSION` (default `6.6`) selects which prebuilt `Image`
goes into images that embed a kernel (the standalone `twrp` boot image /
`fastboot boot`). The stock `recovery` partition carries no kernel at all
(`kernel_size = 0`), so for `recovery.img` this switch has no effect:

```sh
# build against the default 6.6 kernel
TWRP_PREBUILT_KERNEL_VERSION=6.6 mka recoveryimage
# build against the 6.18 kernel
TWRP_PREBUILT_KERNEL_VERSION=6.18 mka recoveryimage
```

Module set provenance:

| Directory                        | Source                                                              |
| -------------------------------- | ------------------------------------------------------------------- |
| `lib/modules/6.6/`               | vendor originals shipped in the tree (dep files untouched)          |
| `lib/modules/6.18/`              | OTA `vendor_boot` `modules.load.recovery` (139) + `vendor_dlkm` (12) |
| `prebuilt/<variant>/.../6.6/`    | per-variant touch drivers (jinghu: goodix, violin: novatek)         |

`lib/modules/6.18/` has no jinghu/violin touch drivers because the OS4.0
firmware does not ship them - only `xiaomi_touch_dijun` exists there. Jinghu and
violin therefore only get touch on a 6.6 kernel until their own 6.18 builds appear.

Tree maintenance helpers:

| Script                        | Purpose                                                             |
| ----------------------------- | ------------------------------------------------------------------- |
| `scripts/build_moddeps.py`    | rebuild `modules.dep`/`modules.softdep` from the firmware's own depmod output |
| `scripts/verify_tree.py`      | check vermagic, dep graph and requested-module coverage              |
| `scripts/parse_boot.py`       | split a boot/vendor_boot image into kernel, ramdisk, dtb, bootconfig |
| `scripts/unpack_ramdisk.py`   | decompress an lz4-legacy ramdisk and extract its cpio entries        |
| `scripts/extract_payload_partition.py` | extract one partition out of an OTA `payload.bin`           |

## Supported devices

| Codename | Device                  |
| -------- | --------------------    |
| dijun    | Xiaomi 15s Pro     \*   |
| violin   | Xiaomi Pad 7s Pro  \*   |
| jinghu   | Xiaomi Pad 7 Ultra \*   |

\* untest


## Features

- [x] ADB
- [x] Decryption
- [x] Display
- [x] Fastbootd
- [x] Flashing
- [x] MTP
- [x] Sideload
- [x] USB-OTG
- [x] Vibrator

## Build it yourself

- [TWRP-Test/platform_manifest_twrp_aosp](https://github.com/TWRP-Test/platform_manifest_twrp_aosp)
