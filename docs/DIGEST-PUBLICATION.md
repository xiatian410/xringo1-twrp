# 备份摘要文件的原子发布

日期：2026-11-12。维护补丁为[0046](../dtsrc/O1_asic_dual/patches/0046-atomic-backup-digests.patch)。本轮只离线执行测试与构建，未连接设备。

原`TwrpDigestDriver::WriteDigest`先计算摘要，再通过`TWFunc::WriteToFile`截断正式`.sha2`/`.md5`文件写入。写入失败会破坏已有摘要，进程中断可留下半条记录；没有文件/目录fsync，返回成功不能证明发布已持久化。原函数的错误返回虽会传播到备份调用者，但不能恢复已截断内容。

## 修改后的行为

1. 仍使用真实流式BoringSSL MD5或SHA-256，保持`<hex>  <basename>\n`格式与原有设置入口。
2. 在目标同目录创建唯一`.twrp-digest.XXXXXX`临时文件并设置CLOEXEC。固定短文件名避免合法长摘要文件名加临时后缀后超出NAME_MAX。
3. 处理短写、EINTR和零写；应用既有的尽力设置Android元数据策略后，同步文件并检查关闭结果。不重试失败close，避免误关已复用描述符。
4. 只有前序步骤全部成功才rename替换正式摘要，然后同步目录。替换前失败保留已有摘要，并清理本次临时文件；正式摘要为符号链接时替换链接自身，不改写链接目标。
5. rename之后目录同步失败会返回false并记录`Digest replaced but directory sync failed`，完整新文件已可见，不能声称回退到旧文件。
6. 同步错误传回`MakeDigest`和实际`BackupPartition`；性能模式有作用域收尾，digest失败或其后取消均不会让该分区备份返回成功。

临时文件不作为`.sha2`/`.md5`读入，分卷清单也不将其识别为archive part。进程退出可留下临时文件，尚未新增自动清理。对多个分卷是逐文件发布；后一卷失败不回滚已成功发布的前卷。完整备份目录的成功标记、可信卷清单、archive数据持久性和断电恢复仍待完成。

## 离线证据

[检查程序](../tests/digest_publication_test.py)编译完整生产digest driver和TwrpDigest，并执行原样提取的`BackupPartition`调用体。使用真实BoringSSL、普通文件I/O、rename、fork、进程退出与ASan/UBSan；Python hashlib独立提供两种算法的预期摘要。输入跨越256KiB读取块，摘要内容和原始输入逐字节核对。

[54项结果](../logs/digest-publication.json)全部通过；[相同夹具的旧实现](../logs/digest-publication-before.json)54项中44项失败。覆盖两种算法的新建/覆盖、长文件名、短写、EINTR、零写、部分写后ENOSPC、临时文件创建、目录打开、文件同步、关闭、rename与目录同步错误、正式摘要为符号链接/目录、源文件缺失、失败后重试，以及普通/分组分卷。

三个进程中断边界分别为：临时文件部分写入后、临时文件同步后但rename前、rename后但目录同步前。它们验证进程死亡时可见文件内容与临时文件，不模拟突然断电或缓存丢失。写临时文件期间也核对正式路径未变，不只检查函数最终返回。

实际`BackupPartition`接入真实`MakeDigest`与原子发布，覆盖成功、同步失败与生成摘要后取消。分区archive内容创建、设置、GUI、挂载和Android元数据仍为夹具，不是完整`RunBackup`端到端验证。原厂驱动、DSP、电机和手机存储未参与。

[恢复流程54项](../logs/digest-atomic-restore.json)和[备份会话55项](../logs/digest-atomic-backup.json)回归通过。恢复组执行真实hash/driver；备份会话组继续把digest作为边界，不能把两组分别通过表述成完整备份流程已通过。

## 构建与候选

`make -j$(nproc) installclean`后执行`make -j$(nproc) recoveryimage`，30并发，两阶段成功，见[构建日志](../logs/build-digest-atomic.log)。[封装核对](../logs/verify-digest-atomic.log)确认六份精确profile、78份去重blob、原镜像头、当前新编译二进制及原厂安全组件字节。

候选：[recovery-dijun-unified-digest-atomic.img](../imgs/built/recovery-dijun-unified-digest-atomic.img)，SHA256 `7f4c42935ff34c01ce85cec049c94b60ebd072400255cf299aedaca10dacafff`，100MiB。[736份生产来源](../imgs/built/recovery-dijun-unified-digest-atomic-sources.json)与[封装元数据](../imgs/built/recovery-dijun-unified-digest-atomic.json)随候选保存。与前一mtp-reset候选比较，六份profile/78blob一致，所核对核心二进制仅`system/bin/recovery`改变；FF库和GUI库字节未改。

当前镜像激活/模块/策略/init回放和最终定向交付核对见[交付审计](../logs/digest-atomic-delivery.json)。该审计只绑定本次修改与相关回归，不代替历史全量证据刷新或原任务12组验收。震动、OS4自动触摸/唤醒和设置现场故障仍未解决。

使用时原有备份摘要生成入口自动使用新流程。已有摘要和`.sha2`/`.md5`读取格式保留，不要求用户删除或转换备份。生成摘要失败仍导致备份失败；完整新摘要可见也不等于整份备份可恢复。

复现：

```bash
python3 tests/digest_publication_test.py --output logs/digest-publication.json
python3 tests/digest_publication_test.py --source backups/digest-atomic-pre-fix/digest --output logs/digest-publication-before.json
python3 tests/restore_session_test.py --report logs/digest-atomic-restore.json
python3 tests/backup_session_test.py --report logs/digest-atomic-backup.json
python3 scripts/audit_digest_publication_delivery.py
```

旧实现负向对照应返回非零，其余项的断言与构建来源必须一并核对。
