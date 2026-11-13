# OS4 正式版无法触摸：反馈、离线排查与顺序修正候选

## 当前候选状态（2026-11-13）

当前本地交付候选已更新为 `recovery-dijun-unified-ordinary-reports.img`，SHA-256 `aee7856e90ba4f5861bdc918d4da0b585b7de4fd337a64138204c9f526d3b300`。相较较早的 touch-priority 候选，运行时在 Synaptics 模块 live 且 Xiaomi input 已注册后等待2秒，再写 `enable_touch_raw=0` 并核对软件缓存。9项私有文件策略用例通过，镜像内脚本与调用打包审计通过，构建绑定809项来源、六个 profile。

这只证明有界请求被发出以及软件缓存读回为0，不证明控制器接受、普通报告实际发送或 Recovery 收到坐标。用户提供的既有手动 raw0 观察仍是215条 input 事件；它不是这个自动启动候选的测试结果。驱动延迟任务参数为50 jiffies，但目标内核 `HZ` 和实际启动时序没有由此候选测量，2秒是有限等待策略。不要将本候选称为已修复触摸。

## OS4.0.4 现场日志补充

### 第四批：关闭raw后真实坐标恢复，已构建启动策略候选

用户命令回执已保存为[原始文本](../logs/touch-raw-off-user-transcript.txt)：写raw0、读回0，随后event3在1157.900042→1161.555421秒输出215条事件，包括7组tracking ID开始/结束、BTN_TOUCH按下/抬起及变化X/Y。由[解析器](../scripts/audit_touch_raw_off_observation.py)核对范围与事件配对，见[结果](../logs/touch-raw-off-observation.json)。这是该次启动恢复Linux input坐标的真实证据；用户尚未明确确认GUI、冷启动或唤醒稳定性。补充dmesg为UTF16，已覆盖较晚时段，没有触摸协议行，不能据此声称抓到切换后的0x11或命令ack。

新维护脚本`profiles/runtime/dijun-touch-reports.sh`等待模块live与Xiaomi input注册后，经原厂节点请求raw0；runtime modules阶段用6秒timeout调用，属性只发布requested/request_failed，不发布ready。原厂wrapper初始`.data+0x400`为1，不随Synaptics内部raw0自动更新，因此此前读值推断被收窄。另确认mode1004会排队250jiffies的syna_tmd_signal_work，后者可开启raw1；未证明现场触发该路径。没有添加循环重置、固件刷新或盲目改模块。

该阶段的早期候选 SHA256 为 `0d6b65d3a2e526c95220fd3cffdf6b9021c977c1a028d3055b199091da005bd5`，有7项私有文件策略检查及708项来源；它已被上文809项来源的新候选取代。早期检查同样不执行内核/sysfs回调，不能作为控制器接受请求或触摸已修复的证据。

### 第三批 v1 debug：已定位 raw 报告模式不匹配

新现场目录 `imgs/built/1/touch-v1-debug`：uptime926.86→936.92，流式日志在934.918166→936.176377出现170个v1报文头，全部`a5 c0 80 06`，ID0xc0、长度1664，没有0x11。触摸IRQ4621→4791、SPI DMA4615→4785，各增加170；getevent和流式dmesg均以137结束，event3有枚举、无input事件。`enable_touch_raw`缓存读值为1；controller-info为application0x01、v1、build4463140、10 objects、1439×3199。日志等级3/1→3/4→3/1恢复正确。复现`python3 scripts/audit_touch_v1_debug_observation.py`，见[新观察](../logs/touch-v1-debug-observation.json)。

原始ISR只让0x11进入普通触摸parser/input，0xc0走raw帧路径，因此当前捕获明确表现为Recovery需要普通坐标、控制器却发送raw帧的模式不匹配。此前“报文类型未知”的缺口已补上。尚不知道是谁在启动`enable_touch_raw(0)`之后启用raw，也没有证据证明关闭后已恢复坐标，不把模式定位等同功能修复。

原厂`/sys/class/touch/touch_dev/enable_touch_raw`写0会经wrapper回调请求关闭0xc0、开启0x11；wrapper会忽略回调错误并更新自己的缓存，因此写成功和读回0只能证明软件状态，必须再看实际坐标。给用户的针对性命令为`adb shell "echo 0 > /sys/class/touch/touch_dev/enable_touch_raw"`，随后读值并观察event3。命令不含复杂正则/管道，避免此前PowerShell转义问题；本轮代理未执行设备命令。生产树与镜像尚未改，后续永久适配需定位模式切换来源/时序并验证报告恢复。

### 第二批现场日志：动作关联 IRQ 已取得

采集脚本进一步补足结果检查：开启vendor debug后核对读回`3 4`，恢复后核对原两项值；记录getevent/dmesg超时退出码，提前失败不打印成功。`python3 tests/touch_debug_collector_test.py`在私有路径实际执行脚本，替代cat/timeout/dmesg，检查正常、初值无法解析、开启读回失败、恢复读回失败、getevent失败5条路径；没有运行设备或Windows PowerShell。结果见[采集脚本检查](../logs/touch-debug-collector-test.json)。

用户新增 `touch-idle-irq.txt`、`touch-active.txt` 与含启动过程的 `touch-dmesg-before.txt`。静置 139.25→143.26 秒，触摸 IRQ 323→323、SPI DMA 317→317；划屏 170.58→182.59 秒，触摸 IRQ 956→2569、SPI DMA 949→2562，两者均增加 1613（约134.30次/秒），getevent 只有设备枚举，没有保存 EV_ABS/KEY/SYN。该文件没有 getevent 退出码，完整窗口采集成功仍有证据限制；用户确认无事件。当前优先级已转到 IRQ 后 v1 报文类型、配置与解析/input 路径，不再以缺少动作计数作为下一阻塞点；中断/DMA 不证明报文有效。

新启动日志明确使用 `syna_tcm_v1_detect`，CRC/extra RC 关闭；应用固件 build4463140匹配、免刷新成功、后台 input 注册完成。初始化中的 fw-version/IC-mode “power off”警告发生于 connect 尚未完成阶段，不能单独认定运行时断电。前述 v2 模拟仍只是独立覆盖，不能用来说明本次 v1 故障。新机器记录为 [动作关联观察](../logs/touch-action-runtime-observation.json)，可用 `python3 scripts/audit_touch_action_observation.py` 复现。

同日志还保留当时的震动芯片观察；用户随后确认 OS4 震动已正常。该事项已解决并退出例行检查，不再按旧记录重复分析。

用户的组合 PowerShell 命令失败是 native argument 传递丢失正则引号，`|spi_dma_irq` 被 shell 当管道，`touch-window.txt` 不用于计数判断。后续改为推送脚本，避开复杂 native quoting。[v1 debug采集入口](../scripts/collect-touch-v1-debug.ps1)与[设备脚本](../scripts/collect-touch-v1-debug.sh)临时将原厂日志等级设为`3 4`，采8秒事件并流式保存10秒dmesg，结束恢复原值；原厂wrapper store的第二参数>3调用Synaptics日志回调，仅设debug_log_flag，v1读路径会打印4字节报文头。没有reset/raw/report模式写入。脚本只做主机语法检查，未在Windows或设备执行；断电/SIGKILL无法保证trap执行，不宣称实际报文已取得。

### 缓存状态读取与分时日志分析（2026-11-12）

当前现场文件仍是 00:01 的同一批，没有收到新的静置/划屏窗口或开机早期日志。此前重复复核已有包没有进一步确定故障分支，当前不以更多合成触摸成功作为修复进度。

进一步核对两份 OS4 原始模块的 `kobj_attr_info`：名称 `info`、权限 0444、无 store，回调 `syna_sysfs_info_show` 只格式化内存中的连接标志、固件模式、版本等信息，调用本地内存复制与日志函数，没有 SPI、reset 或报告切换调用。可复现检查为 `python3 scripts/audit_touch_cached_info.py`，结果见 [静态检查](../logs/touch-cached-info-audit.json)。这不是实际 sysfs 执行，也不保证读取期间状态一致；其中 Firmware mode 是驱动缓存，不能视为一次新控制器查询。

[采集脚本](../scripts/collect-touch-no-events.sh)已在计时窗口外尝试读取 platform/SPI 设备下精确的 `synaptics_tcm/info`；节点不存在时记录缺失，不递归读取 `testing`、raw 帧、reset 等可能触发操作的节点。脚本未放入生产镜像，本轮没有连接设备或重建镜像。

新增 [分时分析器](../scripts/analyze_touch_window.py)，使用采集目录中的 CPU 计数总和、uptime 和带设备路径的坐标事件，输出观察结果及下一排查方向。计数倒退、CPU/IRQ 身份变化、异常 getevent 退出和缺文件均输出 insufficient，不将累计 IRQ 认作动作响应；重复窗口间的未知重启仍不能仅凭文件完全排除。用法：

```bash
python3 scripts/analyze_touch_window.py /path/to/dijun-touch-no-events --output /tmp/touch-window.json
```

[10 项合成日志检查](../logs/touch-window-analysis-test.json)覆盖无 IRQ、有 IRQ 无事件、有坐标、能力列表、计数倒退、IRQ 重编号、采集错误、缺文件、UTF-16 和窗口重叠；不验证控制器。对现有 `imgs/built/1` 分析明确返回 [insufficient](../logs/touch-existing-window-analysis.json)，原因是缺少窗口起止文件。触摸 P0、震动与完整功能目标保持未完成。

### 无事件上报后的定向采集（2026-11-12）

再次复核原始正式版 ISR 后更正：`xiaomi_get_sensorhub_status(0)` 的 bit0 分支在 `0x1bd0..0x1be4` 打印日志，然后跳回 `0x1a5c` 继续报告判断，并非退出 ISR。此前本页把它解释为跳过 input 解析不准确；后续 IRQ 模拟已覆盖该继续分支。没有现场证据支持以 sensorhub 状态作为直接阻断原因。当前最小缺口仍是同一划屏窗口内的 IRQ/SPI DMA 计数差和同期事件、驱动日志，不再增加无现场判别力的合成成功场景。

重新核对现场 ZIP 的 `dijun-runtime.log`：包含 `runtime cache: verified os4-stable`、Synaptics/Xiaomi 模块插入和 `runtime modules: complete`。结合现场 input 和用户确认，当前故障位于控制器到 Linux input 事件之间；不能以节点存在宣称触摸可用。当前日志不足以选定具体根因，也没有据此制作另一份修复镜像。

再次核对正式版原始 `syna_dev_isr`（[反汇编](../logs/os4-stable-touch-isr.disasm)）：TUI 锁失败、TUI 状态及 GPIO 电平门控可以在读取报文前退出；`syna_tcm_get_event_data` 失败会退出；只有报告 ID `0x11` 进入普通触摸 parser。故“IRQ 增长且无事件”仍包含多个分支，不能直接认定 parser 或 raw 模式是本次根因。特别是若锁/TUI 门控使低电平 IRQ 未被正常处理，中断增长也未必代表有效报文持续到达。

新增只读采集工具：[PowerShell 入口](../scripts/collect-touch-no-events.ps1)、[设备侧脚本](../scripts/collect-touch-no-events.sh)。静置 4 秒和划屏 12 秒分别保存中断起止、uptime、所有 input 事件；同时记录 IRQ 状态、前后 dmesg、profile/cache 和 firmware 路径。按各窗口时长比较 IRQ 增量，避免把启动累计值或后台中断误当划屏响应。脚本只写 `/tmp` 日志，没有 reset、report-mode/sysfs 写入或模块重载。采集窗口正常会由 timeout 结束，退出码单独保存。主机侧完成 shell 语法检查；没有运行 ADB 或实机采集，PowerShell 入口尚未在 Windows 执行验证。

2026-11-12 收到用户提供的 recovery 日志包 [os4-touch-20261112-000013.zip](../imgs/built/1/os4-touch-20261112-000013.zip)，SHA-256 `b113b4bb4a422bd79698d2b72fa4823c699d99e5da14d90755ab06be4362a4c8`。日志确认 profile 为 `os4-stable`、module phase 为 `complete`，`synaptics_tcm2` 和 `xiaomi_touch_dijun` live；`/proc/bus/input/devices` 有 `Xiaomi_Touch_Input_0`，event3 的 ABS_MT 范围为 X 0..143999、Y 0..319999、10 slots。这个快照证明 input 注册，不证明驱动产生了触摸坐标。

随包 `os4-touch-getevent-live.txt` 只列出设备名称，没有 `EV_ABS`/`ABS_MT_*` 事件记录。用户随后明确确认触摸没有事件上报，因此目前把 GUI 消费层降为次要排查方向。`interrupts.txt` 中 Synaptics IRQ `xiaomi_tpsynaptics_tcm` 累计为 3003；这是启动后累计快照，不能证明用户触摸曾触发 IRQ。约启动 624 秒的 dmesg 只有一条 `syna_set_thermal_temp` 温度日志，没有 probe/启动阶段信息；由于采集较晚，缺少错误行不能证明启动时无错误。当前仍无法区分控制器/IRQ未触发与 IRQ 后报文读取、配置或解析没有产生坐标。机器可读检查见 [OS4 stable runtime observation](../logs/os4-stable-haptics-runtime-observation.json)。下一次只需一次定向采集：开始 `getevent -lt /dev/input/event3` 和触摸 IRQ 计数，然后手指划动屏幕数秒，再读 IRQ 计数并停止 getevent；IRQ 不变优先查控制器 IRQ/供电/引脚，IRQ 增长而 event3 无坐标则查 Synaptics SPI 读取、报告配置和 parser。若 event3 有坐标而 GUI 无响应，才转查 Recovery 输入消费。P0 保持未解决。

PowerShell 定向采集（设备保持在 recovery，先执行第 1 条记下基线；第 2 条运行期间在屏幕上连续划动约 5 秒，再按 Ctrl+C；最后执行第 3 条）：

```powershell
adb shell "grep xiaomi_tpsynaptics_tcm /proc/interrupts"
adb shell "getevent -lt /dev/input/event3"
adb shell "grep xiaomi_tpsynaptics_tcm /proc/interrupts"
```

请只回贴 getevent 中的触摸事件，以及两行 IRQ 计数。若 event3 有 `ABS_MT_POSITION_X/Y` 且 IRQ 增长，驱动已把坐标送到 Linux input，下一层才是 Recovery 消费；若 IRQ 增长但无坐标，重点查 Synaptics 读报文/配置/解析；若 IRQ 不增长，重点查控制器 IRQ/供电/引脚。单独 IRQ 变化仍需和这次划动同时发生才有意义。

2026-11-11，用户反馈 OS4 正式版安装最新镜像后无法使用触摸。此前未提供该次启动日志或镜像哈希；现已补充现场包。此前“坐标回放通过”和“profile 脚本通过”不等于触摸已可用。当前仍为 P0，根因未确定。

本轮仅做固件和主机分析，没有连接设备或要求实机测试。

历史候选 [recovery-dijun-unified-module-state.img](../imgs/built/recovery-dijun-unified-module-state.img) 的 SHA-256 为 `c282f535b1fdac6f5eafe25ca46116441195affe9d67f4511178a930634c4346`；镜像已从原始构建输出恢复并重新校验，来源清单为明确标记的事后重建。该候选曾保留触摸依赖优先顺序、`initstate=live` 检查和 coming 有限等待，并优先尝试触摸依赖闭包；同镜像 9 组 profile runtime 测试和 24 次 module-state 阶段调用通过。它没有实机验证，用户报告的触摸失效仍未解决。

## 可确认的风险与修正

原模块计划中，`xring_smartpa` / OS4 的 `xring_audio_hw_third` 位于 `synaptics_tcm2` 前面。组合音频/震动 probe 不是 Synaptics 的硬依赖，初始化可能阻塞；但整个 modules 阶段共用 45 秒用户空间期限。前面的可选 probe 若耗尽该期限，触摸可能还未尝试加载。该路径是可确认的风险，尚无证据说明本次用户失效一定由它触发；不可将候选命名解释为已恢复触摸。

[计划生成器](../scripts/generate_profile_runtime.py)现在优先选择已就绪的触摸硬依赖，同时保持每条已接受的原厂硬/软依赖边；六包均让 Synaptics 先于可选震动模块。OS2/OS3 的索引为 49→50，OS4 为 52→53（从 0 起）。闭包数量仍为 51/54，没有换入另一版本模块，也没有卸载已加载驱动。

运行时新增 `twrp.profile.touch_modules=pending/loaded/failed`。历史 touch-priority 版本的 `loaded` 只证明模块目录存在；当前 module-state 候选要求 `initstate=live`，仍不宣称 SPI probe、input 注册或事件可用。插入前记录模块名，完成时把 `/proc/bus/input/devices` 写入 `/tmp/dijun-runtime.log`，以区分后续定位层次。若阶段提前超时，末尾快照仍可能缺失；处于不可中断睡眠的内核操作仍无强制回收保证。

cache 阶段仍要求完整、精确匹配的固件档案；本轮未引入未知版本回退。身份不匹配、cache 缺失及上游触摸依赖阻塞仍可能使触摸无法加载。这些是候选的实际限制。

## 固件差异

正式版 Synaptics 模块 SHA-256 为 `8fecca0cfad0cdef274356a28dc3f06ee9f8025ba244d313ee9bf8d1f58ffc3f`，旧 OS4 为 `dc2b7631bdac52d6c2152abb465aab7842e232da1bbf20958113b6c26d94b7bf`。正式版的 ISR、应用信息读取和触摸报文解析函数指令发生变化；当前正式版 profile 使用对应的新模块哈希。Xiaomi 触摸包装模块及所查 shub 模块在两包中相同。

新驱动仍有普通报告 `0x11` 的解析和 input 上报路径；原厂初始化调用 `syna_tcm_enable_touch_raw(0)`，请求关闭 `0xc0`、打开 `0x11`。这些是反汇编观察，未执行 SPI 命令，不能确认硬件接受，也没有据此强行启动完整 Android 的触摸算法服务。

## 候选与验证

候选：`recovery-dijun-unified-touch-priority.img`（历史文件当前缺失），104,857,600 字节。

SHA-256：`220a8cf491d96e08dff5a2f7737258bc78b1947d77be382b2b026a6a0b0eec6f`。

按 `make -j$(nproc) installclean`、`make -j$(nproc) recoveryimage` 构建，30 jobs；[构建日志](../logs/build-touch-priority-final.log)、`镜像检查`（历史文件当前缺失）、`来源档案`（历史文件当前缺失）。本次只修改设备运行时和生成计划，recovery C++ 补丁集不变，上一份 haptics-worker 产物保留。

- [六包计划检查](../logs/touch-priority-plans.json)：重新生成并比较真实计划，核对硬依赖、可接受的软依赖顺序和触摸优先关系。
- [同镜像运行时回放](../logs/touch-priority-profile-runtime.json)：8 组、96 次阶段调用；六包两槽位、未加载依赖顺序、可选震动失败后触摸模块存在、触摸插入失败与已加载状态，以及原有身份/缓存/安全服务拒绝路径。
- [输入到 GUI 回放](../logs/touch-delivery.json)：已有节点、晚注册节点两条路径通过；使用真实 FIFO/inotify/epoll/read、minui 注册与 Type-B 解析、触摸队列和 GUI read callback，核对历史 100 倍坐标的按下与释放。evdev ioctl 与 LVGL 为夹具，不运行内核触摸驱动。
- 当前镜像的 init、12 项通用策略及 53 项 USB 专用域检查通过；[交付审计](../logs/touch-priority-delivery-audit.log)核对来源和证据。

这份候选消除了可选震动先加载的顺序风险，**尚不能宣称 OS4 正式版触摸已修复**。下一排查点为精确 profile/cache 是否成功、驱动 probe/固件请求、input 注册与事件生成；用户报告的失效状态持续保留，直至取得足以判定的证据。

## 原厂启动、中断与报文解析的离线执行

本轮续接增加 [ARM64 模拟程序](../tests/touch_startup_emulation.py)和[结果](../logs/touch-startup-emulation.json)：旧 OS4、正式版各 44 项，共 88 项通过。直接重定位并执行上述两份原始 `.ko`，没有改写模块指令；硬件回调夹具保留原始 CFI 签名检查。执行超过指令/时间预算或遇到未知内核调用即失败，不默认返回成功。

| 层次 | 执行与观察 | 解释边界 |
|---|---|---|
| 报告切换 | `enable_touch_raw(0/1)` 两条命令的四种成功/失败组合；第一条失败、第二条成功时返回 0，软件 raw 标志仍先更新 | 最终返回 0 不能证明两条 SPI 命令都成功；命令传输是夹具 |
| 连接 | 电源、setup、设备识别、IRQ 错误；应用信息/配置失败；panel 边界失败；已连接与 state=3 | 应用信息/配置失败可切到 bootloader 后仍返回 0 并排队后台任务；连接返回 0 不保证 input 已注册 |
| 后台固件 | 原始 delayed worker 和 reflash body；缺文件/权限拒绝、最多三次更新、应用信息失败、bootloader 模式夹具 | 这些路径仍会调用 input 注册接口；注册接口由夹具返回已分配对象，不证明真实注册、控制器恢复或固件更新成功 |
| 原始 ISR | 普通/未知报告、raw 帧、读取/解析失败、无 input、TUI、锁忙、GPIO 非活动；普通按下/释放 | TUI、锁或 GPIO 门控可在读取报文前退出；`0xc0` raw 帧不发普通坐标；软件 raw 标志为 1 时收到 `0x11` 仍可走普通解析 |
| 原始 parser→ISR | 合成配置描述 object index、classification、X/Y、宽度，原厂 parser 解析后由原厂 ISR 上报按下/释放 | 解析得到 644/1589 后发出 64400/158900；不是从真实控制器抓到的报文或配置，不代表其余报文格式已覆盖 |
| parser 前置条件 | 空 core、报文、输出、缺报告配置均返回失败 | 配置缺失不能被“驱动模块已加载”排除 |

中断的独立故障场景在 parser 边界注入解码对象；最后两条成功链路执行原始 parser，使用明确的合成配置和报文。内核 input API、固件请求/更新、IRQ 注册、调度器、锁和 SPI/GPIO 硬件是边界，未启动真实内核。后台固件结束也没有在所执行路径中重新调用报告模式切换，不能假定它自动修复此前切换失败。

这批结果把可复现的失效分支细化到连接、配置、门控与报文层，**没有确定此次正式版失效发生在哪一层**。两包均通过这些合成报文场景，不能据函数字节变化就归因于新解析器退化。本轮生产源码、设备树和当前 `recovery-dijun-unified-touch-priority.img` 未改变，因此没有重编译或生成另一份“已修复”镜像。

复现：`python3 tests/touch_startup_emulation.py`。报告绑定两份原始模块、测试程序、共用 ELF/ARM64 加载器、模拟器依赖和反汇编记录；交付审计同时校验这些指纹。后续优先核对原厂 probe 的设备树条件、实际报告配置取得路径与 profile/cache 失败边界；实机失效状态保持未解决。

## 配置获取、probe 与原始设备树的续接证据

新增 [62 项原始配置/probe 模拟](../logs/touch-configuration-emulation.json)，两包各 31 项。[测试程序](../tests/touch_configuration_emulation.py)实际执行 `get_app_info`、`preserve_touch_report_config`、`request_irq`、平台 `probe`、`connect`、后台固件流程、parser 和 ISR。控制器 `0x20` 应用信息、`0x25` 报告配置是合成响应；SPI/GPIO、IRQ 注册、panel/cdev 注册、内存分配与 disconnect 清理为显式边界，原始间接调用的 CFI 检查仍执行。

成功链路现已覆盖“probe→connect→应用信息→配置复制→后台再次配置→input 注册→parser→ISR 坐标输出”。panel setup 仍是边界，未执行 SPI bus probe 或真实控制器读写；不能据此宣称完整驱动实机初始化通过。

新确认的失效机制：

- 配置命令失败后，connect 可切换到 bootloader 而 probe 仍返回 0。若后台没有恢复应用模式、取得报告配置，仍会调用 input 注册，但 parser 因配置缺失失败，ISR 不发坐标。模拟同时覆盖通过夹具恢复应用模式/配置后可输出坐标的另一分支；不表示更新程序已证明能恢复真实硬件。
- 已有配置缓冲区收到零长度配置时，配置函数可能返回 0 且保存长度为 0，随后 parser 返回失败；首次分配时零长度响应走失败分支。前者说明配置函数成功也不能单独作为触摸就绪证据。
- 正式版 `get_app_info` 将大于 10 的触点数限制为 10，旧版原始函数保留 15；空应用信息响应在这组初始内存中可返回 0 且触点数为 0。范围内没有证据表明触点数上限变化导致本次完全无触摸。
- GPIO 无效、缺少 managed device、IRQ 注册失败、分配失败、配置容量不足和空响应均有独立失败场景；cdev 失败会走 remove/disconnect 边界，未用空操作代替该路径并宣称完整清理有效。

另新增[原厂触摸设备树检查](../logs/touch-devicetree-audit.json)，重建 host libfdt 后分别合并两包 dijun 第 5 条 DTBO，绑定原始 vendor_boot 内 DTB 与 DTBO 哈希。触摸节点所有属性在直接 phandle 解析为节点路径后相同，确认 1440×3200、倍率 100、IRQ GPIO 12/低电平、复位 GPIO 10、SPI 和触摸包装节点可用；引脚与两个电源目标节点属性字节相同。panel 目标节点部分属性仍有原始引用编号变化，报告保留字节，未把这些目标的全部属性声明为递归等价。该检查也不证明 bootloader 实际选了第 5 条。

原厂 ODM 的 `synaptics_spi_dijun.img`、`dijun_syna_thp_config.ini` 与当前两套 profile 的 `/lib/firmware` blob 按哈希吻合，且两包文件相同；模块计划仍使用各自独立 `.ko`。这排除了本轮所查清单中固件名字/内容遗漏，不能证明实际启动 cache 已发布或驱动读取到这些字节。

复现命令：`python3 tests/touch_configuration_emulation.py`、`python3 scripts/audit_touch_devicetree.py`。这批生产源码未变，当前候选仍为 `recovery-dijun-unified-touch-priority.img`，SHA-256 不变。**用户 OS4 正式版触摸失效仍未定位到具体分支**；下一步继续审查 SPI bus probe/pinctrl、电源准备与 cache/挂载前置条件，保留原厂控制器状态未知的边界。

## SPI probe、引脚与供电的原始函数执行

[新增模拟程序](../tests/touch_spi_emulation.py)对两包各执行 29 项、共 [58 项场景](../logs/touch-spi-emulation.json)。运行原始 SPI probe、`xiaomi_parse_dt`、GPIO 请求包装、供电和硬复位代码，并加入原始 SPI→平台 probe→配置→ISR 接续。OF 接口使用上述原始 DTBO 合并结果，包含 `synpatics,cfg_0` 子节点和原厂固件/配置名称；GPIO 全局编号 76/74 为夹具映射，真实 DT 中引脚编号是 12/10，不能混为一谈。未知调用与执行预算耗尽仍失败。

- 从清零的 resolution/factor 字段出发，原始 Xiaomi 解析取得 1440×3200 和倍率 100；SPI mode 为 0。没有沿用先前 panel 成功夹具来伪造这组值。
- pinctrl 获取返回 `-EPROBE_DEFER`/其他错误、四种 state 查找失败、active state 选择失败，均存在继续到 `platform_device_add` 的路径。GPIO 获取返回 `-EPROBE_DEFER` 也可先保存负数再继续注册。这里证明错误可能被忽略，未证明真实引脚失效。
- avdd/iovdd 获取延迟会返回 `-517`，SPI setup/平台注册错误按测试分支返回失败。某些 regulator 清理接口收到原始错误指针；夹具只记录调用，未证明内核清理安全。
- GPIO 申请路径实际执行原厂包装，覆盖 IRQ/reset 申请失败。供电按 avdd→iovdd 请求 enable、成功后请求 50 ms 等待；硬复位按低→高请求 GPIO 写入和 10/200 ms 等待。睡眠、电源与 GPIO 是显式边界，没有实际等待或测量电平。

`platform_device_add` 是单独边界，**没有把注册成功解释为 `syna_dev_probe` 执行成功**。新增的六种接续场景在 SPI 成功后显式调用原始平台 probe，共用 SPI 创建的 hw 对象、原始函数指针和 CFI 检查，实际运行供电/GPIO 回调；不再使用此前的成功 power/setup 回调夹具。正常配置可从后台注册走到原始 parser/ISR 输出坐标，配置超时仍可注册 input 而不输出事件；GPIO 申请失败终止 probe，原始 connect 把供电失败转换为 `-ENODEV`（-19）。内核绑定调度、控制器响应、core 分配、panel/cdev 和 IRQ 注册仍是显式边界，未运行真实 SPI 传输。两包在当前范围内行为一致，不能将这些原厂缺陷直接归因为正式版专属回归。

加载链路审查仍保留两点：cache 要求完整精确档案，任一必需源失败会拒绝额外模块；该阶段运行时仅以 `/sys/module` 目录判定存在，后续 module-state 候选已加入 `initstate=live` 检查与 coming 有限等待，详见本页开头。没有当次内核状态证据证明该机制触发了用户失效；没有重载/卸载或修改原厂模块。

复现：先运行 `python3 scripts/audit_touch_devicetree.py`，再运行 `python3 tests/touch_spi_emulation.py`。报告绑定原模块、DTBO/DTB/子节点证据、反汇编、共用加载器及模拟器依赖；交付审计核对全部指纹。本轮生产代码和镜像未变，未重新编译；用户触摸失效仍未解决。

## SPI 传输、识别入口与 panel setup 续接

[传输程序](../tests/touch_transport_emulation.py)新增两包共 [86 项](../logs/touch-transport-emulation.json)，实际执行原始读写、缓冲管理、CFI 与 `syna_tcm_detect_device`。`spi_sync` 遍历原厂生成的传输链表、提供明确的合成字节；不模拟物理总线。协议 v1/v2 成功检测函数是显式边界，另有场景取消这两个 hook，执行原始函数对无效合成头的拒绝。

- 原厂 bulk read 在本组 DT 参数下使用空 TX 指针，257/258 字节读请求向上对齐为 320 字节，返回与拷贝仍为请求长度；write 不做同样对齐。缓冲区重复使用、增长与三处分配失败均有执行记录。
- 平台/SPI/上下文缺失返回 -6；休眠完成等待失败返回 -22，未传输；成功完成后可继续。传输 -110 向上传递，read 不覆盖调用者原缓冲，锁和 PM 退出路径有检查。调度、锁、内存分配、完成事件与 PM 是夹具。
- 自动识别先写 `02` 再读四字节，先尝试 v2，失败后 v1；读写失败、缺回调和协议未安装操作表均失败。这不证明真实控制器使用哪种协议，或原始完整命令帧已验证。

[panel 程序](../tests/touch_panel_emulation.py)另执行两包共 [22 项](../logs/touch-panel-emulation.json)。从原始 DT 解析结果出发，执行原厂 `syna_xiaomi_touch_probe` 的 lockdown 选择、配置名回退、参数组装和原始普通报告切换；flash 读、panel/notifier/TUI 注册与 debugfs 为显式边界。该函数为 void，不把遗留返回寄存器解释为成功。

发现并复现一个此前未覆盖的重复路径：flash 持续返回全零 128 字节 lockdown 时，原始代码在这组初始状态下反复读取；两包均在 100,000 指令预算内读了 2,173 次，未到达 panel 注册、报告切换或 sleep。反汇编显示全零分支令索引为 -1，随后 `index >= 9` 判断不会退出该循环。预算耗尽只在这一预期用例中作为重复路径证据，其他未知调用/预算耗尽仍失败；不是实机卡死时间测量。先返回两次全零、第三次有效则继续注册，证明模拟未把整个函数固定为失败。

flash 返回错误或固件完成等待超时则各经过五次显式 1 秒等待后继续配置名回退；等待没有在主机实际耗时执行。panel/notifier 返回错误、第一/第二/两条报告切换命令失败时，原函数仍继续后续注册步骤。配置名与 1440×3200 参数可正确组装，也不能证明包装层注册成功或普通报告已启用。

这些行为在旧 OS4 和正式版均可复现，**没有证据说明本次失效属于全零 lockdown 或任一错误分支**。本轮没有修改 `.ko`、生产设备树或当前 `recovery-dijun-unified-module-state.img`，也未新构建镜像。后续执行点是原始 v1/v2 报文、识别/lockdown 数据边界和 Xiaomi 包装层注册，再与现有配置→ISR→GUI 链路接续。触摸 P0 与整体任务均保持未完成。

复现：`python3 tests/touch_transport_emulation.py`、`python3 tests/touch_panel_emulation.py`。两份报告绑定原始模块/DT/子节点、测试、加载器、模拟器依赖与反汇编，并进入交付一致性审计。

## Xiaomi 包装层入口续接

[包装层模拟](../tests/touch_wrapper_emulation.py)新增两包各 25 项、共 [50 项](../logs/touch-wrapper-emulation.json)，执行原厂 `register_touch_panel`、`register_xiaomi_input_dev`、`store_enable_touch_raw`，并以显式 callback bridge 连接另一个独立地址空间中的 Synaptics 原厂 report-mode 函数。原厂结构体字段、CFI 和返回路径执行；proc、workqueue、线程、shub notifier、输入核心、内存分配和内核注册服务是边界。panel 参数来自此前执行 Synaptics 原始 setup 的合成 flash 响应，不能解释为真实控制器数据。

- panel 注册位图在初始化完成后才设置；重复注册返回 -1。参数缺失、ID 越界、分配和 workqueue 失败均不置位；但 mode 初始化、shub notifier 注册和温度线程失败路径可能仍返回 0 并置位，输入节点尚未注册。这些错误边界均有回放。
- input 入口可以在 panel 未注册时单独创建 input 设备；失败分支会返回空指针，input 注册错误会释放设备；MT slots 的初始化错误被忽略。故 `/dev/input/event*` 存在只证明 wrapper input core 注册层的一部分，不能证明 Synaptics panel/config、IRQ 或事件流就绪。
- sysfs `store_enable_touch_raw` 对空输入返回 -22；合法文本会调用 panel 回调、保存 requested state，最终返回输入字节数。即便 callback 中两条底层 SPI 命令都返回 -110，包装 sysfs 仍返回成功写入长度。这与此前发现的 raw 标志先更新及第一条命令失败可被后续成功掩盖共同说明：sysfs 写入成功或 enable 标志为 0，均不确认控制器已切换到普通 `0x11` 报告。

生产 recovery 不应通过重复写 sysfs 强制切换：包装层会改软件状态但隐藏硬件错误，且它仅是控制器已正确识别、配置、上电后的接口。当前候选无新改动，本轮没有编译或实机测试；正式版触摸失效仍为 P0 未定位。

复现：`python3 tests/touch_wrapper_emulation.py`。报告绑定两个原厂包装模块与 Synaptics 模块、DT 属性、原始反汇编、测试和模拟器依赖，并进入交付审计。

## 原始协议识别与 ID 长度边界

[识别程序](../tests/touch_identification_emulation.py)在两包各执行 31 项、共 [62 项](../logs/touch-identification-emulation.json)。原始 v1/v2 detect、ID parser、传输长度设置、v1 CRC 状态更新与操作表安装实际执行。message read/write、continued-read 和 v2 command request 是明确边界，提供合成 ID 字节、状态与错误；未执行完整报文编解码、CRC 传输验证或真实 SPI。v2 合成四字节头 `10 00 00 27` 的校验尾字节由主机枚举生成，随后由原始 ARM64 CRC6 检查代码验证；这不是控制器抓包。

- 缺少 core、短头、错误标识/校验头被拒绝；空 ID 与目标缓冲容量不足无法完成识别。原始 parser 复制合成的 build ID `4463140` 和 mode，分别覆盖 application 与 bootloader，成功后安装对应版本的读写函数。
- v2 首次 read message 返回 `-110` 后可通过合成的 identify 成功响应继续；identify 也失败、reset 成功时，两协议均可继续。两条命令均失败则检测失败。这是明确错误恢复分支，不能把初次读错误单独认定为永久无触摸。
- v1 的 build ID 或最大写长度为零时检测失败；v2 build ID 为零时失败，但本组最大写长度/可用读长度为零时，设置函数仍返回 0，detect 可安装操作表并返回成功。这说明检测成功也不足以确认长度协商可用。
- v2 请求设置读长度的 command 9 返回 `-110` 时，detect 返回 `-242` 且未安装读操作表；软件读长度已经变为 256。host 已有读写上限为 128 时，原始代码保留该限制。状态字段与返回值必须联合解读。

旧版和正式版在这些输入下结果相同，未发现足以解释正式版专属失效的分支差异。生产代码与当前 `recovery-dijun-unified-module-state.img` 未变，没有重新构建；用户触摸 P0 仍未解决。后续需继续 message 编解码和 IRQ/配置接续，不能将这里的显式报文边界写成完整协议已模拟。

复现：`python3 tests/touch_identification_emulation.py`。报告绑定原始模块、反汇编、测试、公共加载器与模拟器依赖；交付审计检查用例数、驱动与输入指纹。

## 历史 firmware-load 线索的归属

会话早先贴出的 recovery 排查 `dmesg` 曾有 `synaptics_spi_dijun.img` 请求返回 `-2`、kernel `firmware_load` AVC、`TpFirmwareLoadFail`，随后仍注册 Xiaomi input；另有 evdev 坐标记录。它们属于历史排查证据，不能视为 OS4.0.4.0 当前失效启动的记录，更不能把它们说成来自正常 Android 系统启动。早先字段明确含 OS4.0.0.19 身份。

当前源码已有 `sepolicy/kernel.te` 允许规则和 `0006-kernel-firmware-permission.patch`；当前镜像的二进制策略报告已验证 rootfs、vendor_file 和 kernel self 的 `firmware_load` 决策。runtime 在额外模块加载前核验/发布 `/lib/firmware` 并设置 firmware_class 路径。故本轮不重复加入已有规则，也不根据历史 AVC 宣称当前根因。模块是否在这之前已 probe、实际 profile/cache、控制器响应仍需分开判断；本轮未连接设备或要求重测历史镜像。

## 原始报文读取、事件复制与 ISR 接续

[报文模拟程序](../tests/touch_message_emulation.py)执行两包各 45 项、共 [90 项场景](../logs/touch-message-emulation.json)，[运行记录](../logs/touch-message-emulation.log)通过。v1 执行原厂四字节头读取、标识重试、continued-read 分段拼接、payload/report/output 缓冲复制、parser 和 ISR；传输回调提供显式合成字节，未接物理 SPI。v2 执行原厂 read_message、dispatch、get_event_data、parser 和 ISR，但 command 10 的执行仍为显式边界，提供解码后的响应状态和 payload，**未执行完整 v2 帧传输/校验协议**。配置来自合成 command 0x25 响应，内核内存、锁、GPIO、时间、completion 和 input API 仍为夹具。

- 合成普通报告可经原始读取→复制→parser→ISR 输出 64400/158900，并在 classification=0 时释放触点。v1 的六字节读上限场景执行多段拼接；持续错误头经过 20 次读取/等待后返回 -242，错误 continuation 标识也返回 -242；读取 -110 向上传递。
- 缓冲分配失败分别覆盖 input、payload、report 和 output。v2 report 分配失败被 void dispatch 路径记录，但上层仍返回 0，report/output 长度为 0；不能把 read_message 返回 0 当作报告可用。其余已覆盖分配失败返回负数。
- 复用已有缓冲区后收到空 `0x11`，两协议均可将 report 长度清零，却保留调用者 output 的旧长度 8。通过原始 ISR 重复执行时，上一次合成按下坐标被再次上报，没有产生释放；这是明确的旧缓冲复用机制，不是当前实机全无触摸的根因证据。
- v2 status=4 跳过分发，event ID 为 ff；已填充的旧 report/output 长度仍保留。源缓冲容量不足返回 -22。pending command 遇读超时，两协议均置 command state 为 -1 并通知 completion；错误返回路径的旧输出不得按新帧使用。

两包在这组输入下行为一致。当前未观察到正式版独有的报文分支失败；也没有证据说明实机正在收到空报告或经历内存分配失败。本轮没有修改原厂 `.ko`、生产设备树或镜像，当前候选仍为 `recovery-dijun-unified-module-state.img`，用户触摸 P0 保持未解决。离线后续重点是减少 v2 command 边界，并审查实际模块自动加载与 profile/cache 激活时序；不以继续增加成功用例数代替根因证据。

复现：`python3 tests/touch_message_emulation.py`。报告绑定原始模块、反汇编、测试及其导入程序、依赖清单和模拟器文件；[交付审计](../logs/touch-message-delivery-audit.log)校验 90 项数量、上述关键分支和当前产物来源。

随后执行[静态加载时序检查](../scripts/audit_touch_load_order.py)，[两包结果](../logs/touch-load-order-audit.json)通过：从原始 vendor_boot 镜像重新解析全部 ramdisk 条目，两包均不含 Synaptics/Xiaomi touch `.ko`，modules.load 与 recovery 清单也没有这两个名字。当前候选 ramdisk 不带 `/lib/modules`，其所有 `.rc` 无直接模块加载动作，recovery 主 init 未导入原厂 vendor 的 `init.O1_asic.rc`。原厂该文件会启动 vendor_dlkm_load，但不是当前 recovery 的直接导入项；当前 C++ profile 分支先调用 cache、成功后调用 modules，runtime 在 insmod 前发布固件。报告绑定镜像、两包 vendor_boot、所查源码与原厂二阶段脚本。

这只是源码与归档检查，未运行 bootloader ramdisk 合并、Android init 或内核，不证明设备实际执行顺序；也不能把“未在这些文件发现早载”扩大为排除所有早载来源。当前检查不支持将固件发布前自动加载认定为根因。后续主要缺口仍是完整 v2 command/帧协议、控制器真实响应和内核调度状态。

## v2 原始 command、帧校验与初始化接续

[v2 程序](../tests/touch_v2_command_emulation.py)新增两包各 39 项、共 [78 项原始 ARM64 场景](../logs/touch-v2-command-emulation.json)。取消上一组的 `execute_cmd_request` 整体响应夹具，实际执行 v2 command、write/read、CRC6/CRC16、序号、重试、分段拼接、read/write_message、事件复制、parser 和 ISR。物理读回调提供显式合成帧，写回调记录原厂生成字节并独立校验 CRC；没有物理 SPI、控制器、内核并发或 IRQ 时序。大部分独立场景仍用此前的合成配置获取边界，最后三项改为执行原始 `0x25` 配置命令，其中正常链路还执行 `0x20` 应用信息命令；不是所有初始化路径都已取消夹具。

- 正常、预测读取和分段报告可到达原始 parser/ISR；分段 command 发送命令 9 再发送 continuation 1，收到报告后的继续读取命令为 7。原厂生成的两帧 ordinary/raw 切换命令为 6/5，payload 分别指定关闭/开启的报告 ID。第一帧写超时而第二帧成功时，整体仍返回 0；第二帧超时返回 -110。此前只在命令返回边界观察到的掩盖机制，现在由原始帧路径重现。
- 单次头 CRC、序号或 payload CRC 错误后可用后续有效合成响应恢复。头 CRC 或序号连续失败各读取/发送六次后，read_message/get_event_data 仍可返回 0，ID 为 fe，没有输出报告；不能只看返回码。
- 连续七次 payload CRC 失败后，本组初始缓冲状态下仍可分发 ID=11、长度=8、内容全零的报告。原始 ISR 只上报 BTN_TOUCH/BTN_TOOL_FINGER=0 和 SYN_REPORT，没有坐标。这里模拟的是损坏字节和软件路径，未证明真实控制器发生校验错误。
- 配置命令 `0x25` 在同类 CRC 耗尽分支可返回 0，保存 13 字节全零配置；后续合法合成触摸报告经 ISR 仍只产生无触点状态。配置读超时则返回 -110、保存长度为零、ISR 不输出事件。正常配置与应用信息经完整帧回路后，可取得 1440×3200/10 个触点并发出 64400/158900 坐标。
- 分别覆盖发送、首读、源缓冲、扩容、payload/report/output 的分配失败及缺读写回调。report 分配失败仍可能被 void dispatch 隐藏；其他已覆盖分配错误返回 -243，缺回调 -245、传输超时 -110。status=4 跳过分发；status=8 连续重试后可向调用者复制先前配置命令留下的 response 缓冲，不能视为新触摸帧。

两版在这些输入下结果一致。此轮把 v2 command 从整体替代缩小为物理字节回调，补充了足以产生“无坐标”的可复现机制，但没有当前设备状态证据将其认定为此次根因。**用户触摸 P0 仍未解决，震动和完整适配任务也未完成。** 生产树与 `recovery-dijun-unified-module-state.img` 未改，没有重新构建。

复现：`python3 tests/touch_v2_command_emulation.py`。报告绑定两份原始模块、完整执行链导入脚本、反汇编和模拟器指纹；[交付审计](../logs/touch-v2-command-delivery-audit.log)核对关键错误结果及当前 707 份产物来源。后续重点为原始 detect→应用信息/配置→panel 启动接续、bootloader/application 模式恢复与 IRQ/完成事件边界；控制器真实响应仍未知。

## v2 识别、模式恢复与后台启动接续

[启动接续程序](../tests/touch_v2_startup_emulation.py)执行旧 OS4 与正式版各 22 项、共 [44 项场景](../logs/touch-v2-startup-emulation.json)，[运行记录](../logs/touch-v2-startup-emulation.log)通过。初始状态清空协议、模式、操作表、读写上限、尺寸/触点数量与 input 指针；从原厂单字节 `02` 探测、四字节头、ID 报告及长度协商开始，经原始 v2 帧代码接续连接、应用信息、报告配置、模式切换、后台和 ISR。ID、应用信息、配置与报告字节均为合成，原厂代码自行解析；没有直接写模式字段假装切换成功。

- 普通连接返回 0 后尚无 input，后台请求固件失败仍可注册 input。初始应用信息和配置有效时，合成报告经 ISR 输出 64400/158900。后台没有重新获取配置，使用连接阶段保存的配置。
- `0x20` 应用信息超时后，原厂先执行三次事件读取，再重发命令。一次超时后恢复可继续获取配置；三次命令及各自三次事件读取全部失败后，连接流程发送 `0x1f` 切到 bootloader。配置 `0x25` 超时也进入该模式。两类连接仍返回 0，申请 IRQ、调用 panel 边界并排队后台；固件请求失败后注册 input，配置长度为零，随后合法触摸报告也没有事件。
- 经原始 `0x14` 命令和 ID 报告切回 application 模式，仅改变模式，未补回配置。固件请求失败，或更新回调三次失败，均跳过后台应用信息/配置重取，仍注册 input，没有坐标。固件更新回调成功的对照分支实际执行后台 `0x20/0x25` 并保存配置，随后合成坐标恢复。这里的固件更新回调是显式返回夹具，**未执行固件解析、刷写或真实控制器重启**。
- 切换模式命令超时返回 -110，响应仍停留旧模式返回 -242，无效目标返回 -241。完整协议选择器的长度协商失败最终返回 -245；此前孤立 v2 detect 的 -242 不应套用到完整选择器。IRQ 注册错误 -5 时连接关闭电源，不排后台且不注册 input。

这些场景都有返回值、状态、命令顺序、剩余帧、配置、input 和事件断言。模拟执行原厂 IRQ 请求函数，但内核注册返回由夹具提供，后台由程序顺序调用；供电/复位、panel setup、input 注册、固件请求/更新与内核服务仍是边界。两版在本组输入下行为一致，不能把缺配置机制认定为正式版独有回归或本次实机根因。

复现：`python3 tests/touch_v2_startup_emulation.py`。[交付审计](../logs/touch-v2-startup-delivery-audit.log)核对 44 项及关键分支，并绑定原厂模块、反汇编、导入程序和模拟器指纹。生产代码和当前 `recovery-dijun-unified-module-state.img` 未改，没有重新构建；用户触摸 P0、震动及整体适配继续未完成。下一步减少同一启动链中的 panel/flash 和报告切换边界，保留对真实控制器/IRQ/内核调度未知状态的记录。

## 原始 panel、报告切换与 flash 读取接入 v2 启动

[接续程序](../tests/touch_v2_panel_startup_emulation.py)执行两包各 16 项、共 [32 项场景](../logs/touch-v2-panel-startup-emulation.json)，[运行日志](../logs/touch-v2-panel-startup-emulation.log)通过。尺寸和倍率先清零，再执行原始 `xiaomi_parse_dt` 读取已绑定的原始 DTBO 属性；同一模块实例实际执行识别、应用信息/配置、IRQ 请求函数、panel 初始化、报告切换、后台和 ISR。kernel OF API、panel/notifier/input 注册及物理字节仍为显式夹具，后台顺序调用，没有启动内核。

- 普通链路发送 `06` 关闭 `c0`、`05` 开启 `11`，随后后台注册 input，合成触摸报告输出坐标。第一、第二或两条报告切换写入超时，外层连接均仍返回 0、排后台并注册 input。若随后显式供给合法报告仍可输出坐标；若供给 status4 无事件响应则无坐标。后者**不是控制器启用状态模型**，不能据此宣称实机发生报告关闭，也不能用前者说明开启超时无影响。
- panel 注册 -12、notifier 注册 -517 也不阻止连接返回 0 或后台 input 注册。持续全零 lockdown 在执行预算内反复读取超过 100 次，未到 panel 注册、报告切换或后台排队；先空、第三次有效可继续。flash 请求错误与 firmware completion 超时仍按原厂路径进行五次 1000 ms 睡眠请求后继续，睡眠仅记录，未等待物理时间。
- 原始配置请求超时后，控制器模式按合成 ID 切为 bootloader，原始 panel 仍可注册，但原始报告切换在此模式跳过，不发送 `06/05`。随后 input 注册成功，配置长度为零，合法合成报告也不输出事件。该场景减少了上一组的 panel 替代边界。
- 最后三项分别执行原始 flash 正常读取、一次读取超时后恢复、identify 持续超时。前两项实际执行 `02` identify、`1f` 切 bootloader、`10` boot info、`13` 读取、`14` 回 application；boot info 为合成，原厂计算得到读取请求 `100000004000`，即从字节地址 32 读取 128 字节。原厂代码将合成 lockdown 复制到独立 flash 缓冲，随后 panel 取出配置名和参数，最终合成坐标通过。读取超时先切回 application，再重试完整流程；identify 五次超时后仍能按原厂 fallback 参数继续 panel 和 input 注册。

前三类的 flash-area 仍是显式边界；最后三项取消该边界，运行原厂 flash setup、boot config、read 和模式返回代码。固件解析/更新、wrapper 内部注册、真实控制器状态及 IRQ/完成事件调度仍未执行。两版在本组输入下相同，没有正式版独有根因证据。

复现：`python3 tests/touch_v2_panel_startup_emulation.py`。[交付审计](../logs/touch-v2-panel-startup-delivery-audit.log)核对关键命令、无配置/无报告、raw 路由、预算耗尽与恢复结果，并绑定模块、DT 证据、反汇编、导入程序和模拟器指纹。生产源码和 `recovery-dijun-unified-module-state.img` 未改，没有重新构建；触摸 P0、震动与完整适配目标保持未完成。

## 原厂固件容器与后台恢复接续

[26 项模拟](../logs/touch-firmware-emulation.json)执行两包原始 `syna_tcm_do_fw_update` 和 image-ID 比较函数，并将成功/失败接回原始后台、配置获取与 ISR。两包使用相同的原厂固件字节（SHA-256 `edaa698e65a41d165d87ceec13559f41232c0d9c42ce09e326fe2a5678928fee`）。原始解析识别 BOOT_CONFIG / APP_CODE / APP_CONFIG 三个区域，分别校验 8 / 143840 / 5810 字节；第四个表项不是有效区域，由原始代码跳过。CRC kernel 服务通过独立 zlib 计算，控制器 ID/配置/报文是显式合成响应。

- build 与完整 16 字节配置 ID 匹配时，原始更新返回 0 且不发送 flash 命令。build、配置首/尾字节不同或 force 请求均转入 flash setup；这些场景在原始 identify 的合成超时处返回 -5，未执行擦除、编程或控制器复位。
- 错误 magic 或三个区域的 CRC 损坏分别在原始解析路径返回 -241，不发送 flash 命令。后台会重试三次并释放固件；它是 void worker，报告没有把遗留返回寄存器记录成成功码。
- 正常匹配的免写分支之后，后台仍执行原始应用信息/配置获取，合成 ISR 可输出坐标。初始配置失败后仅恢复 application 模式仍为 cfg=0；随后同一免写决策和原始配置重取可恢复 cfg=13。
- 已有有效配置时，三次固件 CRC 失败仍可保留配置并输出合成坐标。初始缺配置且三次 flash-access identify 都超时时，仍注册 input，但保持 bootloader/cfg=0，ISR 无事件。固件失败是否阻断触摸取决于此前状态，不能仅据报错判定。

`python3 tests/touch_firmware_emulation.py` 可复现。panel/输入/IRQ 注册、供电、内核调度和物理控制器仍为边界；后台顺序执行。报告绑定实际固件、原始模块、反汇编及全部导入程序/模拟器，由[交付审计](../logs/touch-firmware-delivery-audit.log)复核。两包相同行为尚未解释用户 OS4 正式版触摸失效；当前生产树和 module-state 镜像未改。后续继续原始 flash 写入/复位、wrapper 接续与 IRQ/内核调度分析。

## 原始擦除/编程命令失败与后台接续

[程序](../tests/touch_flash_failure_emulation.py)新增两包共 [32 项](../logs/touch-flash-failure-emulation.json)，每包 12 项更新错误路径和 4 项连接→三次更新失败→后台注册→ISR 场景。原始固件与 CRC、identify、切模式、boot-info、块检查、擦除/编程命令构造及 reset 都实际执行；物理传输仍明确提供合成响应。没有连接设备或写入 flash，也没有完整编程成功场景。

合成 boot-info 声明 16 字节写块、128 字节擦除页、256 字节最大写入。独立清单逐项核对 APP_CODE/APP_CONFIG 擦除起始页与向上取整页数；原始 v2 编程包每段含 240 字节，核对首两段块地址及原厂 payload 字节（帧 CRC 同时检查）。分别在擦除、首段、第二段返回超时；更新最终返回 -5，但会执行原始 reset。只修改配置 ID 尾字节时，仅进入 APP_CONFIG 路径。零写块、超传输尺寸写块、零擦除页、boot-info 超时及切模式仍为 app 的响应分别在发送擦除之前失败。

这些更新失败均清除 pending 并调用完成通知，完成通知不是成功。擦除失败后的 reset 超时或返回 bootloader 会保留 bootloader；reset 返回 application 也不能证明应用配置已恢复。更新外层将这些失败归并为 -5，内部日志、模式及命令序列必须一起检查。

四项后台接续从真实 connect 开始：已有/缺少报告配置，各配 reset 返回 app/bootloader；原始后台三次更新均在擦除响应处失败，然后仍注册 input，且没有重新发送应用信息/配置请求（32/37）。缺配置时，随后提供合法合成触摸帧仍没有坐标，即使 reset 报告 app；已有配置时，原始 parser 能处理明确注入的合成帧。bootloader 场景能解析合成帧仅证明 parser 路径没有以模式阻断，不能推断真实 bootloader 发普通触摸报告。

复现：`python3 tests/touch_flash_failure_emulation.py > logs/touch-flash-failure-emulation.log 2>&1`。[交付审计](../logs/touch-flash-failure-delivery-audit.log)绑定原始模块/固件/DT、反汇编、导入程序及模拟器来源，并核对关键分支。两包机制一致，尚无证据将此作为用户正式版故障根因；完整编程/固件状态、IRQ/内核调度与 wrapper 接续仍待继续。当前生产树和镜像不变，不宣称触摸已修复。

## 完整编程请求与配置恢复

[26 项模拟](../logs/touch-flash-complete-emulation.json)执行完整原始固件编程命令生成、复位和后台配置重取，补充上一批仅首两段写入失败的范围。[程序](../tests/touch_flash_complete_emulation.py)在无关指令 hook 处提前返回，减少 Python 参数寄存器读取；没有跳过任何原始 ARM64 指令、CRC 或服务边界。完整入口使用有限 2000 万指令/45 秒预算；超限失败。先前探索器 45 秒只到第 467 条请求，已作为不完整运行处理，未算成功。

独立清单验证 APP_CODE 143840 字节分 600 段、APP_CONFIG 5810 字节分 25 段，总计 625 段。每段核对原厂 payload、块地址和 v2 帧 CRC；两条擦除命令核对页范围，末段分别为 80/50 字节，不补假定尾字节。仅配置 ID 尾字节不同执行 25 段配置更新。所有响应、几何和模式均为明确合成值；没有证明真实 flash 接受这些请求，也未模拟写入改变控制器身份或配置。

- 正常完整请求和配置单独更新返回 0；末段 app 写、配置擦除、末段配置写、reset 超时/状态拒绝分别返回 -5，精确核对实际请求前缀及完成通知。
- 所有编程命令得到夹具确认，但 reset 响应仍报告 bootloader 时，原厂 reset 只记录异常模式，update 仍可返回 0。后台应用设置函数遇 bootloader 直接返回 -22，不主动切 app；随后仍注册 input，cfg=0，合法合成报文无事件。
- 正常 app reset 后，配置请求超时或返回空响应也会留下 cfg=0 并注册 input，无合成坐标；超时不会在本路径自动切 bootloader，最终仍为 app。
- app-info/配置重取均成功时，cfg=13，原始 ISR 输出合成坐标。第一次最后一段配置写失败、第二次完整重试成功的场景核对 1250 段请求和四次擦除，最终同样恢复合成坐标。

初版夹具曾在 bootloader 场景额外提供切 app/配置信息响应，被未消费响应断言拒绝；[保存日志](../logs/touch-flash-complete-expectation-before.log)保留该错误预期，随后按原始 `syna_dev_set_up_app_fw` 分支修正。另一个初版假设配置超时会自动切模式，也由断言拒绝并按实际行为改正。没有以丢弃未消费响应的方式通过测试。

复现：`python3 tests/touch_flash_complete_emulation.py > logs/touch-flash-complete-emulation.log 2>&1`。[交付审计](../logs/touch-flash-complete-delivery-audit.log)核对原厂文件、全部程序与模拟器来源和完整/部分请求清单。原始包装层接续及 IRQ/完成/内核调度仍待验证，两版在本批夹具下行为一致，当前实机根因未确定。生产源码/设备树/当前 module-state 镜像未改，触摸 P0 继续保留。


## IRQ 开关、系统 PM 与 ISR 门控

[40 项原始 ARM64 场景](../logs/touch-irq-emulation.json)覆盖旧 OS4/正式版各 20 项。[程序](../tests/touch_irq_emulation.py)执行原始 `syna_spi_enable_irq`、`syna_tcm_enable_irq`、`syna_pm_suspend/resume`，并接入已有原始报告配置解析/ISR。IRQ descriptor、depth、wake 返回值、锁、等待和普通触摸报文都是显式夹具；没有运行内核调度、IRQ 控制器或真实控制器。depth 字段布局绑定这两份精确模块，不泛化到其他 ABI。

- 开启 IRQ 时，软件 enabled=0 的场景将 depth=3 通过三次 `enable_irq` 请求降到 0；depth=0 仍请求一次 enable。若软件标志已经为 1，即使夹具 depth=3，原始函数也不请求 enable。IRQ 编号为 0 时返回 0，未置 enabled。这说明返回码/标志不足以单独证明硬件中断可达，不能证明当前设备正处于这些状态。
- 原始开启循环依赖 `enable_irq` 后 descriptor depth 实际减少。命名的 `unchanged-depth-budget` 场景固定 depth=2，原始代码重复 enable 并耗尽有限 10 万指令/2 秒预算，未置 enabled。只有此场景将预期预算耗尽作为被观测结果；其他执行超限均失败。没有据此宣称真实内核会不减少 depth 或永久挂起。
- `syna_tcm_enable_irq(0)` 遇 pending 持续为 1 时，请求 150 次 20 ms 睡眠，然后仍执行 disable；第 1/3 次睡眠后显式清 pending 分别只请求 1/3 次。累计 3000 ms 为请求总量，模拟没有真实等待，不是测得的设备唤醒延迟。此接口为 void，报告不以遗留 x0 作为成功码。
- `irq_set_irq_wake` 明确返回 -5 时，原厂仍更改软件 wake 标志。重复开启会跳过已标记的动作；关闭失败同样清除标志。wake 是系统唤醒配置，不能与普通中断是否启用混为一谈。
- 系统 `syna_pm_suspend` 置 PM 标志并清 completion 计数，resume 清标志并通知 completion；这两个入口没有请求 SPI 命令或 IRQ 开关。PM 标志仍为 1 时，原始 parser/ISR 能输出所供合成按下坐标。sensorhub 返回 1 的原始分支记录日志后继续，仍输出相同坐标。初版测试曾错误预期 sensorhub=1 会阻断事件，断言失败后按反汇编的继续分支纠正，没有把该假设写成根因。

复现：`python3 tests/touch_irq_emulation.py > logs/touch-irq-emulation.log 2>&1`。[交付审计](../logs/touch-irq-delivery-audit.log)核对模块/测试/模拟器来源和上述关键状态。显示相关 `syna_dev_suspend/resume` 与本节系统 PM 是不同入口，前者、包装层跨模块接续、实际 IRQ 调度/并发仍待验证。两版在当前场景一致，正式版触摸 P0 根因未确定；震动与其余任务保持进行中。生产设备树和当前 module-state 镜像未改，没有新增“已修复”镜像或请求实机测试。


## 显示休眠／恢复入口及失败后的 active 状态

[48 项模拟](../logs/touch-display-resume-emulation.json)执行两包各 24 项原始 `syna_dev_suspend/resume`、normal/low-power sensing、sleep/dynamic 命令、应用信息/配置解析、报告切换、IRQ 开关和 parser/ISR。[程序](../tests/touch_display_resume_emulation.py)继承已绑定模块的 IRQ 夹具，没有改原厂指令；所有场景要求在有限预算内返回，未知服务失败。

这里的无手势模式、初始 sensing/state、IRQ depth 为显式条件，不是设备状态转储。send-command 提供合成响应，reset、读事件、温度回调、电源与 pinctrl 为边界；未执行显示 notifier 调度、物理控制器或真实延时。原始 free-input 仍继承显式边界；合成 ISR 仅验证保留下来的报告配置能否被解析。

- 两次顺序 suspend→resume 成功：各请求 sleep 0x2c，恢复硬复位路径各请求 100 ms 等待，重取 app-info 0x20 与 config 0x25，再请求关闭 raw 0xc0／开启普通 0x11；每次配置为 13 字节，合成坐标为 64400/158900。这是顺序回放，没有模拟快速按键并发。
- 配置超时/空配置、应用信息耗尽、bootloader、复位读报超时/错误事件，以及 sensing sleep/dynamic 四次失败，都可返回错误却留下 active=1；随后再次 resume 返回 0，不调用温度、命令或 IRQ 恢复。初始缺配置的这些场景保持 cfg=0，合法合成报文仍无事件。不能从 active 或第二次成功码推断触摸已恢复。
- 配对场景先让配置超时，取消超时后直接再 resume 仍不获取配置、无事件；重新走 suspend→resume 才重取 13 字节配置并恢复合成坐标。没有据此建议用户重测或宣称按电源键可修复实机。
- 应用信息超时执行三次请求以及九次 typed read-message 排空；加上硬复位读事件共十次。排空服务明确返回 -110，原始间接 CFI 检查仍执行。normal sensing 唤醒命令为 0x2d，失败可重试四次，耗尽后还读取一次事件再尝试；dynamic ID9=0 也覆盖同样的四次失败。
- 报告切换第一条、第二条或两条都失败，resume 仍可返回 0。合成 ISR 在所供有效配置/报文下仍有坐标，这只证明软件解析未被阻断，不能证明控制器接受过开启命令。raw 标志保留时 resume 跳过普通报告恢复，所供普通报文仍可解析。
- 恢复 pinctrl 失败后仍可能继续成功；供电失败转换为 -19、保留非 active 状态，尚未进入配置。sleep 命令失败的 suspend 仍置非 active，但该错误路径不关闭 IRQ。pending 持续时显示 suspend 只请求三次 20 ms 后继续关闭，不是前节独立 IRQ 接口的 150 次。

复现：`python3 tests/touch_display_resume_emulation.py > logs/touch-display-resume-emulation.log 2>&1`。[交付审计](../logs/touch-display-resume-delivery-audit.log)核对全部来源及恢复/失败配对状态。两包表现一致；原始状态机制明确，但缺少将其与当前正式版故障对应的证据，故仍不修改原厂模块或生成“已修复”镜像。手势开启分支、显示通知队列/内核并发、包装层调用链继续待验；触摸 P0、震动和整体目标未完成。


## Xiaomi 显示通知、worker 与下层恢复接续

[30 项模拟](../logs/touch-notifier-emulation.json)对旧 OS4/正式版各执行 15 项，接通原始 `xiaomi_drm_panel_notifier_callback`、`schedule_resume_suspend_work`、suspend/resume worker，经显式 callback 桥进入原始 `syna_tcm_resume_suspend` 及上一节 display 恢复。原始 wrapper panel 注册和参数捕获也执行，输入参数来自绑定 DT 的原始 Synaptics setup。wrapper 文件两包相同，Synaptics 仍使用各包独立原始模块。

[程序](../tests/touch_notifier_emulation.py)使用两个独立 ARM64 地址空间，typed host callback 桥执行两侧原始 CFI，**不是内核链接或内核并发模拟**。下层 enable 标志与回调地址是显式已安装夹具；IPC、时间、IC-mode 和前述电源/IRQ/控制器仍是边界。worker 没有返回值；检查它实际调用和写下的状态，不解读遗留 x0。

- 通知 event 1/3 请求 suspend work，event 2 请求 resume work；顺序 1→2→2→3→2 产生五次 flush/queue 请求，但只有四次下层回调，第二次 2 被 wrapper 的休眠标志跳过。event 0/4/7/8、panel 越界/负数/未注册及空通知均不排恢复任务。
- 下层配置失败返回 -110 后，wrapper 仍清自己的休眠标志，下层已经 active=1、cfg=0；重复 event 2 不再进下层，合成报文无事件。新的 3→2 周期在错误消失后重新取配置并恢复合成坐标。报告保存失败时快照，后续恢复没有覆盖原失败证据。
- 下层供电返回 -19、dispatch 禁用返回 -1 或 wrapper 回调指针为空时，wrapper 也会清标志，下层仍非 active、cfg=0。重复 event 2 仍跳过；不能只修正下层 active 检查就声称整条恢复链可靠。
- 明确让 queue 返回 0 的场景不执行 worker、保留原标志；这只验证拒绝时行为，没有把它归因为真实内核合并任务。原始调度在 queue 前执行 flush，fixture 要求队列已经排空，若非空直接失败。当前顺序结果不能证明快速开关屏的竞态、任务丢失或阻塞时长。

复现：`python3 tests/touch_notifier_emulation.py > logs/touch-notifier-emulation.log 2>&1`。[交付审计](../logs/touch-notifier-delivery-audit.log)绑定 DT/模块/反汇编、全部导入程序与模拟器，并核对失败快照、重复通知和恢复配对。两版行为一致，未取得将该机制绑定到当前正式版故障的证据，不改写原厂模块，也未生成或宣称触摸已恢复的镜像。下一缺口为非空 flush/通知并发、手势与原始 IPC/IC-mode，以及震动完整 DSP/IRQ 和任务文档其他未完成组。


## 原始 IC mode 2 与恢复链

[22 项接续](../logs/touch-ic-mode-emulation.json)取消此前 `syna_set_ic_mode` 整体成功替身，执行两份 OS4 的原始 IC 模式函数及 notifier→worker→dispatch→显示恢复。直接入口核对正常、命令超时、分配失败、managed device 缺失、IRQ 关闭、inactive 和 bootloader 七条路径；四条 notifier 接续核对正常、IC 命令/分配失败和配置失败。原始模式 2 发 `0xc7`、payload `31 0a 00`，保留间接回调 CFI 检查。控制器应答仍为明确夹具。

上层 dispatch 保存显示 resume 的返回值，调用 IC mode 后直接返回已保存值，未传播 IC 命令故障。IC 命令超时或分配失败时 dispatch 仍可返回 0，wrapper 清休眠标志，重复亮屏跳过回调。配置获取失败时它仍尝试 IC 命令，但不会补回配置，合成 ISR 无坐标；有配置时可解析提供的合成坐标，这不证明控制器接受模式切换。IC 函数不存在统一错误返回约定，本批只记录遗留 x0，不当作函数成功；明确判断采用 dispatch 返回和调用轨迹。

复现：`python3 tests/touch_ic_mode_emulation.py > logs/touch-ic-mode-emulation.log 2>&1`。报告绑定两份 Synaptics、wrapper、DT、反汇编、导入程序及模拟器；[交付审计](../logs/touch-ic-mode-delivery-audit.log)核对来源和关键分支。物理传输/IRQ、调度、内核链接、模式实际生效和当前实机根因未验证。这次没有生产改动或新镜像；OS4 正式版触摸 P0 仍未解决，震动及完整 12 组任务继续保留。

## 通知到达时仍有待执行任务

[新增 16 项](../logs/touch-pending-flush-emulation.json)覆盖两份 OS4 的原始 notifier、非空 flush、旧 worker 完成、新 worker 排队和下层显示恢复/IC 模式函数。[程序](../tests/touch_pending_flush_emulation.py)刻意不在相邻通知间排空队列。原始通知到 `__flush_workqueue` 时保存 CPU 上下文，在另一栈执行已排队的原始 worker，再恢复原通知继续排新任务。每个入口最多两段、每段 10 万指令/2 秒；未知服务、额外 flush 或超限均失败。沿用显式跨模块 callback 桥和控制器应答，没有运行真实 Linux 调度器或同时执行两个通知。

正常 off→on、off→on→off→on 保留对应回调顺序；重复 off/on 的旧任务先在 flush 执行，新任务随后因原厂休眠标志跳过。新任务明确被 queue 拒绝时，已经 flush 的旧任务状态仍保留，不把拒绝解释为真实内核会随机丢任务。此前只有空队列覆盖，本批补上的是有限顺序 flush，不是任意竞态验证。

配置获取失败的 resume 在下一次亮屏通知的 flush 内执行：原厂仍留下 active=1、wrapper 非休眠、cfg=0；新排的重复亮屏 worker 跳过下层，合成报文无坐标。错误解除后经新的 off→on 可重新获取配置并输出合成坐标。这与此前逐次 drain 的故障机制一致，未发现正式版独有差异，也不证明本次设备故障属于该路径。

复现：`python3 tests/touch_pending_flush_emulation.py > logs/touch-pending-flush-emulation.log 2>&1`。报告复核既有 DT/模块/反汇编/模拟器及全部导入程序指纹；[本批交付审计](../logs/pending-flush-irq-delivery-audit.log)同时检查失败快照、flush 的非空队列和恢复配对。当前生产树与 module-state 镜像未改，OS4 正式版触摸 P0、震动及整体 12 组目标保持未完成。

## 原始启动接通 Xiaomi panel/input 注册

[新增两包共 16 项](../logs/touch-joined-registration-emulation.json)将原始 Synaptics DT/panel/connect/后台与原始 Xiaomi `register_touch_panel`、`register_xiaomi_input_dev` 接通。参数直接复制原始 setup 生成的 0xd6 字节；两个 ARM64 空间以显式 host 桥传递结果，不是实际内核链接。wrapper callback 表仍为夹具，input 对象使用同一数值地址在两侧独立映射，验证 Synaptics 写下其 private context，不声称完整对象内存共享。input core、分配/注册/slots、线程/proc/mode/notifier、控制器应答与 lockdown 仍为边界。本批固定请求固件返回 -2，以隔离原始注册接续，不重复模拟固件更新。

正常场景实际执行 wrapper 注册 10 个 Type-B slots、143999/319999 两轴，后台得到 input，原始 ISR 输出所供合成坐标。panel 队列分配失败返回 -1，connect 仍成功、后台仍能单独注册 input 并解析合成报文；panel 温度线程 -12 的原始返回为 0，panel mask 已置位。slots -12 也被忽略，仍请求 input 注册；此时合成 input 服务仍接收事件，不能推断真实 input core 在 slots 失败后正常工作。cfg 获取超时场景虽两侧注册成功，仍 cfg=0、无坐标。

input 分配失败或 input_register_device=-12 时，wrapper 返回 0；后者还执行 input_free_device。两份 Synaptics 后台随后都执行 `str x19,[x0,#0x2c0]`，**先写空指针偏移 0x2c0，之后才有 cbz x0**。模拟捕获唯一未映射 8 字节写，核对 x0=0、value=CTX、原始指令字节 `13 60 01 f9`，立即终止该 worker，不映射零页、不继续 ISR，也不把它算作正常返回。旧版指令在模块偏移 0x1c7b4，正式版 0x1c9f0，保存反汇编并绑定哈希。这确认原厂错误路径的可达性，**没有证据表明本次用户启动发生了 input 分配/注册失败**，不能据此认定根因或承诺空指针补丁能恢复触摸。

最初测试假定 input 失败会返回且无事件，被未映射写拒绝后改为上述终止断言；panel 队列/线程返回也按实际分支纠正，全部重跑。[程序](../tests/touch_joined_registration_emulation.py)保留这些准确边界，未知服务与非预期内存错误仍失败。复现：`python3 tests/touch_joined_registration_emulation.py > logs/touch-joined-registration-emulation.log 2>&1`。[交付审计](../logs/touch-joined-registration-delivery-audit.log)核对原始模块、DT、既有依赖、反汇编、模拟器和关键分支。生产设备树/模块/当前镜像未改，OS4 正式版触摸 P0、震动与全部 12 组目标保持进行中。
