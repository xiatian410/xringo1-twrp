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
