# Xiaomi 15S Pro Recovery

[![Source and patch integrity](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml/badge.svg)](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml)

基于 **TWRP / YARP** 的 Xiaomi 15S Pro（`dijun`，**XRING O1**）Recovery 适配工程，包含设备树、固定平台补丁、构建脚本和离线验证源码。

目标是使用同一份镜像覆盖 **HyperOS 3 / 4**，并在组件兼容时支持已收录的 HyperOS 2 样本。各固件采用精确 profile 选择模块与安全组件，不按系统大版本混装。

> **开发中，仅发布源码。** 六份固件 profile 已纳入维护，但不代表所有版本、功能或完整 OTA 安装已通过设备验收。构建需自行准备 Android 源码、原厂资源和本地签名密钥。

## 项目状态

| 类别 | 状态 |
| --- | --- |
| 固件范围 | HyperOS 2 / 3 / 4 共六份样本；不据首尾样本推断所有中间版本 |
| 已维护 | OTG / UFS 识别、刷入目标选择、NV 界面限制、加载页名称、温度避让及部分文件系统、MTP、OTA 错误处理 |
| 用户确认 | OS4 震动正常；backup-manifest 基线设置正常 |
| 未完成 | 自动触摸启动、容量刷新页面停留定位、完整 OTA / 快照生命周期，以及存储和安全服务集成 |

详细支持范围见[兼容矩阵](compatibility-matrix.md)，当前优先级见[工作队列](docs/WORK-QUEUE.md)。候选镜像及 SHA-256 统一记录在[交付报告](simulation-report.md)。CI 检查源码完整性与文档，不代替功能验收。

## 快速开始

### 获取源码

```bash
git clone https://github.com/xiatian410/xringo1-twrp.git
cd xringo1-twrp
```

### 检查公开源码

只需 Python 3，无需原厂固件：

```bash
python3 scripts/check_public_tree.py
python3 scripts/check_documentation.py
```

### 构建镜像

按[构建指南](BUILD-AND-TEST.md)准备固定 revision 的 Android 源码、匹配资源与签名密钥，并确认工作区目录。然后在完整工作区执行：

```bash
bash scripts/compile_recovery.sh
```

脚本同步维护设备树，先运行 `installclean`，再使用 `make -j$(nproc) recoveryimage` 构建。产物仅保存在本地，仓库不提供编译镜像下载。

## 文档

| 需求 | 入口 |
| --- | --- |
| 功能使用与兼容范围 | [功能说明](FEATURE-USAGE.md) · [兼容矩阵](compatibility-matrix.md) |
| 构建与原厂资源 | [构建指南](BUILD-AND-TEST.md) · [固件映射](FIRMWARE-MAP.md) |
| 当前交付与后续任务 | [交付报告](simulation-report.md) · [工作队列](docs/WORK-QUEUE.md) |
| 实现、测试与历史记录 | [技术文档索引](docs/README.md) |
| 适配要求与维护流程 | [目标规范](ADAPTATION-GOALS.md) · [维护指南](MAINTENANCE.md) |

## 目录结构

```text
.
├── .github/workflows/   # 公开源码 CI
├── docs/               # 主题说明、验证摘要和工作队列
│   └── archive/        # 历史调查与阶段记录
├── dtsrc/O1_asic_dual/  # 唯一维护设备树、profile 和固定补丁
├── manifests/          # Android 源码 revision 清单
├── scripts/            # 资源提取、构建、同步与核验
├── tests/              # 离线测试源码和合成夹具
└── tools/              # 诊断采集工具源码
```

平台基线、补丁顺序及摘要见 [series.json](dtsrc/O1_asic_dual/patches/series.json)。

## 公开范围与验证限制

仓库公开源码、配置、补丁、脚本、测试和文档。**不上传镜像、编译文件、原厂 blob、完整 OTA、私钥、原始设备日志或本地缓存。**

- [SOURCE-MANIFEST.json](SOURCE-MANIFEST.json)：公开文件的摘要与权限。
- [PRIVATE-ASSETS.json](PRIVATE-ASSETS.json)：需自行准备的构建资源路径、大小与摘要，不含资源本体或私钥。
- [CURRENT-VALIDATION.json](docs/CURRENT-VALIDATION.json)：已记录验证的结果、输入和适用范围。

文档中的 `logs/`、`imgs/`、`firmware/` 为完整工作区的本地证据路径，不是下载链接。部分测试依赖 Android 构建树、LVGL 或 QEMU，具体见主题说明。离线验证不操作手机或物理块设备；测试替身、编译成功和 CI 通过均不等同于实机功能正常。

## 反馈与贡献

请通过 [GitHub Issues](https://github.com/xiatian410/xringo1-twrp/issues) 提供固件版本、Recovery 候选、复现步骤，以及预期和实际结果。公开日志前移除个人信息和密钥。

修改约定见[贡献指南](CONTRIBUTING.md)。维护者每批修改按[同步流程](MAINTENANCE.md#github-同步)更新仓库。

## 致谢与许可

感谢 Team Win、[TWRP-Test/android_bootable_recovery](https://github.com/TWRP-Test/android_bootable_recovery) 与 AOSP。各文件保留原版权和许可，参见 [NOTICE](NOTICE) 及文件声明；本仓库不以单一新许可覆盖全部上游代码。
