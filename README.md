# Xiaomi 15S Pro · XRING O1 Recovery

[![Source integrity](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml/badge.svg)](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml)

面向 **Xiaomi 15S Pro（dijun / XRING O1）** 的 TWRP / YARP 设备树、固定平台补丁与离线验证工具。

以同一份 Recovery 镜像适配 **HyperOS 3 / 4** 为主要目标，并在兼容条件允许时覆盖已收录的 HyperOS 2 样本。各固件使用独立 profile 管理内核模块、安全服务和固件资源。

> **适配进行中，仅发布源码。** 本仓库不提供编译镜像。构建与 CI 通过不代表全部设备功能、解密或完整 OTA 安装已通过验收。

## 项目状态

| 项目 | 当前范围 |
| --- | --- |
| 设备 | Xiaomi 15S Pro · `dijun` · XRING O1 |
| 固件样本 | HyperOS 2 / 3 / 4 各两份；不自动外推到未收录版本 |
| 已维护修正 | UFS / OTG 识别、镜像目标选择、NV 普通界面操作限制、加载页名称、温度避让摄像头及部分操作失败处理 |
| 用户确认 | OS4 震动正常；backup-manifest 基线设置正常 |
| 主要未完成项 | 自动触摸启动、完整 OTA / 快照安装、部分存储与安全服务全流程 |
| 待定位故障 | 备份容量刷新完成后，现场页面未退出 |

当前候选与验证边界见 [交付报告](simulation-report.md)，具体固件范围见 [兼容矩阵](compatibility-matrix.md)。下一步维护以 [工作队列](docs/WORK-QUEUE.md) 为准。

## 快速开始

```bash
git clone https://github.com/xiatian410/xringo1-twrp.git
cd xringo1-twrp
```

仅检查公开源码，无需原厂固件：

```bash
python3 scripts/check_public_tree.py
python3 scripts/check_documentation.py
```

构建前需按 [构建指南](BUILD-AND-TEST.md) 准备固定版本的 Android 源码、匹配的原厂资源和本地签名密钥。**公开 checkout 本身不包含完整构建资源。** 准备好完整工作区后执行：

```bash
python3 scripts/sync_device_tree.py
bash scripts/compile_recovery.sh
```

构建脚本同步设备树，执行 `installclean`，再运行 `make -j$(nproc) recoveryimage`。当前脚本的固定目录、依赖及产物路径见构建指南。

## 文档导航

| 文档 | 用途 |
| --- | --- |
| [功能说明](FEATURE-USAGE.md) | 功能入口、使用范围和已知限制 |
| [构建指南](BUILD-AND-TEST.md) | 源码、私有资源、签名与构建步骤 |
| [固件映射](FIRMWARE-MAP.md) | OTA 来源与 profile 对应关系 |
| [技术文档](docs/README.md) | 按主题查阅实现、验证方法与历史证据 |
| [适配目标](ADAPTATION-GOALS.md) | 完整需求与验收标准 |
| [维护指南](MAINTENANCE.md) | 补丁、资源、交付及 GitHub 同步规范 |
| [贡献指南](CONTRIBUTING.md) | 问题反馈和修改要求 |

## 仓库结构

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

Recovery 上游为 [TWRP-Test/android_bootable_recovery](https://github.com/TWRP-Test/android_bootable_recovery)。本仓库维护设备树与可追溯补丁，不复制完整 Android 源码。平台基线、补丁顺序和摘要由 [series.json](dtsrc/O1_asic_dual/patches/series.json) 固定。

## 验证与公开范围

GitHub Actions 检查文件清单、Python / JSON 语法、补丁摘要和文档入口。功能测试可能另需 Android 构建树、原厂样本、LVGL 或 QEMU，范围见各主题说明。离线验证不操作手机或物理块设备；历史结果只代表当时的输入。

公开内容包括维护源码、配置、补丁、脚本、测试和文档。镜像、编译文件、原厂 blob、完整 OTA、私钥、原始设备日志和大型生成报告留在本地。

- `SOURCE-MANIFEST.json`：公开文件的摘要与权限，由导出工具生成。
- `PRIVATE-ASSETS.json`：未公开构建资源的元数据，不包含资源本体或私钥。
- 文档中的 `logs/`、`imgs/` 等路径：本地证据位置，不是公开下载入口。

每批修改通过 [维护流程](MAINTENANCE.md#github-同步) 导出并同步 GitHub。

## 版权与许可

TWRP、Team Win 与 AOSP 代码保留各自版权和许可，参见 [NOTICE](NOTICE) 及各文件声明。本仓库不以单一新许可覆盖全部上游代码。
