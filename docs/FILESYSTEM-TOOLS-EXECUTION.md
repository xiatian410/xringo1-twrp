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

测试输入含非空文件、空文件和符号链接。另用主机debugfs将ext4 payload inode链接计数设为7，目标e2fsck `-fp`实际修正并退出1，随后`-fn`退出0；独立内容读回一致。这覆盖一种有界元数据损坏，不代表其他损坏可修复；详见[结果处理修正](FSCK-RESULT-ADAPTATION.md)。F2FS目前只完成填充后结构检查，没有独立读回payload或验证内核casefold查找。没有执行Android安全标签初始化、fscrypt、dm-default-key、断电恢复或磁盘满故障。

QEMU的uname暴露主机kernel版本；F2FS输出也记录无法读取/proc/version，所以不能将此结果当作Android内核能力检查。linker通过私有LD_LIBRARY_PATH加载同镜像库，输出缺少生成的linkerconfig警告，执行仍成功；生产namespace和SELinux行为没有验证。工具执行没有调用GUI/PartitionManager、UFS ioctl或discard，不能替代完整清除/格式转换/挂载验收。

镜像及工具库、测试脚本、QEMU、主机debugfs与对应partition.cpp的哈希都在报告中。当前镜像继承ext修复结果处理，并补充时间失败处理；震动和完整任务目标继续进行中。
