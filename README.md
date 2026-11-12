# Xiaomi 15S Pro Recovery

[![Source integrity](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml/badge.svg)](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml)

面向 **Xiaomi 15S Pro（`dijun` / XRING O1）** 的 TWRP / YARP 设备树、固定平台补丁与离线验证工具。

目标是以同一份 Recovery 镜像适配 **HyperOS 3 / 4**，并在兼容条件允许时覆盖已收录的 HyperOS 2 样本。内核模块、安全服务和固件资源按精确 profile 选择。

> **适配进行中 · 仅发布源码。** 本仓库不提供编译镜像或专有固件。公开 checkout 需要补齐本地资源才能构建；CI 通过不表示全部设备功能或 OTA 安装已经验收。

## 导航

[项目状态](#项目状态) · [快速开始](#快速开始) · [文档](#文档) · [目录结构](#目录结构) · [公开范围](#公开范围) · [贡献与许可](#贡献与许可)

## 项目状态

| 项目 | 状态 |
| --- | --- |
| 设备 | Xiaomi 15S Pro · `dijun` · XRING O1 |
| 样本 | HyperOS 2 / 3 / 4 各两份，版本与边界见[兼容矩阵](compatibility-matrix.md) |
| 已维护 | UFS / OTG 识别、刷入目标选择、NV 普通界面操作限制、XRING O1 加载页、温度摄像头避让，以及部分安装 / MTP / 操作收尾修正 |
| 用户确认 | OS4 震动正常；backup-manifest 基线设置正常 |
| 仍待完成 | 自动触摸启动、完整 OTA / 快照安装、存储与安全服务集成 |
| 待定位 | 备份容量刷新日志结束后，现场页面仍未结束 |

当前候选与验证边界统一见[交付报告](simulation-report.md)，下一步见[工作队列](docs/WORK-QUEUE.md)。历史测试数量不作为功能完成度。

## 快速开始

### 获取源码

```bash
git clone https://github.com/xiatian410/xringo1-twrp.git
cd xringo1-twrp
```

### 检查公开源码

仅需 Python 3，无需原厂固件：

```bash
python3 scripts/check_public_tree.py
python3 scripts/check_documentation.py
```

### 构建 Recovery

按[构建指南](BUILD-AND-TEST.md)准备固定 revision 的 Android 源码、匹配的原厂资源和本地签名密钥，核对脚本目录后，在完整工作区执行：

```bash
python3 scripts/sync_device_tree.py
bash scripts/compile_recovery.sh
```

构建脚本同步维护设备树，执行 `installclean`，然后运行 `make -j$(nproc) recoveryimage`。资源准备、固定目录和产物位置均在构建指南中说明。

## 文档

| 阅读目的 | 入口 |
| --- | --- |
| 使用功能、了解限制 | [功能说明](FEATURE-USAGE.md) |
| 准备依赖与构建 | [构建指南](BUILD-AND-TEST.md) |
| 核对固件版本与来源 | [兼容矩阵](compatibility-matrix.md) · [固件映射](FIRMWARE-MAP.md) |
| 查看当前候选与未完成项 | [交付报告](simulation-report.md) · [工作队列](docs/WORK-QUEUE.md) |
| 阅读技术实现 | [技术文档索引](docs/README.md) |
| 维护设备树与发布源码 | [适配目标](ADAPTATION-GOALS.md) · [维护指南](MAINTENANCE.md) |
| 追溯已解决问题和旧候选 | [历史归档](docs/archive/README.md) |

## 目录结构

```text
.
├── .github/workflows/   # 公开源码完整性检查
├── docs/               # 当前技术说明、工作队列与验证摘要
│   └── archive/        # 已解决问题与历史阶段记录
├── dtsrc/O1_asic_dual/  # 维护设备树、profile 与固定补丁
├── manifests/          # Android 源码 revision 清单
├── scripts/            # 提取、同步、构建和核验工具
├── tests/              # 离线测试源码与合成夹具
└── tools/              # 诊断采集工具源码
```

上游为 [TWRP-Test/android_bootable_recovery](https://github.com/TWRP-Test/android_bootable_recovery)。平台基线、补丁顺序和摘要固定在 [series.json](dtsrc/O1_asic_dual/patches/series.json) 中。

## 公开范围

公开内容包括维护源码、配置、补丁、脚本、测试和文档。镜像、编译文件、原厂 blob、完整 OTA、私钥、原始设备日志及大型生成报告保留在本地。离线验证不操作手机或物理块设备。

| 文件 | 用途 |
| --- | --- |
| [SOURCE-MANIFEST.json](SOURCE-MANIFEST.json) | 导出工具生成的公开文件摘要与权限 |
| [PRIVATE-ASSETS.json](PRIVATE-ASSETS.json) | 未公开构建资源的元数据，不包含资源本体或私钥 |
| [CURRENT-VALIDATION.json](docs/CURRENT-VALIDATION.json) | 公开验证摘要 |

技术记录中的 `logs/`、`imgs/`、`firmware/` 等路径指向本地证据，不是公开下载链接。部分验证还需 Android 构建树、LVGL 或 QEMU，具体依赖和替身边界见对应主题文档。

## 贡献与许可

问题反馈与修改要求见[贡献指南](CONTRIBUTING.md)。请提供固件版本、Recovery 候选、复现步骤及预期与实际结果；公开日志摘录需去除个人信息和密钥。每批维护修改按[同步流程](MAINTENANCE.md#github-同步)审核导出并同步 GitHub，编译产物不上传。

TWRP、Team Win 与 AOSP 代码保留各自版权和许可，参见 [NOTICE](NOTICE) 和各文件声明。本仓库不以单一新许可覆盖全部上游代码。
