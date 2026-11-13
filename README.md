# Xiaomi 15S Pro Recovery

[![Source and patch integrity](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml/badge.svg)](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml)

基于 **TWRP / YARP** 的 Xiaomi 15S Pro（`dijun` / **XRING O1**）Recovery 适配工程，公开维护设备树、固定平台补丁、构建脚本和离线验证源码。

目标是使用同一镜像优先覆盖 **HyperOS 3 / 4**，在兼容条件允许时扩展到已收录的 HyperOS 2 样本。六份固件 profile 按组件身份选择模块和安全服务；收录样本不代表该版本全部功能已经验收。

[项目状态](#项目状态) · [快速开始](#快速开始) · [目录结构](#目录结构) · [文档](#文档) · [参与贡献](#参与贡献)

## 项目状态

**开发中，完整适配尚未完成。** 当前候选、SHA-256 和验证范围见[交付报告](simulation-report.md)，版本范围见[兼容矩阵](compatibility-matrix.md)，未解决问题统一维护在[工作队列](docs/WORK-QUEUE.md)。

已维护 OTG / UFS 识别、刷入目标选择、NV 界面限制、加载页名称、温度避让及部分文件系统、MTP、OTA 错误处理。用户已确认 OS4 震动正常、backup-manifest 基线设置正常；自动触摸启动、容量刷新页面停留及完整 OTA / 快照生命周期等仍有未完成边界。

CI 检查公开源码、补丁和文档完整性。构建成功与离线测试通过均不代替设备功能验收。

## 快速开始

### 获取源码

需要 Git 和 Python 3；以下检查不需要原厂固件：

```bash
git clone https://github.com/xiatian410/xringo1-twrp.git
cd xringo1-twrp
python3 scripts/check_public_tree.py
python3 scripts/check_documentation.py
```

### 构建镜像

本仓库是适配工程，完整构建还需要固定 revision 的 Android 源码、匹配原厂资源、本地签名密钥和规定的工作区目录。先完成[构建指南](BUILD-AND-TEST.md)中的准备步骤，再在完整工作区执行：

```bash
bash scripts/compile_recovery.sh
```

脚本同步维护设备树，执行 `installclean`，然后使用 `make -j$(nproc) recoveryimage` 构建。镜像与编译文件仅保留在本地，不随源码上传。

## 目录结构

```text
.
├── .github/workflows/   # 公开源码 CI
├── docs/               # 技术主题、验证摘要和工作队列
│   └── archive/        # 历史调查与阶段记录
├── dtsrc/O1_asic_dual/  # 维护设备树、固件 profile 和固定补丁
├── manifests/          # Android 源码 revision 清单
├── scripts/            # 资源提取、构建、同步与核验
├── tests/              # 离线测试源码和合成夹具
└── tools/              # 诊断采集工具源码
```

平台基线、补丁顺序及摘要见 [series.json](dtsrc/O1_asic_dual/patches/series.json)。

## 文档

| 主题 | 入口 |
| --- | --- |
| 使用与兼容性 | [功能说明](FEATURE-USAGE.md) · [兼容矩阵](compatibility-matrix.md) |
| 构建与固件 | [构建指南](BUILD-AND-TEST.md) · [固件映射](FIRMWARE-MAP.md) |
| 交付与待办 | [交付报告](simulation-report.md) · [工作队列](docs/WORK-QUEUE.md) |
| 技术实现与历史记录 | [技术文档索引](docs/README.md) |
| 目标与维护 | [适配规范](ADAPTATION-GOALS.md) · [维护指南](MAINTENANCE.md) |

公开清单 [SOURCE-MANIFEST.json](SOURCE-MANIFEST.json) 记录文件摘要和权限；[PRIVATE-ASSETS.json](PRIVATE-ASSETS.json) 只记录需自行准备的资源元数据；[CURRENT-VALIDATION.json](docs/CURRENT-VALIDATION.json) 汇总验证范围。

原厂 blob、完整 OTA、镜像、编译文件、私钥、原始设备日志和缓存不公开。技术文档中的 `logs/`、`imgs/`、`firmware/` 是完整工作区的本地路径，不是下载链接。部分验证还依赖 Android 构建树、LVGL 或 QEMU；本工程的离线维护不操作手机或物理块设备。

## 参与贡献

通过 [GitHub Issues](https://github.com/xiatian410/xringo1-twrp/issues) 反馈固件版本、Recovery 候选、复现步骤以及预期和实际结果，公开日志前移除个人信息与密钥。

提交与文本格式遵循[贡献指南](CONTRIBUTING.md)。维护者每批修改按[同步流程](MAINTENANCE.md#github-同步)更新仓库，历史版本通过 Git 追溯。

## 致谢与许可

感谢 Team Win、[TWRP-Test/android_bootable_recovery](https://github.com/TWRP-Test/android_bootable_recovery) 和 AOSP。各文件保留原版权及许可，参见 [NOTICE](NOTICE) 与文件声明；本仓库不以单一新许可覆盖全部上游代码。
