#
# Copyright (C) 2025 The Android Open Source Project
#
# SPDX-License-Identifier: Apache-2.0
#

# Building with minimal manifest
ALLOW_MISSING_DEPENDENCIES := true

DEVICE_PATH := device/xiaomi/O1_asic

# Rules
BUILD_BROKEN_DUP_RULES := true
BUILD_BROKEN_ELF_PREBUILT_PRODUCT_COPY_FILES := true
BUILD_BROKEN_NINJA_USES_ENV_VARS += RTIC_MPGEN
BUILD_BROKEN_PLUGIN_VALIDATION := soong-libaosprecovery_defaults soong-libguitwrp_defaults soong-libminuitwrp_defaults soong-vold_defaults

# Architecture
TARGET_ARCH := arm64
TARGET_ARCH_VARIANT := armv8-a
TARGET_CPU_ABI := arm64-v8a
TARGET_CPU_ABI2 :=
TARGET_CPU_VARIANT := generic

TARGET_2ND_ARCH := arm
TARGET_2ND_ARCH_VARIANT := armv8-a
TARGET_2ND_CPU_ABI := armeabi-v7a
TARGET_2ND_CPU_ABI2 := armeabi
TARGET_2ND_CPU_VARIANT := generic
TARGET_2ND_CPU_VARIANT_RUNTIME := generic

# Platform identity
PRODUCT_PLATFORM := O1_asic
TARGET_BOOTLOADER_BOARD_NAME := $(PRODUCT_PLATFORM)
TARGET_NO_BOOTLOADER := true

TARGET_BOARD_PLATFORM         := O1_asic
TARGET_BOARD_PLATFORM_GPU     := mali-g720

# Kernel
BOARD_KERNEL_IMAGE_NAME       := Image
BOARD_BOOT_HEADER_VERSION     := 4
BOARD_KERNEL_PAGESIZE         := 4096
TARGET_KERNEL_CLANG_COMPILE   := true

# --- Dual-kernel support -------------------------------------------------
# The recovery image ships NO kernel (stock recovery.img has kernel_size=0),
# so the device boots recovery on whatever kernel the boot partition holds.
# The dijun unified candidate excludes the historical major.minor overlay.
# Additional modules are selected by exact firmware profile and copied from
# matching installed sources (see profiles/ and ../../docs/PROFILE-SELECTION.md).
#
# TWRP_PREBUILT_KERNEL_VERSION only decides which prebuilt Image is used for
# images that DO embed a kernel (e.g. `twrp` boot image / fastboot boot).
#   6.6  -> prebuilt/kernel        (tree default, HyperOS A15 / 6.6.77)
#   6.18 -> prebuilt/kernel-6.18   (OS4.0 / A17 / 6.18.21)
TWRP_PREBUILT_KERNEL_VERSION ?= 6.6
ifeq ($(TWRP_PREBUILT_KERNEL_VERSION),6.6)
    TARGET_PREBUILT_KERNEL := $(DEVICE_PATH)/prebuilt/kernel
else
    TARGET_PREBUILT_KERNEL := $(DEVICE_PATH)/prebuilt/kernel-$(TWRP_PREBUILT_KERNEL_VERSION)
endif
BOARD_MKBOOTIMG_ARGS          += --header_version $(BOARD_BOOT_HEADER_VERSION)
BOARD_MKBOOTIMG_ARGS          += --pagesize $(BOARD_KERNEL_PAGESIZE)

# Ramdisk use lz4
BOARD_RAMDISK_USE_LZ4 := true

# A/B
BOARD_EXCLUDE_KERNEL_FROM_RECOVERY_IMAGE := true

AB_OTA_UPDATER := true
AB_OTA_PARTITIONS += \
    boot \
    init_boot \
    vendor_boot \
    dtbo \
    vbmeta \
    vbmeta_system \
    odm \
    product \
    system \
    system_ext \
    system_dlkm \
    vendor \
    vendor_dlkm

# Verified Boot
BOARD_AVB_ENABLE := true
BOARD_AVB_MAKE_VBMETA_IMAGE_ARGS += --flags 3

# Partitions
BOARD_PROPERTY_OVERRIDES_SPLIT_ENABLED := true

# Workaround for error copying vendor files to recovery ramdisk
TARGET_COPY_OUT_VENDOR := vendor

TARGET_COPY_OUT_ODM := odm
BOARD_ODMIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_USES_VENDOR_DLKMIMAGE := true
TARGET_COPY_OUT_VENDOR_DLKM := vendor_dlkm
BOARD_VENDOR_DLKMIMAGE_FILE_SYSTEM_TYPE := ext4

BOARD_RECOVERYIMAGE_PARTITION_SIZE := 104857600

# Dynamic Partition
# Group/list taken verbatim from the OS4.0.0.19 payload DeltaArchiveManifest
# (dynamic_partition_metadata -> group xring_dynamic_partitions, size 11263803392).
BOARD_SUPER_PARTITION_GROUPS := xring_dynamic_partitions
BOARD_XRING_DYNAMIC_PARTITIONS_PARTITION_LIST := \
    odm odm_dlkm product system system_dlkm system_ext vendor vendor_dlkm mi_product mi_ext

# File systems
TARGET_USERIMAGES_USE_EXT4 := true
TARGET_USERIMAGES_USE_F2FS := true

# Root
BOARD_ROOT_EXTRA_FOLDERS := metadata nvram proinfo protect_f protect_s nvdata nvcfg logfs
BOARD_ROOT_EXTRA_SYMLINKS := /vendor/dsp:/dsp

# Extras
TARGET_SYSTEM_PROP += $(DEVICE_PATH)/system.prop

# Kernel firmware loading stays enforcing; grant only recovery firmware access.
BOARD_SEPOLICY_DIRS += $(DEVICE_PATH)/sepolicy
# The USB helper is a recovery system component, not a vendor property owner.
SYSTEM_EXT_PRIVATE_SEPOLICY_DIRS += $(DEVICE_PATH)/sepolicy/system_ext

# Recovery
TARGET_RECOVERY_PIXEL_FORMAT := BGRA_8888
TARGET_RECOVERY_FSTAB := $(DEVICE_PATH)/recovery.fstab
ifeq ($(TARGET_PRODUCT),twrp_dijun)
# core/Makefile otherwise rsyncs DEVICE/recovery/root independently of the
# filtered PRODUCT_COPY_FILES list, reintroducing legacy modules and variants.
# All dijun overlays are owned by explicit rules in device.mk; this directory
# intentionally has no recovery/root subtree for that implicit rsync step.
TARGET_RECOVERY_DEVICE_DIRS := $(DEVICE_PATH)/profiles/common
endif

# Crypto
TW_INCLUDE_CRYPTO := true
TW_INCLUDE_CRYPTO_FBE := true
TW_INCLUDE_FBE_METADATA_DECRYPT := true
# GUI2 offers explicit per-user unlock; the old skip flag had no consumer in
# this pinned recovery/vold source and did not control secondary-user support.
BOARD_USES_METADATA_PARTITION := true
TW_INCLUDE_OMAPI := true
TW_USE_FSCRYPT_POLICY := 2

# Security patch level
PLATFORM_VERSION := 17
# Keep the Android 16 source/API release table; KeyMint uses the OS profile above.
PLATFORM_VERSION_LAST_STABLE := 16
PLATFORM_SECURITY_PATCH := 2026-09-01
VENDOR_SECURITY_PATCH := $(PLATFORM_SECURITY_PATCH)
BOOT_SECURITY_PATCH := $(PLATFORM_SECURITY_PATCH)

# Tool
TW_INCLUDE_7ZA := true
TW_INCLUDE_ZSTD := true
TW_INCLUDE_REPACKTOOLS := true
TW_INCLUDE_RESETPROP := true
TW_INCLUDE_LIBRESETPROP := true
TW_ENABLE_ALL_PARTITION_TOOLS := true

# Debug
TARGET_USES_LOGD := true
TWRP_INCLUDE_LOGCAT := true
TARGET_RECOVERY_DEVICE_MODULES += debuggerd
RECOVERY_BINARY_SOURCE_FILES += $(TARGET_OUT_EXECUTABLES)/debuggerd
TARGET_RECOVERY_DEVICE_MODULES += strace
RECOVERY_BINARY_SOURCE_FILES += $(TARGET_OUT_EXECUTABLES)/strace

# Fastbootd
TW_INCLUDE_FASTBOOTD := true

# Common TWRP Configuration
#TW_THEME := portrait_hdpi
TW_FRAMERATE := 120
TW_NO_LEGACY_PROPS := true
TW_INCLUDE_NTFS_3G := true
TW_NO_SCREEN_BLANK := true
TW_USE_DMCTL := true
TW_USE_TOOLBOX := true
TARGET_USES_MKE2FS := true
TW_INPUT_BLACKLIST := "hbtp_vm:uinput-xiaomi"
TW_BRIGHTNESS_PATH := "/sys/class/backlight/panel0-backlight/brightness"
TW_MAX_BRIGHTNESS := 2047
TW_EXTRA_LANGUAGES := true
TW_DEFAULT_BRIGHTNESS := 250
TW_EXCLUDE_APEX := true
TW_EXCLUDE_DEFAULT_USB_INIT := true
TW_STATUS_ICONS_ALIGN := center

#TW_PERSIST_DIR := /data/recovery/TWRP
TW_USE_SERIALNO_PROPERTY_FOR_DEVICE_ID := true
TW_SCREEN_BLANK_ON_BOOT := false
TW_DRM_DEVICE := /dev/dri/card0

# Legacy additional-module union for non-profile builds. Dijun's
# ro.twrp.device_profiles branch bypasses this list and all directory probing.
# Per-sample names/CRCs/counts are generated
# in firmware/samples/*/analysis/facts.json and docs/firmware-compatibility.json.
TW_LOAD_VENDOR_MODULES := \
    "ab_slot_bootable_ctrl.ko apb_timer.ko atf_mdr.ko bootinfo.ko boottime.ko bq27z561.ko charger_partition.ko dmd.ko drm_display_helper.ko \
    dse.ko dump_display.ko dw_apb_rtc.ko dw_wdt.ko ex_pd_protocol.ko external_tcpc.ko fbe.ko flowctrl.ko fsa4480-i2c.ko \
    fts_touch_spi.ko hl7603.ko hwid.ko kmod_protect.ko lp-dfx.ko mca_basic_wireless.ko mca_bmd.ko mca_buckchg_jeita.ko mca_business_battery_comp.ko \
    mca_business_charger_comp.ko mca_business_misc_comp.ko mca_charge_interface.ko mca_charge_mievent.ko mca_charger_thermal.ko mca_common.ko mca_connector_antiburn.ko mca_event.ko mca_hwid.ko \
    mca_ibat_ocp_monitor.ko mca_log.ko mca_lpd_detect.ko mca_parse_dts.ko mca_path_control.ko mca_pd_auth.ko mca_platform_base.ko mca_platform_bc12_class.ko mca_platform_buckchg_class.ko \
    mca_platform_cp_class.ko mca_platform_fg_ic_ops.ko mca_platform_loadsw_class.ko mca_platform_subpmic_cid_class.ko mca_platform_wireless_class.ko mca_protocol_class.ko mca_protocol_pd_class.ko mca_protocol_qc_class.ko mca_quick_wireless.ko \
    mca_smart_charge.ko mca_soc_limit.ko mca_strategy_buckchg.ko mca_strategy_class.ko mca_strategy_fg_class.ko mca_strategy_fg_comp.ko mca_strategy_quickchg.ko mca_subpmic_sysfs.ko mca_sysfs.ko \
    mca_vbat_ovp_monitor.ko mca_wireless_revchg.ko mca_workqueue.ko mca_xring_o1_sysfs.ko mca_xring_panel.ko mca_xring_usb.ko media-dvfs.ko mi_memory.ko mi_wq_dynamic_priority.ko \
    miev.ko mitee.ko nanosic_platform.ko nt36532_touch.ko nuvolta_1652.ko os_cpu_plat_common.ko os_cpu_vip_sched.ko perf-actuator.ko peri-dvfs.ko \
    pinctrl-xr.ko protocol_pd_manager.ko ps5169.ko redriver.ko sc8510.ko sc8577.ko sc8581.ko sc96231_comp.ko sc9625_comp.ko \
    sched-walt.ko securelib.ko shub_app_router.ko shub_boot_prepare.ko shub_ipc_drv.ko subpmic_sc6601a.ko subpmic_sc6601a_cid.ko subpmic_sc6601a_driver.ko \
    tcpc_sc2150.ko tcpc_sc660x.ko touch_boost.ko tui.ko xm_battmngr_init.ko xm_charger.ko xm_utils.ko xr-clk.ko \
    xr-pmic-spmi.ko xr-spmi-controller.ko xr_bootup_stage1.ko xr_bootup_track_stage1.ko xr_cpufreq.ko xr_cpuidle.ko xr_ddr.ko xr_dfx.ko xr_doze.ko \
    xr_dynamic_governor.ko xr_ffa-module.ko xr_heaps.ko xr_hwspinlock.ko xr_ip_reset.ko xr_ipc.ko xr_isp.ko xr_kdump.ko xr_mem_adapter.ko \
    xr_mem_s1.ko xr_minidump.ko xr_pm_comm.ko xr_pmic.ko xr_regulator.ko xr_rpmb.ko xr_spi_mmio.ko xr_timestamp.ko xr_uart.ko xr_ufs.ko \
    xr_vh_printk.ko xr_vote_mng.ko xring-ade.ko xring-drm.ko xring-dwc3.ko xring-noc.ko xring-ocm.ko xring-xhci-hcd.ko xring_axi_dmac.ko \
    xring_hwspinlock.ko xring_i2c.ko xring_ras.ko xring_smmu.ko xring_thermal.ko xring_trng.ko xring_usb.ko xring_usb_adsp_stub.ko xring_usb_phy.ko \
    xring_usb_repeater.ko xring_usb_reset.ko xrsp_driver.ko \
    xring_audio_hw_third.ko $(TWRP_TOUCH_MODULES)"
TW_LOAD_VENDOR_MODULES_EXCLUDE_GKI := true
TW_LOAD_VENDOR_BOOT_MODULES := true
TW_LOAD_PREBUILT_MODULES_AT_FIRST := false
# ro.twrp.cpu_temp_type selects cpu-crg; the generic ordinal is not used on dijun.
# All five sampled stock init.target.rc files wait for this battery supply.
# Read actual sysfs values for the status bar; Health's OTA fallback is 100%.
TW_USE_LEGACY_BATTERY_SERVICES := true
TW_CUSTOM_BATTERY_PATH := "/sys/class/power_supply/battery"
TW_BACKUP_EXCLUSIONS := /data/fonts

# Match the stock ramdisk-only recovery header (OS version/SPL field zero).
BOARD_RECOVERY_MKBOOTIMG_ARGS = $(BOARD_MKBOOTIMG_ARGS) --os_version 0.0.0 --os_patch_level ""
