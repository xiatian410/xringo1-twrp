> 历史技术记录：OS4 震动现已由用户确认正常，已解决，不属于当前排查或例行检查。以下旧状态只对应当时的记录。当前进度见 [工作队列](../../WORK-QUEUE.md)。

# 原厂震动播放 worker 与初始化边界模拟

2026-11-11，六份 OS2/OS3/OS4 样本新增 **120 项播放/固件/I2C 包装模拟、54 项 probe 早期模拟**，全部通过。仅执行主机上的原厂 ARM64 模块指令；生产代码与当前镜像没有变化。当前候选仍为 `recovery-dijun-unified-haptics-worker.img`，来源见[震动适配记录](../../HAPTICS-ADAPTATION.md)。本轮未连接手机，物理电机仍为 U。

证据：[播放报告](../../../logs/haptics-playback-emulation.json)、[播放日志](../../../logs/haptics-playback-emulation.log)、[probe 报告](../../../logs/haptics-probe-emulation.json)、[probe 日志](../../../logs/haptics-probe-emulation.log)。两份报告绑定五个唯一原厂模块哈希、模拟器依赖和测试源码；播放报告另绑定当前生产 FF 源码。

## 播放路径：每份样本 20 项

[播放模拟器](../../../tests/haptics_playback_emulation.py)捕获生产 FF 的 80 ms 正弦请求，执行原厂上传回调与 worker、播放回调，再实际执行入队的 `cs40l26_vibe_start_worker` 和 `cs40l26_vibe_stop_worker`。这补充了[前一组生命周期模拟](HAPTICS-LIFECYCLE-EMULATION.md)只到播放入队的范围。

| 范围 | 每样本数量 | 断言 |
|---|---:|---|
| 上传→播放→start、停止→stop | 2 | 时长寄存器 80、触发源 0；start 邮箱 `0x01800081`，stop 邮箱 `0x05000000` |
| start 错误 | 7 | 第 1/2 次寄存器写、第 1/2 次 DSP 符号查询、邮箱、PM、缺失上传记录分别失败；不继续发送或更新状态 |
| stop 边界 | 3 | 配置 1200 µs 延迟产生 1200–1300 µs 请求；PM 失败不发送；邮箱失败被观察 |
| 固件请求与解析 | 3 | 普通/校准文件缺失返回 -2；注入解析错误 -22 后释放固件 |
| I2C 包装 | 5 | 分配、regmap、core probe 延迟/失败/成功；核对 device、regmap、IRQ 与 drvdata 传递 |

普通/校准请求文件分别为 `cs40l26.wmfw`、`cs40l26-calib.wmfw`。解析错误用例显式设置已初始化标志，绕过 DSP 硬件预配置；没有执行固件解析器。I2C 用例把 core probe 当作替身，只验证包装层的参数和错误传播。

运行时 PM、DSP 符号查找、regmap、邮箱、状态更新、睡眠与队列服务均有明确夹具。状态更新钩子只记录调用，不注入 IRQ 或完成事件；延迟只记录请求，不等待对应墙钟时间。这些用例不证明真实 DSP 接受邮箱或电机输出。

## 初始化路径：每份样本 9 项

[probe 模拟器](../../../tests/haptics_probe_emulation.py)执行原厂 `cs40l26_probe`，不替换 probe 本身。它重新用 AOSP libfdt 合并每份原始 DTBO 的第 5 条与对应基础 DTB，核对合并哈希和完整 CS40L26 属性，并确认该节点没有子节点，再将这些属性提供给内核属性 API 夹具。原始分区与合并来源见[DTBO 记录](HAPTICS-LIFECYCLE-EMULATION.md)。没有模拟 bootloader 的板型选择。

| 注入失败的位置 | 六样本观察到的 probe 返回 | 其他断言 |
|---|---:|---|
| workqueue 分配 | -12 | 未注册 input，调用 remove 边界 |
| 获取稳压器 | -517 | 未进入后续电源步骤 |
| 启用稳压器 | -5 | 未进入 GPIO/pinctrl 步骤 |
| 获取复位 GPIO | -517 | 未进入 pinctrl 步骤 |
| 获取 pinctrl，返回 -517 | **0** | 调用 remove 边界，未注册 input |
| 获取 pinctrl，返回 -5 | -22 | 直接返回，未调用 remove 边界 |
| 查找默认 pinctrl 状态，返回 -5 | **0** | 调用 remove 边界，未注册 input |
| 选择 pinctrl 状态 | -5 | 未进入 PLL 步骤 |
| PLL 边界 | -5 | 此前已按原始顺序请求 1500–1600 µs、复位逻辑值 0、6000–6100 µs |

最后一项同时核对原厂读到 `cirrus,f0-default = 130 << 14`，以及 `fw-defer`、`rom-only` 标志为假。所有路径均在 PLL 访问失败前后终止，未执行 DSP 启动、IRQ 和后续 input 初始化；稳压器/GPIO/pinctrl 是显式句柄夹具，remove 只记录入口，没有验证内部清理。复位逻辑值不等于已测量的引脚电平。

原厂 pinctrl 错误分支可能返回 0 的结果来自原始指令执行，不能把它解释成历史无震动的确诊。它进一步说明模块加载、probe 返回、input 注册和实际播放需要分别验证。本轮没有修改原厂二进制，也没有用强行忽略错误的方式适配。

## 复现与后续

```bash
python3 scripts/setup_haptics_emulator.py
python3 tests/haptics_playback_emulation.py
python3 tests/haptics_probe_emulation.py
python3 tests/haptics_pll_emulation.py
python3 scripts/audit_unified_delivery.py
```

新增 [PLL/芯片识别报告](../../../logs/haptics-pll-emulation.json)：六个样本共 80 项原厂 ARM64 模拟通过。OS2/OS3 的 PLL 五次 `regmap_update_bits_base` 失败路径、模式参数和 probe 收尾均执行；OS4 另执行 CS40L26 ID/revision 读取、已知/未知芯片分支、I2C 读取错误，以及原始 probe→PLL→芯片识别的失败接续。寄存器读写、芯片响应、remove 与后续 firmware/DSP 入口是边界，不把成功识别解释成 PLL 锁定或电机可用。

仍待补齐 PLL/芯片识别之后的完整固件解析与 DSP 启动、IRQ/完成事件，以及完整 GUI 页面和业务调用者联调。真实内核调度、供电、I2C 与电机输出保持 U。生产镜像未变，本轮无需重编译；以后生产改动继续使用最终 installclean 与 `make -j$(nproc)`。

后续当前候选更新为 `recovery-dijun-unified-module-state.img`，见[触摸排查](../../OS4-TOUCH-FAILURE.md)；本页原厂 ARM64 用例没有生产源码变化，仍属于有效的函数模拟证据。

后续新增两包正常/校准共 64 项[实际 DSP 固件解析与系数初始化](HAPTICS-FIRMWARE-EMULATION.md)，替代本页早期用例中整段 parser 失败夹具的局部覆盖；本页原 120 项用例的边界保持原样。当前交付为 `recovery-dijun-unified-module-state.img`，物理震动仍未验证。
