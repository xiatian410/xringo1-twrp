# 功能入口与当前使用边界

本地最新候选`recovery-dijun-unified-mtp-directory.img`：电脑通过MTP上传目录时应用有效修改时间，目录在SendObjectInfo完成；元数据失败报告错误且保留目录以供重试。后续上传子文件会自然改变父目录日期，不保证整棵树最终日期还原。范围见[目录上传](docs/MTP-DIRECTORY-METADATA.md)。以下旧候选为历史记录。

ZIP安装链新增20项真正ARM64测试载荷的离线执行证据，见[执行范围](docs/ZIP-ARM64-EXECUTION.md)；使用入口和生产镜像未改变。真实OTA updater/update_engine、payload及实机写入仍未验收，不能把测试ELF成功当作任意刷机包兼容。

本地最新候选`recovery-dijun-unified-sideload-reboot.img`继承NV普通挂载限制和OTG误枚举修正；侧载协议重启请求接入GUI统一路由，Rescue暂不支持。当前为离线候选，不能据此称实体重启或USB已验收。

当前本地离线候选与验证状态以`simulation-report.json`及`ADAPTATION-GOALS.md`为准。NVData/NVCFG/protect_f/s不出现在普通挂载操作列表，GUI手动操作会被拒绝；Recovery内部用途和原厂fstab保持。源码批次同步公开GitHub，编译文件仅保留本地。

本地候选`recovery-dijun-unified-sideload-completion.img`：ORS sideload通过核心安装一次包，updater请求的cache清理在每个minadbd状态ACK前完成并报告失败；GUI的cache/Dalvik清理错误也会显示操作失败。失败可能发生在包已有部分写入后，不会回滚。实际USB/FUSE与ARM updater尚未验收。详见docs/SIDELOAD-LIFECYCLE.md。

当前本地候选`recovery-dijun-unified-sideload-lifecycle.img`包含侧载进程收尾修正。退出侧载时请求当前传输终止，后台统一回收；取消不会回滚已经安装的内容，也不保证立刻打断同步安装。完整USB/FUSE/安装器链路仍未验收，未连接设备。范围见docs/SIDELOAD-LIFECYCLE.md。

当前候选`recovery-dijun-unified-zip-queue.img`，SHA256 `4425846118c018b9a87b40c9bb549c6f9aa13af2c724973104c53ea013324a7f`。多包ZIP安装中，任意已尝试包请求的清缓存会保留到队列结束；后续包失败也不会抹掉此前请求。清理失败时整体显示失败，已完成包数保留，不能据失败状态判断先前安装已撤销。继承NV挂载限制及OTG发现修正，新候选尚未实机验证。以下早期候选记录仅表示当时状态。

当前候选`recovery-dijun-unified-nv-mount-policy.img`已去掉普通挂载页的NVData/NVCFG/protect选项；旧页面残留请求及手动backend调用也会拒绝挂载/卸载，内部服务仍使用原厂配置。不是通过删除fstab实现。SHA256 `0be46fb13091c4ebe663b5196ba22beadf5874990f7b811cb6d64c247195e5fe`，未实机验证。源码更新须同步[公开仓库](https://github.com/xiatian410/xringo1-twrp)，编译镜像留在本地。以下旧候选均为历史记录。

当前统一候选为`recovery-dijun-unified-zip-selection.img`，SHA256 `c6d2d09d50f3a1fda0f19164bc6204d4b911be6417efe18553af429bbfe3c3c6`。挂载页的假OTG修正已继承：发现按完整USB控制器路径匹配，避免把内置UFS分区列成0B的usbotg存储。NV/protect仍为原厂维护分区，与用户共享存储不同；设置沿用用户已确认正常的实现。新候选尚未实机验证。

安装ZIP入口保持“安装→刷机包→选择文件→确认”；通用updater优先，否则按设备公布的ABI顺序选择对应后缀，缺少匹配时拒绝安装。签名选项按原设置执行，修复没有放宽签名或摘要检查。36项主机ZIP链/22项updater回归已覆盖，具体边界见[安装验收](docs/INSTALL-CHAIN-VALIDATION.md)。ARM updater、A/B payload、sideload和完整GUI安装链仍未验收。

以下为历史候选记录，“当前”仅指当时。

当前候选`recovery-dijun-unified-updater-protocol.img`继承此前修正；安装ZIP时，updater缺失或非法的进度命令现在会记录错误并使安装失败，空日志不再触发空指针路径。失败不代表已执行的updater分区写入被撤销；处理错误后应先确认目标状态。此为离线候选，SHA256 `9875f7e53ab1eb3a7347cd538097c82ea4c81ac31c5569cc446120e0eb1d7912`，完整ZIP/OTA/sideload尚未验收。镜像双槽路由40项与updater协议22项的边界见[安装验收](docs/INSTALL-CHAIN-VALIDATION.md)。

当前候选`recovery-dijun-unified-sparse-flash.img`继承OTG误枚举、MTP上传日期、CE失败清理修正。安装页面选择镜像及目标后，sparse刷写现在检查展开容量并等待同步/关闭成功；失败不能视为分区原内容仍完整。未知/零容量目标拒绝写入，错误原因在日志中。此为离线候选，SHA256 `93aea3b2b22f387c79c42899c78152d8bf2b33f86f1ac2683796a97a340552c6`；完整安装/槽位/sideload还未验收，详见[范围](docs/SPARSE-IMAGE-FLASH.md)。

以下保留历史候选记录，各“当前”仅指当时。


2026-11-12 当前候选`recovery-dijun-unified-ce-cleanup.img`继承OTG与MTP修正，新增解密失败后的单用户CE清理。入口仍为“挂载→解密Data→选择用户”；如果凭据provider失败，Recovery尝试撤销该次可能安装的CE密钥，失败有日志，其他用户状态不变。错误后可重试，不能把失败状态或缓存移除当成真实内核已锁定证明；工作资料若绑定父用户凭据，仍无完整协议支持结论。SHA256 `9861830824b5a34bb5782bdbd6704bbc7c4b33374e20fe0fb87ffa23fae498cf`，未实机验证。



2026-11-12当前候选`recovery-dijun-unified-mtp-upload-time.img`包含0048 OTG列表修正和0049 MTP文件时间修正。电脑上传文件的合法修改时间现在包括Unix零秒；缺失/非法日期继续采用新文件创建时的时间。设置时间失败会使本次文件上传失败并保留原目标，可在处理存储错误后重新上传；不因此承诺目录日期、DateCreated、USB断线恢复或断电持久性。SHA256 `57798214bab0d211aa53e5036e46e45c528483aebb3cc16286da86406928484a`，未执行实机测试。



2026-11-12 OTG列表修正候选：`recovery-dijun-unified-otg-discovery.img`。内部共享存储仍使用data/media；真实USB分区使用`OTG <磁盘名> <分区号>`名称，例如`OTG sda 1`。旧版本可能将内置UFS分区错误列成`/storage/usbotg-sd*-N`且显示0B；本候选修正发现层，不应靠选择这些0B项目作为备份位置。NVData/NVCFG等是原厂维护分区声明，与用户共享存储不同。设置在backup-manifest基准上经用户确认正常；本候选尚未实机验证，详情见`docs/MOUNT-LIST-EXPLANATION.md`。


2026-11-12 备份摘要：当前digest-atomic候选的既有备份摘要生成入口自动使用临时文件/同步/原子替换，MD5与SHA-256格式保留。生成失败继续导致备份失败；完整摘要可见不等于整份备份可恢复。候选和离线边界见[摘要发布](docs/DIGEST-PUBLICATION.md)。震动、自动触摸和设置现场故障仍未解决。

本文件按当前 GUI2 中文入口整理，不是要求本轮连接手机或实机验证。

当前候选为mtp-reset（最终哈希以simulation-report.json为准），继承0038语言/主题失败重试等已有修改。0045使电脑发送MTP class Reset后旧会话释放，需要重新OpenSession；存储保持注册，详见[复位范围](docs/MTP-RESET-SESSION.md)。无需为此连接手机或回测历史镜像。设置无法修改和物理无震动仍未解决；已有设置采集工具适用于当前Recovery，无需清除或重置。
版本范围以 [兼容矩阵](compatibility-matrix.md) 为准；六个样本的 profile 启动已接入统一候选，完整功能仍未验收。
入口存在和能够编译，都不代表功能已经通过模拟。

| 功能 | 入口与操作顺序 | 前提、失败表现与验证状态 |
|---|---|---|
| 日志 | 设置中的“命令输出”查看输出；“导出日志”选择是否包含内核/logcat 后导出 | 目标存储必须可写；导出失败保留 `/tmp/recovery.log`；profile 状态另见 `/tmp/dijun-runtime.log`；选择与失败路径已模拟 |
| 显示/亮度 | 设置 → 屏幕 → 调整亮度、超时 | 原厂 backlight 节点；OS4 显示有历史证据；通用像素/旋转/PNG/DRM damage 主机检查通过，实际 KMS 仍未模拟 |
| 触摸/按键 | 常规点击滑动；电源短按开关屏；电源+音量下截图 | 按键队列已有 S2 回归；触摸事件历史正常，历史 dijun 量程/四旋转/十指与滑动片段已回放，实际延迟 U |
| 震动 | 设置 → 震动 → 按钮/键盘/操作震动 → 应用 | 运行时无后端则隐藏入口；设备晚注册可重新进入设置，页内断开后修改返回失败。设置保存不是电机回执；22 组调用链及固件/策略检查通过；新增 64 项完成反馈回放，操作超过 10 秒才触发，0 ms 关闭，失败/取消也可提示结束，物理电机 U，见[震动记录](docs/HAPTICS-ADAPTATION.md) |
| 时间 | 设置 → 时间与时区 → 时区、偏移、DST、12/24 小时制 | 默认北京/香港 UTC+8；保留自定义时区，旧默认迁移；无需用改 RTC 掩盖时区错误；原子保存、错误传递、旧默认迁移和 DST 已完成 21 组主机回归；新增[时间读取/转换失败处理](docs/CLOCK-FAILURE-ADAPTATION.md)，状态28组通过；RTC 硬件读数/漂移未验证 |
| 电量/温度 | 状态栏查看电量与充电图标；CPU 温度暂没有图形入口 | battery sysfs 与状态解析、温度数据接口完成 24 组模拟；缺值隐藏电量区，实际 0% 可显示；Health/RTC 硬件不在此结论内，见[状态读取](docs/STATUS-ADAPTATION.md) |
| 解密 | 启动解密页面或存储中的“解密 Data” → 用户凭据 → 查看解锁结果 | OS4 用户 0 有历史证据；服务缺失/错误凭据不可转成自动格式化；五版身份/启动顺序已模拟；未知组合或服务失败保持加密，新增逐用户选择、状态隔离和损坏资料处理；工作资料绑定密钥仍未验证，见 [多用户说明](docs/MULTIUSER-ADAPTATION.md) |
| 挂载 | 挂载 → 对应分区 → 挂载/卸载；选择存储切换访问目标 | system/vendor模式切换失败会返回错误并尝试恢复原状态，见[范围](docs/MOUNT-MODE-ADAPTATION.md)；EROFS 按只读处理；OS2/OS3 没有 mi_product，不能据其缺失判断整个 super 损坏 |
| MTP | 挂载/存储页面 → 启用 MTP；关闭后回到普通 USB 配置 | 内部媒体需解密并挂载；FunctionFS 的 ADB/MTP 两端须准备好；原生/兼容传输、42 项对象/会话及 [48 项移动/复制/重建](docs/MTP-TRANSFERS-ADAPTATION.md)回放通过；[62 项事件生命周期](docs/MTP-EVENTS-ADAPTATION.md)通过；[42 项 init/configfs 调度](docs/USB-CONFIGFS-ADAPTATION.md)通过；[66 项控制报文回放](docs/MTP-CONTROL-ADAPTATION.md)通过，[40+11 项调用层/消息回放](docs/MTP-CALLER-ADAPTATION.md)通过；取消/复位整合、解密后发布及完整联调待补，Windows 枚举 U |
| OTG | 挂载后在“选择存储”中选USB OTG，再浏览或作为备份目标 | 完整控制器模式发现12项、存储选择15项通过，修复内置UFS误枚举；实际USB/写入中拔除未验证，见[挂载说明](docs/MOUNT-LIST-EXPLANATION.md) |
| 安装 ZIP | 安装 → 刷机包 → 选择文件/队列 → 确认 → 查看结果与日志 | 主机传统ZIP核心36项及真实后台队列23项通过；清缓存失败使整体失败，保留已完成包数；GUI点击/ARM updater/AB payload未验收，见[安装范围](docs/INSTALL-CHAIN-VALIDATION.md) |
| 刷写镜像 | 安装 → 镜像 → 文件 → 目标分区/槽位 → 确认 | 主机后台/目标路由/真实libsparse接续40项通过；展开容量和同步错误会失败，已有写入不保证撤销；实际boot-control/物理分区仍未验证 |
| sideload | 高级 → ADB Sideload → 开始传输 → 查看结果/取消 | 是独立传输入口；协议中断与状态恢复待模拟 |
| fastbootd/重启 | 快捷操作 → 重启 → Fastbootd、Bootloader、Recovery、系统或关机 | Fastbootd 与 Bootloader 是不同入口；当前槽位、退出路由待完整模拟 |
| 备份 | 备份 → 目标存储 → 分区/压缩等选项 → 开始 | Data 文件备份不自动包含内部媒体；未解密用户的内容不承诺可恢复；归档层 30 项、原始镜像复制 65 项回放通过；取消和收尾 55 项回放通过，已有同名目录拒绝覆盖；压缩/加密/分卷管道 46 项通过，完整管理器与断电完整性仍待补；[编解码范围](docs/ARCHIVE-PIPELINE-ADAPTATION.md)；[备份会话](docs/BACKUP-SESSION-ADAPTATION.md)、[原始镜像边界](docs/RAW-IMAGE-ADAPTATION.md) |
| 恢复 | 恢复 → 存储中的备份 → 校验/选择分区 → 恢复 | 不能把一份未知版本备份默认视为当前布局兼容；归档元数据和原始镜像容量/失败路径已回放；空洞会展开，恢复已写块不能回滚，新增恢复预检/目标清单/digest 54 项回放，压缩/加密管道 46 项通过，完整管理器与加密卷仍待补；[编解码范围](docs/ARCHIVE-PIPELINE-ADAPTATION.md)；[会话预检](docs/RESTORE-SESSION-ADAPTATION.md)、[归档](docs/ARCHIVE-RESTORE-ADAPTATION.md)、[原始镜像](docs/RAW-IMAGE-ADAPTATION.md) |
| 清除/格式化 | 清除 → 高级清除选择分区，或独立“格式化 Data”确认流程 | 格式化 Data 会清除内部存储；解密失败不代表需要格式化；嵌套挂载点/转换/修复/调整大小的目标路由46断言通过，底层工具尚未在一次性镜像完整验收，见[操作路径范围](docs/PARTITION-OPERATION-PATHS.md) |
| 文件管理/终端 | 高级 → 文件管理或终端 | 权限、符号链接、路径边界和命令错误处理待模拟；不能把只读分区当可写 |
| 截图/录屏 | 快捷操作 → 截屏/开始录屏/停止录屏；设置调整录制帧率 | 输出存储需可写；18项主机视频颜色/时间轴/队列回归、6项stdio/codec错误与重录通过；FFmpeg原生解码18文件与72次短文件跳转通过；另3份12.5秒样片的1313帧编号及30次跨Cluster/关键帧跳转通过。停止时关闭文件失败返回保存错误，失败部分文件保留；未验证完整手机采样链/性能/断电持久性 |
| 语言/外观/设置 | 设置 → 语言、外观及相应子项 → 应用；settings-row候选支持整行切换复选框/开关 | 设置能否持久化依赖可访问存储；迁移、损坏设置、满盘、挂载失败已模拟；提交前失败保留旧文件，详见 [设置适配](docs/SETTINGS-ADAPTATION.md) |
| 网络与其他模式 | 暂不声明支持 | Wi-Fi 当前未启用；通用界面的 Download/EDL 等项目不等于 dijun 已适配 |

实现或验证状态有变化时，同时更新矩阵与本表，避免入口说明被误读为成功承诺。

界面反馈：普通有效点击只发一次按钮反馈；数字键盘拖出取消输入，使用独立键盘反馈通道；确认滑块在拖动中被禁用会取消并复位，重新启用后可以重新滑动。五个业务按钮、键盘、开关及滑块的 21 项实际 LVGL 夹具检查通过；这不是完整页面或物理电机验收，见[界面反馈说明](docs/UI-FEEDBACK-ADAPTATION.md)。

统一候选依赖当前槽位的 system/vendor/ODM 身份与模块资源。若系统分区已清除、版本不在六份档案中或组件混装，将跳过额外模块与解密激活；不应将此状态当作需要格式化 Data 的证据。详见 [启动与诊断](docs/PROFILE-SELECTION.md)。

操作完成反馈的时间阈值、次数、结果语义与验证范围见[专门记录](docs/OPERATION-FEEDBACK-ADAPTATION.md)。

GUI 震动在后台执行，后台空闲时约每 500 ms 刷新能力，进行中的设备 I/O 可推迟刷新；设备晚注册时可重新进入设置。积压反馈只保留最新一条，超过 250 ms 的待办丢弃；请求失败会显示现有硬件错误提示。操作退出等待已开始 I/O 清理，永久内核阻塞没有退出期限。详见[后台执行范围](docs/HAPTICS-WORKER-ADAPTATION.md)。物理震动仍未验证。
# 文件系统工具验证补充（2026-11-12）

当前候选中的ext4/F2FS/EROFS工具已在QEMU用户态对一次性普通文件执行15项检查，见[范围和运行说明](docs/FILESYSTEM-TOOLS-EXECUTION.md)。这不改变清除/格式化入口的确认要求，也不证明加密卷或内核挂载可用；无需在手机上执行文中的模拟命令。


2026-11-12当前候选`recovery-dijun-unified-fsck-result.img`新增[ext修复结果处理](docs/FSCK-RESULT-ADAPTATION.md)：e2fsck退出1表示已修正，接受为成功；需重启/未修正/执行失败仍失败。`python3 tests/filesystem_tools_image_test.py`默认绑定此镜像，17项实际工具检查通过；完整GUI/内核/加密未验证。

CPU温度数据接口：当前thermal-identity候选按原厂type=cpu-crg匹配，避免使用其他thermal_zone0；节点缺失/重名/读取失败不提供读数，晚出现可在下一次5秒刷新恢复。GUI2尚无温度显示控件，不能作为已可用的界面功能。见[状态范围](docs/STATUS-ADAPTATION.md)。

CPU温度：temperature-ui候选在状态栏显示cpu-crg读数（°C）；数据不可用/禁用时隐藏，恢复后再显示，空间不足时优先显示时间/录屏/电量。读取按type精确匹配，不依赖thermal_zone编号；主机界面检查通过，物理精度与手机显示未验证。见[状态范围](docs/STATUS-ADAPTATION.md)。

MTP上传的修改日期现在识别Z或±HHMM，不再依赖Recovery当前时区解释显式偏移；非法日期保持上传时刻。仅输入日期与主机文件链已验证，Windows枚举仍未知，见[MTP日期适配](docs/MTP-DATETIME-ADAPTATION.md)。当前候选还会忽略已结束或其他事务的Cancel，避免旧取消打断新传输；不需要额外开关。实际USB取消/重置联调仍未确认，详见[事务匹配范围](docs/MTP-TRANSACTION-CANCEL.md)。

震动请求候选增加后台请求与FF调用日志，现有“导出日志”可包含这些记录；无需打开隐藏开关。日志accepted=1仅表示请求接受，不保证电机输出，见[字段说明](docs/HAPTICS-REQUEST-TRACE.md)。


时间与时区保存：0042候选在应用失败时保留当前运行时区和待选项，可在存储恢复后再次应用。成功才刷新状态栏并重建页面。若底层目录fsync失败，完整设置文件可能已经发布，界面回退不表示磁盘回滚；不能用该修正补偿手机RTC漂移。当前产物以simulation-report.json为准。
