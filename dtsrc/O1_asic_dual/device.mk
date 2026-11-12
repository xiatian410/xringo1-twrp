#
# Copyright (C) 2025 The Android Open Source Project
#
# SPDX-License-Identifier: Apache-2.0
#

# Configure base.mk
$(call inherit-product, $(SRC_TARGET_DIR)/product/base.mk)

# Configure core_64_bit_only.mk
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit_only.mk)

# Configure virtual_ab_ota compression_with_xor.mk
$(call inherit-product, $(SRC_TARGET_DIR)/product/virtual_ab_ota/compression_with_xor.mk)

# Configure emulated_storage.mk
$(call inherit-product, $(SRC_TARGET_DIR)/product/emulated_storage.mk)

# Configure twrp config common.mk
$(call inherit-product, vendor/twrp/config/common.mk)

# Soong namespace
PRODUCT_SOONG_NAMESPACES += \
    $(DEVICE_PATH)

# Disable prebuilt ELF page size check (needed for magiskboot)
PRODUCT_CHECK_PREBUILT_MAX_PAGE_SIZE := false

# Dynamic partitions
PRODUCT_USE_DYNAMIC_PARTITIONS := true

# Enable Fuse Passthrough
PRODUCT_PROPERTY_OVERRIDES += persist.sys.fuse.passthrough.enable=true

# Otacert
PRODUCT_EXTRA_RECOVERY_KEYS += \
    $(DEVICE_PATH)/security/releasekey

# Required modules (vendor boot modules + odm files via prebuilt, task_profiles)
PRODUCT_PACKAGES += \
    task_profiles_recovery
ifneq ($(TARGET_PRODUCT),twrp_dijun)
PRODUCT_PACKAGES += prebuilt
endif

# Recovery fstab (AOSP format)
PRODUCT_COPY_FILES += \
    $(DEVICE_PATH)/recovery.fstab:recovery/root/system/etc/recovery.fstab

# Recovery root overlay (init*.rc files)
ifeq ($(TARGET_PRODUCT),twrp_dijun)
# The inherited stock vendor_boot owns first-stage modules. Do not overlay the
# old 6.6/6.18 module union or unrelated variant firmware in a unified image.
PRODUCT_COPY_FILES += $(filter-out \
    $(DEVICE_PATH)/recovery/root/lib/modules/% \
    $(DEVICE_PATH)/recovery/root/odm/variant/%,\
    $(call find-copy-subdir-files,*,$(DEVICE_PATH)/recovery/root,recovery/root))
else
PRODUCT_COPY_FILES += $(call find-copy-subdir-files,*,$(DEVICE_PATH)/recovery/root,recovery/root)
endif

# System etc files
PRODUCT_COPY_FILES += \
    $(DEVICE_PATH)/system/etc/task_profiles.json:recovery/root/system/etc/task_profiles.json

# Exact-profile runtime; the four other products/old trees are not covered.
ifeq ($(TARGET_PRODUCT),twrp_dijun)
# Original ODM property and DT cirrus,f0-default both specify 130 Hz.
PRODUCT_PROPERTY_OVERRIDES += ro.twrp.haptics_frequency=130 ro.twrp.device_profiles=true
PRODUCT_PACKAGES += dijun-wait-services dijun-usb-config
PRODUCT_COPY_FILES += $(call find-copy-subdir-files,*,$(DEVICE_PATH)/profiles/common/root,recovery/root)
PRODUCT_COPY_FILES += $(call find-copy-subdir-files,*,$(DEVICE_PATH)/prebuilt/common/profile-blobs,recovery/root/system/etc/dijun/blobs)
PRODUCT_COPY_FILES += $(foreach profile,os2-initial os2-final os3-initial os3-final os4-current os4-stable,\
    $(foreach name,selection.conf runtime-files.list modules.plan crypto.prop,\
    $(DEVICE_PATH)/profiles/$(profile)/$(name):recovery/root/system/etc/dijun/profiles/$(profile)/$(name)))
PRODUCT_COPY_FILES += $(foreach script,dijun-select-profile.sh dijun-runtime.sh dijun-prepare-mitee.sh dijun-touch-reports.sh,\
    $(DEVICE_PATH)/profiles/runtime/$(script):recovery/root/system/bin/$(script))
endif

# Keep vendor partition names without building a synthetic super image.
PRODUCT_BUILD_SUPER_PARTITION := false

# Firmware vendor/build.prop.
PRODUCT_SHIPPING_API_LEVEL := 35
