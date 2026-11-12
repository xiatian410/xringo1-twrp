> 历史技术记录：OS4 震动现已由用户确认正常，已解决，不属于当前排查或例行检查。以下旧状态只对应当时的记录。当前进度见 [工作队列](WORK-QUEUE.md)。

# dijun 震动离线适配记录

2026-11-12 当前源码复核：生产路由28项、后台owner16项、owner→FF六项、LVGL反馈21项、操作反馈64项及六版原厂驱动120项重新执行通过；[新trace报告](../logs/haptics-current-trace.json)14项核对错误日志、替换/过期语义与8种时长ABI，八份effect字节另与保留的旧request-trace报告逐一比较一致。设备I/O、input core、寄存器、PM或DSP仍是各测试明确的边界，不能把这些结果计作马达恢复。此前直接运行trace脚本的默认入口因引用旧源码绑定而失败；新报告显式使用本轮28项route和六项owner-FF结果，未修改历史trace报告。

本轮同时修复simulation-report.json五项当前镜像检查仍指向旧摘要镜像的索引错误。已核对9a1b057d镜像的已有profile/module/policy/init报告的实际SHA、状态、数量和源码绑定；[13项定向绑定](../logs/current-haptics-evidence-bindings.json)均匹配，[旧入口记录](../logs/current-haptics-evidence-index-before.json)保留。重新执行[全量审计](../logs/current-haptics-unified-audit.log)仍在历史module-state-review.json的测试来源摘要处失败；这项修正不代表全量审计通过。现有现场43次SINE和六次brownout仍无法确认马达输出，设备自身校准/寄存器读回仍缺。没有修改生产请求、校准、供电或镜像，设置现场与完整12组保持未完成。

2026-11-12 最新交付更新为[备份完整清单镜像](../imgs/built/recovery-dijun-unified-backup-manifest.img)，SHA256 `9a1b057d001821b0d9a908c003c3810f5295e6fa500e1716f59ae50364126123`；本次生产改动只处理备份/恢复完整性，FF库与波形/校准没有改动。物理震动仍未解决；已有OS4日志中的播放/完成消息不能证明电机输出。未进行实机测试，不对现场要求重复采集；若现有校准/寄存器采集仍缺实际结果，震动根因仍是证据不足，不能宣称修复。全部12组目标继续进行中。

2026-11-12 当前候选变更为[摘要原子发布版本](DIGEST-PUBLICATION.md)，SHA256 `7f4c42935ff34c01ce85cec049c94b60ebd072400255cf299aedaca10dacafff`。本次不修改FF/GUI字节、校准或波形；物理无震动仍未定位。此前046ab9e3及更早“当前镜像”均属历史检查点，完整12组保持进行中。

2026-11-12 当前状态补充：046ab9e3的mtp-reset镜像及735生产来源一致，物理无震动仍未定位。本轮当前镜像启动/模块夹具核对通过，只证明脚本允许独立震动闭包在触摸失败后继续；不证明驱动、校准或电机。校准恢复仍缺设备自身值/读回，不增加硬件写入。完整索引与历史来源漂移见[交付证据状态](DELIVERY-EVIDENCE-STATUS.md)，后文“当前镜像”均须按各历史检查点解读。

2026-11-12 codec/PCM与FF原始接续：[两份OS4共12场景](../logs/haptics-pcm-ff-join-review.json)执行codec probe、Mode1/Slot1 put、hw_params/sysclk与参数/时钟/RX widget，再接生产80ms SINE/IRQ。原始回调生成slots2/3、24bit word/32bit slot及单声道1.536MHz/双声道3.072MHz夹具缓存；不代表真实backend协商。四次参数寄存器更新全失败仍返回0；RX首/末写失败返回-5，后续FF仍发相同参数和命令。指针/分配/字符串/格式/寄存器/PM/ACK/调度/IRQ为显式边界，无真实ALSA/DSP/电机。详见[范围](HAPTICS-PCM-FF-STATE.md)。生产046ab9e3/735来源保持，未改增益、校准或路由；共享软件路径仍不能选定物理原因，后续重点每设备校准/寄存器读回与输出通路，已有采集不重复索取。设置现场、自动触摸、震动及完整12组未完成。

2026-11-12 ASP与FF同上下文接续：[两份OS4共14场景](../logs/haptics-asp-ff-join-review.json)从原厂A1 probe执行clk_en/asp_start/时钟切换，再提交生产80ms SINE和显式提供的开始/完成IRQ。未开ASP、已开及开启失败均请求相同五次FF写入与0x01800081命令；没有发现纯软件ASP前置门控。ASP标志在尝试前已置1且失败不回退，完成时重启ASP失败可留下state1/count0/completion已饱和；13jiffy STOP超时也可能最终回调返回0。codec/BCLK3.072MHz/PLL0/寄存器/PM/锁/ACK/队列/IRQ仍为显式边界，不证明实际时钟或电机。详见[范围](HAPTICS-ASP-FF-STATE.md)。生产未变，046ab9e3镜像/735来源保持；下一步ASP参数/PCM寄存器与每设备校准读回，震动、设置现场、自动触摸及完整12组保持未完成。

2026-11-12 音频socket对端接续：[两份OS4共34场景](../logs/haptics-audio-peer-review.json)执行原始socket handler→ResourceManager→ModulePrimary→updateA2HMode及串行原子release，使用前轮捕获的72字节启动消息。编号42通知震动流活动并协调已有流A2H；未知编号/短读/EOF/read=-1也请求相同0100回复，不能当成硬件就绪。合成许可流不活动时请求Haptics Source2，app拒绝时0，活动时不请求设置。socket/stream/usecase/app策略/setA2HParameter仍为显式边界，无真实ALSA/DSP/电机。详见[范围](HAPTICS-AUDIO-SOCKET-PEER.md)。没有生产修改或新构建，046ab9e3镜像/735来源保持；下一步ASP与独立FF状态关联，物理震动、设置现场、自动触摸及完整12组未完成。

2026-11-12 原厂线程/XML已接续：[14场景](../logs/haptics-service-tail-review.json)执行动态效果线程构造、原始XML消费者/容器插入及首次worker到等待，发现worker即使空闲也会请求音频socket、设置Source=PCM与ASP/TDM、打开PCM0/9。此前“构造/on无额外mixer写入”只限那些函数，不能扩大为后台没有初始化或FF不依赖音频状态。XML缺失long默认35，正常31；数组失败仍开PCM、socket超时仍继续，接口成功仍不证明路由就绪。libxml/线程/ALSA/socket边界与未执行的完整生命周期列于[范围](HAPTICS-SERVICE-THREAD-XML.md)。生产046ab9e3保持，下一步核对ASP与FF状态及socket对端，无物理震动修复结论。

2026-11-12 实际PCM分支已续接：[26场景](../logs/haptics-pcm-init-review.json)现在执行原始selector/PCM/波形数据构造及AAC初始化本体，后接部分构造上下文的普通on。已执行初始化范围无额外mixer/供电控制请求，AAC初始化返回错误也不阻止外层继续；这不足以将PCM初始化认定为缺失的FF使能。校准恢复、跳过的替代设备/map、XML long-id与恢复标志、loader/libc/math/线程为明确边界，AWA本体和worker未执行，尚非完整服务启动。详见[完整范围和后续](HAPTICS-PCM-INITIALIZATION.md)。当前046ab9e3镜像保持，物理无震动、设置现场及完整12组未解决；下文前次“0x29280未执行”仅是历史边界。

## 2026-11-12：原厂服务输入发现与FF后端构造

后续静态核对：OS4稳定版ODM build.prop还声明`ro.odm.mm.vibrator.device_type=pcm`；0x126c4的原始selector会把pcm映射1、走0x1327c的PCM后端构造。上组单独执行0x26a74的FF后端不能代替该实际分支，也不能据其没有写控制判断完整服务没有写控制。0x29280、0x271e4与XML/线程/后端派发仍须接续；这里没有执行它们或推导普通FF一定依赖PCM。当前MTP Reset候选没有修改震动路径。

[原始指令程序](../tests/haptics_service_init_review.py)和[30项结果](../logs/haptics-service-init-review.json)补查此前播放模拟直接提供初始化状态的缺口。每份OS4服务12种发现前缀路径、3种单独后端构造路径；绑定两份ELF、反汇编及ODM build.prop（audio_haptic_support/cirrus=true、manufacturer=cirrus、sys_path为0-0043）。不是完整服务构造或main执行。

- 外层constructor从0x12ce0执行到0x13084，识别cs40l26_input即调用0x2bdfc恢复，再查询EVIOCGBIT。即使能力查询失败/不支持，恢复请求仍已发生。恢复本体在本组替换为记录调用并返回，原有restore套件单独覆盖，不能把两组称为同上下文恢复。
- FF描述符接受与Cirrus属性独立：Cirrus=false仍保留fd，audio=false不阻止Cirrus=true；mixer_open失败不撤销fd/Cirrus标志。初始effect id=-1、幅度32767。目录缺失/open拒绝/name及能力错误、跳过pwrkey、open/name首次EINTR重试均核对。
- 另从0x26a74执行原始FF后端constructor，原始manufacturer resolver运行，sysfs全局路径作为独立夹具供给。仅以O_RDWR打开/custom_wave并读取custom_wave_id；字段31时保存31，文件缺失或字段解析失败保留-1。没有在这两个已执行范围内捕获额外write、mixer控制写或FF播放ioctl，不能扩大为整个服务没有初始化写。

PLT的目录/ioctl/属性/mixer、分配、libc++字符串及参数读取均有显式夹具；未知调用和100k指令/2秒预算失败即终止。外层0x13084之后的替代设备、XML/线程、音频后端派发和普通on连接没有执行，也没有真实ALSA、寄存器读回、DSP或马达。当前代码缺少原厂校准恢复仍是已知差异，但本组没有证明该差异导致物理无震动；不能因模拟路径完成而盲写校准/功放开关。

复现`python3 tests/haptics_service_init_review.py`；审核`python3 scripts/audit_haptics_service_init_review.py`。生产和当前da614695镜像未改，无新构建；震动与设置现场继续未解决，完整12组目标不变。

## 2026-11-12：原厂CUSTOM请求接入完整上传回调

此前stock-wave检查直接进入post-user-copy worker，没有覆盖原厂服务CUSTOM指针到驱动回调的连接。[新增程序](../tests/haptics_custom_callback_review.py)从两份OS4原始服务helper捕获48字节effect和`{0,31}`数据，long_vib_id来自各自XML；在原始A1 probe/固件解析之后，将effect交给原始`cs40l26_upload_effect`。合成input-core分配ID7并重定位用户指针；原始回调自行分配4字节、检查长度/地址范围、调用copy、入队并flush原始worker，再清理和释放临时数据。原始start最终请求`0x0100001f`，与先前手工填充worker的结果一致。

[12项结果](../logs/haptics-custom-callback-review.json)覆盖每包正常波形31、复制残余1/4字节、分配失败、用户指针越界和编号43越界。失败分别返回-14/-12/-22，复制/地址失败不入队，原始回调清零暂存effect并释放自己的缓冲区；部分复制后原始memset对剩余尾部清零，再释放，检查了释放前字节。没有将失败的CUSTOM上传当作成功播放。

`__arch_copy_from_user`是有界内存复制夹具；Unicorn映射的task/特权寄存器没有真实页表隔离或用户地址故障。分配/释放、kernel input ID、PM/regmap/mailbox、stock表推导的DSP波形计数和顺序队列仍为显式边界。固件parser和原始回调/worker执行不等于DSP运行或真实内核usercopy。没有发现足以据此切换生产SINE到CUSTOM的回调错误；原厂计时线程、gain与真实控制器状态、物理输出仍缺证据。

复现`python3 tests/haptics_custom_callback_review.py`，核对`python3 scripts/audit_haptics_custom_callback_review.py`。本轮未修改生产源码/设备树/镜像；当前交付仍是mtp-transaction候选`da614695…`，震动与完整12组保持未完成。

## 2026-11-12：当前镜像固件发布与实际参数差异

[当前镜像启动脚本回放](../tests/haptics_firmware_publication_test.py)从settings-row镜像提取真实脚本、profile清单和CAS资源，六版本×双槽共12次激活。所有模块初始未加载；在每次insmod替身入口核对firmware_class.path=/lib/firmware及9个Cirrus文件完整SHA256，共624个插入边界/5616次文件哈希比较。cache后删除私有fixture的vendor/odm firmware目录并清空挂载表，继续modules；RAM副本仍与各版本ODM文件一致。该删除仅模拟原始路径不可用，不是执行内核卸载。[结果](../logs/haptics-firmware-publication.json)、[交付审计](../logs/haptics-firmware-publication-audit.json)。

两份OS4原厂ueventd明确ODM先于vendor。同名a2h/dbc文件除了注释还有真实系数差异：a2h有8个32位参数字不同（涉及FM_OSC_FC_DELTA_PHI、ENV_CLICK_GAIN、ENV_BUMP_GAIN、ENV_BUZZ_GAIN/THRESH等），dbc有2个不同，原始固件parser给出名称DBC_RISE_HEADROOM/DBC_FALL_HEADROOM；地址分别0x2805a00/0x2805a04。原始容器/算法表独立解码参数字，名称由原始parser解析，不按文件名推断参数作用。统一镜像保留ODM优先，未将vendor值混入RAM副本。

本组只运行主机shell与私有文件，properties/insmod/挂载/节点是替身，parameter名称解析的DSP表亦是文件解码夹具。没有执行内核firmware loader、真实加载后的DSP寄存器、手机缓存或电机；不能据此认定用户当时镜像用了正确字节或该差异导致无震动。当前候选生产代码/镜像未改。下一步仍需设备自身校准/保护/供电状态；已有采集工具，无新增重复采集要求。

## 2026-11-12：欠压通知与错误释放区分

[44项原始IRQ函数执行](../logs/haptics-protection-irq-review.json)将此前反汇编观察变成有错误分支的请求证据。两包`cs40l26_vbbr_flag`仅打印VBST低于阈值，`cs40l26_vbst_att_clr`仅打印解除衰减，均返回IRQ_HANDLED且不读写regmap。所谓“解除”是硬件事件的日志名称，不是这两个回调恢复软件增益的证据。

另四个故障handler（boost过压、欠压、boost短路、amp短路）执行原始error_release：读取0x2034，以对应bit3/4/2/1执行清零→置位→清零；每个读错误/三步写错误都会短路并返回IRQ_NONE，成功才返回IRQ_HANDLED。寄存器初值与错误为显式夹具，写入不更新供给值；没有执行内核IRQ dispatcher、真实保护状态、供电或电机，不将释放命令成功称为电气故障已解除。未向生产添加手工释放或关闭保护。

这没有改变现场限制：43次播放中6次出现VBST通知、36次既无通知也无提前停止，无法以该告警解释全部无震动。设备自身供电/校准/保护参数仍待已有状态采集结果；生产镜像不变，震动未解决。

## 2026-11-12：Haptics Source是音频PCM/A2H通路

从两份原始OS4模块的重定位数据完整还原10条DAPM route、8个widget及Source enum：值0/1/2分别为Off/PCM/A2H；Source控制使用内核`snd_soc_dapm_put_enum_double`，虚拟寄存器为0xffffffff。PCM经ASPRX1/2追溯到ASP Playback及ASP PLL/Params，A2H另从PCM取输入，最终到OUT。没有Off选中的route。此前服务捕获的Source0→1明确选择PCM，不能称为通用“启用FF”开关。

[执行程序](../tests/haptics_dapm_route_review.py)还运行原始`cs40l26_asp_rx`事件回调，共[20项结果](../logs/haptics-dapm-route-review.json)。显式event2上电在A1写ASP数据路由0x4c00/0x4c20=50及0x4800掩码0x30003；B2读取原始parser定位的SVC FLAGS，初值0时额外置mask5并保存恢复标志，初值1时不改。event4先发mailbox0x3000003，必要时恢复SVC FLAGS，再禁用ASP接收/恢复数据路由；寄存器前两步失败、mailbox失败和无效event均核对返回/短路。

DAPM调度、widget/component/device指针、SVC读数、regmap和mailbox ACK仍是显式夹具，写入不更新供给的寄存器值；没有运行ALSA dispatcher、音频PCM流、DSP或电机。仅手工执行PCM回调不证明选择Source就实际使该widget上电，也不能排除音频初始化对DSP的间接影响。结合此前普通on不调用mixer的原始服务证据，当前没有依据向Recovery启动流程盲写Source=PCM。下一优先证据仍是设备自身校准/persist/供电与DSP保护状态，已有采集工具等待现场结果。

生产镜像仍为settings-row候选`3c0bed7c…`，本项未改播放波形、增益、校准或保护，也未重建镜像。震动、触摸自动启动与完整12组目标继续进行中。

## 2026-11-12：SINE上传使用真实固件系数地址

此前播放模拟将cl_dsp_get_reg替换成虚拟地址，不能排除原始SINE请求与实际固件系数不匹配。[新增执行程序](../tests/haptics_sine_coefficients_review.py)把生产FF字节捕获、原始WMFW parser/coeff-init/get_reg/get_coeff与原始cs40l26_sine_upload接在同一地址空间，两份OS4共[46项检查](../logs/haptics-sine-coefficients-review.json)。

生产8ms/幅度64/80ms请求解析到`BUZZ_EFFECTS2_BUZZ_DURATION=0x280701c`写20、`BUZZ_EFFECTS2_BUZZ_FREQ=0x2807014`写125、`BUZZ_EFFECTS2_BUZZ_LEVEL=0x2807018`写64，生成mailbox记录`0x01800081`。packed算法表Xbase与偏移3/4/5独立计算的地址吻合。SINE调用者传算法0x1f202，而实际元数据记录为0x4f202；原始get_coeff按低16位匹配，**该高位差异不会造成这三项查找失败，无依据改写算法ID或原厂模块**。

覆盖生产1..10000ms（20000请求由生产限制为10000）、period0/3/4/8/10/11/65535的250..100Hz限制、magnitude负数/0/45/64/255/32767的0..255限制。第一个regmap写失败返回-5且不更新输出record，但先占用SINE槽；同ID重试成功覆盖三项。该槽现象已有错误传播，不据此解释当前43次上传成功的现场流程。

算法表由文件解码后供给显式regmap读边界，写入仅记录不更新硬件；没有执行DSP、真实input core、I2C、校准或电机。当前125Hz请求与原厂DT130Hz基础频率接近，但两者不能证明实际共振或可感知输出。本轮排除的是离线系数匹配/地址/参数转换疑点；没有新增生产修改、新镜像或硬件恢复结论。完整12组继续进行中。

## 2026-11-12：区分普通长震动与波形效果的音频路由

[原始服务执行](../tests/haptics_service_route_review.py)与[20项结果](../logs/haptics-service-route-review.json)补齐此前仅解析XML、没有执行列表消费者的缺口。两份OS4服务SHA均为`0eacb88e11a3402b1551b79cc85e3cfcbbd518c7da44684fc5354829e27be2e7`。

- `0x1426c`消费显式安装的XML列表：编号31在DVL缓存1/SVC缓存1条件下请求SVC=0，然后Haptics Source=0→1；SVC缓存已为0时跳过该写。编号0请求DVL=0；编号218在两缓存均0时请求DVL=1/SVC=1。
- 实际控件helper `0x140a0`在调用mixer前更新算法缓存，`mixer_ctl_set_value=-5`只记日志，仍向上返回0。复用该上下文重试31时，原始代码不重试失败的SVC写，只切Source。缺控件则返回-1、结束该次路由；上层`0x1426c`最终尾调用日志，x0不是可靠的路由状态，结果通过最终日志参数判断。
- **普通on入口`0x13e04`在80/300ms、回调为空、校准恢复标志已置位的明确条件下，直接接入原始FF helper，发gain100→CUSTOM{0,31}/replay0→play1→AStatus OK，没有访问mixer。** 此前“缺少原厂Source切换”的差异不能作为该普通长震动路径的必要前提。反汇编中`0x147c8`则从另一波形效果分支调用路由helper。

libc++哈希表布局、设备对象、mixer/FF及日志返回为显式夹具，没有执行XML解析器、constructor、Binder、ALSA、非空callback的计时线程、校准恢复、DSP或电机。这里没有核对Source控件对应的完整内核/DAPM链，也不排除DSP内部依赖。缓存更新/日志成功不证明实际设置，主机请求不证明震动。

本次没有向生产镜像添加mixer切换、改变FF波形或写入校准。当前候选仍为`recovery-dijun-unified-clock-failure.img`（`1c0813cf…`）；下文其他“当前”镜像均为历史检查点。后续仍需区分设备自身stored校准与persist值、实际供电和DSP保护状态；已提供状态采集入口，无新增重复采集请求。震动与完整12组目标继续进行中。

## 2026-11-12：补齐原厂长震动对照入口

独立[诊断工具](../tools/haptics-diagnostic/README.md)新增显式`--stock-long`，固定提交已核对的原厂OS4 HAL请求：gain100→PERIODIC/CUSTOM、2个short{0,31}、replay0→play1→用户指定1..1000ms后erase。现有SINE入口保留。31项主机syscall替身检查通过，CUSTOM完整请求除运行时指针外与原始服务捕获相同，所指4字节也一致；增益/能力拒绝、短写和各阶段失败已覆盖。12项QEMU目标启动/拒绝/普通文件失败检查通过，没有真实播放。

工具不自动选固件/读波形数量，调用者只可用于已审核OS4；不能凭input名称推广到其他版本。CUSTOM不靠replay自动停止，内核阻塞会延长实际时长；显式gain100不会恢复旧值，没有可用通用读回。两入口同时存在波形与增益差异，不能单独归因。使用前先保留现有只读状态采集；本轮未在手机执行，不重复索取日志，也未将工具放入生产镜像。物理无震动仍未解决，当前生产候选仍为e153160d的fsck-result镜像。


## 2026-11-12：核对音频初始化是否为直接FF播放的缺失前提

[复核程序](../tests/haptics_algorithm_defaults_review.py)与[结果](../logs/haptics-algorithm-defaults-review.json)绑定两份OS4原厂模块、正常WMFW及参数文件。由原始parser解析系数地址，再独立解码文件按上传顺序提供的初值，得到：

- SVC的`FLAGS`属于算法`0x4013c`，文件初值为0。
- DVL的`EN`属于算法`0x40140`，WMFW初值0，后加载的`cs40l26-dvl.bin`覆盖为1。
- 原始ALSA get回调在显式提供上述寄存器值后分别返回0/1；PM失败和目标寄存器读失败传播-5，不更新输出。12项检查通过。SVC查询还会执行固件版本读取，故不能把所有regmap读取都当成目标控制读取。

原厂`odm/etc/audio/sku_xring/audio_route_config.xml`的初始控制列表确有`Haptics Source=Off`与`SVC Algo Enable=1`，所以音频初始化与纯固件初值存在差异；XML本身不证明手机实际执行了该控制。`waveform_conf.xml`中长震动编号31列在`no_svc`、不在`no_dvl`，本次只解析列表，没有执行其消费者，不能由名字推导所有播放分支的实际开关。

原始`cs40l26_vibe_start_worker`本次另保存反汇编：其查询TIMEOUT_MS、SOURCE_INVERT并发送mailbox，没有调用SVC/DVL的ALSA get/put。这个直接函数范围不能排除DSP内部依赖或其他路径的初始化。与既有原厂probe自带SINE自检合看，目前证据仍不足以认定“缺少音频服务”就是无震动原因，也不足以把SVC=0解释成静音。**文件初值与主机提供的寄存器边界都不是设备读回；没有DSP、电机或音频core执行。**

保留已有只读状态采集作为区分实际校准/保护状态的入口，不重复要求模块存在证明。本次没有写入控制、提升增益、禁用保护或修改生产镜像。当前候选仍为`recovery-dijun-unified-partition-paths.img`（fac3c815…），震动未解决。

## 2026-11-12：按现场A1芯片核对默认Q与原厂恢复差异

新增[16项原始指令检查](../logs/haptics-A1-calibration-review.json)，[程序](../tests/haptics_a1_calibration_review.py)绑定两份OS4原始模块、固件、原始DT合并来源和现场ID行。实际现场是0x40A260/A1；之前完整DSP配置夹具多为0x40A270/B2，不能把B2不写Q的结果当作A1初始化。

原始probe在实际DT属性下解析`cirrus,f0-default=130<<14`；未提供redc-default/q-default，零初始化上下文字段保留0。probe执行到fw_upload边界刻意返回-5并进入remove，**没有完成A1 probe**。再把解析后的三字段显式转接给另一个已解析原始WMFW的上下文，执行原始`cs40l26_calib_dt_config`，得到：

| 条件 | 原始写入请求 | 返回 |
|---|---|---|
| A1，原厂DT | F0_OTP_STORED=`0x208000`（130Hz）；Q_STORED=`0`；不写REDC | 0 |
| B2，同样字段 | F0_OTP_STORED=`0x208000`；跳过Q | 0 |
| A1，显式正值Q夹具 | 同样F0与指定Q | 0 |
| A1，Q字段超出23位 | 同样F0，跳过Q | 0 |
| A1，F0或Q写入注入错误 | 保留此前已尝试的写入，传播错误 | -5 |
| A1，原始q_stored恢复入口 | 正值十六进制可进入Q寄存器写入；PM错误时不写 | 文本长度或-5 |

Q寄存器由原始parser/get_reg解析为`0x2802150`；F0为`0x2802128`。正值样例`a000`只是私有测试夹具，**不属于设备校准，不能写入手机**。PM、寄存器、设备属性和服务为显式替身，写入不会改变真实硬件；未知DSP如何使用Q、ROM/OTP如何续接、现场Q读回及persist文件值。

这使“原厂服务恢复校准、Recovery缺少恢复”的差异具体到了现场revision的Q分支，但**Q=0尚不等于已证明静音**。已有43次mailbox完成同样不能证明电机。下一判断应比对采集工具中的设备自身q_stored与vib_cal_q；若不一致，再核对单位/范围/恢复错误决定生产修改。不能凭该分支盲写Q或启动测量校准。本轮未修改生产镜像。

2026-11-12 定向状态工具：已提供[采集说明](HAPTICS-STATE-COLLECTION.md)及成对PowerShell/sh脚本。针对现有43次真实播放证据，采集DSP/固件/保护算法参数、stored校准和已挂载persist三文件；不重复要求模块存在证明。两份OS4原始ELF属性分组/7项show核对，11项私有执行覆盖超时/失败/未审核profile与只读输入保持。寄存器show可唤醒DSP，先保存baseline；overprotection_gain不是通用FF增益。设备/Windows尚未执行，不自动播放、不写校准/增益。当前触摸+设置候选仍为487b5；无新震动生产修正，任务保持进行中。

## 2026-11-12：已有raw-off日志同时捕获43次真实震动流程

重新按震动关键词解析用户提供的`imgs/built/1/touch-after-raw-off.txt`（UTF16），发现此前触摸解析未覆盖的1531条Cirrus日志。uptime1189.869809→1277.023436内可配对43次SINE upload_ret0、play val1、start-worker完成、TRIGGER_CP与COMPLETE_MBOX；43次上传均显示43 RAM波形。请求时长80ms共32次，106ms共9次，256ms共2次；trigger→complete中位数分别79.813/108.074/256.7825ms。这是实际driver/mailbox执行证据，已超过input注册/能力快照，但不能证明真实幅度/电机位移，也没有用户空间调用者身份或GUI动作关联。

6次流程记录VBST低于brownout阈值并随后记录解除衰减；其余37次没有该告警，其中36次也未在完成前停止。第16号（从0计数）的80ms流程在约72ms后收到stop，完成间隔约71.059ms；不能将全部43次解释为过早erase。5条`0x13020`首次写NACK在日志顺序上都位于stop请求之后、后续PM state 2完成及stop/erase日志之前；之后又有新上传返回0及TRIGGER_CP/COMPLETE_MBOX。这只是时间窗口，日志没有线程号或事务标识，中间另有PM调用，不能确认每次失败写入的最终返回。撤回此前“NACK未中断后续播放、不能作为无震动原因”的推断；因果关系仍未知。

原厂`cs40l26_vbbr_flag`和`cs40l26_vbst_att_clr`在所查模块中只记录日志并返回IRQ_HANDLED；“解除衰减”字符串不能证明执行了软件增益恢复写入。缺VP-supply/dummy regulator也存在于先前启动日志，但原厂dijun DT只声明VA-supply；尚无依据添加虚假供电节点、关闭欠压保护或提高幅度。保留真实供电测量未知。

[解析器](../scripts/audit_haptics_playback_observation.py)绑定日志、原厂模块和[所查函数](../logs/os4-stable-haptics-field-review.disasm)，[机器结果](../logs/haptics-playback-field-observation.json)保存逐次时间/行号/状态及5个NACK的前后日志窗口；窗口不表示同一事务。下一步仍是设备自身校准/增益/状态只读证据和驱动初始化状态；已有状态采集脚本未在设备执行。没有修改震动生产路径、新建震动修复镜像或运行设备命令。物理无震动保持未解决。

2026-11-12 mailbox/PM错误路径复核：[32项原始ARM64执行](../logs/haptics-mailbox-error-review.json)覆盖两份OS4模块。撤掉完整mailbox函数替身，在regmap边界分别提供首次NACK后成功、前19次失败后成功、20次写失败、读错误、20次读失败、19次busy后清零及20次busy。原函数在写/读耗尽时返回-62，busy耗尽时返回-110；每次busy重新开始独立的20次读取错误预算。

原始stop worker→原始pm_enter→原始mailbox接续进一步确认：PM入口错误直接退出，不打印done；PM入口成功而mailbox写/读耗尽，仍记录Failed to stop playback和done。因此done不能证明停止命令成功，erase_ret0也不替代前一命令返回。原厂[PM反汇编](../logs/os4-stable-haptics-pm-error-review.disasm)的state 2 done在成功返回分支，但现场无TID，不能将其强行绑定到某条NACK。寄存器读写、runtime-PM返回、锁、sleep、恢复helper及PM退出为显式夹具；没有执行PM core、I2C、DSP或马达，也不证明现场重试恢复。复现`python3 tests/haptics_mailbox_error_review.py`与`python3 scripts/audit_haptics_mailbox_error_review.py`。生产镜像不变，震动仍未修复。


2026-11-12当前交付为ordinary-reports触摸启动策略候选，SHA256 `0d6b65d3a2e526c95220fd3cffdf6b9021c977c1a028d3055b199091da005bd5`；该次重建没有修改FF播放/校准。震动仍未恢复，旧镜像缺失记录仅描述此前检查点。新增设置故障另查持久化，不将其直接归因为震动驱动。

日期：2026-11-11。用户反馈上一版仍无震动。本轮检查原厂固件和实际生产调用链，修正可确认的软件缺口；没有连接手机，没有执行校准，也没有确认电机已经恢复。

第二批现场补充更新了芯片条件：[动作关联观察](../logs/touch-action-runtime-observation.json)绑定用户`touch-dmesg-before.txt`，该次启动识别CS40L26 ID0x40A260/revision0xA1、实际加载43个RAM波形，probe自检上传返回0、start worker完成。早期B2 q拒绝与RAM count5/32的模拟只是条件分支覆盖，不能作为该次实机条件；本机A1 q路径和CUSTOM31索引范围需据43波形分析。当前生产仍使用SINE，原厂probe自检同样使用SINE，不能只因原厂HAL采用CUSTOM就断言SINE入口错误。日志没有GUI请求关联或物理输出证据，无震动仍未修复。

当前交付目录镜像再次缺失；Android原始输出的c282f文件仍存在且哈希已核对。后文“已恢复”的记录是较早检查点，不表示当前交付文件存在。独立ARM64 linker检查使用原始输出，详见[范围](PROFILE-LINKER-ARM64.md)，没有生成新镜像。

2026-11-12 已从 Android 构建目录恢复原始镜像，SHA-256 `c282f535b1fdac6f5eafe25ca46116441195affe9d67f4511178a930634c4346`，重新核对封装、六份 profile 和当前编译二进制通过。707 份来源指纹为本次事后重建，已明确标记，并非恢复了构建时原始清单。未修改生产代码或重新编译；触摸和震动仍未解决。

OS4.0.4 现场补充：用户日志包（历史路径 `../imgs/built/1/os4-touch-20261112-000013.zip`，当前工作区缺失）及[只读解析报告](../logs/os4-stable-haptics-runtime-observation.json)确认运行时模块和 `cs40l26_input` event4 已出现，FF_PERIODIC/SINE 能力可见，`/dev/input/event4` 为 `root:input 0660`，Recovery 选中了该后端。firmware rootfs 写入及 `adaptive_haptics_prop` AVC 均标记 `permissive=1`，这不是操作失败的证据。现场没有 Cirrus probe/DSP 启动日志、真实 ioctl/play 回执或请求前后 IRQ 差值，无法把故障缩小到 DSP/mailbox 或物理执行器；震动仍未解决。

## 历史候选记录

诊断工具目标运行补充：[8项QEMU用户态执行](../logs/haptics-diagnostic-arm64-test.json)运行交付静态ARM64文件，实际bionic启动/参数/时钟/stdio/open/close执行；无参数和非法时长返回2，缺节点ENOENT，普通文件名称ioctl返回ENOTTY后关闭。使用临时前缀和不存在的唯一event路径，没有真实input、成功FF请求或DSP执行。该结果补足此前只有目标编译的局限，不能证明手机运行兼容性、Android内核/SELinux或电机。用法与依赖见[说明](../tools/haptics-diagnostic/README.md)，未修改生产镜像。

现场提交定位：提供[独立 ARM64 诊断工具](../tools/haptics-diagnostic/README.md)，不进入生产镜像。当前 Recovery 为 SINE/8ms/64，原厂 probe 自检为 SINE/8ms/45，不能据此认定 Recovery 幅度不足。工具逐步记录 open/名称/能力/upload/play/erase/close 的 BEGIN、返回码、errno、单调耗时；只读 inspect 不上传，play 必须显式指定 cs40l26 input 和时长。保持 owning fd 到 replay 结束后擦除，避免提前 close；内核阻塞和 worker/DSP 错误不由 syscall 成功排除。没有执行目标文件或设备命令。

[20 项主机检查](../logs/haptics-diagnostic-test.json)以 syscall 替身验证失败/短写/睡眠中断/关闭错误、请求前参数拒绝，以及与实际生产捕获的完整效果字节一致。静态 ARM64 文件及构建输入哈希已保存；ARM64 libc 执行、硬件和 OS2 兼容性没有验证。当前生产代码和 c282f 镜像未变，工具不是修复结论。

2026-11-12 原厂校准恢复核查：新增[原始服务执行程序](../tests/haptics_calibration_restore_emulation.py)和[16 项结果](../logs/haptics-calibration-restore-emulation.json)，两份 OS4 服务哈希相同。执行入口 `0x2bdfc`、原始文件读取 `0x2b604` 与写入 `0x2ba98`；属性、文件系统、libc 格式化/十六进制转换和日志为显式夹具，没有访问设备 persist 或 sysfs。正常值为合成样例，绝不可写入设备。

- 原厂从 `/mnt/vendor/persist/haptics/vib_cal_z`、`vib_cal_f0`、`vib_cal_q` 读取十六进制数；日志按 z/32768、f0/16384、q/1024 换算。缺文件返回 -1，无效文本在本组清零初始状态下保留 0，非正数逐项跳过。
- 从 `ro.odm.mm.vibrator.sys_path`（两包均为 `/sys/bus/i2c/drivers/xring-smartpa/0-0043`）探测 `input/input0..9/calibration/redc_stored`，找到后向同一 calibration 目录的 redc/f0/q_stored 写十六进制文本。已覆盖 input4、input9、缺全部/单项、无效/非正数、sys_path 不存在和写失败。
- 原始写 helper 忽略 fprintf 失败，仍继续下一项。恢复函数不置全局 `0x34308`；原厂 FF helper 在调用恢复后直接置 1（原始 `0x11b60..0x11b68`），不检查写入是否成功。因此该标志不证明校准恢复或 DSP 就绪。
- 原始模块的 `q_stored_store` 在 chip revision=B2 时直接返回 -1；f0/redc 则继续经 PM、系数查询和寄存器写入，均可能失败。保存[原始 store 反汇编](../logs/os4-stable-haptics-calibration-stores.disasm)，本批未执行这些 driver store、PM 或真实寄存器写入。

当前 Recovery runtime 没有同等校准恢复，这是已确认的初始化差异；尚无现场校准文件、DSP 状态或相关故障日志证明它导致无震动。下一步应核对原厂固件默认值和播放对这些系数的依赖，再确定是否补入按设备读取并检查返回的恢复流程。不能伪造校准、启动校准或仅复制三项写入后宣称修复。生产镜像未变，触摸 P0 和震动保持未解决。

校准系数续接：[36 项原始驱动执行与文件初值检查](../logs/haptics-calibration-coefficients-emulation.json)，[程序](../tests/haptics_calibration_coefficients_emulation.py)。原始 WMFW parser/系数初始化使用文件解出的算法表作为 regmap 读取边界，解析 525 项元数据并解析出算法 `0x400bd` 的 F0_OTP_STORED=`0x2802128`、REDC_OTP_STORED=`0x280212c`、Q_STORED=`0x2802150`。独立扫描正常 WMFW 的 packed/unpacked X 区和随后五份 WMDR 参数，没有找到三项地址的初值；报告保留 null/空 history，不能据此断言它们在硬件上为零或未初始化，ROM/OTP/DSP 仍未执行。

原始 f0/redc/q store 执行有效、无效文本、PM 失败、寄存器写失败与 A1/B2 条件；系数查询实际运行，PM、整数转换和寄存器访问为显式边界。f0/redc 可写原始系数地址，错误返回 -5，转换失败返回 -22；B2 q 入口直接返回 -1，A1 所供有效值可进入写入。合成数值不是真实设备校准。

本批还执行原始 `cs40l26_calib_dt_config`：原厂 dijun DT 已有 `cirrus,f0-default=130<<14`，向对应上下文字段显式提供该值时，B2 路径会向 F0_OTP_STORED 写 `0x208000`，写失败返回 -5；未供默认值且 redc/q 字段为零的 B2 路径不写这三项。字段来源映射由既有原始 probe/upload 检查另外覆盖，本批没有宣称重跑完整 probe。故“Recovery 没恢复 persist”不能推成“基础频率未配置”，校准恢复作为当前无震动根因的证据仍不足。下一步查 ROM/OTP 初始化与实际播放依赖，不盲目修改生产路径。镜像不变。

2026-11-12 增益核查：[原始指令检查](../tests/haptics_gain_emulation.py)及[结果](../logs/haptics-gain-emulation.json)执行两份 OS4 的 probe、增益回调和 worker。probe 把当前/保存增益均初始化为 100；原厂自检没有调用 set_gain。从实际 WMFW packed X-memory 独立解出 `SOURCE_ATTENUATION`（算法 0x4013c、寄存器 0x28059e8）初值为 0，并检查后续五份参数文件的覆盖情况。原始 worker 将增益 0/50/100 分别映射为衰减 400/24/0；101 和 65535 被回调拒绝且不入队、不写寄存器。因此不能以“未发 FF_GAIN 导致默认静音”为由修改生产参数，尤其不可直接发送通用的 65535。两包共 12 个场景只证明原始指令和固件字节下的行为，PM、寄存器、mailbox、调度仍为夹具；不能排除现场另有调用改动增益，也不证明 DSP/电机工作。

文件：recovery-dijun-unified-module-state.img（历史路径 `../imgs/built/recovery-dijun-unified-module-state.img`，当前工作区缺失）。

- SHA-256：`abc31e604a466df1d6102132caa5a0a880a9f0f8a3f4acb43e1b46ce8c06d9ae`
- MD5：`675950d18c2c5e25bc268cb56d130f45`
- 总大小 104,857,600 B；压缩 ramdisk 76,627,106 B；对齐后封装/填充预算 28,225,536 B。
- 同一镜像包含六份 OS2/OS3/OS4 精确档案、78 个去重 blob；没有新增通用 `.ko` 或首阶段加载表。
- `make -j$(nproc) installclean` 后执行 `make -j$(nproc) recoveryimage`，30 并发。

[历史构建日志](../logs/build-haptics-worker-final.log)仍存在；上列 abc31e 是较早产物哈希，现有 c282f 镜像的实际构建日志是 [input-priority 构建](../logs/build-haptics-input-priority.log)。当前来源清单为事后重建，见本页开头。
界面反馈修正另见 [UI 记录](UI-FEEDBACK-ADAPTATION.md)；上一份 `recovery-dijun-unified-haptics-route.img` 保留。
完整目标的当前进度与待办以 [模拟报告](../simulation-report.md) 为准。
此前 OS4 `haptics-policy`、`haptics-odm`、`haptics-mtp` 产物仅保留历史证据，见 [原记录](HAPTICS-OS4-HISTORY.md)。

## 六份固件证据

2026-11-12 原厂请求对比：[检查程序](../tests/haptics_service_request_emulation.py)执行两包相同 SHA 的原厂服务 `0x119b4` FF helper，显式注入已打开 fd、Cirrus 模式和 route-ready 状态。`waveform_conf.xml` 的 `long_vib_id/data=31` 作为配置边界提供，没有执行 XML parser、构造函数、Binder、PCM、校准或回调线程。80/300/10000 ms 三种请求均先提交 `FF_GAIN=100`，再上传 `FF_PERIODIC/FF_CUSTOM`，custom 两个 16 位数为 `{0,31}`，replay.length=0，最后写 effect-id/value=1。以停止调用者的 duration=0 参数再次执行 helper，只删除该效果。完整服务如何计时/调用停止未在本组执行。

同组捕获当前生产 Recovery 的真实 ABI 字节：`FF_PERIODIC/FF_SINE`、period=8、magnitude=64、replay.length=请求时长。把原厂 custom 数据放在原始 driver worker 的 post-user-copy 边界后，RAM count=5 的显式夹具返回 -22；count=32 的夹具接受并发送 mailbox `0x100001f`，TIMEOUT_MS=0。Recovery 正弦路径此前使用 `0x1800081` 与指定时长。因此两条路径存在可确认差异，但不能因原厂使用 CUSTOM 就断言正弦失效，或把旧模拟中的 count=5 当作现场值。当前没有替换生产波形/增益参数，下一证据需要现场有效波形数、DSP 状态和播放请求相关回执。

两包共 [18 个原厂请求/driver 场景](../logs/haptics-service-request-emulation.json)，[运行记录](../logs/haptics-service-request-emulation.log)保存结果。未知 PLT 服务及执行预算耗尽失败；ioctl/write、PM、波形数量、寄存器/mailbox 为明确夹具，原始 input copy/内核调度和物理电机未执行。报告绑定服务、原厂 XML/属性、模块、当前生产 FF 源码、测试和反汇编。

`scripts/audit_haptics_profiles.py` 从原厂 ODM 属性、模块 ELF、加载计划及 CAS 固件字节重新核对。
[结果 JSON](../logs/haptics-profile-audit.json)记录文件 SHA-256、属性行号、依赖、完整 vermagic、导入 CRC 指纹和固件来源。

| 样本 | 原厂频率 | 提供 CS40L26 的模块 | 硬依赖 | RAM 固件来源 |
|---|---|---|---|---|
| OS2 初版 | 130 Hz | xring_smartpa | miev | 对应 ODM 的 9 个 Cirrus 文件 |
| OS2 末版 | 130 Hz | xring_smartpa | miev | 对应 ODM 的 9 个 Cirrus 文件 |
| OS3 初版 | 130 Hz | xring_smartpa | miev | 对应 ODM 的 9 个 Cirrus 文件 |
| OS3 末版 | 130 Hz | xring_smartpa | miev | 对应 ODM 的 9 个 Cirrus 文件 |
| OS4 当前包 | 130 Hz | xring_audio_hw_third | fsa4480_i2c | 对应 ODM 的 9 个 Cirrus 文件 |
| OS4 正式版 4.0.4.0 | 130 Hz | xring_audio_hw_third | fsa4480_i2c | 对应 ODM 的 9 个 Cirrus 文件 |

六份样本对应五个唯一模块哈希；两份 OS4 的模块相同，其余四份各不相同，不能因模块名、内核大版本相同而交换。计划中硬依赖与 I2C 总线模块先于震动模块；模块从匹配槽位的原厂来源获取，profile 校验并暂存固件后才尝试加载。这项检查证明计划和来源一致，不能证明内核 probe、电源或 I2C 事务成功。

原厂 ODM 的部分同名参数文件与 vendor 不同。统一候选按各自 profile 发布到 RAM `/lib/firmware`，不受随后 vendor/ODM 卸载影响，也不跨版本混用。固件集合包含校准镜像，只保留原厂资源；恢复流程没有运行原厂校准脚本、切换校准模式或改写 persist 校准值。

## 实际调用链修正

[0013 补丁](../dtsrc/O1_asic_dual/0013-haptics-runtime-routing.patch)固定三个生产文件的修改，由 [补丁清单](../dtsrc/O1_asic_dual/patches/series.json)记录基线、顺序和结果哈希。

| 原行为 | 当前行为 |
|---|---|
| GUI2 仅看编译允许标志，设备不存在也报告可震动 | 结合运行时 FF/LED/timed_output 能力；GUI 读取后台缓存，空闲时每 500 ms 更新；设备 I/O 可推迟刷新 |
| 能力探测优先 FF，播放却优先旧 LED 节点 | 两条路径统一 FF 优先，再完整 LED 节点对，最后 timed_output |
| LED 只有 activate 节点也算支持 | duration、activate 均须可写 |
| 文件写入、刷新、关闭失败被忽略 | 每步检查并返回失败；duration 写失败不继续 activate |
| 部分设备名查询失败后仍可能使用缓冲区 | 查询失败直接关闭并跳过；限制名称终止位置 |
| 播放直接读取未经通道限制的持久化值 | 使用与设置显示一致的通道上限；0 不播放 |
| 没有设备时难以区别探测失败原因 | 记录匹配名称数、不支持效果数、打开失败数、名称查询失败数；后续仍继续探测 |

每次调用只向选定后端提交；上传或播放失败不立即换另一个后端重复提交。FF 文件描述符失效后可重新探测，设备晚注册也能被后续请求发现。
没有可用硬件时入口隐藏，是能力降级行为，不能当作震动故障已修复。

## 主机回归与证据边界

[测试驱动](../tests/haptics_route_test.py)编译实际 `twrp_hardware_settings.cpp`、`haptics.cpp`、`force_feedback.cpp`，旧后端比较还提取实际 `DataManager::Vibrate()`。系统节点重定向到临时目录，ioctl/属性/设置存储由替身提供，使用 UBSan。

22 个场景全部通过：[报告](../logs/haptics-route.json)。同一组用例在保存的修改前源码中有 15 个未通过：[修改前报告](../logs/haptics-route-before.json)。这包含能力/路由契约变化，不表示发现了 15 个独立硬件根因。

- 能力：没有设备、设备晚注册、消失再出现、编译标志禁用、名称查询失败、不支持效果。
- 通道：按钮/键盘/操作分别传递时长、持久化值与读取值越界限制、0 关闭、底层 10 秒上限。
- 路由：FF 与旧 LED 共存、LED 节点缺项、完整 LED、timed_output。
- 错误：打开拒绝、短写、刷新/关闭失败、LED duration 写失败、FF 上传/播放失败。

保留的 [FF/电源键回归](../logs/haptics-route-device-regression.log)另查周期、效果清理、常量/rumble 后备及快速电源键。Cirrus 使用配置 130 Hz，FF 整数毫秒周期取 8 ms（125 Hz），幅度 64；频率与驱动幅度边界的原始证据见历史记录。

测试没有操作真实 `/dev/input`、sysfs、驱动、电机或 HAL，也没有运行 LVGL 图形渲染。本次构建采用通用 FF/LED/timed_output 分支，HIDL/AIDL/TSPDRV/Samsung 分支不在这 22 个用例的覆盖承诺内。
已修复的 firmware_load 权限仍由镜像策略检查独立验证。旧内核拒绝日志来自触摸固件请求，不能据此声称它就是 Cirrus 不工作的唯一原因。
驱动接受 FF 请求后还有内核队列和硬件操作；用户空间成功写入不等于电机完成振动。

## 使用与诊断语义

设置页面会按运行时能力决定是否显示“震动”。进入后可分别调整按钮/键盘（0–300 ms）和操作（0–500 ms）。设备迟到时后台会重新探测，可重新进入设置读取最新能力；页面已经打开后设备消失，修改会返回失败。
“应用”保存设置的结果，不是电机回执；当前硬件 backend 的播放接口不向页面返回播放失败，具体原因仍在 recovery 日志中。
日志区分没有 FF 设备、模块加载失败、固件准备失败、效果上传失败和播放事件失败；内核 probe 细节仍属于内核日志。

新增实际 LVGL 回放：五个按钮回调的双重反馈、键盘拖出仍输入、滑块禁用/重复松手仍确认已修正；21 场景通过、修改前 11 场景失败，见[界面反馈记录](UI-FEEDBACK-ADAPTATION.md)。这使用实际控件、指针事件与绘制，业务操作和硬件输出仍是替身。

剩余：完整页面与其余完成反馈调用者、设备初始化时序、真实驱动队列阻塞、供电与 I2C、实际电机效果。软件范围继续补齐；硬件部分保持 U。本轮不以新的实机操作或物理震动结果作为验收条件。

当前目标文档把震动保留为未解决组。最近离线续接已覆盖原始 mailbox IRQ、生产 FF effect 与主动擦除 completion，且接通原始 regmap pre 回调；详见[ARM64 原厂模拟总记录](HAPTICS-FIRMWARE-EMULATION.md)。Android ODM AIDL vibrator service 与 recovery 直接使用 evdev FF 是不同路由；不能拿 Android HAL manifest 当作 recovery 的驱动/设备可用证明。离线下一步先核实模块计划/等待/权限/事件节点链与 OS2/OS3 差异，真实硬件结果继续标 U。

操作完成反馈已复用 ACTION 设置后端，单调计时、队列合并计时、重复结束抑制与并发忙状态进入 64 项回放；修改前 25 项失败。备份/恢复/ZIP worker 的结果与反馈分开核对，详见[完成反馈记录](OPERATION-FEEDBACK-ADAPTATION.md)。

原厂 ARM64 函数新增 120 项模拟通过：捕获当前生产 FF 二进制请求，执行各版正弦处理/播放回调，核对 DSP 参数、寄存器失败和槽耗尽。[执行范围](HAPTICS-DRIVER-EMULATION.md)区分原始指令与内核/DSP 替身。

后续[生命周期与 DTBO 复核](HAPTICS-LIFECYCLE-EMULATION.md)新增 90 项函数模拟与 48 次原始 overlay 合并，覆盖 input 注册、上传/擦除 worker、重复播放回调及错误返回。原厂 PM 提前失败可能留下成功状态；OS4 组合模块加载成功不保证 Cirrus input 存在。同步擦除可等待“效果时长 + 500 ms”，GUI 后台 owner 已实现并有[16 项并发回归](HAPTICS-WORKER-ADAPTATION.md)；该组未执行完整 probe、start/stop/IRQ；后续补充见下文，真实调度和电机继续未验证。

本轮 [0027 后台执行修正](HAPTICS-WORKER-ADAPTATION.md)已进入当前候选；请求合并/过期、后台失败提示、stop/join 与 FF 描述符释放均有主机回归。非 GUI 完成调用者继续在业务 worker 同步运行。

后续[播放与初始化边界模拟](HAPTICS-PLAYBACK-EMULATION.md)新增 120+54 项通过，执行 start/stop 原厂 worker 和 PLL 前的原厂 probe；固件请求/解析失败、I2C 包装、原始 DTBO 属性、供电/复位/pinctrl 早期失败均有边界记录。完整 DSP/IRQ 与物理电机仍待验证；当前镜像未变。

## 2026-11-12：现场 A1 完整启动与生产 FF 接续

[16 项接续结果](../logs/haptics-A1-joined-review.json)由[执行程序](../tests/haptics_a1_joined_review.py)生成，覆盖两份 OS4 的原始 probe、DT、固件/参数、配置、自带 SINE 自检，以及生产捕获的 80ms/8ms/64 请求和原始 mailbox handler/erase 等待。此前 A1 校准检查显式跨上下文转接，本次在同一设备上下文中完成；旧检查保留其原范围。

A1 原始 resolver 选择 ROM 首地址 `0x2800370`，B2 为 `0x2801f98`。仅替换芯片 ID 而沿用 B2 寄存器夹具会在 `0x2800368` 的未知读取处拒绝继续，不能当成设备故障。A1 的 PM 状态读取明确供给 `[3,1,3,3]`：前两次对应加载前关闭，后两次对应加载后唤醒；这些是模拟输入，不是从写入推导的实际状态。保留过时的 `[3,1]` 负例会返回 -22，证明原始代码检查加载后状态。

原厂 DT 分支在 DSP 配置中请求写序列的 A1 errata 首项 `0x2c28=0`，并非无条件执行五项表。稍后 boost 配置也操作相同 key/clip 地址，不能据地址相同把它算成其余 errata 已执行。A1 在同一 probe 中写 F0=`130<<14`、Q_STORED=0，B2 跳过 Q；A1 errata 首序列写失败、Q 写失败和固件首写失败都传播 -5 到 probe/remove，不进入 input 或自检。成功夹具下两版均完成 68 次固件/参数写、25 次序列 bulk 写及 27 个 IRQ 注册调用。

A1 接入生产 FF 请求后，原始上传写入 duration=20、frequency=125、level=64，启动 timeout=80 并请求 mailbox `0x01800081`。显式提供 start/done 消息时 erase=0；只有 start 没有 done 时请求 580ms 等待后返回 -62、保留效果。自检/生产请求/IRQ 在同一上下文执行，但 input、PM、邮箱确认、寄存器、全 FF 序列、队列/单等待者 completion 都是边界替身；没有执行 DSP、真实内核并发、物理 IRQ、校准读回或电机。

本次没有发现可直接落到生产代码的 A1/B2 选择错误，不修改原厂模块、Q/增益/保护或音频 Source。生产镜像仍为 settings-row (`3c0bed7c…`)。A1 Q=0 是否影响本机输出、persist 校准恢复和供电/保护状态仍需已有现场证据入口区分，不能由这组通过结果推断震动恢复。震动和全部 12 组目标继续未完成。

## 2026-11-12：补齐 FF core 停止再擦除边界，并与现场43次对照

此前完整驱动模拟直接调用 `cs40l26_erase_effect`，没有执行 Linux FF core 的停止前置回调。[新增16项检查](../logs/haptics-ff-core-review.json)将上游Linux v6.18 `check_effect_access/erase_effect/input_ff_erase/input_ff_flush` 原函数编译为宿主C，通过显式ctypes桥接同一A1原厂probe/配置/生产FF/停止/擦除ARM64上下文。EVIOCRMFF由evdev转到input_ff_erase，先playback(id,0)，清owner，再调用erase；失败恢复owner。close路径flush逐项调用但忽略错误、返回0。上游文件为版本参照，不是已恢复的本机vendor内核源码；锁/日志、内核结构为夹具，没有执行真实内核并发。

覆盖已自然完成、stop后done、只有stop确认、无完成、stop mailbox失败后done、stop PM失败后done、close仅stop及错误owner。只有`0x01000012`停止确认会通知stop completion，不能代替`0x01000000`播放完成；在保持播放状态的显式夹具下，erase请求580ms等待后-62。直接erase会报告失败并恢复owner；flush却仍返回0。这是参考core/原始驱动之间的失败机制，不是本机已发生或已修复的证明。PM/寄存器/全FF序列/mailbox/队列/completion仍为显式边界，DSP、电机未执行。

随后对已有现场 `touch-after-raw-off.txt` 做[独立43次停止/擦除配对](../logs/haptics-erase-field-observation.json)：每次stop0→erase请求→stop worker done→erase worker均有记录，43次 `erase_ret` 全部0，最大请求至完成为10.491ms。**现有现场没有此擦除超时证据，不能以模拟风险解释那批无震动，亦不能据close=0断言驱动清理成功。** 未取得用户态ioctl返回、caller身份、校准读回或电机位移。现有43次上传/start/mailbox证据与此互补。

当前mount-mode候选保持不变，无生产参数/播放模式修改，不重编译。已有采集工具针对本机校准和状态的缺口仍有效；没有重复要求实机测试。震动及全部12组继续未完成。

## 2026-11-12：六版本供电/复位/IRQ完整引用

[静态解析程序](../scripts/audit_haptics_power_topology.py)重新编译AOSP libfdt，合并六个原始base DTB与dijun overlay5，并与已记录合并SHA逐项核对。沿phandle解析得到[六版拓扑](../logs/haptics-power-topology.json)：VA-supply均为`/soc/spmi@E0001000/pmic@f/mldo8`（声明1.65–1.96V范围，不是读回电压），vin-supply为`mbuck10`，后者有regulator-always-on。复位引用EC128000控制器offset24，GPIO line名为GPIO_105、低有效；IRQ引用E000C080控制器offset14，GPIO_046，interrupts={14,8}为低电平触发，default pinctrl引用gpio_046_default。数字GPIO全局编号不能直接由line名推导，因此未生成手动gpio命令。

对每版原始ELF重定位`cs40l26_supplies`表，名称均为VP/VA。OS2/OS3数组总长64字节、OS4为48字节，按各自布局读取而非套用OS4 stride。六份原厂DT均只声明VA，没有VP。已有现场明确记录`supply VP not found, using dummy regulator`，与缺少VP声明相符；这**不证明VP物理供电缺失、不证明dummy导致静音，也没有可据此编造的VP phandle**。

两份OS4全部已提取init rc逐文件绑定哈希并保存相关命令。vibratorfeature rc包含校准目录、权限、service/property启动，没有write命令；另一个system通用init的相关写为`/sys/class/leds/vibrator/trigger "transient"`，用途是创建LED属性。它不指向本机Cirrus input，不能据此补一个功放使能。音频service另声明vibrator_audio_socket_0。此搜索仅覆盖已提取rc，不覆盖二进制服务内写入或未提取脚本。OS2/OS3此服务rc未在现有分析目录提取，报告保留空，不将缺资料当成无启动动作。

本轮解析ELF数据/设备树，没有执行regulator、GPIO、probe或电机；实际VA/VP电压、复位电平、boost与输出依旧未知。静态证据没有发现应添加到Recovery的外部Cirrus使能步骤。保持原厂供电/保护/校准，不改生产镜像；mount-mode仍为当前候选，物理无震动与完整12组继续进行中。

震动校准恢复接续：新增[14项原厂服务→同一probe后A1/B2 sysfs store检查](../logs/haptics-restore-joined-review.json)。A1接受合成z/f0/q，真实系数地址依次0x280212c/0x2802128/0x2802150；B2拒绝Q。越界F0、PM失败或Q写失败传回stdio错误，原服务仍继续，不能以恢复函数结束认定就绪。有效合成值恢复后生产SINE依然提交20/125/64并在显式done下擦除；这不是DSP/电机或校准必要性的证明。本机persist值与寄存器读回仍未知，未向生产加入未经现场值核对的恢复或校准。生产otg-selection候选不变、无需重编译；震动及完整12组保持进行中。

执行 `python3 tests/haptics_restore_joined_review.py`，再运行 `python3 scripts/audit_haptics_restore_joined_review.py`。服务和模块在独立ARM64空间，只有fprintf/sysfs边界显式桥接；文件/格式化/十六进制转换、PM、寄存器是夹具，模块probe/parser/store在同一上下文实际执行。合成阻抗0x28000、频率0x208000、Q0xa000只用于检查，不允许写入设备作为校准。恢复阶段临时PM拦截在生产请求前撤销，防止无意改变后续执行范围。

震动原厂波形核实：新增[10项WMDR波形表/原始parser/CUSTOM请求检查](../logs/haptics-stock-wave-review.json)。从原厂cs40l26.bin独立解码43条记录，与同一A1 probe的原始解析输出逐条核对类型、flags、offset、length和数据SHA。原厂long_vib_id31对应type12、offset1916、length7words，数据SHA `a7a957218ddc595e63d4dc8097d5b7aa0b92f72f96104307a1d8bb4f41d4704e`。以文件解析数量43作为显式regmap读边界，原始CUSTOM31/42 worker成功，43越界-22、空表-61、20次读取失败最终-62。排除所查OS4参数包缺波形31的疑点；不证明DSP加载/电机输出，也不据此把生产SINE换成CUSTOM。当前otg-selection镜像未改，震动及完整12组仍进行中。

运行 `python3 tests/haptics_stock_wave_review.py` 和 `python3 scripts/audit_haptics_stock_wave_review.py`。服务FF字节实际捕获，但模块从post-user-copy worker接入，没有执行特权user-copy、真实input core、FF_GAIN或服务停止计时；CUSTOM的replay0与外部停止需求仍保留。43来自文件元数据，随后供给显式regmap边界，并非DSP实际读回。正确编号在upload中两次查询count，越界/空表各一次，读错误重试20次后-62；未知边界和预算耗尽仍拒绝继续。物理震动不能以波形存在、upload0或mailbox成功验收。

温度GUI续接时复核：原厂restore与stock wave来源审计在temperature-ui候选上仍通过，未修改FF库。较早 `audit_haptics_runtime_observation.py` 本轮因原始 `imgs/built/1/os4-touch-20261112-000013.zip` 已不在当前工作区而无法重跑，见 `logs/temperature-ui-haptics-observation.log`；早期归档报告只保留历史证据身份，不能声称当前再次核对该包。现存touch-after-raw-off文本及其43次驱动请求证据不受该缺包结论替代，物理震动仍未解决。

震动OS2/OS3真实系数续接：新增[60项原始解析器→系数查找→FF上传检查](../logs/haptics-legacy-firmware-join.json)。四份OS2/OS3的normal/calib固件均用原始parser解析实际字节；独立packed算法表供给regmap读取。normal固件接同一上下文的原始upload callback/worker，撤掉cl_dsp_get_coeff替身，80ms/8ms/64请求解析到0x280701c/14/18并写20/125/64，与OS4一致。首/次/三项写失败均停止并传-5，缺首项名称原始查找传-14；头错误/固件写错误不产生完整系数，table读失败仍保留解析metadata但返回-5。parser-only也能建立软件系数且不写固件，不能据此推断DSP已加载。此举补齐旧版“模拟系数地址”边界，没有执行完整probe/参数加载、真实PM/input/workqueue/start/IRQ/DSP或电机；不把结果解释为震动恢复。生产temperature-ui候选与FF库未改，无需重编译，全部12组继续进行中。

复现：`python3 tests/haptics_legacy_firmware_join.py`，再执行 `python3 scripts/audit_haptics_legacy_firmware_join.py`。旧模块使用kvmalloc_node/__kmalloc分配接口，DSP指针为CTX+0x58，与OS4的+0x50不同，夹具按各自布局处理；执行预算有限，未知导入/寄存器和预算耗尽拒绝继续。

震动OS2/OS3参数加载续接：新增[48项原始wavetable创建/固件解析/参数loader和parser接续](../logs/haptics-legacy-parameters-join.json)，四版normal均请求5文件/34次参数raw写，calib请求4文件/28次写。逐文件记录原始parser返回，独立解码WMDR核对全部地址/长度/数据SHA。主文件缺失、头错误(-22)、首写错误(-5)及SVC首写错误(-5)均警告后继续，loader最终仍返回0；首分配失败才返回-12。calib模式用原厂参数会有三条revision警告但接受对应区域，不能把警告当作全包拒绝。参数写仅被记录，未使DSP运行，亦未连通完整probe/config/start/IRQ；loader0不是参数完整或电机输出的证明。没有证据将该故障机制对应到用户当前OS4无震动，不改原厂模块或生产请求。temperature-ui镜像未改，全部12组保持进行中。

复现：`python3 tests/haptics_legacy_parameters_join.py`，随后 `python3 scripts/audit_haptics_legacy_parameters_join.py`。loader的七个文件名缓冲区由原始kmalloc_trace调用分配；字符串/请求/释放是显式内核边界，系数查找、文件选择及错误继续逻辑未拦截。正常/校准入口固定调用coeff_load(ctx,0)，与原始fw_upload所查路径一致；不宣称覆盖运行时wavetable切换。

## 诊断请求的波形与增益分别控制

震动诊断因素分离：独立工具新增--sine-gain100与--custom-existing-gain，与原--play/--stock-long组成波形SINE/CUSTOM×是否写gain100的四种请求。两个SINE的effect字节完全相同；两个CUSTOM除运行时指针外与原厂HAL捕获一致，数组{0,31}也核对。47项主机syscall替身和18项目标ARM64/QEMU启动/拒绝/普通文件失败检查通过；不等于真实播放。显式gain100在close后保留，“不写增益”不会恢复默认状态，必须记录执行顺序，不能把跨次请求视为独立初态；工具不自动播放四种模式。CUSTOM继续仅供已审核OS4，cross入口限1..1000ms，无任意波形/增益。重新构建独立工具并打包tools/haptics-diagnostic-os4.zip，未连接手机或修改生产镜像。当前MTP日期候选8c624d0e不变，物理震动、设置现场和完整12组仍未完成。

使用和顺序限制详见[独立工具说明](../tools/haptics-diagnostic/README.md)。本项修正的是诊断归因能力；既有43次现场SINE成功并不能证明CUSTOM会恢复，四种离线请求也没有测到电机。原厂校准值/状态读回仍缺，不向生产写入合成数据。

## 用户态与驱动日志的连接缺口

震动生产请求诊断补齐：维护补丁0040在后台owner记录begin/end/expired、请求序号/时长/队龄/替换计数/耗时，在FF层记录实际type/waveform/period/magnitude和擦除/上传/播放/close的开始结束、实际返回值、独立保存的errno、单调时间与PID/TID。提交入口不执行日志I/O；周期能力probe正常不打日志。GUI与FF序号是不同空间，只能结合线程/时间定位，不能认定跨调用者严格关联。日志可能拖慢worker，不提供阻塞输出的实时保证；accepted仅系统调用边界，不等于电机。24项路由/4项后台FF/16项owner/14项日志ABI核对通过，8种时长effect字节与旧捕获一致。新增擦除失败和短写模拟；短写不再误报旧errno。installclean后make -j$(nproc)30并发新候选recovery-dijun-unified-haptics-request-trace.img，SHA256 `610f4acc2534cbd3fdd95f6733257efa52329435569df5230c4ea1a9c3326a8d`，726来源与封装/新二进制核对通过；同镜像profile另记。未改波形、幅度、增益、校准或触发实机操作，震动与完整12组仍未完成。

完整字段、顺序和边界见[请求诊断](HAPTICS-REQUEST-TRACE.md)。原厂校准值/电机输出仍未取得，不能将新日志或ABI一致视为修复。


FF能力查询中断修正见[说明](HAPTICS-PROBE-ADAPTATION.md)，修正瞬时查询错误触发关闭的风险；不解释现有现场持续无震动，当前产物见simulation-report.json。
