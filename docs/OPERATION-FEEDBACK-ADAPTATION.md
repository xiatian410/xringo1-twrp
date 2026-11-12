# 操作完成反馈的离线验证

日期：2026-11-11。当前候选与校验和见[模拟报告](../simulation-report.md)。本项检查任务结束时的震动请求、忙状态和屏幕唤醒通知，没有测试物理电机，也没有执行真实分区操作。

## 修改

[0017 补丁](../dtsrc/O1_asic_dual/0017-operation-completion-feedback.patch)仅修改 `gui2/backend/twrp_operation.cpp`。该文件由 recovery 可执行文件链接，不属于 `libgui2.so`。

| 原行为 | 当前行为 |
|---|---|
| 用系统日历时间计算耗时，校时可使短任务触发或长任务不触发 | 使用 `steady_clock`；超过 10 秒的任务请求操作反馈，恰好 10 秒不触发 |
| 多 ZIP 队列每项重新记录开始时间，最后一项较短时没有完成反馈 | 同一工作线程的重复 start 延续第一次开始的时间；整个队列结束一次 |
| 重复 end 会重复震动、发布完成通知和释放性能状态 | 没有该线程活动任务的 end 被忽略并记录；不同线程不能结束别人的任务 |
| 一个任务结束会清除其他工作线程的忙状态 | 用互斥锁和活动计数管理共享忙状态；最后一个任务结束才清除 |
| 完成属性一直保留为 1 | 首个活动任务开始时置 0，全部结束时置 1；该属性不表示成功 |
| 操作反馈直接读取 DataManager 数值，绕过 GUI2 后端的能力与范围限制 | 复用实际 hardware settings 后端的 ACTION 通道，检查设备可用性和禁用设置，限制 0–500 ms |

0 ms 关闭操作震动。设备晚注册时，下次请求重新检查；设备消失时不提交请求。系统时间的前后跳变不改变完成反馈阈值。

失败和取消也属于任务完成：若超过阈值，可以发出一次结束反馈。成功、失败、取消仍由各 backend 的 DONE/FAILED/CANCELLED 状态表达，不能用震动或 `twrp.action_complete=1` 判断结果。
后台只发布完成事件，实际 screen backend 的 UI tick 消费它并请求唤醒。多个完成事件发生在同一 tick 前时合并为一次唤醒，震动请求仍按任务分别计算。

## 64 项主机回放

[测试脚本](../tests/operation_feedback_test.py)编译完整生产 `twrp_operation.cpp` 和 `twrp_hardware_settings.cpp`，并提取实际 `DataManager::Vibrate()`、screen tick、备份 run、恢复 run 和 ZIP run_zip 函数体。状态枚举来自生产头文件。

32 个场景各在当前 haptics 编译分支及 `TW_NO_HAPTICS` 分支运行一次，共 64 项通过：[结果](../logs/operation-feedback.json)。同一测试对保存的旧 operation 源码有 25 项失败：[修改前](../logs/operation-feedback-before.json)。数量包含编译分支与同一缺陷的多个触发场景，不等于 25 个独立根因。

- 时间：短任务、恰好 10 秒、10 秒加 1 ms、长任务、日历时间前跳/后跳、连续任务。
- 生命周期：重复 start/end、无 start、另一线程错误 end、真实双线程重叠、完成属性复位。
- 后端结果：备份成功/失败/取消/非法名称；恢复成功/失败；三 ZIP 完整队列及第二项失败。
- 反馈设置：时长传递、0 关闭、全局禁用、负值与超范围值、设备缺失/迟到/消失。
- 屏幕事件：实际 tick 一次消费、后续 tick 不重复、多完成事件合并。

使用 ASan/UBSan、真实线程及信号量，时钟独立控制，没有依靠长时间 sleep。报告保存所有生产源、共享头文件及测试源的 SHA-256。编译和执行只使用临时目录。

## 边界与剩余工作

分区工作、Android 属性服务、性能管理器、屏幕硬件和最终震动设备均为替身。已执行完整的上述 worker 函数体，但没有执行 backend 的 start/acknowledge 全生命周期、完整 GUI 页面或 PartitionManager 的备份恢复会话。此测试与既有 FF 路由测试互补，不能合并宣称一次真实硬件端到端调用。

接口要求同一工作线程成对调用 start/end；同线程重复 start 延续同一任务，不是可嵌套的任务栈。线程异常退出而没有 end 的清理不在本补丁范围内。共享进度仍是全局值，本修改只避免其他任务尚在运行时被置为完成，并不提供多个进度条。

后续[恢复会话预检](RESTORE-SESSION-ADAPTATION.md)已独立修复并回放取消标志残留、子分区 digest 和分卷清单，共 54 项通过。本项完成反馈回放仍不覆盖底层分区工作；后续[备份会话 55 项](BACKUP-SESSION-ADAPTATION.md)另行执行了 start/acknowledge/destructor、取消与 `.info` 顺序。压缩/加密分卷内容另由[46 项管道回放](ARCHIVE-PIPELINE-ADAPTATION.md)覆盖；完整管理器、digest 原子发布和强杀/断电清理仍待完成。

其他页面的完整业务流程、设备初始化时序、内核驱动队列、供电与实际电机效果仍未验证。硬件状态保持 U，不要求用户提供新的实机结果。
