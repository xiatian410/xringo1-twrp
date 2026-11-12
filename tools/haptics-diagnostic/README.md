# dijun 震动请求诊断工具

此工具独立于Recovery镜像，尚未在设备运行。不恢复或生成校准、不写persist/sysfs、模块、SELinux或触摸报告模式。`--inspect`只查询；四个显式播放入口分别控制波形与是否写入FF_GAIN=100。

| 入口 | 波形 | 写FF_GAIN | 时长限制 |
|---|---|---|---|
| `--play` | 当前Recovery SINE，period8/magnitude64 | 无，保留当时增益 | 1..10000ms |
| `--sine-gain100` | 完全相同的SINE | 100 | 1..1000ms |
| `--custom-existing-gain` | 原厂CUSTOM {0,31}，replay0 | 无，保留当时增益 | 1..1000ms |
| `--stock-long` | 完全相同的CUSTOM | 100 | 1..1000ms |

这四种请求补齐此前SINE/不写gain对CUSTOM/gain100同时变化两个因素的缺口。**不写增益不等于恢复默认增益**：显式gain100会保留，close不恢复，后续“不写增益”沿用这一值。工具没有通用增益读回，必须保留执行顺序和当时状态，不能把跨次请求当作独立初态实验。没有自动串行跑四种模式或自动恢复状态。

静态ARM64文件、构建输入和哈希见相邻`haptics-diagnostic-arm64.json`。使用当前Android bionic构建；编译target为android35，现有CRT的ELF note标识Android36。没有验证OS2运行兼容性。

```sh
python3 tools/haptics-diagnostic/build.py
python3 tests/haptics_diagnostic_test.py
python3 tests/haptics_diagnostic_arm64_test.py
```

设备侧接口如下，仅为用法说明，本轮未执行ADB或这些设备命令：

```sh
/tmp/haptics-diagnostic --inspect /dev/input/event4
/tmp/haptics-diagnostic --play /dev/input/event4 80
/tmp/haptics-diagnostic --stock-long /dev/input/event4 80
/tmp/haptics-diagnostic --sine-gain100 /dev/input/event4 80
/tmp/haptics-diagnostic --custom-existing-gain /dev/input/event4 80
```

event4只来自已有现场日志，必须以实际input名称为准。播放要求严格名称`cs40l26_input`；工具无参数只显示帮助，不会自动播放。

- `--inspect`以只读fd查询名称/能力。
- `--play`要求PERIODIC/SINE，提交SINE、8ms周期、64幅度、1..10000ms时长。
- `--sine-gain100`额外要求GAIN，先写原厂值100，然后保持SINE的全部effect字节；无任意增益参数。
- `--custom-existing-gain`要求PERIODIC/CUSTOM，CUSTOM请求与stock-long完全相同，但不查询或设置FF增益；无GAIN能力仍可提交。
- `--stock-long`要求PERIODIC/CUSTOM/GAIN，只供已核对的dijun OS4 current/stable驱动。固定使用原厂HAL的gain100、FF_PERIODIC/FF_CUSTOM、custom_len2、custom_data={0,31}、replay.length0；等待后EVIOCRMFF擦除以停止，时长限1..1000ms。不提供任意编号、幅度或增益参数。

工具本身不识别固件版本或读取RAM波形数量，不能由名称/能力推断其他版本编号31有效。现有OS4现场有43个RAM波形，但不能把这个计数转移到其他启动。编号、时长、ABI、原厂服务请求证据见[适配记录](../../docs/HAPTICS-ADAPTATION.md)和[原厂请求报告](../../logs/haptics-service-request-emulation.json)。

当前47项主机syscall替身检查与18项QEMU目标启动/拒绝/普通文件失败检查通过；SINE两入口effect字节一致，CUSTOM两入口除地址指针外全部字节与原始HAL捕获一致，数组4字节也核对。QEMU没有模拟成功EVIOCSFF或电机；主机成功路径依赖显式syscall替身。新工具不是震动修复镜像，不构成现场已恢复结论。

CUSTOM长震动依赖用户态擦除停止，内核阻塞可能使实际时长超过请求；退出/close清理也依赖驱动。gain100来自原厂HAL，不是通用FF常用的65535。工具不恢复旧增益，因为没有已核对的通用FF增益读回；新值会保留至后续修改或驱动重新初始化。两条播放入口同时存在波形和显式增益差异，因此不同表现不能单独归因于CUSTOM编号。

每一步输出BEGIN/END、返回码、errno和单调时间：open、name、capabilities、可选gain、upload、play、erase、close。BEGIN立即刷新；不为内核ioctl承诺可取消超时。即使外部timeout发信号，D状态调用也可能不能立即退出。保持拥有fd至等待结束后再擦除，避免提前close删除效果。失败时不重试另一播放模式，不触发校准。

31项主机syscall替身检查覆盖顺序、短写、失败、参数/能力拒绝，以及SINE与Recovery捕获一致、CUSTOM与原始HAL捕获一致。CUSTOM比较完整ff_effect（仅规范化两者运行时指针）及所指4字节，验证gain100先于upload。不是DSP或电机证据。

另有12项QEMU用户态实际ARM64启动/参数/缺路径/普通文件失败检查。使用唯一数字event路径并确认主机不存在同名节点；普通文件在临时QEMU前缀内，真实bionic/name ioctl失败后关闭，没有成功gain/upload/play。QEMU Linux-user不等于Android内核或SELinux。结果在`logs/haptics-diagnostic-test.json`和`logs/haptics-diagnostic-arm64-test.json`。

QEMU来自Debian qemu-user `1:10.0.13+ds-0+deb13u1`，提取而未安装或注册binfmt；来源、版本和哈希见`tools/qemu-user/source.json`。诊断工具不是生产震动修复，当前Recovery镜像未改。
