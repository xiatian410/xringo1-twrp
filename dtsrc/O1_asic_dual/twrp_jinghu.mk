#
# Copyright (C) 2025 The Android Open Source Project
#
# SPDX-License-Identifier: Apache-2.0
#

DEVICE_PATH := device/xiaomi/O1_asic

# Inherit from device.mk configuration
$(call inherit-product, $(DEVICE_PATH)/device.mk)

PRODUCT_RELEASE_NAME := jinghu

## Device identifier
PRODUCT_DEVICE := O1_asic
PRODUCT_NAME := twrp_jinghu
PRODUCT_BRAND := Xiaomi
PRODUCT_MODEL := 25032RP42C
PRODUCT_MANUFACTURER := Xiaomi

TARGET_OTA_ASSERT_DEVICE := jinghu

# Device-specific touch modules appended to common TW_LOAD_VENDOR_MODULES
TWRP_TOUCH_MODULES := goodix_core.ko xiaomi_touch_jinghu.ko

# Device-specific partition sizes (source: HyperOS-Port-Python partition_info.json)
BOARD_SUPER_PARTITION_SIZE := 11811160064
BOARD_XRING_DYNAMIC_PARTITIONS_SIZE := 11800674304

# Jinghu: Xiaomi Pad 7 Ultra (tablet, landscape)
TW_STATUS_ICONS_ALIGN := center
TW_Y_OFFSET := 99
TW_H_OFFSET := -99
TW_ROTATION := landscape
TW_THEME := landscape_hdpi

PRODUCT_PROPERTY_OVERRIDES += \
    ro.product.system.model=25032RP42C

PRODUCT_SYSTEM_PROPERTIES += \
    ro.product.system.marketname=Xiaomi_Pad_7_Ultra




