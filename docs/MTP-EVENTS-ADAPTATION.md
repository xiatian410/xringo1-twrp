# MTP 事件请求、退出与重连

补丁：[0023-mtp-event-lifecycle.patch](../dtsrc/O1_asic_dual/0023-mtp-event-lifecycle.patch)。当前镜像和哈希见[模拟报告](../simulation-report.md)。只运行主机夹具，没有连接手机。

## 问题和实现

此前每个事件创建一个线程，线程直接写 interrupt endpoint；close 先 join 所有线程，再关闭端点。端点停止接收时，写入和 join 都可能一直等待。线程对象也一直积累到关闭，多个写入的提交顺序没有保证。

仅增加 O_NONBLOCK 不足以解决此问题：[Linux v6.6 FunctionFS](https://raw.githubusercontent.com/torvalds/linux/v6.6/drivers/usb/gadget/function/f_fs.c) 的同步请求提交后仍等待完成，异步请求另有取消路径。本地保存了[参考源码](../logs/mtp-events-linux-v6.6-f_fs.c)；这是上游实现参考，不是五版 XRing 厂商内核逐行等价证明。

原生和兼容传输现在共用一个事件工作线程、最多 128 个排队事件和一个正在发送的请求。每个事件复制到独立缓冲区，最长 512 字节；无效长度/空指针拒绝，队列满返回 EAGAIN，关闭后返回 ESHUTDOWN。生产服务端已有错误日志，入队返回成功只表示接受发送，不表示电脑已经收到。

事件端点使用独立的单请求 Linux AIO context，打开为非阻塞；eventfd 同时承载新事件、完成和停止唤醒。依次提交保持顺序，提交或完成阶段的 EINTR/EAGAIN 均有期限地重试；完成通知先排空再等待，避免端点仍堵塞时忙循环。单事件期限为两秒，超时、永久错误或短完成会停止事件工作线程、丢弃未发送队列、撤销 MTP ready；后续发送明确报错。短完成不补发尾部，以免把不完整 USB 事件当作新的容器。

close 先阻止生产者入队并唤醒工作线程；工作线程取消在途请求并回收 AIO context 后才释放缓冲区。取消可能异步完成，或与正常完成竞争，因此依赖 io_destroy 的内核回收语义，不通过 detach、关闭后复用 fd 或提前释放缓冲区逃避等待。正常退出、析构和失败启动均清理资源；start/close 串行化，重复 start 返回 EBUSY。重连只使用新一代队列。

## 主机验证

[62 项最终报告](../logs/mtp-events.json)通过，[同一测试的旧源码结果](../logs/mtp-events-before.json)有 56 项失败；其中顺序/并发场景的旧版失败可能受调度影响，不能把失败数量当作固定缺陷数。每个场景分别运行原生与兼容实现，编译实际 MtpFfsHandle、MtpFfsCompatHandle、描述符及 libasyncio，启用 ASan/UBSan/LSan。

| 范围 | 验证内容 |
|---|---|
| 顺序与所有权 | 64 个连续事件、调用后覆盖原缓冲区、四个并发生产者；逐字节确认事件内容和唯一性 |
| 输入/生命周期 | 零/超大长度、转换为 size_t 的负值、空指针；启动前、关闭后、重复关闭、重复启动 |
| 积压/退出 | 填满 interrupt 管道后关闭或析构；180 次入队验证上限；发送与关闭竞争；重新附加端点后无旧事件 |
| 请求失败 | 端点断开、提交 EINTR/EAGAIN/EIO、完成 EINTR/EAGAIN、短完成、错误完成、两秒期限；堵塞后主机恢复接收 |
| 取消 | 请求保持在途；同步取消、异步取消、完成抢先导致 EINVAL 三种边界，回收后关闭 |
| 启动失败 | 单请求 AIO context 创建失败、端点 fcntl 失败；ready 撤销及资源清理 |

普通事件通过实际主机 AIO/管道传输。管道不能模拟 USB 控制器的挂起请求，因此在途完成、取消竞争和指定错误通过 AIO 边界替身注入；队列、线程、截止时间、生产者锁和缓冲区生命周期执行生产代码。阻塞失败夹具由独立测试进程的五秒期限终止，不终止工作区或构建进程。

第一版事件候选仅重试提交错误，在完成结果返回临时错误时过早停止。[6 项补充负向回放](../logs/mtp-events-completion-before.json)全部失败，修复后纳入本组 62 项。`recovery-dijun-unified-mtp-events.img` 是这一中间版本；该阶段候选为 `recovery-dijun-unified-mtp-events-r2.img`；最新 USB 候选见模拟报告。

原有 [MTP 文件传输](../logs/mtp-transport-regression.json)、[42 项对象/会话](../logs/mtp-objects.json)、[48 项移动/复制](../logs/mtp-transfers.json)在当前源码上通过。对象数据库测试仍使用内存 USB 对端，其通过不能替代本组传输退出检查。

```bash
python3 tests/mtp_events_test.py
python3 tests/mtp_events_test.py --source backups/mtp-events-pre-fix --report logs/mtp-events-before.json
python3 tests/run_mtp_transport.py
```

第二条是负向对照，预期非零；失败场景数不等于独立缺陷数。

## 使用和未完成项

使用入口仍是挂载/存储页面的 MTP 开关，无需选择原生或兼容事件模式。事件发送失败会记录 `MTP interrupt event worker stopped`；队列拥塞或发送失败时不能把缓存目录视为电脑已同步完成，应停止当前传输并重新枚举。

本组验证生产传输层在模拟边界下的退出，不证明实际 UDC 的取消期限。内核驱动若不兑现取消/回收语义，用户态不能据此保证绝对时间上限。Windows 枚举、物理 USB 拔插与控制器行为仍为 U。

Android init/configfs 的属性队列、双 ready 顺序、ready 撤销后的解绑及 ADB 恢复已有后续独立调度夹具；仅看到 ready=0 不证明 USB 配置已切换。USB 控制请求、解密后存储发布、媒体格式/日期和覆盖上传的原子提交也仍未完成。整项 MTP 和总目标保持进行中；本补丁不改变震动硬件的未验证状态。

后续 [USB configfs 与服务交接](USB-CONFIGFS-ADAPTATION.md)使用真实 init 调度和生产 helper 完成 42 项回放；实际 USB 控制器、Windows、完整旁加载和 MTP 调用者确认仍不由此证明。

后续[控制报文与事件批次](MTP-CONTROL-ADAPTATION.md)补充 66 项验证；实际 UDC、bulk AIO 回收、兼容模式 ep0 调度和取消/复位整合仍未完成。
