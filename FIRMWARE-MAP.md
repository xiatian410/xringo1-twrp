> 历史阶段记录：当前多版本目标、构建与验收以 [ADAPTATION-GOALS.md](ADAPTATION-GOALS.md)、[MAINTENANCE.md](MAINTENANCE.md) 和 [compatibility-matrix.md](compatibility-matrix.md) 为准。旧产物/兼容声明不代表本轮结果。

# 固件里 6.18 内核/模块在哪，怎么被使用

对象：`dijun-ota_full-OS4.0.0.19.XODCNXM-user-17.0-aa6a58e947.zip`
（7.82 GB，内含 `payload.bin` 7,821,653,872 B，AB OTA，SDK 37 / Android 17）

## 一、payload 里的位置

`payload.bin` 头：`magic=CrAU`, version=2, manifest=282,940 B, metadata_signature=267 B，
数据区从偏移 **283,231** 开始。manifest 的大端 protobuf 里，分区在字段 13（PartitionUpdate），
`new_partition_info` 在字段 7，操作（InstallOperation）在字段 8，操作数据偏移是**相对 payload.bin 起点的绝对偏移**。

| 分区 | 分区大小 | op 数 | payload 数据范围 | 压缩 |
|---|---|---|---|---|
| boot | 100,663,296 | 48 | 10,936,232 .. 23,746,364 | REPLACE_BZ, REPLACE_XZ |
| vendor_boot | 100,663,296 | 48 | 7,659,103,037 .. 7,663,033,336 | REPLACE_BZ, REPLACE_XZ |
| init_boot | 16,777,216 | 8 | 25,315,110 .. 27,360,830 | REPLACE_BZ, REPLACE_XZ |
| recovery | 104,857,600 | 50 | 5,844,978,992 .. 5,870,350,822 | REPLACE_BZ, REPLACE_XZ |
| vendor_dlkm | 17,481,728 | 9 | 7,663,033,336 .. 7,674,343,968 | REPLACE_XZ |
| system_dlkm | 18,034,688 | 9 | 6,598,793,240 .. 6,613,369,540 | REPLACE, REPLACE_XZ |
| odm_dlkm | 348,160 | 1 | 1,755,986,197 .. 1,756,019,413 | REPLACE_XZ |

动态分区组：`xring_dynamic_partitions`，组大小 11,263,803,392，super 11,274,289,152，
10 个逻辑分区 `odm odm_dlkm product system system_dlkm system_ext vendor vendor_dlkm mi_product mi_ext`。

## 二、6.18 内核在哪

**`boot.img`**，header v4，`kernel_size = 42,936,832`，`ramdisk_size = 0`。

```
Linux version 6.18.21-android17-5-g1d099fcb35e0-abogki538445360-4k
vermagic=6.18.21-android17-5-g1d099fcb35e0-abogki538445360-4k SMP preempt mod_unload modversions aarch64
```

md5 `3cc2c33ded69eedb533ec3b7e71d641d`，已落到 `prebuilt/kernel-6.18`。
`recovery.img` 的 `kernel_size = 0`——原厂恢复镜像本身不带内核，靠 boot 分区那个 6.18 跑。

## 三、6.18 模块在哪（三处，用途不同）

### 1) vendor_boot.img 的 vendor_ramdisk —— 恢复/首阶段用的那一套

`vendor_boot` header v4，ramdisk 表 1 项，`vendor_ramdisk_size = 5,408,349`，
lz4-legacy 解出 19,422,720 B，424 个 cpio 条目：

```
/lib/modules/6.18.21-android17-5-maybe-dirty-4k/
    kernel/drivers/gpu/drm/display/drm_display_helper.ko     1 个
    extra/xring-modules/...  extra/xiaomi-modules/...       138 个
    modules.dep              139 行（111 行有硬依赖）
    modules.softdep          51 行（1 行注释 + 50 条 softdep）
    modules.load             68 行    <- 正常开机
    modules.load.recovery    139 行   <- 进 recovery
    modules.order  modules.alias  modules.symbols  modules.blocklist
    modules.builtin(.bin/.modinfo/.alias.bin)  modules.dep.bin  ...
```

注意 vermagic 前缀是 `6.18.21-android17-5-maybe-dirty-4k`，与内核的
`...-android17-5-g1d099fcb35e0-abogki538445360-4k` **不同**——厂商的模块是本地
"maybe-dirty" 构建，靠 `CONFIG_MODVERSIONS` 的符号 CRC 对齐，不靠 vermagic 全等
（`same_magic()` 只比较第一个空格之后的部分，两边都是
`SMP preempt mod_unload modversions aarch64`，所以能在 CRC 阶段过关）。

### 2) vendor_dlkm.img（EROFS，17,481,728 B）—— 运行时才挂的驱动

`/vendor_dlkm/lib/modules/` 下 194 个 .ko（`atf_shmem binder_gki bq27z561 btmtk_uart_unify
cfg80211 connfem cpnv ...`），全部同一 vermagic。

### 3) system_dlkm.img（EROFS，18,034,688 B）—— GKI 通用模块

`/system_dlkm/lib/modules/6.18.21-android17-5-g1d099fcb35e0-abogki538445360-4k/` 下
105 个 .ko（`zsmalloc netfs zram virtio_* bluetooth btqca can-* 9pnet rfcomm ...`），
带自己的 `modules.load`（83 条）/`modules.dep`/`modules.softdep`。

`odm_dlkm.img` 只有 4 个文件（`etc/build.prop` 等），没有 .ko。

## 四、固件自己怎么用这些文件

**首阶段（init_boot 里的 `init`）** —— `system/core/init/first_stage_init.cpp`：

1. `uname()` 拿 release，解析出 major/minor；
2. 打开 `/lib/modules`（即 vendor_boot 的 ramdisk），在子目录里找
   名字等于 `uts.release` 或 `major.minor` 的目录，按页大小后缀（`_16k`/`_64k`）过滤；
3. 按 `boot_mode` 选加载清单：正常=`modules.load`，恢复=`modules.load.recovery`，
   `modules.load.charger` 充电；找不到目标清单就退回 `modules.load`；
4. `Modprobe m({dir}, 清单)` 解析 `modules.alias` / `modules.dep` / `modules.softdep` /
   `modules.options` / `modules.blocklist`，按依赖顺序 insmod。

**第二阶段**——`ro.kernel.version` 由 init 用 `uname` 设置（`SetKernelVersion()`），
供 `ueventd` 等按版本找 `/vendor/lib/modules` / `/odm/lib/modules` 下的固件。
`system_dlkm` 由 GKI 的 `system_dlkm` 挂载点提供，走自己的 `modules.load`。

**cmdline / bootconfig**（vendor_boot）：`log_buf_len=1M
firmware_class.path=/vendor/firmware,/odm/firmware, loglevel=7 erofs.reserved_pages=64
fw_devlink.strict=1 ... dump_display.fingerprint=dijun:AndroidV/OS4.0.0.19.XODCN:user`；
bootconfig 单独 206 B：`androidboot.boot_device_root=super`、
`androidboot.super_partition=super`、`androidboot.hardware.platform=O1_asic`、
`androidboot.hardware=O1_asic`、`androidboot.selinux=enforcing`。

## 五、对 TWRP 的直接含义

TWRP 的 `KernelModuleLoader::LoadVendorModules()`（`bootable/recovery/kernel_module_loader.cpp`）
探测顺序是

```
/lib/modules            -> /lib/modules/<ro.kernel.version>  -> /lib/modules/<ver>-gki
/vendor/lib/modules     -> /vendor/lib/modules/1.1
（挂上后再试） /vendor/lib/modules/<ver>  /vendor_dlkm/lib/modules
```

`ro.kernel.version` 是 init 用 `uname` 设的 major.minor。所以只要 ramdisk 里同时有
`/lib/modules/6.6/` 和 `/lib/modules/6.18/`，**同一个 recovery 镜像在 6.6 内核和
6.18 内核上各取各的模块**，不需要任何代码改动——这就是双版本兼容的机制基础。

实测（`scripts/simulate_loader.py`，对构建产物 `out/target/product/O1_asic/ramdisk-recovery.img`）：

```
release 6.18.21-... -> ro.kernel.version=6.18
  探测 /lib/modules         0 *.ko
  探测 /lib/modules/6.18  151 *.ko   <- 选中
  请求 157 项，命中 151，跳过 6（atf_mdr.ko mca_soc_limit.ko nt36532_touch.ko xr_heaps.ko xr_mem_adapter.ko xring_hwspinlock.ko）
  modules.dep 151 条，softdep 47 条，悬空硬依赖 0，未入 dep 的请求 0，softdep 未解析 0

release 6.6.77-... -> ro.kernel.version=6.6
  探测 /lib/modules/6.6   146 *.ko   <- 选中
  请求 157 项，命中 146，跳过 11（bootinfo.ko boottime.ko dump_display.ko mi_memory.ko ...）
  悬空硬依赖 0
```

两套目录互不干扰，各自 `modules.dep` 里的条目在各自目录内全部自洽。
