# Xiaomi 15S Pro · XRING O1 Recovery

[![Source integrity](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml/badge.svg)](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml)

面向 **Xiaomi 15S Pro（dijun / XRING O1）** 的 TWRP / YARP 设备树与平台补丁。优先使用同一份 Recovery 镜像适配 HyperOS 3、HyperOS 4，并在兼容条件允许时覆盖已收录的 HyperOS 2 样本。

> 项目仍在适配中。公开仓库提供维护源码、构建配置和离线验证工具，不提供编译镜像。CI 通过不代表设备功能或完整 OTA 安装已验收。

## 适配状态

| 范围 | 状态 |
| --- | --- |
| 固件 | OS2、OS3、OS4 各两份独立档案；不自动外推到中间版本 |
| 已修正 | 内置 UFS 被误列为 OTG、刷入目标列表、普通界面的 NV 操作限制 |
| 最近交付 | 温度避让中央摄像头、ext 扩容尺寸边界、A/B 更新器同步拒绝收尾 |
| 用户确认 | OS4 震动正常；backup-manifest 基线设置正常 |
| 待完成 | 自动触摸启动、完整 OTA / 快照安装，以及部分存储与服务全流程 |
| 待定位 | 备份容量刷新完成后，现场页面仍未结束 |

候选名称、SHA-256 与验证边界统一记录在 [交付报告](simulation-report.md)；具体功能状态见 [兼容矩阵](compatibility-matrix.md)，当前优先级见 [工作队列](docs/WORK-QUEUE.md)。历史结果只适用于对应版本和输入。

## 文档

| 用途 | 入口 |
| --- | --- |
| 使用功能与了解限制 | [功能说明](FEATURE-USAGE.md) |
| 准备资源与编译 | [构建指南](BUILD-AND-TEST.md) · [固件映射](FIRMWARE-MAP.md) |
| 了解目标与验收要求 | [适配目标](ADAPTATION-GOALS.md) |
| 查阅具体修正 | [技术文档索引](docs/README.md) |
| 维护和提交修改 | [维护指南](MAINTENANCE.md) · [贡献指南](CONTRIBUTING.md) |

## 源码结构

```text
.
├── dtsrc/O1_asic_dual/   # 设备树、六份固件档案与固定平台补丁
├── manifests/           # Android 源码 revision
├── scripts/             # 提取、同步、构建与核验工具
├── tests/               # 离线检查源码与合成夹具
├── docs/                # 分主题技术说明与公开验证摘要
└── tools/               # 诊断采集工具源码
```

Recovery 上游为 [TWRP-Test/android_bootable_recovery](https://github.com/TWRP-Test/android_bootable_recovery)。仓库提供可追溯补丁，不复制完整 Android 源码；平台基线、补丁顺序和摘要见 [series.json](dtsrc/O1_asic_dual/patches/series.json)。

## 构建

公开 checkout 还需补齐固定版本的 Android 源码、匹配的原厂资源与本地签名密钥。按 [构建指南](BUILD-AND-TEST.md) 准备完整工作区后执行：

```bash
python3 scripts/sync_device_tree.py
bash scripts/compile_recovery.sh
```

构建脚本同步设备树，执行 `installclean`，再运行 `make -j$(nproc) recoveryimage`。当前目录约定和产物路径见构建指南。

## 验证

公开 checkout 可运行以下检查，无需原厂固件：

```bash
python3 scripts/check_public_tree.py
python3 scripts/check_documentation.py
```

GitHub Actions 检查公开文件清单、Python / JSON 语法、补丁摘要及文档入口。功能验证可能另需 Android 构建树、原厂样本、LVGL 或 QEMU；具体范围见各主题说明。离线验证不操作手机或物理块设备。

## 发布与许可

公开内容包括设备树文本、固定补丁、脚本、测试、文档及资源摘要。镜像、编译文件、原厂 blob、完整 OTA、私钥与原始设备日志不上传。同步流程见 [发布约定](docs/GITHUB-PUBLICATION.md)。

`SOURCE-MANIFEST.json` 记录公开文件摘要，`PRIVATE-ASSETS.json` 仅记录本地构建资源元数据。

TWRP、Team Win 与 AOSP 代码保留各自版权及许可；参见 [NOTICE](NOTICE) 与原文件声明。本仓库不以单一新许可覆盖全部上游代码。
