# MTP 目录上传时间与完成状态

维护补丁0059修正两个相连的问题：`SendObjectInfo`解析了目录修改时间却未应用；目录已经结束后又将其保存成等待`SendObject`的文件传输。普通电脑通常不为目录发送文件数据，旧状态会在下一条命令被当作放弃的上传清理。

现在创建或接纳目录后，使用`O_DIRECTORY | O_NOFOLLOW`打开目录fd，应用有效修改时间（包括Unix零秒、负秒与时区偏移），再刷新数据库。目录不进入文件传输等待状态。时间缺失或非法时不设置日期。打开目录、设置时间或关闭失败时返回错误并释放数据库传输保护；已有目录和子文件保留，允许重试。错误不承诺撤销已成功的元数据写入，也不承诺删除刚建的目录。

验证执行原始server、packet、database和storage，使用私有chroot真实文件、inotify与线程，USB及属性为替身。16项新增场景覆盖日期边界、已有目录、open/futimens/close故障、失败重试、无日期目录后的意外SendObject、后续普通命令与无日期文件上传。还核对现存目录内容与数据库日期。修正前同一测试源码16项有14失败；当前对象链路110项、move/copy转移48项通过，ASan/UBSan检查启用。

```bash
python3 tests/mtp_objects_test.py --report logs/mtp-directory-objects.json
python3 tests/mtp_transfers_test.py --report logs/mtp-directory-transfers.json
python3 scripts/audit_mtp_directory_delivery.py
```

2026-11-12最终候选`recovery-dijun-unified-mtp-directory.img`，SHA256 `215914df1f8768bf00272f5c10c03b90fa8e624e9b1337fa6801a0ef3e5155b0`。按installclean后`make -j$(nproc)`（30并发）构建，765来源及六profile封装核对；镜像仅保留本地。完整报告在本地`logs/mtp-directory-*.json`，公开摘要为`docs/CURRENT-VALIDATION.json`。

目录时间在本次SendObjectInfo阶段生效。后续创建子文件会由文件系统更新父目录时间，MTP当前没有整棵树结束时重放目录日期的协议实现；这项仍未完成。没有测试真实USB/Windows、Android ARM64 MTP运行或断电；跨重启`.mtp-upload-*`临时文件回收也仍缺少持久归属证明，不能按名字前缀删除未知用户文件。完整12组适配目标保持进行中。
