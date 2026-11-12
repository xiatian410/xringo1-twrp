# MTP 启停、状态与存储消息离线适配

本轮执行实际管理器函数、实际 ForkServer/Start、实际存储接收循环，使用主机进程、线程、socket、信号与 wait；Android 属性/USB 配置完成和存储对象接收端使用替身。没有连接手机或执行真实 UDC。

[调用层报告](../logs/mtp-caller.json) 40 项通过，同一测试在[保留旧源码](../logs/mtp-caller-before.json)有 24 项失败；[接收端报告](../logs/mtp-receiver.json) 11 项通过，[旧源码](../logs/mtp-receiver-before.json)有 4 项失败。失败数量是用例数，不等于独立缺陷数。ASan/UBSan 覆盖主机执行。

启动现在核对受管理子进程、USB 请求、实际配置状态和 FunctionFS ready，八秒内未确认则返回失败并请求恢复 ADB。重复启动只复用仍存活且已确认的实例。旧式 android_usb 路径保留配置状态检查，不要求其不提供的 FunctionFS ready。

关闭先撤销界面状态，确认子进程归属后发送 SIGKILL，最多等待两秒；无法确认归属或退出超时保留 PID，禁止新建重叠实例。ADB 配置最多等待五秒确认，属性失败和配置错误向调用者返回失败。此期限只约束相应等待循环；挂载、执行器排队和调度仍不属于严格的端到端期限。

状态读取使用 try-lock 和非阻塞子进程观察，不在 GUI 线程等待启动/关闭；它核对当前进程与 USB 状态，属于瞬时快照。管理器按操作事务锁→MTP 锁的顺序串行修改，进程工具要求本管理器是该子进程的唯一回收者；不能把此实现当作支持任意外部 reaper 的 PID 句柄。

存储消息使用 SOCK_SEQPACKET，send 带 MSG_NOSIGNAL/MSG_DONTWAIT，避免接收端退出杀死 recovery 或满队列阻塞。短发送和失败返回 false。接收端重试 EINTR，拒绝长度错误及未终止的字符串。消息发送成功只表示入队，不表示数据库已接纳；队列重试、AddAll 每项结果汇总、解密后发布确认仍待补。

子进程定期检查 recovery 父进程关系，父进程退出后主动退出。没有使用 PR_SET_PDEATHSIG：Linux 将其绑定到创建线程的退出，而 MTP 可能由临时操作线程启动。真实线程回放已覆盖“启动线程结束后 MTP 仍存活”，子收割器夹具覆盖实际父进程退出。检测周期 250 ms，实际调度可能延后。

[补丁](../dtsrc/O1_asic_dual/patches/0026-mtp-caller-lifecycle.patch)可从固定源码基线重建。[当前模拟报告](../simulation-report.md)绑定镜像、构建来源与 53 项二进制策略检查，含 recovery 的 socket 与 fork/signal 权限。没有修改 recovery 域权限来掩盖错误。

复查命令：

```bash
python3 tests/mtp_caller_test.py
python3 tests/mtp_receiver_test.py
python3 tests/mtp_caller_test.py --source backups/mtp-caller-pre-fix --report logs/mtp-caller-before.json
python3 tests/mtp_receiver_test.py --source backups/mtp-caller-pre-fix --report logs/mtp-receiver-before.json
```

后两条是负向对照，预期返回非零。测试超时清理其独立进程组，避免故障夹具遗留子进程。

尚未完成完整 GUI/挂载/init/解密后发布端到端联调；临时工作线程与真正进程退出的测试不代表整套 fork 后 C++ 库在任意并发负载下无锁风险。完整交易取消、会话 reset、compat ep0 调度、bulk AIO drain、真实 USB/Windows 枚举仍保持独立未完成项。物理震动、TEE 与唤醒延迟也不由本组用例证明。
