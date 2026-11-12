# payload 操作执行器到 COW 的 ARM64 接续

本项接续 [COW 格式验证](OTA-COW-ROUNDTRIP.md)，执行当前构建的真实 `InstallOperationExecutor → BzipExtentWriter / XzExtentWriter → BlockExtentWriter → SnapshotExtentWriter → ICowWriter`，再用真实 CowReader 解压读回。输入为合成操作数据，不是整份原厂 OTA。

## 八个场景

测试使用六份已校验 manifest 共同请求的 COW v3、LZ4、64 KiB 参数，向两个不连续的八块区间写入共 64 KiB 数据：目标块 `0..7` 和 `24..31`。对读回的每个目标块和每段解压内容进行检查，主机另核对 SHA-256。

| 场景 | 原操作返回 | 实际 COW 结果 |
| --- | --- | --- |
| REPLACE | true | 16 个目标块，内容完整 |
| REPLACE_BZ | true | 原 bzip2 解压后写入，内容完整 |
| REPLACE_XZ | true | 原 xz-embedded / CRC32 解压后写入，内容完整 |
| BZip2 损坏头 | false | 无数据块 |
| XZ 损坏头 | false | 无数据块 |
| 第二目标超容量 | false | 第一段八块已写入；没有回滚保证 |
| RAW 输入仅 4096 字节 | true | 缓冲未达到第一 extent 的 32768 字节，实际无 COW 数据块 |
| RAW 输入超出目标 4096 字节 | false | 所有预期块已经写入；错误返回不能当成目标未改变 |

`short-raw` 的 PASS 表示**准确复现上述返回与内容差异**，不表示此输入有效或安装成功。操作层的 `true` 只表示它消费了输入，不独立证明目标 extents 全部填满。

## 上层约束与结论

当前源码检查显示：

- DeltaPerformer 按 manifest 声明的 `data_length` 缓冲完整输入，并执行 operation hash 检查；它不能仅凭此推导解压后的 extents 已填满。
- VABCPartitionWriter 完成时添加结束标签、Finalize 并检查 merge ops。
- FilesystemVerifierAction 对最终 target hash 不匹配的 full payload 返回 `kNewRootfsVerificationError`。

上述八场景中这些上层是**源码检查，未执行**；后续十场景的 VABC / 最终校验实际执行范围见下节。因此不把短输入行为直接升级为“OTA 可错误成功”的结论，也没有依据此测试盲改生产代码。后续应接续完整 DeltaPerformer / VABC 完成 / 最终哈希验证，检查失败是否沿安装生命周期正确返回。

六份原厂操作统计也写入本地报告。合成 REPLACE / BZ / XZ 不代替原厂操作数据的完整执行，更不覆盖 delta/source-copy/diff、ZERO / DISCARD 的完整安装行为。

## 执行与来源边界

入口：`python3 tests/ota_operation_cow.py`，需要完整 Android 构建树、当前交付镜像、原厂 manifest 和固定 QEMU。

- 运行的是 AArch64 ELF，链接当前 Recovery `libpayload_consumer.a` 等生产 archive；没有复制或重写执行器方法。
- 原构建命令、archive、生成 protobuf / 传递头文件、测试、输入及 QEMU 均有摘要绑定。
- linker 与共享库来自当前交付镜像。archive 是测试时绑定，旧 775 来源清单没有对它做历史绑定，不能据此宣称等同于交付 engine 内部全部代码。
- 私有 chroot 仅使用普通文件，无设备、mount、真实 `/proc` 或 init namespace。链接器配置回退警告保留。
- 没有执行 VABC Init / OpenCowWriter、SnapshotManager、payload 签名 / 哈希验证、LP / dm-user / UBLK、merge、实际 USB 或 GUI。

本地原始报告为 `logs/ota-operation-cow.json`；公开摘要见 [CURRENT-VALIDATION.json](CURRENT-VALIDATION.json)。本批只新增证据，没有生产补丁、新镜像或功能已修复声明。此前五场景 COW 格式结果复用，不重新运行。

## VABC 会话与最终校验接续

入口：`python3 tests/ota_vabc_session.py`。本地报告 `logs/ota-vabc-session.json`；使用同一套构建 archive、交付 linker / 共享库和固定 QEMU。此前八场景和五场景格式检查来源未变，直接复用。

真实执行链为：`VABCPartitionWriter::Init → PerformReplaceOperation / PerformZeroOrDiscardOperation → CheckpointUpdateProgress → FinishedInstallOps → Close → CompressedSnapshotReader`。再将原读取器生成的完整 128 KiB 视图保存为普通文件，交给原 `ActionProcessor → FilesystemVerifierAction` 异步读取和哈希比较。没有提取或重写生产方法。

| 场景 | 操作返回 | 完成 / 关闭 | 最终校验 |
| --- | --- | --- | --- |
| RAW / BZ / XZ | true | true / 0 | 成功 |
| RAW 加 ZERO | true | true / 0 | 成功，零区间与保留源数据分别检查 |
| RAW 仅 4096 字节 | true | true / 0 | 错误 15：`kNewRootfsVerificationError` |
| RAW 超出目标 4096 字节 | false | true / 0 | 内容完整，独立校验成功；不能忽略前面的操作失败 |
| BZ / XZ 损坏头 | false | true / 0 | 错误 15 |
| 正常数据但期望哈希错误 | true | true / 0 | 错误 15 |
| OpenCowWriter 拒绝 | Init false | 完成 false / 关闭 0 | 不启动校验，无 COW 文件 |

共十场景。操作失败后继续调用完成与独立校验，仅用于观察留下的内容，**不是实际安装应继续的成功路径**。`FinishedInstallOps` 成功本身不证明目标内容完整；本次执行确认原最终校验器能拒绝短输入，不据此增加生产补丁。

`FileControl` 是明确的设备控制替身：创建普通 COW 文件，记录 Map / Unmap 各一次，其他未使用接口拒绝调用。真实快照读取器按 7013 字节分段读取，覆盖未对齐边界；未写区间从普通 source 文件读取。设备映射处把视图落盘，**没有运行 SnapshotManager、dm-user、snapuserd 或 UBLK**。实际校验器对普通文件设置块设备只读的 ioctl 返回 ENOTTY，警告原样保留，不屏蔽或替换返回值。

此处关闭 verity 写入，没有构建 FEC / hash tree，不涉及 AVB。未覆盖断点恢复、COPY / XOR / diff、真实签名 payload 输入、槽位切换或合并。完整 OTA 仍未验收，下一步应定位完整输入和失败传播的具体缺口，不重复运行本组。archive 依旧只有测试时摘要绑定，不能冒称已由旧交付来源清单历史绑定。
