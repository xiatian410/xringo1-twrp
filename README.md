# Xiaomi 15S Pro Recovery

[![Source and patch integrity](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml/badge.svg)](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml)

基于 TWRP / YARP 的 **Xiaomi 15S Pro** Recovery 适配工程，设备代号 **`dijun`**，平台 **XRING O1**。

本仓库维护设备树、固定版本的平台补丁、构建工具和离线验证源码。目标是以同一 Recovery 镜像优先适配 **HyperOS 3 / 4**，并在兼容条件允许时覆盖已收录的 HyperOS 2 样本。

[当前状态](#当前状态) · [快速开始](#快速开始) · [构建](#构建) · [文档](#文档) · [贡献](#贡献)

## 当前状态

**项目仍在开发，尚未完成全部适配。** 六份固件 profile 已纳入统一候选，按组件身份选择模块与安全服务；这不代表各系统版本的全部功能已经验收。

| 项目 | 说明 |
| --- | --- |
| 设备 | Xiaomi 15S Pro（`dijun`） |
| 平台 | XRING O1（设备树目录：`O1_asic`） |
| 优先范围 | HyperOS 3 / 4；HyperOS 2 作为兼容扩展 |
| 镜像布局 | Recovery 不携带内核，沿用匹配系统的 boot / vendor_boot |
| 当前候选与 SHA-256 | [交付报告](simulation-report.md) |
| 未完成事项 | [工作队列](docs/WORK-QUEUE.md) |

版本范围见[兼容矩阵](compatibility-matrix.md)，页面入口与限制见[功能说明](FEATURE-USAGE.md)。CI 检查公开源码和补丁完整性；构建成功与离线验证通过不代替设备功能验收。

## 快速开始

安装 Git 和 Python 3，然后获取并检查公开源码：

```bash
git clone https://github.com/xiatian410/xringo1-twrp.git
cd xringo1-twrp
python3 scripts/check_public_tree.py
python3 scripts/check_documentation.py
```

这些检查不需要原厂固件。完整构建所需的专有资源、Android 源码和本地签名密钥需另行准备。

## 构建

先按[构建指南](docs/BUILDING.md)准备固定 revision 的 Android 源码、匹配资源和工作区目录，再执行：

```bash
bash scripts/compile_recovery.sh
```

脚本同步维护设备树，执行 `installclean`，然后以 `make -j$(nproc) recoveryimage` 构建。平台基线、补丁顺序和摘要由 [series.json](dtsrc/O1_asic_dual/patches/series.json) 固定。

镜像和编译产物仅保留在本地，本仓库不提供二进制下载。

## 目录结构

```text
.
├── .github/workflows/   # 源码与文档 CI
├── docs/               # 构建、固件、技术说明和工作队列
│   └── archive/        # 历史调查与阶段记录
├── dtsrc/O1_asic_dual/  # 维护设备树、profile 和固定补丁
├── manifests/          # Android 源码 revision 清单
├── scripts/            # 提取、构建、同步与核验工具
├── tests/              # 离线测试源码和合成夹具
└── tools/              # 诊断采集工具源码
```

## 文档

| 需要了解 | 文档 |
| --- | --- |
| 使用入口与已知限制 | [功能说明](FEATURE-USAGE.md) · [兼容矩阵](compatibility-matrix.md) |
| 构建与固件准备 | [构建指南](docs/BUILDING.md) · [固件来源与 ABI 比较](docs/FIRMWARE.md) |
| 当前交付与下一步 | [交付报告](simulation-report.md) · [工作队列](docs/WORK-QUEUE.md) |
| 功能实现与验证方法 | [技术文档索引](docs/README.md) |
| 目标、验收与维护流程 | [适配规范](ADAPTATION-GOALS.md) · [维护指南](MAINTENANCE.md) |

公开源码清单 [SOURCE-MANIFEST.json](SOURCE-MANIFEST.json) 记录文件摘要和权限；[PRIVATE-ASSETS.json](PRIVATE-ASSETS.json) 记录需自行准备的资源元数据；[验证摘要](docs/CURRENT-VALIDATION.json) 记录离线覆盖范围。

原厂 blob、完整 OTA、镜像、编译文件、私钥、原始设备日志和缓存不公开。技术文档中的 `logs/`、`imgs/`、`firmware/` 路径属于完整本地工作区，不是下载链接。部分验证依赖 Android 构建树、LVGL 或 QEMU，具体前提见对应主题文档。

## 贡献

请通过 [Issues](https://github.com/xiatian410/xringo1-twrp/issues) 提供固件版本、Recovery 候选及哈希、复现步骤、预期与实际结果，公开日志前移除个人信息和密钥。

提交与格式约定见[贡献指南](CONTRIBUTING.md)。维护者按[同步流程](MAINTENANCE.md#github-同步)发布每批源码与文档修改，历史实现通过 Git 追溯。当前代理维护仅进行离线操作，不连接手机或操作物理块设备。

## 致谢与许可

感谢 Team Win、[TWRP-Test/android_bootable_recovery](https://github.com/TWRP-Test/android_bootable_recovery) 和 AOSP。

各文件保留原版权及许可，详见 [NOTICE](NOTICE) 和文件声明。本仓库不以单一新许可覆盖全部上游代码。
