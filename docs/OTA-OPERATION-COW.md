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

这些上层是**源码检查，未在本测试执行**。因此不把短输入行为直接升级为“OTA 可错误成功”的结论，也没有依据此测试盲改生产代码。后续应接续完整 DeltaPerformer / VABC 完成 / 最终哈希验证，检查失败是否沿安装生命周期正确返回。

六份原厂操作统计也写入本地报告。合成 REPLACE / BZ / XZ 不代替原厂操作数据的完整执行，更不覆盖 delta/source-copy/diff、ZERO / DISCARD 的完整安装行为。

## 执行与来源边界

入口：`python3 tests/ota_operation_cow.py`，需要完整 Android 构建树、当前交付镜像、原厂 manifest 和固定 QEMU。

- 运行的是 AArch64 ELF，链接当前 Recovery `libpayload_consumer.a` 等生产 archive；没有复制或重写执行器方法。
- 原构建命令、archive、生成 protobuf / 传递头文件、测试、输入及 QEMU 均有摘要绑定。
- linker 与共享库来自当前交付镜像。archive 是测试时绑定，旧 775 来源清单没有对它做历史绑定，不能据此宣称等同于交付 engine 内部全部代码。
- 私有 chroot 仅使用普通文件，无设备、mount、真实 `/proc` 或 init namespace。链接器配置回退警告保留。
- 没有执行 VABC Init / OpenCowWriter、SnapshotManager、payload 签名 / 哈希验证、LP / dm-user / UBLK、merge、实际 USB 或 GUI。

本地原始报告为 `logs/ota-operation-cow.json`；公开摘要见 [CURRENT-VALIDATION.json](CURRENT-VALIDATION.json)。本批只新增证据，没有生产补丁、新镜像或功能已修复声明。此前五场景 COW 格式结果复用，不重新运行。
