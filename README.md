# Xiaomi 15S Pro Recovery

[![Source integrity](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml/badge.svg)](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml)

面向 **Xiaomi 15S Pro（dijun / XRING O1）** 的 TWRP / YARP 设备树、平台补丁与离线验证工具。

项目以同一份 Recovery 镜像适配 **HyperOS 3 / 4** 为目标，并在兼容条件允许时覆盖已收录的 HyperOS 2 样本。内核模块、安全服务与固件资源按精确 profile 选择。

> **适配进行中，当前仓库仅发布源码。** 公开 checkout 不包含完整构建资源；构建或 CI 通过不代表全部设备功能与 OTA 安装已通过验收。

## 目录

- [项目状态](#项目状态)
- [快速开始](#快速开始)
- [文档](#文档)
- [源码布局](#源码布局)
- [验证与公开范围](#验证与公开范围)
- [参与贡献](#参与贡献)
- [版权与许可](#版权与许可)

## 项目状态

| 项目 | 说明 |
| --- | --- |
| 设备 | Xiaomi 15S Pro · `dijun` · XRING O1 |
| 固件范围 | HyperOS 2 / 3 / 4 各两份样本，具体版本见[兼容矩阵](compatibility-matrix.md) |
| 已维护修正 | UFS / OTG 识别、刷入目标选择、NV 普通界面操作限制、加载页名称、温度摄像头避让及部分操作失败处理 |
| 用户确认 | OS4 震动正常；backup-manifest 基线设置正常 |
| 主要剩余工作 | 自动触摸启动、OTA / 快照安装全流程、存储与安全服务集成 |
| 待定位故障 | 备份容量刷新完成后，现场页面仍未结束 |

[交付报告](simulation-report.md)记录当前候选及验证边界，[工作队列](docs/WORK-QUEUE.md)记录下一步。历史测试数量不作为当前完成度。

## 快速开始

### 获取源码

```bash
git clone https://github.com/xiatian410/xringo1-twrp.git
cd xringo1-twrp
```

### 检查公开文件

以下检查需要 Python 3，无需原厂固件：

```bash
python3 scripts/check_public_tree.py
python3 scripts/check_documentation.py
```

### 构建 Recovery

先按[构建指南](BUILD-AND-TEST.md)准备固定版本的 Android 源码、匹配原厂资源与本地签名密钥，并核对脚本使用的目录。在完整工作区执行：

```bash
python3 scripts/sync_device_tree.py
bash scripts/compile_recovery.sh
```

构建脚本同步维护设备树，执行 `installclean`，再运行 `make -j$(nproc) recoveryimage`。当前产物路径为 `/root/AAA/twrp/out/target/product/O1_asic/recovery.img`。

## 文档

| 入口 | 内容 |
| --- | --- |
| [功能说明](FEATURE-USAGE.md) | 功能入口、使用范围与已知限制 |
| [构建指南](BUILD-AND-TEST.md) | 依赖、资源准备、签名与构建步骤 |
| [兼容矩阵](compatibility-matrix.md) | 已收录固件与适配状态 |
| [固件映射](FIRMWARE-MAP.md) | OTA 来源及 profile 对应关系 |
| [技术文档](docs/README.md) | 按主题组织的实现与验证说明 |
| [适配目标](ADAPTATION-GOALS.md) | 完整需求与验收标准 |
| [工作队列](docs/WORK-QUEUE.md) | 当前优先级与未完成边界 |
| [维护指南](MAINTENANCE.md) | 固定补丁、交付与 GitHub 同步流程 |

## 源码布局

```text
.
├── .github/workflows/   # 公开源码 CI
├── docs/               # 技术说明、工作队列与验证摘要
├── dtsrc/O1_asic_dual/  # 维护设备树、固件 profile 与固定补丁
├── manifests/          # Android 源码 revision 清单
├── scripts/            # 提取、同步、构建与核验工具
├── tests/              # 离线测试源码与合成夹具
└── tools/              # 诊断采集工具源码
```

Recovery 上游为 [TWRP-Test/android_bootable_recovery](https://github.com/TWRP-Test/android_bootable_recovery)。本仓库维护设备树与可追溯补丁；平台基线、补丁顺序和摘要固定在 [series.json](dtsrc/O1_asic_dual/patches/series.json)。

## 验证与公开范围

GitHub Actions 检查公开文件清单、Python / JSON 语法、补丁摘要与文档入口。功能验证可能另需 Android 构建树、原厂样本、LVGL 或 QEMU，依赖及边界见各主题说明。离线验证不操作手机或物理块设备。

公开内容包括维护源码、配置、补丁、脚本、测试与文档。镜像、编译文件、原厂 blob、完整 OTA、私钥、原始设备日志及大型生成报告留在本地。

| 文件或路径 | 用途 |
| --- | --- |
| `SOURCE-MANIFEST.json` | 导出工具生成的公开文件摘要与权限 |
| `PRIVATE-ASSETS.json` | 未公开构建资源的元数据，不含资源本体或私钥 |
| `docs/CURRENT-VALIDATION.json` | 公开验证摘要 |
| 文档中的 `logs/`、`imgs/` 等路径 | 本地证据位置，不是公开下载入口 |

## 参与贡献

问题反馈和修改要求见[贡献指南](CONTRIBUTING.md)。请提供固件版本、Recovery 候选、复现步骤及预期与实际结果；日志摘录需去除个人信息和密钥。

维护者每批修改按[同步流程](MAINTENANCE.md#github-同步)审核导出并推送 GitHub，编译产物不随源码上传。

## 版权与许可

TWRP、Team Win 与 AOSP 代码保留各自版权和许可，参见 [NOTICE](NOTICE) 及各文件声明。本仓库不以单一新许可覆盖全部上游代码。
