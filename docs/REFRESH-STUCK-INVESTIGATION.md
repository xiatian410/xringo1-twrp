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

## 后台状态发布接续检查

`tests/refresh_worker_chain_test.py/.cpp`补查了先前由状态替身提供的边界：使用原`tools_backend`接口/`twrp_tools_backend`类、start/run/refreshsizes/status/acknowledge/join/析构方法、真实std::thread/互斥锁和原状态到页面映射，再接实际LVGL进度组件。三种调度通过：扫描先保持运行再结束、后台在建页前完成、完成确认后再次刷新。运行中第二次start被拒绝，acknowledge不会清除RUNNING，完成后副标题更新且进度条隐藏。

`UpdateSystemDetails`由条件变量控制的显式扫描边界替代；DataManager、operation_start/end与显示flush也是替身，未走的其他工具函数触达即失败。这是发布链范围的补充检查，不是完整GUI tick/页面路由、Android运行时或XRING DRM证明；原先三个状态输入场景证据保留，不重跑。没有据此修改生产或构建镜像。

源码还显示完成不会自动离开工具页面：它更新副标题并显示完成操作，等待用户返回；console的初始运行文字作为历史记录保留。没有现场截图，不能断定这就是用户看到的现象，也不能把用户反馈判成误解。

分析脚本同时修正PowerShell CRLF解析，原报告中的`main_drm_snapshot=null`现在能正确记录336主线程已有的DRM栈；这只修正分析输出，不改变原始日志或根因结论。

## 下一步与当前结论

当前缺陷仍为“刷新已结束但页面看起来仍在运行”，根因未确定。后续需要区分实际呈现的是否为 console 历史起始行、提交帧等待是否阻止后续轮询；主循环软件接续的有限结果见下文。只使用现有或用户后续自发提供的现场证据，不要求重做容量刷新。代理不连接手机或物理块设备。

提供 [只读采集器](../tools/refresh-state-collector/README.md)，逐项超时保存两组线程/内核日志。Windows/手机上尚未执行验证。现阶段没有“修复刷新卡住”的新生产补丁或新镜像；当前ab-command候选是此前OTA命令修正，不能作为本故障修复版。

可复查本地报告：`logs/refresh-capture-analysis.json`、`logs/refresh-progress.json`。分析脚本 `scripts/analyze_refresh_capture.py`处理PowerShell UTF-16与UTF-8日志；输出包含原日志摘要和本地来源哈希，公开摘要只列结论，不上传设备原日志内容。

## 本轮页面生命周期有限收尾

`tests/refresh_worker_chain_test.py --lifecycle`接续实际page_host/scaffold/router/PUSH/POP及动作行；运行后完成、建页前完成、8次循环重入均通过。动作行属于当前页面，完成后可返回；旧视图、动作和过渡阻挡随页删除，settle后只余一个页面。该测试的路由组装、tick、扫描和flush是显式替身，不是完整gui2主循环或DRM，没有复现现场根因。详见`logs/refresh-page-lifecycle.json`及[有限维护](archive/BOUNDED-MAINTENANCE.md)。原worker报告保留为历史，不重写其旧来源哈希。

0067 修改了共用工具 worker 的备份目录分支，因此原三种页面调度做了必要回归，均通过，报告为 `logs/backup-manage-refresh-lifecycle.json`。它取代本地旧生命周期报告的当前来源绑定；旧哈希仅为历史引用，不伪称旧报告与新源码一致。本批修复的是备份目录管理，现场刷新问题仍未解决。

## 工具日志分批渲染（0070）

本轮定位并修正一项独立的软件响应问题：工具进度页从游标 0 一次取出全部历史日志，并逐行创建 LVGL 标签、强制布局后才刷新状态。历史记录数量决定建页与轮询的同步工作量。这个路径与已有安装 / 解密页的有界日志窗口不一致；它可以拖延状态呈现，但现有现场采集没有测量 GUI 用户态耗时，不能认定它就是那次停留的唯一根因。

补丁 `0070-tool-console-bounded-window.patch` 复用现有 `console_window`：

- 首帧成功提交、页面种类与实例序号均匹配后才读取日志；页面删除、重建时清空窗口并撤销读取许可。
- 默认保留最多 160 个显示行，单次读取最多 24 项 / 4096 字节 / 64 条消息，每批应用最多 32 行；长行使用已有 UTF-8 分段。
- 初次进入从最近 160 项开始；向上滚动可回看旧内容，不删除 backend 历史。
- 状态更新先于日志读取；日志锁暂忙时，不阻止 DONE 状态更新。

`tests/tool_console_test.py` 执行原 worker/start/run/status、原进度适配器、原日志轮询方法、原 before_render/after_present 与实际 LVGL。六个场景覆盖 5000 项历史、建页前完成、日志锁忙、向上回看、日志代次变化、删除重建；全部通过。修正前六项均在首次无界读取断言失败，属于同一个缺陷的重复入口，不能计作六个独立缺陷。

```bash
python3 tests/tool_console_test.py
# 需本地保留的旧源码；预期失败：
python3 tests/tool_console_test.py --before
```

报告为本地 `logs/tool-console.json` 与 `logs/tool-console-before.json`。目录扫描、console 生产端、字体、flush 和测试调度是显式替身；没有执行完整 GUI 主循环、Android 或 XRING DRM。原生命周期结果保留为历史，不重写其来源。

当前候选为 `recovery-dijun-unified-tool-console.img`，SHA-256 `93a36568316d6b0acba348d63c524db8b424953acfbfae9154d09d9b89d79b90`。清理构建后有 785 项生产来源绑定、六份 profile；与 snapshot-sync 候选相比仅 `libgui2.so`、构建属性与 ramdisk 摘要变化。原容量计算与工具 worker 未改。本轮修复日志渲染工作量，现场问题仍记为未闭环，不宣称实机修复。

<a id="cli-fifo"></a>

## 主循环 CLI 输出握手阻塞（0077）

继续检查真实 `gui2_loop_tick` 时发现独立缺陷：工具终态轮询之前调用 `background->poll()`，后者在读到 CLI 请求后用 `fopen(orsout, "w")` 打开输出 FIFO。请求方未打开读取端或中途退出时，主线程会阻塞在 open，之后不再到达工具状态更新。已有现场材料未证明当时存在 CLI 请求，**不认定它就是刷新现场根因**，也不改变容量计算或 DRM。

0077 使用非阻塞、CLOEXEC 的 FIFO writer。读取端尚未连接时保存单个请求，后续 tick 重试；五秒后丢弃，不执行命令并重建监听。读取端连接后保持非阻塞写入，避免客户端不读导致共享 console 锁或 GUI 卡住。输出满时 stdio 可报 EAGAIN，CLI 镜像日志不保证完整；Recovery 自身日志仍保留。已开始的命令不会因读端消失而强制取消。忙状态和不支持的旧 GUI 命令仍返回原错误。

读取缓冲按实际 read 长度终止，不再读取未初始化字节或强制改写末尾两个字符。固定1024字节客户端保留兼容；一次短写按一次请求处理，本项不实现多客户端或跨read拼包协议。监听重新启动清除未派发请求，不让上次请求在新生命周期执行。

`tests/cli_fifo_test.py/.cpp` 执行原 background backend 完整 listener、poll、实际线程及完成回调，使用私有目录真实 FIFO/open/read/stdio/select，启用ASan/UBSan；DataManager、分区、console镜像接口和命令内容执行为显式替身。12场景涵盖无读端、延迟连接、普通/忙/不支持/短/最大长度命令、读端消失、超时恢复、连续请求、输出满与监听重启。全部通过；旧源码同组七项失败，其中五项为八秒进程期限触发，其余是最大命令被改写及输出未收尾。失败数量不是七个独立缺陷。

```bash
python3 tests/cli_fifo_test.py
# 依赖本地旧源码，预期失败：
python3 tests/cli_fifo_test.py --source logs/cli-fifo-before/twrp_background_backend.cpp --report logs/cli-fifo-before.json
python3 scripts/audit_cli_fifo_delivery.py
```

清理构建后候选为 `recovery-dijun-unified-cli-fifo.img`，793生产来源、六profile。相对0076只改变Recovery主程序、构建属性和ramdisk摘要，GUI库、工具worker及容量扫描字节未改，复用相关未变证据。没有执行手机、真实CLI命令、完整GUI/Android主循环或XRING显示；现场页面停留仍未闭环。当前产物哈希见[交付报告](../simulation-report.md)，原历史报告不改写。

<a id="gui-loop"></a>

## 原 GUI tick 与主循环接续

`tests/refresh_loop_test.py/.cpp` 补查已有生命周期夹具未执行的两个入口：原 `gui2_loop_tick` 与完整 `app/gui2_loop.cpp`。复用原工具 worker、状态适配器、LVGL 进度组件、page host 和路由组装，不再另测容量扫描算法或同类状态映射。

三个有限场景通过：

| 场景 | 结果 |
| --- | --- |
| 建页时仍运行，首轮提交后后台结束 | 后续原 tick 更新副标题、隐藏进度条并显示完成动作，提交边界观察到完成页面 |
| 建页前后台已完成 | 首次 tick / 提交即为完成状态 |
| 首轮提交人为等待 220ms，后台在等待期间完成 | 等待内 tick 计数不变，文字仍为运行；解除等待后下一轮 tick 更新完成状态 |

第三项用独立线程观察 worker DONE 与 GUI tick 计数；等待期间不跨线程访问 LVGL，显示替身在 GUI 线程恢复后核对旧文字。进程有外部 12 秒期限，内部主循环也有 5 秒期限，避免夹具永久等待。

```bash
python3 tests/refresh_loop_test.py
```

报告为本地 `logs/refresh-loop.json`，包含原源码、夹具、LVGL 库来源和编译命令。使用 UBSan。扫描、DataManager / 操作呈现、字体 / flush、输入、性能策略、提交门控、路由组装及不相关 GUI 服务为显式替身；后台 poll 和 console poll 仅计数，未重新验证 FIFO / 日志窗口。其他页面的进度轮询若意外进入会失败。**这不是完整 Android GUI 或真实 DRM 执行。**

该结果确认：在所述边界返回时，原 tick 与主循环能接到 DONE；提交等待可以使已完成的 worker 暂时无法呈现，但不证明现场有持久 DRM 阻塞。现场非原子内核栈不足以作此结论。下一步应使用能区分提交等待和历史文字的现场证据，不再增加同类 DONE / 扫描夹具，也不根据模拟等待切换 DRM 或加入猜测性超时。

本批只新增执行证据，无生产修正、无新补丁、无镜像重编；当前候选仍以交付报告为准。现场问题保持未解决。
