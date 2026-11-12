> 历史技术记录：OS4 震动现已由用户确认正常，已解决，不属于当前排查或例行检查。以下旧状态只对应当时的记录。当前进度见 [工作队列](WORK-QUEUE.md)。

# OS4 原厂震动 DSP 固件解析与地址解析

## 2026-11-12：旧版完整配置、input 与内置自检

[原始执行程序](../tests/haptics_legacy_config_input_join.py)在上一批probe/firmware上下文上继续执行DSP配置、GPIO/boost/brownout、runtime PM、logger、ASP和IRQ/input初始化，并执行原厂probe内置的upload/playback/erase。四份OS2/OS3各11条路径，共[44项](../logs/haptics-legacy-config-input-join.json)；[审计](../scripts/audit_haptics_legacy_config_input_join.py)核对来源、错误传播、原始remove和自检边界。当前生产与镜像未修改。

| 边界 | 已执行的原厂行为 |
| --- | --- |
| CALL_RAM_INIT写入持续失败 | 原始20次写入/等待后-62，尚未设置fw_loaded，也未进入wseq |
| active sequence读失败 / HALO状态0 | 分别-5/-22；fw_loaded已为1，未进入input |
| runtime resume失败 | -5，原始PM错误处理/退出与remove；未注册IRQ/input |
| IRQ chip失败 / 第27个thread注册失败 | 均-5；后者已请求27个virq/thread，仍未进入input |
| input FF分配 / input注册失败 | 分别-12/-5，原始probe退出；回调安装只在FF分配成功后发生 |
| MFD注册失败 | -5，原始remove调用sysfs_remove_groups及input_unregister_device服务；input注册标志仍为1，不能代表设备仍存活 |
| 自检mailbox显式ACK | 原始probe返回0；原始upload/start/erase worker顺序运行，效果链表最终为空 |
| 自检start mailbox返回-5 | probe仍返回0、upload/erase状态字段仍0；因此这些返回或标志不能当作播放命令成功 |

所有场景使用真实DT默认选择的正常WMFW与5份WMDR，独立清单逐段核对68次raw写入。完整配置路径还产生25次wseq bulk写入；这些写入只是被记录，没有真实芯片接受或执行。原厂内置自检effect为48字节、100ms、SINE周期8ms、幅度45；原始解析后上传请求BUZZ2 duration25/freq125/level45，start请求duration100与mailbox0x01800081。这不是GUI生产80ms请求，也不是更换生产波形的依据。

旧版结构由原始反汇编和执行断言确定：CTX input为+0x50、DSP为+0x58、input私有数据为+0x2d8、FF effects为+0x80，四个FF回调指向各自原厂符号。IRQ返回指针槽为CTX+0x1c60。原始alloc_workqueue flags0xa0012/max_active1；运行器在flush处保存调用者CPU上下文，按FIFO执行同一队列中的upload/start/erase，再恢复调用者。它不执行真实内核调度或并发，实际vendor内核的workqueue/input/PM行为仍未证明。

边界仍包括synthetic芯片0x40a270/B2、ROM/PM/HALO/logger/wave-count读值、独立WMFW算法表、全FF立即结束的sequence数据、mailbox ACK、电源/GPIO、分配与内核IRQ/input/PM服务。没有执行DSP，寄存器写入不反向修改夹具读值。两条自检路径均断言没有completion/wait服务调用；未提供或模拟真实完成IRQ，不能称为完成事件验证。后续仍需真实IRQ消息与vendor内核并发/完成链、实际寄存器/校准依赖等证据，不以probe0推出物理震动。

范围纠正：之前前缀16项及上传20项把remove本体标成“未执行/被替换”，这是错误的。原始`cs40l26_remove`符号没有hook，执行跟踪确认每条失败路径进入一次；被替换的是关IRQ、取消工作、注销input等内核服务。两份程序、报告和索引已修正并重跑。下方早期文档关于旧版“本地teardown不调用remove”的判断同样撤回；OS4套件明确hook remove的范围不受此纠正影响。

```bash
python3 tests/haptics_legacy_config_input_join.py > logs/haptics-legacy-config-input-join.log 2>&1
python3 scripts/audit_haptics_legacy_config_input_join.py
```

## 2026-11-12：OS2/OS3 原始 probe 与固件、参数上传连接

当前镜像以`simulation-report.json`为准；下文早期候选为历史检查点。本次没有生产修改或新镜像。

新增[程序](../tests/haptics_legacy_probe_upload_join.py)、[20项报告](../logs/haptics-legacy-probe-upload-join.json)及[来源审计](../scripts/audit_haptics_legacy_probe_upload_join.py)。四份OS2/OS3模块各执行五条路径，从原始`cs40l26_probe`进入，沿真实DT解析、PLL helper、芯片ID判断、DSP分配、wavetable创建、固件请求、pre-config、WMFW解析与系数初始化、WMDR参数加载到配置入口；不再手工准备一个已解析DSP再单独调用后段。

| 路径 | 原始执行与断言 |
| --- | --- |
| 全部文件，PM状态3→1 | 34次WMFW+34次参数raw写入，共68次，逐次匹配文件计算的地址、长度、SHA256；第一MEM_RDY更新注入-5后原始probe退出 |
| 全部文件，PM状态3→2 | 同样到达配置入口；证明该旧版pre-config并非只接受状态1 |
| pre-config一直状态3 | mailbox显式ACK后轮询10次，返回-22；无WMFW解析或raw写入；含前面2次电源/复位等待共12次sleep边界 |
| 第一WMFW raw写入失败 | 返回-5，记录一次写入请求，释放该固件描述符；未加载参数 |
| 主cs40l26.bin缺失 | 原始loader警告并继续另外4份参数，共63次raw写入，仍进入配置；因此到达配置不能证明全部参数已加载 |

每条路径`fw_loaded`均为0，未执行input初始化。持续状态3时，原始upload在pre-config失败处直接返回，未调用该固件描述符的release；本测试执行原厂remove本体，但其取消工作、关闭IRQ、释放内核设备等服务仍是夹具；不能把upload的缺少release观察扩大为实际内核卸载后的泄漏结论。

DT取自各样本overlay-5合并清单，固件/参数取实际ODM文件。身份0x40a270/B2与ROM状态读值是明确夹具；算法表由实际WMFW独立解码后提供给regmap。内存分配、request/release、mailbox ACK、regulator/GPIO/pinctrl、电源管理与remove调用的内核teardown服务为边界；写入不改变模拟硬件，也不执行DSP。未知读取/导入及执行预算耗尽均报错。该旧版身份不能用于推断现场OS4的0x40a260/A1，也没有物理震动结论。

下一缺口是旧版完整DSP配置、input注册、start/IRQ与probe自检的同上下文接续；现场无震动、自动触摸与设置故障保持未解决。

```bash
python3 tests/haptics_legacy_probe_upload_join.py > logs/haptics-legacy-probe-upload-join.log 2>&1
python3 scripts/audit_haptics_legacy_probe_upload_join.py
```

2026-11-12 已从 Android 构建目录恢复原始镜像，SHA-256 `c282f535b1fdac6f5eafe25ca46116441195affe9d67f4511178a930634c4346`，重新核对封装、六份 profile 和当前编译二进制通过。707 份来源指纹为本次事后重建，已明确标记，并非恢复了构建时原始清单。未修改生产代码或重新编译；触摸和震动仍未解决。 产物为 `recovery-dijun-unified-module-state.img`，目标状态见[适配检查点](../ADAPTATION-GOALS.md)。

[模拟程序](../tests/haptics_firmware_emulation.py)对旧 OS4 与正式版的原厂组合模块执行 `cl_dsp_create`、header、完整 firmware parser、系数初始化及系数地址查询。每版使用正常/校准两份实际 ODM 固件，每份 16 项，共 [64 项](../logs/haptics-firmware-emulation.json)；[运行日志](../logs/haptics-firmware-emulation.log)保存结果。正常/校准固件具有不同算法和系数布局，模拟算法 ID 分别取自各自实际元数据，不将正常固件的 ID 套用于校准固件。

| 实际执行范围 | 验证结果 |
|---|---|
| 原始 create 和链表初始化 | device/regmap 指针及链表头正确，未直接注入已完成解析的 DSP 结构 |
| 正常固件容器 | 45 个 region；34 次分段 raw write；525 个系数条目 |
| 校准固件容器 | 46 个 region；35 次分段 raw write；428 个系数条目 |
| 地址/字节核对 | 独立容器清单计算 5/6/16/17/18 类型地址及最长 4096 字节分段，逐段 SHA-256 与原始代码的写入请求相等 |
| 不写模式 | 原始 parser 仍建立元数据并进入系数初始化，不发送 raw write |
| 写失败 | 第一次、中间、最后一次写入分别返回 -5，原始代码停止，未进入系数初始化读取 |
| header/长度错误 | magic、header size、格式、core、版本、未对齐总长度均返回 -22，未写内存或建立系数 |
| 系数初始化读取错误 | 首次读取失败返回 -5；算法字段中途读取失败亦停止并返回 -5 |
| 算法表异常 | count=33 和错误结束标识分别返回 -22 |
| 空算法表 | count=0 加有效结束标识时，原始 parser 返回 0，但本次所查系数地址仍为 0，后续原始 get_reg 返回 -22 |
| 匹配算法表 | 提供明确合成的匹配算法 ID、X/Y 基址后，原始初始化写入系数地址，原始 get_reg 返回 0，地址符合独立计算 |

空表用例说明 parser 返回 0 与后续可用系数地址不是同一个验收条件。匹配表用例仅验证软件地址计算，算法表由夹具明确提供；不表示真实 DSP 已运行或产生该表。解析后的系数数量与内存写入请求也不能证明芯片接受了这些字节。

内存分配和复制、日志、释放、regmap raw write/read 都是边界。raw write 记录地址和原始字节摘要，可注入失败；没有物理 I2C 或寄存器状态。算法表和读错误均为合成；没有执行 DSP 指令、probe 全链、IRQ、完成事件、内核调度、真实输入核心或电机输出。未知导入和指令/时间预算耗尽均直接失败。

复现：

```bash
python3 tests/haptics_firmware_emulation.py > logs/haptics-firmware-emulation.log 2>&1
python3 scripts/audit_unified_delivery.py > logs/haptics-firmware-delivery-audit.log 2>&1
```

报告绑定实际模块/固件、反汇编、程序和模拟器依赖；[交付一致性审计](../logs/haptics-firmware-delivery-audit.log)核对这些指纹与现有镜像来源。本批没有更改生产代码，因此不为模拟通过重复构建镜像。

后续需继续原始固件上传到 DSP pre/post-config、芯片/固件身份和启动条件的接续，以及 IRQ/完成事件；OS2/OS3 的此层解析器也未纳入本批。物理电机状态仍为 U，不能将本批算法表故障注入认定为用户无震动的实机根因。

## 原始上传、DSP 关机与身份检查接续

后续 [72 项模拟](../logs/haptics-upload-emulation.json)将两包原始 `cs40l26_fw_upload` 与原始芯片 resolver、wavetable create、PM transition、DSP state-get、pre-config、固件/系数解析器和身份读取接到同一地址空间。每包正常/校准各 12 项、身份边界另 12 项。[程序](../tests/haptics_upload_emulation.py)及[运行日志](../logs/haptics-upload-emulation.log)记录完整范围。

- 固件请求缺失返回 -2；邮箱失败返回 -5。退出低功耗的合成状态持续不满足时，原始 PM 路径尝试五次后返回 -110；随后 shutdown 标记不符返回 -22。关机轮询持续返回状态 3 时，pre-config 十次等待后返回 -22，均未进入固件 parser 或发送固件 raw write。
- 关机请求写失败、错误固件 magic、第一次 raw write 失败、算法数量读取失败分别阻止后续流程。pre-config 失败时原始 upload 直接返回，未进入 parser 后的 `release_firmware`；模拟保留该观察，不伪造已经释放，也未修改原厂模块。
- 原始 `get_fw_params` 通过原始 `cl_dsp_fw_rev_get/id_get` 执行 regmap 读取。正常 ID `0x1800d4` 的 `0x07022b` / `0x270216`、校准 ID `0x1800da` 的 `0x010123` / `0x21010d` 最低边界及前一版本拒绝、`0x0a0000` 分支、未知 ID/主版本均有断言。所供 revision/ID 是明确合成值，不是芯片实际值。
- 最深接续中，正常/校准固件分别发送 34/35 次固件段写入，完成原始系数初始化和身份检查，继续请求真实 ODM `.bin` 参数文件，进入原始配置函数；在第一条 MEM_RDY 更新（`0x2900`, mask/value=2）明确注入 -5 后退出，`fw_loaded` 保持 0。
- 正常请求 `.bin`、`-svc`、`-dvl`、`-a2h`、`-dbc`，校准请求 `.bin`、`-svc`、`-dvl`、`-calib`。实际 `.bin` 字节由原始 parser 读取；本批算法 revision 为合成的统一值，原始 parser 拒绝这些参数文件的 revision 后，外层仍继续到配置入口。**没有证明参数已加载成功。** 后续应从原始 packed 固件/参数元数据建立每算法身份与版本，然后接续 DSP config。

邮箱仅提供确认结果，状态序列、算法表和 regmap 都是显式夹具；写入记录不模拟 DSP 执行或真实芯片状态。完整上传超过孤立函数预算，专门入口使用有限 100 万指令/10 秒预算，超限仍失败；没有扩大所有用例的默认预算，也没有将超时计为成功。本批所有上传场景最终均失败，不能宣称已模拟完整 DSP 启动。

复现：`python3 tests/haptics_upload_emulation.py > logs/haptics-upload-emulation.log 2>&1`。新报告绑定原始模块、9 份实际 ODM 文件/样本、反汇编和所有导入程序/模拟器，纳入[历史交付审计](../logs/haptics-upload-delivery-audit.log)。没有当前镜像可供核对；震动与触摸 P0 仍未解决。

## 原厂 packed 算法表与实际参数写入

随后 [16 项接续](../logs/haptics-coefficients-emulation.json)已减少上述统一合成版本的限制。[程序](../tests/haptics_coefficients_emulation.py)独立读取原厂 wmfw 的 `0x11000000` packed X-memory region，每 4 字节反序后解出 24 位 little-endian words，按原始结构取得固件行、13 个算法行和 `0xbedead` 结束标识。两份固件各 14 行，ID、revision、X/Y 基址均来自原始字节；正常固件身份为 `0x1800d4/0x07024e`，校准为 `0x1800da/0x010146`。

这些行通过**寄存器读取夹具**提供；前提是 DSP 对外暴露该固件中的算法表，没有执行 DSP 或证明实际芯片当前处于此状态。没有通过 raw write 回调偷偷合成硬件就绪。

正常路径原始参数 parser 接受 `.bin/-svc/-dvl/-a2h/-dbc`，新增 **34 次参数写入**；校准路径接受 `.bin/-svc/-dvl/-calib`，新增 **28 次**。独立 WMDR 解析按区域 offset、类型、算法 ID/revision、X/Y 基址和 4096 字节分段计算，逐项核对原始代码的地址、长度与 SHA-256。正常/校准总计固件+参数写入 68/63 次。正常场景没有此前的算法版本拒绝日志；仍只在最后明确注入的 MEM_RDY 更新失败处返回 -5。

同组另覆盖主参数文件缺失、第一组参数 revision 错误、第一条参数 raw write 失败；原厂外层仍可继续加载其余参数并到达配置入口。它不会把每个参数错误都传播成 upload 的最终返回，因此参数请求数量、最终返回或到达 config 都不足以确认参数完整。失败后的实际参数请求和写入序列均已保存。

本批固定检查失败写之后的行为，而非强行把整次启动设为成功。当前所有场景仍在配置第一条 MEM_RDY 失败退出，`fw_loaded=0`；DSP boot、后续写序列、IRQ 和电机仍待继续。复现：`python3 tests/haptics_coefficients_emulation.py > logs/haptics-coefficients-emulation.log 2>&1`；[日志](../logs/haptics-coefficients-emulation.log)、[历史交付审计](../logs/haptics-coefficients-delivery-audit.log)绑定全部原厂文件和导入程序。生产树未改；当前镜像缺失。

## DSP 配置与就绪标志边界

[36 项接续](../logs/haptics-config-emulation.json)在原始上传及真实参数解析后，允许第一条 MEM_RDY 更新成功，实际执行 CALL_RAM_INIT、memchunk/write-sequence 解析和写入、HALO 检查及 IRQ mask 更新，最后在 GPIO 读取返回 -5。每包正常/校准各九项，覆盖 CALL_RAM_INIT 连续写失败、两次序列读失败、两次序列写失败、HALO 读失败/无效状态、IRQ mask 读失败和 GPIO 读失败。

CALL_RAM_INIT 连续写失败时原厂尝试 20 次，20 次等待后返回 -62，`fw_loaded=0`。成功后原厂在后续配置完成之前就设置 `fw_loaded=1`；之后上述读写或状态错误返回 -5/-22，该标志仍为 1。必须同时检查最终返回和后续初始化，不能仅凭这个标志宣称固件就绪。

原始 ACTIVE_SEQUENCE/POWER_ON_SEQUENCE 分别读取 132/516 字节，本批提供全 FF 的立即终止序列，明确不是芯片转储。原始代码随后实际生成并请求写序列；最深 GPIO 场景记录五次 bulk write。PM/HALO/IRQ 寄存器值、邮箱确认和 debugfs 返回是明确边界，写回调不改变这些状态，不表示 DSP 已运行。正常/校准仍分别执行 68/63 次实际固件及参数 raw write 请求。每个场景都以注入错误或无效状态结束，没有完整配置成功场景。

复现：`python3 tests/haptics_config_emulation.py > logs/haptics-config-emulation.log 2>&1`，再运行 `python3 scripts/audit_haptics_config_boundaries.py`。报告绑定原始模块、全部实际固件/参数、反汇编及导入程序；专用审计验证来源指纹、四种驱动/固件组合与关键错误分支。此处 GPIO 之后的配置、完整 probe 和 input 初始化当时尚未覆盖；随后已由下文 probe、postboost、runtime-PM、IRQ/input 与自检接续推进。这里的 36 项配置用例仍全部以错误或无效状态结束，未执行 DSP，也不证明物理电机输出。OS4 正式版触摸 P0 仍未解决。

六份 OS2/OS3/OS4 样本的固件字节比较另见[机器报告](../logs/haptics-firmware-cross-version-audit.json)和[核验结果](../logs/haptics-firmware-cross-version-audit-verification.json)。七个 Cirrus 文件的 ODM 字节跨六样本一致，样本内 ODM/vendor 的全部 42 对关系也已核验；firmware ELF 与输入文件哈希绑定。该结果只建立提取字节来源一致性，不建立内核运行时请求/发布、parser、DSP 或电机结论。复现 `python3 tests/haptics_firmware_cross_version_audit.py` 后运行 `python3 scripts/audit_haptics_firmware_cross_version.py`。统一交付审计现会校验报告中的来源、测试哈希及其汇总核验结果。

这两类证据缩小了“版本间固件内容不同”这一假设，但仍未验证设备实际 firmware loader 选择、成功 DSP 运行或输出。当前有意义的后续工作是沿真实 OS2/OS3 probe 上下文继续，而不是再重复孤立 parser/成功写入；OS4 配置序列的全 FF 数据及 PM/HALO/IRQ 状态也仍是 synthetic boundary，不能把已跑到 GPIO 解释为配置正确。

## 原始 probe 与上传/配置接续

此前上传模拟预置了一部分设备字段，本批 [16 项接续](../logs/haptics-probe-upload-emulation.json)从清零 `CTX` 开始，仅保留明确的 device/regmap 句柄。原始 `cs40l26_probe` 读取绑定到实际 overlay-5 的 DT 属性，执行原始供电/复位请求、PLL 寄存器更新和芯片解析，建立 ROM 指针与默认字段，随后原始调用进入上传/配置。同一地址空间执行，无跨实例转接，也未用上传函数替身。

两份 OS4 每包八项，分别在请求固件、第一条 raw write、CALL_RAM_INIT 连续写、第一条序列读/写、HALO 状态、GPIO IRQ mask 读及后续 boost-control 读处失败。最深场景实际执行 GPIO、boost DCM/IPK，写 `0x3808=0x40` 和 `0x3800=0xaa` 后在 `0x3804` 显式返回 -5。原始写序列请求九次 bulk write；已有地址可能更新原序列条目，不以调用次数推断每次都新增条目。

独立固件/WMDR 清单核对全部 68 次 raw write 的地址、长度与摘要；原始读取默认 F0=130<<14，fw-defer/rom-only 为假，实际选择正常固件。八种失败都传回 probe，进入 remove 边界并未执行 input 初始化。CALL_RAM_INIT 之后的失败仍有 `fw_loaded=1`，但 probe 返回负值，进一步明确该标志不足以证明绑定和 input 就绪。

原始 DT 证据及其原始固件来源哈希逐项检查。fixture 仍包括 regulator/GPIO/pinctrl、workqueue、regmap、邮箱、debugfs、立即结束的全 FF 序列、PM/HALO/IRQ 读取值和 remove 返回；remove 仅记录调用，没有验证内部释放。没有 DSP 指令执行、物理电源/总线、真实 IRQ/完成或电机输出。新 probe 入口使用有限 100 万指令/10 秒预算，超限失败。校准固件此前有孤立上传/配置覆盖，本批 probe 只走实际 DT 选择的正常固件。

复现：`python3 tests/haptics_probe_upload_emulation.py > logs/haptics-probe-upload-emulation.log 2>&1`。[程序](../tests/haptics_probe_upload_emulation.py)、[日志](../logs/haptics-probe-upload-emulation.log)及[历史交付审计](../logs/haptics-probe-upload-delivery-audit.log)保存范围、关键分支与来源。后续离线工作继续检查原厂初始化和不同 OS 模块路径，不将故障注入认定为实际无震动根因。生产树未改；当前镜像缺失，触摸 P0 与整体目标仍未完成。


## Boost 后的 clip、欠压保护与第二 IRQ mask

[26 项原始接续](../logs/haptics-postboost-emulation.json)每份 OS4 各 13 项，从原始 probe、真实 DT 属性解析和正常固件上传推进到 boost-control、clip、DBC、zero-cross、noise/aux-noise、校准参数及欠压保护。独立原厂容器/WMDR 清单仍核对全部 68 次 raw write。每项故障都传回 probe=-5、调用 remove 边界且未执行 input init；此时 `fw_loaded=1` 仍保留，不当作可震动证据。

[程序](../tests/haptics_postboost_emulation.py)明确给 `0x381c/0x3804/0x7068/0x201c/0x6408/0x6404` 提供合成读数，最后两个高字节分别设 A5/5A 来验证保留位。所有写入只记录，不改变硬件。全 FF 立即结束序列、PM/HALO 状态、邮箱应答、debugfs 和 regulator/GPIO/pinctrl/remove 服务仍继承前述夹具，未执行 DSP、真实 IRQ 或实际清理。

- 分别注入 clip 读/写、欠压 enable 读/写、两个阈值寄存器读/写错误；四个序列高低部分分别在第 19/20/21/22 次 bulk write 失败。每项检查准确终点和失败传播，没有用笼统成功值越过未知边界。
- 原始 device-property 服务目的地址记录显示 `cirrus,vbbr-thld-uv` 写 CTX+0x1b74，`cirrus,vpbr-thld-uv` 写 CTX+0x1b90。后续 brownout 函数分别消费这两组用于 0x6408 与 0x6404。独立清单按 DT 读取值计算阈值 /55000+1 与 /47000+13、掩码和各档位，匹配 `0xa549140c`/`0x5a491909`；enable 为 0x3000。这里保留原厂实际字段顺序，不据变量名宣称硬件参数错置，不交换生产 DT。
- 最深场景已执行两组阈值写入和 22 次 bulk 请求，在第二组 IRQ mask `0x10114` 读取明确返回 -5，未执行 watchdog/runtime PM。探索中给该读取显式合成成功后可进入 watchdog 再到 runtime-PM 的未知服务，未知服务被拒绝；该不完整探索未纳入成功用例，也不将它说成完整 DSP 初始化。

复现：`python3 tests/haptics_postboost_emulation.py > logs/haptics-postboost-emulation.log 2>&1`。[日志](../logs/haptics-postboost-emulation.log)和[交付审计](../logs/haptics-postboost-delivery-audit.log)绑定两份原始模块、DT/固件/参数、反汇编、全部导入程序与模拟器。初始独立计算曾误用第二阈值比例，原始写入比较拒绝后按原始常量的有理比例修正为 /47000；未以抄录实际输出替代公式断言。完整 runtime-PM/logger/ASP、DSP 执行、probe 收尾、播放/IRQ/电机和 OS2/OS3 此层仍待继续。当前生产和 module-state 镜像不变，触摸 P0、震动及全部任务继续进行中。


## Runtime PM、logger 与 ASP 的原始接续

新增两包各八项、共 [16 项原始 probe 配置模拟](../logs/haptics-runtime-config-emulation.json)。原始 probe 从真实 DT、正常固件及参数上传继续到 runtime PM、logger 和 ASP；全部 68 次固件/参数 raw write 仍逐段核对。八类故障为 runtime resume、logger COUNT/SOURCE 读取、logger/ASP 分配、ASP 多寄存器写和两条 ASP 写序列失败。每项错误传播到 probe/remove，未执行 input init；`fw_loaded=1` 仍保留。

原始 PM setup 请求 autosuspend=2000 ms。resume 返回 -5 后，原始错误处理实际调用 set-status(0) 和 PM exit，再返回原错误；此前测试对“没有 PM exit”的预期错误，已依据反汇编纠正。其他 logger/ASP 失败也走原始 PM exit。内核 PM 服务和定时器只记录明确的调用/返回值，没有运行真实 PM 核心或调度器。

COUNT/SOURCE 地址由原始参数解析与 get-reg 得到，分别为 `0x2805a34/0x2805a44`；初始读数 0 为合成值，写入不会改变读夹具。logger 原始写 COUNT=1、SOURCE=13964937；ASP 原始请求两条 reg_sequence `[0x4c40,8,0]`、`[0x4c50,9,0]`。全 FF 序列、PM/HALO、邮箱、硬件与 remove 内部清理仍为边界，不能由这些调用推断 DSP、IRQ 或电机已就绪。

复现：`python3 tests/haptics_runtime_config_emulation.py > logs/haptics-runtime-config-emulation.log 2>&1`。未知服务和预算耗尽失败；报告绑定模块、DT、固件、反汇编、所有导入程序及模拟器。下一边界为 B2 邮箱、波形数量和 probe 收尾/input。生产设备树及当前镜像未改；OS4 正式版触摸 P0、震动及整体 12 组工作继续进行中。


## 波形诊断、IRQ 与 input 初始化接续

两包各 13 项、共 [26 项模拟](../logs/haptics-wave-irq-emulation.json)由原始 probe、实际固件/参数、完整配置继续经过 B2 邮箱、波形计数、播放配置、IRQ 和 input 初始化。全部 68 次 raw write 仍与独立容器/WMDR 清单核对，25 次写序列请求记录在案。每项均以明确错误结束，没有完整 probe 成功用例。

- B2 邮箱 `0x03000009` 失败、播放配置 `0x2802158` 写失败会阻断后续 IRQ/input；原始 PM exit 仍执行。
- 波形计数地址由原始 get-reg 得到，NUM_OF_WAVES=`0x2802140`、OWT_NUM_OF_WAVES_XM=`0x2805368`。正常读数 5/0 为显式合成值。任一计数持续 -5 时，两次查询各重试 20 次，共 40 次失败读取；配置仅把负计数用于诊断日志，仍接到 IRQ。最后故意让 IRQ chip 建立失败，不能称为 probe 成功。
- IRQ chip 失败、首个 virq 获取失败、第 1/27 个 threaded IRQ 请求失败均准确传回 probe/remove。显式 IRQ 服务夹具提供 virq 101..127；真实 IRQ 分配、触发、完成事件与 remove 内部清理没有运行。
- IRQ 请求全部通过夹具后，原始 input init 运行并声明 FF periodic/gain/sine/custom 四种能力；原始函数清 rumble 位，安装 upload/erase/playback/gain 回调。input 分配、FF 创建、input 注册、sysfs 创建分别失败，检查 -12/-5 和后续未调用路径。另一个场景在 input init 返回成功、置注册标志 1 后，让 MFD 创建失败，probe 仍失败。input/FF 分配、注册和 sysfs 均为内核服务夹具，没有真实 evdev 节点。

[程序](../tests/haptics_wave_irq_emulation.py)继承已有边界，未修改共用模拟器。PM/HALO/logger、全 FF 序列、mailbox ACK 和 regmap 仍是明确夹具；写入不改变提供的读值。执行原厂 ARM64 不等于 DSP 指令运行或电机输出。报告绑定 DT/固件/模块、反汇编、程序和模拟器来源；[交付审计](../logs/haptics-wave-irq-delivery-audit.log)复核关键失败传播与来源。复现：`python3 tests/haptics_wave_irq_emulation.py > logs/haptics-wave-irq-emulation.log 2>&1`。

OS4 的 probe、自带 upload/play/erase 自检、IRQ handler 和完成消息软件路径已有后续接续，边界是显式内核/寄存器/mailbox夹具，不是 Linux IRQ 调度、DSP 执行或电机位移。下一项跨版本工作是把 OS2/OS3 原始 probe 与现有固件解析、参数加载、input-init 证据接成同一启动路径，并逐版本比较调用/属性差异；不能把仅有符号名当作可执行兼容证明。当前生产设备树、补丁和镜像未改，也没有新的硬件成功结论。触摸 P0、震动和全部 12 组目标继续进行中。

## 六版本 probe 静态调用目标对照

[六份原厂 ELF 的重定位清单](../logs/haptics-probe-callgraph.json)确认 OS2 初版/末版与 OS3 初版/末版在 `cs40l26_probe` 的直接调用目标及出现顺序一致；OS4 旧版与正式版也一致，但两组之间不同。OS2/OS3 probe 包含 `regmap_read`/`regmap_write` 与直接 upload/playback/erase effect 调用；OS4 probe 包含 `cs40l26_part_num_resolve`，使用 `regmap_update_bits_base` 路径，且没有这些直接自测调用。旧版还引用 `alloc_workqueue`、`init_timer_key`、`device_get_child_node_count`；OS4 使用 noprof workqueue、`timer_init_key`、`__dev_fwnode_const`/`fwnode_get_child_node_count`。

这是 ELF relocation/symbol 静态库存，调用重定位次序不等同运行时分支次序；没有执行六个 probe，也没有确认每个直接调用在现场条件下均会触发。它说明 OS2/OS3 的接续必须执行各自原始 probe 并处理自身导入和控制流，不能只拿 OS4 probe 模型或名称相同的函数替代。复现：`python3 tests/haptics_probe_callgraph.py`。报告绑定六个模块哈希和脚本哈希；未改生产代码或镜像。后续仍是 OS2/OS3 probe 到 input/init/selftest 的原始函数接续及明确错误边界，不代表震动恢复。

## OS2/OS3 原始 probe 前缀执行

[16 项执行结果](../logs/haptics-legacy-probe-prefix.json)现对四份 OS2/OS3 原厂 `xring_smartpa.ko` 分别运行 `cs40l26_probe`，DT 属性取自合并后原厂 overlay 5。每个模块覆盖 pinctrl state 选择失败、PLL helper 失败、PLL 成功后首个芯片 ID `regmap_read` 失败，并增加一条越过 PLL/ID 到首个真实 firmware request 的接续。四个失败场景均执行原始`cs40l26_remove`，其内核teardown服务为夹具；此前“本地teardown不调用remove”的判断错误，已用原始符号入口计数、未安装hook断言和重跑结果纠正。

接续场景执行原始 `cs40l26_set_pll_loop`，其五次 regmap 更新及 mode 配置用成功返回夹具；chip ID/revision 以明确 synthetic 值 `0x40a270/0xb2` 返回。原始 probe 随后执行两个 chip ID 相关寄存器读、两个 `0x2806fb0/0x2806fb4` 写、`0x2c04` PLL mode 更新、`0x7404` 启动位更新、六个 waitqueue 初始化，并请求准确名称 `cs40l26.wmfw`。本用例在该 request 注入 `-ENOENT`，原始 probe 以 -2 退出并运行本地清理。该 synthetic 身份不是固件包测得的实机芯片身份；无硬件读回佐证。

属性解析、原始 PLL helper 和 probe 主体为原始 ARM64 ELF；regulator/GPIO/pinctrl、PLL/chip-ID regmap 返回、request_firmware 错误及内核服务是有记录的 host fixtures。firmware bytes 并未交给此 joined probe，也没有运行 DSP、注册 FF input、播放/IRQ/自检或测电机。复现 `python3 tests/haptics_legacy_probe_prefix.py`，独立核对 `python3 scripts/audit_haptics_legacy_probe_prefix.py`。OS2/OS3 的成功固件加载及后续 probe/input/start/IRQ/selftest 同上下文接续仍待完成，不能据本模拟判定震动硬件状态。


## 原始 probe 收尾与自带上传/播放/擦除

[16 项接续](../logs/haptics-probe-selftest-emulation.json)从清零上下文和原始 DT，经实际固件/参数解析、配置、IRQ/input 初始化走到原始 probe 返回，并执行原始 upload effect/worker、playback effect/start worker、erase effect/worker。input/FF/MFD、IRQ、PM、寄存器、mailbox ACK 仍是明确服务夹具；不是运行 Linux 或 DSP。每份 OS4 七条执行场景，加一条拒绝非法队列顺序的模型检查。

原始 probe 请求 `alloc_workqueue(..., 0x20012, 1)`。上游 Linux v6.18 的 `__WQ_ORDERED=1<<17`、`WQ_UNBOUND=1<<1` 和 ordered 队列契约见[固定来源](https://raw.githubusercontent.com/torvalds/linux/v6.18/include/linux/workqueue.h)，已保存并绑定[本地字节](../logs/upstream-linux-v6.18-workqueue.h)。它是上游定义参照，不是此设备正在运行的内核源码证明。模型只接受排队顺序执行：upload flush 执行上传；erase flush 前先执行排队的 start，再执行 erase。曾尝试的“erase 越过 start”模型已拒绝，不纳入合法时序结论。原始内核并发与实际耗时没有模拟。

用户提供的 OS4.0.4 recovery 包有 mailbox IRQ 累计值，但没有采样时间差。原始 probe 自检自身会构造 100 ms sine effect、启动后发送 `0x01800081` mailbox 再擦除；因此累计 mailbox IRQ可能包含 probe 自检，但现有包不能将它与 GUI 用户请求关联，也不能用其计数证明实测电机输出。此次现场 FF 节点和能力成立、Recovery 选择该节点；请求后的 `EVIOCSFF`/play errno 与 IRQ 差值尚无记录。

原始自检构造 periodic/sine 效果，时长 100 ms、周期 8 ms、幅度 45；由原始代码写出三组算法参数 25/125/45，启动写时长 100、模式字段 0，发送 mailbox `0x01800081`。完整 68 次固件/参数 raw write 仍独立核对；原始 get-reg/算法解析不以合成地址替代。正常路径最终清空效果链表，probe=0；这里仅证明该软件流程在夹具下可走通，ACK 不代表物理电机反馈。

故障配对确认 probe=0 不代表自检成功：

- upload PM 失败时上传结果字段仍为 0，后续 start 没有效果可播，erase 报 -61；probe 最终仍返回 0。
- start PM 失败、启动时长写失败、启动 mailbox -5 都可能没有成功播放命令，probe 仍返回 0。
- upload 参数首写 -5，上传结果为 -5、erase -61，probe 最终忽略自检错误返回 0。
- erase PM 失败时擦除结果仍为 0，效果链表保留，probe 仍返回 0；不把遗留状态说成真实内存泄漏或当前设备根因。

所有分支核对 worker 顺序、故障写入和 mailbox、有无链表节点、结果字段及 probe 返回。flush 用保存/恢复 Unicorn 上下文的显式顺序执行，不以返回 1 假装 worker 已运行；未知服务、未到返回地址、超预算或额外 flush 均失败。没有真实完成中断或等待电机停止；当前自检路径没有借此验证完成事件。

复现：`python3 tests/haptics_probe_selftest_emulation.py > logs/haptics-probe-selftest-emulation.log 2>&1`。[程序](../tests/haptics_probe_selftest_emulation.py)、[日志](../logs/haptics-probe-selftest-emulation.log)和[审计](../logs/haptics-probe-selftest-delivery-audit.log)保存指纹与关键状态。下一工作为真实 IRQ handler/完成状态接续、OS2/OS3 初始化差异和用户空间完整设置页面；不依据 probe=0 擅改原厂二进制。生产树和当前镜像未改；触摸 P0、震动与整体 12 组目标保持进行中。

## 已注册 mailbox IRQ、环形队列和完成通知

[新增 30 项](../logs/haptics-irq-completion-emulation.json)每包 15 项，从完整原始 probe 出发查找实际注册的第 23 个 threaded IRQ（夹具 virq 123），执行其原始 `cs40l26_handle_mbox_buffer`。原厂系数解析得到 QUEUE_BASE/LEN/WT/RD 地址 `0x28073fc/400/404/408`，不是直接替换 get-reg 返回值。队列内容是明确的四槽合成环，只有成功写 RD 确认才改变环的读指针；其他硬件写仍不改变合成读值。严格 mutex 夹具拒绝重复锁定或未锁解锁；complete/complete_all 和 sysfs_notify 只记录调用，没有模拟内核完成计数、等待者或真实 IRQ。

消息 `0x01000010` 在门控允许时增加计数；`0x01000011` 同样增加计数，不能按名字误判为完成。`0x01000001` 减少计数；`0x01000000` 调用 complete_all 再减少计数，计数饱和到零；`0x01000012` 仅调用另一 complete。环尾 start→done 核对两次 ACK 的回绕地址，最终回到计数/状态零。强制 mutex_is_locked=0 时，完成通知仍发生，但状态更新被原厂拒绝。初始测试对 GPIO 消息和缺锁时完成通知的预期曾被实际执行拒绝，已依据原厂分支修正并完整重跑。

批量读失败、pending-command 非零、消息读失败和 ACK 写失败均可返回 IRQ_HANDLED=1；其中 ACK 失败不推进读指针，也不执行消息状态更新。返回 1 不能证明队列已消费或震动完成。所有用例核对完整 68 次原厂固件/参数写、锁释放、准确 ACK、状态、通知和完成调用；未知服务或执行预算耗尽失败。DSP 指令、电机反馈、物理 IRQ 交付、内核并发/等待仍未覆盖。

复现：`python3 tests/haptics_irq_completion_emulation.py > logs/haptics-irq-completion-emulation.log 2>&1`。[程序](../tests/haptics_irq_completion_emulation.py)及[交付审计](../logs/pending-flush-irq-delivery-audit.log)绑定来源与关键分支。当前生产树和镜像未改，不由模拟中断推出实际震动可用；后续继续原始播放/擦除等待与完成调用接续、OS2/OS3 初始化和用户空间完整路由。OS4 正式版触摸 P0 与全部目标仍保留。

## 生产 FF 效果、播放 IRQ 与主动擦除等待

[新增 30 项接续](../logs/haptics-active-erase-emulation.json)由实际生产 `force_feedback.cpp` 在 host syscall 边界生成效果，选择 80 ms、FF_PERIODIC/FF_SINE、周期 8 ms、幅度 64、由 input-core 夹具分配 id=7。随后每项从清零上下文、原始 DT 与完整原始 probe 出发，逐段核对 68 次固件/参数 raw write，再执行原始 upload callback/worker、play callback/start worker、已注册 mailbox handler 及 erase callback/worker。上传写 20/125/64、启动写 80/0 并请求 `0x01800081`。ID 分配、input/PM/regmap/mailbox 等仍为明确夹具，不是运行内核/DSP。

本批取消“等待完成直接成功”的替身：单等待者 completion 模型只因原始 handler 调用 complete/complete_all 增加或饱和计数，等待消费普通 token；在等待边界保存 CPU 上下文，另一栈执行原始 IRQ handler，再恢复原 worker。固定 HZ=1000，正返回值用 1 表示剩余 jiffies，未模拟墙钟时间、真实并发/唤醒。上游 [completion.c](https://raw.githubusercontent.com/torvalds/linux/v6.18/kernel/sched/completion.c)／[completion.h](https://raw.githubusercontent.com/torvalds/linux/v6.18/include/linux/completion.h)已保存为[源文件](../logs/upstream-linux-v6.18-completion.c)／[头文件](../logs/upstream-linux-v6.18-completion.h)并绑定指纹；仅作内核契约参照，不冒充设备源码证明。

- 原始 probe 后 `CTX+0x1d4=1`，成功 start 等待启动 IRQ 更新播放状态；没有启动消息时软件状态仍零，erase 不等待便释放效果。启动 mailbox=-5 也会被之后的 erase=0 掩盖。这些是明确缺失消息／错误响应场景，不证明真实硬件没有振动。
- 启动消息置 state/count=1 后，erase 先解锁再请求等待。80 ms 效果的请求期限为 580 ms；零时长为 10000 ms。正确 `0x01000000` 调用 `complete_all(CTX+0x228)`，原始 handler 清状态，再恢复 worker 释放效果。两个完成消息不会把计数减为负。
- 停止消息 `0x01000012` 只通知 `CTX+0x208`，不能满足等待的 `CTX+0x228`。未知消息、队列读失败、读指针 ACK 失败及完全缺少完成消息都返回 erase=-62、保留效果与 active 状态；IRQ 错误场景仍返回 IRQ_HANDLED=1。
- 超时后迟到的正确 done，再次 erase 可返回 0、释放原效果，未请求第二次等待。反向配对先完成并释放，再上传/启动第二个效果；原始成功 start 会清除旧 completion，第二次缺 done 仍超时，旧 complete_all 不能误满足新效果。
- 另两项显式将启动 gate 改为零，执行原始 start 直接状态更新，再配 done/timeout；这是受控软件分支，不改变生产 DT 或驱动。

早期探索曾把 start worker 的基址偏移累加错为 CTX+0x234，断言拒绝后按原始 x20=CTX+0xc0 修正到 CTX+0x1d4，并重新完整执行。所有最终用例检查原始 worker 顺序、精确写入、等待前后锁/计数/状态、释放/保留以及配对重试；没有在 worker/IRQ 运行过程中递归启动同一 Unicorn 实例。每段有限 10 万指令/2 秒，未知服务或预算耗尽失败。

复现：`python3 tests/haptics_active_erase_emulation.py > logs/haptics-active-erase-emulation.log 2>&1`。[程序](../tests/haptics_active_erase_emulation.py)和[交付审计](../logs/haptics-active-erase-delivery-audit.log)绑定生产效果来源、原始 DT/固件/模块、反汇编、内核参照及模拟器。当前设备树/源码/镜像不变；没有足够证据将上述机制认定为用户无震动根因。后续优先实际 regmap IRQ/pre/post 回调接续、OS2/OS3 原始初始化差异和完整 GUI 路由；触摸 P0 与全部任务继续保留。

## regmap IRQ 前置回调

[新增两包共 12 项](../logs/haptics-pre-irq-emulation.json)从原始 probe 解析实际 `cs40l26_regmap_irq_chip` 数据，执行其原始 `cs40l26_handle_pre_irq`。数据中的 pre 指针确实指向该函数，post 指针为 null，driver context 指向 probe context，配置 27 个子中断。前置函数原始执行 `cs40l26_pm_enter`、读取状态 `0x10004`、`cs40l26_pm_exit`。内核 regmap 服务和读值是夹具；没有运行 regmap 核心状态/掩码比较、nested IRQ 映射与实际调度。

PM resume -5 时，原始 PM 错误恢复会 set-status(0)、调用 suspend，然后 pre 返回 -5，不读状态寄存器；状态读取 -5 同样在 PM exit 后返回 -5。状态读成功但 bit0=0 会记录原始错误、仍返回 0；bit0=1 也返回 0。对两类非零条件显式安排子 handler 后，它都执行并通过前述原始 mailbox 路径处理 done。此安排依据固定版本的[上游 Linux v6.18 regmap-irq 参照](https://raw.githubusercontent.com/torvalds/linux/v6.18/drivers/base/regmap/regmap-irq.c)，代码在 `regmap_irq_thread` 调用 pre 时不检查其返回值；本地参照为[源码](../logs/upstream-linux-v6.18-regmap-irq.c)。这只界定测试的 callback 顺序，不证明手机运行的内核源码/行为完全相同，也未模拟实际 status/mask 选择。因此 pre 返回 -5 本身不足以说明设备不会执行 mailbox 子 IRQ。

复现：`python3 tests/haptics_pre_irq_emulation.py > logs/haptics-pre-irq-emulation.log 2>&1`。[交付审计](../logs/haptics-pre-irq-delivery-audit.log)绑定模块、DT、原始反汇编、上游参照和导入模拟器。当前生产文件不变，震动硬件路径与 OS2/OS3 初始化仍待分析；OS4 触摸 P0 和整体目标继续进行中。

## Android vibrator 服务与 recovery FF 路由边界

两份 OS4 ODM manifest 都发布 Android AIDL `android.hardware.vibrator/IVibrator/default` 与 `/vibratorfeature`，ODM init 明确启动 `vendor.xring.hardware.vibratorfeature.service`，并设置 `RICHTAP_DEVICE_PATH=/dev/qcom_haptic`；framework matrix 还声明 `vendor.hardware.vibratorfeature/IVibratorExt/default`。这是完整 Android 系统的 HAL/权限环境。当前 recovery 的[实际 Force Feedback 实现](</root/AAA/twrp/bootable/recovery/twrpminui/force_feedback.cpp>)直接扫描 `/dev/input/event*`，检查设备名与 EV_FF 能力，再上传 effect/write EV_FF；没有调用上述 Android AIDL 服务或读取其配置。不能用 Android HAL manifest 存在来证明 recovery 里该 HAL 已启动或可用，也不应因 recovery 未启动它就直接改 init。

设备树固定 `ro.twrp.haptics_frequency=130`；原厂固件也声明 130 Hz，production FF builder 按整数毫秒周期生成 8 ms，幅度按 CS40L26 的 0..255 边界发 64。[主动擦除接续](../logs/haptics-active-erase-emulation.json)使用实际 production builder 生成效果，并执行原始 OS4 driver 播放/完成等待代码。它验证了请求结构与已分析固件参数的一致性，不覆盖 evdev 打开、recovery init 绑定、真实 IRQ/DSP 或电机。

因此当前用户态与目标驱动能力在主机证据中兼容，但 recovery 启动后可探测到的真实 input 节点仍是缺失的关键证据。本轮不要求实机操作；离线剩余优先检查 init 模块计划是否必然包含并成功触发 OS4 驱动、profile 是否包含完整 firmware、以及构建策略/服务权限是否允许 FF input 使用。最终仍需把现实设备缺口标为 U，不将 Android 的另一个 HAL 路径冒充恢复环境验证。
