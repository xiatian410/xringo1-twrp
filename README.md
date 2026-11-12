# Xiaomi 15S Pro Recovery

[![Source integrity](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml/badge.svg)](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml)

面向 **Xiaomi 15S Pro（`dijun` / XRING O1）** 的 TWRP / YARP 设备树、平台补丁与离线验证工具。

以同一份 Recovery 镜像适配 **HyperOS 3 / 4**，并在兼容条件允许时覆盖已收录的 HyperOS 2 样本。内核模块、安全服务及固件资源按精确 profile 选择。

> **适配进行中，仅发布源码。** 仓库不包含编译镜像、原厂固件或私钥。公开源码需补齐本地资源才能构建；CI 检查源码完整性，不代表设备功能或完整 OTA 安装已验收。

[功能说明](FEATURE-USAGE.md) · [构建指南](BUILD-AND-TEST.md) · [兼容矩阵](compatibility-matrix.md) · [工作队列](docs/WORK-QUEUE.md) · [技术文档](docs/README.md)

## 项目状态

| 项目 | 说明 |
| --- | --- |
| 设备 | Xiaomi 15S Pro · `dijun` · XRING O1 |
| 固件样本 | HyperOS 2 / 3 / 4 各两份；具体版本见[兼容矩阵](compatibility-matrix.md) |
| 已维护 | OTG / UFS 识别、刷入目标选择、NV 普通界面限制、加载页名称、温度避让，以及部分文件系统、MTP 和 OTA 错误处理 |
| 用户确认 | OS4 震动正常；backup-manifest 基线设置正常 |
| 未完成 | 自动触摸启动、完整 OTA / 快照安装、存储与安全服务集成 |
| 待定位 | 容量刷新后台结束后，现场页面仍停留在刷新状态 |

候选镜像标识、修正范围与验证限制统一记录在[交付报告](simulation-report.md)。下一步以[工作队列](docs/WORK-QUEUE.md)为准，历史测试数量不作为功能完成度。

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

### 构建镜像

先按[构建指南](BUILD-AND-TEST.md)准备固定 revision 的 Android 源码、匹配的原厂资源和本地签名密钥，并核对脚本使用的目录。在完整工作区执行：

```bash
bash scripts/compile_recovery.sh
```

脚本同步维护设备树，执行 `installclean`，再运行 `make -j$(nproc) recoveryimage`。依赖、目录约束和产物位置见构建指南。

## 文档导航

| 内容 | 入口 |
| --- | --- |
| 功能与使用限制 | [功能说明](FEATURE-USAGE.md) |
| 构建环境与资源准备 | [构建指南](BUILD-AND-TEST.md) |
| 固件版本与来源 | [兼容矩阵](compatibility-matrix.md) · [固件映射](FIRMWARE-MAP.md) |
| 当前交付与下一步 | [交付报告](simulation-report.md) · [工作队列](docs/WORK-QUEUE.md) |
| 各功能的实现与验证 | [技术文档索引](docs/README.md) |
| 目标、维护与贡献 | [适配目标](ADAPTATION-GOALS.md) · [维护指南](MAINTENANCE.md) · [贡献指南](CONTRIBUTING.md) |
| 历史调查 | [历史归档](docs/archive/README.md) |

## 仓库结构

```text
.
├── .github/workflows/   # 公开源码完整性检查
├── docs/               # 主题文档、工作队列及验证摘要
│   └── archive/        # 已解决问题与历史阶段记录
├── dtsrc/O1_asic_dual/  # 维护设备树、profile 及固定补丁
├── manifests/          # Android 源码 revision 清单
├── scripts/            # 提取、同步、构建及核验工具
├── tests/              # 离线测试源码与合成夹具
└── tools/              # 诊断采集工具源码
```

上游为 [TWRP-Test/android_bootable_recovery](https://github.com/TWRP-Test/android_bootable_recovery)。平台基线、补丁顺序和摘要固定在 [series.json](dtsrc/O1_asic_dual/patches/series.json) 中。

## 源码与资源范围

公开内容包括维护源码、配置、补丁、脚本、测试和文档。镜像、编译文件、原厂 blob、完整 OTA、私钥、原始设备日志及大型生成报告保留在本地。

- [SOURCE-MANIFEST.json](SOURCE-MANIFEST.json)：公开文件摘要与权限。
- [PRIVATE-ASSETS.json](PRIVATE-ASSETS.json)：未公开构建资源的元数据，不含资源本体或私钥。
- [CURRENT-VALIDATION.json](docs/CURRENT-VALIDATION.json)：公开验证摘要。

文档中的 `logs/`、`imgs/`、`firmware/` 路径指向本地证据，不是公开下载链接。部分验证需要 Android 构建树、LVGL 或 QEMU；依赖与模拟边界见对应主题文档。离线验证不操作手机或物理块设备。

## 贡献与许可

问题反馈与修改要求见[贡献指南](CONTRIBUTING.md)。请提供固件版本、Recovery 候选、复现步骤以及预期与实际结果；公开日志前请移除个人信息和密钥。每批维护修改按[同步流程](MAINTENANCE.md#github-同步)同步 GitHub，编译产物不上传。

TWRP、Team Win 与 AOSP 代码保留各自版权和许可，参见 [NOTICE](NOTICE) 及各文件声明。本仓库不以单一新许可覆盖全部上游代码。
