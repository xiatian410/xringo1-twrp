# Xiaomi 15S Pro · TWRP / YARP Recovery

[![Source integrity](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml/badge.svg)](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml)

面向 **Xiaomi 15S Pro（`dijun` / XRING O1）** 的设备树、平台补丁和离线验证工具。目标是以同一份 Recovery 镜像适配 **HyperOS 3 / 4**，在组件兼容时覆盖已收录的 HyperOS 2 样本。

> **适配进行中 · 仅发布源码。** 构建需要另行准备 Android 源码、原厂资源和本地密钥。CI 通过不代表设备功能或完整 OTA 安装已验收。

## 导航

| 用途 | 文档 |
| --- | --- |
| 使用与支持状态 | [功能说明](FEATURE-USAGE.md) · [兼容矩阵](compatibility-matrix.md) |
| 构建与固件来源 | [构建指南](BUILD-AND-TEST.md) · [固件映射](FIRMWARE-MAP.md) |
| 交付与待办 | [交付报告](simulation-report.md) · [工作队列](docs/WORK-QUEUE.md) |
| 实现与验证 | [技术文档](docs/README.md) |
| 需求与维护 | [适配目标](ADAPTATION-GOALS.md) · [维护指南](MAINTENANCE.md) |

## 适配状态

- **设备范围**：`dijun`，六份 HyperOS 2 / 3 / 4 固件档案。模块、安全服务和固件按精确 profile 选择；首尾样本不代表所有中间版本。
- **已维护**：OTG / UFS 识别、刷入目标选择、NV 普通界面限制、加载页名称、温度避让，以及部分文件系统、MTP 和 OTA 错误处理。
- **用户确认**：OS4 震动正常；backup-manifest 基线设置正常。
- **尚未完成**：OS4 自动触摸启动、完整 OTA / 快照生命周期、存储与安全服务集成；容量刷新页面停留问题仍待定位。

各项证据与限制见[兼容矩阵](compatibility-matrix.md)。候选镜像哈希统一维护在[交付报告](simulation-report.md)，不以历史测试数量计算完成度。

## 快速开始

### 获取与检查源码

公开源码检查仅需 Python 3，无需原厂固件：

```bash
git clone https://github.com/xiatian410/xringo1-twrp.git
cd xringo1-twrp
python3 scripts/check_public_tree.py
python3 scripts/check_documentation.py
```

### 构建 Recovery

按[构建指南](BUILD-AND-TEST.md)准备固定 revision 的 Android 源码、匹配资源与本地签名密钥，并核对脚本目录。在完整工作区执行：

```bash
bash scripts/compile_recovery.sh
```

脚本同步维护设备树，执行 `installclean`，再运行 `make -j$(nproc) recoveryimage`。产物仅保存在本地。

## 目录结构

```text
.
├── .github/workflows/   # 公开源码 CI
├── docs/               # 主题文档、工作队列与验证摘要
│   └── archive/        # 历史调查和阶段记录
├── dtsrc/O1_asic_dual/  # 维护设备树、profile 与固定补丁
├── manifests/          # Android 源码 revision 清单
├── scripts/            # 提取、同步、构建与核验工具
├── tests/              # 离线测试源码和合成夹具
└── tools/              # 诊断采集工具源码
```

上游：[TWRP-Test/android_bootable_recovery](https://github.com/TWRP-Test/android_bootable_recovery)。平台基线、补丁顺序与摘要见 [series.json](dtsrc/O1_asic_dual/patches/series.json)。

## 公开范围

仓库包含维护源码、配置、补丁、脚本、测试和文档。**镜像、编译文件、原厂 blob、完整 OTA、私钥、原始设备日志和本地缓存不上传。**

| 清单 | 内容 |
| --- | --- |
| [SOURCE-MANIFEST.json](SOURCE-MANIFEST.json) | 公开文件摘要与权限 |
| [PRIVATE-ASSETS.json](PRIVATE-ASSETS.json) | 未公开构建资源的大小、摘要与路径，不含资源本体或私钥 |
| [CURRENT-VALIDATION.json](docs/CURRENT-VALIDATION.json) | 验证结果摘要与范围 |

文档中的 `logs/`、`imgs/`、`firmware/` 路径指向本地证据，不是公开下载地址。部分验证依赖 Android 构建树、LVGL 或 QEMU；具体依赖见主题文档。离线工作不操作手机或物理块设备。

## 反馈与贡献

通过 [GitHub Issues](https://github.com/xiatian410/xringo1-twrp/issues) 提交固件版本、Recovery 候选、复现步骤及预期与实际结果。公开日志前移除个人信息和密钥。修改约定见[贡献指南](CONTRIBUTING.md)，每批维护通过[同步流程](MAINTENANCE.md#github-同步)更新 GitHub。

## 致谢与许可

感谢 TWRP、Team Win 与 AOSP 上游。各文件保留原版权和许可，参见 [NOTICE](NOTICE) 及文件声明；本仓库不以单一新许可覆盖全部上游代码。
