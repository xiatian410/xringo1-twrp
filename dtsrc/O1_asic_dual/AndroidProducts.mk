#
# Copyright (C) 2025 The Android Open Source Project
#
# SPDX-License-Identifier: Apache-2.0
#

PRODUCT_MAKEFILES := \
    $(LOCAL_DIR)/twrp_dijun.mk \
    $(LOCAL_DIR)/twrp_jinghu.mk \
    $(LOCAL_DIR)/twrp_violin.mk

COMMON_LUNCH_CHOICES := \
    twrp_dijun-bp2a-eng \
    twrp_jinghu-bp2a-eng \
    twrp_violin-bp2a-eng
