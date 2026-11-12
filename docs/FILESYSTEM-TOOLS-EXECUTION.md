# 当前镜像文件系统工具实际执行

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
