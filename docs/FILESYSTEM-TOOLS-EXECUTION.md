# 当前镜像文件系统工具实际执行

<a id="format-mounted-guards"></a>
## 离线格式化的挂载前置检查（0086）

修复入口的 0085 不覆盖格式化 helpers。它们原先同样只检查 `Unmount()` 返回值，在该请求按用户设置保留 System 挂载时仍执行 mkfs。固定补丁 `patches/0086-offline-format-mount-guards.patch` 补齐 WipeExtfs、USE_EXT4 下的 WipeExt4、WipeFat、WipeExfat、WipeF2fs 和 WipeNtfs 的入口检查：卸载请求后若 `IsMounted()` 仍真，输出既有 fail_unmount / EBUSY 消息并失败，不调用格式化工具，不改变文件系统类型或重建目录。

原 `Wipe()` 的同格式 rm-rf / 媒体保留分派不受影响；这些分支原本就需要已挂载文件系统。当前格式化 helper 在确认已卸载后仍保留同格式缺工具的既有 rm-rf 回退，不借此强制卸载保留中的 System。

```bash
python3 tests/format_transition_test.py --mounted --report logs/format-mounted-current.json
python3 tests/format_transition_test.py --builtin-ext4 --report logs/format-mounted-builtin-current.json
python3 tests/format_transition_test.py --report logs/format-mounted-transition-regression.json
python3 tests/format_tool_chain_test.py --report logs/format-mounted-tool-regression.json
python3 tests/repair_mounted_test.py --report logs/format-mounted-repair-regression.json
python3 scripts/audit_format_mounted_delivery.py
```

扩展既有格式转换夹具，执行完整 Wipe / helpers / manager / backend：ext4、ext2、ext3、FAT、exFAT、F2FS、NTFS 各有“卸载成功但保留挂载”和正常卸载两个场景，加同格式 rm-rf 保留挂载控制，共十五项。旧代码七个格式选择均误执行工具；修正后十五项通过，命令数、返回状态、类型和重建次数均核对。可选 `USE_EXT4` 单独编译原内建分支；保留挂载时不得进入 make_ext4fs，旧同组一个场景失败、修正通过。内建 formatter 是明确拒绝调用的替身，不证明其真实工具实现。

此组 Unmount / IsMounted 是显式状态替身，模拟上节原 Unmount 已执行证明的保留挂载返回语义；没有调用 mount 或 umount。工具 / 容量 / 设备 / metadata 也为替身。原二十五项格式转换回归通过；新镜像 ARM64 格式化后修复六项回归及 0085 原 Unmount / Repair / Resize 九项回归通过，实际工具只操作私有普通文件。

清理构建使用 installclean 和 `make -j$(nproc)`；804 来源绑定，六份 profile 字节不变，相对 0085 仅 Recovery 主程序、构建属性和摘要变化，`logs/format-mounted-delivery.json` 审计通过。现行候选与哈希见[交付报告](../simulation-report.md)。

本项到此收尾，不扩展等价格式选择夹具。检查使用既有挂载点观测，不证明同设备所有别名挂载、外部并发重挂载、完整 GUI / fscrypt 或真实 kernel / 断电。后续格式化后的临时挂载、标签初始化与目录重建仍需按具体故障处理，本项不声称完整格式化生命周期完成。

<a id="repair-mounted-guard"></a>
## 离线修复的挂载前置检查（0085）

`Unmount()` 在 `tw_dont_unmount_system` 设置开启、目标仍是已挂载 Android root 时，可以保持挂载并返回 true。旧 `Repair()` 仅检查返回值，随后运行离线 fsck；`Resize()` 通过前置 Repair 也会进入该路径。固定补丁 `patches/0085-offline-repair-mount-guard.patch` 在卸载请求之后再次查询 `IsMounted()`，仍挂载则输出现有 fail_unmount / EBUSY 消息并失败，不启动 fsck 或 resize2fs，也不强制覆盖用户的保留挂载设置。

```bash
python3 tests/repair_mounted_test.py
python3 tests/repair_exit_status_test.py --report logs/repair-mounted-exit-regression.json
python3 tests/repair_tool_chain_test.py --report logs/repair-mounted-tool-regression.json
python3 tests/format_tool_chain_test.py --report logs/repair-mounted-format-regression.json
python3 scripts/audit_repair_mounted_delivery.py
```

九个场景执行原 Unmount / CanRepair / Repair / Resize、manager 路由和 backend 包装：修复 / 扩容的保留挂载、正常卸载、已卸载和卸载失败，以及 F2FS 修复。旧代码两个保留挂载场景误执行工具；修正后全部通过，保留挂载和卸载失败均不执行命令，backend 发布失败。场景中的 mount 状态、umount 系统调用、设备路径、容量和命令执行是明确替身，原 Unmount 的保留 System 分支实际执行；没有进行真实挂载或磁盘操作。

受影响修复返回码回归 146 个断言通过；同镜像 ARM64 e2fsck 七个实际调用场景以及格式化 / Repair 六个接续场景通过，后两者只操作 QEMU 私有普通文件，卸载仍是替身。成功修复、修正错误码 1、无效文件、缺工具、卸载拒绝和子目标失败等按原范围核对，保留原报告不覆盖。新增 `--report` 只用于保留这次格式化回归报告。

以 installclean 和 `make -j$(nproc)` 清理构建，803 来源绑定、六份 profile 字节不变；相对 0084 仅 Recovery 主程序、构建属性和 ramdisk 摘要变化，`logs/repair-mounted-delivery.json` 审计通过。候选及哈希以[交付报告](../simulation-report.md)为准。

本修正覆盖 Repair 入口及 Resize 前置 Repair，不声称所有格式化 / 恢复入口的挂载生命周期已检查。`IsMounted()` 仍使用既有挂载点 / stat 观测，没有增加按设备扫描所有别名挂载或真实内核验证。不得将本组替身结果解释为完整 GUI / fscrypt / 实机验收；本项完成后不重复同类保留挂载夹具。

## 早期工具执行记录

以下保留早期候选与工具输入，当前镜像与状态以上方交付链接为准。

2026-11-12。当前绑定`recovery-dijun-unified-clock-failure.img`（SHA256 `1c0813cf324d76be52e588e4dd3358c1c104946841e393aef84df2d951437adc`）。从镜像提取ARM64工具、linker和共享库，在QEMU用户态执行；不使用主机mkfs替代目标格式化工具。所有目标都是程序新建、结束即删除的私有普通文件，没有挂载、loop或真实块设备。此前fac3c815镜像的15项是历史检查点。

[程序](../tests/filesystem_tools_image_test.py)、[机器报告](../logs/filesystem-tools-image-test.json)、[完整输出](../logs/filesystem-tools-image-test.log)。运行：

```sh
python3 tests/filesystem_tools_image_test.py
```

17项检查通过，覆盖范围如下：

| 文件系统 | 实际执行及独立核对 |
|---|---|
| ext4 | `mke2fs -t ext4 -b 4096 -I 512 -O metadata_csum,64bit,extent`创建64MiB卷；核对superblock容量；e2fsdroid填充；e2fsck `-fp`检查干净卷；主机debugfs独立读出payload并比对；底层文件扩至96MiB后resize2fs扩容，再e2fsck `-fn`及superblock容量复核 |
| F2FS | make_f2fs使用Recovery的`-g android`、project_quota/extra_attr、casefold/utf8及`size/4096`参数；核对256MiB容量和magic；sload_f2fs填入私有源目录；fsck.f2fs dry-run通过且整个镜像哈希不变 |
| EROFS | mkfs.erofs使用lz4hc构建；fsck.erofs检查并提取；payload逐字节一致，符号链接目标一致，输入镜像哈希不变 |
| 无效输入 | 三种checker对私有全零普通文件均返回非零：e2fsck=8、fsck.f2fs=255、fsck.erofs=1 |

F2FS工具帮助写的是sectors，但Android默认配置明确设置wanted_sector_size=4096，再按实际sector大小折算。本次真实工具生成的superblock确认size/4096没有把256MiB错误截成32MiB；不能仅凭帮助文本把生产参数改为size/512。

测试输入含非空文件、空文件和符号链接。另用主机debugfs将ext4 payload inode链接计数设为7，目标e2fsck `-fp`实际修正并退出1，随后`-fn`退出0；独立内容读回一致。这覆盖一种有界元数据损坏，不代表其他损坏可修复；详见下文“修复结果与调用链”。F2FS目前只完成填充后结构检查，没有独立读回payload或验证内核casefold查找。没有执行Android安全标签初始化、fscrypt、dm-default-key、断电恢复或磁盘满故障。

QEMU的uname暴露主机kernel版本；F2FS输出也记录无法读取/proc/version，所以不能将此结果当作Android内核能力检查。linker通过私有LD_LIBRARY_PATH加载同镜像库，输出缺少生成的linkerconfig警告，执行仍成功；生产namespace和SELinux行为没有验证。工具执行没有调用GUI/PartitionManager、UFS ioctl或discard，不能替代完整清除/格式转换/挂载验收。

镜像及工具库、测试脚本、QEMU、主机debugfs与对应partition.cpp的哈希都在报告中。当前镜像继承ext修复结果处理，并补充时间失败处理；震动和完整任务目标继续进行中。

## 修复结果与调用链

2026-11-12 当前backup-manifest镜像接续验证：`python3 tests/repair_tool_chain_test.py`的七场景通过，见`logs/repair-tool-chain.json`。将原始backend repair包装、分区最长前缀lookup/RepairByPath、TWPartition::Repair及输出ExecCmd接到同镜像ARM64 e2fsck；主机静态harness在私有chroot内执行，兼容launcher通过QEMU/同镜像Android linker与库调用实际工具。干净卷wait0、实际链接计数修复wait256（退出1）、无效卷wait2048（退出8）正确传回；缺工具/卸载拒绝/未知目标无checker执行，子分区无效使整体失败。实际修复后再次-fn通过，主机debugfs读回payload一致。设备解析、卸载和operation_start/end是显式夹具，没有完整GUI、真实挂载、FBE或硬件生命周期，不把`full_lifecycle`标成完成。未改生产或重编译。

2026-11-12。当前Repair通过普通ExecCmd执行e2fsck，只接受退出0。e2fsck的退出1表示已修正错误，普通ExecCmd却把所有非零退出折叠为-1，导致成功修复仍显示失败。

维护补丁[0030-e2fsck-corrected-result.patch](../dtsrc/O1_asic_dual/patches/0030-e2fsck-corrected-result.patch)仅对e2fsck使用保留POSIX wait status的既有ExecCmd输出重载，输出仍写入recovery日志。正常退出0或1视作修复成功；2/3的需重启状态、未修正错误、执行错误、取消及信号终止继续返回失败。其他文件系统工具保持既有返回语义；不扩大可修复分区或自动重启。

[真实Repair方法测试](../tests/repair_exit_status_test.py)使用私有挂载/命令边界，但由真实主机shell的exit/signal生成wait status，生成的修复命令只记录不执行。146断言通过；[旧实现](../logs/repair-exit-status-before.json)中ext2/3/4退出1共3断言失败。[新结果](../logs/repair-exit-status.json)覆盖0/1、需重启2/3、4/8/16/32/128/255、信号、启动失败、缺工具、卸载失败和其他文件系统行为。

另有本文前述 ARM64 工具执行：主机debugfs将一次性ext4镜像内payload inode链接计数从1改为7；目标e2fsck `-fp`报告FIXED并退出1，随后目标e2fsck `-fn`退出0，独立读回payload一致。由此明确区分“原始工具成功修正”和“Recovery误报失败”，没有对真实分区制造损坏。

新候选`recovery-dijun-unified-fsck-result.img`，SHA256 `e153160d5cb2c8f438a899847bff6714caee37ac32eeb136996ef1aa08395b11`，installclean后make -j$(nproc) recoveryimage构建成功，711来源指纹记录；包装与新二进制检查通过。没有修改震动、触摸或解密路径，完整GUI/内核挂载/硬件验证仍未完成。

复现命令：`python3 tests/repair_exit_status_test.py`；格式化/真实修复工具：`python3 tests/filesystem_tools_image_test.py`。前者不运行实际工具，后者仅对程序新建的私有文件执行工具；这两层检查共同支持本次返回值修正，仍不是完整界面操作验收。

## 目录清除失败传播（0073）

`RemoveDir(path, true)` 原先在同一个 `error_code` 上反复调用 `remove_all`，早期失败会被后续成功清空；目录迭代递增还使用可能抛异常的接口。`WipeRmrf`、`WipeAndSec` 和 `WipeDataCache` 又忽略返回值，即使目标文件仍在，也会一路发布清除成功。

[0073 固定补丁](../dtsrc/O1_asic_dual/patches/0073-wipe-directory-error-propagation.patch)在首个删除错误时记录并返回失败，迭代递增也使用 `error_code` 检查。三个清除入口传播删除返回值；整分区内容清除失败不再继续重建 android_secure 目录。缓存或 android_secure 子目录本来不存在时保持幂等成功，路径查询失败仍为失败。中途失败可能已删除其他内容，不承诺回滚。

有限验证执行真实 `RemoveDir`、三个分区 helper、manager 路由及后台 `LIST/run/report_item`，在私有 chroot 内创建普通文件，降权至 uid/gid 65534 后用真实权限拒绝触发失败。11 场景通过，旧实现同组 5 失败：三个权限拒绝、整分区路径缺失，以及第一项失败被后续成功覆盖。另覆盖删除成功、挂载拒绝及不存在的两个子目录。共用删除函数改变后，原备份目录管理 12 场景必要回归通过。未重跑无关页面、profile 启动或震动测试。

```bash
python3 tests/wipe_errors_test.py
# 需本地保存的旧源，预期五项失败：
python3 tests/wipe_errors_test.py --before
python3 tests/backup_manage_test.py --report logs/wipe-errors-backup-regression.json
python3 scripts/audit_wipe_errors_delivery.py
```

挂载、设备解析、其他清除模式和操作呈现是明确替身；同步调用原 `run`，没有覆盖完整后台 start/thread、GUI 或真实文件系统挂载。`RecreateAndSecFolder` 是计数替身，仅验证失败不再调用它，不证明其内部重建正确。

候选 `recovery-dijun-unified-wipe-errors.img`，SHA-256 `4be5c38595551ad48a5fc3ec09376431cfeed0ccf2c6dc77d97b73e89082ca78`。先 `installclean`，再 `make -j$(nproc)` 30 并发；788 份生产来源及六份 profile 封装核对。相对 progress-console 候选，只有 Recovery 主程序、构建属性和 ramdisk 摘要改变。

剩余具体缺口：`WipeDataWithoutWipingMediaFunc` 仍有只记录 unlink 失败后返回成功的路径；Dalvik / 媒体清除的其他调用方也未在本批覆盖。它们需要分别考虑排除目录、部分删除和错误传播，不能用这 11 项结果宣称完整清除 / 格式化已验收。现场容量刷新故障不在本批修复范围内。

## 保留媒体的数据清除（0074）

0073 未覆盖的 `WipeDataWithoutWipingMediaFunc` 会在 unlink 失败时只输出日志，目录删除失败也一律忽略，最后仍发布成功。[0074 固定补丁](../dtsrc/O1_asic_dual/patches/0074-media-preserving-wipe-errors.patch)让递归中的类型读取、删除和目录迭代错误返回失败，阻止 wrapper 的“完成”消息，并通过 manager / 清除后台发布 FAILED。

递归新增可选的 `retained` 输出，明确向父级报告是否留下排除内容。只有实际保留排除内容时，才接受删除父目录的 ENOTEMPTY；权限及 I/O 错误仍失败。继续使用原 `TWExclude` 的相对 / 绝对排除匹配，并以 symlink_status 检查条目，删除链接本身而不进入其目标。`TW_WORKAROUND_BACKUP_BUG` 保留 `/data/data` 的既有行为；本设备未启用该宏，但单独编译该分支检查兼容性。清除可能已部分完成，失败不提供回滚。

```bash
python3 tests/media_wipe_test.py
# 需要本地旧源，预期三项失败：
python3 tests/media_wipe_test.py --before
python3 scripts/audit_media_wipe_delivery.py
```

13 场景执行原始递归与 wrapper、真实排除匹配和路径规范化、manager 路由及后台 LIST/run/report。覆盖媒体保留、嵌套绝对排除、相对 lost+found 排除、指向媒体 / 外部目录的链接及悬空链接、unlink / opendir / rmdir 权限拒绝、排除目录同级删除拒绝、不可读但已排除的媒体、挂载拒绝、根目录缺失及 workaround 两个编译分支。真实权限错误来自私有 chroot 中普通文件和降权 uid/gid，不操作物理设备。旧实现同组三项误成功。首次两项夹具父目录默认 0755 导致额外权限拒绝，已修正为显式创建可写父目录，原失败记录保留为 `logs/media-wipe-first-attempt.json`。

挂载、设备解析、同文件系统的 Wipe 分派与操作展示为明确替身；未执行完整 Wipe 方法、worker start/thread 或 GUI。目录迭代错误走 error_code 路径，但没有注入真实内核 readdir / stat EIO，也未覆盖并发替换 / 写入者。0073 的三个分区方法与本次修改前字节一致，其余原绑定来源不变，因此复用目录清除 11 项和备份目录 12 项结果，不重复执行或改写旧报告。

候选 `recovery-dijun-unified-media-wipe.img`，SHA-256 `d487215a5a604bdf1abad2007984e26f38ed8e5a7e9140059db4f90199f9a646`；先 installclean，再 `make -j$(nproc)` 30 并发，789 来源 / 六 profile。相对 wipe-errors 候选只改变主程序、构建属性与 ramdisk 摘要；GUI / MTP / updater / profile 字节不变。完整格式化 / 写入 / 修复、真实挂载及 Dalvik / 媒体清除的其他调用方仍未闭环。

## Dalvik 与内部存储清除（0075）

`WipeDalvikCache` 原先忽略删除结果，并在 cache 或已有 sd-ext 挂载失败时继续输出成功；路径存在性查询也把权限失败当作“不存在”。`WipeMediaFromData` 忽略删除失败，并删除 `/data/media` 根目录；FBE 下原 `RecreateMediaFolder` 直接返回，成功删除后也不恢复根目录。

[0075 固定补丁](../dtsrc/O1_asic_dual/patches/0075-manager-cache-media-wipe-errors.patch)让 Dalvik 的所需挂载、路径查询与删除失败返回失败，只有实际完成对应删除才输出 cleaned，所有目标处理完才输出完成。不存在的缓存目录可跳过；存在且标记 present 的 sd-ext 挂载失败不再被静默跳过。

内部存储清除先确认 `/data/media` 是真实目录，拒绝缺失 / 链接 / 非目录目标，再移除 MTP 登记、用 `RemoveDir(..., true)` 只删除内容。根目录的 inode、已有策略与元数据保持原位，不再走重建；部分删除失败也尝试恢复 MTP 登记，但操作结果仍失败。登记接口的实际 USB 结果不在本批验证范围内，失败可能已产生部分删除，不承诺回滚。此改动不代替完整用户媒体重建或 CE 密钥生命周期。

```bash
python3 tests/manager_wipe_test.py
# 需要本地旧源，预期九项失败：
python3 tests/manager_wipe_test.py --before
python3 scripts/audit_manager_wipe_delivery.py
```

16 场景执行实际 manager / RemoveDir、原媒体重建方法（旧实现会调用）与后台 LIST/run/report；在私有 chroot 普通文件上降权制造真实权限拒绝。覆盖 Dalvik 正常 / 独立 cache / 缺失、删除 / 查询失败、data/cache/sd-ext 挂载拒绝；媒体 FBE/legacy 成功、删除失败、根目录缺失 / 符号链接、挂载拒绝、无媒体能力和缺 data。旧实现同组九项不符合预期。媒体成功及删除失败时核对根 inode 与 `user.wipe-root` 扩展属性；这是普通测试标记，**不是 fscrypt policy ioctl / 密钥验证**。链接目标外的文件保持不变。

挂载、MTP、metadata 和操作展示为替身，未执行完整 GUI/start/thread、真实挂载、USB 或内核 I/O 错误。0074 使用的 manager lookup / WipeByPath 方法与本次前源码逐方法比较一致，其他绑定来源不变，复用其 13 项结果及备份目录 12 项，不改写旧报告或重复执行。

候选 `recovery-dijun-unified-manager-wipe.img`，SHA-256 `bfe8bebdcfd4fbaf3fbb2b291239922b1bf089d527b7aeef3389342026e762e4`；先 installclean，再 `make -j$(nproc)` 30 并发，790 来源 / 六 profile。相对 media-wipe 候选只改变 Recovery 主程序、构建属性与 ramdisk 摘要，GUI/MTP/updater/profile 字节不变。完整格式化 / 写入 / 修复、真实 fscrypt/MTP 与断电仍未闭环；不将三批目录清除修正当作完整文件系统适配完成。

## 文件系统转换分派与状态（0076）

更改文件系统调用原 `Wipe(new_file_system)`，但全局 rm-rf / 分区 use_rm_rf 标志原先会直接删除旧文件并返回成功，没有转换格式。ext / FAT / F2FS 工具缺失时也可能退回同样的删除。NTFS / F2FS 分派还错误使用旧 `current_file_system_` 的 tntfs / mifs 别名；F2FS/exFAT/NTFS 成功后未更新类型，随后的重建 / 挂载可能仍使用旧类型。

[0076 固定补丁](../dtsrc/O1_asic_dual/patches/0076-filesystem-conversion-dispatch.patch)将 rm-rf 限于同类型清除；转换必须走请求格式。工具缺失只允许同类型的既有 rm-rf 回退，转换返回失败。分派按请求类型及别名选择，成功后在重建前更新 F2FS/exFAT/NTFS 类型；USE_EXT4 分支成功也补齐 ext4 类型。未知格式、拒绝清除、卸载失败和工具非零仍失败，不把部分格式化解释为回滚。

```bash
python3 tests/format_transition_test.py
# 需要本地旧源，预期十项失败：
python3 tests/format_transition_test.py --before
python3 scripts/audit_format_transition_delivery.py
```

25 场景执行完整原 `Wipe(new_file_system)`、ext4 wrapper/extfs/FAT/exFAT/F2FS/NTFS helper、manager lookup/WipeByPath 与 changefilesystem backend 包装。覆盖五类格式成功、旧 tntfs→F2FS / mifs→FAT、两种 rm-rf 覆盖、同类型 rm-rf、五类缺工具、三类同类型回退、四类命令失败及卸载/设备/允许清除状态。旧实现同组十项失败；这包括同一缺陷的多触发方式，不是十个独立根因。

命令执行、容量、设备探测、卸载、属性与 metadata 为替身；没有运行 mkfs、挂载或完整 GUI，不将更新内存类型称作真实盘面转换。extfs 选择以无 selinux_handle 分支执行，实际 e2fsdroid / USE_EXT4 内建分支未执行。首次测试编译缺少 filesystem 头文件，补齐后通过，失败日志保留。原工具执行与修复检查仍按其历史范围保留，未被伪装为本批接续验证。

0074/0075 的相关执行方法未变：逐方法对比保存的旧源，核对其他绑定来源，复用媒体递归13项与 manager清除16项，不重跑已修正目录清除。它们当时明确替代 Wipe 分派，不能与本批拼成一次完整设备调用。

候选 `recovery-dijun-unified-format-transition.img`，SHA-256 `f0a1ff30d0735eafdc6cc1822351a8cd34d01745b51c767b33fbf808ad1b0ba7`；先 installclean，再 `make -j$(nproc)` 30 并发，791 来源 / 六 profile。相对 manager-wipe 只改变 Recovery 主程序、构建属性与 ramdisk 摘要，其他业务库和 profile 不变。下一明确边界是实际目标格式化工具与读回/修复接续及 GUI/挂载生命周期，不继续扩增等价命令夹具。

## 实际格式化工具与调用链接续

0076 的命令替身边界现由 `tests/format_tool_chain_test.py` 补充六个实际执行场景。镜像仍为 format-transition，SHA-256 `f0a1ff30d0735eafdc6cc1822351a8cd34d01745b51c767b33fbf808ad1b0ba7`，791 生产来源未变。本批没有新增生产修正或构建。

主机 C++ 执行原完整 Wipe 分派、格式化 helpers、manager lookup/WipeByPath、changefilesystem 包装、Repair 与两个 ExecCmd / WaitForChild 重载。实际 fork/exec/wait 在私有 chroot 内通过 host shell 启动兼容 launcher，原工具 argv 不改写；launcher 以 QEMU 和同镜像 linker / 共享库运行 ARM64 mke2fs/make_f2fs/sload_f2fs/e2fsck/fsck.f2fs。块大小 ioctl 明确由目标普通文件 stat 大小替代；卸载、设备探测、属性、metadata 与展示继续是边界。

六场景：ext4→F2FS、F2FS→ext4、全局/分区 rm-rf 开启时仍真正转换、4MiB 小卷实际 make_f2fs 拒绝、缺 make_f2fs 时没有执行命令且整个文件哈希不变。成功场景随即调用原 Repair，F2FS 走 fsck.f2fs -a，ext4 走 e2fsck -fp。实际盘面 magic 与变化哈希核对；ext4 后续 e2fsdroid 填充、e2fsck -fn、独立 host debugfs 读回 payload 一致。F2FS 后续 sload 填充、fsck dry-run 结构检查通过且哈希未变，尚无独立 payload 读回。

```bash
python3 tests/format_tool_chain_test.py
python3 scripts/audit_format_tool_chain.py
```

隔离环境提供普通空文件 `/proc/mounts`，明确代表无挂载，不挂载 procfs、不读取主机挂载表。初次缺少该文件使 F2FS regular-file 检查在 getmntent(NULL) 退出；随后一次 launcher PATH 未包含 `/system/bin`，造成 sload 找不到，均为夹具问题。编译缺少 fs 别名也已补齐，失败日志保留，没有据此修改生产模块。linker 缺 `/proc/self/fd` / linkerconfig 的警告保留，不声称生产 namespace 已验证。

selinux_handle 为空，原 WipeExtfs 的 e2fsdroid 标签初始化分支未执行；后续显式内容填充不是该分支的替代证明。sload_f2fs 使用原 `-t /data`，没有接入真实 Android 属性、标签或加密密钥。父 Recovery 调用者为主机程序，不是完整 ARM64 Recovery/GUI，MTP与真实挂载、fscrypt、discard、并发和断电仍未覆盖。测试只允许脚本新建普通文件；没有操作手机或物理块设备。

<a id="f2fs-readback"></a>

## F2FS 独立内容读回

`tests/f2fs_readback_test.py` 补齐此前只有结构检查的内容边界：当前 cli-fifo 镜像的 ARM64 `make_f2fs` / `sload_f2fs` 经固定 QEMU 和同镜像 linker / 库，在私有 chroot 中创建及填充 256 MiB 普通文件。格式参数保留 `project_quota,extra_attr`；没有挂载文件系统、连接手机或访问物理块设备。

独立 Debian amd64 `dump.f2fs` 从该镜像导出六个合成文件，包括空文件、251字节内联文件、普通数据、嵌套中文名称、5 MiB+17字节多节点文件与长零数据区域，全部内容/大小/SHA一致。另一份副本中只翻转实际payload数据的一个字节，独立导出仅该文件不一致，其余内容一致；两次读取前后整个镜像SHA不变。它证明普通文件内容读回，不证明稀疏物理分配、元数据、压缩或加密。

Debian1.16读取器只支持按inode导出，没有Android分支的递归`-r/-o`选项，第一次尝试失败保留为 `logs/f2fs-readback-first-attempt.json`。改用已知合成名称/父inode字段定位候选inode后，由外部读取器自行解析NAT和数据；这不是通用目录遍历器，不能把已知路径夹具说成目录查找验收。

该读取器还存在独立兼容问题：`dump_inode_blk` 用固定 `INLINE_DATA_OFFSET`，遗漏 `extra_attr` 占用。未修正的主机包能读回其他五文件，内联小文件内容错误。主机专用 [补丁](../scripts/f2fs-inline-reader.patch)改用该源码已有的 `inline_data_addr(node_blk)`；Android当前dump实现已如此处理，无需修改生产工具。保留原包同组失败报告，不将读取器错误归因于ARM64写入损坏。源码归档及补丁SHA固定在 [来源清单](../scripts/f2fs-reader-source.json)。

```bash
# 需要Debian source源及gcc/make/autoconf/automake/libtool/pkgconf/uuid-dev
python3 scripts/prepare_f2fs_reader.py
python3 tests/f2fs_readback_test.py
python3 scripts/audit_f2fs_readback.py
```

准备脚本将源码和编译文件只留在本地 `tools/f2fs-host`，不覆盖已有构建目录；没有将host读取器作为Recovery补丁，也未安装替换系统文件。首次libtool包装器/共享库构建路径问题已修正为明确禁用共享libf2fs后复制ELF，最终脚本从新目录实际执行并通过。原Debian二进制对照依赖本地已提取包，使用`--stock-reader`和单独`--report`保存。

本批只有验证及host工具维护，生产候选、793来源及六profile不变，没有重编Recovery。结果 `logs/f2fs-readback.json` 和定向核对 `logs/f2fs-readback-audit.json`。不重复此前六种转换场景；父manager/GUI、真实挂载/fscrypt、F2FS目录通用查找及断电边界仍未完成。

<a id="persist-postformat"></a>

## persist 格式化后的临时挂载与错误返回（0087）

`WipeExtfs` 在 mke2fs 成功后，按 SELinux 配置选择执行 e2fsdroid。persist 分支会临时挂载新文件系统、删除 lost+found，再卸载后进行离线标记。原实现忽略三个步骤的结果，且到最后才更新文件系统类型，可能以旧类型挂载、在挂载失败后删除宿主目录，或在仍挂载时执行离线工具。

0087 在 mkfs 成功后立即记录新类型；挂载失败立即返回，删除失败也会尝试卸载，卸载失败或仍挂载均拒绝继续 e2fsdroid。后处理失败返回失败，但已完成格式化的新类型保留，不承诺数据回滚。未找到 SELinux context 时仍沿用既有跳过标签的策略，本批未改变该策略。普通 GUI 的 NV / persist 策略不变，内部 core 路径不因此扩大访问范围。

扩展现有格式转换夹具，而非新增等价套件：ext2 / ext3 / ext4 各覆盖成功、挂载失败、删除失败、卸载失败、卸载请求成功但仍挂载、标签查找失败，共 18 场景。检查实际生产 Wipe / helper / manager / backend 返回值、命令顺序、新类型、清理尝试及最终挂载状态。旧实现 15 项失败，修正后全部通过；25 项原格式转换与六项同镜像 ARM64 工具回归通过。

```bash
python3 tests/format_transition_test.py --persist --report logs/format-persist-current.json
python3 tests/format_tool_chain_test.py --report logs/format-persist-tool-regression.json
python3 scripts/audit_format_persist_delivery.py
```

挂载、设备、容量、SELinux 和目录删除是显式故障边界；没有操作实际 persist、物理块设备或真实挂载。ARM64 工具回归只在私有普通文件上运行。and-sec / media 目录重建、完整 GUI / fscrypt 生命周期仍未完成，本批不据此关闭完整文件系统目标。最终 installclean / 30 并发构建，805 来源绑定；候选哈希集中见[交付报告](../simulation-report.md)。

<a id="andsec-recreation"></a>

## Android Secure 目录重建结果（0088）

原 `RecreateAndSecFolder` 为 void：挂载失败仅记录，mkdir 和别名挂载 / 卸载返回均忽略。格式化 helpers 与 rm-rf 随后仍返回成功。父分区 Mount 无法为尚不存在的目录执行绑定；旧逻辑在创建前调用管理器挂载，创建后再卸载，也没有可靠恢复 `/and-sec` 绑定。

0088 将其改为 bool。无 Android Secure 功能时直接成功；父挂载失败立即返回；使用 lstat 确认目录，缺失时按 0755 创建，查询 / 创建失败或非目录返回失败。目录就绪后检查已有绑定，未绑定时调用原 BindMount，并传回实际结果。七种格式选择（ext2/ext3/ext4/vfat/exfat/f2fs/ntfs）和 WipeRmrf 均检查返回值；失败不输出最终 done，不假装回滚已完成清除或新文件系统类型。保留父挂载，不为目录重建调用管理器卸载整个存储。

扩展已有格式转换夹具，37 场景覆盖上述八个入口各四种结果（成功 / mkdir失败 / bind失败 / Mount失败），以及直接调用的禁用、已有目录、已有绑定、普通文件与符号链接。目录创建及 lstat 使用私有临时普通文件；mkdir拒绝、挂载、绑定、设备和格式化命令为显式边界。原 helper/manager/changefilesystem 返回及最终目录检查均执行，旧实现 34 项失败，修正后 37 项通过。25 项格式转换、11 项实际私有目录权限清除结果回归与六项同镜像 ARM64 格式化修复通过。

```bash
python3 tests/format_transition_test.py --andsec --report logs/andsec-recreate-current.json
python3 tests/wipe_errors_test.py --report logs/andsec-recreate-wipe-regression.json
python3 tests/format_tool_chain_test.py --report logs/andsec-recreate-tool-regression.json
python3 scripts/audit_andsec_recreate_delivery.py
```

SetupAndSec 的发现阶段仍按原 best-effort 方式记录失败；可选 USE_EXT4 内建格式化的 lost+found 后处理与 media 目录重建不在本修正内。不是完整 MountFilesystem / 真实 bind、GUI、fscrypt 或并发外部目录更改的证明。最终 installclean / 30 并发构建、806 份来源、六份 profile 不变，候选见[交付报告](../simulation-report.md)。
