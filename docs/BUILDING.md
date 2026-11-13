# 构建指南

本工程提供设备树和平台补丁，完整构建还需要 Android 源码、原厂资源与本地签名密钥。仅 clone 公开仓库不能直接生成完整镜像。

## 依赖与目录

当前维护脚本使用固定目录：

| 路径 | 内容 |
| --- | --- |
| `/root/AAA/xringo1-twrp` | 本工程完整工作区 |
| `/root/AAA/twrp` | Android 源码树 |
| `dtsrc/O1_asic_dual` | 唯一维护设备树 |
| `/root/AAA/twrp/device/xiaomi/O1_asic` | 同步生成的设备树 |

Android 仓库 revision 见 [pinned.xml](../manifests/pinned.xml)。平台修改基线和补丁顺序见 [series.json](../dtsrc/O1_asic_dual/patches/series.json)，不要用浮动分支代替固定 commit。

其他依赖由所执行脚本决定，包括 Python 3、Android 构建工具以及部分检查需要的 LZ4、QEMU、LVGL、ffmpeg 等；公开源码 CI 不要求这些完整依赖。

## 准备资源

1. 按 [固件映射](FIRMWARE.md) 获取对应样本，使用 [维护流程](../MAINTENANCE.md) 提取并校验关键分区与组件。
2. 恢复公开快照中 `PRIVATE-ASSETS.json` 列出的资源。已有匹配本地资源树时可执行：

   ```bash
   python3 scripts/restore_private_assets.py --from-tree /path/to/local-assets
   ```

   工具逐项校验路径、大小和 SHA-256；不会下载资源或恢复私钥。
3. 自行准备配置引用的本地 `dtsrc/O1_asic_dual/security/releasekey.pk8` 与 `releasekey.x509.pem`。密钥不进入公开同步。

## 同步和构建

在完整工作区执行：

```bash
python3 scripts/sync_device_tree.py
bash scripts/compile_recovery.sh
```

第一条只核对固定基线、维护补丁和待同步内容。构建脚本执行同步后，使用：

```bash
cd /root/AAA/twrp
export ALLOW_MISSING_DEPENDENCIES=true
source build/envsetup.sh
lunch twrp_dijun-bp2a-eng
make -j$(nproc) installclean
make -j$(nproc) recoveryimage
```

脚本还会处理主机只有 `python3` 而没有 `python` 命令的情况。不要通过管道运行 `lunch`，否则环境变量可能只在子 shell 中生效。

当前脚本保留 `ALLOW_MISSING_DEPENDENCIES=true` 配置；它不表示未准备的资源可以省略。构建前仍应完成资源核对，构建后核对最终 ramdisk 内容。

产物：`/root/AAA/twrp/out/target/product/O1_asic/recovery.img`。镜像不携带 kernel，沿用匹配系统的 boot / vendor_boot。最终交付必须先清理安装输出，避免旧库或 stamp 残留。

## 验证

公开 checkout：

```bash
python3 scripts/check_public_tree.py
python3 scripts/check_documentation.py
```

完整工作区中的功能检查按改动影响选择，具体命令见各技术文档与 `tests/` 脚本帮助；不默认全量重跑。当前交付的验证摘要见 [simulation-report.md](../simulation-report.md)。

清理构建成功仅证明构建完成。还需记录补丁、来源、镜像 SHA-256 和封装检查，明确模拟替身、真实执行与未验证边界。本指南不包含刷机或 AVB 修改步骤。
