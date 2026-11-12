#
# Copyright (C) 2025 The Android Open Source Project
#
# SPDX-License-Identifier: Apache-2.0
#

DEVICE_PATH := device/xiaomi/O1_asic

# Inherit from device.mk configuration
$(call inherit-product, $(DEVICE_PATH)/device.mk)

PRODUCT_RELEASE_NAME := dijun

## Device identifier
PRODUCT_DEVICE := O1_asic
PRODUCT_NAME := twrp_dijun
PRODUCT_BRAND := Xiaomi
PRODUCT_MODEL := 25042PN24C
PRODUCT_MANUFACTURER := Xiaomi

TARGET_OTA_ASSERT_DEVICE := dijun

# Device-specific touch modules appended to common TW_LOAD_VENDOR_MODULES
TWRP_TOUCH_MODULES := synaptics_tcm2.ko xiaomi_touch_dijun.ko

# Device-specific partition sizes (source: HyperOS-Port-Python partition_info.json)
BOARD_SUPER_PARTITION_SIZE := 11274289152
BOARD_XRING_DYNAMIC_PARTITIONS_SIZE := 11263803392

# Dijun: Xiaomi 15S Pro (phone, portrait)
TW_STATUS_ICONS_ALIGN := center
TW_ROTATION := 0
TW_THEME := portrait_hdpi

PRODUCT_PROPERTY_OVERRIDES += \
    ro.product.system.model=25042PN24C

PRODUCT_SYSTEM_PROPERTIES += \
    ro.product.system.marketname=Xiaomi_15S_Pro



