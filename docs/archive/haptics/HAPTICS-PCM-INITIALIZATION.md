> 历史技术记录：OS4 震动现已由用户确认正常，已解决，不属于当前排查或例行检查。以下旧状态只对应当时的记录。当前进度见 [工作队列](../../WORK-QUEUE.md)。

# OS4 原厂 PCM 与波形库初始化核查

后续[服务线程/XML核查](HAPTICS-SERVICE-THREAD-XML.md)已推进原始worker到首次等待，发现后台会请求Source=PCM、ASP/TDM及PCM open。下文“没有控制写入”仅限PCM/data/AAC构造范围，不能推导整个服务没有音频初始化，也不能排除其对独立FF的间接依赖。后续仍未证明这项差异造成物理无震动，生产镜像保持046ab9e3。

2026-11-12：两份 OS4 原厂服务确实根据 `ro.odm.mm.vibrator.device_type=pcm` 选择 PCM 后端。这次执行了该选择、PCM 构造及 AAC 波形库初始化本体，补上此前单独 FF 后端检查的范围缺口。已执行范围没有额外供电或 mixer 控制写入，尚无依据把 PCM 初始化加入 Recovery 作为无震动修复。

证据为 [执行程序](../../../tests/haptics_pcm_init_review.py)、[26 项结果](../../../logs/haptics-pcm-init-review.json)和[来源核对](../../../scripts/audit_haptics_pcm_init_review.py)。两份服务 SHA256 均为 `0eacb88e11a3402b1551b79cc85e3cfcbbd518c7da44684fc5354829e27be2e7`，两份 `libaachaptics.so` 均为 `3f8bb19b8a739fcd37ca557c83b808a48417bc7a1a10be95c7306530b62e1221`；属性、XML、反汇编、测试和模拟器文件也绑定摘要。

## 实际执行范围

1. 在同一模拟地址空间先执行原始输入发现前缀 `0x12ce0..0x13084`。恢复校准仅记录调用，目录、能力 ioctl、属性和 mixer 是显式边界。
2. 单独执行原始库列表初始化 `0x27f08..0x27f44`，取得 AAC、AWA 两个绝对路径。未执行整个 ELF loader 或其他全局初始化。
3. 显式跳过替代设备与配置 map 范围 `0x13084..0x1324c`，设置外层对象寄存器，连续执行 `0x1324c..0x1349c`：原始 selector → PCM 对象构造 → 波形数据对象构造。后续服务线程、XML 消费和完整 constructor 尚未执行，不能称为完整服务启动。
4. AAC 的 dlsym 指向映射后的真实函数。原始 `aac_haptics_init` 本体在上述调用上下文执行，相对重定位实际应用；malloc、libc/math、信号量和线程接口为显式边界。原始线程入口 `0xf558` 仅记录，未调度。AWA 后备库的初始化本体没有执行，仅记录频率参数。
5. 随后在该部分构造的对象上调用原始普通 `on(80ms)`。XML 的 long-id=31 与 restore-complete 标志显式提供；callback 为空，不创建计时线程。不是完整 Binder/服务生命周期接续。

所有执行有有限预算，未知调用立即失败；连续 PCM/AAC 范围最多 100 万条指令、10 秒，输入发现沿用 10 万条、2 秒限制。sysfs 与文件内容为内存夹具，未读写设备或主机硬件。

## 发现及含义

| 观察 | 可以支持的结论 |
| --- | --- |
| 原始 selector 返回 1，PCM 构造设采样率 48000、端口 `XR_TDM7_RX`；对象配置六个 32 位字为 `[48000,0,24,0,4,0]` | 原厂实际选择 PCM 构造；不是此前单独 FF 分支。这里的数组是对象内存字，不擅自解释为完整 ALSA 参数 |
| 构造打开 mixer card 0、保存配置，没有 `pcm_open`、mixer 控制写入或播放请求 | 这些构造指令本身没有发出额外控制；后续线程、路由及 DAPM 不在本次结论范围 |
| `f0_value` 文本转整数后除 10，与属性 130 比较 | 合成 120/140 Hz 被接受，119/141 Hz 与缺文件回退到 130；不是实际芯片读回或校准成功 |
| AAC 接收 `[512,48000,1,130]`，初始化分配内存、计算滤波系数，申请信号量/mutex，创建后分离工作线程 | 原始 init 本体已执行，但线程创建由夹具返回。没有执行 AAC 工作线程、音频流、DSP 或电机 |
| 首次分配失败返回 -2、信号量失败返回 -1；服务仍返回到波形数据构造之后 | 库初始化失败没有阻止这个构造范围继续；constructor 到达末端不是波形库就绪证据 |
| pthread_create 返回 POSIX 错误 11 时，原始库只检查负数，继续请求 detach(0)，最终返回 11；服务同样忽略 | 记录原厂错误处理边界；这是故障注入，不证明现场发生了线程创建错误 |
| mixer 缺失、所有库缺失、init 符号缺失及 AAC 初始化错误后，单独普通 on 入口仍提交 gain100 → CUSTOM31 → play | 在明确提供 long-id/恢复标志的部分上下文中，普通 on 不调用 PCM backend；仍不能排除完整启动和设备音频状态的间接依赖 |

每份样本 13 场景：正常、mixer 缺失、频率文件缺失、频率范围两端及越界、首库缺失后备 AWA、所有库缺失、AAC init 符号缺失、分配/信号量/线程创建失败。普通 on 请求逐条核对 24 字节 gain/play、48 字节 effect 与 CUSTOM `{0,31}` 数据。

## 交付与后续

当前镜像仍为 `recovery-dijun-unified-mtp-reset.img`，SHA256 `046ab9e356e5301661daa4ff7dd6a29504cee7706ee32da0353d988f7e6a4e27`。本轮只有证据、测试和文档修改，没有改生产路径或重新构建；定向审计核对当前镜像与 735 份生产来源。历史全量审计仍不作为本轮通过依据。

物理无震动、触摸自动恢复、设置现场问题及完整 12 组目标保持未解决。下一初始化缺口是原厂服务线程/XML/后端派发与普通 on 的完整生命周期连接；实际校准、保护、供电和 DSP 状态还缺设备自身读回。现有采集请求保留，不重复要求相同日志，不改写校准值、保护参数、波形或 PCM 路由。

复现：

```bash
python3 tests/haptics_pcm_init_review.py > logs/haptics-pcm-init-review.log 2>&1
python3 scripts/audit_haptics_pcm_init_review.py > logs/haptics-pcm-init-review-audit.log 2>&1
```
