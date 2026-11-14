# Xiaomi 15S Pro Recovery

[![Source and patch integrity](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml/badge.svg)](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml)

TWRP / YARP recovery adaptation for Xiaomi 15S Pro (`dijun`, XRING O1). The project aims to use one recovery image across sampled HyperOS 3 and 4 releases, with sampled HyperOS 2 releases as an extension.

## Status

The bounded offline adaptation work has entered maintenance with explicit unverified boundaries. One candidate contains six exact firmware profiles; this establishes the documented packaging and software selection scope, not complete device compatibility. See the [compatibility matrix](compatibility-matrix.md) for version-specific dependencies and remaining limits.

| | Current scope |
| --- | --- |
| Device | Xiaomi 15S Pro (`dijun`) |
| Platform | XRING O1; maintained device tree `dtsrc/O1_asic_dual` |
| Firmware | HyperOS 3 and 4 priority; sampled HyperOS 2 extension |
| Recovery layout | Kernel comes from the matching system `boot` / `vendor_boot` images |
| Current candidate | [Image, source revision and validation](simulation-report.md) |
| Open work | [Priorities and remaining boundaries](docs/WORK-QUEUE.md) |

The original OS4.0.4.0 full ZIP completed one explicit file-model installation, including all 4933 payload operations, 42 final partition hashes and ten COW initializations. Physical partition mapping, slot changes and reboot-time snapshot merge remain unverified. Patch 0139 fixes a reproduced return-route error after refreshing backup sizes without first opening storage selection. Hardware confirmation remains outstanding; the earlier DPU stack snapshot does not establish a cause for this route error. Resolved vibration and settings issues are excluded from routine rechecks.

## Build

A public checkout is not a standalone build tree. A complete build requires the pinned Android source, locally prepared stock firmware assets, and private signing keys. The repository does not contain full OTA packages, original firmware blobs, signing keys, or built images. See [build requirements](docs/BUILDING.md).

After preparing those dependencies, run the maintained build script from the full workspace:

```sh
bash scripts/compile_recovery.sh
```

The script synchronizes the maintained device tree, runs `installclean`, builds `recoveryimage` with `make -j$(nproc)`, and records source provenance. Patch order and pinned source baselines are in [series.json](dtsrc/O1_asic_dual/patches/series.json).

To check a public checkout without Android build dependencies:

```sh
python3 scripts/check_public_tree.py
python3 scripts/check_documentation.py
```

## Documentation

| Topic | Entry |
| --- | --- |
| User-facing pages and limitations | [Feature guide](FEATURE-USAGE.md) · [Compatibility matrix](compatibility-matrix.md) |
| Firmware samples and ABI profiles | [Firmware guide](docs/FIRMWARE.md) · [Firmware inventory](firmware-inventory.json) |
| Current candidate and validation | [Delivery report](simulation-report.md) · [Work queue](docs/WORK-QUEUE.md) |
| Technical topics | [Documentation index](docs/README.md) |
| Goals and maintenance | [Adaptation goals](ADAPTATION-GOALS.md) · [Maintenance guide](MAINTENANCE.md) |

## Scope

Validation is a mix of firmware inspection, host tests, ARM64 userspace execution, and image checks. Each report identifies its boundaries. Offline success does not establish hardware behavior, and the project does not claim complete device validation.

The public repository contains maintained source, pinned patches, scripts, tests, and documentation. It excludes recovery images, compiled artifacts, complete OTA packages, original firmware binaries, private signing keys, raw device logs, and local caches.

## License

Thanks to Team Win, [TWRP-Test/android_bootable_recovery](https://github.com/TWRP-Test/android_bootable_recovery), and AOSP. Existing file copyrights and licenses remain in force; see [NOTICE](NOTICE). This project does not replace upstream licenses with one blanket license.
