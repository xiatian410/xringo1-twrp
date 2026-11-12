# payload 操作执行器到 COW 的 ARM64 接续

本项接续 本文后附的 COW 格式验证，执行当前构建的真实 `InstallOperationExecutor → BzipExtentWriter / XzExtentWriter → BlockExtentWriter → SnapshotExtentWriter → ICowWriter`，再用真实 CowReader 解压读回。输入为合成操作数据，不是整份原厂 OTA。

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

## COW 格式往返验证

本项回答一个具体问题：六份所列原厂 OTA 请求的 **COW v3 / LZ4 / 64 KiB 压缩块**，是否能由当前构建的 Recovery 快照库实际写入、解析并解压读回。它不验证整份 OTA 安装。

### 输入与执行

`tests/ota_cow_roundtrip.py` 核对六份本地 `payload-manifest.pb` 与提取 inventory 的摘要及 metadata 校验记录，读取真实动态分区参数。六份均为 full payload、minor 0，均请求 snapshot / VABC、COW 3、LZ4、65536 字节压缩块；两份 OS4 另设置 `disable_ublk`。OS4 还有当前原型未消费的动态字段 9，显式记录而不忽略成“全字段兼容”。

测试程序链接当前 Android 构建的 **ARM64 `libsnapshot_cow.a`**，使用原构建命令中的 ABI、头文件和链接依赖；仅测试入口保持 assert 开启。固定 QEMU 在私有 chroot 中执行，Android linker 与共享库从当前交付镜像提取并逐文件绑定。

只访问临时普通文件，不创建设备节点、挂载或使用真实分区。私有环境没有真实 `/proc` / linkerconfig，链接器回退警告保留在本地报告；不能外推为真实 init namespace 验证。

### 结果

五个场景通过：

| 场景 | 核对内容 |
| --- | --- |
| 原厂参数往返 | 写入 64 KiB 确定性数据和两个 ZERO 块；Finalize / 关闭后重新 Parse / LZ4 解压，逐字节及主机 SHA-256 核对；压缩数据长度确实小于原始长度 |
| 容量拒绝 | 128 块上限拒绝 129 块请求，Finalize 正确返回 |
| 损坏头 | 改坏 COW magic 后 Parse 拒绝，不生成读回输出 |
| 不支持版本 | version 99 的 writer 创建被拒绝 |
| 不支持压缩器 | 非法压缩算法被拒绝 |

往返同时核对 v3 header、4096 字节 block、65536 最大压缩块、LZ4 标识、ZERO 目标集合，以及已存在标签 41 接受 / 不存在标签 42 拒绝。v3 标签位于 resume buffer，不能套用 v2 的 `GetLastLabel` 行为；恢复标签检查不是 OTA 重启恢复或断电试验。

六份 manifest 参数相同，因此执行一组共享参数往返，不重复执行六份等价夹具。没有发现本段需要修改生产代码的格式缺陷。

### 来源与边界

本地报告：`logs/ota-cow-roundtrip.json`，记录 archive、输入 manifest、工具链、链接依赖、QEMU、镜像库和测试源码摘要。

当前交付为 `recovery-dijun-unified-bounded-maintenance.img`，SHA-256 `218c5edd28c4e458464fc035a73b68808b016598c51e50877b2c0a1b055da3c3`。其旧 775 来源清单**没有历史绑定快照 archive 的摘要**。本测试绑定的是当前构建 archive 与当前 engine 链接输入声明，不据此宣称这些 archive 字节已被历史清单证明等同于交付 engine 内部代码。共享库和 linker 则直接来自交付镜像。

未执行：update_engine payload 解码与签名、SnapshotManager、LP / block-device 元数据、dm-user / UBLK、实际 snapuserd、分区写入、快照合并、OTA 重启与完整 GUI / USB。`disable_ublk` 这里只读取参数，未验证行为。

本批仅新增执行证据与范围说明，无生产补丁、无新镜像。完整任务仍进行中，下一步需推进实际 payload 消费到快照的连接，不继续拆分同类格式叶函数。

### 复现

需完整本地 Android 构建树、六份已校验样本、当前交付镜像和固定 QEMU：

```bash
python3 tests/ota_cow_roundtrip.py
```

公开仓库只发布源码与结果摘要，不包含这些依赖或原始日志。

## 快照映射失败的校验门控（0066）

`FilesystemVerifierAction` 原先忽略首次 `MapAllPartitions()` 和写入 verity 后重新映射的返回值。映射返回 false 时，如果目标路径仍有内容匹配的旧可读视图，原异步哈希流程可报告成功。这是调用方的软件错误，不依赖真实设备才能证明。

[0066 固定补丁](../dtsrc/O1_asic_dual/patches/0066-snapshot-map-verification-errors.patch) 在首次映射失败时通过既有 ScopedActionCompleter 返回 `kFilesystemVerifierError`（47）；重映射失败时先清理再返回 false，由原调用者传播同一错误。两处都尝试 `UnmapAllPartitions()` 释放可能已部分建立的映射，不重试，不继续读取旧目标。

`UnmapAllPartitions()` 自身的布尔值没有被改为新的通用失败门槛：Android 实现有独立的“没有自管映射”语义，不应盲目等同于清理失败。此处尝试清理不承诺已执行真实快照资源释放。

入口：`python3 tests/ota_snapshot_map.py --image /path/to/recovery.img`。编译完整原 ARM64 verifier 翻译单元，执行真实 ActionProcessor、异步读文件及哈希。FileControl 显式注入映射结果；匹配普通文件模拟残留可读视图，不创建设备或运行 SnapshotManager。生产翻译单元使用原 `NDEBUG` 以匹配 libchrome ABI，测试入口保留断言。

| 场景 | 修正后 | 修正前 |
| --- | --- | --- |
| 正常映射 | 成功 | 成功 |
| 首次映射失败、旧路径内容匹配 | 错误 47 | 误报成功 |
| 首次映射失败、目标不存在 | 错误 47 | 错误 47 |
| 正常重新映射 | 成功 | 成功 |
| 重映射失败、旧路径内容匹配 | 错误 47；包含前置卸载与失败后清理 | 误报成功 |
| 正常映射、哈希不符 | 错误 15 | 错误 15 |

六场景通过，同一夹具换回旧源码有两处失败；报告为本地 `logs/ota-snapshot-map.json` 与 `logs/ota-snapshot-map-before.json`。当前候选 `recovery-dijun-unified-snapshot-map.img`，SHA-256 `54d2210ef4b3213d4703ca2278b5ed49591ab2d61cac314ed0b737814f202a03`，779 份生产来源。installclean 后 `make -j$(nproc)` 构建完成，更新器含两条新诊断且与构建输出逐字节一致；相对前候选仅更新器、构建属性和文件摘要清单改变。

定向交付核对：`python3 scripts/audit_snapshot_map_delivery.py`，输出 `logs/snapshot-map-delivery.json`。字节未变的 GUI、profile 脚本和原厂资源不重复运行等价测试；旧报告不因此升级为新镜像全流程验收。完整 OTA 输入、实际 SnapshotManager / snapuserd、槽位切换和合并仍待完成。

## 从 payload 接到安装结束与切槽门控

`python3 tests/ota_payload_stream.py --finalize` 扩展同一测试入口，将合成 payload、VABC / COW、快照读回和原异步校验器的输出直接连接到真实 `PostinstallRunnerAction`。五个场景通过；不是复制五个独立叶函数。未发现本段需要新增生产补丁的错误，本批不重新构建镜像。

| 场景 | 最终结果 | FinishUpdate / 切槽调用 |
| --- | --- | --- |
| 完整写入、校验和完成 | 成功 | 各一次，先 FinishUpdate 后切槽 |
| FinishUpdate 拒绝 | 错误 5 | 完成一次，不切槽 |
| 切槽接口拒绝 | 错误 5 | 各一次，错误传到 ActionProcessor 结束 |
| 明确不切换槽位 | 状态 52（UpdatedButNotActive） | 均不调用 |
| 最终目标哈希不符 | 错误 15 | 不进入 PostinstallRunnerAction，均不调用 |

报告为本地 `logs/ota-payload-finalization.json`，来源复核为 `logs/ota-payload-finalization-review.json`。原始 13 场景因同一测试入口有改动，使用独立报告 `logs/ota-payload-finalization-stream-regression.json` 回归，旧报告原样保留。首次新场景的清理计数断言错误已保留：被前序哈希失败清除的未运行 action 内部 plan 仍为空，析构不会额外卸载；这不是生产故障。

本组明确跳过实际 postinstall 脚本，安装计划 `download_url` 为空；不能据此宣称原厂 postinstall 分区挂载或脚本执行已通过。FinishUpdate 与 SetActiveBootSlot 是观察调用顺序并注入失败的边界，FakeHardware 的相关回调仅在内存中执行，不修改槽位、metadata、vbmeta 或其他真实设备。原校验器、postinstall action、ActionProcessor 均来自实际 ARM64 构建代码；生产 archive 按测试时摘要绑定，不能升级为旧镜像清单的历史绑定。

当前候选仍为 snapshot-map，779 份生产来源及镜像字节不变。此证据缩小的是“校验结果如何到达安装结束及切槽接口”的缺口；实际 SnapshotManager、Boot Control HAL、完整下载器 / GUI、真实 OTA 输入、postinstall 脚本和快照合并仍未完成，不追加等价的正常路径测试来代替这些边界。

## OS4 原厂操作数据执行

`python3 tests/ota_operation_cow.py --stock` 使用两份 OS4 的**真实操作 protobuf、原始编码数据和目标 extents**，执行原 ARM64 InstallOperationExecutor → SnapshotExtentWriter → COW，再通过原 CowReader 解压读回。每份选择 REPLACE / REPLACE_BZ / REPLACE_XZ 各一个，共六项通过；不是重新运行合成压缩输入。

| 操作 | 分区与序号（从 0 开始） | 两份输入大小 | 输出大小 |
| --- | --- | --- | --- |
| REPLACE | mi_ext / 1 | 各 2,097,152 B | 各 2,097,152 B |
| REPLACE_BZ | odm / 7 | 921,694 / 922,091 B | 各 2,097,152 B |
| REPLACE_XZ | mi_product / 0 | 各 3,452 B | 各 348,160 B |

旧 OS4 从本地原始 ZIP 读取；正式版仅使用既有 range cache，不重新下载。编码输入的 SHA-256 必须匹配原 manifest 的 operation hash；每个完整分区文件先核对大小与 SHA-256，再按原 extents 切出独立期望值。ARM64 读回逐字节相同，主机另记录摘要，非零目标块位置及无重复 / 遗漏块均断言。未操作真实分区或 vbmeta；仅在私有 chroot 读写普通文件。

最初 BZ 选择了 48 字节的近全零编码块，后改为 odm 的约 900 KiB 实际压缩块，避免仅证明极简单内容。六项报告为 `logs/ota-stock-operation-cow.json`；旧选择的结果保留本地。共用测试入口修改后，原八项回归单独保存为 `logs/ota-operation-cow-after-stock-extension.json`，原始报告未覆盖。可用 `--report` 指定独立输出。

六份 manifest 的操作清点均只有 REPLACE / BZ / XZ；两份 OS4 的 system 另声明可选 `system/bin/otapreopt_script`。这一静态观察不代替实际 postinstall 挂载或执行验收。此组六项只覆盖两份 OS4 的所选操作，**未将原厂完整 manifest 和全部数据交给 DeltaPerformer**，也未执行 SnapshotManager、postinstall、切槽或合并；此前完整接续仍使用合成 payload。没有发现本段需要改生产代码的问题，snapshot-map 镜像与 779 来源保持不变。

## 完整本地 OS4 payload 输入

入口 `python3 tests/ota_stock_payload.py` 使用本地 OS4 旧样本 ZIP 中未改动的 `payload.bin`，原始 CrAU 头、manifest、操作数据和尾部签名均不重建。输入大小 7,821,653,872 B，42 个分区、4,903 个操作，目标共 10,235,486,208 B。完整流与原最终校验器执行通过：全部 4,903 个操作完成，42 个目标哈希逐项匹配，完整 payload 长度与 FILE_HASH 匹配。不是完整设备 OTA 验收。

原 DeltaPerformer 按 1 MiB 流式读取，真实分区工厂为静态分区选择原 PartitionWriter、为十个动态分区选择 VABCPartitionWriter。静态目标是临时普通文件；动态目标为原 COW writer，完成后通过 CompressedSnapshotReader 将视图落盘，再由原异步 FilesystemVerifierAction 检查原 manifest 的最终目标哈希。完整测试使用磁盘目录，避免 15 GiB 的 `/tmp` tmpfs 被完整目标与 COW 占满。

PreparePartitionsForUpdate / BootControl 的路径和设备映射由明确替身实现；没有真实 LP、SnapshotManager、snapuserd、mount、槽位切换、postinstall 或物理设备操作。原厂 payload 中的 vbmeta 仅作为普通文件内容写入临时目录，不执行 AVB 修改。FakeHardware 时间与版本接口不能证明设备实际降级 / SPL 策略。生产 archive 只做测试时绑定，不升级为历史镜像来源证明。

首次测试环境遗漏 `/system/etc/security/otacerts.zip`，mandatory 元数据检查在首块返回错误 25。原始失败报告保留为 `logs/ota-stock-payload-missing-cert.json`。随后从**同一交付镜像**提取该证书到原路径，保留 mandatory 配置，未引入测试公钥或修改签名策略；Recovery 内部密码学比较的既有编译边界仍然适用，不能据此宣称整包认证通过。

本地 stdout / stderr 和结构化结果分别保存在 `logs/ota-stock-payload.stdout`、`logs/ota-stock-payload.stderr`、`logs/ota-stock-payload.json`。`python3 scripts/review_stock_payload.py` 复核来源、当前镜像库 / 证书、完整 payload 哈希、操作完成数和 42 个目标哈希，而不重跑耗时执行。本次复核通过；所有 42 个目标哈希与原 manifest 一致，十个动态分区 COW 视图正常读回。原链接器 / 缺失 proc / 普通文件 ioctl 警告保留，没有将这些替身提升为真实系统启动证据。

## OS4 正式版完整输入执行

正式版完整执行使用同一 `tests/ota_stock_payload.py --sample os4-stable` 入口，旧样本默认参数与旧报告保留，不因扩展选择参数重新运行旧样本。`--source` 可指定匹配所选样本的本地原始 ZIP；脚本检查 payload 头、manifest 和 metadata 摘要，最终由更新器检查 FILE_HASH。

`scripts/materialize_cached_ota.py` 将现有正式版范围缓存补成完整普通 ZIP。已有缓存缺 15 个 8 MiB 分片，只补缺失项；请求固定既有 ETag，要求 HTTP 206、精确 Content-Range 和相同对象长度，写入临时文件后再发布。合并前逐块检查大小，合并后检查原 manifest、metadata hash、完整 payload FILE_HASH 与 ZIP 内 properties。此过程不进行证书认证，不能将强 ETag 当作完整 ZIP 哈希。

重组 ZIP 大小为 7,883,598,024 B，SHA-256 为 `a1dcfecccf4397943e6836539bea6573ade01c84ef9ee1e360df9c233493f04b`。payload 大小为 7,883,589,123 B，原 manifest 有 42 分区、4,933 操作，目标共 10,297,356,288 B。原始缓存与 ZIP 只保留本地；`logs/ota-stock-stable-materialization.json` 记录本次补块、分块哈希与最终输入摘要。旧 inventory 不被静默重写为新提取历史。

正式版运行结果写入独立 `logs/ota-stock-stable-payload.json`、`.stdout`、`.stderr`，来源复核入口为 `python3 scripts/review_stock_payload.py --report logs/ota-stock-stable-payload.json`。完整流和来源复核均通过：4,933 个操作全部完成，42 个原 manifest 目标哈希逐项一致，十个动态分区 COW 视图全部正常读回。完整 FILE_SIZE / FILE_HASH 匹配；Prepare、设备映射、namespace 仍是上述离线边界，无实际 SnapshotManager / postinstall / 合并验收。未发现本段生产代码缺陷，无新增补丁或镜像。旧样本结果作为历史证据复用，不因脚本增加参数覆盖旧报告或伪称重新执行。

## Recovery 缺失 metadata 时的回退判断

本段检查一个具体实现决定：`PreparePartitionsForUpdate` 在 Recovery 的 `/metadata` 不可用时允许进入直接分区准备，但 `MapAllPartitions` 仍按目标的 snapshot 能力请求映射，是否会使最终校验误拒绝。不能单凭直接调用后者失败就增加补丁。

`python3 tests/ota_recovery_fallback.py` 编译完整原 `DynamicPartitionControlAndroid` 翻译单元，以当前交付 linker / 库和固定 QEMU 运行六个 AArch64 场景。使用已有 friend 注入无 metadata 的 ISnapshotManager 边界，直接分区准备、Recovery 模式和 AVB footer effect 为明确替身；不会访问 AVB、metadata、挂载或物理设备。场景包括 Recovery 回退成功、直接准备失败、Android metadata 失败、独立映射成功 / 失败及无 snapshot 目标。实际控制器的准备、目标标志、metadata 条件、compression 查询和完成路径执行。

观察到 Recovery 回退成功后，单独调用 MapAllPartitions 确实仍会请求映射并失败。但真实分区 writer 工厂与最终 verifier 先检查 `UpdateUsesSnapshotCompression()`。原 libsnapshot 在共享状态锁获取失败时返回 false；测试的无 metadata 边界也明确返回 false。**没有证据表明实际调用方会在这条回退路径请求映射，因此撤回“新增回退映射门控补丁”的假设。** 此处 caller gate 与 libsnapshot 实现为源码核对，控制器为实际执行；未把它们描述为一次完整 SnapshotManager / verifier 端到端运行。

初次测试误将 `-UNDEBUG` 放在构建模板的 `-DNDEBUG` 之前，断言实际被关闭，所得初次 PASS 已作废、仅本地留档；最终夹具加入编译期 NDEBUG 拒绝，并在所有生产参数之后启用断言，六场景重新通过。负向断言运行显示孤立映射失败，随后按调用方条件修正测试预期，未将夹具假设误记为生产缺陷。

当前生产来源恢复并核对为 log-export 候选的 781 份绑定，交付仍为 `recovery-dijun-unified-log-export.img`（`629f19792d41e1fbc4ec0ad0b7f38bed70ba9b51f234544de4f5cd53a551bf3c`）。试验补丁和试验镜像不交付，未重编无变化的正式候选。报告 `logs/ota-recovery-fallback.json`，范围复核入口 `python3 scripts/review_recovery_fallback.py`。这新增一条实现决定的证据，不是功能修复；真实 SnapshotManager / metadata / 映射和完整 OTA 仍待完成。

## 快照状态文件同步失败0069

本批执行原始 ARM64 `SnapshotManager::FinishedSnapshotWrites()`，不再用该方法的返回值替身。实际 protobuf 状态读取、目录锁、snapshot 状态文件解析、forward-merge / rollback / boot 标记处理与原子写入辅助函数，均在私有临时目录执行。初始 `Initiated` 状态和 `using_snapuserd` snapshot 记录由夹具提供，不代表真实 COW 已写完；映射、分区访问、image manager 和切槽操作全部拒绝。唯一允许的 boot HAL 方法为记录 `SNAPSHOTTED` 并提供成功 / 失败结果的边界。

发现原 `WriteStringToFileAtomic()` 在临时文件 `fsync` 返回错误后只记录日志，仍继续 rename 并可能返回成功。针对 `snapshot-boot.tmp` 和 `state.tmp` 分别注入一次 `EIO`，原 `FinishedSnapshotWrites()` 均返回 true。调用方 `DynamicPartitionControlAndroid::FinishUpdate()` 直接传播该结果，之后的 PostinstallRunnerAction 据此决定是否继续切槽，故这是实际错误传播缺陷。

维护补丁 [0069-snapshot-state-sync-errors.patch](../dtsrc/O1_asic_dual/patches/0069-snapshot-state-sync-errors.patch) 在文件同步失败时返回 false，并以 `TEMP_FAILURE_RETRY` 重试 `EINTR`。保持目录同步的既有语义。该辅助函数由多种 libsnapshot 库共用，因此 init、fastbootd、Recovery 和 update_engine_sideload 都重新链接；没有改动签名或 AVB 策略。

```bash
python3 tests/ota_snapshot_finish.py
python3 scripts/audit_snapshot_sync_delivery.py
```

16 个场景覆盖正常完成、wipe forward 标记、幂等调用、非法初态、缺 metadata / snapshots、损坏 snapshot protobuf、forward 写入 / rollback 移除 / boot rename / state 临时文件打开失败、HAL merge 状态拒绝、两个文件同步错误和两个 `EINTR` 重试。成功时逐字比较保留的状态字段、boot 槽位和标记；失败时检查原状态保留。旧 helper 使用同一夹具单独编译覆盖，16 项中两项 I/O 错误误报成功，另两项虽返回成功但没有实际重试同步；新 helper 全部通过。夹具编译强制开启断言，QEMU、linker、库、静态 archives、源码与输入均有摘要绑定。

最终候选 `recovery-dijun-unified-snapshot-sync.img`，SHA-256 `e1e651e05787f750a310a8eaaff8da897e38043c40d8eac59b69afce2f8d3cc6`。`installclean` 后 `make -j$(nproc)`，30 并发，784 生产来源绑定、六 profile 封装通过。本地报告为 `logs/ota-snapshot-finish.json`、`logs/ota-snapshot-finish-before.json` 与 `logs/snapshot-sync-delivery.json`；原始日志和镜像不上传。

**边界：** 状态组不是事务。boot 标记或 HAL merge 状态可能先于最终 state 写入保留；失败的临时文件也会保留，后续正常写入沿用既有覆盖行为。已经 `Unverified` 的幂等调用不会重新检查标记。本批不新增全组回滚，不证明断电持久性、实际 HAL、metadata 挂载、设备映射、snapuserd、合并或整份 OTA 到最终切槽的完整接续。两份原厂 payload 的既有结果仅复用未变的执行器范围，不把本批状态文件测试与它们拼接成完整安装证明。

## 实际收尾调用链与失败后重试

0069 的文件同步修正后，进一步把原始 `PostinstallRunnerAction → DynamicPartitionControlAndroid::FinishUpdate → SnapshotManager::GetUpdateState / FinishedSnapshotWrites` 接在同一个 ARM64 进程内运行。原控制器通过现有 friend 接口注入真实 SnapshotManager 和“metadata 已挂载”的显式 token；没有覆写 FinishUpdate 返回结果，也没有修改原始实现。PostinstallRunnerAction 的输入为合成 InstallPlan，空 URL 沿原无脚本路径完成，不执行真实 postinstall 脚本。

六场景执行正常完成，以及 boot / state 文件同步失败、state 临时文件打开失败、HAL merge 状态拒绝、切槽失败。前四类收尾失败返回 `kPostinstallRunnerError`，切槽调用次数为零。移除注入故障后销毁并重新创建控制器与 SnapshotManager，沿用同一份状态文件、启动标记和残留临时文件重试；全部完成并仅在收尾成功后尝试切槽。切槽失败时实际状态已经 Unverified，重试由原控制器跳过重复状态发布，直接再次尝试切槽。检查完整顺序、最终状态字段及标记内容，而非只看终态成功。

```bash
python3 tests/ota_snapshot_finish.py --postinstall
python3 scripts/review_snapshot_postinstall.py
```

新夹具为 `tests/ota_snapshot_postinstall.cpp`，复用前节的拒绝设备依赖和 fsync 注入。实际切槽和 HAL merge 状态仅观察参数、调用顺序及提供结果；FakeHardware 不执行 vbmeta 写入。没有真实挂载、块设备、snapuserd、COW 合并或断电。本证据接续原始收尾控制流，尚未把原厂 payload、实际映射与 postinstall 脚本贯通，不将其称作完整 OTA 安装。

本地报告 `logs/ota-snapshot-postinstall.json` 与 `logs/ota-snapshot-postinstall-review.json`。六场景通过，未发现需追加生产修改的行为。共享测试脚本增加模式后，原 16 场景及旧 helper 的四个预期失败做一次必要回归。当前候选仍为前节 snapshot-sync，784 生产来源未变；本批仅增加验证证据，没有新镜像构建。

## postinstall 程序退出与取消接续

进一步执行原始 `PostinstallRunnerAction → Subprocess → brillo::ProcessImpl / ProcessReaper / AsynchronousSignalHandler`。父进程和无害子程序均为实际 ARM64 ELF，经当前候选的 linker / libc 在私有 chroot 中运行。真实 clone、进程组、进度管道、signalfd、wait 和取消清理均执行；execv 边界显式改为启动 QEMU 和 Android linker，保留原 postinstall 程序及两个参数（target slot=1、progress fd=3）。不依赖主机 binfmt，不挂载 proc 或任何设备。

设备只读标记、挂载 / 卸载、FinishUpdate 和切槽为记录型边界，实际 mount / ioctl 没有执行。程序写入精确进入标记、发送 0.25 / NaN / 0.75 进度后，按场景退出或等待取消。9 场景覆盖成功、exit7、可选 exit7、特殊 exit3 / exit4、SIGTERM、程序缺失、挂载拒绝、执行中取消。必选失败阻止 FinishUpdate 和切槽；可选失败沿原策略继续。取消产生 ProcessingStopped，不冒充完成或切槽，检查无遗留可回收子进程。进度值有界且正常场景实际接收两段有效进度，NaN 未污染进度。

```bash
python3 tests/ota_postinstall_program.py
python3 scripts/review_postinstall_program.py
```

夹具 `tests/ota_postinstall_program.cpp` 在包含 libchrome 头时匹配生产 NDEBUG ABI，随后显式恢复并检查断言开启；子程序源码 `tests/ota_postinstall_program.c` 不操作原厂数据。最初夹具存在 wrapper 声明、final stub 继承、libchrome ABI 和标记长度错误，均在编译 / 运行失败后修正，没有修改生产实现或放宽最终状态检查。本地报告 `logs/ota-postinstall-program.json` 和 `logs/ota-postinstall-program-review.json` 记录原始诊断与源码 / 库 / ELF 摘要。

同时读取并核对六份已有原厂 payload manifest 的摘要：两份 OS4 配置 `system/system/bin/otapreopt_script`（partition=system，relative path=`system/bin/otapreopt_script`），`run_postinstall=true`、`postinstall_optional=true`；OS2 / OS3 四样本无 postinstall 配置。这里只确认安装计划的原厂配置，不代表已经执行 otapreopt。

九场景通过，未发现需生产修正的行为。本批无新构建，沿用 snapshot-sync 候选与 784 来源。原厂 otapreopt、真实挂载与执行 namespace、实际 SnapshotManager / payload 到脚本接续及快照合并仍未完成，不把单独通过的链条拼接为完整 OTA 证明。
