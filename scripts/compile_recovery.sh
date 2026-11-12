#!/bin/bash
set -e
python3 "$(dirname -- "$0")/sync_device_tree.py" --sync
cd /root/AAA/twrp
if ! command -v python >/dev/null 2>&1; then
    mkdir -p /tmp/dijun-build-bin
    ln -sf "$(command -v python3)" /tmp/dijun-build-bin/python
    export PATH=/tmp/dijun-build-bin:$PATH
fi
export ALLOW_MISSING_DEPENDENCIES=true
source build/envsetup.sh >/dev/null
lunch twrp_dijun-bp2a-eng >/dev/null
make -j$(nproc) installclean
make -j$(nproc) recoveryimage
