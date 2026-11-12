# MTP 控制报文、事务取消与 Reset

本文按控制报文、活动事务匹配和 Reset 会话释放收录实现记录。各阶段的未覆盖项只代表当时边界；后续补充见对应小节，完整 USB 集成状态以工作队列为准。

2026-11-12 后续0045已补充[Reset服务器会话释放](MTP-CONTROL-ADAPTATION.md#reset-session)，当前候选为mtp-reset（046ab9e3…）；下文Reset未实现的描述是本阶段历史边界。真实端点/bulk取消与残余包/旧事件队列仍待整合，不以此次软件检查证明真实USB。

后续0044已加入[活动事务匹配](MTP-CONTROL-ADAPTATION.md#transaction-cancel)：当前73项控制检查覆盖空闲/不同ID/结束后Cancel不再中断，原有66项为本阶段历史结果。服务器生命周期在独立真实server/USB peer检查中覆盖；Reset、DeviceBusy、bulk取消及compat ep0仍待整合，未验证真实USB。

补丁：[0025-mtp-control-framing.patch](../dtsrc/O1_asic_dual/0025-mtp-control-framing.patch)。当前候选和哈希见[模拟报告](../simulation-report.md)。本阶段不连接手机。

## 修复内容

旧实现要求状态查询至少分配 8 字节，并把 `sizeof(st)`（指针大小）写入回复长度；在 64 位环境，正常状态误报 8 字节，取消状态又加到 12 字节，但实际只分配主机请求的空间。正常的 4 字节查询会失败，8 字节取消查询还可能越界。旧实现也忽略控制传输短读、短写和系统调用失败，不支持的 IN 请求会回复零数据。

现在用固定的小缓冲区生成回复：正常状态 4 字节，取消状态沿用当前 AOSP 的两个 16 位端点参数，共 8 字节，所有字段按小端编码。发送量不超过主机 `wLength`；主机先读头部、发送失败或 SETUP 被替换时，取消状态保留到完整回复发送成功。端点地址读取当前速度的 `FUNCTIONFS_ENDPOINT_DESC` 并验证方向/类型/地址；不用上游可能返回 255 的 `ENDPOINT_REVMAP` 值伪造地址。

严格检查请求类型、方向、接口、保留值以及 Cancel/Reset 长度。不支持的 SETUP 在消费 OUT 数据前，通过 FunctionFS 的反向 ep0 访问返回 STALL。成功发出 STALL 的 `EL2HLT` 不作为服务端退出原因；`EIDRM` 表示主机已替换 SETUP。EINTR 可以重试，短控制报文不能靠下一次 read/write 拼接，永久错误向调用者返回。

Cancel 数据要求 6 字节和 `0x4001` 取消码；Reset 要求零数据并完成零长度确认。这两种有效请求暂时保留原有 `ECANCELED` 中断契约，**没有因此实现交易 ID 匹配或完整会话复位**。

事件读取检查 EOF 和记录长度。批次内继续处理待回应的 SETUP，但后续 ENABLE 不再抹掉早先的取消/错误；DISABLE/UNBIND 优先返回断开，防止旧传输被同批重新启用事件复活。

## 依据

- [USB-IF 原规范及 2007-03-16 勘误](https://usb.org/sites/default/files/usb_still_img10.zip)：§5.2 规定控制请求布局，勘误将 `wIndex` 修正为实际接口号。本机 FunctionFS 描述符使用局部接口 0，内核会把组合设备上的主机接口号反向映射到它。并非要求电脑侧 MTP 永远占接口 0。
- [Linux v6.6 FunctionFS 实现](https://raw.githubusercontent.com/torvalds/linux/v6.6/drivers/usb/gadget/function/f_fs.c)：`ffs_func_setup`、`__ffs_ep0_stall`、ep0 read/write 和 endpoint ioctl 的行为。本地[来源与哈希](../logs/mtp-control-references.json)可复核；不是五版厂商内核等价证明。
- 状态端点参数保留 AOSP 现有的 16 位表示；原规范表 5.2-7 未固定此参数宽度。本阶段没有用 bulk 容器的 32 位参数规定替换控制请求布局，也没有声称完成 Windows 互操作验证。

## 离线验证

[66 项生产代码回放](../logs/mtp-control.json)全部通过；[修改前同组回放](../logs/mtp-control-before.json)有 60 项失败。失败数包含相同缺陷的不同输入，不是 60 个独立硬件问题。测试启用 ASan/UBSan/LSan，直接调用实际 `handleControlRequest` 和 `handleEvent`；仅替换 ep0 read/write、端点 ioctl，模拟一次 SETUP 对应一次数据阶段的内核边界。

| 范围 | 场景 |
|---|---|
| 状态报文 | 0～65535 字节请求、正常/取消回复的逐字节结果、先读头后读完整回复 |
| 发送和端点 | EINTR、短写、EIO、EAGAIN、SETUP 替换、描述符失败/错误方向/零地址/保留位/类型 |
| 请求拒绝 | 错误 recipient/type/index/value、未知及扩展请求、错误方向、Cancel/Reset 长度 |
| OUT 数据 | 正常取消/复位、错误取消码、短读、EINTR、失败、SETUP 替换 |
| 事件批次 | EOF、短记录、错误/暂不可读、挂起恢复、断开→启用、取消→启用、断开与状态查询同批 |

复现命令：

```bash
python3 tests/mtp_control_test.py
python3 tests/mtp_control_test.py --source backups/mtp-control-pre-fix --report logs/mtp-control-before.json
```

第二条是预期失败的负向对照。既有事件、文件传输、对象和移动/复制回归在最终源码上重新执行，报告继续绑定源文件哈希。

## 剩余范围

本阶段只解决报文解析、回复及事件批次错误保留。交易 ID 精确取消、DeviceBusy 时序、Reset 清理服务器会话、bulk AIO 的取消/回收、兼容传输 ep0 调度仍需整合回放。实际控制器的 STALL/CLEAR_FEATURE 时序也不由主机替身证明。

MTP 启停调用者对进程存活/USB 状态的确认、解密后目录发布、覆盖上传原子性及媒体日期仍待完成。目标保持进行中；震动、真实硬件解密、Windows 枚举与快速唤醒延迟保持硬件未验证。

<a id="reset-session"></a>

## Reset 与服务器会话释放

2026-11-12。此前Reset和匹配Cancel都只返回ECANCELED，服务器会继续使用旧session。电脑复位后重新OpenSession会收到SESSION_ALREADY_OPEN，未完成的SendObjectInfo与编辑资源也可能保留。

维护补丁`patches/0045-mtp-reset-session.patch`增加独立的Reset信号。FunctionFS只在合法零长度OUT确认成功后置位；失败/被替换的SETUP以及Cancel不置位。信号未被服务器消费时GetDeviceStatus回复4字节DeviceBusy，消费后恢复OK；此前设备取消状态在Reset时清除。此处Busy只覆盖待消费信号，不代表完整硬件复位期间的状态机。

服务器在命令/数据读写与请求处理边界消费信号，由服务器线程释放旧session：停止新通知，撤销尚未完成的上传预留，清空数据/响应状态，重新扫描已打开的编辑对象并关闭其描述符。已写入的编辑字节不回滚，已成功发布的文件不删除。存储和数据库保持注册，下一条需session的请求得到SESSION_NOT_OPEN；重新OpenSession后可继续上传。Reset本身不发送MTP事务响应。原/dev/mtp_usb transport默认不产生用户态Reset信号，内核路径不变。

复位与断线同时返回时保留ESHUTDOWN等终止错误，释放后退出；不能因处理Reset吞掉断线而等待下一请求。首个候选实现曾在新增断线用例失败，已修正并重新installclean构建，首个构建不是交付产物。

离线证据：

- [控制请求80项](../logs/mtp-reset-control.json)：合法Reset信号、消费一次、DeviceBusy→OK、清除旧取消、失败/替换SETUP不发信号、Cancel不发Reset及Reset+DISABLE。旧实现同80项中3项失败。
- [服务器/数据库78项](../logs/mtp-reset-server.json)：真实生产server/packet/database和私有文件。新增10项覆盖空闲、未完成新建/覆盖、data-in/data-out/response、receive/send、编辑及断线；旧代码10项中9项失败，断线场景原来即可退出。恢复会话、抑制旧通知/旧事务响应、保留原文件、清除staging与再次上传均检查。
- [移动复制48项](../logs/mtp-reset-transfers.json)、[native/compat事件62项](../logs/mtp-reset-events.json)、[传输往返](../logs/mtp-reset-transport.json)回归通过。

控制和服务器使用不同USB替身，尚未把真实FunctionFS控制请求、bulk AIO取消/回收和服务器连成同一会话。compat ep0派发、队列中旧事件的撤回、复位后bulk残余包/端点halt清理、真实UDC/Windows仍未验证。server在同步操作返回后才消费信号；没有强行终止已开始的内核/文件I/O。测试启用ASan/UBSan；chroot服务器场景禁用无法访问/proc的LSan。不存在手机命令或实机验证。

候选`recovery-dijun-unified-mtp-reset.img`已按用户要求installclean后`make -j$(nproc)`30并发构建，哈希和最终审计以simulation-report.json及logs/mtp-reset-delivery.json为准。本轮只修正MTP软件缺口，震动与设置故障未解决，全目标保持进行中。

复现：`python3 tests/mtp_control_test.py --report logs/mtp-reset-control.json`、`python3 tests/mtp_objects_test.py --report logs/mtp-reset-server.json`。负向对照使用`--source backups/mtp-reset-pre-fix`与独立报告；服务器对照只选10个reset场景。交付审核入口`python3 scripts/audit_mtp_reset_delivery.py`。

<a id="transaction-cancel"></a>

## 取消请求与活动事务匹配

2026-11-12 后续0045已补充[Reset服务器会话释放](MTP-CONTROL-ADAPTATION.md#reset-session)，当前候选为mtp-reset（046ab9e3…）；下文Reset未实现的描述是本阶段历史边界。真实端点/bulk取消与残余包/旧事件队列仍待整合，不以此次软件检查证明真实USB。

2026-11-12。此前 FunctionFS 验证 Cancel 的 6 字节长度和 `0x4001` 取消码，却忽略其后 4 字节事务 ID，所有合法 Cancel 都以 `ECANCELED` 中断当前操作。旧上传结束后的延迟取消可能打断新上传，空闲时的取消也会被当成传输中断。

维护补丁 `patches/0044-mtp-transaction-cancel.patch` 增加服务器拥有的事务生命周期。解析命令后、进入数据阶段之前调用 `beginTransaction(id)`，作用域结束时调用 `endTransaction()`，覆盖响应、continue、break 和正常完成。FunctionFS 仅对活动 ID 相同的 Cancel 保留中断契约；空闲或 ID 不同的请求消费一次 OUT 数据阶段后正常返回。活动标志与完整 32 位 ID 一起原子读取，ID 0 不与空闲混淆，也不截断高位。旧 `/dev/mtp_usb` transport 的默认生命周期方法为空，其内核控制请求处理不变。

[73 项真实控制请求检查](../logs/mtp-transaction-control.json)通过：原有 66 项加空闲、不同 ID、已结束、下一事务、ID 0、ID 0xffffffff 及高位不匹配。保存的旧源码运行相同测试时有 [5 项失败](../logs/mtp-transaction-control-before.json)，均为不应中断却返回 ECANCELED；旧源码缺少生命周期接口时测试适配器显式不调用该接口，不代替其控制请求实现。

[68 项服务器/数据库检查](../logs/mtp-transaction-server.json)执行真实 `MtpServer::run` 和私有文件操作，在 USB peer 边界记录 begin/end，断言所有返回后的活动状态清零且生命周期成对。另有 [48 项移动/复制](../logs/mtp-transaction-transfers.json)、[62 项 native/compat 事件检查](../logs/mtp-transaction-events.json)及[传输往返](../logs/mtp-transaction-transport.json)通过。主机检查启用 ASan/UBSan；ep0 和服务器 USB peer 是不同测试中的显式边界，没有把它们说成一次真实主机取消会话。

最终镜像为 `recovery-dijun-unified-mtp-transaction.img`，SHA256 `da614695843c1c8f7dd8e1eabc747a65d4e5d755680ba1a0c1dbaeec08ac79b8`。已执行 installclean 和 `make -j$(nproc)`，30 并发构建成功；734 份来源与镜像封装核对，后续同镜像 profile 回放结果见交付审计。与上一 haptics-probe 候选对比，封装检查记录的核心二进制只有 `libtwrpmtp-ffs.so` 改变。

本项不完成 Reset 的服务器会话清理、DeviceBusy 状态时序、bulk AIO 取消回收或 compat ep0 调度。服务器尚未解析出命令时没有活动事务；不把空闲取消处理当成部分命令恢复验证。未验证真实 UDC、Windows 枚举或手机传输，也没有修改震动播放、校准或触摸策略。震动、设置现场故障和完整适配目标仍未完成。

复现：`python3 tests/mtp_control_test.py --report logs/mtp-transaction-control.json`；负向对照增加 `--source backups/mtp-transaction-pre-fix` 和独立报告路径。完整交付核对入口为 `python3 scripts/audit_mtp_transaction_delivery.py`。此次定向审计不替代仍被历史来源漂移阻断的 `audit_unified_delivery.py` 全量审计。
