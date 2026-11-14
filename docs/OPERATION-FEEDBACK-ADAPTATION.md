# 操作反馈与页面生命周期

<a id="cli-command-bounds"></a>
## CLI 命令组装越界（0136）

原`twrp`客户端先sprintf复制argv[1]，再以`command`同时作为源与目标拼接后续参数；没有总长度检查，超过1024字节数组会栈越界。固定1024字节发送记录未清零，命令终止符之后还含未初始化字节。

[0136补丁](../dtsrc/O1_asic_dual/patches/0136-cli-command-bounds.patch)将数组整体初始化为零，逐参数检查内容和分隔空格的容量，再用memcpy追加。保留最多1023字节和一个NUL、原有空格拼接、空参数及固定1024字节记录；超长命令在打开任一FIFO前返回失败，不截断或部分发送。未修改已有help/version/capability分支。

`tests/cli_command_test.py`执行原始main的命令路径，ASan/UBSan验证单/多参数、空参数、中文/空格、三个合法上限与五种超长情况，共12项通过。精确比较发送内容、终止符到末尾全零；失败必须无open/write/close。相同夹具旧版五个超长场景均被ASan识别为stack-buffer-overflow，七个控制原本通过。FIFO的open/read/write/close及help/capability为替身，没有实际执行命令。

原监听器16项报告`logs/shutdown-admission-cli.json`的全部来源哈希仍一致，本批复用而不重跑。最终镜像仅`twrp`客户端与构建属性/摘要改变；Recovery/GUI字节不变。未完成整条client/server/ORS接合、ARM64运行、CLI退出码传播、连接等待/超时或物理设备验证，不将本修正扩展为完整CLI验收。

```bash
python3 tests/cli_command_test.py --report logs/cli-command-current.json
python3 scripts/audit_cli_command.py
```

本地报告`logs/cli-command-{current,old}.json`，交付核对`logs/cli-command-delivery-audit.json`；当前镜像见[交付报告](../simulation-report.md)。

<a id="terminal-shutdown-boundary"></a>
## 终端重启预约与最终回收（0127）

此前终端不参与0124任务准入，重启预约后仍能创建shell或向已存在的PTY写入。GUI最终退出又仅调用非阻塞stop，未等待0125后台reaper，可能在直接shell尚未回收时继续最终同步/卸载。

[0127补丁](../dtsrc/O1_asic_dual/patches/0127-terminal-shutdown-boundary.patch)将PTY start及write接入原executor短期ticket：预约后拒绝新入口，正在写入时不能预约重启。启动结果经完整engine和GUI adapter返回，不以旧shell仍运行误报新start成功。GUI最终退出和adapter析构调用幂等shutdown，关闭PTY并等待直接子进程reaper；主题切换等日常stop保持非阻塞。最终GUI调用位于图形资源释放之前。

沿现有PTY测试扩展准入五项及完整engine/adapter五项，并回归原回收七项，ASan/UBSan全部通过。准入覆盖预约后启动/写入拒绝、写入与预约衔接、预约回滚及延迟wait；完整引擎覆盖字符/按键/整行输入、start返回、最终join及adapter析构。相同夹具旧owner新增五项中四项失败，预约回滚原本通过。原PTY/fork/setsid/ioctl/kill/wait/线程/executor实际执行，shell exec为无害native等待程序，写入/等待时序与部分错误有替身。GUI最终调用只静态核对，未执行完整页面/Android shell或物理重启。

本修正不为整个交互shell持有长寿命ticket，否则仅打开终端就会永久拒绝重启；它阻止预约后的新启动/写入，最终join保证直接shell回收。已执行命令的所有后台后代、直接ORS、完整MTP/USB关闭和进程级静止仍未解决。不可中断内核等待也可能使最终join等待，不宣称有物理I/O超时保证。

本地证据为`logs/terminal-shutdown-{current,old,engine,reap}.json`，交付核对为`python3 scripts/audit_terminal_shutdown.py`。当前镜像及哈希见[交付报告](../simulation-report.md)，无关完整OTA沿用已有模型结果。

<a id="terminal-child-reaping"></a>
## 终端关闭后的直接子进程回收

0125修正PTY关闭后仅WNOHANG检查一次便丢弃PID的问题。关闭PTY后终止仍归owner所有、尚未回收的直接shell，后台线程waitpid并重试EINTR；GUI stop不等待，重复关闭无操作，旧shell未回收时拒绝重新打开，回收后可重开。析构等待reaper结束。unlockpt/fork失败关闭master，子进程slave打开/dup2/setsid/控制终端失败则退出，启动失败不再resize无效PTY。

私有PTY与无害native子进程验证七项：unlock失败、fork失败、关闭、已退出shell、wait中断、延迟回收、重开；原owner类在ASan/UBSan下全部通过，相同夹具旧版六项失败（fork失败关闭原本正确）。使用真实getpt/unlockpt/fork/setsid/ioctl/kill/wait及线程；exec和部分错误/等待调度为替身，没有运行Android命令或操作物理设备。

镜像`recovery-dijun-unified-terminal-reap.img`，SHA-256 `b7004782ada0776af3627b5f574a2d6c833306f2414e1f7075dda6f5e411c36c`；installclean后30并发，857份生产来源及六profile。报告本地`logs/terminal-reap-current.json`和`logs/terminal-reap-old.json`，核对入口`python3 scripts/audit_terminal_reap.py`。本批仅recovery程序及构建属性/摘要改变，OTA和其他无关测试复用既有证据。

这里只回收直接shell，不对未经确认的进程组发信号，也不证明所有后台后代已退出。终端任务准入、完整关闭屏障、Android shell/GUI及真实最终重启仍未验收；不可中断内核等待仍可能使最终析构等待。


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

后续[恢复会话预检](RESTORE-SESSION-ADAPTATION.md)已独立修复并回放取消标志残留、子分区 digest 和分卷清单，共 54 项通过。本项完成反馈回放仍不覆盖底层分区工作；后续[备份会话 55 项](BACKUP-SESSION-ADAPTATION.md)另行执行了 start/acknowledge/destructor、取消与 `.info` 顺序。压缩/加密分卷内容另由[46 项管道回放](BACKUP-DATA-PATHS.md#archive-pipeline)覆盖；完整管理器、digest 原子发布和强杀/断电清理仍待完成。

其他页面的完整业务流程、设备初始化时序、内核驱动队列、供电与实际电机效果仍未验证。硬件状态保持 U，不要求用户提供新的实机结果。

## 日志导出的失败状态（0068）

“高级 → 复制日志”原来忽略当前存储挂载和 recovery.log 复制结果；内核日志 / logcat 辅助函数返回 void，即使读取或写入失败也输出成功，并将整个工具任务发布为 DONE。这影响故障资料是否确实保存的判断。

[0068 固定补丁](../dtsrc/O1_asic_dual/patches/0068-log-export-failure-propagation.patch) 在共用存储操作锁内读取当前路径并挂载，路径为空、非绝对路径或挂载失败立即结束为失败。Recovery 文件复制、勾选的内核日志和 logcat 都需成功，任务才为 DONE；任一失败为 FAILED，但继续尝试其他独立导出，保留已成功文件。成功消息只表示对应文件已写出，整体结果由任务状态表达。内核日志获取失败或 logcat 子进程非零退出时，不再用空/部分捕获内容覆盖旧文件。WriteToFile 继续检查写入和 close 失败。

`python3 tests/copylog_test.py` 在私有 chroot 内执行生产工具 worker 的 start/run/status/acknowledge、实际线程、CopyFile 和 WriteToFile。13 场景覆盖全部成功、只复制 recovery.log、挂载失败、空存储、源缺失、各文件写入失败、内核 sizing/read 失败、logcat 捕获失败、两个捕获同时失败与成功/失败后复用；旧源码同组 11 失败。已核对逐文件内容、成功消息数和整体状态。挂载、选择、klogctl、logcat 捕获、metadata、sync 和操作展示是明确边界；未读取主机内核或 Android 日志，也未操作设备。

当前候选 `recovery-dijun-unified-log-export.img`，SHA-256 `629f19792d41e1fbc4ec0ad0b7f38bed70ba9b51f234544de4f5cd53a551bf3c`。installclean 后 `make -j$(nproc)` 30 并发构建，781 份生产来源、六份 profile 和打包 Recovery 核对。与 backup-manage 候选仅主程序、构建属性与文件摘要不同；备份管理 / 刷新 worker 实际函数未变，直接复用原检查，不再次跑页面生命周期或震动测试。审计入口 `python3 scripts/audit_copylog_delivery.py`。

本修正不使日志文件写入成为原子替换，写入中失败可能留下部分目标内容；不承诺断电持久性、对正在增长的源日志取得一致快照、内核 ring buffer 绝对不截断或真实 USB 存储行为。也没有修复容量刷新现场的展示故障。

## 进度页日志生命周期补齐（0072）

0070 只修正了工具进度页；本轮检查同类调用，确认备份、恢复、清除、侧载与 fastbootd 日志页仍从 0 整批读取并创建全部历史标签。0072 让这五个入口复用同一个有界 `console_window`，不复制日志实现，不改变 backend 任务或数据操作。

每页分别持有窗口、读取许可和呈现标记。只有该页首帧成功提交、页面类型和实例序号均匹配后才允许读取；公共 scaffold 删除旧页时清空 view/window 并撤销许可。备份、恢复、清除和侧载先更新状态再读取日志。沿用最多 160 显示行、24 项/4096 字节/64 消息的读取上限、32 行应用批次及向上回看，不裁剪 backend 历史。

复用已有测试入口 `tests/tool_console_test.py --pages`，执行五个原始 poller、共用窗口与 LVGL 行应用、原始 before_render/after_present 和从公共 scaffold 提取的对应删除清理语句。每入口六种调度：5000 项历史、任务已完成、console 忙、历史回看、代次变化、删除重入，共 30 项通过。旧五个入口的同组 30 项均在首次无界读取断言失败，属于同一类缺陷的多入口覆盖，不能计作 30 个独立缺陷。共享呈现回调改变后原工具页六项必要回归通过。

```bash
python3 tests/tool_console_test.py --pages
# 需本地旧源码，预期失败：
python3 tests/tool_console_test.py --pages --before
python3 tests/tool_console_test.py
python3 scripts/audit_progress_console_delivery.py
```

状态来源为已完成的真实工具 worker；五个业务 backend、目标页面的完整 builder/router/tick、console 生产端、字体、flush 和 DRM 不是本测试范围。fastbootd 场景的“已完成”仅是共用 fixture 的状态，不宣称 fastbootd 有该终态。没有执行备份、清除、恢复、实际侧载或 USB；本批也不声称闭环现场刷新停留根因。

候选 `recovery-dijun-unified-progress-console.img`，SHA-256 `a29624a081b50c7b5c388c3d4f79695dfebd9791c83c48770fc267fe28721b9c`。按 `installclean` 后 `make -j$(nproc)`（30 并发）构建，787 项生产来源、六份 profile；对上一候选仅 GUI 库、构建属性与 ramdisk 摘要变化。触摸策略及 MTP/updater/profile 资源未改，不因本批重跑。

## GUI2 点击反馈与取消

本节保留 2026-11-11 的点击取消与反馈次数修正。OS4 震动后续已由用户确认正常，不再作为待办；这里的离线结果只说明组件事件行为。当前候选见[交付报告](../simulation-report.md)。

### 发现与修正

实际 `accept_click()` 会提交 BUTTON 反馈；五个业务回调又各提交一次：取消 sideload、文件排序、取消安装后倒计时、取消备份、选择转换文件系统。原实现一次点击产生两次震动请求，两个正常点击产生四次。对应 FF 后端会清理上一效果并重新上传，这与实机体感之间仍缺硬件证据。

[0014 补丁](../dtsrc/O1_asic_dual/0014-ui-feedback-and-cancel.patch)移除这五个重复调用，保留公共点击检查的反馈。VALUE_CHANGED 开关、键盘和滑动确认各有独立入口，没有批量删除其反馈。

实际 LVGL 指针回放还暴露两处取消错误：

- 键盘按钮没有接入按下移出取消逻辑。拖出后释放仍会输入并触发反馈。现在复用点击检查，但关闭其默认 BUTTON 反馈；实际输入被接受后，键盘自己的回调只发一次 KEYBOARD 反馈。
- 确认滑块在拖动中被禁用后，RELEASED 仍可能确认；成功后额外收到 RELEASED 也会重复确认。现在只有正在进行的拖动能结束，禁用中的拖动复位到起点；重新启用后仍可正常完成一次。

上述回调的业务边界由替身接收；验证过程没有开始侧载、取消真实备份或转换任何分区。

### 实际运行范围

[Python 驱动](../tests/haptics_ui_test.py)和[C++ 夹具](../tests/haptics_ui_test.cpp)采用：

- 原 `external/lvgl/Android.bp` 所列源文件与实际 `gui2/lv_conf.h`；按内容指纹缓存主机静态库，以 `make -j$(nproc)` 构建。主机自然使用非 ARM NEON 分支。
- 实际 LVGL display、pointer indev、事件分发与软件绘制，向 480×960 内存 framebuffer 输出。
- 实际 GUI2 公共按钮、键盘、确认滑块、点击取消检查、布局辅助函数、SVG 缓存和箭头资源。
- 从实际 `gui2.cpp` 提取五个业务回调、键盘反馈回调和侧载开关回调，保留原函数体。
- 设置与业务 backend、震动硬件接收端替身。GUI2 C++ 部分启用 UBSan；LVGL/ThorVG 库采用普通主机编译，没有把整个依赖库称为 sanitizer 验证。

从指针读取回放正常操作；PRESS_LOST 与额外 RELEASED 用真实 LVGL 事件接口注入，作为异常顺序检查。没有直接操作控件私有状态来代替其生产回调。

### 结果

[当前报告](../logs/haptics-ui.json)：21 场景通过；[同组修改前报告](../logs/haptics-ui-before.json)：11 场景失败。
报告记录生产源码、头文件、测试源码、LVGL 全部参与文件、配置、编译器、静态库与截图哈希。

| 场景组 | 场景数 | 预期 |
|---|---:|---|
| 五个重复反馈回调 | 5 | 一次有效点击，一次 BUTTON 请求，业务回调仍执行 |
| 连续点击与取消 | 5 | 两次点击保留两次；拖出、拖回、PRESS_LOST 不操作；无硬件对象不影响业务 |
| VALUE_CHANGED 开关 | 1 | 一次变更，一次 BUTTON 请求 |
| 实际数字键盘 | 5 | 一次输入一次 KEYBOARD；拖出/拖回取消，禁用 PIN 字段不输入，连续两键不丢失 |
| 实际确认滑块 | 5 | 完整滑动确认一次；未到终点、禁用或重复松手不确认；重新启用可用 |

全部场景实际产生非空 framebuffer。已检查两份夹具截图：[数字键盘](../logs/haptics-ui-frames/keyboard.png)、[确认滑块](../logs/haptics-ui-frames/swipe-complete.png)。它们是组件夹具截图，未展示完整手机页面；没有据此宣称全界面布局已经验收。

`gui2.cpp` 其他多用户入口回归也重新执行，结果见[报告](../logs/ui-feedback-multiuser-routes.json)。

### 边界与后续

本轮证明这些组件的事件顺序和软件反馈次数。它没有启动完整 Android recovery，没有执行 DRM、原厂驱动、TEE 或真实电机。主机截图使用内置字体，未证明设备字体、完整页面布局、所有确认页或物理输入时序。

操作完成反馈的备份/恢复/ZIP 生产调用者现有[独立 64 项回放](OPERATION-FEEDBACK-ADAPTATION.md)。还需覆盖其余页面事件路由、完整页面截图，以及目标文档中的备份/恢复、OTG、合成卷等功能。此前 22 场景验证的“设置 backend→通用震动路由→FF”与此处事件验证互补；没有把两组拼接说成一次真实硬件调用。
