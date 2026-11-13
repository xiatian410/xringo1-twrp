# 备份会话、目录管理与摘要发布

<a id="exclusion-union"></a>

## 重复及嵌套排除容量（0112）

Data初始化的ExcludeAll与后续SetupDataMedia会重复登记cache/per_boot/gsi；未解密用户媒体目录也可能与/data/media重叠。此前容量统计逐项相加，同一内容被重复扣除。0112只在容量统计的局部副本排序去重，并跳过已计量真实目录的后代；匹配要求路径组件边界，sub不覆盖submarine。原始登记列表和备份/清除匹配行为不变。lstat识别目录，链接不作为覆盖其他路径的目录，也不解析链接别名。

扩展既有容量测试至19项，真实私有文件/完整exclude源码/ASan及UBSan全部通过；同夹具旧实现7/19失败。新增覆盖重复文件、重复目录、父子登记的两种顺序、三级嵌套、相似前缀兄弟目录、多用户媒体重叠及规范化后重复路径。4097字节文件原先可被计成8194或12291，现在只计一次；保留原11项文件/链接/取消检查。既有普通/gzip/AES/组合与分卷八项往返通过，不重复无关套件。

本地报告`logs/exclusion-union.json`、`logs/exclusion-union-old.json`、`logs/exclusion-union-codec.json`；交付审计`python3 scripts/audit_exclusion_union.py`绑定0112与清理构建、840来源和六profile。容量仍为逻辑字节估计；I/O错误、路径别名/并发替换、分配块及完整manager/GUI仍有边界。此项不解释现场DRM等待，不重跑未改OTA或已解决功能。

<a id="exclusion-capacity"></a>

## 排除项容量（0110）

容量扫描此前仅在目录分支检查排除策略，导致绝对排除的普通文件（包括设备树声明的`/data/adb/ksu/modules.img`）仍计入备份大小；排除容量统计又只尝试opendir文件，得到零。链接还可能被位掩码误判为目录并跟随目标。0110在访问条目前应用排除策略，使用S_ISDIR/S_ISREG/S_ISLNK分类；绝对排除项先lstat，普通文件与链接计入自身st_size，目录才递归。悬空链接也可计量，缺失路径及取消仍返回零。

完整exclude源码在私有主机文件上执行，保留原路径规范化方法，仅日志和include边界为替身。ASan/UBSan下11项覆盖普通文件、绝对文件/目录、文件/目录/悬空链接、相对文件/目录、尾斜杠、缺失路径及取消，源文件内容保持；同测试旧实现6/11失败。既有tar/pigz/OAES链定向执行普通、gzip、AES、组合编码与四种分卷八项往返通过，不重复无关故障套件。

本地报告`logs/exclusion-size.json`、`logs/exclusion-size-old.json`、`logs/exclusion-size-codec.json`；交付审计`python3 scripts/audit_exclusion_capacity.py`核对0110、清理构建、838来源和六profile。容量仍是逻辑字节估计，读取错误未显式失败、重叠排除项可能重复、稀疏分配和并发变化仍有局限；没有完整manager/挂载/fscrypt/GUI验证。此修正不解释现场显示提交卡住，也未重跑完整OTA。

<a id="source-type-classification"></a>

## 源类型与属性读取（0108）

普通递归列表及加密路径两次顶层扫描此前仅按dirent.d_type判断；文件系统允许返回DT_UNKNOWN，此时条目不进入文件/目录列表。对普通文件的stat也未检查返回值，可能沿用旧st_size。0108在排除项检查后使用检查返回值的lstat分类与计量，未知d_type仍能识别真实类型；链接保留自身类型，不跟随目录链接或悬空目标。属性错误立即失败并关闭目录，最终父进程不发布data.info。没有为消失的文件忽略错误。

在现有tar/pigz/OAES/fork套件增加32场景：普通/gzip/AES/混合编码与userdata_encryption路径，顶层/嵌套DT_UNKNOWN、嵌套属性EIO/ENOENT、加密两次顶层属性失败。当前216项通过；旧源码同32项全部失败。DT_UNKNOWN仅在readdir边界修改返回类型，真实文件/目录/链接/归档与恢复仍执行；stat故障限私有源路径与指定扫描阶段，容量预估及实际归档读取不注入。成功要求内容/权限/链接/排除往返，失败要求父进程错误、无.info和目录open/close计数相等。

本地报告`logs/archive-types-pipeline.json`、`logs/archive-types-negative.json`及`logs/archive-types-delivery-audit.json`。libtar未改，沿用0107的独立111项证据；完整编码回归包含该库。容量预估仍是近似值，未覆盖真实fscrypt/ARM64 codec、属性检查后的并发替换、挂载根/完整manager/GUI或断电。不把此修正称为源文件快照一致性保证。

```bash
# 已执行；相关来源与输入不变时复用。
python3 tests/archive_pipeline_test.py --report logs/archive-types-pipeline.json
python3 scripts/audit_archive_walk_delivery.py --source-types
```

<a id="directory-enumeration-errors"></a>

## 目录读取失败必须终止备份（0107）

此前readdir返回空时未区分EOF与错误，可能只收集部分文件却发布成功备份。0107在每次读取前清除errno，正常结束后检查读取及closedir结果；普通递归列表、加密路径的两次顶层扫描和libtar递归树入口均传播错误。递归子目录失败时关闭上层目录，libtar保留首个错误的errno。父进程收到失败，不发布data.info；已有部分输出不代表完整归档。

在现有套件内扩展故障场景，未新增等价测试框架。libtar111项、tar/pigz/OAES/fork链184项通过。旧源码同夹具3/4及21/32失败：读取/关闭错误可误报成功，普通递归打开失败漏关上层目录。旧加密顶层第一次读取失败有时本就因后续线程规划失败，保留为控制，不称为新修复。正常EOF夹具在每个成功读取后留下EIO，仍必须完成内容/权限/链接往返；故障夹具核对所有已打开目录均关闭、父失败且无data.info。

本地报告`logs/archive-walk-restore.json`、`logs/archive-walk-negative.json`、`logs/archive-walk-pipeline.json`、`logs/archive-walk-pipeline-negative-final.json`及`logs/archive-walk-delivery-audit.json`。原生产代码在主机ASan/UBSan运行，目录open/read/close错误由私有夹具边界注入，LSan仍关闭。未验证真实损坏文件系统、fscrypt、ARM64 codec、完整manager/GUI或断电；容量估计API、DT_UNKNOWN条目与并发源一致性没有在此修正。

```bash
# 已执行；相关来源和输入不变时复用。
python3 tests/archive_restore_test.py --report logs/archive-walk-restore.json
python3 tests/archive_pipeline_test.py --report logs/archive-walk-pipeline.json
python3 scripts/audit_archive_walk_delivery.py
```

<a id="source-key-failure"></a>

## 源文件缺密钥时不得跳过成功（0106）

此前`tar_append_file`对所有条目先做一次多余的open探测。遇到ENOKEY直接返回0，既不写该条目也不报告失败；普通文件（包括空文件）会被静默漏备份。对链接做同样探测还会因目标不可打开而漏掉本来无需读取目标内容的符号链接/硬链接。

0106移除这次探测。普通文件仍由原`tar_append_regfile`实际打开读取，ENOKEY/EKEYREVOKED/EACCES按失败传回，父进程不发布.info；链接保留原readlink/已归档inode记录与header，恢复链接元数据。此修正不会解锁文件或补齐缺失密钥，备份失败的部分输出不能视为完整归档。

libtar107项、完整tar/pigz/OAES/fork编码链152项通过。同组旧源码新增六项有四项失败：有内容/空文件ENOKEY静默漏备份，以及链接探测导致漏条目；撤销密钥/权限拒绝原本就能失败，是保留控制。编码链四模式各覆盖ENOKEY/EKEYREVOKED/EACCES，旧4/12失败。普通文件核对原errno和父进程失败/无data.info，符号链接核对恢复后的悬空目标，硬链接核对相同inode与内容。相关报告为`logs/archive-key-restore.json`、`logs/archive-key-negative.json`、`logs/archive-key-pipeline.json`、`logs/archive-key-pipeline-negative.json`、`logs/archive-key-delivery-audit.json`。

打开错误仅在私有夹具指定源路径注入，不代表真实fscrypt/TEE；没有全manager/GUI、ARM64 codec、并发源快照或断电验证。必要回归通过即收尾，不为相同实现重复这组检查。

```bash
# 已执行，来源和输入不变时复用。
python3 tests/archive_restore_test.py --report logs/archive-key-restore.json
python3 tests/archive_pipeline_test.py --report logs/archive-key-pipeline.json
python3 scripts/audit_archive_key_delivery.py
```

<a id="source-read-completion"></a>

## 源文件读取完整性（0105）

`tar_append_regfile`的最后一块原先仅检查`read == -1`。若文件在header的stat之后缩短，成功短读或EOF仍被当成已读足；未读到的缓冲区字节会进入归档，父进程可能发布成功信息。0105统一每块的精确读取：保留累积字节，短读和EINTR继续，提前EOF设为EIO，读取错误立即传回原addFile/tar线程/createTarFork，父进程不发布.info。没有用补零掩盖源读取失败，也不宣称完整并发快照一致性；文件增长、同长修改或头部/打开间身份替换仍有边界。

现有libtar套件101项、tar/pigz/OAES/fork套件140项通过。新增libtar12场景覆盖0/1/511/512/513/1024边界、17字节短读、单次EINTR、511/512/513大小的真实truncate和末块EIO；成功必须按内容/权限/时间往返一致，失败核对返回值与errno。旧源码5/12失败。编码链四模式（普通、gzip、AES、两者）各覆盖EOF、短读、EINTR、EIO，共16项；旧12/16失败。EOF在已完成header的源read边界实际截短文件；其他read故障由syscall wrapper注入。失败必须到达父进程且无data.info，成功恢复逐文件核对内容。

本地报告`logs/archive-read-restore.json`、`logs/archive-read-negative.json`、`logs/archive-read-pipeline.json`、`logs/archive-read-pipeline-negative.json`与`logs/archive-read-delivery-audit.json`。生产代码在主机ASan/UBSan执行，使用私有普通文件；Android界面/进度、fscrypt provider和少量libbase接口为替身，codec非ARM64，未覆盖真实manager/GUI/块I/O或断电。来源未变时复用这组结果，不例行重跑。

```bash
# 已执行，来源和输入不变时复用。
python3 tests/archive_restore_test.py --report logs/archive-read-restore.json
python3 tests/archive_pipeline_test.py --report logs/archive-read-pipeline.json
python3 scripts/audit_archive_read_delivery.py
```

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
- tar/pigz/OAES 内容往返另由[编解码管道 46 项](BACKUP-DATA-PATHS.md#archive-pipeline)覆盖；完整管理器流程、稀疏空洞、真实进度条和可信卷清单/卷尾缺失检测仍待补；digest sidecar独立原子提交已由后续0046及独立真实文件检查覆盖，不等于整份备份原子提交。
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
