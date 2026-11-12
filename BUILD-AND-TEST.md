> 历史阶段记录：当前多版本目标、构建与验收以 [ADAPTATION-GOALS.md](ADAPTATION-GOALS.md)、[MAINTENANCE.md](MAINTENANCE.md) 和 [compatibility-matrix.md](compatibility-matrix.md) 为准。旧产物/兼容声明不代表本轮结果。

# 构建与实测记录

## 当前多版本适配目标

见 [ADAPTATION-GOALS.md](ADAPTATION-GOALS.md)：优先 OS3/OS4 单镜像，条件允许扩展 OS2；
本轮仅固件分析、构建和模拟验证。下文实机命令属于历史说明，不是本轮执行步骤。

## 一、构建环境

- 主机：Debian 13 (trixie)，x86_64，16 核，31 GB 内存，磁盘余 157 GB
- AOSP 树：`/root/AAA/twrp`（76 GB），`repo init -u https://github.com/TWRP-Test/platform_manifest_twrp_aosp -b twrp-16.0`
- 设备树：`/root/AAA/xringo1-twrp/dtsrc/O1_asic_dual` → 同步到 `/root/AAA/twrp/device/xiaomi/O1_asic`
- lunch：`twrp_dijun-bp2a-eng`

### 构建过程中改的两处

1. **`device.mk` 增加 `PRODUCT_BUILD_SUPER_PARTITION := false`**
   设备树的 `BOARD_XRING_DYNAMIC_PARTITIONS_PARTITION_LIST` 里含 `mi_ext`、`mi_product`
   （这俩确实在真机 super 里），但 soong 的 fsgen 只认 AOSP 的分区名表，
   直接报
   `partition "mi_ext" is not a super image supported partition`。
   我们从不刷自建 super.img，关掉 super 合成即可，分区列表保留（TWRP 靠它算 super 布局）。

2. **构建脚本不能用管道包 `lunch`**
   `lunch ... | tail` 会把 lunch 放进子 shell，导出的变量全部丢失，
   后续 `mka` 走 `TARGET_RELEASE=trunk_staging` 分支直接
   `panic: Missing config trunk_staging`。改成 `lunch ... >/dev/null` 后正常。

## 二、构建结果

```
mka recoveryimage -j12     -> 12 分 55 秒，29900 个任务，0 失败
out/target/product/O1_asic/recovery.img   104,857,600 B
out/target/product/O1_asic/ramdisk-recovery.img   56,925,255 B  (lz4-legacy，解开 141,121,280 B)
```

`recovery.img` header v4，`kernel_size = 0`（`BOARD_EXCLUDE_KERNEL_FROM_RECOVERY_IMAGE := true`，
与原厂 recovery.img 一致），`ramdisk_size = 56,925,255`，
末尾 832 B 的 AVB hash footer，`Algorithm: NONE`（未签名，`avbtool info_image` 可读）。

ramdisk 解开 1211 个 cpio 条目，关键内容：

```
lib/modules/6.6/     146 *.ko + modules.dep(146) + modules.softdep(100)
lib/modules/6.18/    151 *.ko + modules.dep(151) + modules.softdep(45)
system/bin/recovery  3,354,888 B  aarch64 PIE，67 处 twrp 标记 + 19 处 gui2 符号
system/bin/init      2,760,632 B
system/lib64/        192 个 .so（recovery 的 63 个 NEEDED 全部可解析）
odm/variant/{dijun,jinghu,violin}/   三机型触摸固件与 lib64
res/images 103 张 + res/fonts 4 个字体
```

`prebuilt/Android.mk` 的后安装日志确认为 dijun 只合并了 2 个变体模块：

```
prebuilt: variant dijun
prebuilt:   6.6 -> lib/modules/6.6 (2 variant modules)
prebuilt:     dep += synaptics_tcm2.ko
prebuilt:     dep += xiaomi_touch_dijun.ko
prebuilt:   6.6 dep entries=2 softdep lines=0        <- 变体目录自身只有 2 条，未覆盖共享的 146 条
```

构建后 `lib/modules/{6.6,6.18}/modules.{dep,softdep}` 与设备树里的源文件**逐字节相同**，
无重复行——说明变体合并逻辑幂等，没有把共享依赖表冲掉。

## 三、两个内核版本的镜像

`recovery.img` 不带内核（原厂如此：内核在 boot 分区）。为了能 `fastboot boot` 起来测，
用 `mkbootimg` 把构建出的 ramdisk 分别与两个 prebuilt Image 拼成可直接引导的 boot 镜像：

| 文件 | 内核 | ramdisk | 总大小 | md5 |
|---|---|---|---|---|
| `imgs/built/twrp-recovery.img` | 无 | 56,925,255 | 104,857,600 | b1ec63a4f225a2e30825f0447fec785f |
| `imgs/built/twrp-boot-6.6.img` | 6.6.77（34,148,032） | 56,925,255 | 91,078,656 | 5f3d7b2d71ac354388cb0cc3e5fa4373 |
| `imgs/built/twrp-boot-6.18.img` | 6.18.21（42,936,832） | 56,925,255 | 99,868,672 | 3b6561ce0cf997a88e989c960eee8baf |

嵌入的内核与 `prebuilt/kernel`、`prebuilt/kernel-6.18` 的 md5 逐一核对一致
（`9c663b9b...` / `3cc2c33d...`）。

体积对分区限额：

| 镜像 | 大小 | 分区 | 余量 |
|---|---|---|---|
| twrp-boot-6.6.img | 91,078,656 | boot 100,663,296 | +9,584,640 |
| twrp-boot-6.18.img | 99,868,672 | boot 100,663,296 | +794,624 |
| twrp-recovery.img | 104,857,600 | recovery 104,857,600 | 0（正好填满） |

三个都装得下；6.18 版只剩 0.79 MB 余量，ramdisk 再涨就塞不进 boot 分区了。

## 四、静态仿真：双版本选择确实成立

`scripts/simulate_loader.py` 复刻 `kernel_module_loader.cpp` 的目录探测与
`WriteModuleList()`／libmodprobe 的过滤逻辑，跑构建产物：

```
release 6.18.21-android17-5-g1d099fcb35e0-abogki538445360-4k  -> ro.kernel.version=6.18
  probe /lib/modules          0 *.ko
  probe /lib/modules/6.18   151 *.ko   <- 选中
  请求 157 项，命中 151，跳过 6 个（atf_mdr mca_soc_limit nt36532_touch xr_heaps xr_mem_adapter xring_hwspinlock）
  dep 151 条，softdep 47 条，悬空硬依赖 0，请求项全部在 dep 里，softdep 引用全部可解析

release 6.6.77-android15-8-g5770c661275f-abogki443185593-4k  -> ro.kernel.version=6.6
  probe /lib/modules/6.6    146 *.ko   <- 选中
  请求 157 项，命中 146，跳过 11 个（bootinfo boottime dump_display mi_memory ...）
  悬空硬依赖 0

RESULT: OK
```

157 项的 `TW_LOAD_VENDOR_MODULES` 是从构建出的 `system/bin/recovery` 里 `strings` 出来的
（`ab_slot_bootable_ctrl.ko ... xrsp_driver.ko synaptics_tcm2.ko xiaomi_touch_dijun.ko`），
确认它被真正编进二进制并覆盖两套模块的全部 146+151 个文件。

## 五、AVB 签名：刷机前必须处理

自建 `recovery.img` 的 footer 是 `Algorithm: NONE`，而原厂：

```
recovery  : SHA256_RSA4096, key sha1 eea2cb523d1b26d27160c61e58db85e61711d0f0, rollback idx 11
vbmeta    : SHA256_RSA4096, key sha1 4d3c99cf6e79eaa26268ed601cfc341736f987ef, rollback idx 10
vbmeta_vendor / vbmeta_system 用同一把 4d3c99cf...
设备树 security/releasekey 的公钥 sha1 是 b440b0a78da6e64434c803ba52f2bf83aac86651 —— 三把都不匹配
```

recovery 的 hash 描述符挂在**顶层 vbmeta.img**（不是 vbmeta_vendor），
所以只刷 recovery 分区、不动 vbmeta，bootloader 校验会失败。

两条路：

1. **刷进 A/B 的 recovery 槽 + 关验证**：`fastboot --disable-verity --disable-verification flash vbmeta <原厂 vbmeta.img 重签或空 vbmeta>`；
2. **不刷，直接 `fastboot boot twrp-boot-6.6.img`**——绕过 recovery 分区与 vbmeta，
   最适合首次验证（6.6 版 91 MB，boot 分区装得下）。

## 六、实机测试：没做成

```
$ adb devices        -> 空
$ fastboot devices   -> 空
$ lsusb              -> 只有 VMware 虚拟鼠标/集线器
```

这台是 VMware 虚拟机，没有任何 USB 直通的 Android 设备，`fastboot boot` / `flash` 无从执行。
**所以"上机验证"这一步没有发生**，下面的检查清单留给有设备时执行。

### 上机检查清单

```bash
# 1. 首次：只临时引导，不动分区
fastboot boot twrp-boot-6.6.img

# 2. 起来后立刻确认模块选择
adb shell dmesg | grep -i "ro.kernel.version"      # 期望 6.6
adb shell "logcat -d | grep -E 'Checking directory|Modules Loaded|modules from'"
#    期望看到 Checking directory: /lib/modules/6.6 与 146 附近的数量

# 3. 确认触摸
adb shell "cat /proc/modules | grep -E 'xiaomi_touch|synaptics'"   # 期望两个都在

# 4. 确认分区挂载（mi_ext / mi_product 是这版新加的）
adb shell "cat /proc/mounts | grep -E 'mi_ext|mi_product|vendor_dlkm'"

# 5. 确认 UI
adb shell screencap -p /sdcard/twrp.png && adb pull /sdcard/twrp.png

# 6. 换 6.18 内核再走一遍
fastboot boot twrp-boot-6.18.img
adb shell "logcat -d | grep 'Checking directory'"   # 期望选中 /lib/modules/6.18

# 7. 只有 1~6 全过，才考虑刷进 recovery 分区（需先处理 vbmeta）
```

---

# 七、首次实机结果与修复（2026-11-10）

## 7.1 实机反馈

```
fastboot boot twrp-boot-6.6.img
  Sending 'boot.img' (88944 KB)  OKAY [ 2.264s]
  Booting  FAILED (remote: 'unknown command')      <- 该 bootloader 没有 boot 命令
```

刷进 recovery 分区后 TWRP 能起来，ADB 可用，但每 5 秒重启一次：

```
Starting TWRP 3.7.1_16-0-a93a12ec ... (pid 307)
Display Mode 0 resolution: 1440 x 3200 @ 120 FPS
Allocating buffer with resolution 1440 x 3200 pitch: 5760 bpp: 32, size: 18432000
TWRP DRM: display 0 found 0/2 primary planes for CRTC index 0
Failed to init display
gui2: minui display initialization failed
E:GUI2 exited with error 1.
```

并且触摸全无：`/proc/modules` 里没有 `xiaomi_touch`/`synaptics`，
`getevent` 只有 `pwrkey` / `volumeup` / `volumedown` 三个按键节点。

## 7.2 根因一：minui 的平面选择是高通专用

`twrpminui/graphics_drm.cpp` 是从 CLO（高通）移植的，挑平面时只认名
`capabilities` 的属性，再解析其 blob 里的 `primary_smart_plane_id=`；
层混合器数量又只认 connector 上名 `mode_properties` 的拓扑 blob
（`sde_singlepipe` / `sde_dualpipe` ...）。

实测玄戒 `xring-drm.ko` 里：

| 字符串 | 出现次数 |
|---|---|
| `primary_smart_plane_id` | 0 |
| `mode_properties` | 0 |
| `capabilities` | 12（是标准 DRM 的 properties 名，非 CLO blob） |

所以 `selected` 恒为 0，而 `number_of_lms` 停在 `DEFAULT_NUM_LMS = 2`，
报出 `found 0/2`。分母的 2 恰好证明拓扑根本没读到。

**修法**（`dtsrc/O1_asic_dual/0001-generic-kms-plane-selection.patch`，25 增 5 删）：

1. 新增 `plane_is_primary()`：`capabilities` blob 判不了时，回退到标准
   DRM 的不可变 `type` 枚举，`type == DRM_PLANE_TYPE_PRIMARY(1)` 即认为是主平面；
2. `mode_properties` 缺失时把 `number_of_lms` 定为 1——通用 KMS 驱动由一个主平面
   直接驱动整个 connector，若仍按 2 走 `AtomicPopulatePlane()` 的
   `src_w = width / number_of_lms` 横向切分，会只画出半个屏幕或重复贴图；
3. 选出平面后再用实际数量校正一次 `number_of_lms`。

## 7.3 根因二：模块加载时机晚于 GUI

TWRP 自己的 `KernelModuleLoader::LoadVendorModules()` 挂在
`partitionmanager.cpp:478` 的 `ProcessFstabFiles()` 里，而 `main()`
是先 `gui2_start()` → 图形初始化，失败就 `return -1` 由 init 重启进程。
图形这一关过不去，就永远走不到加载模块那一步，于是触摸、panel、DRM 全都没有。

**修法**：给每个版本目录生成 `modules.load.recovery`（`scripts/gen_loadrecovery.py`），
让 init 的 first-stage `LoadKernelModules()` 在 TWRP 启动前就地加载：

```
6.6/modules.load.recovery    146 条（按 modules.dep 拓扑排序）
6.18/modules.load.recovery   151 条
```

init 会按 `uname -r` 的 major.minor 自动选中对应目录，所以双版本仍是全自动。
顺序上 `drm_display_helper` → `xring-drm` → `xring-ocm` → `mca_xring_panel`，
触摸是 `xiaomi_touch_dijun` → `synaptics_tcm2`。

## 7.4 构建中踩到的坑：改 .so 不生效

改了 `graphics_drm.cpp` 后重编，`libtwrpminui.so` 确实更新了，
但 ramdisk 里躺的还是旧文件。原因是 recovery 把库靠
`bootable/recovery/prebuilt/Android.mk` 的 `relink_libraries` 伪目标拷进
`recovery/root/system/lib64/`，其 stamp 只依赖库文件**存在性**，
上游内容变化不会触发重跑。删掉 stamp 才真正刷新：

```bash
rm -f out/target/product/O1_asic/recovery/root/relink_libraries-timestamp \
      out/target/product/O1_asic/obj/FAKE/relink_libraries_intermediates/relink_libraries-timestamp \
      out/target/product/O1_asic/obj/PACKAGING/recovery_intermediates/ramdisk_files-timestamp \
      out/target/product/O1_asic/ramdisk-recovery.{cpio,img} \
      out/target/product/O1_asic/recovery.img
```

## 7.5 修复后的产物

```
imgs/built/twrp-recovery.img   104,857,600   b83ad9659fa1a80a1eaf70f79ed260fd
imgs/built/twrp-boot-6.6.img    91,082,752   366c296cebe691ce69a247797e3cd179
imgs/built/twrp-boot-6.18.img   99,872,768   cc4e0fd3e9cfc79191c3ab164c6027d4
ramdisk-recovery.img            56,930,293（比上一版 +5,038 B）
```

ramdisk 内已确认：

```
system/lib64/libtwrpminui.so      268,648 B  b5a01b94...（含 type 回退 + lm=1）
lib/modules/6.6/modules.load.recovery    2,492 B  146 行
lib/modules/6.18/modules.load.recovery   2,580 B  151 行
```

## 7.6 历史产物说明

上节镜像和自动生成的 first-stage 模块列表已停用；当前实机基线见文末。
本机使用正常的 recovery A/B 分区，测试当前候选只刷 recovery。

## MiTEE 解密适配候选（2026-11-11）

固件服务链路、设备树改动和验证边界见 [CRYPTO-ADAPTATION.md](dtsrc/O1_asic_dual/CRYPTO-ADAPTATION.md)。
输出 `imgs/built/twrp-recovery-mitee.img`；这是基于已构建 recovery 的 ramdisk 重打包，尚未证明实机解密。

## 实机基线：元数据与用户 0 解密通过（2026-11-11）

`imgs/built/twrp-recovery-mitee-bootfix.img`，MD5
`5819f969bceb558cf734d5ae5608e211`。构建命令 `make -j$(nproc) recoveryimage`，
30 并行。`logs/bootfix-recovery.log` 确认元数据映射 `/dev/block/mapper/userdata`、
`User 0 Decrypted Successfully!`、内部存储 `/data/media/0`。
保留为当前已验证基线；6.6、用户 999、备份恢复和实际刷写不在这次验证范围内。

## 外设修复候选：2026-11-11

输出：`imgs/built/twrp-recovery-devicefix.img`，MD5 `1795eee8bfec097568a0ead30182ba67`；
校验与检查记录在同名 `.json`，源码哈希见同名 `-sources.json`。
原已验证可解密镜像另存 `imgs/verified/twrp-recovery-mitee-bootfix.img`。

本次补全 MTP FunctionFS、北京时间默认与旧默认迁移、6.18 Cirrus 震动驱动和固件，
修复 GUI2 连续电源短按丢失/未提交关屏请求无法取消。源代码回归测试已通过，
实际外设行为需要真机验证。完整修改依据见设备树 `CRYPTO-ADAPTATION.md` 文末。

```powershell
fastboot --slot=all flash recovery .\twrp-recovery-devicefix.img
fastboot reboot recovery
```

进入后确认解密仍成功，再测试电脑能否复制文件、点击震动与快速关屏/亮屏。
若需要记录当前外设状态，使用有界命令，无需 `adb wait-for-device`：

```powershell
adb shell 'date; date -u; getprop persist.sys.timezone; getprop sys.usb.config; getprop sys.usb.state; getprop sys.usb.ffs.ready; getprop sys.usb.ffs.mtp.ready; ls /dev/usb-ffs/mtp; cat /proc/bus/input/devices'
adb shell dmesg | Select-String 'cs40l26|haptic|firmware|syna|suspend|resume'
adb pull /tmp/recovery.log .\devicefix-recovery.log
adb logcat -b all -d > .\devicefix-logcat.txt
```

源码构建：`bash scripts/compile_recovery.sh`；脚本先清理安装输出，再以
`make -j$(nproc) recoveryimage` 打包，避免旧 relink 库和遗留模块列表进入镜像。
