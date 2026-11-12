> 历史技术记录：OS4 震动现已由用户确认正常，已解决，不属于当前排查或例行检查。以下旧状态只对应当时的记录。当前进度见 [工作队列](WORK-QUEUE.md)。

> 历史记录：以下为 OS4 单版本中间产物的原始适配记录，不是当前交付。当前统一候选见 [震动适配](HAPTICS-ADAPTATION.md)。

# dijun 震动离线适配记录

日期：2026-11-11。用户反馈上一版震动仍不工作。本次没有连接手机，也没有要求新的实机测试。

## 新候选与可复核结果

文件：[`twrp-recovery-haptics-mtp.img`](../imgs/built/twrp-recovery-haptics-mtp.img)

- SHA-256：`28ae2d8b62fc5e43e1e5f091accd3059c9241c421afcbe633f23125e3b87384c`
- MD5：`a7702f3514c79bdcfe150e875753d754`
- 镜像 104,857,600 B；压缩 ramdisk 80,305,746 B。头页与对齐后的 ramdisk 合计 80,310,272 B，余下 24,547,328 B 是填充与封装预算，不等同于可随意添加的原始文件大小。
- 已执行 `make -j$(nproc) installclean`、`make -j$(nproc) recoveryimage`，30 并发。
- 最终镜像中的策略、130 Hz 属性、FF 库和当前构建一致；55 项基线解密条目保持一致，具体比较字段见检查脚本。
- 物理震动结果：**U，未验证**。当前候选仍使用 OS4 解密组件，不是已经完成的 OS3/OS4 通用镜像。

证据：[构建日志](../logs/build-haptics-mtp.log)、[镜像检查](../logs/haptics-audit/image-verification-mtp.log)、
[策略用例 JSON](../logs/haptics-audit/policy-regression-mtp.json)、
[源码指纹](../imgs/built/twrp-recovery-haptics-mtp-sources.json)。

## 已确认的固件与源码问题

### 内核固件加载权限缺失

上一版实际打包的 recovery 策略没有 `system:firmware_load` 权限定义；kernel 域仍处于 enforcing。
既有日志也出现内核未知权限提示及 `scontext=u:r:kernel:s0` 的固件加载拒绝。
Linux 6.18 固件加载器在请求期间使用 init 的内核凭据，SELinux 分别检查直接读取的文件标签与回退路径的 kernel 标签。
因此仅让 recovery 进程 permissive 或仅复制固件文件，不能消除这条检查。
依据：[Linux 6.18 firmware loader](https://raw.githubusercontent.com/torvalds/linux/v6.18/drivers/base/firmware_loader/main.c)、
[Linux 6.18 SELinux hooks](https://raw.githubusercontent.com/torvalds/linux/v6.18/security/selinux/hooks.c)。

修改为：平台 access_vectors 定义该权限，设备 recovery-only 规则允许 kernel 对 self/rootfs/vendor_file 做 firmware_load，
并允许读取 vendor_file。当前镜像 file_contexts 对 `/vendor/firmware` 使用 vendor_file，ramdisk 初始文件可为 rootfs。
kernel 保持 enforcing；没有给 shell 或 app 数据增加固件加载授权。

`tests/haptics_policy_regression.py` 使用 AOSP 实际 libsepol 查询旧、新二进制策略，未向主机加载策略。
旧策略用例返回“权限不存在”；新策略的三种目标标签、vendor 文件读取通过；app_data_file 与 shell 负例仍被拒绝。
9 项全部通过，并核对被测策略确实来自新镜像。

这证明一个真实的兼容缺口已修正。历史拒绝日志来自触摸固件请求；尚无新 Cirrus 实机日志证明它是“无震动”的唯一原因。

### 原厂频率与 FF 参数

OS4 原厂 ODM 属性 `ro.odm.mm.vibrator.resonant_frequency=130`，DT `cirrus,f0-default=0x208000`（Q14）也为 130 Hz。
旧候选使用固定 5 ms / 200 Hz。新版以 `ro.twrp.haptics_frequency=130` 配置 dijun，
按 FF 整数毫秒周期取 8 ms / 125 Hz；保留其他设备的默认值，非法频率退回 200 Hz。

驱动只接受 FF_PERIODIC/FF_SINE 等能力，幅度上限为 255；候选保留幅度 64 和 UI 请求的持续时间。
驱动 probe 默认 gain 已为 100，故没有把“缺少 FF_GAIN”当作确定根因，也没有写入 Linux 通用 65535 增益值。
FF 必须分别上传效果和发送播放事件，重复反馈还需清理上一效果。
接口依据：[Linux force-feedback 文档](https://www.kernel.org/doc/html/latest/input/ff.html)。

`tests/devicefix_regression.py` 编译实际生产 FF 源码，以替身 ioctl 验证上传、播放、重复效果、常量/rumble 后备及非法频率。
同一 130 Hz 用例在保存的上一版源码上失败，在新源码上通过。快速电源键的两个既有回归用例也通过，原源码会失败。
这不是电机振幅、噪声或体感测试。

### 驱动、固件与跨版本区别

OS4 `xring_audio_hw_third.ko` 包含 Cirrus CS40L26 的 I2C 驱动及其他音频驱动；硬依赖包括 `fsa4480-i2c`。
原厂 dijun DT overlay 启用 `/soc/i2c@EC100000/cs40l26@43`，没有启用 fw-defer/ROM-only；
probe 的固件上传失败可能发生在 input 注册之前。因此“模块已加载”不足以代表存在可播放的 input 节点。

原厂 ueventd 优先查找 ODM，其 `cs40l26-a2h.bin`、`cs40l26-dbc.bin` 与 vendor 同名文件内容不同。
新版保留 vendor 的 9 个原文件，并将匹配 OS4 ODM 的 9 个 Cirrus 文件、触摸镜像和配置共 11 个文件放入独立 ramdisk `/lib/firmware`，内核自定义固件路径指向这里。
Android 默认 `/odm/firmware` 是符号链接，且 vendor/ODM 会被 TWRP 临时挂载和卸载；使用 RAM 目录保证这些动作不会遮住固件。
镜像校验逐字节核对这 11 份文件及两组不同参数，来源见 [ODM 清单](../dtsrc/O1_asic_dual/prebuilt/dijun/haptics/odm-firmware-inventory.json)。不改写 persist 校准值。
前一份 `haptics-policy.img` 保留为中间产物，它仅包含 vendor 版本固件。
OS2/OS3 同一驱动代码由 `xring_smartpa.ko` 提供，硬依赖为 `miev`，不能塞入 OS4 的模块代替。
各样本模块的完整导入/导出 CRC、原路径与哈希见 `firmware/samples/<sample>/analysis/facts.json`。

## 剩余范围

五个样本的精确选择、固件发布和模块加载顺序已接入统一候选，并完成主机模拟；见 [启动说明](PROFILE-SELECTION.md)。
故障路径需保留明确日志：模块未加载、probe 失败、没有 FF 能力、上传失败、播放失败分别记录。
实际电机、启动时序、供电状态和快速唤醒延迟持续标记 U；本轮不补做实机测试。

当前 `haptics-mtp.img` 同时包含已通过主机回归的 MTP 修正，详见 [MTP 记录](MTP-ADAPTATION.md)。此前 `haptics-policy.img`、`haptics-odm.img` 是保留的中间产物。

当前统一候选把上述固件保存为去重 blob，选中 profile 后才发布 RAM 路径。旧 `haptics-mtp.img` 保留为 OS4 中间产物；最新文件与校验和见 [模拟报告](../simulation-report.md)。
