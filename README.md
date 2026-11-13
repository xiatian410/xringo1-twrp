# Xiaomi 15S Pro Recovery

[![Source and patch integrity](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml/badge.svg)](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml)

TWRP / YARP recovery adaptation for Xiaomi 15S Pro (`dijun`, XRING O1). The project targets one recovery image for HyperOS 3 and 4, with HyperOS 2 support considered where firmware compatibility allows it.

## Project Status

The project is under active development. Six firmware profiles are included in the unified candidate, but this does not mean every feature is validated on every release.

| Item | Current scope |
| --- | --- |
| Device | Xiaomi 15S Pro (`dijun`) |
| Platform | XRING O1; maintained device-tree directory `O1_asic` |
| Firmware | HyperOS 3 and 4 priority; sampled HyperOS 2 versions as an extension |
| Recovery layout | Kernel is supplied by the matching system `boot` / `vendor_boot` images |
| Current image and validation | [Delivery report](simulation-report.md) |
| Open work | [Work queue](docs/WORK-QUEUE.md) |

The OS4.0.4 full OTA package has completed one offline installation model run with `MODEL_SUCCESS`. The model does not verify device partition mapping, mounts, hardware services, boot-slot behavior, or post-reboot snapshot merging. The exact package and scope are documented in the [installation-chain report](docs/INSTALL-CHAIN-VALIDATION.md#stock-zip-allocated-success).

## Prepare and Build

Install Git and Python 3 to inspect the public source:

```sh
git clone https://github.com/xiatian410/xringo1-twrp.git
cd xringo1-twrp
python3 scripts/check_public_tree.py
python3 scripts/check_documentation.py
```

For a recovery build, prepare the pinned Android source revision, matching local firmware assets, and local signing keys as described in the [build guide](docs/BUILDING.md). Then run:

```sh
bash scripts/compile_recovery.sh
```

The build script synchronizes the maintained device tree, runs `installclean`, and builds with `make -j$(nproc) recoveryimage`. Patch order and baseline are recorded in [series.json](dtsrc/O1_asic_dual/patches/series.json).

## Documentation

| Topic | Entry |
| --- | --- |
| User-facing functions and limits | [Feature guide](FEATURE-USAGE.md) · [Compatibility matrix](compatibility-matrix.md) |
| Firmware sources and ABI comparison | [Firmware guide](docs/FIRMWARE.md) · [Firmware inventory](firmware-inventory.json) |
| Current delivery and remaining work | [Delivery report](simulation-report.md) · [Work queue](docs/WORK-QUEUE.md) |
| Technical implementation and evidence scope | [Documentation index](docs/README.md) |
| Adaptation requirements and maintenance | [Goals](ADAPTATION-GOALS.md) · [Maintenance](MAINTENANCE.md) |

## Public Repository Scope

The repository contains maintained device-tree sources, pinned patches, scripts, tests, and documentation. It excludes recovery images, compiled artifacts, complete OTA packages, original firmware binaries, private signing keys, raw device logs, and local caches. Build prerequisites and private assets must be prepared locally; see the [build guide](docs/BUILDING.md).

CI checks public source integrity and documentation. Passing CI or offline simulation does not establish hardware behavior. Each technical report states its tested scope and remaining limits. Contributions and issue reports should include the firmware version, candidate image hash, reproduction steps, and expected versus observed behavior; remove personal data and secrets from logs.

## License and Acknowledgements

Thanks to Team Win, [TWRP-Test/android_bootable_recovery](https://github.com/TWRP-Test/android_bootable_recovery), and AOSP. Existing file copyrights and licenses remain in force; see [NOTICE](NOTICE). This project does not replace upstream licenses with one blanket license.
