# 分区界面修正：镜像目标与 NV 操作

用户报告确认刷入页“目标分区点不动”，并发现高级清除仍有 NV。此次检查发现两个具体缺陷：原厂文件系统 fstab 不含 raw 镜像目标，候选镜像也未带 `twrp.flags`，因而没有 Boot 等可选项；先前 0054 只限制普通挂载，没有覆盖清除与分区工具。此前检查范围不足。

维护的 `profiles/common/root/system/etc/twrp.flags` 现补入 Boot、Init Boot、Vendor Boot、Recovery、DTBO，交由核心检查分区是否存在及选择当前槽位。六份 OTA 的分区清单均含这五项；不写死 `_a`/`_b`。选择目标、滑动确认、真正写入仍是不同步骤。普通 `.img` 的目标选择应由这五种已存在分区提供，标题本身不承担选择功能。

补丁 0060 与配置共同覆盖以下普通 GUI 入口：

| 入口 | NV 行为 | 正常目标 |
|---|---|---|
| 挂载/卸载 | 沿用 0054：隐藏并拒绝直接或解析别名请求 | 保留 |
| 高级清除 | 隐藏；提交和执行前检查全部列表，含 NV 则在第一次清除前拒绝 | 保留 Data/Cache 等 |
| 修复/调整大小/更改文件系统 | 不提供详情；启动和执行前拒绝 | 保留 |
| 镜像刷入 | 不列出；启动和执行前拒绝，空目标/分号多目标亦拒绝 | 补齐五个 raw 目标 |

NV 集合为 nvram、proinfo、nvdata、nvcfg、protect_f、protect_s，含 `/mnt/vendor/` 对应路径、规范化路径、子路径和解析到 NV 的别名。前缀相似的普通路径不误拦截。原厂 fstab 不删除，内部服务仍可访问；备份/恢复和特权终端不受此普通 GUI 策略限制。persist、metadata 不按 NV 集合隐藏。FactoryReset 仍按核心 `wipe_during_factory_reset_` 标记选择目标，未给 NV 新增该标记。

离线检查执行生产方法：26 个路径/批次场景覆盖列表、提交、执行、别名、混合清除预检和分号注入；旧实现同组 19 个失败，修正后通过。真实 LVGL 确认页与原回调覆盖五目标各 label/detail/arrow/blank/drag-out，共 25 场景；导航目的地记录，不执行完整 Android 页面切换。原镜像写入链 40 场景核对私有文件内容与双槽顺序；原修复链 7 场景调用镜像 ARM64 e2fsck；挂载策略 26 场景回归通过。设备发现、实际挂载/容量及破坏性操作在策略测试中为明确替身，不能据此声称实机或完整 12 组功能已验收。

最终候选：`recovery-dijun-unified-partition-actions.img`，SHA256 `f9a11c04da1669ef601ca52ee6c38a99f32011aedcab06a5005af4f74f386db6`。最终 `installclean` 后 `make -j$(nproc)` 以 30 并发构建；769 来源绑定、六 profile 封装和实际镜像 flags 字节核对。初次编译发现新增自由函数访问私有字段，已改用公开 `GetMountPoint()`，修正后重新清理构建。未操作手机或物理块设备。

本地证据：`logs/partition-actions-delivery.json`、`nv-partition-actions.json`、`install-target-interaction.json`、`partition-actions-image-chain.json`、`partition-actions-repair-chain.json`、`partition-actions-mount.json`。公开仓库仅发布源码、配置、补丁、测试及摘要，不上传镜像、编译产物或原始日志。
