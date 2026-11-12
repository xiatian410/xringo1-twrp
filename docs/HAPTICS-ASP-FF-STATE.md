# ASP 状态与独立 FF 播放接续

2026-11-12：两份 OS4 原始 A1 驱动各 7 场景执行完毕。未启用 ASP、启用以及启用失败的上下文均会请求相同 FF SINE 参数和 mailbox 命令。这是软件路径观察，不证明任何一路的物理震动，也不能排除实际时钟/路由/DSP 的影响。没有生产修改或新镜像。

## 接续范围

`tests/haptics_asp_ff_join_review.py` 继承已有 A1 probe 接续，在同一个 Unicorn 地址空间执行原厂 probe/固件与参数解析/配置/input 自检，再执行真实 `cs40l26_clk_en`、`cs40l26_asp_start`、`cs40l26_swap_ext_clk`、`cs40l26_set_pll_loop`；随后提交从当前生产 `force_feedback.cpp` 捕获的 80ms SINE effect，执行真实 upload/play/start worker，并由原始 mailbox IRQ 消费显式提供的 TRIGGER_CP、COMPLETE_MBOX。

使用已审查的两份 OS4 `xring_audio_hw_third.ko`，SHA256 均为 `969a17203bf56c3d5b46e3a3ee1827cb3579aaa423c2fc21508e73d2548650f6`。A1 身份、原始 ROM 解析及 probe 基础边界沿用前轮，详见 `tests/haptics_a1_joined_review.py`。probe 自测结束后的计数/state 被显式复位为零；这不是手机实际状态读回。

## 结果

| 场景 | ASP 时钟回调返回 | FF 完成后 state/count/ASP 标志 |
|---|---:|---|
| 未启用 ASP | 未调用 | 0 / 0 / 0 |
| STOP 等待超时，后续时钟调用成功 | 0 | 2 / 0 / 1 |
| ASP STOP 命令返回 -5 | -5 | 1 / 0 / 1 |
| ASP START 命令返回 -5 | -5 | 1 / 0 / 1 |
| PLL 读取返回 -5 | -5 | 1 / 0 / 1 |
| 不支持的 BCLK=0 | -22 | 2 / 0 / 1 |
| PLL 位更新连续五次返回 -5 | -110 | 2 / 0 / 1 |

两版本的全部场景，FF upload/play 请求都返回 0，start worker 都写入 `BUZZ2 duration=20/frequency=125/level=64`、start duration=80、另一个播放参数=0，并请求 mailbox `0x01800081`。原始解析器与 get_reg 实际解析系数地址，无手填地址返回。没有额外 FF_GAIN 或波形变更。

`clk_en(event=2)` 在尝试启动前已把 ASP 标志设为 1，初始 state=2，即使后续失败也不回退。提供 TRIGGER_CP 后 count=1/state=1；提供 COMPLETE_MBOX 后 count=0。若 ASP 标志为 1，完成处理尝试再次 `asp_start`；再次失败的前三类场景保留 state=1，但 waveform completion 已饱和为 `0xffffffff`。因此 state=1 既不能单独证明仍有 FF 波形在播放，也不能代替计数、完成消息和实际输出。

正常时钟夹具也没有提供 STOP IRQ，13 jiffy 等待返回 0；原始回调警告后继续时钟切换，最终可返回 0。以本轮提供的 BCLK=3072000Hz，原始时钟路径请求 PLL mask/value `0x800/0x800`、`0x7e7/0x420`、`0x800/0`。五次 PLL 位更新失败则返回 -110；不支持的 BCLK 返回 -22。原始 probe 的增益默认值为 100，本轮不修改，因此未进入低于 100 的 ASP 增益 worker 调度分支。

## 边界与后续

codec/component/device 指针拓扑、3.072MHz BCLK、PLL read=0、13-jiffy 超时、kernel PM/锁/顺序队列、所有 regmap/mailbox 返回及 IRQ 消息均为显式夹具。BCLK 是驱动接受的模拟值，不是现场测量或对真实 DAI 配置的断言；写入不自动更新硬件读值。未知调用、有限指令/时间预算耗尽仍失败。没有真实 ALSA dispatcher、DAPM 图调度、时钟切换、DSP 执行或电机。

本轮降低了“原厂驱动纯软件上强制先开启 ASP 才发送 FF”这一假设的可信度；没有证明 ASP 对实际电气输出完全无影响。下一步需要检查 ASP 参数/PCM widget 的实际寄存器改变、A1 DSP/校准恢复与独立 FF 输出的关系。现有现场日志已经有播放/完成消息，进一步堆叠模拟成功不能替代每设备校准/寄存器读回。未盲加 PCM 路由、未修改增益或保护参数。

复现：`python3 tests/haptics_asp_ff_join_review.py`；交付绑定审核：`python3 scripts/audit_haptics_asp_ff_join_review.py`。结果保存于 `logs/haptics-asp-ff-join-review.json`，各 OS4 原始函数反汇编与审计报告并列。物理震动、设置现场、自动触摸与完整 12 组目标保持未完成。
