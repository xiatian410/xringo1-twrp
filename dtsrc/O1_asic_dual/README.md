# dijun 维护设备树

设备：**Xiaomi 15S Pro（dijun / XRING O1）**。本目录为配置、profile 和平台补丁的唯一维护入口，生成目录为 Android 源码树中的 `device/xiaomi/O1_asic`。

## 范围

六份 OS2 / OS3 / OS4 档案已纳入统一候选，优先 OS3 / OS4；完整功能仍在适配。其他机型的遗留资源不属于本工程的支持承诺。

- [目标与验收规范](../../ADAPTATION-GOALS.md)
- [版本与功能状态](../../compatibility-matrix.md)
- [当前交付](../../simulation-report.md)
- [固件档案](../../FIRMWARE-MAP.md)

OS4 震动用户已确认正常，不再例行调查。历史模拟不代替新候选的设备验收。

## 配置与来源

`profiles/` 保留固件身份、组件和激活规则；不能跨 ABI 混用原厂模块、安全服务或 TA。公共组件仅在有哈希 / 兼容性证据时共享。

[patches/series.json](patches/series.json) 固定 Recovery、SELinux、tinyxml2、vold 和 update_engine 的仓库基线、补丁顺序及摘要。平台源码以维护补丁重建，脚本拒绝覆盖未知修改。

Recovery 不携带 kernel，沿用对应系统的 boot / vendor_boot。不得新增自定义 `modules.load` / `modules.load.recovery` 覆盖原厂首阶段加载。旧内核与机型目录是来源资料，不代表统一 ABI 支持。

## 构建

从工程根目录执行：

```bash
python3 scripts/sync_device_tree.py
bash scripts/compile_recovery.sh
```

需先准备完整 Android 源码、私有资源及本地构建密钥。构建脚本同步设备树，执行 `installclean`，再使用 `make -j$(nproc) recoveryimage`。

完整前提见 [构建指南](../../BUILD-AND-TEST.md)，新增固件和补丁流程见 [维护指南](../../MAINTENANCE.md)。编译镜像、原厂 blob、私钥和原始设备日志不上传公开仓库。
