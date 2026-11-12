# MTP 取消请求与活动事务匹配

2026-11-12 后续0045已补充[Reset服务器会话释放](MTP-RESET-SESSION.md)，当前候选为mtp-reset（046ab9e3…）；下文Reset未实现的描述是本阶段历史边界。真实端点/bulk取消与残余包/旧事件队列仍待整合，不以此次软件检查证明真实USB。

2026-11-12。此前 FunctionFS 验证 Cancel 的 6 字节长度和 `0x4001` 取消码，却忽略其后 4 字节事务 ID，所有合法 Cancel 都以 `ECANCELED` 中断当前操作。旧上传结束后的延迟取消可能打断新上传，空闲时的取消也会被当成传输中断。

维护补丁 `patches/0044-mtp-transaction-cancel.patch` 增加服务器拥有的事务生命周期。解析命令后、进入数据阶段之前调用 `beginTransaction(id)`，作用域结束时调用 `endTransaction()`，覆盖响应、continue、break 和正常完成。FunctionFS 仅对活动 ID 相同的 Cancel 保留中断契约；空闲或 ID 不同的请求消费一次 OUT 数据阶段后正常返回。活动标志与完整 32 位 ID 一起原子读取，ID 0 不与空闲混淆，也不截断高位。旧 `/dev/mtp_usb` transport 的默认生命周期方法为空，其内核控制请求处理不变。

[73 项真实控制请求检查](../logs/mtp-transaction-control.json)通过：原有 66 项加空闲、不同 ID、已结束、下一事务、ID 0、ID 0xffffffff 及高位不匹配。保存的旧源码运行相同测试时有 [5 项失败](../logs/mtp-transaction-control-before.json)，均为不应中断却返回 ECANCELED；旧源码缺少生命周期接口时测试适配器显式不调用该接口，不代替其控制请求实现。

[68 项服务器/数据库检查](../logs/mtp-transaction-server.json)执行真实 `MtpServer::run` 和私有文件操作，在 USB peer 边界记录 begin/end，断言所有返回后的活动状态清零且生命周期成对。另有 [48 项移动/复制](../logs/mtp-transaction-transfers.json)、[62 项 native/compat 事件检查](../logs/mtp-transaction-events.json)及[传输往返](../logs/mtp-transaction-transport.json)通过。主机检查启用 ASan/UBSan；ep0 和服务器 USB peer 是不同测试中的显式边界，没有把它们说成一次真实主机取消会话。

最终镜像为 `recovery-dijun-unified-mtp-transaction.img`，SHA256 `da614695843c1c8f7dd8e1eabc747a65d4e5d755680ba1a0c1dbaeec08ac79b8`。已执行 installclean 和 `make -j$(nproc)`，30 并发构建成功；734 份来源与镜像封装核对，后续同镜像 profile 回放结果见交付审计。与上一 haptics-probe 候选对比，封装检查记录的核心二进制只有 `libtwrpmtp-ffs.so` 改变。

本项不完成 Reset 的服务器会话清理、DeviceBusy 状态时序、bulk AIO 取消回收或 compat ep0 调度。服务器尚未解析出命令时没有活动事务；不把空闲取消处理当成部分命令恢复验证。未验证真实 UDC、Windows 枚举或手机传输，也没有修改震动播放、校准或触摸策略。震动、设置现场故障和完整适配目标仍未完成。

复现：`python3 tests/mtp_control_test.py --report logs/mtp-transaction-control.json`；负向对照增加 `--source backups/mtp-transaction-pre-fix` 和独立报告路径。完整交付核对入口为 `python3 scripts/audit_mtp_transaction_delivery.py`。此次定向审计不替代仍被历史来源漂移阻断的 `audit_unified_delivery.py` 全量审计。
