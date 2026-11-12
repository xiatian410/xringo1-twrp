# 嵌套分区操作路径修正

2026-11-12。设置保存的0028修正使`/mnt/vendor/persist/TWRP`能找到persist，但清除、转换文件系统、修复、调整大小四个入口仍使用GetRootPath。dijun fstab登记`/mnt/vendor/protect_f`、protect_s、nvdata、nvcfg、persist，旧入口却只查`/mnt`，因此无法选择这些真实挂载点。转换/修复/调整大小还缺少`/system`→`/system_root`映射。

维护补丁[0029-nested-partition-operations.patch](../dtsrc/O1_asic_dual/patches/0029-nested-partition-operations.patch)复用真实FindPartitionByPath选出的owner，按owner挂载点执行，并在操作全程持有现有递归操作锁。保留原始Wipe/Repair/Resize能力检查和确认入口；没有添加分区、改变可清除权限、改写fstab或绕过解密失败保护。路径包含普通子目录时仍归属其分区，不能将WipeByPath当成文件删除接口。

同时修正两个错误返回：子分区失败不再被忽略；不存在独立cache时，`/data/cache`清理返回值不再被丢弃。后者只传播WipeDataCache的现有结果；该底层函数未完整检查目录删除错误，本轮不能据此承诺所有删除故障均能传播。多分区操作不具备回滚，某项失败时此前成功项仍可能已完成。

## 验证

[检查程序](../tests/partition_operation_path_test.py)提取真实lookup、两种WipeByPath、RepairByPath和ResizeByPath方法，用私有分区对象记录调用。46断言通过；[旧源码同组](../logs/partition-operation-path-before.json)有20失败断言，这不是20个独立缺陷。覆盖：

- 嵌套挂载点、相邻名称边界、/system别名、/sdcard归属。
- 目标返回失败、子分区失败、父子调用、同块设备别名卸载。
- cache降级成功/失败、and-sec专用入口和既有tmp语义。

底层Wipe、Repair、Resize、Mount、实际设备定位及操作锁为替身；未运行格式化/fsck工具、删除目录、挂载或访问任何块设备。这是目标路由和返回值检查，**不是完整文件系统或清除功能验收**。UBSan开启。

设置挂载31断言、设置存储21项、备份55项、恢复54项及profile核心门控均通过。补丁序列从固定基线复现；installclean后`make -j$(nproc) recoveryimage`以30并发成功，新的recovery二进制与镜像内容一致。当前候选[recovery-dijun-unified-partition-paths.img](../imgs/built/recovery-dijun-unified-partition-paths.img)，SHA256 `fac3c815d6fab6febe23910c2f7bbf2c28d509a35003cb9db6df388b9237b4ed`。来源清单记录710文件；封装检查通过，同镜像profile回归9组、102次阶段调用通过。历史全量审计不转移至新镜像。

## 使用范围

后续已补充[15项同镜像ARM64文件系统工具执行](FILESYSTEM-TOOLS-EXECUTION.md)：私有普通文件中的ext4/F2FS/EROFS格式化、填充、检查、ext4扩容及部分内容读回。此证据独立于上面的分区对象替身；仍未贯通GUI/真实PartitionManager与内核挂载、加密或物理I/O，不将其升级为完整清除验收。

清除页面选择明确分区后确认；修复/文件系统变更页面只显示底层判定可用的操作。清除Data和格式化Data仍是不同入口，不能因解密失败自动执行。本轮修正目标查找，不是建议操作persist或protect分区；对这些分区的真实清除未执行、未验证。物理震动、自动触摸/唤醒、设置现场保存及其他任务文档项目继续未完成。
