# 刷新容量页面不结束：现场分析

2026-11-13 用户提供 `refresh-stuck-20261113-002627.zip`。原始日志只保留本地，不上传公开仓库。它包含 recovery.log/recovery-after.log、线程栈、线程列表、logcat、dmesg；只有一组线程栈，没有 GUI 截图、用户态栈或提交时间线。

## 已确定

- recovery.log 第1279行启动 Refreshing Sizes，第1288行记录 Data backup size is 95.0 GB，第1289行完成，第1290行 `operation_end - status=0`。
- 邻近单调时钟为67535ms和72682ms；因此该次刷新从开始到操作结束不超过约5.15秒。不能用采集时仍显示的文字推断容量扫描持续到338秒。
- 两份 recovery 日志相同；之后仍有输入相关亮度/反馈记录。不能将用户反馈“页面一直不结束”否定为没有问题，但现场不支持“仍在扫描”的判断。
- 338.12秒附近采集时，主Recovery进程主线程的内核栈经过 `kthread_flush_work` → `dpu_drm_atomic_commit` → DRM atomic ioctl。其他线程主要为Binder、futex、poll及定时等待；没有可辨认的刷新worker或目录扫描栈。
- 主线程 wchan 为 hrtimer_nanosleep，syscall为ppoll，而单独读取的stack为DRM ioctl。这些字段非原子读取，可能采到不同瞬间。因此**不能据此宣称驱动永久卡死，也不能直接切换DRM模式/加超时冒充修复**。

## 已核对的代码

备份按钮进入工具worker，`refreshsizes()`同步调用 `UpdateSystemDetails`。已挂载 Data 的同步目录统计会持存储操作锁，确有长时间等待风险，但不是本份日志已证实的根因。当前不改容量计算、不改变95.0GB结果，也不强行把异步快速估算替换成精确扫描。

工具worker在refreshsizes返回后将state发布为DONE，再清running；GUI每100ms轮询 `refresh_tool_progress`，生产 `update_progress`据终态修改summary、停止动画并显示完成操作。`tests/refresh_progress_test.py`实际执行原状态映射与LVGL进度组件，分别覆盖RUNNING→DONE、RUNNING→FAILED、页面首次轮询已DONE，三个场景文字和隐藏进度条均通过。**worker状态为显式输入、字体/显示flush为主机替身；此测试不能证明现场worker发布、页面轮询或DRM扫描输出正常。** 没有复现的软件缺陷就不修改该组件。

## 下一步与当前结论

当前缺陷仍为“刷新已结束但页面看起来仍在运行”，根因未确定。下一项需要区分：实际显示的是否为console的历史起始行、GUI是否收到DONE、DRM提交是否长期等待；不是继续重复目录扫描测试。若现有现场仍在，应优先保留当前页面截图、重复主线程栈/各自uptime和用户态调用位置证据；不要求重做容量刷新。代理不连接手机或物理块设备。

提供 [只读采集器](../tools/refresh-state-collector/README.md)，逐项超时保存两组线程/内核日志。Windows/手机上尚未执行验证。现阶段没有“修复刷新卡住”的新生产补丁或新镜像；当前ab-command候选是此前OTA命令修正，不能作为本故障修复版。

可复查本地报告：`logs/refresh-capture-analysis.json`、`logs/refresh-progress.json`。分析脚本 `scripts/analyze_refresh_capture.py`处理PowerShell UTF-16与UTF-8日志；输出包含原日志摘要和本地来源哈希，公开摘要只列结论，不上传设备原日志内容。
