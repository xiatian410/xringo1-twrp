# 分区界面修正：镜像目标与 NV 操作

<a id="ors-deferred-reboot"></a>
## ORS 重启请求与统一收尾（0135）

原脚本`reboot`与启动action成功路径直接调用TwReboot，绕过GUI后台任务收尾；显式重启调用若返回，还会继续执行后续命令。直接解析器也没有关机预约准入票。

[0135补丁](../dtsrc/O1_asic_dual/patches/0135-ors-deferred-reboot.patch)将重启变为待处理请求：显式命令停止解析，真实脚本关闭成功后才入队；关闭失败不会发布。启动action识别专用返回值，不执行后续缓存脚本，也不覆盖显式目标为system。普通脚本全部成功时只提交system请求。支持system/recovery/poweroff/bootloader/download/edl/fastboot；空参数仍为system，未知参数改为明确失败，避免误重启系统。

原GUI外部重启消费器读取队列，通过现有`request_reboot`执行存储锁、能力检查、关机预约和目标写入；失败保留请求供下次轮询。解析器和启动action各持有真实executor票，正在执行或尚未返回时阻止关机预约，预约成功后拒绝直接脚本新任务。启动流程发现待处理请求后跳过后续服务/只读提示，正常完成startup worker后才由GUI消费；此处连接经静态检查，未执行完整startup。

复用ORS检查器新增`--reboot`：七目标、默认目标、自动请求、显式启动请求保留缓存、无效目标、已预约拒绝、写失败/忙/能力失败后重试、关闭失败共16项通过。同夹具旧版16项失败。执行原队列/完整解析器/action/GUI消费方法和真实executor；私有脚本、ASan/UBSan，配置/能力/sync/minadbd空队列/最终重启为替身；关闭失败在真实关闭后注入。相关输入28、命令58、缺参20、顺序9和侧载重启23项通过；旧报告保持原字节，不刷新历史结果。

有限重启交接修正至此收尾。未证明完整GUI/FIFO状态、任意终端后代、进程级停止、并发脚本暂存隔离、USB关闭、物理重启或OTA启动合并；完整OTA沿用已有原包模型结果。

```bash
python3 tests/ors_results_test.py --reboot --report logs/ors-reboot-current.json
python3 scripts/audit_ors_results.py --reboot
```

本地报告为`logs/ors-reboot-{current,old,input,commands,arguments,sequence,sideload}.json`与`logs/ors-reboot-delivery-audit.json`。本批最终镜像及哈希见[交付报告](../simulation-report.md)。

<a id="ors-input-boundaries"></a>
## ORS 读取错误和超长命令（0134）

原解析器把`fgets`失败都视为EOF，并忽略`fclose`失败；读取脚本目录或发生EIO时可能返回成功，启动action还会自动重启。固定缓冲区读不下一整行时，会先执行被截断的命令，再把剩余内容当作下一条命令。

[0134补丁](../dtsrc/O1_asic_dual/patches/0134-ors-input-error-boundaries.patch)在执行前及循环结束后检查流错误，关闭失败也传回失败。达到511字节命令上限时，先检查下一字节为换行或EOF才执行，否则整行失败且不执行截断前缀。合法上限、末行无换行、空文件与空行保留。已有操作不回滚；不是物理I/O超时或完整ORS关机准入修正。

复用原解析器/action检查器的`--input`模式共28项：原私有文件/目录，`fopencookie`向真实stdio注入首读、部分命令、完整命令之后和上限探测EIO，真实关闭后注入关闭返回错误；检查超长首行及前一命令成功后的失败，另有12项正常边界控制。当前全通过；同夹具旧版16个错误场景全失败，含自动重启和截断前缀执行。原命令58、缺参20、启动顺序9因解析器变更复查通过，此项有限收尾。

检查使用ASan/UBSan；manager、shell、配置、console、sleep与最终重启为替身，没有实际设备操作、完整GUI/FIFO退出码、物理I/O时限、并发路径稳定性或回滚保证。旧版故障进程各用独立目录，避免失败遗留污染后续控制场景。完整OTA沿用既有原包模型结果。

```bash
python3 tests/ors_results_test.py --input --report logs/ors-input-current.json
python3 scripts/audit_ors_results.py --input
```

本地报告为`logs/ors-input-{current,old,commands,arguments,sequence}.json`与`logs/ors-input-delivery-audit.json`。当前镜像见[交付报告](../simulation-report.md)。

<a id="ors-missing-arguments"></a>
## ORS 缺少参数时停止解析（0133）

原解析器遇到没有选项的`backup`或没有名称的`set`时，把`strtok`的空结果交给`strcpy`，会使Recovery进程崩溃。仅含多个空格的参数还可能把残留换行识别成选项/名称，继续执行后续命令，并在启动入口自动重启。

[0133补丁](../dtsrc/O1_asic_dual/patches/0133-ors-missing-arguments.patch)在这两处复制前检查参数，并把空格、制表符和换行作为分隔符。缺少参数返回失败，复用原循环结束、关闭并删除临时脚本；启动action不会自动重启。正常备份选项、显式备份名、设置空值及设置普通值保留。

复用原ORS检查器新增`--arguments`模式，执行完整原解析器/action和私有脚本，直接/启动入口共20项通过。相同夹具旧版12项失败：8项被ASan/UBSan捕获为空指针崩溃，4项空白参数继续执行，其中启动入口自动重启。原命令58项和启动顺序9项因解析器变更复查通过，此批到此收尾。

分区操作、备份执行、配置、console、sleep及最终重启为替身；不代表真实备份、完整GUI/FIFO退出码、直接ORS关机准入或设备重启验收。未改准入架构，未重跑完整OTA及震动。

```bash
python3 tests/ors_results_test.py --arguments --report logs/ors-arguments-current.json
python3 scripts/audit_ors_results.py --arguments
```

本地报告为`logs/ors-arguments-{current,old,commands,sequence}.json`与`logs/ors-arguments-delivery-audit.json`。当前镜像见[交付报告](../simulation-report.md)。

<a id="aux-wipe-results"></a>
## 电池统计与 Android Secure 清除结果（0132）

电池统计清除原先先探测文件存在，再忽略`remove`结果；权限不足或路径类型错误会误报成功。Android Secure 清除遍历多个存储时，用最后一次结果覆盖先前失败，也会在失败后继续下一个目标。

[0132补丁](../dtsrc/O1_asic_dual/patches/0132-aux-wipe-failure-propagation.patch)直接检查电池统计文件的`unlink`结果：不存在仍算成功，其他错误返回失败且不打印已清除。删除链接仅删除链接本身。Android Secure 任一目标失败立即停止，并将失败传回原后台操作的终态；全部成功和没有目标的既有语义保留。已经删除的内容不回滚。

`tests/aux_wipe_test.py`执行原manager、`WipeAndSec`、`RemoveDir`及后台`run`，使用私有chroot文件、uid65534和真实目录权限错误，覆盖普通成功、不存在、删除/查找拒绝、目录误作文件、链接、挂载拒绝、多目标失败以及LIST入口，共15项。修正版全通过；相同夹具旧版7项失败，其中5项误报成功，另2项虽返回失败却仍继续下一目标。

挂载、配置、console、executor及其他manager路由为显式替身。没有执行完整GUI/start/thread、真实挂载、fscrypt、物理I/O或并发路径替换；不是完整文件系统生命周期验收。完整OTA沿用既有原包模型结果，不重跑震动或无关功能。

```bash
python3 tests/aux_wipe_test.py
python3 scripts/audit_aux_wipe.py
```

本地证据为`logs/aux-wipe-current.json`、`logs/aux-wipe-old.json`和`logs/aux-wipe-delivery-audit.json`。镜像与构建来源见[交付报告](../simulation-report.md)。

<a id="ors-staging-errors"></a>
## 脚本暂存失败保留原文件（0130）

`check_for_script_file`和`copy_script_file`原先忽略`TWFunc::CopyFile`结果，无论复制是否成功都删除源脚本并报告成功。目标写入/权限设置失败时可能丢失源文件；源删除失败时仍可能执行副本并自动重启，下次启动又重复执行源脚本。

[0130补丁](../dtsrc/O1_asic_dual/patches/0130-ors-staging-error-propagation.patch)检查复制和源删除结果，失败时保留源文件、尝试删除本次临时副本，并返回失败。缓存检查区分未发现（0）、已暂存（1）和暂存失败（-1）；启动action收到负值即结束，不执行副本或自动重启，即使之前的临时脚本已成功。CLI复制函数保留原0失败/1成功协议，源已是临时路径的快捷分支不变。缓存挂载失败沿用原未发现行为，本批未改动该策略。

同一`tests/ors_results_test.py --staging`复用完整原检查/复制/解析器/action，并执行原`TWFunc::CopyFile`。23个场景使用独立私有目录，覆盖正常、源不存在、已位于临时路径、目标被目录占据、chmod失败、源unlink失败、挂载失败，以及前一脚本成功后的缓存处理。修正版全部通过，同夹具旧版11项失败；顺序九项和单脚本58项通过。源文件内容逐字节比较，成功副本也读回确认。

挂载、chmod/unlink故障、配置、shell及最终重启为显式替身，其余复制/权限正常路径和私有文件真实执行。不是断电持久性、路径竞争、原子事务、完整CLI/GUI或真实启动验收。临时副本清理是尽力操作，不能保证不可删除对象被移除。首次对照用例因断言失败未清理残留而污染后续用例，已将每个场景隔离目录，首次结果保留但不作为统计。

本地最终报告：`logs/ors-staging-current.json`、`logs/ors-staging-old.json`、`logs/ors-staging-sequence.json`、`logs/ors-staging-commands.json`。交付核对：`python3 scripts/audit_ors_results.py --staging`。当前镜像见[交付报告](../simulation-report.md)，不重复完整OTA或无关功能检查。

<a id="ors-startup-sequence"></a>
## 多份启动脚本的失败处理（0129）

启动action依次处理临时转换脚本和缓存ORS。0128已将单份脚本内操作失败传回解析器，但action仍分别记录成功：第一份成功、第二份失败时仍自动重启；第一份失败时仍消费并执行第二份，其成功还会覆盖前一次失败状态。

[0129补丁](../dtsrc/O1_asic_dual/patches/0129-ors-startup-sequence-failure.patch)让action在任一脚本失败时设置结束页并返回失败。第一份失败不再检查/移动缓存脚本，留待后续明确处理；两份均成功仍保留自动重启，没有脚本时仍返回未执行。已完成的操作不回滚；不是新的关机准入或事务协议。

`tests/ors_results_test.py --sequence`执行完整原解析器和启动action，临时/缓存各取不存在、成功、失败，共九个组合，使用私有普通脚本文件；检查执行次数、后续命令、缓存是否保留、结束状态和自动重启。修正版九项通过，同夹具旧版四项失败；单脚本58项回归通过。分区/shell执行、配置、sleep及最终重启为替身，不代表真实启动、缓存挂载或设备操作。

本地报告：`logs/ors-sequence-current.json`、`logs/ors-sequence-old.json`、`logs/ors-sequence-command-regression.json`。交付核对入口为`python3 scripts/audit_ors_results.py --sequence`。当前镜像见[交付报告](../simulation-report.md)，完整OTA沿用历史原包模型结果。

<a id="ors-command-results"></a>
## ORS脚本操作失败传播（0128）

原ORS解释器忽略了清除Cache/System/Dalvik、恢复出厂、格式化Data、挂载/卸载及`cmd`的失败结果。因`ret_val`保持0，失败后会继续执行下一条脚本；由启动action执行时，还可能据此进入自动重启。

[0128补丁](../dtsrc/O1_asic_dual/patches/0128-ors-command-error-propagation.patch)将上述分区操作的bool语义返回值转换为ORS的0成功/1失败，将`ExecCmd`非0返回转为失败，缺少参数的`cmd`也失败。失败后复用原解析循环停止；System清除失败不再进入后续详情刷新。成功路径和缺省命令别名保留。本补丁不更改NV界面策略或底层分区权限，也不回滚已经完成的操作。

新增定向检查执行完整原`run_script_file`与`Run_OpenRecoveryScript_Action`，用私有脚本文件验证58个成功/失败与直接/启动入口组合。每条被测命令后放置`set sentinel reached`，断言失败不执行后续命令、不进入自动重启，并返回1；成功仍执行后续命令并保留启动action的自动重启路径。当前全部通过，相同夹具旧版30项失败，含`tail=1 reboots=1`的实际替身调用记录。

分区操作、shell执行、DataManager、消息、sleep及最终reboot是显式替身；没有执行真实清除/格式化/挂载、Android shell或重启。已存在的底层文件系统工具证据沿用，不将此次结果称为完整GUI/FIFO状态、ORS准入或完整OTA验收。原`done_ors`表示解析结束，失败结果由返回码及启动页面状态区分，本批没有增加新的CLI退出码协议。

```bash
python3 tests/ors_results_test.py --report logs/ors-results-current.json
python3 scripts/audit_ors_results.py
```

本地报告为`logs/ors-results-current.json`、`logs/ors-results-old.json`及`logs/ors-results-delivery-audit.json`。当前镜像见[交付报告](../simulation-report.md)。以下保留此前分区界面维护记录。

用户报告确认刷入页“目标分区点不动”，并发现高级清除仍有 NV。此次检查发现两个具体缺陷：原厂文件系统 fstab 不含 raw 镜像目标，候选镜像也未带 `twrp.flags`，因而没有 Boot 等可选项；先前 0054 只限制普通挂载，没有覆盖清除与分区工具。此前检查范围不足。

维护的 `profiles/common/root/system/etc/twrp.flags` 现补入 Boot、Init Boot、Vendor Boot、Recovery、DTBO，交由核心检查分区是否存在及选择当前槽位。六份 OTA 的分区清单均含这五项；不写死 `_a`/`_b`。选择目标、滑动确认、真正写入仍是不同步骤。普通 `.img` 的目标选择应由这五种已存在分区提供，标题本身不承担选择功能。

补丁 0060 与配置共同覆盖以下普通 GUI 入口：

| 入口 | NV 行为 | 正常目标 |
|---|---|---|
| 挂载/卸载 | 沿用 0054：隐藏并拒绝直接或解析别名请求 | 保留 |
| 高级清除 | 隐藏；提交和执行前检查全部列表，含 NV 则在第一次清除前拒绝 | 保留 Data/Cache 等 |
| 修复/调整大小/更改文件系统 | 不提供详情；启动和执行前拒绝 | 保留 |
| 镜像刷入 | 不列出；启动和执行前拒绝，空目标/分号多目标亦拒绝 | 补齐五个 raw 目标 |

NV 集合为 nvram、proinfo、nvdata、nvcfg、protect_f、protect_s，含 `/mnt/vendor/` 对应路径、规范化路径、子路径和解析到 NV 的别名。前缀相似的普通路径不误拦截。原厂 fstab 不删除，内部服务仍可访问；备份/恢复和特权终端不受此普通 GUI 策略限制。persist、metadata 不按 NV 集合隐藏。FactoryReset 仍按核心 `wipe_during_factory_reset_` 标记选择目标，未给 NV 新增该标记。

离线检查执行生产方法：26 个路径/批次场景覆盖列表、提交、执行、别名、混合清除预检和分号注入；旧实现同组 19 个失败，修正后通过。真实 LVGL 确认页与原回调覆盖五目标各 label/detail/arrow/blank/drag-out，共 25 场景；路由执行目标点击后的 REPLACE、返回安装入口的 POP、再次 PUSH。确认接合回归让五目标各四种有效点击位置完成真实滑块拖动，断言 `start_image` 收到所选镜像路径、目标挂载点和双槽标志，并进入 INSTALL_PROGRESS；另五种拖出手势取消，共 25 项通过。之后将同一套点击/确认测试绑定当前候选镜像中提取的 `twrp.flags`，再次25项通过，证实这份交付镜像确实包含五个目标。安装源和 manager 仍为观察替身，未执行分区写入；原镜像写入链 40 场景核对私有文件内容与双槽顺序，修复链 7 场景调用镜像 ARM64 e2fsck，挂载策略 26 场景回归通过。上述离线证据不代表实机触摸或完整刷写已验收。

最终候选：`recovery-dijun-unified-partition-actions.img`，SHA256 `f9a11c04da1669ef601ca52ee6c38a99f32011aedcab06a5005af4f74f386db6`。最终 `installclean` 后 `make -j$(nproc)` 以 30 并发构建；769 来源绑定、六 profile 封装和实际镜像 flags 字节核对。初次编译发现新增自由函数访问私有字段，已改用公开 `GetMountPoint()`，修正后重新清理构建。未操作手机或物理块设备。

本地证据：`logs/partition-actions-delivery.json`、`nv-partition-actions.json`、`install-target-lifecycle.json`、`install-target-confirmation-chain.json`、`install-target-current-image.json`、`partition-actions-image-chain.json`、`partition-actions-repair-chain.json`、`partition-actions-mount.json`。公开仓库仅发布源码、配置、补丁、测试及摘要，不上传镜像、编译产物或原始日志。

<a id="tool-page-worker-lifecycle"></a>
## 分区工具页面与后台接续

`tests/partition_tool_pages_test.py` 补齐此前分开验证的页面与 worker 交接：原分区选项 builder / 点击回调 → 确认或选择文件系统 → 原工具后台线程 → 原进度页状态更新 → 返回分区详情。真实 LVGL 指针点击与滑块输入、page_host / scaffold、PUSH / POP、操作锁、后台 start / run / status / acknowledge 均参与执行；路由器由夹具接到这些原始页面，返回逻辑只提取 PARTITION_OPTIONS、CHANGE_FS、TOOL_CONFIRM、TOOL_PROGRESS 四个相关分支。

十个场景通过：修复、扩容、格式转换各自成功与失败，格式未选择、启动被拒后重试、确认前返回，以及格式页完成后再次进入。检查目标 / 格式传递、运行时拒绝返回与第二任务、DONE / FAILED 文案和按钮、返回后清空旧 view 并重新取详情。格式化失败的 manager 替身保留已改变的文件系统类型，用于确认页面不会显示虚假的回滚状态；这不是实际格式化证据。

本地报告 `logs/partition-tool-pages.json` 保存输出、编译命令、源码及 LVGL 依赖指纹。首次编译的定义提取 / include 问题，以及第二次运行中重复进入时错误要求累计调用数为零的问题，均属测试夹具；修正后十项通过，未发现需要修改的生产缺陷。只新增接续证据，没有生产补丁或新镜像。

**范围限制：** PartitionManager 操作与详情提供者、设置、字体、console 读取和显示提交为明确替身。没有运行 mkfs / fsck、完整 GUI 主循环、内核挂载或 fscrypt，不将此测试与独立的[ARM64 工具证据](FILESYSTEM-TOOLS-EXECUTION.md)拼称一次完整文件系统生命周期。相关源码与输入未变时复用本结果，不追加等价回放。

## 嵌套分区操作路径

以下保留 0029 的核心路径修正记录。它与后续 GUI 的 NV 操作限制分属不同层次，不能据核心能够查找分区推断普通界面允许清除 NV。

2026-11-12。设置保存的0028修正使`/mnt/vendor/persist/TWRP`能找到persist，但清除、转换文件系统、修复、调整大小四个入口仍使用GetRootPath。dijun fstab登记`/mnt/vendor/protect_f`、protect_s、nvdata、nvcfg、persist，旧入口却只查`/mnt`，因此无法选择这些真实挂载点。转换/修复/调整大小还缺少`/system`→`/system_root`映射。

维护补丁[0029-nested-partition-operations.patch](../dtsrc/O1_asic_dual/patches/0029-nested-partition-operations.patch)复用真实FindPartitionByPath选出的owner，按owner挂载点执行，并在操作全程持有现有递归操作锁。保留原始Wipe/Repair/Resize能力检查和确认入口；没有添加分区、改变可清除权限、改写fstab或绕过解密失败保护。路径包含普通子目录时仍归属其分区，不能将WipeByPath当成文件删除接口。

同时修正两个错误返回：子分区失败不再被忽略；不存在独立cache时，`/data/cache`清理返回值不再被丢弃。后者只传播WipeDataCache的现有结果；该底层函数未完整检查目录删除错误，本轮不能据此承诺所有删除故障均能传播。多分区操作不具备回滚，某项失败时此前成功项仍可能已完成。

### 验证

[检查程序](../tests/partition_operation_path_test.py)提取真实lookup、两种WipeByPath、RepairByPath和ResizeByPath方法，用私有分区对象记录调用。46断言通过；[旧源码同组](../logs/partition-operation-path-before.json)有20失败断言，这不是20个独立缺陷。覆盖：

- 嵌套挂载点、相邻名称边界、/system别名、/sdcard归属。
- 目标返回失败、子分区失败、父子调用、同块设备别名卸载。
- cache降级成功/失败、and-sec专用入口和既有tmp语义。

底层Wipe、Repair、Resize、Mount、实际设备定位及操作锁为替身；未运行格式化/fsck工具、删除目录、挂载或访问任何块设备。这是目标路由和返回值检查，**不是完整文件系统或清除功能验收**。UBSan开启。

设置挂载31断言、设置存储21项、备份55项、恢复54项及profile核心门控均通过。补丁序列从固定基线复现；installclean后`make -j$(nproc) recoveryimage`以30并发成功，新的recovery二进制与镜像内容一致。当前候选[recovery-dijun-unified-partition-paths.img](../imgs/built/recovery-dijun-unified-partition-paths.img)，SHA256 `fac3c815d6fab6febe23910c2f7bbf2c28d509a35003cb9db6df388b9237b4ed`。来源清单记录710文件；封装检查通过，同镜像profile回归9组、102次阶段调用通过。历史全量审计不转移至新镜像。

### 使用范围

后续已补充[15项同镜像ARM64文件系统工具执行](FILESYSTEM-TOOLS-EXECUTION.md)：私有普通文件中的ext4/F2FS/EROFS格式化、填充、检查、ext4扩容及部分内容读回。此证据独立于上面的分区对象替身；仍未贯通GUI/真实PartitionManager与内核挂载、加密或物理I/O，不将其升级为完整清除验收。

清除页面选择明确分区后确认；修复/文件系统变更页面只显示底层判定可用的操作。清除Data和格式化Data仍是不同入口，不能因解密失败自动执行。本轮修正目标查找，不是建议操作persist或protect分区；对这些分区的真实清除未执行、未验证。以上为该阶段的历史输入和验证边界；后续 NV 界面限制以上文 0054 / 0060 为准，当前状态见 [工作队列](WORK-QUEUE.md)。
