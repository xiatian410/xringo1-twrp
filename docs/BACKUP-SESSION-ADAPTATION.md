# 备份会话、取消和 tar 子进程

2026-11-12 补充：独立digest sidecar原子发布现由维护补丁0046实现；补丁0047增加新备份INCOMPLETE/COMPLETE文件清单以及恢复枚举/写入前校验。17项manifest检查、RunBackup55项、RunRestore56项通过；旧版无清单备份仍按legacy接受，不宣称有完整性证明。新镜像、构建和同镜像检查见[任务进度](../ADAPTATION-GOALS.md)。原始archive编码/真实断电和文件系统耐久性仍未验证。

日期：2026-11-11。实现位于设备树固定补丁 [0019](../dtsrc/O1_asic_dual/0019-backup-session-cancellation.patch)。当前镜像、哈希与构建证据见[模拟报告](../simulation-report.md)。本轮没有连接手机。

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
- recovery 进程被强杀、主机掉电、目录删除失败可能留下不完整目录；目前没有整份备份完成标记/可信分卷清单，也不保证断电原子提交。目录 inode 检查不抵御所有检查之后的外部路径替换。
- tar/pigz/OAES 内容往返另由[编解码管道 46 项](ARCHIVE-PIPELINE-ADAPTATION.md)覆盖；完整管理器流程、稀疏空洞、真实进度条和可信卷清单/卷尾缺失检测仍待补；digest sidecar独立原子提交已由后续0046及独立真实文件检查覆盖，不等于整份备份原子提交。
- 同步内核写入失败可能形成部分恢复；本次不会回滚已写分区。FlashImage/repacker 独立入口的取消残留仍待审计。
- 震动物理效果和所有手机外设继续标为 U；本次不声称改善了电机硬件表现。
