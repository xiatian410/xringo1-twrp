# Xiaomi 15S Pro Recovery

[![Source integrity](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml/badge.svg)](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml)

面向 **Xiaomi 15S Pro（dijun / XRING O1）** 的 TWRP / YARP 设备树、平台补丁与离线验证工具。

目标是以同一份 Recovery 镜像适配 **HyperOS 3 / 4**，并在兼容条件允许时覆盖已收录的 HyperOS 2 样本。不同固件使用独立 profile，分别维护内核模块、安全服务与固件资源。

> **项目仍在适配中。** 本仓库发布维护源码，不提供编译镜像。构建和 CI 通过不等于全部设备功能、解密或完整 OTA 安装通过验收。

## 导航

[项目状态](#项目状态) · [使用与构建](#使用与构建) · [仓库结构](#仓库结构) · [验证](#验证) · [参与维护](#参与维护) · [版权与许可](#版权与许可)

## 项目状态

| 项目 | 状态 |
| --- | --- |
| 固件档案 | OS2、OS3、OS4 各两份独立样本；不自动外推到中间版本 |
| 已维护修正 | UFS / OTG 识别、镜像刷入目标、NV 普通界面操作限制、加载页名称、温度避让摄像头及部分安装失败处理 |
| 用户确认 | OS4 震动正常；backup-manifest 基线设置正常 |
| 未完成 | 自动触摸启动、完整 OTA / 快照安装及部分存储与服务全流程 |
| 待定位 | 备份容量刷新后，现场页面未退出 |

- [兼容矩阵](compatibility-matrix.md)：各固件的支持范围。
- [交付与验证报告](simulation-report.md)：当前候选、证据与限制。
- [工作队列](docs/WORK-QUEUE.md)：当前优先事项。
- [适配目标](ADAPTATION-GOALS.md)：需求与验收边界。

## 使用与构建

功能入口和已知限制见 [功能说明](FEATURE-USAGE.md)；固件来源与 profile 对应关系见 [固件映射](FIRMWARE-MAP.md)。

公开 checkout 需要补齐固定版本的 Android 源码、匹配的原厂资源和本地签名密钥。先按 [构建指南](BUILD-AND-TEST.md) 准备完整工作区，再执行：

```bash
python3 scripts/sync_device_tree.py
bash scripts/compile_recovery.sh
```

构建脚本同步设备树，执行 `installclean`，然后运行 `make -j$(nproc) recoveryimage`。目录约定、依赖和产物路径以构建指南为准。

## 仓库结构

```text
.
├── dtsrc/O1_asic_dual/   # 设备树、固件 profile 与固定平台补丁
├── manifests/           # Android 源码 revision 清单
├── scripts/             # 资源提取、同步、构建与核验工具
├── tests/               # 离线测试源码与合成夹具
├── docs/                # 技术文档、工作队列与公开验证摘要
└── tools/               # 诊断采集工具源码
```

Recovery 上游为 [TWRP-Test/android_bootable_recovery](https://github.com/TWRP-Test/android_bootable_recovery)。本仓库维护设备树与可追溯补丁，不复制完整 Android 源码。平台基线、补丁顺序及摘要见 [series.json](dtsrc/O1_asic_dual/patches/series.json)。

实现细节按主题收录在 [技术文档索引](docs/README.md)。历史候选记录只代表当时输入，不作为当前功能承诺。

## 验证

在公开 checkout 中，无需原厂固件即可运行：

```bash
python3 scripts/check_public_tree.py
python3 scripts/check_documentation.py
```

GitHub Actions 检查公开文件清单、Python / JSON 语法、补丁摘要与文档入口。功能测试可能另需 Android 构建树、原厂样本、LVGL 或 QEMU，具体范围见对应主题文档。离线验证不操作手机或物理块设备。

## 参与维护

提交问题与修改前，请阅读 [贡献指南](CONTRIBUTING.md) 和 [维护指南](MAINTENANCE.md)。每批维护完成后通过审核导出流程同步 GitHub，规则见 [GitHub 同步](MAINTENANCE.md#github-同步)。

公开内容包括设备树文本、补丁、脚本、测试、文档与资源摘要；镜像、编译文件、原厂 blob、完整 OTA、私钥、原始设备日志和大型生成报告保留在本地。

`SOURCE-MANIFEST.json` 记录公开文件的摘要与权限；`PRIVATE-ASSETS.json` 只记录未公开构建资源的元数据。

## 版权与许可

TWRP、Team Win 与 AOSP 代码保留各自版权和许可。参见 [NOTICE](NOTICE) 与各文件声明；本仓库不以单一新许可覆盖全部上游代码。
