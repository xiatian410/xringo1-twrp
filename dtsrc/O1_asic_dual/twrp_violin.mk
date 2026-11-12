#
# Copyright (C) 2025 The Android Open Source Project
#
# SPDX-License-Identifier: Apache-2.0
#

DEVICE_PATH := device/xiaomi/O1_asic

# Inherit from device.mk configuration
$(call inherit-product, $(DEVICE_PATH)/device.mk)

PRODUCT_RELEASE_NAME := violin

## Device identifier
PRODUCT_DEVICE := O1_asic
PRODUCT_NAME := twrp_violin
PRODUCT_BRAND := Xiaomi
PRODUCT_MODEL := 25053RP5CC
PRODUCT_MANUFACTURER := Xiaomi

TARGET_OTA_ASSERT_DEVICE := violin

# Device-specific touch modules appended to common TW_LOAD_VENDOR_MODULES
TWRP_TOUCH_MODULES := nt36532_tc_touch.ko xiaomi_touch_violin.ko

# Device-specific partition sizes (source: HyperOS-Port-Python partition_info.json)
BOARD_SUPER_PARTITION_SIZE := 10737418240
BOARD_XRING_DYNAMIC_PARTITIONS_SIZE := 10726932480

# Violin: Xiaomi Pad 7S Pro 12.5 (tablet, landscape)
TW_STATUS_ICONS_ALIGN := center
TW_Y_OFFSET := 99
TW_H_OFFSET := -99
TW_ROTATION := landscape
TW_THEME := landscape_hdpi

PRODUCT_PROPERTY_OVERRIDES += \
    ro.product.system.model=25053RP5CC

PRODUCT_SYSTEM_PROPERTIES += \
    ro.product.system.marketname=Xiaomi_Pad_7S_Pro_12.5

