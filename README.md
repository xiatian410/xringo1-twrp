# Xiaomi 15S Pro · XRING O1 Recovery

[![Source integrity](https://github.com/xiatian410/xringo1-twrp/actions/workflows/source-check.yml/badge.svg)](https://github.com/xiatian410/xringo1-twrp/actions)

面向 **Xiaomi 15S Pro（dijun / XRING O1）** 的 TWRP / YARP 设备树、平台补丁与离线验证工程。目标是使用同一份 Recovery 镜像优先适配 HyperOS 3、HyperOS 4，并在兼容条件允许时覆盖所列 HyperOS 2 样本。

> **适配仍在进行中。** 六份固件档案已纳入统一候选；这不代表所有版本、所有功能均已实机验证。本仓库仅发布源码，不提供编译镜像或二进制 Releases。

## 项目状态

| 项目 | 当前状态 |
| --- | --- |
| 固件范围 | OS2、OS3、OS4 各两份独立档案；中间版本不自动视为兼容 |
| 统一候选 | `recovery-dijun-unified-bounded-maintenance.img`，仅保存在维护者本地 |
| 最近修正 | 温度避让中央摄像头、ext 扩容尺寸边界、A/B 更新器同步拒绝收尾 |
| 分区界面 | 修正刷入目标缺失；限制普通 GUI 对 NV 维护分区的挂载、清除及工具操作 |
| USB OTG | 修正内置 UFS 分区被误列为大量 0 B 外部存储 |
| OS4 震动 | 用户已确认正常，已解决，不再例行检查 |
| OTA / A/B | 已修正部分命令、校验及失败收尾；完整 payload / 快照安装链仍未验收 |
| 备份容量刷新 | 日志显示操作已完成，现场画面未结束的原因尚未定位 |

候选 SHA-256：

```text
218c5edd28c4e458464fc035a73b68808b016598c51e50877b2c0a1b055da3c3
```

当前版本与离线验证摘要见 [验证报告](simulation-report.md)；后续优先级见 [工作队列](docs/WORK-QUEUE.md)。历史设备结果只适用于当时的版本和镜像，不转移为新候选的验收结论。

## 文档导航

- [适配目标与验收规范](ADAPTATION-GOALS.md)
- [版本与功能状态](compatibility-matrix.md)
- [功能入口与使用边界](FEATURE-USAGE.md)
- [构建指南](BUILD-AND-TEST.md)
- [维护与固件增补](MAINTENANCE.md)
- [技术文档索引](docs/README.md)
- [贡献指南](CONTRIBUTING.md)

## 源码结构

```text
.
├── dtsrc/O1_asic_dual/   # 维护设备树、六份 profile、平台补丁
├── manifests/           # Android 源码固定 revision
├── scripts/             # 提取、同步、构建与核验工具
├── tests/               # 离线检查源码与合成夹具
├── docs/                # 分主题设计、故障与验证说明
└── tools/               # 有界诊断采集工具
```

平台基线、补丁顺序和 SHA-256 固定在 [series.json](dtsrc/O1_asic_dual/patches/series.json)。Recovery 上游为 [TWRP-Test/android_bootable_recovery](https://github.com/TWRP-Test/android_bootable_recovery)；公开仓库提供可追溯的补丁，不复制整份 Android 源码树。

## 构建

公开 checkout 不能直接构建完整镜像：需先准备固定版本的 Android 源码、匹配的原厂资源及本地签名密钥，详见 [构建指南](BUILD-AND-TEST.md)。当前脚本采用以下工作区布局：

```text
/root/AAA/xringo1-twrp   # 本工程
/root/AAA/twrp          # Android 源码树
```

准备完成后：

```bash
python3 scripts/sync_device_tree.py
bash scripts/compile_recovery.sh
```

构建脚本同步设备树，执行 `installclean`，再使用 `make -j$(nproc) recoveryimage`。产物位于 Android 源码树的 `out/target/product/O1_asic/recovery.img`。

## 验证范围

公开 checkout 可执行不依赖固件的源码完整性检查：

```bash
python3 scripts/check_public_tree.py
python3 scripts/check_documentation.py
```

GitHub Actions 检查公开文件清单、Python / JSON 语法、补丁摘要和文档入口链接。功能检查还可能需要 Android 构建树、原厂样本、LVGL 或 QEMU；CI 通过不表示设备功能已验收。离线检查不操作手机或物理块设备。

## 发布范围与许可

- 公开：设备树文本、固定补丁、脚本、测试、文档及资源摘要。
- 不公开：编译镜像、可执行文件、原厂 blob、完整 OTA、私钥和原始设备日志。
- `SOURCE-MANIFEST.json` 记录公开文件摘要；`PRIVATE-ASSETS.json` 只记录本地构建资源元数据。

TWRP、Team Win 与 AOSP 代码保留各自版权及许可；参见 [NOTICE](NOTICE) 和原文件声明。本仓库不以单一新许可覆盖全部上游代码。
