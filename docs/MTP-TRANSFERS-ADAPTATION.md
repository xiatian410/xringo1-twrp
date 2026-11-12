# MTP 移动、复制与目录重建

日期：2026-11-11。补丁：[0022-mtp-transfer-reconciliation.patch](../dtsrc/O1_asic_dual/0022-mtp-transfer-reconciliation.patch)。当前镜像、哈希与分层验收见[模拟报告](../simulation-report.md)。本组没有连接手机或执行物理 USB 操作。

## 实现变化

原数据库的移动、复制和 rescan 都返回未实现。CopyObject 的 begin 返回类型是 16 位响应码，却被当作 32 位对象句柄；end 还把非零响应码隐式转为成功布尔值。现在数据库提供一个带独立结果句柄的 `transferObject` 操作，服务端直接返回其结果，消除拆分回调的状态歧义。

操作期间同时锁住源和目标存储树，阻止 inotify 把移动中的对象先删除、再分配新句柄。移动保留顶层与已缓存子项的句柄及持久 UID，更新存储 ID、父目录、属性和监视路径；复制分配新句柄。重复目标、无效父目录、跨存储父句柄、把目录移入自身子树等请求均拒绝。

文件操作用目录 fd 锚定递归访问，父路径和源文件使用 `O_NOFOLLOW`，不沿符号链接读取外部文件。复制通过排他创建拒绝覆盖，累计 sendfile 短传输，重试 EINTR，零进展、ENOSPC、文件长度/修改时间变化、fsync 与 close 错误均返回失败。目录递归检查每个普通文件的大小上限，保留修改时间，文件权限按 MTP 的媒体访问常量设置；这不是备份权限/xattr 复制实现。

移动优先使用 `renameat2(RENAME_NOREPLACE)`；遇到 EXDEV 才复制并同步目标，然后删除源。源删除失败时保留完整目标副本并返回失败，重建两个目录以反映实际文件状态。源目录可能已经部分删除，不能承诺回滚；用户应检查两边内容再继续。目标已完成但父目录 fsync 失败时也返回失败，完整副本可能已经可见。

`rescanFile` 按已知对象路径刷新属性，拒绝把不相关路径绑定到已有句柄。队列溢出会重读已缓存目录，移除消失或类型改变的项、发现新增项并保持未变化的句柄；只为实际变化生成事件。根目录移走/删除后清空旧项，路径恢复后可重新枚举和监视。对象信息和路径查询不再把消失或被替换成符号链接的文件报告成零字节普通文件。

## 验证与复现

[48 项报告](../logs/mtp-transfers.json)通过；[旧源码同组对照](../logs/mtp-transfers-before.json)有 36 项失败。测试使用实际 MTP server、packet、database、storage 和文件工具，独立 chroot 内真实文件、inotify、线程与 fd；仅 USB 对端、日志/属性和指定故障系统调用是替身。ASan/UBSan 启用，LSan 因 chroot 内无法访问 `/proc` 而关闭。

| 范围 | 本组覆盖 |
|---|---|
| 复制与内容 | 单文件、目录、空目录、同存储子目录；逐字节核对内容，原件保留、新句柄可查询 |
| 移动 | 同目录不变、同存储、两个存储、模拟 EXDEV、目录子项句柄保持、移动后继续观察新增文件、修改后持久 UID 保持 |
| 拒绝与失败 | 重名文件/目录、父目录/存储/对象无效、根对象、目录循环、符号链接/FIFO、父路径被替换、文件大小上限 |
| 复制 I/O | sendfile 短传输/EINTR/零返回/ENOSPC、目录中途失败、文件 fsync/close、目标父目录 fsync 失败 |
| 移动失败 | rename 拒绝、源文件删除失败、源目录部分删除失败；完整副本仍可访问，错误不伪装成功 |
| 重建 | rescan 元数据/文件消失/路径不匹配；注入 IN_Q_OVERFLOW 后核对根与已缓存子目录；根目录删除及重建 |

EXDEV 通过 syscall 包装注入，因为夹具源与目标位于同一个主机文件系统；后续复制、同步、删除和数据库重建执行真实代码。溢出测试先消费并丢弃指定 inotify 事件，再向生产事件处理器注入一个真实格式的 IN_Q_OVERFLOW 记录，不靠修改数据库来制造通过。对照中的失败数量不代表独立缺陷数量。

原有[42 项对象用例](../logs/mtp-objects.json)在当前代码上再次通过，同一新版测试驱动的[旧对象实现](../logs/mtp-objects-before.json)仍有 28 项失败。其删除故障注入同时覆盖 unlink 和新的 unlinkat，避免系统调用变化后原测试失去作用。

```bash
python3 tests/mtp_transfers_test.py
python3 tests/mtp_transfers_test.py --source backups/mtp-transfers-pre-fix --report logs/mtp-transfers-before.json
python3 tests/mtp_objects_test.py
```

第二条预期非零。所有写入限制在驱动创建的私有目录，不使用主机物理盘或手机分区。

## 使用和仍需验收的边界

从[挂载/存储页面启用 MTP](../FEATURE-USAGE.md)，在电脑文件管理器中复制、移动已解密并发布的媒体文件。目标已有同名项时本实现拒绝覆盖；应先改名或明确处理旧文件。复制成功有新对象句柄，移动成功保留原对象身份。

这组不验证 Windows 枚举、真实 USB 取消、Android configfs/双 ready 时序或解密后目录发布。后续 [0023 事件生命周期](MTP-EVENTS-ADAPTATION.md)改为单工作线程、有限队列及可取消 AIO，62 项主机回放通过；实际 UDC 仍未验证；configfs 调度另有后续独立回放。前述树锁保护只覆盖本进程的观察者，不等于外部程序无法在操作中修改路径；目录内容并发变化、源部分删除与断电不提供事务回滚。普通文件格式仍为通用类型，完整媒体属性/日期协议和上传覆盖的原子提交另列待办。

原厂内核、MiTEE、UFS、物理电机与真实触摸唤醒均未由这些 MTP 用例验证。

后续 [USB configfs 与服务交接](USB-CONFIGFS-ADAPTATION.md)使用真实 init 调度和生产 helper 完成 42 项回放；实际 USB 控制器、Windows、完整旁加载和 MTP 调用者确认仍不由此证明。
