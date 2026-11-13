# 备份与恢复数据路径

本文汇总归档编解码、文件元数据恢复与原始镜像复制的实现和分层验证。会话管理见[备份会话](BACKUP-SESSION-ADAPTATION.md)与[恢复预检](RESTORE-SESSION-ADAPTATION.md)；当前交付及剩余范围以[交付报告](../simulation-report.md)和[工作队列](WORK-QUEUE.md)为准。下文日期和测试数量保留各阶段原有范围，不代表当前完整验收。

- [归档编解码与分卷](#archive-pipeline)
- [文件与元数据恢复](#archive-restore)
- [原始镜像复制](#raw-image)

<a id="archive-pipeline"></a>

## tar、压缩、加密与分卷管道

日期：2026-11-11。修改固定在设备树补丁 [0020](../dtsrc/O1_asic_dual/0020-archive-codec-pipelines.patch)，当前镜像和哈希见[模拟报告](../simulation-report.md)。本轮只执行主机夹具，没有连接手机。

### 修改与原因

| 原行为 | 当前行为 |
|---|---|
| AES fork 后没有 exec，继承其他归档线程的管道写端，解密/编码等待 EOF 不能结束 | AES 子进程重定向标准输入输出后关闭其他描述符；支持 close_range 和有限 fd 遍历后备 |
| libtar 将管道单次短读当成块损坏 | 读取回调累计到请求长度，重试 EINTR；全部恢复入口使用该回调，真实 EOF/错误仍返回失败 |
| tar 结束后未等待解码器，gzip 尾部 CRC 错误可能被忽略 | 消费结束块后的流，检查零填充和编码器最终退出结果；失败终止并回收相关 helper |
| OAES 流函数没有结果，子进程可能把失败报告成成功 | 检查随机数、读取、写入和 EVP 调用，返回 bool 并成为子进程退出码 |
| 多线程共享 tar 写缓冲区、位置和进度 fd | 状态改为 thread_local，归档线程各自拥有缓冲区 |
| 加密列表遗漏顶层目录，只收录其子项 | 先收录目录，保留 Android 目录标记；混合备份的明文计数累加 |
| 未使用线程生成的空 tar 被当成错误密码；遇到空缺线程号就终止扫描 | 接受有效空 tar，扫描并等待实际存在的线程组 |
| 分卷允许超出两位序号，路径中的 `%` 被当成格式串 | 每线程最多 00–99，共 100 卷；超过范围失败。路径作为格式参数处理 |
| waitpid 被信号打断或目标不是子进程时可能误报 | 重试 EINTR，核对 PID、退出状态与信号；无效/已回收子进程返回失败 |

tar 写出结束后会检查 close、编码器退出和输出文件 fsync；失败不会由上层发布成功 `.info`。恢复中途失败可能已经修改目标文件，不能回滚已写内容。恢复的子进程组归属复用 `BackupProcess`，但没有据此宣称完整恢复界面取消流程已完成。

### 实际执行范围

[测试驱动](../tests/archive_pipeline_test.py)编译完整生产 `twrpTar.cpp`、`tarWrite.cpp`、OAES、InfoManager、排除列表和 15 份 libtar C 源；编译仓库 pigz，链接实际 BoringSSL。TWFunc 的类型识别、密码探测、AES 包装及 wait 函数体也来自生产源码。

[46 项报告](../logs/archive-pipeline.json)全部通过。测试在独立临时 chroot 内创建源文件、归档，再删除源目录并恢复，逐字节比较内容，同时检查模式、相对符号链接和目录 `user.default` 标记。ASan/UBSan 启用；已有 libtar 扩展元数据分配清理问题另列待办，LSan 未启用。

- 普通 tar、gzip、AES、gzip+AES，分别覆盖正常文件、空归档和分卷。
- 混合明文/加密、多线程组及线程号间隙；路径含 `%`；分卷序号溢出拒绝。
- gzip CRC 损坏与截断、AES 截断、错误密码、tar 结束块后非零数据、缺失 pigz、随机源缺失或不足、源目录不存在。
- 真实子进程退出/信号/EINTR/非子进程错误；两线程交错写缓冲区；管道分段、读取中断、真实截断和无效 fd。

[旧代码对照](../logs/archive-pipeline-before.json)使用同一测试源码，46 项中 31 项失败。加密路径超时和并发缓冲区错误均作为失败保留；超时清理只通过 pidfd 定位 cwd 属于当前私有夹具的进程，不向任意主机 PID 发信号。失败用例数量不等于独立缺陷数量。

实际混合分卷回放曾暴露[短读失败](../logs/archive-pipeline-short-read-failure.json)。新增回调独立测试通过后，完整回放又发现恢复入口尚未连接回调，[失败记录](../logs/archive-pipeline-unwired-read-failure.json)保留；最终 46 项报告对应全部恢复入口已修正的源码。

### 夹具替代与尚未完成

| 边界 | 本组做法与限制 |
|---|---|
| 分区与 GUI | 临时主机目录；挂载、UI、进度接收、默认标签设置是替身，没有完整 RunBackup/RunRestore 管理器会话 |
| 分卷尺寸 | 测试阈值 64 KiB；正式配置仍为 1.5 GiB，本组未写满真实大卷 |
| 加密 | OAES/BoringSSL 在主机真实执行；不涉及 ARM64、MiTEE、FBE、RPMB 或 UFS wrapped-key |
| fscrypt | provider 返回无策略，不证明合成加密卷或实际 fscrypt 映射 |
| 随机源 | 夹具文件装入主机随机字节；缺失和短输入专门注入，不是手机熵源验证 |
| 文件属性 | 检查内容、mode、链接及 Android 目录标记；任意应用 xattr、最终目录时间、SELinux/capability 错误和稀疏空洞仍待补 |

旧 OAES CBC 格式没有认证标签。本次错误检测不等于能检测所有密文篡改，也不能证明最后一个完整分卷及其 sidecar 一同消失时仍可发现；需要另外的可信完整清单/校验设计。不能把“错误密码用例被拒绝”说成格式已经获得完整认证。

仍待补：完整管理器与 GUI 端到端、真实进度、digest sidecar 原子发布、进程死亡/断电后的整份备份完整性、完整归档路径约束、FlashImage/repacker 独立取消路径。其他分层证据见[备份会话](BACKUP-SESSION-ADAPTATION.md)、[恢复预检](RESTORE-SESSION-ADAPTATION.md)和[元数据恢复](BACKUP-DATA-PATHS.md#archive-restore)。

复现：

```bash
python3 tests/archive_pipeline_test.py
python3 tests/archive_pipeline_test.py --source backups/archive-pipeline-pre-fix --report logs/archive-pipeline-before.json
```

第二条是负向对照，预期返回非零。不得将其用作刷机或物理盘操作。

短读修正后另外重复四类加密分卷回放五轮，共 20 次通过：[第 1 轮](../logs/archive-pipeline-repeat-1.json)、[第 2 轮](../logs/archive-pipeline-repeat-2.json)、[第 3 轮](../logs/archive-pipeline-repeat-3.json)、[第 4 轮](../logs/archive-pipeline-repeat-4.json)、[第 5 轮](../logs/archive-pipeline-repeat-5.json)。

<a id="archive-restore"></a>

## 文件归档与元数据恢复

日期：2026-11-11。当前镜像与校验和见[模拟报告](../simulation-report.md)。这是备份/恢复目标中的归档层进度，完整功能验收仍在进行。

### 修复内容

[0015 补丁](../dtsrc/O1_asic_dual/0015-archive-restore-validation.patch)修改实际 `libtar/block.c`、`libtar/extract.c`：

- 硬链接目标使用独立的有界缓冲区，不再把恢复前缀写进 tar 头内存。兼容空前缀，链接创建失败返回错误；已有哈希映射的目标不重复加前缀。
- 普通文件恢复补齐短写，重试 EINTR，零字节写入按 EIO 失败。ENOSPC 和关闭失败保持失败，不能只根据读取完归档就报告成功。
- 普通恢复必须读到两个完整的全零结束块。缺失、只剩一个或块内混入非零数据均失败；显式 `TAR_IGNORE_EOT` 仍保留读到物理 EOF 的语义。
- 扩展记录按十进制字节长度解析，支持能力/加密策略中的二进制零字节；不再用 `strlen`/`strstr` 扫描整块。未知记录忽略，已知记录长度、换行、策略容器版本不合法则失败。仍只支持原实现写出的单块扩展头，未新增完整通用 PAX 支持。
- GNU 长名称和长链接增加终止字节及长度检查，修复名称恰好占满 512 字节时的越界读取。
- 已存在目录也恢复 Android `user.default`、`user.inode_cache`、`user.inode_code_cache`。缓存索引写成恢复后子目录的新 inode，不能照抄旧 inode。新目录先设置 fscrypt 策略，再创建缓存子目录。

旧实现的长硬链接用例触发 ASan 堆越界；短写用例虽然恢复返回成功，文件长度却变短。合成 v2 策略和 Android 属性共存时，旧字符串解析器漏读策略内零字节之后的属性。上述均有修改前回放，不只是源码推断。

### 回放范围与结果

[驱动脚本](../tests/archive_restore_test.py)编译 `libtar/Android.bp` 中的全部 15 个生产 C 文件，额外使用库自带 `strlcpy.c` 适配主机。使用实际 `USE_FSCRYPT` 分支和 TWRP 归档选项；主机补充标准头文件及 `__unused` 定义，没有改写归档算法。

每个用例在 `/tmp/dijun-archive-*` 的独立目录执行。夹具只接受预定义用例名，要求临时目录标记，不接受任意磁盘路径。没有挂载、格式化或写入真实分区。

[当前报告](../logs/archive-restore.json)：30 项通过；[同组旧代码报告](../logs/archive-restore-before.json)：17 项失败。报告保存生产源码、相关头文件、夹具源码和编译命令的指纹。

| 范围 | 数量 | 具体检查 |
|---|---:|---|
| 普通文件元数据往返 | 1 | 0/1/511/512/513/8193 字节，内容、mode、uid/gid、文件 mtime |
| 符号链接与硬链接 | 6 | 悬空符号链接、短/长硬链接、空前缀、目标不存在、512 字节 GNU 名称；硬链接核对实际 inode |
| 恢复写入故障 | 5 | 短写、EINTR、零写入、部分写入后 ENOSPC、close 错误 |
| 归档完整性 | 8 | 截断头/数据、缺失/单个/损坏结束块、校验和错误、有效空归档、IGNORE_EOT |
| Android 目录属性 | 4 | 新/已有目录、xattr 写失败、合成 fscrypt 策略先于缓存子目录 |
| 扩展记录解析 | 5 | 记录长度超限、截断能力/策略、缺换行、未知记录内出现已知标签文本 |
| 稀疏文件内容 | 1 | 恢复文件长度和全部内容一致；同时记录实际磁盘块数 |

ASan/UBSan 覆盖这些生产 C 源码。历史 append 扩展缓冲区所有权清理尚未完成，LeakSanitizer 未启用，不能称为内存泄漏检查通过。

文件系统、链接和 Android user xattr 为真实主机操作；故障在 write/close/setxattr 边界注入。真实 MiTEE、密钥、fscrypt ioctl 和 SELinux 强制策略未执行。唯一合成加密用例替换 vold/kernel provider，实际执行策略序列化/解析并断言设置时目录为空，不证明加密内容可恢复。

### 使用与尚未覆盖项

界面入口仍为“备份”选择存储和分区，以及“恢复”选择已有备份。Data 文件备份的媒体排除、未解密用户排除由上层控制，这次没有把那些分支视为已验证。此次修复随统一镜像提供，五份固件档案使用同一归档代码；S2 结果不是五个真实手机文件系统的测试。

本次尚未执行 `twrpTar` 的压缩、加密归档、分卷、线程/子进程与取消流程，也未执行原始分区复制、整条 GUI 备份/恢复任务。归档层中途失败不是事务回滚，已恢复的条目可能仍存在；不能把“返回错误”说成目标保持原样。

稀疏内容用例通过，但源文件 16 个 512 字节块，恢复后 2056 个块，空洞被展开。保持空洞、目录最终时间、任意应用 xattr、SELinux/capability 恢复失败传播、真实加密策略映射，以及完整不可信归档路径约束仍待补。当前结果不能据此宣称“所有元数据完全保留”。

复现命令：

```bash
python3 tests/archive_restore_test.py
python3 tests/archive_restore_test.py --source backups/archive-pre-fix/libtar --report logs/archive-restore-before.json
```

第二条用于负向对照，预期失败。源文件留档仅用于复现，正式源码由固定基线与补丁重建。

后续[46 项编解码管道回放](BACKUP-DATA-PATHS.md#archive-pipeline)真实执行了 twrpTar/pigz/OAES、普通/压缩/加密/混合分卷和字节恢复。本页 30 项元数据测试的替身范围保持不变；各层通过仍不等于完整 GUI/分区管理器会话通过。

<a id="raw-image"></a>

## 原始分区镜像备份与恢复

日期：2026-11-11。最新镜像与校验和见[模拟报告](../simulation-report.md)。本项补充[文件归档恢复](BACKUP-DATA-PATHS.md#archive-restore)，没有将整个备份、恢复或刷写功能标为完成。

### 实际修改

[0016 补丁](../dtsrc/O1_asic_dual/0016-raw-image-transfer-validation.patch)修改 `partition.cpp` 中的 `TWPartition::RawReadWrite()`，保留 `BackupImage()`、`RestoreImage()` 调用入口。

- 备份从已打开的块设备查询实际容量，复制完整分区，不以可能过时的 `backup_size_` 决定读多少字节。
- 恢复源必须是非空普通文件；目标必须是已存在的块设备。通过目标文件描述符查询容量，未知容量或镜像超限在写入和可选 discard 之前失败。缺失目标不会被创建成普通文件。
- 备份目标使用同目录唯一临时文件。完整写入、同步、检查关闭结果后，rename 提交，再同步父目录。提交前出错或可控取消时移除临时文件，并保留原有完整备份。拒绝最终目标为符号链接、非普通文件或源设备的同 inode 别名。
- 补齐短读和短写，重试 EINTR；提前 EOF、零写入、I/O 错误、ENOSPC、fsync/close/rename 错误均返回失败。可选默认权限/上下文处理仍为尽力而为，以保持不支持该元数据的存储格式行为。
- 开始前、读写之间、重试和提交前检查取消。只有数据同步、关闭及备份提交完成后才发送最后的强制进度刷新。
- 如果其他构建启用 `TW_ENABLE_BLKDISCARD`，使用已校验的同一个目标描述符，完成输入及容量检查后才尝试 discard；不支持 discard 时继续普通写入。当前 dijun 构建仍未启用此选项。

Linux 对块设备忽略 `O_TRUNC`，旧代码的这个标志不能据此解释为“物理分区立刻被截空”。问题在于旧流程没有核实目标类型，缺失/错误路径可能创建或截断普通文件。主机夹具也复现块设备忽略 O_TRUNC 的行为，避免制造不符合真实内核语义的失败。

### 生产代码回放

[驱动脚本](../tests/raw_image_test.py)从当前 checkout 提取完整 `BackupImage()`、`RestoreImage()`、`RawReadWrite()` 和实际 `CheckBackupCancel()` 函数体，编译执行；使用实际 AOSP `unique_fd` 和 `scopeguard` 头文件，启用 ASan/UBSan。

替身仅提供外围对象和系统边界：

- 一个普通临时文件由 fstat/BLKGETSIZE64 边界描述为块设备。读写、同步、关闭、临时文件和 rename 操作作用于真实主机文件。
- BLKDISCARD 只在这个普通文件上模拟，绝不调用真实块设备 ioctl。
- 分区发现、恢复文件系统类别查询、GUI 进度接收端和默认 metadata 接口是替身；没有声称运行完整 PartitionManager 或 Android 存储栈。
- write/read/fsync/close/rename 等边界注入指定错误，取消设置实际 getter 所读的 atomic 标志。
- 执行入口只接受预定义场景，要求 `/tmp/dijun-raw-*` 目录和夹具标记；生产函数取得的路径均限定在临时目录内。不接收任意磁盘路径，不挂载或写入真实分区。

[当前报告](../logs/raw-image.json)：65 项通过，其中 59 项采用当前无 discard 构建条件，6 项单独验证可选 discard 分支。[同组旧代码](../logs/raw-image-before.json)：43 项失败；这是场景数量，不是 43 个独立根因。

覆盖正常复制、无进度对象、by-name 符号链接、短读/短写、EINTR、提前 EOF、读写错误、满盘、同步/关闭错误、取消、容量未知/为零、路径缺失/类型错误、过时容量缓存、备份目标别名、提交失败以及可选 metadata 失败。

完整往返用例执行实际备份入口，改写模拟分区，再把刚生成的备份交给实际恢复入口，逐字节比较最终分区。普通恢复用例还验证较小镜像写入时，无 discard 模式保留目标尾部。

另外两个子进程中断用例：写入第一块后立即退出，确认旧备份仍完整、仅留下未提交的 `.tmp.*`；rename 后立即退出，确认新备份完整可见。这不是机器断电测试，也没有证明父目录未同步时的掉电持久性。

### 使用和边界

界面“备份”中选择原始镜像分区时走此路径；“恢复”中的 emmc 镜像恢复也使用它。普通镜像刷写可调用同一复制函数，但本次没有执行它的完整入口、槽位选择或 Android sparse 镜像分支，不能据此宣布“镜像刷写全流程通过”。

文件备份是 tar/压缩/分卷流程，与原始分区按字节复制不同；Data 文件备份不会因为此改动自动包含内部媒体或未解密用户数据。原始镜像的字节一致不证明其文件系统、密钥、槽位或系统版本可互换。

失败语义如下：

- 备份提交前失败：旧备份保留，正常返回路径清理临时文件。进程强行终止可能留下 `.tmp.*`，本轮没有新增启动清理策略。
- 备份 rename 后目录 fsync 失败：函数返回失败，但完整新备份已经可见，不能承诺旧文件仍在。
- 恢复在写入或 discard 后失败/取消：可能已改变目标内容，不能事务回滚。仅校验阶段拒绝和开始前取消保证本次没有开始修改目标。
- 取消检查不能中断一个已经阻塞在内核中的 read/write/ioctl/fsync；不是硬实时取消承诺。

备份取消/目录所有权/`.info` 顺序现由[55 项会话回放](BACKUP-SESSION-ADAPTATION.md)覆盖。仍待补：完整归档进度、digest 原子发布、强杀/断电完整性、完整管理器归档流程、稀疏文件空洞、真实块设备语义、LP/A-B 路由及合成加密卷。当前 S2 结果属于五档案共享的复制代码，不是五个版本的实机恢复结果。

复现：

```bash
python3 tests/raw_image_test.py
python3 tests/raw_image_test.py --source backups/raw-image-pre-fix/partition.cpp --report logs/raw-image-before.json
```

第二条是负向对照，预期失败。物理震动、TEE 和真实手机读写仍保持未验证。

后续恢复 manager 预检另有[54 项回放](RESTORE-SESSION-ADAPTATION.md)：会话入口清除旧取消、固定父子目标清单、预先检查全部已选镜像容量与 digest，再进入本页的原始复制。完整管理器归档端到端和 FlashImage/repacker 独立入口仍未完成；压缩/加密分卷另由[46 项管道回放](BACKUP-DATA-PATHS.md#archive-pipeline)覆盖。
