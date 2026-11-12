# 备份会话、目录管理与摘要发布

2026-11-12 补充：独立digest sidecar原子发布现由维护补丁0046实现；补丁0047增加新备份INCOMPLETE/COMPLETE文件清单以及恢复枚举/写入前校验。17项manifest检查、RunBackup55项、RunRestore56项通过；旧版无清单备份仍按legacy接受，不宣称有完整性证明。新镜像、构建和同镜像检查见[任务进度](../ADAPTATION-GOALS.md)。原始archive编码/真实断电和文件系统耐久性仍未验证。

以下会话检查记录对应 2026-11-11 阶段；后续修正见本文各小节，历史未完成描述不覆盖后续交付。实现位于设备树固定补丁 [0019](../dtsrc/O1_asic_dual/0019-backup-session-cancellation.patch)。当前镜像、哈希与构建证据见[模拟报告](../simulation-report.md)。本轮没有连接手机。

备份取消不再直接使用一个可能为 `-1`、已回收或属于旧任务的 PID。新的 `BackupProcess` 在互斥锁内建立并登记私有进程组；取消只向仍由当前备份拥有的组发信号。备份线程负责读管道、等待退出、回收 leader 并清除 PID。leader 保持未回收状态直到组信号发出，避免回收后 PID 被复用。失败或取消的压缩/加密 helper 也随组终止，取消线程不再循环等待 `kill(pid, 0)`。

管道读取支持碎片和 EINTR；截断记录作为失败处理。轮询也检查 leader 是否异常退出，终止其遗留 helper，使 helper 持有管道的情况能够收尾。`waitid(WNOWAIT)` 用于保留进程归属，`waitpid` 回收只由备份线程执行。这要求其子进程不被其他全局 reaper 偷先回收；没有引入 Android init 替代测试。

`.info` 在进度头完整、tar 子进程成功退出且未取消之后才写入；保存失败传回调用者。写入使用已有的实际 `InfoManager::SaveValues` 临时文件、同步和 rename 实现。没有把“管道关闭”当成“备份成功”。

备份管理器的其他修正：

- 在已有存储事务锁下生成去重的父/子分区计划，未知、不可备份或明确选择但缺失的目标直接失败；隐式缺失子分区不会被执行。
- 先测量文件备份源，检查总量溢出和 32 MiB 余量；小于余量的空闲空间不再发生无符号减法下溢。
- 最终名称必须有效；以 `mkdir` 原子创建新叶目录，已有目录和符号链接均拒绝。未解密 userdata 不妨碍另一个可访问存储上的目标目录创建。
- 失败或取消后，只有备份线程清理它捕获的目录；清理前核对目录设备号/inode，避免按界面已经更改的名称删除另一份备份。完整目录删除包括 `.win100` 等分卷。
- 每个分区备份后、digest 后及最终收尾再次检查取消；失败不会发出 `backup_completed`。临时进度和性能状态有作用域收尾。
- GUI 在公开运行状态之前清除旧取消标志，后台入口保留随后提交的取消。开始下一次任务前先 join 上次取消线程；销毁 backend 会发取消再 join。终态和 `running=false` 在同一状态锁内发布。
- 脚本同步入口默认开启新会话并清除旧标志；repacker 的调用类型同步更新，但本轮没有模拟完整 repack。

## 离线证据

[测试驱动](../tests/backup_session_test.py)与[夹具](../tests/backup_session_test.cpp)执行实际 `RunBackup`、`BackupPartition`、取消、名称验证、完整 `createTarFork` 函数体、`BackupProcess`、`InfoManager::SaveValues`，以及 GUI backend 的 start/run/cancel/status/acknowledge/destructor。

[55 项结果](../logs/backup-session.json)全部通过；[同组旧源码对照](../logs/backup-session-before.json)有 35 项失败。这些是失败场景数量，包含同一缺陷的多种入口，不是 35 个独立硬件缺陷。

覆盖普通/重复/父子/无结尾分号选择、未知与缺失目标、测量失败、容量下溢/溢出、已有目录和符号链接、第一/最后分区失败或取消、digest 失败/取消、收尾取消、目录被替换、加密状态下的外部目标；tar fork 失败、提前取消、重复取消、group/helper 终止、leader 崩溃、回收后取消、下一次备份、管道碎片/截断、wait EINTR、`.info` 创建/同步失败，以及 GUI 提前取消、退出、重新开始和重复启动。

进程、信号、管道、临时目录、`.info` 序列化与文件同步是在主机上真实执行的。ASan/UBSan 启用。信号包装器拒绝测试不拥有的 ID；负向对照超时后，测试驱动以 pidfd 只清理 cwd 属于本次私有夹具的进程，并回收被收养的 helper。不会向 `kill(-1)` 或主机任意 PID 发送真实信号。

分区挂载、archive 编码器、digest 生成入口、GUI 消息和进度显示是边界替身。`createTarFork` 的未加密分支实际运行，压缩/加密算法、加密线程的归档内容未在本组执行；真实 digest 已由独立[恢复会话测试](RESTORE-SESSION-ADAPTATION.md)覆盖。不能把各层分开通过表述成完整归档端到端通过。最终镜像策略另行查询 `recovery → recovery` 的 `setpgid/sigkill/sigchld`，三项允许；与原九项策略用例合为[12 项](../logs/backup-session-policy-regression.json)。

## 保留边界

- 内核不可中断 I/O 不能靠信号强制即时终止；取消入口返回不等于所有设备写入已完成。界面等待工作线程收尾。
- recovery 进程被强杀、主机掉电、目录删除失败可能留下不完整目录；后续 0047 已增加完成标记与分卷校验，仍不保证断电原子提交。目录 inode 检查不抵御所有检查之后的外部路径替换。
- tar/pigz/OAES 内容往返另由[编解码管道 46 项](ARCHIVE-PIPELINE-ADAPTATION.md)覆盖；完整管理器流程、稀疏空洞、真实进度条和可信卷清单/卷尾缺失检测仍待补；digest sidecar独立原子提交已由后续0046及独立真实文件检查覆盖，不等于整份备份原子提交。
- 同步内核写入失败可能形成部分恢复；本次不会回滚已写分区。FlashImage/repacker 独立入口的取消残留仍待审计。
- 本组会话检查不证明手机外设效果；震动已由用户确认正常，不属于当前待办。

## 备份目录重命名与删除（0067）

工具 worker 原来拼接 `cd … && mv …` / `rm -rf …`。已有备份目录可从电脑导入，名称不受重命名输入框的字符限制；名称及备份根路径中的 `$()` 会被 shell 展开。重命名目标在前端检查后被创建时，`mv` 还可能把原备份移入目标目录并报告成功。旧实现只取 target 的 basename，未确认其属于当前备份根。

[0067 固定补丁](../dtsrc/O1_asic_dual/patches/0067-backup-folder-literal-operations.patch) 在共用存储操作锁内验证目标为当前根的直接子目录，拒绝目录符号链接、无效新名称及缺失目标。打开父目录后，重命名使用 `renameat2(RENAME_NOREPLACE)`，不覆盖或移入已有目标；删除通过父 fd 锚定路径调用原 `TWFunc::RemoveDir`。不再将备份名称送入 shell。内核不支持 no-replace 时明确失败，不退回覆盖式 rename。

`python3 tests/backup_manage_test.py` 执行生产 start/run/status/acknowledge/join、实际线程、文件 API 和原 RemoveDir；DataManager、操作展示及未调用工具为明确边界。12 场景通过，原实现同组 8 场景失败：普通与特殊名称/根路径、不同父目录、目标已存在、越界名称、目录链接、删除、源缺失和 worker 复用。仅操作私有临时普通文件。共享 worker 的刷新页面生命周期另有三种调度通过，包括八次重入，没有复现或修复用户的刷新卡住现场。

候选 `recovery-dijun-unified-backup-manage.img`，SHA-256 `ecdab5945ca529e3b20049e79ea8799f18292c9b4883f6210055719be6527fe4`；installclean 后 `make -j$(nproc)` 30 并发构建，780 份生产来源和六份 profile 核对。相对 snapshot-map 只有 Recovery 主程序、构建属性与文件摘要变化。审计入口 `python3 scripts/audit_backup_manage_delivery.py`。

范围限制：这是目录管理修复，不是完整备份/恢复或断电持久性验收。父 fd 防止根路径变化重定向，但不承诺消除外部并发替换子目录的全部竞争。删除中途失败可能已移除部分内容；不承诺回滚，也不改变其他命令工具或 TWRP 根目录改名入口。

<a id="digest-publication"></a>

## 摘要文件原子发布（0046）

[0046 固定补丁](../dtsrc/O1_asic_dual/patches/0046-atomic-backup-digests.patch)避免截断正式 `.sha2` / `.md5` 后写入失败破坏原摘要。仍使用真实流式 BoringSSL MD5 / SHA-256，保持 `<hex>  <basename>\n` 格式和原有使用入口。

1. 在同目录创建唯一 `.twrp-digest.XXXXXX` 临时文件并设置 CLOEXEC；固定短名称避免合法长目标名超出 NAME_MAX。
2. 处理短写、EINTR 和零写，沿用尽力设置 Android 元数据的策略，检查文件同步及关闭。不重试失败的 close，避免误关已复用的 fd。
3. 前序成功才 rename 替换并同步目录。发布前失败保留旧摘要并清理临时文件；正式摘要为符号链接时替换链接本身。
4. rename 后目录同步失败返回 false，并记录 `Digest replaced but directory sync failed`。完整新文件已可见，不能声称回退到旧文件。
5. 错误传回 `MakeDigest` 和 `BackupPartition`，性能状态按作用域收尾；摘要失败或之后取消不能让分区备份返回成功。

临时文件不作为摘要或 archive part 读取。进程退出仍可能留下临时文件，没有自动清理；多卷逐文件发布，后一卷失败不回滚前卷。这不是整份备份的原子提交。后续 0047 的完成清单与恢复预检独立生效，完整 archive 持久性和断电恢复仍未验收。

`tests/digest_publication_test.py` 编译完整生产 digest driver / TwrpDigest，并接入原 `BackupPartition` 方法；实际执行 BoringSSL、普通文件、rename、fork 与进程退出，启用 ASan / UBSan。Python hashlib 独立给出两种算法预期，输入跨越 256 KiB 读取块。

54 项通过，旧实现同组 44 项失败。覆盖新建 / 覆盖、长名称、短写 / EINTR / 零写 / ENOSPC、创建 / 打开 / 同步 / 关闭 / rename 失败、链接与目录目标、源缺失、重试和分卷。三个进程退出边界检查发布前后可见内容，不能模拟突然掉电。恢复 54 项及备份会话 55 项为当时的相关回归；挂载、archive 创建、Android 元数据及 GUI 仍是边界，不可拼接为完整端到端验收。

```bash
python3 tests/digest_publication_test.py --output logs/digest-publication.json
python3 tests/digest_publication_test.py --source backups/digest-atomic-pre-fix/digest --output logs/digest-publication-before.json
python3 tests/restore_session_test.py --report logs/digest-atomic-restore.json
python3 tests/backup_session_test.py --report logs/digest-atomic-backup.json
python3 scripts/audit_digest_publication_delivery.py
```

负向对照预期非零，依赖本地旧源码。历史构建及来源哈希见本地 `logs/digest-atomic-delivery.json` 与机器索引；本文合并不改写旧证据。
