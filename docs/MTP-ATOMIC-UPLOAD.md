# MTP上传原子发布

2026-11-12补充0059：目录SendObjectInfo应用有效修改时间并立即结束传输，元数据失败保留目录供重试。110项对象/48项转移检查及精确边界见[目录上传](MTP-DIRECTORY-METADATA.md)。子文件写入后的父目录最终日期、跨重启临时文件归属回收仍未完成。


2026-11-12补充0049：文件上传临时inode的futimens失败现被视为提交前失败，不再rename覆盖旧目标；有效Unix零秒与缺日期区分。文件fsync/close/rename/目录同步原子发布机制保持，目录同步失败仍是已提交但持久性不确定。94项对象链路/48项转移与16项日期旧10失败见[时间接续](MTP-DATETIME-ADAPTATION.md)。跨重启临时文件所有权与回收仍未完成，不按通用前缀删除用户文件。下文mtime缺值哨兵未修正是历史描述。


MTP上传原子发布：补丁0041以同目录唯一临时文件接收，接收/长度校验/fsync/close均成功才rename，失败只删除临时文件，保留旧目标。数据库在同一observer锁下创建并登记精确临时路径，inotify、ReadDir与overflow reconciliation均不发布传输中的临时文件。68项真实server/database/storage主机检查（含22项新原子发布场景）与48项move/copy回归通过；旧实现5项覆盖对照均失败。目录fsync在rename之后失败只警告，完整新文件已提交，不能声称可恢复旧inode；模拟进程中途退出保留旧目标但留下临时文件，跨重启清理未完成。installclean后make -j$(nproc)30并发构建recovery-dijun-unified-mtp-atomic-upload.img，SHA256 `7ca65801af3a62b4970cf1ad12d05a8af49dd8e870992b45e40ad6192a06a23a`，727来源与封装核对通过，同镜像profile回放结果另记。震动、现场设置及完整12组仍未完成。

验证入口：

```bash
python3 tests/mtp_objects_test.py --report logs/mtp-atomic-objects.json
python3 tests/mtp_transfers_test.py --report logs/mtp-atomic-transfers.json
python3 scripts/audit_mtp_atomic_upload.py
```

新建与覆盖各11场景：成功、接收失败、返回成功但长度不足、文件同步失败、写零字节、rename失败、临时文件创建失败、close失败、目录同步失败、取消、进程中途退出。传输边界检查目标仍为旧内容/不存在，精确临时路径不出现在数据库；完成后核对内容、handle保留与临时文件清理。取消沿用server不发响应的行为，通过后续命令完成同步；USB替身显式丢弃取消数据余量，不能替代FunctionFS取消验证。进程退出由父进程检查原文件与单个临时残留；它不是断电或文件系统恢复测试。

临时路径登记仅本storage生命周期有效，失败unlink会保留登记避免同进程暴露，重新建库/重启后仍可能枚举残留。这一缺口不得描述为完整崩溃恢复；不按通用隐藏前缀删除未知用户文件。外部并发rename、父目录替换、真实挂载与SELinux仍需独立验证。

文件权限沿用上传策略FILE_PERM/FILE_GROUP，覆盖后目标为新inode，未保留旧inode的扩展属性/硬链接关系；旧路径上的其他硬链接继续指向旧内容。mtime沿用现有输入日期行为，epoch0作为缺值哨兵问题尚未修复。目录同步失败的MTP响应仍为成功，因为rename已提交完整新文件；日志说明断电持久性不确定，不能将其解释为可回滚失败。

0041维护注意：createSendObjectFile是IMtpDatabase新增的必需接口，当前唯一实现TwrpMtpDatabase转交所属storage；临时文件登记与inotify处理共享tree_mutex_。不得仅修改server为mkstemp而绕过登记，否则observer可能发布半成品。目录列举和overflow重建也必须保留精确路径过滤。


MTP原子上传交付收尾：同镜像六版本双槽9组/102次阶段调用通过，727来源保持一致、维护文件76+1+3重建且0待更新；与610f4acc候选仅MTP库字节改变。当前审计logs/mtp-atomic-delivery.json。进程退出临时残留、目标断电/USB和完整调用链仍未完成，震动与现场设置尚未解决，完整12组继续进行中。
