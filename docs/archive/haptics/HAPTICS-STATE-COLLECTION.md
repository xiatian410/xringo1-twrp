> 历史技术记录：OS4 震动现已由用户确认正常，已解决，不属于当前排查或例行检查。以下旧状态只对应当时的记录。当前进度见 [工作队列](../../WORK-QUEUE.md)。

# OS4 无震动状态采集

已有现场日志包含43次成功SINE上传、start worker和配对mailbox完成，不能再用模块列表或input注册作为下一轮主要证据。本工具补充设备校准、原厂服务路径及DSP状态；不自动播放，不写sysfs，不触发校准，不修改增益，不挂载persist，不清理日志。

## Windows 使用

将[PowerShell入口](../../../scripts/collect-haptics-state.ps1)和[设备侧脚本](../../../scripts/collect-haptics-state.sh)放在同一目录。已在Recovery且ADB可用时，在该目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\collect-haptics-state.ps1
```

多个ADB设备时，追加 `-Serial 设备序列号`。脚本不会执行wait-for-device，不会重启或刷写；未连接到一个Recovery设备时直接报错。输出当前电脑目录的 `dijun-haptics-state-日期时间-PID.zip`。无需重新执行整套触摸采集，也无需按提示播放或测试震动。

入口将脚本推送到唯一的`/tmp/dijun-haptics-state-日期时间-PID.sh`，通过`adb shell sh`执行，再拉取输出并压缩。设备侧拒绝已有目录或符号链接，避免混入上一次结果。Windows/Android端尚未执行；主机检查使用实际POSIX sh与私有文件。

## 内容与副作用

首先保存dmesg、IRQ、uptime和Recovery日志，再读取属性。驱动的dsp_state、fw_rev、f0/redc/q_stored及overprotection_gain的show路径含PM resume/寄存器访问，**这些读取可能唤醒DSP并产生PM/mailbox日志**；它们不是完全被动的内存快照。读取后的日志必须与before区分，不将新出现的PM活动当作采集前故障。vibe_state只读缓存/锁。

只在`/proc/mounts`确认persist已挂载到`/mnt/vendor/persist`时，读取原厂服务使用的三个文件：`haptics/vib_cal_z`、`vib_cal_f0`、`vib_cal_q`。不读取其他persist内容、TEE密钥或用户文件。保留原始十六进制文本，不把模拟测试中的数值用作设备校准。

通过`cs40l26_input`名称发现input，不固定event4/input4。OS4 current/stable两个原始模块的ELF属性表均已核对，允许读取：

| 分组 | 属性 | 解释限制 |
|---|---|---|
| default | vibe_state、dsp_state、fw_rev | 软件/固件状态，不是电机位移证明；dsp_state读本身会唤醒DSP |
| default | overprotection_gain | 保护算法参数，**不是通用evdev FF增益**；未提供通用FF增益读回 |
| calibration | f0_stored、redc_stored、q_stored | 已存DSP校准值；q在B2条件下原始驱动拒绝，拒绝不等于静音原因 |

其他profile只采集日志、已挂载的原厂校准文件和节点元数据，跳过未审核驱动属性并报告partial。禁止递归读取sysfs/debugfs；不读取trigger_calibration、swap_firmware、fw_ctrl_val或max_vbst/logger最大值。保留固定I2C路径的ls元数据，用于比对原厂`xring-smartpa`路径与现场`xring-haptic`绑定，路径缺失本身不证明原厂恢复或驱动失败。

每次命令有2或3秒用户态期限，每个节点至多复制4096字节。Linux不可中断内核I/O仍可能推迟进程退出，timeout不是内核事务可取消的保证。节点读失败继续保存其余结果；`READ_EXIT`与`commands.tsv`记录错误，`collection-exit.txt`非零表示部分采集。缺少persist挂载、节点或未知profile都不能当作完整采集成功。入口仍尝试保存partial包。

## 离线检查与下一判断

运行`python3 tests/haptics_state_collector_test.py`。11项私有文件执行覆盖正常、节点缺失、读错误、阻塞FIFO超时、persist未挂载、未审核profile、无匹配input、已有目录/符号链接、非法输出及缺timeout；检查输入文件未改、敏感/校准触发节点未打开、初始dmesg早于状态读取。另从两份原始OS4 ELF重定位属性组，核对7项名称、分组、可读权限与show指针。结果为[主机报告](../../../logs/haptics-state-collector-test.json)。未执行Windows、Android、I2C、DSP或物理震动。

若设备persist文件与stored值不同，先核对原厂格式、单位、芯片revision和恢复路径失败，再决定初始化适配；不能直接写回或启动校准。若相符，继续原厂播放参数、保护衰减与供电链。无论何种结果，mailbox完成和状态可读都不能证明电机正常。
