# 原厂震动驱动函数离线模拟

2026-11-11，六份固件完成 120 项主机模拟，报告为 [JSON](../logs/haptics-driver-emulation.json)、[日志](../logs/haptics-driver-emulation.log)。本次没有改动 recovery 生产源码或重新构建镜像；当前镜像及其来源见[震动适配记录](HAPTICS-ADAPTATION.md)。

这轮新增证据回答一个具体问题：当前生产 FF 请求的二进制结构、正弦周期、幅度和播放事件，能否被各版原厂驱动中已检查的函数正确解析。它不验证驱动 probe、DSP 固件实际加载、I2C、电源、内核调度或物理电机。

## 执行范围

[捕获器](../tests/haptics_driver_capture.cpp)编译实际 `twrpminui/force_feedback.cpp`，仅替换 input 路径、能力 ioctl、属性读取和事件输出。捕获 48 字节 `ff_effect` 及 24 字节 `input_event`，原始十六进制保存在报告中。Linux input core 的 ID 分配使用夹具值 7；不模拟 core 的权限、ID 分配器或效果生命周期。主机与目标均为小端、64 位 ABI，效果结构长度被显式断言。

[模拟器](../tests/haptics_driver_emulation.py)读取原始 `.ko` 的 ELF alloc 节，应用模块中出现的 AArch64 重定位，并由 Unicorn 执行原始指令。未知重定位、未处理的导入、执行异常和指令预算耗尽均使测试失败。没有重写频率/幅度/时长计算模型，也没有把驱动替换为返回成功的上传函数。

- OS2/OS3：执行原厂 `cs40l26_upload_worker` 的正弦分支；该代码在工作线程中内联，未单独导出正弦上传函数。
- 两份 OS4：执行原厂 `cs40l26_sine_upload`；其外层上传工作线程没有在这项测试中执行。
- 六份样本：执行原厂 `cs40l26_playback_effect`，检查它选中的效果指针和 start work 地址。

输入设备、FF core、已初始化的驱动上下文和效果链表使用合成内存。OS2/OS3 与 OS4 的布局不同，分别从原始指令读取偏移，并绑定五份唯一驱动 SHA-256；未知驱动哈希拒绝运行。OS4 正式版与旧 OS4 的震动模块字节相同，仍分别执行样本用例。

内核边界替身包括日志、内存分配/释放、mutex、runtime PM 和单调时间。DSP 符号查找返回合成寄存器：OS2/OS3 截取 `cl_dsp_get_coeff`，OS4 截取 `cl_dsp_get_reg`。`regmap_write` 记录参数或注入错误，`queue_work_on` 只记录入队请求。没有执行校准或读取/修改真实 persist。

## 用例与结论

每个样本 20 项，共 120 项：

| 范围 | 每样本数量 | 核对结果 |
|---|---:|---|
| 实际生产请求 1/40/80/160/300/500/10000/20000 ms | 8 | 底层时长上限 10000 ms，原厂写入 DSP 时长 `(ms+3)/4`、频率 125 Hz、幅度 64 |
| 对应播放回调 | 8 | EV_FF / ID 7 / value 1 选中正确效果并请求 start work |
| 第 1/2/3 次寄存器写入失败 | 3 | 原厂正弦上传返回或工作线程记录 `-EIO`，后续寄存器不继续写入 |
| 五个正弦槽均被占用 | 1 | 返回或记录 `-ENOSPC`，没有写入 DSP 寄存器 |

当前生产请求与已执行的原厂处理路径没有发现协议不匹配。130 Hz 配置经过 FF 整数毫秒周期取整成为 8 ms，驱动解析为 125 Hz。该结果不能解释历史实机无震动的唯一根因，也不能证明当前镜像已经恢复震动。

后续的[生命周期与 DTBO 复核](HAPTICS-LIFECYCLE-EMULATION.md)已补充 90 项注册/上传/擦除/重复回调模拟和 48 次原始 overlay 合并。完整电源/复位/固件 probe、start/stop/IRQ、真实工作调度仍待补齐；GUI 线程隔离已有[后台 owner 回归](HAPTICS-WORKER-ADAPTATION.md)。真实硬件项保持 U，本轮不要求实机操作。

## 复现

依赖仅安装在主机 `tools/haptics-emulator-python`，不进入 ramdisk。固定的 Unicorn 2.1.4 与 pyelftools 0.32 wheel URL/SHA-256 见[依赖锁](../tests/haptics-emulator-dependencies.json)；安装器核验 wheel 摘要，交付审计还核对实际 Python/共享库文件摘要。

```bash
python3 scripts/setup_haptics_emulator.py
python3 tests/haptics_driver_emulation.py
python3 scripts/audit_unified_delivery.py
```

依赖安装器当前固定 Linux x86_64 wheel；原厂模块与六份 profile 需已提取。测试使用临时文件和内存，不访问真实 input、块设备或 sysfs。
