# 原始分区镜像备份与恢复的离线验证

日期：2026-11-11。最新镜像与校验和见[模拟报告](../simulation-report.md)。本项补充[文件归档恢复](ARCHIVE-RESTORE-ADAPTATION.md)，没有将整个备份、恢复或刷写功能标为完成。

## 实际修改

[0016 补丁](../dtsrc/O1_asic_dual/0016-raw-image-transfer-validation.patch)修改 `partition.cpp` 中的 `TWPartition::RawReadWrite()`，保留 `BackupImage()`、`RestoreImage()` 调用入口。

- 备份从已打开的块设备查询实际容量，复制完整分区，不以可能过时的 `backup_size_` 决定读多少字节。
- 恢复源必须是非空普通文件；目标必须是已存在的块设备。通过目标文件描述符查询容量，未知容量或镜像超限在写入和可选 discard 之前失败。缺失目标不会被创建成普通文件。
- 备份目标使用同目录唯一临时文件。完整写入、同步、检查关闭结果后，rename 提交，再同步父目录。提交前出错或可控取消时移除临时文件，并保留原有完整备份。拒绝最终目标为符号链接、非普通文件或源设备的同 inode 别名。
- 补齐短读和短写，重试 EINTR；提前 EOF、零写入、I/O 错误、ENOSPC、fsync/close/rename 错误均返回失败。可选默认权限/上下文处理仍为尽力而为，以保持不支持该元数据的存储格式行为。
- 开始前、读写之间、重试和提交前检查取消。只有数据同步、关闭及备份提交完成后才发送最后的强制进度刷新。
- 如果其他构建启用 `TW_ENABLE_BLKDISCARD`，使用已校验的同一个目标描述符，完成输入及容量检查后才尝试 discard；不支持 discard 时继续普通写入。当前 dijun 构建仍未启用此选项。

Linux 对块设备忽略 `O_TRUNC`，旧代码的这个标志不能据此解释为“物理分区立刻被截空”。问题在于旧流程没有核实目标类型，缺失/错误路径可能创建或截断普通文件。主机夹具也复现块设备忽略 O_TRUNC 的行为，避免制造不符合真实内核语义的失败。

## 生产代码回放

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

## 使用和边界

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

后续恢复 manager 预检另有[54 项回放](RESTORE-SESSION-ADAPTATION.md)：会话入口清除旧取消、固定父子目标清单、预先检查全部已选镜像容量与 digest，再进入本页的原始复制。完整管理器归档端到端和 FlashImage/repacker 独立入口仍未完成；压缩/加密分卷另由[46 项管道回放](ARCHIVE-PIPELINE-ADAPTATION.md)覆盖。
