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

## DeltaPerformer 完成与关闭错误修正（0065）

沿 `DeltaPerformer::Write` 向上检查，确认最后一个分区的 `FinishedInstallOps` 失败只返回 false、错误码仍为成功；最后一次 `CloseCurrentPartition` 返回值被忽略，甚至可能返回 true。分区切换的 Close 失败也未设置错误码。`DownloadAction::ReceivedBytes` 会把 false + 成功码转换为通用写入错误，所以前两种“缺错误码”不能直接称为整个安装误成功；最后关闭被忽略仍是独立缺陷。

[0065 固定补丁](../dtsrc/O1_asic_dual/patches/0065-delta-partition-finalization-errors.patch) 让这些路径返回 false 并设置 `kDownloadWriteError`（14），在签名数据继续处理之前停止。不自动重试，不清除已经写入的数据。

`python3 tests/ota_delta_finalization.py --image /path/to/recovery.img` 编译原始完整 `delta_performer.cc` 并执行 AArch64 `Write()`。使用既有测试 friend 设置“manifest 已解析”的输入边界；原始分块缓冲、操作哈希、分发、进度、完成与关闭执行，分区 writer 只观察调用并注入失败。

八场景包括正常 / 分块输入、操作失败、强制哈希不匹配、最后完成失败、最后关闭失败、切换完成失败、切换关闭失败。修正前后三个缺陷准确复现，其余五项保持通过。旧源码留本地 `backups/delta-finalization-pre-fix/delta_performer.cc`；公开历史和补丁可重建旧实现，不上传编译产物。

当前镜像为 `recovery-dijun-unified-delta-finalization.img`，SHA-256 `ff01192e210a94a915f2b8e6d421479dcb09cb76d131dad561805e94421d88a2`。先 installclean，再 `make -j$(nproc)` 清理构建，777 份生产来源、六份 profile 与编译更新器逐字节核对。相对前候选仅更新器、构建属性和文件摘要清单改变，未重跑字节未变的 GUI / runtime 功能。

交付检查入口 `python3 scripts/audit_delta_finalization_delivery.py`；本地报告 `logs/delta-finalization-delivery.json`。这是生产修复及其必要回归，仍未执行完整签名 payload 输入、SnapshotManager、槽位切换或合并，不扩大为 OTA 全链验收。

## 合成 payload 从头输入的完整软件接续

入口：`python3 tests/ota_payload_stream.py`；本地报告 `logs/ota-payload-stream.json`。本次不修改生产代码或重编镜像，沿用 delta-finalization 候选。此前直接设置“manifest 已解析”的 friend 只属于收尾错误测试；本组**不使用 friend 或私有状态赋值**。

测试构造 CrAU v2 头、真实 protobuf manifest、操作数据及尾部签名格式块，以每次 113 字节流入原 `DeltaPerformer::Write`。真实执行元数据解析、manifest 检查、MemoryPrefs、InstallPlan 分区解析、分区工厂选择、VABC 写入 / 收尾、payload 长度 / 哈希比较、COW 快照读取，并将完整视图落盘交给原异步 FilesystemVerifierAction。RAW、BZ、XZ 的 64 KiB 内容逐字节读回匹配。

| 输入 / 失败场景 | 结果与写入边界 |
| --- | --- |
| RAW / BZ / XZ | 完整软件链成功、payload 哈希与最终目标哈希匹配 |
| 错误 magic / major / minor / metadata size | 错误 21 / 44 / 45 / 32；未准备分区或打开 COW |
| 操作哈希错误 | 错误 29；COW 已打开但无 replace 数据 |
| 分区准备空间不足 / COW 打开失败 | 错误 60 / 7，无操作写入 |
| 操作数据截断一字节 | Write 等待更多字节；Close 非零、VerifyPayload 长度错误，无操作写入 |
| 尾部签名块截断一字节 | 操作已写入 16 块；Close 非零、VerifyPayload 长度错误，不回滚 |
| 没有尾部签名块 | 操作已写入，VerifyPayload 拒绝缺失签名块 |

共 13 场景。初次把无签名流当成可通过 VerifyPayload 的输入，真实实现拒绝；补齐明确标识的签名格式夹具后，又把“尾部截断无写入”的错误假设修正为上述两个阶段。保留首次失败报告于本地，不把这些夹具问题算成生产缺陷。

**签名边界**：当前 `__ANDROID_RECOVERY__` 编译会跳过 metadata 与 payload 的密码学签名比较，但配置公钥时仍要求非空尾部签名块。测试使用临时生成的公钥和 protobuf 中的 `unsigned-fixture-marker`，它不是有效签名，不能宣称认证成功。没有修改公钥、原信任策略或生产签名代码；完整 OTA ZIP 的外层签名验收属于另一入口范围。

FakeHardware / FakeBootControl 提供版本与槽位接口，FileControl 代替 PreparePartitionsForUpdate 和设备映射，只创建临时普通文件。真实 SnapshotManager / snapuserd / LP / UBLK、重启槽位与合并均未执行。没有真实 OTA 分区数据、postinstall 或完整下载器生命周期，仍不能声明“OTA 全链完成”。交付 linker / 共享库直接取自当前镜像；archive 测试时绑定，来源范围不升级为旧镜像历史证明。
