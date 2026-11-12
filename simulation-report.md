# 离线检查与模拟报告（进行中）

2026-11-12 NV挂载与公开源码要求：用户明确NV不应在普通界面提供挂载操作，维护补丁0054隐藏NVData/NVCFG/protect及对应别名，并在backend拒绝挂载/卸载；保留原厂fstab和内部核心访问，不将其当作用户存储。26项后台策略检查通过，旧实现同组17失败；真实LVGL列表六场景通过，正常夹具20行减为16行。同镜像profile9组/102阶段、module4组/24阶段调用通过。installclean及make -j$(nproc)30并发构建`recovery-dijun-unified-nv-mount-policy.img`，SHA256 `0be46fb13091c4ebe663b5196ba22beadf5874990f7b811cb6d64c247195e5fe`，751来源/六配置封装/维护补丁核对通过；交付审计logs/nv-mount-policy-delivery.json。用户确认OS4震动调用正常，继续其他功能而非围绕震动排查。用户授权通过GitHub CLI账户xiatian410创建公开源码仓库`https://github.com/xiatian410/xringo1-twrp`；以后每个连贯文件修改批次完成后必须执行scripts/sync_github.py --push并核对远端HEAD。编译产物、原厂blob、私钥、原始实机日志不上传。流程见docs/GITHUB-PUBLICATION.md及AGENTS.md。完整12组目标仍进行中。

2026-11-12 ZIP安装接续与ABI选择修正：原始TWinstall_zip→真实ZIP映射/提取、签名/摘要验证→fork/exec/wait的36项主机检查通过；同一最终测试运行旧源码有6项失败。维护补丁0053让外层分派与提取共用通用优先/advertised ABI顺序选择，空abilist回退abi，无匹配明确失败；原22项updater协议sanitizer回归通过。installclean及make -j$(nproc)（30并发）构建`recovery-dijun-unified-zip-selection.img`，SHA256 `c6d2d09d50f3a1fda0f19164bc6204d4b911be6417efe18553af429bbfe3c3c6`，750来源/六配置封装/补丁重建核对通过，同镜像profile9组/102阶段调用、module4组/24调用通过。定向交付见logs/zip-selection-delivery.json，范围见docs/INSTALL-CHAIN-VALIDATION.md。继承截图对应的0048 OTG完整控制器匹配修正，保留用户对设置正常的确认。ABI后缀fixture为主机程序，未执行ARM updater、AB payload、完整backend/GUI队列、sideload或设备测试；完整12组目标与历史全量审计漂移仍未完成。

以下按时间倒序保留历史检查点，旧“当前”和“未执行ZIP”仅指当时。

2026-11-12 安装链路推进：原始后台线程→PartitionManager目标查找/槽位覆盖→TWPartition→真实libsparse的40项主机检查通过，含双槽顺序、失败恢复原槽位与实际文件内容；路径解析/容量/挂载仍为夹具。真实fork/exec updater协议22项通过，旧实现同组14断言失败；维护补丁0052校验进度字段/有限数值/范围，非法输入排空并等待子进程后返回失败，空log及pipe/fork/fdopen错误安全收尾。未执行完整ZIP解压/签名/摘要、OTA payload、sideload或GUI点击。installclean及make -j$(nproc)30并发构建`recovery-dijun-unified-updater-protocol.img`，SHA256 `9875f7e53ab1eb3a7347cd538097c82ea4c81ac31c5569cc446120e0eb1d7912`，749来源和六配置封装核对通过。同镜像profile9组/102阶段调用、module4组/24阶段调用通过。详见docs/INSTALL-CHAIN-VALIDATION.md，定向交付为logs/updater-protocol-delivery.json；继承OTG/sparse/MTP/CE修正，设置正常确认保留，完整12组仍进行中。


2026-11-12 sparse刷写容量与完成修正：维护补丁0051在真实libsparse解析后检查展开长度及已打开块目标BLKGETSIZE64容量，拒绝零长度/越界/未知容量；写后fsync及close错误返回失败，容量查询/同步EINTR可重试，可选discard推迟至校验后。真实三个生产方法与AOSP libsparse在私有文件40项通过、旧实现同组27断言失败，raw传输65项回归通过。中途写失败可能已改变前部数据，不承诺回滚。installclean及make -j$(nproc)30并发构建`recovery-dijun-unified-sparse-flash.img`，SHA256 `93aea3b2b22f387c79c42899c78152d8bf2b33f86f1ac2683796a97a340552c6`，747来源/六配置封装核对通过。同镜像profile9组/102阶段调用、module4组/24阶段调用通过，定向交付审计为logs/sparse-flash-delivery.json。继承0048 OTG、0049 MTP日期与0050 CE失败清理；设置正常的用户确认保留。详见docs/SPARSE-IMAGE-FLASH.md；ZIP/sideload完整链路、槽位/GUI、真实性/CRC及物理断电仍未验收，完整12组继续进行中。


2026-11-12 多用户CE失败收尾修正：原始Decrypt_CE_storage先安装CE后prepare，prepare失败可留s_ce_policies；补丁0050在Recovery的provider失败出口请求驱逐本次用户，失败记录诊断，其他用户隔离。原始Recovery/vold八个方法接续15场景通过，旧实现同组3断言失败；用户枚举/控制18项回归通过。失败后错误secret仍失败、正确secret重新read/install；原始MarkDataLocked→lock/evict→再解锁及adoptable清理均执行，install/evict ioctl和prepare/mount仍是夹具，不等于物理已锁。vold基线e7e26ed2及FsCrypt/Decrypt/Android.bp纳入维护来源记录，未改其密钥协议。installclean及make -j$(nproc)30并发构建`recovery-dijun-unified-ce-cleanup.img`，SHA256 `9861830824b5a34bb5782bdbd6704bbc7c4b33374e20fe0fb87ffa23fae498cf`，746来源/六配置封装通过；同镜像回放和定向审计见logs/ce-lifecycle-delivery.json。父绑定工作资料协议、同步Binder安全中止和真实CE重挂载继续未完成；完整12组目标保持进行中，未操作设备。


2026-11-12 MTP文件上传时间修正：维护补丁0049将有效time_t（包括0和-1）与缺失/非法日期分开，接收失败后不尝试设置时间；futimens失败在rename发布前中止，保留原目标。真实server/database/私有文件链路94项通过，新增新建/覆盖各8项共16日期场景、旧实现同组10失败；移动复制48项通过。首次测试中部分bulk失败后重试暴露USB替身未排残余数据，保存logs/mtp-upload-time-first-attempt.json，不把该边界冒充完整端点恢复；该场景改为已完整读入payload后的接收失败。installclean及make -j$(nproc)30并发构建`recovery-dijun-unified-mtp-upload-time.img`，SHA256 `57798214bab0d211aa53e5036e46e45c528483aebb3cc16286da86406928484a`，742份来源/六配置封装通过；同镜像profile/module回放与定向审计见logs/mtp-upload-time-delivery.json。继承0048 OTG修正，列表证据仍明确绑定此前031497e5镜像；设置用户确认保留。目录日期、媒体完整元数据、临时文件崩溃残留、USB/断电和其余完整12组保持未完成，不以震动为当前主线。



2026-11-12 当前交付为`imgs/built/recovery-dijun-unified-otg-discovery.img`，SHA256 `031497e53bf500805a2ba6d74b4bc0a9315fbdbc5e6740ec028df33059d27561`。用户11张截图显示内部共享存储673GB和大量0B的usbotg-sd*项目。补丁0048修正控制器完整模式被首个通配符截断的发现缺陷，并让GUI识别真实OTG路径；三条入口统一匹配，保留原厂NV声明。发现12项通过/旧同组8失败，真实路径列表6项、保存链22项及选择15项通过；741来源与六配置封装通过。当前镜像profile9组/102阶段、module4组/24阶段以及完整定向来源绑定见`logs/otg-discovery-delivery.json`。私有文件树与设备/挂载夹具不能代替硬件；新镜像未实机验证。设置正常的用户反馈保持；不再以震动为当前主线。12组完整目标和历史总审计来源漂移继续未完成。此前“列表不累加”的测试只覆盖已分类输入，不能排除发现层误识别，详见`docs/MOUNT-LIST-EXPLANATION.md`。下方旧“当前”均为历史检查点。


2026-11-12 当前候选为`recovery-dijun-unified-backup-manifest.img`，SHA256 `9a1b057d001821b0d9a908c003c3810f5295e6fa500e1716f59ae50364126123`。补丁0047为新备份增加已同步的未完成标记和原子发布的payload清单；恢复列出与实际写分区前均拒绝未完成/不匹配清单。manifest helper17、真实RunBackup55和RunRestore56项私有主机用例通过。installclean后30并发构建通过，738来源和六配置封装核对通过；同镜像runtime9、module4、haptics policy12、USB policy53、init6检查通过。详见[备份范围](docs/BACKUP-SESSION-ADAPTATION.md)。这不是硬件、真实掉电文件系统或内容认证测试。物理震动仍未解决；设置/触摸现场和完整12组继续未完成。

2026-11-12 备份摘要发布修正：维护补丁0046改为同目录临时写入、文件同步/关闭、rename及目录同步，避免失败或中断截断正式摘要。真实hash/文件与BackupPartition调用54项通过，旧实现同组44项失败；恢复54项/备份会话55项回归通过。installclean后make -j$(nproc)30并发构建`recovery-dijun-unified-digest-atomic.img`，SHA256 `7f4c42935ff34c01ce85cec049c94b60ebd072400255cf299aedaca10dacafff`，736份生产来源/封装通过；同镜像profile9组/102调用、模块4组/24调用、策略12+53/init5通过。目录同步失败时完整新摘要可能已可见，分卷逐文件提交不等于整份备份事务。详见[摘要发布范围](docs/DIGEST-PUBLICATION.md)。当前224项绑定清单126匹配/78漂移/20无充分绑定，全量审计仍未通过；震动、自动触摸、设置现场与原12组任务仍未完成。

2026-11-12 交付证据刷新：当前仍为`recovery-dijun-unified-mtp-reset.img`，SHA256 `046ab9e356e5301661daa4ff7dd6a29504cee7706ee32da0353d988f7e6a4e27`，735份生产来源一致。模块夹具区分模块/触摸报告等待，将可选震动顺序约束改为触摸已尝试；同镜像模块4组/24调用、profile9组/102调用、策略12+53项和init5份通过，旧模块脚本同夹具仍14项失败。主要当前索引已更新为实际重跑报告；222项索引绑定清单124匹配/78漂移/20无充分绑定，总审计仍在历史review摘要处失败，这不是功能通过率。详见[当前交付与证据状态](docs/DELIVERY-EVIDENCE-STATUS.md)。生产代码与镜像未改，震动、设置现场、自动触摸及原12组目标仍未完成。下文早期“当前”及下一步属于各历史检查点。

2026-11-12 codec/PCM与FF原始接续：[两份OS4共12场景](logs/haptics-pcm-ff-join-review.json)执行codec probe、Mode1/Slot1 put、hw_params/sysclk与参数/时钟/RX widget，再接生产80ms SINE/IRQ。原始回调生成slots2/3、24bit word/32bit slot及单声道1.536MHz/双声道3.072MHz夹具缓存；不代表真实backend协商。四次参数寄存器更新全失败仍返回0；RX首/末写失败返回-5，后续FF仍发相同参数和命令。指针/分配/字符串/格式/寄存器/PM/ACK/调度/IRQ为显式边界，无真实ALSA/DSP/电机。详见[范围](docs/HAPTICS-PCM-FF-STATE.md)。生产046ab9e3/735来源保持，未改增益、校准或路由；共享软件路径仍不能选定物理原因，后续重点每设备校准/寄存器读回与输出通路，已有采集不重复索取。设置现场、自动触摸、震动及完整12组未完成。

2026-11-12 ASP与FF同上下文接续：[两份OS4共14场景](logs/haptics-asp-ff-join-review.json)从原厂A1 probe执行clk_en/asp_start/时钟切换，再提交生产80ms SINE和显式提供的开始/完成IRQ。未开ASP、已开及开启失败均请求相同五次FF写入与0x01800081命令；没有发现纯软件ASP前置门控。ASP标志在尝试前已置1且失败不回退，完成时重启ASP失败可留下state1/count0/completion已饱和；13jiffy STOP超时也可能最终回调返回0。codec/BCLK3.072MHz/PLL0/寄存器/PM/锁/ACK/队列/IRQ仍为显式边界，不证明实际时钟或电机。详见[范围](docs/HAPTICS-ASP-FF-STATE.md)。生产未变，046ab9e3镜像/735来源保持；下一步ASP参数/PCM寄存器与每设备校准读回，震动、设置现场、自动触摸及完整12组保持未完成。

2026-11-12 音频socket对端接续：[两份OS4共34场景](logs/haptics-audio-peer-review.json)执行原始socket handler→ResourceManager→ModulePrimary→updateA2HMode及串行原子release，使用前轮捕获的72字节启动消息。编号42通知震动流活动并协调已有流A2H；未知编号/短读/EOF/read=-1也请求相同0100回复，不能当成硬件就绪。合成许可流不活动时请求Haptics Source2，app拒绝时0，活动时不请求设置。socket/stream/usecase/app策略/setA2HParameter仍为显式边界，无真实ALSA/DSP/电机。详见[范围](docs/HAPTICS-AUDIO-SOCKET-PEER.md)。没有生产修改或新构建，046ab9e3镜像/735来源保持；下一步ASP与独立FF状态关联，物理震动、设置现场、自动触摸及完整12组未完成。

2026-11-12 服务尾部/后台PCM：[14场景](logs/haptics-service-tail-review.json)执行原始thread构造/XML消费者及首次worker到timedwait。后台会设置Source=PCM和ASP/TDM并请求PCM0/9；此前普通on不写mixer不能排除此初始化依赖。原始XML缺失/无long项保留35，正常31，合成42被消费后用于on；数组写-5或socket超时仍继续请求PCM。ALSA/socket/Thread/libxml为显式边界，仅原厂tinyalsa转换叶函数实执行，无真实DSP/电机，未确认后台初始化是无震动根因。当前046ab9e3/735生产来源定向核对，生产与镜像不变，完整12组继续进行中；详见[边界](docs/HAPTICS-SERVICE-THREAD-XML.md)。

2026-11-12 原厂PCM/AAC接续：[26场景结果](logs/haptics-pcm-init-review.json)执行原始selector→实际PCM/波形数据构造→AAC init本体，后接部分构造上下文的普通on。PCM仅准备mixer/端口/参数；AAC分配内存、计算滤波系数并请求线程，已执行初始化范围没有额外mixer/供电控制写。缺mixer/库/符号及AAC错误后普通on仍提交CUSTOM31，但long-id/恢复标志与kernel/loader/math/线程是显式边界，AWA本体和实际worker未执行，不能推导物理输出或完整启动。错误分支显示AAC init失败也不阻止constructor继续。来源与当前046ab9e3/735生产文件定向核对；无生产修改/构建，不替代历史总审计。详见[范围](docs/HAPTICS-PCM-INITIALIZATION.md)，震动、触摸/设置及完整12组仍未完成。

MTP Reset交付收尾：同一046ab9e3镜像的profile脚本回放9组/102次阶段调用通过；735来源与完整维护补丁80+1+3文件核对一致，0待同步。交付核对见logs/mtp-reset-delivery.json；这属于离线软件证据，震动/设置及完整12组仍未完成。

2026-11-12 当前候选更新：recovery-dijun-unified-mtp-reset.img，SHA256 046ab9e356e5301661daa4ff7dd6a29504cee7706ee32da0353d988f7e6a4e27。0045修复class Reset仅当Cancel导致旧session留存：独立信号在server线程释放会话/待上传/编辑，保留存储，Reset+断线仍退出。控制80/服务器78/移动复制48/事件62/传输通过，旧控制3/旧Reset服务器9失败。最终installclean后30并发构建、735来源/封装核对通过；同镜像profile回放另记。真实ep0/bulk取消及清理/旧事件未完成，不能宣称整机MTP正常；震动与设置未解决，完整12组继续进行中，详见docs/MTP-RESET-SESSION.md。

2026-11-12 原厂服务初始化补充：[30项结果](logs/haptics-service-init-review.json)覆盖OS4两份原始constructor发现前缀和单独FF后端constructor。恢复调用先于capabilities，独立Cirrus/audio属性、mixer失败保留fd及custom_wave读取缺失/字段错误均核对。校准恢复本体和sysfs全局状态为明确边界，没有完整外层构造/XML/线程/派发、ALSA/DSP或电机；无依据加入功放使能写入。当前da614695镜像与生产未改；设置及震动未解决，12组保持进行中。

2026-11-12 旧版原始配置/input/自检连接：[44项](logs/haptics-legacy-config-input-join.json)覆盖四份OS2/OS3原厂probe到完整配置、27个IRQ注册和input/FF回调；串行执行原始上传/播放/擦除自检，100ms/SINE8ms/45 effect与68次固件参数raw/25次wseq bulk核对。start mailbox-5时probe仍返回0、upload/erase状态0，不能以probe或状态成功证明播放。MFD失败在原始remove请求注销input后仍保留注册标志1；仅服务调用，未真正建立/注销evdev。身份/读寄存器/全FF序列/ACK/PM/IRQ/input与队列为明确夹具，无DSP、completion或电机。此前16/20报告的“remove未执行”已纠正并重跑：原厂remove实际执行，其内核teardown服务为夹具。原始初始化软件连接缺口已缩小，但实际寄存器/校准依赖、IRQ消息/内核并发/硬件输出仍未验证，当前镜像及完整12组进行中状态保持。

2026-11-12 OS2/OS3原始probe/固件/参数连接：[20项](logs/haptics-legacy-probe-upload-join.json)在同一上下文运行真实probe→PLL/ID→DSP分配→正常WMFW→五份参数→配置入口，独立文件清单匹配68次raw写入；MEM_RDY明确注入-5，无完整配置/input/播放。主参数缺失仍进入配置、仅63次写入；PM状态1/2可到解析，持续3在10次轮询后-22，第一固件写错误阻止参数加载。身份/状态/算法表/ACK/电源和内核服务为夹具，原厂remove本体已执行，其内核teardown服务为夹具，无真实DSP/I2C/电机。此前“probe只到固件请求”的记录为历史边界；下一缺口为旧版完整配置/input/start/IRQ/自检。生产及da614695镜像保持不变，物理震动和完整12组仍未完成。

2026-11-12 震动原厂CUSTOM回调接续：[12项](logs/haptics-custom-callback-review.json)连接原始服务/XML effect到同一probe后原始upload callback与worker/start，撤掉手工填worker的跳过路径。复制残余/地址拒绝/分配失败/编号越界分别核对-14/-12/-22、无播放与清理，正常31请求0x0100001f。copy与task/MMU、kernel/PM/regmap/队列/ACK为显式边界，无真实usercopy/DSP/计时线程/电机；未形成生产切换波形依据，当前da614695镜像不变。震动及完整12组继续进行中，范围见docs/HAPTICS-ADAPTATION.md。

2026-11-12 当前产物为[mtp-transaction候选](imgs/built/recovery-dijun-unified-mtp-transaction.img)，SHA256 `da614695843c1c8f7dd8e1eabc747a65d4e5d755680ba1a0c1dbaeec08ac79b8`。修复旧/空闲/不同事务Cancel打断新传输；73项控制请求通过、旧同组5失败，真实server68项生命周期、移动复制48项、事件62项及native/compat传输回归通过。installclean/30并发构建，734来源和封装核对，同镜像profile回放与审计见logs/mtp-transaction-delivery.json。[范围](docs/MTP-TRANSACTION-CANCEL.md)不含Reset、DeviceBusy或真实UDC/Windows，震动和设置现场仍未解决。当前交付以本段及JSON为准，下方历次候选为历史记录；全量审计仍有旧来源漂移，不能把定向PASS升级为完整12组完成。

2026-11-12 震动错误路径纠正：[32项原厂OS4执行](logs/haptics-mailbox-error-review.json)确认mailbox写/读重试耗尽返回-62、busy耗尽返回-110；原始stop worker的PM入口失败会退出，但mailbox失败仍可输出done。现场五条NACK后另有PM state 2完成及stop/erase/下一播放日志；无TID不能归为同一次事务成功，撤回此前“不影响后续播放/不是无震动根因”的推断。[现场结果](logs/haptics-playback-field-observation.json)仅保留顺序窗口与独立PM观察。寄存器/PM/恢复helper为显式夹具，无DSP/I2C/电机验证。生产镜像未改，32项结果不代替物理震动验收，完整12组保持进行中。

OS2/OS3 震动初始化接续新增 [16 项原始 probe 执行](logs/haptics-legacy-probe-prefix.json)：四份 Cirrus 模块各执行三种 pinctrl/PLL/chip-ID 错误分支，并新增一条运行原始 PLL helper、显式 synthetic ID/revision 与 regmap 服务后到达原始 `request_firmware("cs40l26.wmfw")` 的路径；在该入口注入固件缺失后按原厂 teardown 返回。DT 属性来自合并 overlay。PLL/chip-ID/regmap、regulator/GPIO/pinctrl 与内核服务为 fixtures；没有加载固件字节、DSP、FF input、IRQ/自检或电机。实机 chip ID/寄存器值未知；独立来源审计通过，不是震动恢复结论。

震动现场证据与待办已按当前材料重审：[已有日志](logs/haptics-playback-field-observation.json)的 43 个 SINE 周期全部出现上传返回成功、start worker 完成及配对的 `TRIGGER_CP`/`COMPLETE_MBOX`；6 次伴随 VBST brownout，36 次无 brownout 且无完成前 stop，另 1 次提前 stop。stop/erase 的 43 次结果均成功返回。该证据排除了“只注册 input”这一层级的问题，但没有用户空间请求关联、寄存器/校准读回、电气输出或马达位移，不能称为震动已修复。OS4 的 probe/config/IRQ/input 与自检接续均已有离线覆盖；OS2/OS3 仍须把原始 probe 与其既有固件/参数/input 函数证据接通。此前“OS2/OS3 full probe pending”准确保留为未完成项，不能被 ELF 符号存在替代。

跨版本静态边界：[六份模块的 probe relocation/symbol 报告](logs/haptics-probe-callgraph.json)确认 OS2/OS3 与 OS4 直接调用目标不同：旧版 probe 包含 regmap read/write 及 upload/play/erase 自测目标，OS4 包含 part-number resolver 且没有旧版自测目标。重定位清单不等同控制流执行；此为选择下一模拟路径的依据，不是硬件功能证据。

震动能力查询中断修正：补丁0043让已有FF描述符的只读能力查询遇EINTR/EAGAIN时保留描述符与缓存能力，等待下一轮查询；避免关闭触发input core清理效果，不做无限重试。ENODEV/EBADF仍关闭并重新探测。28项路由/6项后台FF通过，旧代码同组EINTR/EAGAIN两项失败；14项日志ABI通过，8种时长effect字节不变。installclean后make -j$(nproc)30并发构建recovery-dijun-unified-haptics-probe.img，SHA256 `e64e796370ad7983d27692ce22827ab03f72999e68881a1b4fe507247ec48f73`，732来源/封装核对通过；同镜像回放另记。现场没有能力查询EINTR证据，不能认定持续无震动根因或物理修复；设置现场及完整12组继续进行中。

时区保存失败回退：补丁0042在页面提交前保留五项旧值，部分写入/生成时区/flush失败时恢复选项和精确旧tw_time_zone，刷新旧环境，保留待选项供重试；检查时区/偏移索引边界。backend生成时区传回读写错误，回退不从GUI选项重建自定义时区。17项真实LVGL回调+实际adapter/libc检查通过，旧回调同组11项失败；保存链22/点击20/语言主题9/震动路由24/owner16回归通过。存储/属性/页面路由为夹具，目录fsync失败后的磁盘发布不构成回滚。installclean后make -j$(nproc)30并发构建recovery-dijun-unified-timezone-retry.img，SHA256 `f31bbe13f856d25c0080b26cac041366bb91c5f61b95f88f9f5136df83a47023`，731来源与封装核对通过，同镜像profile回归另记。不能以此解释所有设置失效，物理震动与完整12组仍未完成。

MTP上传原子发布：补丁0041以同目录唯一临时文件接收，接收/长度校验/fsync/close均成功才rename，失败只删除临时文件，保留旧目标。数据库在同一observer锁下创建并登记精确临时路径，inotify、ReadDir与overflow reconciliation均不发布传输中的临时文件。68项真实server/database/storage主机检查（含22项新原子发布场景）与48项move/copy回归通过；旧实现5项覆盖对照均失败。目录fsync在rename之后失败只警告，完整新文件已提交，不能声称可恢复旧inode；模拟进程中途退出保留旧目标但留下临时文件，跨重启清理未完成。installclean后make -j$(nproc)30并发构建recovery-dijun-unified-mtp-atomic-upload.img，SHA256 `7ca65801af3a62b4970cf1ad12d05a8af49dd8e870992b45e40ad6192a06a23a`，727来源与封装核对通过，同镜像profile回放结果另记。震动、现场设置及完整12组仍未完成。

震动生产请求诊断补齐：维护补丁0040在后台owner记录begin/end/expired、请求序号/时长/队龄/替换计数/耗时，在FF层记录实际type/waveform/period/magnitude和擦除/上传/播放/close的开始结束、实际返回值、独立保存的errno、单调时间与PID/TID。提交入口不执行日志I/O；周期能力probe正常不打日志。GUI与FF序号是不同空间，只能结合线程/时间定位，不能认定跨调用者严格关联。日志可能拖慢worker，不提供阻塞输出的实时保证；accepted仅系统调用边界，不等于电机。24项路由/4项后台FF/16项owner/14项日志ABI核对通过，8种时长effect字节与旧捕获一致。新增擦除失败和短写模拟；短写不再误报旧errno。installclean后make -j$(nproc)30并发新候选recovery-dijun-unified-haptics-request-trace.img，SHA256 `610f4acc2534cbd3fdd95f6733257efa52329435569df5230c4ea1a9c3326a8d`，726来源与封装/新二进制核对通过；同镜像profile另记。未改波形、幅度、增益、校准或触发实机操作，震动与完整12组仍未完成。


震动诊断因素分离：独立工具新增--sine-gain100与--custom-existing-gain，与原--play/--stock-long组成波形SINE/CUSTOM×是否写gain100的四种请求。两个SINE的effect字节完全相同；两个CUSTOM除运行时指针外与原厂HAL捕获一致，数组{0,31}也核对。47项主机syscall替身和18项目标ARM64/QEMU启动/拒绝/普通文件失败检查通过；不等于真实播放。显式gain100在close后保留，“不写增益”不会恢复默认状态，必须记录执行顺序，不能把跨次请求视为独立初态；工具不自动播放四种模式。CUSTOM继续仅供已审核OS4，cross入口限1..1000ms，无任意波形/增益。重新构建独立工具并打包tools/haptics-diagnostic-os4.zip，未连接手机或修改生产镜像。当前MTP日期候选8c624d0e不变，物理震动、设置现场和完整12组仍未完成。


MTP上传日期修正：维护补丁0039按MTP格式校验年月日/时分秒、单个小数位、Z和±HHMM，显式偏移转UTC不依赖Recovery时区；保留无偏移的本地时区/DST行为，拒绝归一化后的非法日期和不存在的本地时间，失败不改变调用者输出。实际MtpUtils+独立Python日期oracle80项通过，旧实现79项中48失败（旧版空指针另未执行）；生产server/database/文件上传46项及移动复制48项通过，含4项新日期落盘检查。主机libc/USB替身非手机RTC/Windows枚举。installclean后make -j$(nproc)30并发构建新候选recovery-dijun-unified-mtp-datetime.img，SHA256 `8c624d0e1a4b9bbff1b99ce83dbcce2c3cdfc3013c2270d65c04e075a8a81ee3`，725来源及封装/新二进制核对通过；同镜像profile另记。没有修正震动、修改校准或改变FF；原子上传覆盖/输出日期格式化/完整元数据等仍待完成，全部12组保持进行中。


设置保存失败后重试修正：维护补丁0038让语言/主题在flush失败时恢复旧内存值，保留待选项；避免主题值先变而未重建、再次点击被同值判断阻断。真实回调/LVGL事件9项通过，旧实现同组4项失败；存储/路由/console为显式夹具，不是实际persist或完整GUI。设置整行20项、真实文件保存21项、嵌套路径31断言回归通过。installclean后make -j$(nproc)30并发构建新候选recovery-dijun-unified-settings-retry.img，SHA256 `e8adb7259265b4fa05a1057ba9141e09af805c7ff2240cb07a45bb009bbe2214`，724来源及封装/新二进制核对通过。同镜像profile回放结果另记。目录fsync失败可能已发布完整新文件，内存回退并不构成磁盘回滚；这一边界保持明确。尚无本次设置现场日志，不能解释全部设置不可修改；物理震动未解决，触摸P0和全部12组继续进行中。


温度GUI交付更新：维护补丁0037通过现有status backend/controller接入tw_cpu_temp，合法整数-273..1000°C独立于电量解析；缺失/非法/禁用时隐藏，后续读数恢复。状态栏按实际文本重新布局，窄屏优先时间/录屏/电量，空间不足隐藏温度；装饰不可点击。11组真实LVGL/provider/controller检查通过，含14种解析值、定时刷新、0/负温、晚到/禁用恢复、电量隐藏、Wi-Fi/录屏、四宽度与明暗主题；28项状态回归通过。已检查1440宽实际渲染图，host字体/settings/tick仍为夹具，未证明Android显示或物理温度。installclean后make -j$(nproc)30并发构建[新候选](imgs/built/recovery-dijun-unified-temperature-ui.img)，SHA256 `f2dea7dbf8ad58a9363f0906effa9ade627e7903bc45ee71e1b1fc1159994d84`，723来源及封装/新二进制核对通过。震动未改且仍未解决，设置现场采集未到，完整12组保持进行中。


最新交付更新：`recovery-dijun-unified-thermal-identity.img`，SHA256 `338a4bf6c4e4563a30e6d26eecfbf6ac0793d5158974753a107eb38674f455db`。0036修正CPU温度固定thermal_zone0的身份假设：dijun设置ro.twrp.cpu_temp_type=cpu-crg，每5秒刷新按type精确匹配；缺失/重复/非法值返回无效，晚注册保持可重试。12项实际文件枚举/真实方法检查通过，旧实现同组9场景失败；28项状态/21项保存回归通过。installclean后30并发构建、719来源及封装/新二进制核对通过。同镜像profile回归另记。GUI尚无温度控件，震动未改/仍未解决，完整12组保持进行中。

最新交付：`recovery-dijun-unified-otg-selection.img`，SHA256 `aaa4b25c1bd58a0b61508288a479d824f38701c38d2ed606530b39c503181ef7`，718来源/封装及installclean后30并发构建通过。0035修正存储选择容量失败/设备消失/设置提交失败时仍提交或留下新挂载的问题，15项真实选择+UpdateSize方法检查通过，旧实现同组12场景失败；底层设备和I/O仍为替身，详见[范围](docs/STORAGE-SELECTION-ADAPTATION.md)。设置20项交互/21项保存/31项路径回归通过，不能替代用户设置操作前后日志。USB发现、写入中拔除、现场设置和物理震动未验证，全部12组保持进行中。

震动固件发布核实：当前settings-row镜像真实脚本/CAS在六版本双槽12次回放中，624个模块插入边界均核对9份Cirrus文件与对应ODM原件一致；原厂firmware目录在cache后从私有夹具移除，RAM字节仍保留。OS4 vendor/ODM同名a2h有8个参数字、dbc有2个参数字不同，原厂ueventd与镜像均ODM优先；保留原厂参数。见[结果](logs/haptics-firmware-publication.json)及[范围](docs/HAPTICS-ADAPTATION.md)。insmod/内核加载/DSP/电机未执行，不能解释用户当时的物理无输出；生产未改，震动和完整12组仍未完成。

震动保护回调核实：新增[44项原始IRQ函数执行](logs/haptics-protection-irq-review.json)，确认VBST欠压/解除通知仅日志，不是软件增益恢复。四类boost/amp故障另读0x2034执行对应位清零/置位/清零，读写失败返回IRQ_NONE；regmap/IRQ/供电为边界，不能证明实际保护解除或当前根因。保持原厂保护、波形与增益，生产镜像未改；详见[范围](docs/HAPTICS-ADAPTATION.md)。实际无震动和全部目标继续未完成。

录屏多段时间轴推进：三份160×96/12.5秒样片各跨3个Cluster及0/5/10秒关键帧，15/30/60 FPS共1313帧编号/PTS经独立FFmpeg原生解码核对，30次跨边界跳转与线性解码一致。没有Cues，最后帧之后的跳转输出为空；不代表小时级/索引性能/目标codec/全分辨率或GUI播放完成。见[结果](logs/video-timeline.json)与[范围](docs/VIDEO-FRAMES-VALIDATION.md)。生产镜像未改，震动和全部12组继续进行中。

震动Source通路核实：两包原始ELF还原10条DAPM route/8个widget，Source0/1/2为Off/PCM/A2H，原厂服务0→1选择PCM。新增20项原始PCM事件执行覆盖A1/B2、SVC FLAGS恢复、寄存器/mailbox失败；DAPM调度/硬件仍为显式夹具，不能据此声称FF需要Source切换。未向Recovery盲写音频路由，生产镜像未改。见[结果](logs/haptics-dapm-route-review.json)与[范围](docs/HAPTICS-ADAPTATION.md)。实际无震动仍未解决，完整12组保持进行中。

设置交互续修：公共checkbox/switch行此前只有右侧控件响应，文字/空白未绑定。新增0033整行命中并复用统一取消guard，保留原业务target/保存失败回退。真实LVGL输入20项通过，旧组件同组8项失败，覆盖拖出返回、滚动、禁用、失败重试。新候选[settings-row镜像](imgs/built/recovery-dijun-unified-settings-row.img)，SHA256 `3c0bed7c0e93b2b5b7a50aada62165d69562c6217955a35d85eb4e03ba7cbe67`，installclean/30并发构建及716来源/封装通过。不是所有设置现场根因的确认，未改震动驱动/幅度/校准；详见[范围](docs/SETTINGS-ADAPTATION.md)。全部12组目标仍在进行中。

独立视频工具检查新增[18份文件与72次跳转](logs/video-ffmpeg.json)：FFmpeg原生VP8解码器验证全部帧/中心像素、Matroska metadata/PTS及1.5s总时长。准确输入跳转保持原PTS，跳转所得帧与线性解码字节一致；超出最后编码帧时输出为空。短单cluster样片不能证明长文件seek性能、GUI实时播放或目标ARM64采样。工具未安装/未打包，生产与当前镜像未变，震动及全部适配目标保持进行中。

当前候选更新为[recording-close镜像](imgs/built/recovery-dijun-unified-recording-close.img)，SHA256 `2773dec6298035e66dcb0b24deb78636207a6bbf24fab6f9490a5ad3151d83c7`。修正fclose失败仍报告视频保存成功；6项stdio/codec故障/重录、18项实际帧/队列回归通过，installclean/30并发构建、714来源与封装核对。同镜像profile回归9组/102次阶段调用通过，完整目标/震动仍未完成。下文旧候选为历史记录。详见[范围](docs/VIDEO-FRAMES-VALIDATION.md)。

录屏队列推进：[18项检查](logs/video-frames.json)将原六组合扩为顺序/拥塞停止排空/拥塞恢复。七帧溢出被丢弃，已入队彩条不受输入改白影响，恢复后时间0/100/200/1000ms保留，停止总时长1500ms；真实VP8编码/WebM文件解析及解码、ASan/UBSan通过。目标codec、shadow/DRM链、I/O错误、独立播放器/seek和全分辨率性能仍未覆盖。没有生产改动/新镜像，震动与12组目标未完成。

SINE实际系数接续：[46项结果](logs/haptics-sine-coefficients-review.json)在原始parser/get_reg中解析生产请求，独立核对BUZZ2三地址；80ms/8ms/64请求转换为duration20/freq125/level64。原始低16位算法匹配接受0x1f202调用与0x4f202元数据，不能凭高位不同改模块；时长/频率/幅度及失败重试覆盖。DSP/真实寄存器/I2C/电机未执行，没有新镜像或震动修复结论，完整12组保留。

原厂服务路由推进：[20项执行](logs/haptics-service-route-review.json)覆盖原始列表消费者、mixer失败与缓存重试、普通on80/300ms。波形效果31使用SVC0/Source0→1；普通on在已恢复校准/空callback条件下直接提交CUSTOM31且不访问mixer。mixer set错误仍可回报成功、缓存跳过重试，故该成功也不是实际初始化证据。缺Source切换尚不能认定为普通长震动必要前提，ALSA/DAPM/DSP/电机均未执行。详见[范围](docs/HAPTICS-ADAPTATION.md)。没有生产修改或新镜像，震动与完整12组目标保持进行中。

当前候选更新为[recovery-dijun-unified-clock-failure.img](imgs/built/recovery-dijun-unified-clock-failure.img)，SHA256 `1c0813cf324d76be52e588e4dd3358c1c104946841e393aef84df2d951437adc`。新增时间读取/转换失败处理，28组状态检查、21组设置与17项目标文件系统工具检查通过；installclean/30并发构建及712来源/封装已核对，同镜像profile回归9组/102次阶段调用通过。旧镜像检查点仍为历史范围，震动及整体目标未完成。见[范围](docs/CLOCK-FAILURE-ADAPTATION.md)。

最新候选为[recovery-dijun-unified-fsck-result.img](imgs/built/recovery-dijun-unified-fsck-result.img)，SHA256 `e153160d5cb2c8f438a899847bff6714caee37ac32eeb136996ef1aa08395b11`。新增e2fsck已修正退出1的正确处理，146断言、17项目标文件系统工具检查及封装/711来源通过。同镜像profile回归9组通过；下文旧镜像记录是历史检查点，完整目标仍未完成。见[修正范围](docs/FSCK-RESULT-ADAPTATION.md)。

当前候选更新为[partition-paths镜像](imgs/built/recovery-dijun-unified-partition-paths.img)，SHA256 `fac3c815d6fab6febe23910c2f7bbf2c28d509a35003cb9db6df388b9237b4ed`，installclean/30并发构建、封装和710来源复核通过。新增[分区操作路由](docs/PARTITION-OPERATION-PATHS.md)46断言通过，底层文件系统工具未执行；触摸/设置修正继承但现场未确认，震动未解决。下列487b5及其他旧镜像检查点均为历史记录，其审计不转移到新候选。

震动现场证据更新：原先作为触摸日志的raw-off dmesg含43次真实SINE上传成功、start worker完成及配对TRIGGER_CP/COMPLETE_MBOX；时长80×32、106×9、256×2。6次VBST欠压并解除衰减、5条mailbox首次写失败，只有一次提前stop；36次无欠压/提前stop仍不能证明物理输出。此前“无请求后回执”的当前描述已过时；优先查实际增益/校准/供电状态与原厂初始化，保留用户空间调用者/GUI动作未关联限制。见[逐次现场证据](logs/haptics-playback-field-observation.json)、[范围](docs/HAPTICS-ADAPTATION.md)。当前487b5镜像不变，未改震动驱动/幅度/保护，整体12组保持进行中。


设置故障已发现并修正具体路径缺陷：GetRootPath把`/mnt/vendor/persist/TWRP`截成`/mnt`，导致真实分区管理器查不到fstab中的persist并拒绝保存。新补丁0028按最长挂载点/别名前缀匹配，挂载/卸载保持真实owner；旧实现31断言13失败，新实现31通过。此前设置测试替换了分区查找，未覆盖该缺口。详见[设置记录](docs/SETTINGS-ADAPTATION.md)。最新候选[触摸+设置镜像](imgs/built/recovery-dijun-unified-touch-settings.img)，SHA256 `487b5ce3d991e46241bcf7768350d8986b135f6e9b6d5b9aa4c3deb6e5457e32`，已installclean/30并发构建，包装检查与709份来源指纹记录通过；同镜像profile回归9组/102次阶段调用通过。保留原设置文件；用户当前保存是否恢复尚未确认，震动/完整12组继续进行中。


新ordinary-reports镜像同镜像profile回归9组通过；设置持久化21项主机回归通过。本次未运行旧的全量交付审计，历史镜像绑定证据不转移到新镜像。

2026-11-12 最新检查点：用户手动写 `enable_touch_raw=0` 后，event3 捕获215条真实input事件、7组完整按下/抬起及变化X/Y，见[现场干预证据](logs/touch-raw-off-observation.json)。已在维护树加入等待模块live与Xiaomi input注册后的普通报告请求，整个调用timeout 6秒；只标记requested，不将sysfs缓存当作触摸就绪。原厂raw缓存初始值就是1，此前“读到1说明启动后有人写入”的推断撤回；mode1004的延迟worker可开启raw，但尚未绑定到现场来源。新候选[ordinary-reports镜像](imgs/built/recovery-dijun-unified-ordinary-reports.img)已installclean后以make -j$(nproc)构建，SHA256 `0d6b65d3a2e526c95220fd3cffdf6b9021c977c1a028d3055b199091da005bd5`，包装与708份来源指纹已记录。冷启动、GUI与休眠唤醒尚未实机验证。震动及完整12组目标继续进行中。

新增用户故障：设置中的多项项目无法修改。源码共同保存路径会在Flush失败时回退开关/阻止语言与主题应用；尚无本次设置点击后的Recovery日志，保存失败只是待核实分支。未删除设置、未改persist内容；需区分点击无响应与修改后回退，并核对错误日志/挂载/容量。


续接完成[28项ARM64 linker检查](logs/profile-linker-arm64.json)：使用仍存在的原始Android输出c282f，18项安全服务依赖加载、6项缺libteecli拒绝、4项动态小程序对照。小程序实际重定位/构造/main成功，缺符号正常加载拒绝而`--list`仍通过，故不把依赖列表视为服务重定位验证。详见[边界](docs/PROFILE-LINKER-ARM64.md)，真实namespace、服务本体重定位、合成卷未覆盖。生产代码未改、未构建，交付目录镜像仍缺失。v1采集脚本5条私有文件路径检查通过，增加等级读回和采集退出码；没有新设备采集。触摸、震动与12组目标仍未完成。

第二批触摸现场证据：[动作关联观察](logs/touch-action-runtime-observation.json)确认静置4.01秒触摸/SPI增量0、划屏12.01秒两者均+1613，未保存input事件；启动TouchComm v1、匹配固件免刷、input注册完成。getevent退出码缺失，不宣称采集完整。震动同启动确认A1/43 RAM波形与probe自检软件路径，仍未证明物理输出。已准备临时开启并恢复原厂日志等级的脚本，未执行设备命令。当前交付镜像路径在本轮后续读取时已不存在，独立linker新测试因缺文件退出，尚未产生通过报告；先前镜像审计不能当作当前文件存在证明。新linker测试未纳入通过索引；完整任务继续进行中。

触摸日志定位工具：[两份原始 OS4 缓存 info 回调静态检查](logs/touch-cached-info-audit.json)确认只读属性和格式化/复制调用，采集脚本新增窗口外缓存快照；[10 项分时日志分析检查](logs/touch-window-analysis-test.json)验证计数/uptime/真实坐标行与错误拒绝。现有现场目录缺窗口数据，分析为 insufficient。没有新增现场根因证据、生产修改或镜像，触摸 P0、震动与12组目标未完成。详见[触摸记录](docs/OS4-TOUCH-FAILURE.md)。

ARM64诊断启动：[8项目标执行](logs/haptics-diagnostic-arm64-test.json)在QEMU用户态跑交付的静态Android ARM64文件，验证bionic启动/参数拒绝、缺节点ENOENT、普通文件ENOTTY和关闭。没有FF上传/播放或设备访问，不覆盖动态linker、Android内核/SELinux/DSP。工具说明已更新，生产镜像和12组未完成状态不变。

录屏帧续接：[6组真实VP8/WebM输出检查](logs/video-frames.json)覆盖五档FPS、奇数尺寸、行填充、12帧中心YUV/时间戳与1500ms总时长，ASan/UBSan通过。生产recorder/converter和仓库libwebm实际执行，使用主机libvpx；目标ARM64/DRM、完整采样、丢帧及I/O故障仍未验证。详见[范围](docs/VIDEO-FRAMES-VALIDATION.md)，该组未完成，没有生产修改或新镜像。

独立诊断工具：[20 项主机检查](logs/haptics-diagnostic-test.json)核对 syscall 顺序、错误、ABI和实际 Recovery 请求字节；[静态 ARM64 文件与说明](tools/haptics-diagnostic/README.md)已保存，不进入生产镜像。只读 inspect 与显式 play 分开，逐步日志可定位阻塞调用；没有执行 ARM64 目标或设备命令，不证明震动恢复。周期/幅度与原厂自检对比不支持盲目增幅，现场请求回执仍缺失。

校准系数续接：[36 项原始 driver 检查](logs/haptics-calibration-coefficients-emulation.json)覆盖系数地址、三项 store 的 A1/B2/PM/写入失败和原始 DT config。WMFW/参数没有三项地址初值不等于硬件为零；原厂 DT 默认 130 Hz 可写 F0_OTP_STORED，因此缺 persist 恢复尚不能认定为无震动原因。PM/regmap 和算法表为显式边界，不运行 DSP 或电机。详见[依据](docs/HAPTICS-ADAPTATION.md)。

原厂服务对比：[18 场景](logs/haptics-service-request-emulation.json)执行 OS4 原厂 Cirrus FF helper 和原始 upload/start worker：原厂 XML 的长震动编号31生成 CUSTOM `{0,31}`、gain=100、replay=0，stop helper 删除效果；生产 Recovery 为 SINE/8ms/64/指定时长。RAM count=5/32 是明确夹具，分别拒绝/接受该 CUSTOM 并在接受时发送 `0x100001f`。原厂计时线程、XML parser、user-copy、DSP 与电机未执行，不将这项差异当作当前根因。生产代码/镜像不变，详见[震动记录](docs/HAPTICS-ADAPTATION.md)。

增益假设补充：[12 项原始 OS4 检查](logs/haptics-gain-emulation.json)通过，确认 probe 的 current/saved gain=100、实际 WMFW/参数字节的 SOURCE_ATTENUATION=0；原始增益 worker 将 0/50/100 转为衰减 400/24/0，101/65535 不入队。这排除“缺少 FF_GAIN 必然默认静音”的推断，未确认现场增益、DSP 或电机状态。生产代码不变。复现 `python3 tests/haptics_gain_emulation.py`。

恢复产物：recovery-dijun-unified-module-state.img（历史路径 `imgs/built/recovery-dijun-unified-module-state.img`，当前工作区缺失）。2026-11-12 已从 Android 构建目录恢复原始镜像，SHA-256 `c282f535b1fdac6f5eafe25ca46116441195affe9d67f4511178a930634c4346`，重新核对封装、六份 profile 和当前编译二进制通过。707 份来源指纹为本次事后重建，已明确标记，并非恢复了构建时原始清单。未修改生产代码或重新编译；触摸和震动仍未解决。

SHA-256：`c282f535b1fdac6f5eafe25ca46116441195affe9d67f4511178a930634c4346`。
总大小 104,857,600 B；压缩 ramdisk 76,627,359 B；对齐后剩余封装/填充预算 28,225,536 B。
镜像检查（历史路径 `imgs/built/recovery-dijun-unified-module-state.json`，当前工作区缺失）重新通过；当前来源指纹（历史路径 `imgs/built/recovery-dijun-unified-module-state-sources.json`，当前工作区缺失）事后重建。[交付一致性审计](logs/haptics-gain-delivery-audit.log)已通过，包含增益检查和重跑后的 playback 120、early probe 54、PLL/chip 80 场景；当前源码、镜像、已索引报告及文档链接一致。审计明确保留来源清单的事后重建属性，不代表触摸、震动或整体目标完成。

| 检查 | 结果 | 证据与范围 |
|---|---|---|
| OS4 正式版差异 | 15 个所需分区验证，独立档案进入当前镜像 | [比较](logs/os4-stable-comparison.json)、[范围](docs/OS4-STABLE-ADAPTATION.md)；139 个模块字节变化，1 个模块导入 CRC 冲突、5 个导入集合变化；tee-supplicant 与一项 TA 变化 |
| 精确选择预检 | 77 场景通过 | [JSON](logs/profile-selection-test.json)；六包真实身份/模块/blob 字节，两槽位及混装/损坏/未知组合；含新旧 OS4 双向混装拒绝 |
| 实际镜像启动脚本 | 8 组、96 次阶段调用通过 | [JSON](logs/module-state-profile-runtime.json)；从同一 SHA 镜像取出脚本/清单/CAS，替换挂载、属性、insmod、Binder |
| 模块初始化状态 | 4 组、24 次同镜像阶段调用通过；旧脚本 14 项断言失败 | [JSON](logs/module-state-image-test.json)、[范围](docs/MODULE-STATE-ADAPTATION.md)；coming/live/going、消失、依赖拒绝，真实内核状态为夹具 |
| 核心门控分支 | 通过 | [日志](logs/profile-core-test.log)；执行真实 C++ 分支，无 legacy 回退、挂载所有权、自动/手动解密门控 |
| Binder 就绪期限 | 5 场景通过 | [日志](logs/wait-services-test.log)；真实 helper，替换 Binder/时钟，缺失/迟到/死亡/引用释放/期限 |
| 镜像来源与容量 | 通过 | [日志](logs/module-state-image-verification.log)；六个相同原厂头格式、无旧模块覆盖、78 blob、OS4 HAL/TA/DSO 字节保留 |
| 干净编译 | 通过 | [日志](logs/build-module-state-final.log)；先 installclean，再 `make -j$(nproc)`，30 jobs |
| 固定补丁重建 | 75 文件通过 | [日志](logs/touch-priority-patch-reconstruction.log)；71 recovery 文件、1 sepolicy 文件、3 个固定 tinyxml2 文件 |
| 实际 init 文件 | 6 份通过 | [JSON](logs/module-state-init-verification.json)；语法、禁止提前/lazy 启动 MiTEE、服务失效撤销 ready；此项只检查语法，调度另有回放 |
| 实际二进制策略 | 12 场景通过 | [JSON](logs/module-state-policy-regression.json)；固件权限正/负例及备份 setpgid/sigkill/sigchld，kernel 保持 enforcing |
| USB init/configfs 调度 | 42 项通过，旧配置 33 项失败 | [报告](logs/usb-init.json)、[范围](docs/USB-CONFIGFS-ADAPTATION.md)；实际 init 调度与 helper，configfs/服务完成为主机边界 |
| USB 专用域策略 | 53 项通过 | [报告](logs/module-state-helper-policy.json)；实际镜像策略，rootfs 入口、enforcing、所需权限和拒绝项 |
| 原厂 OS4 配置/probe 与 DTBO | 两包 62 项函数模拟、2 次设备树检查通过 | [配置](logs/touch-configuration-emulation.json)、[DTBO](logs/touch-devicetree-audit.json)；原始获取→parser→ISR、缺配置时 input 存在但无事件；直接 phandle 与 ODM 固件→profile blob，实际 SPI/板型未知 |
| 原厂 OS4 SPI/供电/复位 | 两包共 58 项通过 | [JSON](logs/touch-spi-emulation.json)；原始 DT 及子节点解析、pinctrl/GPIO 延迟错误、regulator 和平台注册失败；原始硬件回调→平台 probe→parser/ISR，控制器/panel 与真实平台调度为边界 |
| 原厂 OS4 SPI 传输与识别入口 | 两包共 86 项通过 | [JSON](logs/touch-transport-emulation.json)；原始读写/缓冲区/CFI/识别入口，spi_sync 为合成响应；v1/v2 成功检测是边界，另执行原始无效头拒绝路径 |
| 原厂 OS4 panel setup | 两包共 22 项通过 | [JSON](logs/touch-panel-emulation.json)；原始配置名选择/参数/报告切换；全零 lockdown 的重复读取耗尽预算作为预期机制记录，flash/panel 包装注册与内核调度为边界，根因未确定 |
| 原厂 OS4 Xiaomi 包装层 | 两包共 50 项通过 | [JSON](logs/touch-wrapper-emulation.json)；panel/input 独立注册及错误、原始 raw callback 的显式跨实例执行；内核注册、线程、输入核心为边界，sysfs 成功不等于控制器报告已切换 |
| 原厂 OS4 协议识别/ID/长度 | 两包共 62 项通过 | [JSON](logs/touch-identification-emulation.json)；原始 detect/ID parser/长度协商/操作表，合成头执行原始 CRC6；message/command 响应为边界，v2 零长度字段仍可能成功不代表触摸可用 |
| 原厂 OS4 报文→事件→ISR | 两包共 90 项通过 | [JSON](logs/touch-message-emulation.json)；v1 原始头/分段拼接/复制/parser/ISR，v2 command 响应仍为边界；report 分配错误可能返回 0、空报告可能重报旧坐标，未确定实机根因 |
| OS4 静态加载时序 | 两包及当前镜像检查通过 | [JSON](logs/touch-load-order-audit.json)；原始首阶段归档未含两个触摸模块，当前 RC 无直接加载，C++ cache→modules；未执行 bootloader 合并或 init |
| 原厂 OS4 v2 command/帧校验 | 两包共 78 项通过 | [JSON](logs/touch-v2-command-emulation.json)；command/read/write/CRC6/CRC16/序号/分段→parser/ISR，物理字节为夹具；配置 CRC 耗尽可能成功保存全零配置并无坐标，未证实实机根因 |
| 原厂震动 PLL 与芯片识别 | 六包共 80 项通过 | [JSON](logs/haptics-pll-emulation.json)；原始五次 PLL 更新重试及 OS4 ID/revision 判别、probe 失败收尾；寄存器为合成响应，firmware/DSP/IRQ 和电机输出未覆盖 |
| 原厂 OS4 触摸启动/中断/解析 | 两包共 88 项通过，用户失效仍未解决 | [报告](logs/touch-startup-emulation.json)、[范围](docs/OS4-TOUCH-FAILURE.md)；执行原始 ARM64，报告切换错误、后台注册、ISR 门控及原始 parser 合成按下/释放；SPI/控制器与实际配置未验证 |
| dijun 坐标回放 | 6 类通过 | [JSON](logs/dijun-touch-regression.json)；真实输入解析器，历史 100×量程、四旋转边界、滑动片段、十指与释放 |
| 通用 minui | 4 目标及语法检查通过 | [日志](logs/minui-host-regression.log)；像素/旋转/PNG、重连、Type-A/B、DRM damage |
| FF 与快速电源键 | 通过，旧实现失败 | [日志](logs/haptics-route-device-regression.log)；周期/能力/ioctl 与按键队列；无真实电机 |
| 震动调用链 | 22 场景通过，旧源码 15 场景未通过 | [报告](logs/haptics-route.json)、[修改前](logs/haptics-route-before.json)；实际 backend/router/FF，设备与 I/O 替身，没有执行 LVGL 渲染 |
| 实际 LVGL 控件反馈/取消 | 21 场景通过，旧源码 11 场景失败 | [报告](logs/haptics-ui.json)、[修改前](logs/haptics-ui-before.json)、[范围与截图](docs/UI-FEEDBACK-ADAPTATION.md)；真实控件/指针分发/绘制，业务和震动接收端替身 |
| 操作完成反馈 | 64 项通过，旧源码 25 项失败 | [报告](logs/operation-feedback.json)、[范围](docs/OPERATION-FEEDBACK-ADAPTATION.md)；实际生命周期、设置后端及备份/恢复/ZIP worker，时钟/分区/硬件边界替身 |
| GUI 震动后台 owner | 16 项并发及 4 项生产 FF 联调通过 | [报告](logs/haptics-worker.json)、[FF 联调](logs/haptics-worker-ff.json)、[范围](docs/HAPTICS-WORKER-ADAPTATION.md)；实际控制器/backend，探测与播放门闩、最新待办/过期/退出/错误；设备边界替身，永久内核阻塞无退出期限 |
| 原厂 ARM64 震动函数 | 六样本 120 项通过 | [报告](logs/haptics-driver-emulation.json)、[范围](docs/HAPTICS-DRIVER-EMULATION.md)；原始模块指令解析生产 FF 请求；内核/DSP 服务替身，硬件 U |
| 原厂震动注册与效果生命周期 | 六样本 90 项通过 | [报告](logs/haptics-lifecycle-emulation.json)、[范围](docs/HAPTICS-LIFECYCLE-EMULATION.md)；执行注册/上传/擦除原始回调和 worker；PM/调度/DSP/完成事件为替身；完整 probe/start/stop/IRQ 未执行 |
| 原厂早期初始化与播放 worker | 六样本 120+54 项通过 | [播放报告](logs/haptics-playback-emulation.json)、[probe 报告](logs/haptics-probe-emulation.json)、[范围](docs/HAPTICS-PLAYBACK-EMULATION.md)；原始 start/stop、早期固件/I2C 包装和 DT 属性驱动的 PLL 前 probe；硬件服务/清理为显式边界，完整 DSP/IRQ 待补 |
| 原始震动 DTBO | 六样本 48 次合并通过 | [报告](logs/haptics-devicetree-audit.json)；从校验的 vendor_boot 取基础 DTB，libfdt 应用八条 overlay；核对 dijun 绑定与参数，bootloader 选择与硬件 U |
| 六版震动来源 | 6 档案通过 | [JSON](logs/haptics-profile-audit.json)；130 Hz 属性、模块 ELF 与计划哈希/依赖顺序、每版 9 个 ODM RAM 固件 |
| MTP 对象/会话 | 42 项通过，旧源码 28 项失败 | [报告](logs/mtp-objects.json)、[范围](docs/MTP-OBJECTS-ADAPTATION.md)；实际 server/packet/database/storage，真实文件/inotify/线程，内存 USB 对端；上传/下载/枚举/删除失败/冲突重命名/断线清理 |
| MTP 移动/复制与重建 | 48 项通过，旧源码 36 项失败 | [报告](logs/mtp-transfers.json)、[范围](docs/MTP-TRANSFERS-ADAPTATION.md)；实际协议与 fd 文件操作，句柄/UID 保持、短传输/同步/删除失败、rescan/溢出/根目录重建；EXDEV 与溢出记录注入 |
| MTP 事件生命周期 | 62 项通过，旧源码 56 项失败 | [报告](logs/mtp-events.json)、[范围](docs/MTP-EVENTS-ADAPTATION.md)；实际 native/compat 工作线程、AIO/管道、积压/退出/重连；在途完成及取消错误注入 |
| MTP 控制报文/事件批次 | 66 项通过，旧源码 60 项失败 | [报告](logs/mtp-control.json)、[范围](docs/MTP-CONTROL-ADAPTATION.md)；实际生产函数，ep0/端点 ioctl 替身；取消交易匹配和会话复位尚待整合 |
| MTP 启停/消息接收 | 40+11 项通过，旧源码分别 24、4 项失败 | [调用层](logs/mtp-caller.json)、[接收端](logs/mtp-receiver.json)、[范围](docs/MTP-CALLER-ADAPTATION.md)；真实进程/线程/socket，USB 属性完成与存储对象边界替身 |
| MTP 传输 | 通过，旧实现失败 | [JSON](logs/mtp-transport-regression.json)；生产 native/compat 实现、管道及真实文件、ENOSPC、断开、未知长度尾包 |
| 提取器/解析器/系统资源读取 | 4/6/4 项通过 | [提取](logs/firmware-acquire-test.log)、[结构](logs/firmware-facts-test.log)、[EROFS 资源](logs/system-resources-test.log) |
| 设置持久化/时区 | 21 组通过，原代码首轮 19 组中 12 组未通过 | [报告](logs/status-settings-regression.json)；实际 InfoManager/DataManager、临时文件、I/O 故障、迁移/重载/DST；UBSan |
| 原始镜像复制 | 65 项通过，旧版 43 项失败 | [报告](logs/raw-image.json)、[范围](docs/RAW-IMAGE-ADAPTATION.md)；实际三个入口函数，临时文件模拟块设备，包含完整字节往返/取消/进程退出；无真实分区 |
| 备份取消与 tar 生命周期 | 55 项通过，旧版 35 项失败 | [报告](logs/backup-session.json)、[范围](docs/BACKUP-SESSION-ADAPTATION.md)；真实 fork/信号/管道/.info 写入及 GUI worker；归档编码与挂载替身 |
| 恢复会话与分卷校验 | 54 项通过，旧版 45 项失败 | [报告](logs/restore-session.json)、[范围](docs/RESTORE-SESSION-ADAPTATION.md)；实际 manager/digest/原始复制，BoringSSL，临时分区文件；tar 解压边界替身 |
| 归档编解码管道 | 46 项通过，旧源码 31 项失败 | [报告](logs/archive-pipeline.json)、[范围](docs/ARCHIVE-PIPELINE-ADAPTATION.md)；实际 tar/pigz/OAES/BoringSSL，文件与混合分卷字节往返、短读/信号/损坏流及并发缓冲区；完整管理器和硬件加密未执行 |
| 文件归档恢复 | 30 项通过，旧版 17 项失败 | [报告](logs/archive-restore.json)、[范围](docs/ARCHIVE-RESTORE-ADAPTATION.md)；实际 libtar、主机目录/属性、I/O 故障；合成 policy provider |
| 多用户控制/入口 | 核心 18 组、后台 12 类、路由 8 类通过 | [核心](logs/multiuser-core.json)、[线程](logs/multiuser-backend.json)、[路由](logs/ui-feedback-multiuser-routes.json)；XML/ABX 实际解析、状态隔离、固定 ID；provider/LVGL 边界替身 |
| 电量/充电/温度接口/时钟策略 | 24 组通过 | [结果](logs/status-readings.json)；真实读取函数与状态 backend，文件/时钟替身；首轮 23 组旧代码 13 组失败，并发缓存另有修复前失败记录；没有温度 GUI |
| 六版安全组件 | S1 通过 | [JSON](docs/crypto-compatibility.json)；强符号闭包、原厂 TA/私有库和真实系统身份；无 ARM64 HAL 执行 |

此前统一候选 `recovery-dijun-unified-candidate.img` 保留，设置候选 `recovery-dijun-unified-settings.img` 也保留；多用户候选 `recovery-dijun-unified-multiuser.img` 也保留。状态读数候选 `recovery-dijun-unified-status.img` 也保留。震动路由候选 `recovery-dijun-unified-haptics-route.img` 也保留。GUI 反馈候选 `recovery-dijun-unified-ui-feedback.img` 也保留。归档候选 `recovery-dijun-unified-archive.img` 也保留。原始镜像候选 `recovery-dijun-unified-raw-image.img` 也保留。操作完成反馈候选 `recovery-dijun-unified-operation-feedback.img` 也保留。恢复预检候选 `recovery-dijun-unified-restore-session.img` 也保留。备份会话候选 `recovery-dijun-unified-backup-session.img` 也保留。归档编解码候选 `recovery-dijun-unified-archive-pipeline.img` 也保留。MTP 对象候选 `recovery-dijun-unified-mtp-objects.img` 也保留。MTP 转移候选 `recovery-dijun-unified-mtp-transfers.img` 也保留。新候选补齐 MTP 事件队列、取消和退出；没有扩展真实设备解密或硬件声明。

首个统一构建被镜像检查拒绝：默认设备目录复制重新带入了旧模块。
已通过显式 `TARGET_RECOVERY_DEVICE_DIRS` 修正并干净重编译；[失败证据](logs/unified-rejected-overlay-verification.log)保留。
带 `rejected-overlay` 的镜像仅为失败记录，不是交付候选。

六套档案的相同镜像哈希只证明本表已列范围。测试没有在模拟器启动完整 Android 内核，
没有执行原厂 ARM64 HAL；不能把 mock 注册就绪说成真实 metadata/FBE 解密成功。
当前依赖对应槽位的 system/vendor/ODM/module 来源完整，未知版本或被清除的系统不猜测兼容组合。

仍待完成：完整 ramdisk/init/LP 启动模拟、合成加密卷、工作资料绑定密钥及同步调用中止、MTP 完整媒体属性、上传覆盖原子提交、解密后发布、USB 取消交易匹配/会话复位/兼容 ep0/bulk AIO 回收及完整调用者联调、
完整页面及其余业务完成路径、备份/恢复完整管理器流程、真实进度、整份备份中断完整性、digest 原子发布与稀疏空洞、分区写入/格式化/修复、OTG、RTC 冷启动读错/漂移、温度 GUI、视频帧等用例。
设置保存已修复：同目录临时文件完整写入后提交，上层传播实际结果，损坏输入整体拒绝。提交后目录 fsync 失败时返回失败，但完整新文件已可见；不能把这一情形说成旧文件仍在。详见 [设置适配与边界](docs/SETTINGS-ADAPTATION.md)。
电量不再显示 Health OTA 接口的假定值；温度数据使用有符号毫摄氏度，互斥锁保护缓存。硬件传感器读数和 RTC 校准不由这些主机用例证明，详见[状态读取边界](docs/STATUS-ADAPTATION.md)。
六包所需分区和选定系统配置资源已齐；[资源清单](docs/system-resource-inventory.json)注明未读取任意 APK/框架程序内容的边界。

物理震动、TEE/RPMB/UFS wrapped-key、Windows 枚举、真实唤醒延迟与功耗均保持 U。
本轮没有连接手机、刷写或要求实机测试。历史 H 仅属于 `mitee-bootfix.img`。

[机器报告](simulation-report.json) · [功能矩阵](compatibility-matrix.md) · [功能入口](FEATURE-USAGE.md) · [维护流程](MAINTENANCE.md)

恢复预检和备份取消现有独立回放；tar 进程归属、GUI 提前取消、目录所有权和 `.info` 发布顺序已修复。FlashImage/repacker 独立入口取消残留、完整管理器归档流程、digest 原子发布及强杀/断电后的整份备份完整性仍待处理。

短读修正后的四类并行分卷场景另重复五轮，共 20 次通过：[1](logs/archive-pipeline-repeat-1.json)、[2](logs/archive-pipeline-repeat-2.json)、[3](logs/archive-pipeline-repeat-3.json)、[4](logs/archive-pipeline-repeat-4.json)、[5](logs/archive-pipeline-repeat-5.json)。这是针对已发现偶发失败的复查，不扩大其他功能的覆盖范围。

MTP 当前排除初次发现的符号链接和特殊文件；后续外部路径替换仍存在竞态。覆盖已有文件的上传还未改为原子提交，失败可能影响原内容；事件线程与退出已有 [62 项生产代码回放](docs/MTP-EVENTS-ADAPTATION.md)，init/configfs 调度另有 [42 项回放](docs/USB-CONFIGFS-ADAPTATION.md)；实际 UDC 的取消期限仍未验证。

第一份事件候选 `recovery-dijun-unified-mtp-events.img` 在补充的 6 项临时完成错误/恢复接收场景中失败，保留为中间记录；事件阶段 r2 修正该路径，全部 62 项通过。见[负向回放](logs/mtp-events-completion-before.json)。

USB 切换新增 [42 项真实 init 调度/生产 helper 回放](docs/USB-CONFIGFS-ADAPTATION.md)，旧配置同组 33 项失败；当前镜像的 [53 项专用域策略检查](logs/module-state-helper-policy.json)通过，包含 rootfs 执行入口、所需属性和 configfs 权限、任意服务控制/应用数据/原始块写入拒绝。第一份 USB 候选因 init 重标记权限失败而保留为中间记录，USB 阶段 r2 使用平台 recovery 的显式 rootfs 域切换，后续候选保留此方式。

控制报文候选按相同六版 profile 重新构建，原有 62 项事件、42 项对象、48 项移动/复制及文件传输回归通过。新增 66 项仅证明报文与批次处理；完整取消/复位与兼容路径 ep0 调度仍属于未完成项；调用者有后续 40+11 项离线回放，完整挂载/解密后发布联调待补。

OS4 首个正式版已纳入本轮六档案候选。首份正式版构建因激活允许列表遗漏而被同镜像回放拒绝，修正后重新 installclean 构建，六包两槽位与全部模块依赖顺序共 77 次阶段调用通过；失败证据见[正式版增补记录](docs/OS4-STABLE-ADAPTATION.md)。

2026-11-12 OS4.0.4 现场证据补充：只读审计用户日志包（历史路径 `imgs/built/1/os4-touch-20261112-000013.zip`，当前工作区缺失）确认 `os4-stable` cache 已验证、module phase 完成、`xring_audio_hw_third` live、`cs40l26_input` 为 event4，FF 能力与 `root:input 0660` 可见，Recovery 选中该设备。firmware rootfs 写入和 `adaptive_haptics_prop` AVC 均为 `permissive=1`，不证明操作失败。现场没有 Cirrus probe/DSP 启动记录、用户请求的 FF 上传/播放结果或 IRQ 差值；累计 IRQ 不能归因于用户请求或电机输出。六份 OS2/OS3/OS4 档案中的九个 ODM Cirrus 固件文件哈希一致，驱动/初始化路径仍有版本差异待离线核查。审计报告为 [JSON](logs/os4-stable-haptics-runtime-observation.json)，SHA-256 `d91b04b1395c9a032250c0c9403501ac56ee2e87fdb3dbcd9398cbf306603397`，复现 `python3 scripts/audit_haptics_runtime_observation.py`。震动仍未解决；未改生产驱动或重建镜像。原始构建输出中的镜像随后已恢复并核验，来源清单为事后重建。

最新触摸反馈与候选：用户报告 OS4 正式版无法触摸，根因未定。当前触摸优先候选完成 8 组、96 次同镜像运行时阶段调用及 2 条输入注册→GUI 回放；仅证明所列离线路径。见[排查记录](docs/OS4-TOUCH-FAILURE.md)。

本次新增识别模拟不修改生产代码或镜像；历史 OS4.0.0.19 的固件请求/AVC 记录不能归属于本次正式版故障。最新[交付审计](logs/touch-identification-delivery-audit.log)核对包装层、PLL 和识别新增报告及当前 707 份构建来源；触摸 P0 和整体 12 组未完成工作继续保留。

报文续接新增 90 项原始函数模拟，[最新交付审计](logs/touch-message-delivery-audit.log)核对原厂模块、反汇编、测试/模拟器指纹及现有镜像。正常合成帧贯通读取→parser→ISR；两版均出现空报告复用旧长度导致旧坐标重报、v2 report 分配失败上层仍返回 0 的机制，尚无证据表明它们触发了当前触摸失效。v2 command 10 为显式边界，物理总线和真实控制器均未执行。生产代码与 `recovery-dijun-unified-module-state.img` 不变，不生成另一份仅凭模拟通过命名为“修复”的镜像。

后续 78 项 v2 场景取消上述整体 command 10 边界，执行原始帧生成/校验和重试；正常配置/应用信息获取也接入帧回路。CRC 耗尽可能以成功返回并分发全零报告、保存全零配置；两版相同，当前物理根因仍未知。[最新交付审计](logs/touch-v2-command-delivery-audit.log)核对全部来源和关键结果。没有修改生产源码或重新构建镜像，触摸 P0 与其余 12 组功能继续保留。

启动链另增两包 44 项，从原始探测和 ID 报告接到配置、模式恢复、后台与 ISR。配置/应用信息超时后，连接成功和输入注册均可与零配置、无事件同时出现；仅切回 application 模式不能补配置。后台请求固件失败或更新三次失败会跳过应用配置重取，成功回调后的原始获取路径可恢复合成坐标。更新回调、panel、IRQ 注册及内核服务仍是夹具；两版一致，未证明此次实机根因。[报告](logs/touch-v2-startup-emulation.json)及[交付审计](logs/touch-v2-startup-delivery-audit.log)保存边界与来源。当前 `recovery-dijun-unified-module-state.img` 不变，触摸 P0 及整体 12 组工作仍未完成。

随后两包 32 项把原厂 DT/panel 和 v2 报告切换接入启动链，其中六项执行原始 flash setup、boot-info、128 字节 boot-config 读取和 application 返回。报告开启写超时仍能连接成功、注册 input；后续能否出事件取决于显式合成报文，未模拟控制器启用状态。持续全零 lockdown 在预算内重读且未排后台，一次 flash 读超时可在下一轮恢复。配置超时进入 bootloader 后原始 panel 跳过普通报告切换，仍可注册 input 但无事件。两版一致，根因未定。[报告](logs/touch-v2-panel-startup-emulation.json)与[交付审计](logs/touch-v2-panel-startup-delivery-audit.log)绑定来源和分支，当前镜像未改；触摸、震动及整体目标继续进行中。

触摸固件续接新增两包 [26 项原厂解析/ID 比较/后台启动回放](logs/touch-firmware-emulation.json)，三个原始区域 CRC、完整配置 ID 与匹配免写分支实际执行。免写成功后原始配置重取能恢复合成事件；有效配置可在解析失败后保留，缺配置且 flash 访问失败时 input 仍可注册却无事件。不同 ID/强制更新在原始 identify 超时处结束，没有擦除/编程/复位；控制器响应与内核服务是夹具。两版一致，当前物理根因未定；[交付审计](logs/touch-firmware-delivery-audit.log)绑定来源和结果，现有 module-state 镜像不变，触摸 P0、震动及整体 12 组未完成工作继续保留。

震动另增两包正常/校准共 [64 项原厂 DSP 固件解析及系数初始化](logs/haptics-firmware-emulation.json)，正常 525/校准 428 条系数，34/35 次内存段写入逐段核对。空算法表可使 parser 返回 0 而后续 get_reg=-22；合成匹配表可恢复地址计算。regmap 和算法表是显式夹具，未启动 DSP、IRQ 或物理电机；[完整范围](docs/HAPTICS-FIRMWARE-EMULATION.md)及[交付审计](logs/haptics-firmware-delivery-audit.log)保存边界。生产树及现有镜像未变，触摸 P0、震动和整体目标未完成。

震动上传另增两包 [72 项原厂代码接续](logs/haptics-upload-emulation.json)，执行 PM/shutdown/pre-config、实际固件解析、算法表初始化及固件身份边界；最深路径到达原始配置入口并在 MEM_RDY 更新注入 -5。真实 `.bin` 文件虽然读取，但合成算法版本使其被原始 parser 拒绝，不能认定参数加载成功。预处理失败未释放固件是原厂路径观察；硬件根因仍未知。[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)与[交付审计](logs/haptics-upload-delivery-audit.log)保存证据，生产树和镜像未变。

后续两包 [16 项原厂 packed 算法表/参数接续](logs/haptics-coefficients-emulation.json)取代统一合成版本的局部限制：原始参数 parser 接受真实 WMDR，正常/校准分别新增 34/28 次参数写入，独立清单逐段核对。算法表虽来自固件，仍通过 regmap 夹具提供，未执行 DSP；主参数缺失或失败也可继续到 config，完整写序列单独检查。本批在 MEM_RDY 注入失败终止，生产/镜像未变；[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)和[交付审计](logs/haptics-coefficients-delivery-audit.log)保存证据。

震动 DSP 配置接续新增两包正常/校准共 [36 项原始代码模拟](logs/haptics-config-emulation.json)：执行 MEM_RDY、CALL_RAM_INIT、写序列解析/写入、HALO 检查及 IRQ mask，最深到 GPIO 读取注入失败。CALL_RAM_INIT 连续写失败尝试 20 次，返回 -62；其成功后原厂立即设 `fw_loaded=1`，之后序列读取/写入、HALO、IRQ 或 GPIO 失败仍保留 1，因此此标志不能作为配置完成或可震动的证据。序列为全 FF 立即结束的显式合成数据，PM/HALO/IRQ 状态及邮箱确认均为夹具，没有执行 DSP。生产树和当前镜像未改；触摸 P0、震动和全部 12 组未完成项保留。详见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)及[交付审计](logs/haptics-config-delivery-audit.log)。

六份 OS2/OS3/OS4 样本的[跨版本 Cirrus 固件字节比较](logs/haptics-firmware-cross-version-audit.json)记录七个 ODM 文件在所有样本间一致，并记录 42 对 ODM/vendor 哈希关系；独立核验与统一交付审计检查全部输入及测试脚本哈希。该结论只涉及已提取字节，不代表运行时发布、加载、DSP 执行或电机输出。OS2/OS3 成功 firmware request 后仍未在同一原始 probe 上接到成功解析、配置、input、start 和 IRQ；OS4 配置模拟仍以 synthetic sequence/register 状态终止。震动没有修复，生产代码和镜像未改。

触摸 P0 继续：新增两包 [32 项原始 flash 失败/后台接续](logs/touch-flash-failure-emulation.json)。原始块检查、擦除命令、首两段编程命令及复位实际执行，命令页范围/地址/固件字节逐项核对；传输响应与 flash 几何为夹具，全部场景以注入错误结束，没有真实写入或完整编程成功。更新失败仍清 pending 并通知完成；后台三次擦除失败后仍注册 input，缺配置时即使复位回 application 也没有坐标。已有配置可解析明确提供的合成报文，并不证明 bootloader 会真实发报告。两版一致，当前故障根因未定。详见[范围](docs/OS4-TOUCH-FAILURE.md)和[交付审计](logs/touch-flash-failure-delivery-audit.log)。生产树和当前镜像未改，触摸、震动及整体 12 组目标保持进行中。

触摸完整命令接续：两包新增 [26 项原厂完整编程/复位/后台配置模拟](logs/touch-flash-complete-emulation.json)，逐项核对全部 625 段编程请求与两条擦除命令，配置单独更新为 25 段。所有传输确认/boot-info/复位及配置响应均为显式夹具，未执行物理写入。原厂 update 可在 reset 响应仍为 bootloader 时返回 0，随后后台仍注册 input、配置为零且无事件；app 模式下配置获取超时/空配置也无坐标。成功重取配置可恢复合成 ISR，末段写失败后重试则核对 1250 段。测试预期曾错误假设 bootloader 会主动切回 app，已按原始分支纠正；不是生产修复。详见[范围](docs/OS4-TOUCH-FAILURE.md)与[交付审计](logs/touch-flash-complete-delivery-audit.log)。当前镜像未改，触摸 P0、震动及整体目标继续进行中。

震动 probe 接续新增两包 [16 项原始启动链模拟](logs/haptics-probe-upload-emulation.json)：清空设备上下文后由原始 DT 解析、供电/复位、PLL 与芯片识别接入实际固件/参数上传和配置，完整核对 68 次 raw write；最深到 GPIO、boost DCM/IPK 后的 `0x3804` 读取注入失败。所有错误均传播到 probe 并进入 remove 边界，未到 input 初始化；后期错误时 `fw_loaded=1` 仍存在，不能当作 probe 成功。原始合并 DT 属性有来源绑定，电源/寄存器/邮箱/序列与 remove 内部清理仍为夹具；完整 DSP、IRQ、电机和 OS2/OS3 此层接续待继续。见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)和[交付审计](logs/haptics-probe-upload-delivery-audit.log)。生产与当前镜像未改，触摸 P0 和完整 12 组目标继续保留。


触摸 IRQ/PM 续接：新增两包 [40 项原始 IRQ 开关/PM/ISR 模拟](logs/touch-irq-emulation.json)。pending 持续时关闭 IRQ 请求 150×20 ms 等待后仍继续关闭；提前清除分别只请求 1/3 次。开启标志为 1 时可跳过非零 depth；wake 设置失败后软件 wake 标志仍改变。原始 PM 回调仅改变标志/通知 completion，所测 PM 标志与 sensorhub=1 都不阻断合成 ISR 坐标。所有 depth、wake、等待与报文为显式夹具；不等于测得 3 秒硬件延迟或定位当前根因。只有命名的 depth 不变场景允许有限执行预算耗尽，其他超限失败。详见[范围](docs/OS4-TOUCH-FAILURE.md)与[交付审计](logs/touch-irq-delivery-audit.log)。当前生产/镜像未改，触摸 P0、震动和整体 12 组工作继续进行中。


显示恢复续接：两包新增 [48 项原始显示 suspend/resume 模拟](logs/touch-display-resume-emulation.json)，接续原始 sensing/sleep/dynamic、IRQ、应用信息/配置与 parser/ISR。配置超时/空配置、应用信息三次失败、bootloader、复位事件失败、normal sensing 四次耗尽后仍可能设置 active；再次 resume 直接返回 0、不补配置，合成 ISR 无坐标。配置超时消失后，新的 suspend→resume 周期可重新取配置并恢复合成坐标。报告切换失败可被 resume=0 掩盖，不能用注入的坐标证明控制器接受模式切换。pending 关闭在显示入口只请求 3×20 ms，区别于独立 IRQ 接口的 150 次。所有电源/复位/命令响应/IRQ/温度均为显式夹具，无真实显示通知调度或实测延迟。详见[范围](docs/OS4-TOUCH-FAILURE.md)和[交付审计](logs/touch-display-resume-delivery-audit.log)。生产/当前镜像未改，触摸 P0、震动与整体 12 组目标继续进行中。


显示通知包装接续：新增两包 [30 项原始 notifier→worker→Synaptics dispatch/display 恢复模拟](logs/touch-notifier-emulation.json)。包装 worker 在配置失败/供电失败/dispatch 禁用/回调缺失后仍清休眠标志，重复亮屏任务会被包装层跳过，前两类分别留下下层 active=1/0，不能只检查一层状态。配置失败配对仍可经新的休眠/亮屏周期恢复合成坐标。队列拒绝、非法/未注册 panel、空通知及无关事件均有断言。两个独立 ARM64 地址空间通过显式带类型 host callback 桥接，未模拟内核链接/并发；flush 仅接受已排空队列，不宣称快速通知不会丢失。详见[范围](docs/OS4-TOUCH-FAILURE.md)和[交付审计](logs/touch-notifier-delivery-audit.log)。两版一致，根因仍未确定，当前生产/镜像不变，触摸 P0、震动和整体 12 组任务保持进行中。


震动 boost 后配置：两包新增 [26 项原始 probe→上传→clip/DBC/noise/calibration/brownout 模拟](logs/haptics-postboost-emulation.json)。实际 DT 属性读取目的地址与阈值字段绑定，独立核对 `0x201c=0x3000`、合成高位保留后的 `0x6408=0xa549140c`、`0x6404=0x5a491909`；原始代码消费的 vbbr/vpbr 字段顺序保留，不根据名字交换生产参数。clip/欠压读写、四个高低半字写序列及第二 IRQ mask 读取失败都传播 -5 至 probe/remove，不执行 input，即使 fw_loaded=1。完整 68 次原厂固件/参数 raw write 核对通过；寄存器/PM/HALO/序列和服务仍为夹具，没有 DSP/IRQ/电机成功结论。详见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)、[交付审计](logs/haptics-postboost-delivery-audit.log)。生产/当前镜像未改，触摸 P0、震动和整体 12 组目标继续进行中，下一边界为 runtime PM/logger/ASP 配置。


震动 runtime PM/logger/ASP 接续：两包新增 [16 项原始 probe 故障模拟](logs/haptics-runtime-config-emulation.json)，核对 68 次原厂固件/参数 raw write，执行 PM setup/entry/error recovery/exit、logger 和 ASP。resume -5 的原始错误处理会 set-status(0) 并调用 PM exit；logger/ASP 读写/分配/写序列故障均传至 probe/remove，未到 input，fw_loaded=1 不能证明成功。COUNT/SOURCE 初始 0、PM 服务/定时器和序列等为显式夹具，没有 DSP/电机成功结论。详见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)与[交付审计](logs/haptics-runtime-config-delivery-audit.log)。生产/当前镜像未改，触摸 P0、震动和完整目标保留；后续为 B2 邮箱、波形计数及 probe/input 接续。


触摸 IC-mode 接续：两包新增 [22 项原始模式函数/通知恢复模拟](logs/touch-ic-mode-emulation.json)，移除整体 IC-mode 成功替身，核对模式 2 的 `0xc7 / 31 0a 00`。dispatch 返回显示 resume 的保存值，IC 命令超时/分配失败不向上传播；重复亮屏跳过回调。配置失败后该命令仍不补回报告配置，合成 ISR 无坐标。IC 函数遗留 x0 不作为成功返回，控制器响应/IRQ/调度仍是夹具。详见[范围](docs/OS4-TOUCH-FAILURE.md)、[审计](logs/touch-ic-mode-delivery-audit.log)。没有根因或硬件恢复结论，生产及当前镜像不变，触摸 P0、震动和全部 12 组继续进行中。


震动波形/IRQ/input 接续：两包新增 [26 项原始 probe 模拟](logs/haptics-wave-irq-emulation.json)，从 B2 mailbox/波形诊断推进到 27 次 IRQ 请求、input/FF 回调与 sysfs 初始化、MFD 故障。计数读失败两次各重试 20 次，诊断错误未阻断后续 IRQ；B2/播放配置/IRQ/input 失败则传回 probe。input init 成功置注册标志后 MFD 失败，probe 仍失败。内核 IRQ/input/FF、合成计数 5/0、PM/HALO/mailbox 与序列均为明确夹具，全部场景以注入错误结束，没有完整 probe/DSP/电机成功结论。见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)、[审计](logs/haptics-wave-irq-delivery-audit.log)。生产和镜像不变；后续接 probe 自带 upload/play/erase 自检，触摸 P0、震动与全部 12 组目标保留。


震动 probe 自检接续：两包新增 [16 项原始 probe→上传/启动/擦除 worker 模拟](logs/haptics-probe-selftest-emulation.json)。原始 ordered 队列标志 0x20012/max_active1 与顺序模型核对，非法逆序被拒绝；七条执行场景/包实际到 probe 返回。PM、启动写入、mailbox 和上传参数失败均可被最终 probe=0 掩盖，erase PM 失败还留下效果链表。寄存器/PM/IRQ/input/mailbox 仍为明确夹具，没有 DSP/完成中断或电机成功结论。详见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)、[审计](logs/haptics-probe-selftest-delivery-audit.log)。生产与镜像不变；继续 IRQ/完成链、旧版初始化和完整 GUI，触摸 P0、震动及全部 12 组目标保留。


非空通知队列与震动 IRQ 续接：新增两包 [16 项原始触摸 pending-work flush](logs/touch-pending-flush-emulation.json)和 [30 项原始 mailbox IRQ/状态/完成调用](logs/haptics-irq-completion-emulation.json)。触摸在原 notifier 的 flush 边界保存上下文，执行旧 worker 后继续排新任务；正常顺序不丢转换，配置失败后重复亮屏仍跳过下层、cfg=0，新的 off/on 才可恢复合成坐标。震动从实际注册 handler 接入可变合成环，核对 ACK 回绕、GPIO 触发/完成区别、锁门控及 complete 调用；读写失败仍可返回 IRQ_HANDLED。真实调度/物理 IRQ、内核 completion 等待和 DSP/电机仍未验证，不能据此认定当前实机根因或功能已修复。详见[触摸记录](docs/OS4-TOUCH-FAILURE.md)、[震动记录](docs/HAPTICS-FIRMWARE-EMULATION.md)及[交付审计](logs/pending-flush-irq-delivery-audit.log)。生产与 `recovery-dijun-unified-module-state.img` 未改，没有重编译；触摸 P0、震动和全部 12 组目标保持进行中。


触摸跨模块注册续接：新增两包共 [16 项原始 DT/panel/connect/后台→Xiaomi panel/input 注册](logs/touch-joined-registration-emulation.json)。参数直接来自原始 Synaptics setup，双 ARM64 空间显式桥接；callback 表和内核 input 服务仍为夹具。正常分支核对原始轴/slots 与合成 ISR；input 分配/注册失败则 wrapper 返回空，两版 Synaptics 均先写 input+0x2c0、后检查空指针，模拟捕获精确未映射写并终止，不继续 ISR。此为原厂错误路径证据，尚未绑定此次用户故障，不改写原厂模块。panel 队列失败不阻断后台独立 input 注册，配置超时则即使注册成功仍无合成坐标。详见[触摸记录](docs/OS4-TOUCH-FAILURE.md)、[交付审计](logs/touch-joined-registration-delivery-audit.log)。生产与当前 `recovery-dijun-unified-module-state.img` 不变，触摸 P0、震动和整体 12 组目标保持进行中。


震动主动擦除/完成等待续接：新增两包共 [30 项原始 probe→生产 FF 上传/播放→mailbox IRQ→erase 等待](logs/haptics-active-erase-emulation.json)。生产效果为 80 ms/8 ms/64，原始写入独立核对。正确 done 通过原始 handler 解除等待；停止消息通知不同 completion，读/ACK 错误或缺完成则请求 580 ms 后返回 -62、保留效果。超时后迟到 done 可再次 erase 释放；新 start 清除先前 complete_all，第二效果缺 done 仍超时。无启动 IRQ或启动命令失败时 erase=0 也不能证明播放发生。单等待者 completion/HZ/顺序调度是显式模型，上游 completion 源码仅作契约参照，物理 IRQ/DSP/电机未验证。详见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)、[交付审计](logs/haptics-active-erase-delivery-audit.log)。生产和当前 `recovery-dijun-unified-module-state.img` 未改，没有重编译；触摸 P0、震动及全部 12 组目标保持进行中。


震动 regmap IRQ 前置回调新增两包 [12 项原始执行](logs/haptics-pre-irq-emulation.json)：probe 取得原始 chip 指针，确认仅注册 pre、post=null、27 子 IRQ；pre 实际执行 PM resume→`0x10004` 状态读→PM suspend。状态读错误/PM 错误返回 -5；状态 bit0=0 会日志后返回 0。上游 v6.18 regmap 参照在调用 pre 时忽略其返回值，故显式安排子 handler 验证 pre 错误不必然阻断 mailbox done；kernel dispatcher/status-mask/nested IRQ 未执行，不能推断本机实际中断链。见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)和[交付审计](logs/haptics-pre-irq-delivery-audit.log)。生产树和镜像未改；震动仍未解决，触摸 P0、全部 12 组保持进行中。


补充 recovery 震动执行检查点：离线核对发现 OS4 ODM 暴露 AIDL vibrator/vibratorfeature 服务，而 recovery 的实际调用链走 `/dev/input/event*` Force Feedback，不调用 Android 服务。OS4 module plan 包含原始 `xring_audio_hw_third` 与全部 CS40L26 固件，runtime 在缓存后按计划插入并检查 initstate；这仅证明候选设计和 host fixture 路径，不能证明启动时 `/dev/input` 已出现能力匹配的 `cs40l26_input` 节点或设备节点可访问。下一步聚焦建立模块插入→I2C probe→input 注册→节点权限→FF ioctl 的静态/主机证据，并覆盖 OS2/OS3 模块差异；不把 HAL manifest 或脚本 loaded 状态当作震动已用。当前产物不变，触摸 P0、震动与 12 组目标继续进行中。

本轮 profile runtime 调整后重新执行了 `installclean` 和 `recoveryimage`。新镜像 SHA-256 为 `c282f535b1fdac6f5eafe25ca46116441195affe9d67f4511178a930634c4346`。六份计划验证触摸硬依赖闭包先于震动专属闭包；同镜像 9 组 runtime 测试通过，覆盖震动 input 缺失、立即注册和延迟注册。该状态仅代表 `/proc/bus/input/devices` 名称匹配，不代表 FF ioctl、I2C probe 或电机可用；OS4 正式版触摸仍是未解决 P0。
# 原厂震动校准恢复补充（2026-11-12）

分区操作补充：[46断言路由/错误传播](logs/partition-operation-path.json)通过，旧实现同组20断言失败。新增0029修正嵌套挂载点清除/转换/修复/调整大小，统一/system别名并传播子分区/cache降级结果。底层分区操作为替身，没有格式化/fsck/删除或块设备I/O。[范围](docs/PARTITION-OPERATION-PATHS.md)。设置挂载31、设置21、备份55、恢复54及profile核心通过；installclean/30并发构建新partition-paths候选，SHA256 `fac3c815d6fab6febe23910c2f7bbf2c28d509a35003cb9db6df388b9237b4ed`，710来源与包装通过；同镜像runtime9组/102阶段通过。震动仍未解决，完整12组保持未完成。

现场A1分支新增[16项原始DT字段/配置/Q恢复检查](logs/haptics-A1-calibration-review.json)：原厂DT缺q-default时A1请求写Q_STORED=0，B2跳过；F0默认均130Hz。原始probe在fw_upload边界失败后，字段显式转接至另一个原始固件parser上下文，不能声称完整A1 probe或实际DSP初值。详见[解释与未知边界](docs/HAPTICS-ADAPTATION.md)。现场实际stored/persist和Q对输出的影响未知，未改生产校准/增益或生成新镜像；整体目标继续进行中。

[16 项原始服务执行](logs/haptics-calibration-restore-emulation.json)核对 OS4 设备校准读取、input0..9 路径探测和写入失败行为。文件系统、属性、libc 转换/格式化为夹具；没有设备校准数据、driver store 执行或硬件效果证据。当前 Recovery 缺少同等恢复，仍需核对默认值/播放依赖；不能认定为无震动根因。详见[适配依据](docs/HAPTICS-ADAPTATION.md)。触摸 P0、震动和整体目标保持未完成。

2026-11-12 震动状态采集：[11项私有执行与两份OS4 ELF属性表核对](logs/haptics-state-collector-test.json)验证定向工具的只读输入保持、阻塞超时、缺节点/未挂载/读取失败、profile门控和输出冲突拒绝；不是新的手机或DSP成功结果。[用法](docs/HAPTICS-STATE-COLLECTION.md)明确部分读取唤醒DSP，先采baseline；overprotection_gain非通用FF增益。只采设备自身persist三文件，不播放、不写sysfs、不触发校准。工具尚未在Windows/Android执行，未改生产镜像；物理无震动及12组整体目标仍未完成。

# 2026-11-12 震动算法默认值复核补充

[报告](logs/haptics-algorithm-defaults-review.json)执行两份OS4原始SVC/DVL ALSA查询、固件版本/系数地址解析，共12项；寄存器值显式来自原厂文件解码，PM和ALSA对象为夹具。SVC FLAGS=0，DVL EN由WMFW的0经参数覆盖为1；原厂音频XML另配置SVC=1。未执行DSP或音频core，文件默认值不是设备读回，不证明开启SVC即可修复无震动。生产镜像维持fac3c815…；触摸/设置/震动及整体目标未完成。详见[说明](docs/HAPTICS-ADAPTATION.md)。


2026-11-12新增[15项同镜像ARM64文件系统工具执行](docs/FILESYSTEM-TOOLS-EXECUTION.md)：ext4格式化/填充/检查/扩容、F2FS casefold创建/填充/检查、EROFS压缩/提取与三种无效输入拒绝通过。所有写入限私有普通文件，未运行GUI、内核挂载或加密卷，不能作为完整清除/修复验收。生产镜像未变。

2026-11-12独立震动诊断工具增加原厂OS4 CUSTOM31/gain100长震动入口，保持SINE对照；31项主机替身检查与12项目标ARM64启动/失败检查通过。未执行设备播放，未改生产镜像；增益保留/用户态erase/固件范围限制见[说明](tools/haptics-diagnostic/README.md)。

settings-row构建后验证：同镜像profile回归9组/102次阶段调用通过，21项既有控件反馈检查通过；来源重建73+1+3文件一致、0待更新。公共行20项输入检查及保存21/路径31回归作为不同边界证据保留。未确认实际触摸冷启动、设置保存或物理震动，完整目标仍进行中。

震动现场 A1 接续：两份 OS4 共 16 项原始 probe→固件/配置→自检→生产 FF/IRQ/erase 检查通过。A1 原始 ROM 与 B2 不同，加载后 PM 状态需显式转换；过时状态、errata 序列/Q/固件写错误均阻止进入 input。A1 在同一上下文写默认 Q=0，仍不能推导静音；生产80ms/8ms/64请求在显式完成消息下擦除成功，缺 done 则580ms请求后-62。内核/PM/寄存器/邮箱/全FF序列/DSP仍有明确模拟边界，没有电机恢复结论。见[结果](logs/haptics-A1-joined-review.json)、[范围](docs/HAPTICS-ADAPTATION.md)。生产 settings-row 镜像未改，震动与完整12组继续进行中。

挂载模式确定修正：补丁0034把system/vendor切换改为操作锁内的检查/卸载/修改/重新挂载/失败恢复流程；检查两个目标的挂载返回值，全部成功才提交全局模式，保留回滚失败日志和实际未恢复状态。15项生产函数主机检查通过，旧实现同组8项失败。installclean后30并发新候选recovery-dijun-unified-mount-mode.img，SHA256 `848096d4b42b41926e2741ba4a34ef1ec4922aaa66036281724e7a2d65b652f1`，717来源及封装/新二进制核对通过。详见[范围](docs/MOUNT-MODE-ADAPTATION.md)。不是震动或一般设置故障修复结论；全部12组保持进行中。

mount-mode构建后验证：同镜像9组/102次profile阶段调用通过，717来源及新二进制核对完成；GUI/FF库字节与settings-row一致，生产挂载事务15项通过，旧实现同组8失败。未验证实际挂载/界面/震动，目标仍进行中。

震动FF core边界补齐：16项上游6.18原函数→原厂A1停止/擦除接续确认EVIOCRMFF先stop0，只有stop确认不能代替播放done，缺done可-62；flush忽略该错误仍返回0。随后现场43次stop/erase独立配对全部erase_ret0（最大10.491ms），因此该模拟风险不能解释已有无震动现场。上游不是本机vendor源码，PM/寄存器/队列/DSP仍有明确边界；不改生产，当前mount-mode候选保持不变。见[结果](logs/haptics-ff-core-review.json)、[现场](logs/haptics-erase-field-observation.json)、[范围](docs/HAPTICS-ADAPTATION.md)。震动/完整12组继续进行中。

震动六版本供电引用核实：原始DTB+overlay5重新合并并核对，VA均mldo8→常开mbuck10，reset为低有效GPIO_105，IRQ为GPIO_046/低电平。六个原厂模块supplies均VP/VA，但DT只声明VA，与现场VP dummy警告相符；不等于物理缺电或应添加VP。两份OS4提取init相关命令除通用LED trigger外没有Cirrus输出write，二进制服务/实际供电未覆盖。见[拓扑](logs/haptics-power-topology.json)及[范围](docs/HAPTICS-ADAPTATION.md)。不改生产/不重编译，震动与完整12组继续未完成。

同镜像验证收尾：9组/102次profile阶段调用通过，718份构建来源仍一致，设置交互20/保存21/路径31与挂载模式15回归通过；当前交付审计见 `logs/otg-selection-delivery.json`。硬件与完整12组验收仍未完成。

震动校准恢复接续：新增[14项原厂服务→同一probe后A1/B2 sysfs store检查](logs/haptics-restore-joined-review.json)。A1接受合成z/f0/q，真实系数地址依次0x280212c/0x2802128/0x2802150；B2拒绝Q。越界F0、PM失败或Q写失败传回stdio错误，原服务仍继续，不能以恢复函数结束认定就绪。有效合成值恢复后生产SINE依然提交20/125/64并在显式done下擦除；这不是DSP/电机或校准必要性的证明。本机persist值与寄存器读回仍未知，未向生产加入未经现场值核对的恢复或校准。生产otg-selection候选不变、无需重编译；震动及完整12组保持进行中。

震动原厂波形核实：新增[10项WMDR波形表/原始parser/CUSTOM请求检查](logs/haptics-stock-wave-review.json)。从原厂cs40l26.bin独立解码43条记录，与同一A1 probe的原始解析输出逐条核对类型、flags、offset、length和数据SHA。原厂long_vib_id31对应type12、offset1916、length7words，数据SHA `a7a957218ddc595e63d4dc8097d5b7aa0b92f72f96104307a1d8bb4f41d4704e`。以文件解析数量43作为显式regmap读边界，原始CUSTOM31/42 worker成功，43越界-22、空表-61、20次读取失败最终-62。排除所查OS4参数包缺波形31的疑点；不证明DSP加载/电机输出，也不据此把生产SINE换成CUSTOM。当前otg-selection镜像未改，震动及完整12组仍进行中。

CPU温度身份核实：新增[六版本原厂DT/驱动注册证据](logs/thermal-topology.json)。匹配base+overlay5合并后，cpu-crg均引用已启用的tsensor@EB008000通道0，同控制器22个物理传感器、整树38个thermal区域。原始模块通过devm_thermal_of_zone_register注册；通道0不等于Linux thermal_zone0编号，当前固定路径仍未获运行时身份验证。GUI2没有温度字段，后续应按type=cpu-crg匹配并补显示、缺值/晚注册/编号变化检查。此为静态证据，无生产修改/重编译；震动与完整12组目标继续未完成。

thermal-identity构建后收尾：同镜像9组/102阶段profile回放通过，719来源保持一致；当前交付审计见 `logs/thermal-identity-delivery.json`。GUI和FF库与otg-selection一致，温度界面/物理震动/完整目标仍未完成。

temperature-ui构建后收尾：同镜像9组/102阶段profile回放通过；723来源/维护补丁76+1+3文件重建一致、0待更新。当前交付审计 `logs/temperature-ui-delivery.json`；硬件温度/震动及设置现场仍未完成，完整12组保持进行中。

震动OS2/OS3真实系数续接：新增[60项原始解析器→系数查找→FF上传检查](logs/haptics-legacy-firmware-join.json)。四份OS2/OS3的normal/calib固件均用原始parser解析实际字节；独立packed算法表供给regmap读取。normal固件接同一上下文的原始upload callback/worker，撤掉cl_dsp_get_coeff替身，80ms/8ms/64请求解析到0x280701c/14/18并写20/125/64，与OS4一致。首/次/三项写失败均停止并传-5，缺首项名称原始查找传-14；头错误/固件写错误不产生完整系数，table读失败仍保留解析metadata但返回-5。parser-only也能建立软件系数且不写固件，不能据此推断DSP已加载。此举补齐旧版“模拟系数地址”边界，没有执行完整probe/参数加载、真实PM/input/workqueue/start/IRQ/DSP或电机；不把结果解释为震动恢复。生产temperature-ui候选与FF库未改，无需重编译，全部12组继续进行中。

震动OS2/OS3参数加载续接：新增[48项原始wavetable创建/固件解析/参数loader和parser接续](logs/haptics-legacy-parameters-join.json)，四版normal均请求5文件/34次参数raw写，calib请求4文件/28次写。逐文件记录原始parser返回，独立解码WMDR核对全部地址/长度/数据SHA。主文件缺失、头错误(-22)、首写错误(-5)及SVC首写错误(-5)均警告后继续，loader最终仍返回0；首分配失败才返回-12。calib模式用原厂参数会有三条revision警告但接受对应区域，不能把警告当作全包拒绝。参数写仅被记录，未使DSP运行，亦未连通完整probe/config/start/IRQ；loader0不是参数完整或电机输出的证明。没有证据将该故障机制对应到用户当前OS4无震动，不改原厂模块或生产请求。temperature-ui镜像未改，全部12组保持进行中。

settings-retry交付收尾：新镜像内脚本回放9组/102次阶段调用通过；724来源及维护补丁76+1+3文件重建一致、0待更新。已有控件反馈21项通过，FF库与temperature-ui一致。交付审计见logs/settings-retry-delivery.json；设置现场、物理震动及完整12组仍未完成。

MTP日期交付收尾：同镜像9组/102次阶段回放通过，725来源及76+1+3维护文件重建一致、0待更新；新镜像仅MTP库字节改变，GUI/FF库与settings-retry一致。当前审计logs/mtp-datetime-delivery.json。物理震动未解决，设置现场原因未确认，全部12组保持进行中。


请求诊断候选交付收尾：同镜像六版本双槽回放9组/102次阶段调用通过，726份构建来源保持一致，维护文件重建76+1+3且0待更新。14项日志与ABI、24项路由、4项后台FF、16项owner检查通过；交付审计入口`python3 scripts/audit_haptics_request_trace_delivery.py`，结果`logs/haptics-request-trace-delivery.json`。这是诊断候选，未确认触摸、现场设置保存或物理震动恢复，完整12组继续进行中。


2026-11-12 设置完整保存链路续查：新增tests/settings_joined_test.py/.cpp，在私有chroot保留真实/mnt/vendor/persist/TWRP路径，执行真实LVGL文字点击/公共行/取消guard/general回调→twrp_settings_store→DataManager Get/Set/Flush/Save→分区lookup/mount入口→InfoManager文件保存与重新加载。checkbox/switch各11场景，共22项通过；只换回HEAD旧partitionmanager方法同22项均失败。已有挂载/保存时挂载、拒绝挂载、ENOSPC、短写、只读、rename失败、目录fsync失败、BackingFile未初始化、常量键拒绝、其他字段超长均覆盖，并在故障解除后再次点击验证重试。目录fsync失败会出现磁盘新值已发布但UI/内存回退，不声称磁盘回滚。底层Mount/IsMounted、属性/元数据、页面导航/电机为显式替身，不是完整Recovery或现场persist；不推导用户设置已恢复。无生产修改或新构建，当前610f4acc诊断候选不变，震动/设置现场和完整12组继续进行中。复现python3 tests/settings_joined_test.py；审核python3 scripts/audit_settings_joined.py，范围详见docs/SETTINGS-ADAPTATION.md。


MTP原子上传交付收尾：同镜像六版本双槽9组/102次阶段调用通过，727来源保持一致、维护文件76+1+3重建且0待更新；与610f4acc候选仅MTP库字节改变。当前审计logs/mtp-atomic-delivery.json。进程退出临时残留、目标断电/USB和完整调用链仍未完成，震动与现场设置尚未解决，完整12组继续进行中。


时区回退交付收尾：同镜像六版本双槽9组/102次阶段调用通过；731来源、维护文件79+1+3重建一致且0待更新。当前审计logs/timezone-retry-delivery.json。MTP与FF库字节保持上一候选一致，物理无震动、现场设置原因及完整12组仍未完成。


FF查询中断交付收尾：同镜像六版本双槽9组/102次阶段调用通过，732来源、维护文件79+1+3重建一致且0待更新；与f31bbe13候选只有FF库字节改变。28路由/6后台FF/14日志ABI及旧查询2失败对照完成，当前审计logs/haptics-probe-delivery.json。没有实机查询中断或电机恢复证据，物理无震动、现场设置及完整12组仍未完成。
# 2026-11-12 当前证据入口复核

当前镜像仍为backup-manifest候选9a1b057d。五项profile/module/策略/init索引原指向旧7f4c4293报告，已核对已有同镜像报告后修正；旧入口记录在logs/current-haptics-evidence-index-before.json。13项定向绑定均匹配，见logs/current-haptics-evidence-bindings.json。全量审计仍在历史module-state-review.json的tests/module_state_test.py摘要处失败，见logs/current-haptics-unified-audit.log；未放宽检查或修改历史摘要。

生产震动路由28、owner16、owner-FF6、LVGL21、操作反馈64、原厂驱动120和trace14重新执行通过。八种时长effect字节与旧trace报告一致；这是软件请求/显式夹具证据，没有实际DSP、电气或马达输出。当前设置故障仍缺现场操作回执，震动、自动触摸及完整12组保持未完成。无生产改动或新构建。

# 2026-11-12 挂载列表与当前软件路径接续

用户确认backup-manifest镜像设置正常；不再将旧设置症状作为当前故障。当前候选9a1b057d及738份生产来源未变，没有构建新镜像。

`logs/mount-list-chain.json`五项以实际列表分支、快照、backend和LVGL验证已分类分区夹具：正常20个mount行/3个storage行，30次刷新不累加，NV/emmc隔离和移除恢复符合当前代码；名称被显式改成同名时如实显示同名。分类/存在是夹具，未执行真实fstab解析、块设备发现、完整GUI或现场列表，故不确定用户“三十多个内部存储”的根因。`logs/settings-navigation.json`45项与`logs/repair-tool-chain.json`七项同时纳入索引，定向来源审计见`logs/current-offline-paths-audit.json`。

定向审计通过不代替全量审计，不解决已有历史报告来源漂移。物理震动和其余原目标仍未完成；不把模型提供的DSP完成或硬件边界替身作为实机恢复。

