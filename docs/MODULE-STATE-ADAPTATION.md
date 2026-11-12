# 模块初始化状态：依赖就绪判断修正

2026-11-12 当前证据入口更新：`python3 scripts/review_module_state_reference.py`重新核对固定摘要的Linux v6.6参考源码，检查complete_formation设置coming、sysfs发布与init/live顺序等七项，并将原始show_initstate函数在主机结构夹具上执行三种状态。另逐字节复核六份原厂boot kernel的initstate/coming/live/going字符串位置与内核摘要；字符串仍仅是接口佐证，不证明下游实现完全等价。程序同时核对当前backup-manifest镜像脚本的4组/24次阶段报告、同测试来源的旧脚本14个失败对照，确认既有报告来源仍匹配，因此未重复运行未变化的夹具。新报告`logs/module-state-reference-current.json`包含依赖；原`logs/module-state-review.json`原样保留为历史记录，没有只替换其过期测试摘要。

总审计改为读取索引中的新reference review并检查状态输出/顺序/两份脚本报告关联，不放宽模块就绪要求。`logs/module-state-reference-unified-audit.log`现通过738份生产来源、当前镜像入口、模块状态和六包依赖计划，随后在历史settings-persistence报告的data.cpp绑定处拒绝继续。完整索引新鲜度为124匹配/95漂移/20无充分绑定，见`logs/module-state-reference-freshness.json`；这是证据有效性计数，不是功能通过率。用户已确认当前设置正常，此来源漂移不构成新的设置故障。没有生产代码或镜像变化，不宣称异步probe、触摸或电机已恢复。

历史候选 [recovery-dijun-unified-module-state.img](../imgs/built/recovery-dijun-unified-module-state.img) 的 SHA-256 为 `c282f535b1fdac6f5eafe25ca46116441195affe9d67f4511178a930634c4346`，已从原始构建输出恢复；来源清单为事后重建，封装与当前二进制重新核验通过。此历史候选修正启动脚本的模块状态判断与可选震动加载顺序，不能宣称 OS4 正式版触摸或震动物理输出已恢复。未连接设备。

旧脚本把 `/sys/module/<name>` 目录存在作为“已加载”和硬依赖就绪条件。内核会在运行模块初始化函数前发布 sysfs，目录也可能存在于退出过程中。因此模块仍处于 `coming`、`going`，甚至初始化失败尚未清理时，下游驱动可能被过早尝试；触摸状态也可能被误写为 loaded。上游 Linux v6.6 源码展示这一顺序，六份原厂内核均包含 initstate/live/coming/going 接口字符串；这些是接口证据，不等于证明手机曾走该路径。来源见[审查指纹](../logs/module-state-review.json)。

[生产脚本](../dtsrc/O1_asic_dual/profiles/runtime/dijun-runtime.sh)现仅接受 `initstate=live`：

- cache 只跳过明确 live 的模块，其余模块仍从匹配固件按哈希暂存。计划中的条目均有原始 `.ko`，没有按目录推断 built-in。
- 已存在但 coming 的模块最多轮询 20 次、每次请求等待 100 ms；going、未知或无法读取状态立即拒绝。不会卸载或重新插入仍存在的模块。
- 硬依赖必须 live；触摸因硬依赖不满足被跳过时明确写 failed。insmod 成功返回后仍检查状态，无法确认 live 则标记 partial。
- 每个阶段开始把 modules 状态设为 pending，避免重试期间沿用上次 complete。模块状态只证明模块初始化结束，不证明异步 probe、input、固件或事件已就绪。

单次 coming 等待约 2 秒，整体仍受 C++ 的 45 秒外层期限约束；调度延迟可能增加实际经过时间，永久内核 I/O 不能靠 shell 超时保证回收。缺少 initstate 的计划模块会被保守拒绝，未添加宽松回退。crypto 发布仍使用原有独立前置条件，额外外设模块失败不自动阻断已有安全组件。

后续 profile 计划在完成触摸依赖闭包后优先排入震动专属依赖闭包，避免原来排在第 51/54 位的可选音频/震动 probe 被 45 秒总期限截断；全部硬/软依赖顺序仍由计划检查。runtime 会在模块阶段结束时有界检查 `/proc/bus/input/devices` 中 `cs40l26_input`，写入独立的 `twrp.profile.haptics_input` 状态。该状态区分 `initstate=live` 与 input 注册，但不检查 EV_FF ioctl、节点权限或实际输出。

[六包模块计划检查](../logs/touch-priority-plans.json)现同时断言触摸闭包先于震动专属闭包；[主机 runtime 回放](../logs/haptics-input-profile-runtime.log)覆盖立即注册、延迟注册与缺失 input。此回放没有执行 kernel I2C probe，不表示真实 input 或电机可用。

[同镜像状态回放](../logs/module-state-image-test.json)四组、24 次阶段调用通过，覆盖初始化后 live/going/消失/停留 coming、非 live 硬依赖、成功退出却没有 live 状态、六包 cache 保留模块字节。状态和 sleep 为确定性夹具，真实脚本与 OTA 字节执行；不是真实内核加载。[旧脚本同夹具对照](../logs/module-state-before.json)出现 14 个子用例断言失败。完整六包两槽位及原有异常回放仍为 8 组、96 次调用，见[运行时结果](../logs/module-state-profile-runtime.json)。

按 30 并发 `make -j$(nproc) installclean` 后构建，[构建日志](../logs/build-module-state-final.log)、[镜像检查](../imgs/built/recovery-dijun-unified-module-state.json)和 [707 份来源](../imgs/built/recovery-dijun-unified-module-state-sources.json)已保存。12 项通用策略、6 份 init 和 53 项 USB 专用域检查通过。仅生产 shell 改动，recovery C++ 补丁集未变。上一份 touch-priority 产物保留。

复现：

```bash
python3 tests/module_state_test.py --image imgs/built/recovery-dijun-unified-module-state.img --output logs/module-state-image-test.json
python3 tests/module_state_test.py --script backups/module-state-pre-fix/dijun-runtime.sh --output logs/module-state-before.json
```

第二条预期非零退出、14 个断言失败。改测试夹具后须同时重跑两条和完整运行时报告，再更新证据指纹。下一步继续触摸控制器识别/SPI/panel 边界与 haptics DSP/IRQ；本修正不是本次实机根因结论。
