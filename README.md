# Xiaomi 15S Pro Recovery

[![Source and patch integrity](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml/badge.svg)](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml)

基于 **TWRP / YARP** 的 Xiaomi 15S Pro Recovery 适配工程，提供设备树、固定平台补丁、构建脚本和离线验证源码。

| 项目 | 说明 |
| --- | --- |
| 设备 | Xiaomi 15S Pro · `dijun` · **XRING O1** |
| 适配目标 | 同一镜像优先覆盖 HyperOS 3 / 4，兼容时扩展到已收录的 HyperOS 2 样本 |
| 固件选择 | 六份独立 profile，按组件身份选择模块和安全服务 |
| 发布形式 | 公开源码；镜像及原厂资源自行准备 |

> **项目仍在开发中。** 纳入 profile 不代表完整功能已经验收。自动触摸启动、容量刷新页面停留、完整 OTA / 快照生命周期等仍有未完成项，详见[兼容矩阵](compatibility-matrix.md)和[工作队列](docs/WORK-QUEUE.md)。

[构建指南](BUILD-AND-TEST.md) · [功能说明](FEATURE-USAGE.md) · [技术文档](docs/README.md) · [问题反馈](https://github.com/xiatian410/xringo1-twrp/issues)

## 项目状态

- **已维护：** OTG / UFS 识别、刷入目标选择、NV 界面限制、加载页名称、温度避让及部分文件系统、MTP、OTA 错误处理。
- **用户确认：** OS4 震动正常；backup-manifest 基线设置正常。
- **待完成：** 以[工作队列](docs/WORK-QUEUE.md)为准，不据离线检查数量推算功能通过率。

候选镜像、SHA-256 与验证范围统一记录在[交付报告](simulation-report.md)。CI 只检查公开源码、补丁和文档完整性，不代替设备功能验收。

## 快速开始

### 获取并检查源码

仅需 Git 和 Python 3，无需原厂固件：

```bash
git clone https://github.com/xiatian410/xringo1-twrp.git
cd xringo1-twrp
python3 scripts/check_public_tree.py
python3 scripts/check_documentation.py
```

### 构建 Recovery

先按[构建指南](BUILD-AND-TEST.md)准备固定 revision 的 Android 源码、匹配原厂资源、本地签名密钥和工作区目录，再运行：

```bash
bash scripts/compile_recovery.sh
```

脚本同步维护设备树，先执行 `installclean`，再使用 `make -j$(nproc) recoveryimage` 构建。仅克隆本仓库无法直接生成完整镜像；产物保留在本地。

## 文档导航

| 内容 | 入口 |
| --- | --- |
| 功能使用与兼容范围 | [功能说明](FEATURE-USAGE.md) · [兼容矩阵](compatibility-matrix.md) |
| 构建与原厂资源 | [构建指南](BUILD-AND-TEST.md) · [固件映射](FIRMWARE-MAP.md) |
| 当前交付与下一步 | [交付报告](simulation-report.md) · [工作队列](docs/WORK-QUEUE.md) |
| 实现、验证与历史记录 | [技术文档索引](docs/README.md) |
| 需求与维护规则 | [适配目标](ADAPTATION-GOALS.md) · [维护指南](MAINTENANCE.md) · [贡献指南](CONTRIBUTING.md) |

## 目录结构

```text
.
├── .github/workflows/   # 公开源码 CI
├── docs/               # 技术主题、验证摘要和工作队列
│   └── archive/        # 历史调查与阶段记录
├── dtsrc/O1_asic_dual/  # 维护设备树、profile 和固定补丁
├── manifests/          # Android 源码 revision 清单
├── scripts/            # 资源提取、构建、同步与核验
├── tests/              # 离线测试源码和合成夹具
└── tools/              # 诊断采集工具源码
```

平台基线、补丁顺序及摘要见 [series.json](dtsrc/O1_asic_dual/patches/series.json)。

## 公开范围与验证限制

仓库包含维护源码、配置、补丁、脚本、测试和文档。镜像、编译文件、原厂 blob、完整 OTA、私钥、原始设备日志及缓存不上传。

| 清单 | 用途 |
| --- | --- |
| [SOURCE-MANIFEST.json](SOURCE-MANIFEST.json) | 公开文件摘要与权限 |
| [PRIVATE-ASSETS.json](PRIVATE-ASSETS.json) | 需自行准备的资源元数据，不含资源本体或私钥 |
| [CURRENT-VALIDATION.json](docs/CURRENT-VALIDATION.json) | 已记录验证的输入、结果与适用范围 |

文档中的 `logs/`、`imgs/`、`firmware/` 是完整工作区的本地证据路径，不是下载链接。部分验证依赖 Android 构建树、LVGL 或 QEMU。离线检查不操作手机或物理块设备，测试替身和构建成功不能证明硬件功能正常。

## 反馈与贡献

通过 [GitHub Issues](https://github.com/xiatian410/xringo1-twrp/issues) 提供固件版本、Recovery 候选、复现步骤及预期和实际结果，公开日志前移除个人信息和密钥。

提交规则与文本格式见[贡献指南](CONTRIBUTING.md)。维护者每批修改按[同步流程](MAINTENANCE.md#github-同步)更新仓库，历史版本通过 Git 追溯。

## 致谢与许可

感谢 Team Win、[TWRP-Test/android_bootable_recovery](https://github.com/TWRP-Test/android_bootable_recovery) 和 AOSP。各文件保留原版权及许可，参见 [NOTICE](NOTICE) 与文件声明；本仓库不以单一新许可覆盖全部上游代码。
