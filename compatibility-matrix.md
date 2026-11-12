# dijun 版本 × 功能矩阵

更新：2026-11-12，进行中。目标见 [ADAPTATION-GOALS.md](ADAPTATION-GOALS.md)。
当前候选为`recovery-dijun-unified-ce-cleanup.img`，SHA256 `9861830824b5a34bb5782bdbd6704bbc7c4b33374e20fe0fb87ffa23fae498cf`。包含0050 CE失败收尾、0049 MTP文件时间与0048 OTG发现修正；746来源/六配置封装通过，CE原始方法接续15（旧3失败）与用户控制18通过。同镜像profile/module与定向审计见`logs/ce-lifecycle-delivery.json`；历史完整审计不自动转移。

最新限定：OS4正式版raw0手动干预已有215事件/7组按下抬起，启动策略已构建但自动触摸/GUI/唤醒未确认；嵌套persist路径修正有31项真实方法主机检查，用户已确认backup-manifest（9a1b057d）设置正常，该观察不转移为新镜像实机验证。震动现场已有43次upload/start/mailbox完成，用户仍报告无物理输出；A1默认Q写0与原厂恢复差异见[原始代码核对](logs/haptics-A1-calibration-review.json)，不是已确认静音根因。下表U不能覆盖这些具体现场观察，也不表示新镜像功能已通过。

S0=固件证据，S1=静态检查，S2=实际生产代码主机模拟，S3=镜像检查，H=指定历史版本证据，U=硬件未验证。
“待”表示该样本的适配或功能用例尚未完成，不能当作通过。S1/S3 只覆盖单元格列出的范围。

| 功能 | OS2 初版 | OS2 末版 | OS3 初版 | OS3 末版 | OS4 当前样本 | OS4 正式版 4.0.4.0 | 剩余工作/证据 |
|---|---|---|---|---|---|---|---|
| 启动布局 | S1/S3，S2 门控 | S1/S3，S2 门控 | S1/S3，S2 门控 | S1/S3，S2 门控 | S1/S3，S2；H 基线 | S1/S2/S3 封装/门控 | 六包同一无内核 v4 镜像；完整内核/init 合并启动仍待模拟 |
| ADB 与日志 | 待 | 待 | 待 | 待 | S1/S3 init；H 基线 | S1/S3 init；端到端待 | 各 profile 服务失败、重连场景待模拟 |
| DRM 显示/亮度 | S0 驱动 | S0 驱动 | S0 驱动 | S0 驱动 | S2 像素/旋转/PNG；S3；H 基线显示 | S0 驱动；公共 S2；硬件 U | 通用像素/DRM damage 检查通过；实际 plane/topology 和显示硬件仍未模拟 |
| 触摸/按键/唤醒 | S1/S2 模块选择 | S1/S2 模块选择 | S1/S2 模块选择 | S1/S2 模块选择 | S2 坐标/按键；S3；H 事件 | S1/S2 模块选择；硬件 U | dijun 历史 100×量程、四旋转、滑动片段和十指通过；原厂额外模块按 profile 选择，实际唤醒 U |
| 震动 | S1/S2/S3 选择/FF | S1/S2/S3 选择/FF | S1/S2/S3 选择/FF | S1/S2/S3 选择/FF | S1/S2/S3；U 电机 | S1/S2/S3 来源/选择；U 电机 | 六包属性/模块/ODM 固件来源核对；实际设置 backend→router→FF 22 场景通过；无设备隐藏入口，另有 21 场景实际 LVGL 控件回放通过；完成反馈 64 项通过（实际备份/恢复/ZIP worker，分区工作替身）；完整页面仍待补，全部物理电机 U；另有[原厂 ARM64 函数 120 项模拟](docs/HAPTICS-DRIVER-EMULATION.md)，另有[注册/生命周期 90 项及 DTBO 48 次复核](docs/HAPTICS-LIFECYCLE-EMULATION.md)；GUI 后台 owner 已有[16 项并发回归](docs/HAPTICS-WORKER-ADAPTATION.md)；新增[播放/初始化边界 120+54 项](docs/HAPTICS-PLAYBACK-EMULATION.md)通过；完整 DSP/probe/IRQ 仍待 |
| 时间/时区 | S2/S3 设置/时区 | S2/S3 设置/时区 | S2/S3 设置/时区 | S2/S3 设置/时区 | S2/S3 设置/时区 | 公共 S2/S3；RTC U | 公共代码 21 组回归：UTC+8、迁移、重载、DST、I/O 故障；真实 RTC 冷启动/漂移仍 U |
| 电量/充电/温度 | S0 节点；S2 读取 | S0 节点；S2 读取 | S0 节点；S2 读取 | S0 节点；S2 读取 | S0 节点；S2 读取 | 公共 S2；传感器 U | 公共代码 24 组；实际电量/充电硬件 U，温度数据接口通过但没有 GUI 控件；[范围](docs/STATUS-ADAPTATION.md) |
| metadata/FBE 用户 0 | S1 ELF；S2 启动；S3 | S1 ELF；S2 启动；S3 | S1 ELF；S2 启动；S3 | S1 ELF；S2 启动；S3 | H bootfix；S1/S2/S3 | S1 ELF；S2 启动；S3；TEE U | 同一镜像按版本设置身份与启动顺序；S2 使用 Binder 替身，真实 TEE 和合成加密卷仍未验证 |
| 次用户/工作资料 | S2 控制/路由；S3 | S2 控制/路由；S3 | S2 控制/路由；S3 | S2 控制/路由；S3 | S2 控制/路由；S3 | 公共 S2；真实解锁 U | 用户控制18项、原始Recovery/vold CE生命周期15项（旧3失败）及既有backend/路由检查；失败CE清理/重试/锁定后再解锁是带ioctl/prepare/mount边界的共享S2，不是父绑定工作资料解密；父用户绑定密钥、同步调用中止、真实次用户 CE 解锁仍未验证；[范围](docs/MULTIUSER-ADAPTATION.md) |
| 分区挂载/文件系统 | S0 原厂 fstab | S0 原厂 fstab | S0 原厂 fstab | S0 原厂 fstab | S1/S3 fstab | S0/S1 fstab；端到端待 | OS2/OS3 无 mi_product；LP、文件系统夹具待补 |
| MTP | S2 传输/对象；S3 | S2 传输/对象；S3 | S2 传输/对象；S3 | S2 传输/对象；S3 | S1 init；S2 传输/对象；S3 | 公共 S2/S3；Windows U | 同一 MTP 二进制；[94项对象/会话回放](docs/MTP-DATETIME-ADAPTATION.md)通过（含16项文件时间与旧10失败），[48 项移动/复制/溢出重建](docs/MTP-TRANSFERS-ADAPTATION.md)通过；[62 项事件生命周期](docs/MTP-EVENTS-ADAPTATION.md)通过；[42 项 init/configfs 调度](docs/USB-CONFIGFS-ADAPTATION.md)通过；[66 项控制报文回放](docs/MTP-CONTROL-ADAPTATION.md)通过，[40+11 项调用层/消息回放](docs/MTP-CALLER-ADAPTATION.md)通过；取消/复位整合、解密后发布及完整联调待补；六版 Windows 枚举 U |
| USB OTG | S0；共享S2/S3 | S0；共享S2/S3 | S0；共享S2/S3 | S0；共享S2/S3 | S0；共享S2/S3 | S0；共享S2/S3；硬件U | 0048完整控制器路径匹配修正；发现12项（旧8失败）、实际路径列表6项与选择15项，均有明确夹具边界；完整manager/实际USB及写入中移除仍待，见[范围](docs/MOUNT-LIST-EXPLANATION.md)。 |
| ZIP/镜像/sideload | 待 | 待 | 待 | 待 | 已编译；功能模拟待 | 已编译；模拟待 | 尚未在合成分区完成写入、超限、中断用例 |
| 动态分区/A-B/fastbootd | S0 LP 组 | S0 LP 组 | S0 LP 组 | S0 LP 组 | S0/S3；历史槽位信息 | S0 LP；完整路由待 | 两槽位/快照元数据路由待模拟 |
| 备份/恢复 | S2 公共归档/原始复制 | S2 公共归档/原始复制 | S2 公共归档/原始复制 | S2 公共归档/原始复制 | S2 公共归档/原始复制；S3 | 公共 S2/S3；完整管理器待 | 归档 30 项、原始镜像 65 项、[恢复预检/分卷校验 54 项](docs/RESTORE-SESSION-ADAPTATION.md)；新增[备份取消/tar 生命周期 55 项](docs/BACKUP-SESSION-ADAPTATION.md)；[编解码管道 46 项](docs/ARCHIVE-PIPELINE-ADAPTATION.md)通过；完整管理器、digest 原子发布、断电完整性与空洞待补；[范围](docs/RAW-IMAGE-ADAPTATION.md) |
| 清除/格式化/修复 | 公共S2路由；工具待 | 公共S2路由；工具待 | 公共S2路由；工具待 | 公共S2路由；工具待 | 公共S2路由；工具待 | 公共S2路由；工具待 | 嵌套路径路由46断言通过；[同一镜像ARM64工具17项](docs/FILESYSTEM-TOOLS-EXECUTION.md)覆盖私有文件ext4/F2FS/EROFS格式化/检查、ext4扩容及部分内容读回。ext链接计数损坏修复与退出1处理已覆盖；GUI/内核挂载/加密及其他损坏仍待；[范围](docs/PARTITION-OPERATION-PATHS.md) |
| 文件管理/终端/设置 | S2/S3 设置；其他待 | S2/S3 设置；其他待 | S2/S3 设置；其他待 | S2/S3 设置；其他待 | S2/S3 设置；其他待 | 公共 S2/S3 设置；其他待 | [设置保存](docs/SETTINGS-ADAPTATION.md)与异常路径已覆盖；文件管理/终端、重启路由待覆盖 |
| 截图/录屏 | 待 | 待 | 待 | 待 | S2 截图按键组合 | 公共截图 S2；帧检查待 | 像素/帧/时间轴验证待补；组合键通过不等于图像通过 |
| 可选网络 | 未纳入 | 未纳入 | 未纳入 | 未纳入 | 未纳入 | 未纳入 | 当前 Wi-Fi 未启用；不列为已支持 |

历史基线是 `twrp-recovery-mitee-bootfix.img`，MD5 `5819f969bceb558cf734d5ae5608e211`。
当前镜像与 SHA-256 见 [模拟报告](simulation-report.md)。
原厂模块之间已找到的导入/导出 CRC 无冲突；尚未获得的内核导出表仍明确列作 unresolved。
这不等于跨包模块可混装。具体冲突见 [固件报告](docs/firmware-compatibility.md)。
安全服务/TA/私有库差异见 [解密组合报告](docs/crypto-compatibility.md)。

版本选择预检：六份真实身份、模块与资源字节通过 77 个场景，两槽位和混装拒绝均覆盖；[报告](docs/PROFILE-SELECTION.md)。预检属于只读组件 S2；另有同一实际镜像的 77 次阶段调用通过。两者均不替代完整内核启动或真实 TEE 验证。

用户后续raw0干预已恢复现场坐标；自动启动策略仍缺对应新镜像确认，不能用手动恢复或历史坐标回放替代。当前范围与限制见[排查记录](docs/OS4-TOUCH-FAILURE.md)。
