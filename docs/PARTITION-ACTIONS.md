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

## 嵌套分区操作路径

以下保留 0029 的核心路径修正记录。它与后续 GUI 的 NV 操作限制分属不同层次，不能据核心能够查找分区推断普通界面允许清除 NV。

2026-11-12。设置保存的0028修正使`/mnt/vendor/persist/TWRP`能找到persist，但清除、转换文件系统、修复、调整大小四个入口仍使用GetRootPath。dijun fstab登记`/mnt/vendor/protect_f`、protect_s、nvdata、nvcfg、persist，旧入口却只查`/mnt`，因此无法选择这些真实挂载点。转换/修复/调整大小还缺少`/system`→`/system_root`映射。

维护补丁[0029-nested-partition-operations.patch](../dtsrc/O1_asic_dual/patches/0029-nested-partition-operations.patch)复用真实FindPartitionByPath选出的owner，按owner挂载点执行，并在操作全程持有现有递归操作锁。保留原始Wipe/Repair/Resize能力检查和确认入口；没有添加分区、改变可清除权限、改写fstab或绕过解密失败保护。路径包含普通子目录时仍归属其分区，不能将WipeByPath当成文件删除接口。

同时修正两个错误返回：子分区失败不再被忽略；不存在独立cache时，`/data/cache`清理返回值不再被丢弃。后者只传播WipeDataCache的现有结果；该底层函数未完整检查目录删除错误，本轮不能据此承诺所有删除故障均能传播。多分区操作不具备回滚，某项失败时此前成功项仍可能已完成。

### 验证

[检查程序](../tests/partition_operation_path_test.py)提取真实lookup、两种WipeByPath、RepairByPath和ResizeByPath方法，用私有分区对象记录调用。46断言通过；[旧源码同组](../logs/partition-operation-path-before.json)有20失败断言，这不是20个独立缺陷。覆盖：

- 嵌套挂载点、相邻名称边界、/system别名、/sdcard归属。
- 目标返回失败、子分区失败、父子调用、同块设备别名卸载。
- cache降级成功/失败、and-sec专用入口和既有tmp语义。

底层Wipe、Repair、Resize、Mount、实际设备定位及操作锁为替身；未运行格式化/fsck工具、删除目录、挂载或访问任何块设备。这是目标路由和返回值检查，**不是完整文件系统或清除功能验收**。UBSan开启。

设置挂载31断言、设置存储21项、备份55项、恢复54项及profile核心门控均通过。补丁序列从固定基线复现；installclean后`make -j$(nproc) recoveryimage`以30并发成功，新的recovery二进制与镜像内容一致。当前候选[recovery-dijun-unified-partition-paths.img](../imgs/built/recovery-dijun-unified-partition-paths.img)，SHA256 `fac3c815d6fab6febe23910c2f7bbf2c28d509a35003cb9db6df388b9237b4ed`。来源清单记录710文件；封装检查通过，同镜像profile回归9组、102次阶段调用通过。历史全量审计不转移至新镜像。

### 使用范围

后续已补充[15项同镜像ARM64文件系统工具执行](FILESYSTEM-TOOLS-EXECUTION.md)：私有普通文件中的ext4/F2FS/EROFS格式化、填充、检查、ext4扩容及部分内容读回。此证据独立于上面的分区对象替身；仍未贯通GUI/真实PartitionManager与内核挂载、加密或物理I/O，不将其升级为完整清除验收。

清除页面选择明确分区后确认；修复/文件系统变更页面只显示底层判定可用的操作。清除Data和格式化Data仍是不同入口，不能因解密失败自动执行。本轮修正目标查找，不是建议操作persist或protect分区；对这些分区的真实清除未执行、未验证。以上为该阶段的历史输入和验证边界；后续 NV 界面限制以上文 0054 / 0060 为准，当前状态见 [工作队列](WORK-QUEUE.md)。
