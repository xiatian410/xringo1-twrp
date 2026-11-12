#
# Copyright (C) 2026 The Android Open Source Project
#
# SPDX-License-Identifier: Apache-2.0
#

LOCAL_PATH := $(call my-dir)

# Device variant directory: prebuilt/<variant>/
# TARGET_PRODUCT is twrp_dijun / twrp_jinghu / twrp_violin (see
# AndroidProducts.mk), and it is always in scope inside an Android.mk.
ifeq ($(TWRP_PREBUILT_VARIANT),)
    TWRP_PREBUILT_VARIANT := $(patsubst twrp_%,%,$(TARGET_PRODUCT))
endif

# --- Vendor boot kernel modules -------------------------------------------
# prebuilt/<variant>/vendor_boot_modules/<major>.<minor>/  ->  /lib/modules/<major>.<minor>/
#
# The shared overlay (recovery/root/lib/modules/<ver>/, installed by
# PRODUCT_COPY_FILES in device.mk) is the single owner of modules.dep /
# modules.softdep and of the common module set.  The variant directory only
# contributes the device specific modules that are not in the overlay
# (jinghu: goodix_core + xiaomi_touch_jinghu; violin: nt36532_tc_touch +
# xiaomi_touch_violin; dijun: synaptics pair, already in the overlay).
#
# Only *.ko are copied here.  The original rule also copied the variant's
# 2-line modules.dep onto the shared 146-line one, dropping the dependency
# graph for everything else, and picked its source directory with
# `ls -d dijun jinghu violin | head -1`, so a violin/jinghu build silently
# staged dijun's touch drivers.  Both are fixed.
#
# The overlay's modules.dep / modules.softdep stay exactly as the vendor wrote
# them (they describe the overlay's own *.ko set).  The variant's dependency
# lines are appended here, one entry per variant *.ko, and only when that module
# has no entry yet - so the shipped graph always matches the shipped *.ko set,
# and rebuilding over an existing out/ directory does not duplicate lines.
include $(CLEAR_VARS)
LOCAL_MODULE := prebuilt
LOCAL_MODULE_TAGS := optional
LOCAL_MODULE_CLASS := ETC
LOCAL_MODULE_PATH := $(TARGET_RECOVERY_ROOT_OUT)
LOCAL_POST_INSTALL_CMD += \
    _root=$(TARGET_RECOVERY_ROOT_OUT); \
    _src=$(LOCAL_PATH)/$(TWRP_PREBUILT_VARIANT); \
    if [ ! -d "$$_src/vendor_boot_modules" ]; then \
        echo "prebuilt: WARNING no vendor_boot_modules for variant '$(TWRP_PREBUILT_VARIANT)'"; \
    else \
        echo "prebuilt: variant $(TWRP_PREBUILT_VARIANT)"; \
        for _vdir in $$_src/vendor_boot_modules/*/; do \
            _ver=$$(basename "$$_vdir"); \
            _dst="$$_root/lib/modules/$$_ver"; \
            mkdir -p "$$_dst"; \
            _n=$$(ls "$$_vdir"/*.ko 2>/dev/null | wc -l); \
            echo "prebuilt:   $$_ver -> lib/modules/$$_ver ($$_n variant modules)"; \
            cp -f "$$_vdir"/*.ko "$$_dst"/ 2>/dev/null || true; \
            for _ko in "$$_vdir"/*.ko; do \
                [ -f "$$_ko" ] || continue; \
                _name=$$(basename "$$_ko"); \
                if ! grep -q "^$$_name:" "$$_dst/modules.dep" 2>/dev/null; then \
                    if grep -q "^$$_name:" "$$_vdir/modules.dep" 2>/dev/null; then \
                        grep "^$$_name:" "$$_vdir/modules.dep" >> "$$_dst/modules.dep"; \
                    else \
                        echo "$$_name: " >> "$$_dst/modules.dep"; \
                    fi; \
                    echo "prebuilt:     dep += $$_name"; \
                fi; \
                _owner=$$(echo "$$_name" | sed 's/\.ko$$//; s/-/_/g'); \
                if [ -f "$$_vdir/modules.softdep" ] && \
                   ! grep -q "^softdep $$_owner " "$$_dst/modules.softdep" 2>/dev/null; then \
                    grep "^softdep $$_owner " "$$_vdir/modules.softdep" >> "$$_dst/modules.softdep" || true; \
                fi; \
            done; \
            _nd=$$(grep -c . "$$_dst/modules.dep" 2>/dev/null || true); \
            _ns=$$(grep -c . "$$_dst/modules.softdep" 2>/dev/null || true); \
            echo "prebuilt:   $$_ver dep entries=$${_nd:-0} softdep lines=$${_ns:-0}"; \
        done; \
    fi
include $(BUILD_PHONY_PACKAGE)

# --- task_profiles.json (needed by twrp_ramdisk) ---
include $(CLEAR_VARS)
LOCAL_MODULE := task_profiles_recovery
LOCAL_MODULE_STEM := task_profiles.json
LOCAL_MODULE_CLASS := ETC
LOCAL_SRC_FILES := ../system/etc/task_profiles.json
LOCAL_MODULE_PATH := $(TARGET_OUT_ETC)
LOCAL_MODULE_TAGS := optional
include $(BUILD_PREBUILT)
