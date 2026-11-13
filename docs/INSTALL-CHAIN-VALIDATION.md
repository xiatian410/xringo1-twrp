# 镜像路由与 ZIP 安装链离线验收

<a id="stock-os4-zip"></a>
## 原始 OS4.0.4 完整包：入口已测，完整卡刷未通过

2026-11-13，使用用户提供的 `OS4.0.4.0.XODCNXM` 原始完整 ZIP，大小 7,883,598,024 字节，SHA-256 `a1dcfecccf4397943e6836539bea6573ade01c84ef9ee1e360df9c233493f04b`。首次入口检查使用旧 media-recreate 镜像，结果如下；本节后半为已交付的证书修正。

`tests/zip_install_chain_test.py --stock-os4` 执行主机编译的原 `TWinstall_zip`、ZIP 映射、整包签名验证、原 A/B metadata 检查与命令构造，以及 fork / pipe / wait。私有 chroot 中只访问普通文件，挂载、属性、GUI 和更新引擎为明确替身。

| 检查 | 实际结果 |
| --- | --- |
| 开启签名验证，使用当前镜像原有证书 | 三张证书均无法验证，整包拒绝，更新器未启动 |
| 开启签名验证，仅在诊断环境使用包内证书 | 原验证器通过整包签名，进入参数核对程序；没有修改生产信任库 |
| 关闭可选签名验证，原始 ZIP | A/B 命令进入参数核对程序；不表示安装 payload 成功 |
| 设备属性不匹配 | metadata 检查拒绝，更新器未启动 |

四项 PASS 表示符合上述预期，包含两项拒绝，不能理解为四次刷入成功。参数核对程序确认原始 ZIP 路径、payload 偏移 5229、完整 headers、状态 fd 和该偏移处的 `CrAU`，发送进度并退出；**它没有执行真实 update_engine 或任何 payload 操作**。普通 ZIP 36 项回归也通过。报告为本地 `logs/zip-stock-os4.json` 和 `logs/zip-stock-host-regression.json`，公开摘要见 [CURRENT-VALIDATION.json](CURRENT-VALIDATION.json)。

此前完整 payload 独立执行已覆盖 42 个分区、4933 个操作及全部最终分区哈希，但基于旧 snapshot-map 镜像。不能把历史 payload 执行与这次替身更新器接起来，宣称当前完整 ZIP 安装成功。真实 ZIP → update_engine → SnapshotManager / postinstall → 槽位与合并仍未贯通。详见 [完整 payload 记录](OTA-OPERATION-COW.md)。

首次入口检查只暴露签名限制，没有修改生产信任。随后对六份原厂 recovery 逐一核对：其 OTA 信任库都含同一张小米证书，SHA-256 为 `ff85d8bc50e4eed4c5f54734b20003e845a8ee5f206bfe717335ad594dd01a5e`，与这份包中的证书相同。原厂 recovery 的完整哈希亦匹配各自 payload manifest 分区记录。该来源支持加入固定 OEM 公钥，而非运行时信任安装包自带证书。

设备树 `device.mk` 为 `twrp_dijun` 增加 `PRODUCT_EXTRA_RECOVERY_KEYS` 的 `security/xiaomi-ota`；原三张证书保留。`scripts/prepare_stock_ota_certificate.py` 只从六份固定哈希本地原厂 recovery 提取，任一哈希或证书不匹配就停止；不读取待安装 ZIP，不需要 OEM 私钥。证书字节保留本地，公开脚本与哈希；构建准备见[构建指南](BUILDING.md)。这是设备树构建配置修正，没有平台源码修改或新增平台补丁。

`installclean` 后 `make -j$(nproc)`（30 并发）生成 `recovery-dijun-unified-stock-ota-trust.img`，SHA-256 `f302ff2193ba406d5100a2829bb9d8e862d549d5c2a693c5e91c91daf5d64931`。808 生产来源、六份 profile、封装和当前证书内容核对通过；与上一镜像相比仅构建属性、ramdisk 摘要与 `otacerts.zip` 改变，Recovery / 库二进制一致。

修正后五项检查通过：当前镜像固定信任库开启验证可接受原始 4.0.4 整包；移除仅小米公钥则拒绝；诊断证书可接受；关闭可选验证仍生成正确命令；设备不匹配仍拒绝。报告为 `logs/zip-stock-os4-fixed.json`，普通 ZIP 36 项回归为 `logs/zip-stock-trust-host-regression.json`。这里“接受”只指签名与入口到参数核对程序，不是完成 payload 安装。报告的 `production_trust_changed=false` 表示测试运行没有改写交付镜像；本次构建配置确实增加了一张固定公钥。

```bash
python3 scripts/prepare_stock_ota_certificate.py
bash scripts/compile_recovery.sh
python3 tests/zip_install_chain_test.py --stock-os4 --image imgs/built/recovery-dijun-unified-stock-ota-trust.img --report logs/zip-stock-os4-fixed.json
python3 scripts/audit_stock_ota_trust_delivery.py
```

本批签名支持已修正，不再例行重复证书检查。后续接续真实更新引擎，复用独立 payload 证据；完整 OTA 仍未验收。

---

2026-11-13 A/B命令修正：0062 将payload_properties提取失败从成功码改为INSTALL_CORRUPT，拒绝空/NUL headers、压缩/空/越界payload，fork前防御空执行命令。真实ZIP/原命令与pipe/fork/wait接续21项通过，旧版同组8失败，普通ZIP36项回归通过。无害主机程序替代更新器，不执行真实OTA。installclean后30并发构建ab-command候选，SHA256 704b58f5e97563ba9747bbf3c8d0129b83e1233581dec2941d837dfb704aceeb，六profile封装通过；继承XRING O1及NV限制。见docs/INSTALL-CHAIN-VALIDATION.md#ab-command，完整12组保持进行中，源码文档同步GitHub、编译文件不上传。

2026-11-12 新增下文“真实 ARM64 测试 updater”：20项执行当前镜像linker/libc和ZIP内AArch64 ELF，原主机36项回归通过。安装父进程仍为主机程序，execve处显式桥接QEMU；不是完整ARM Recovery、真实OTA updater或payload验收。当前生产镜像保持sideload-reboot候选，未新增生产修正或构建。下文“ARM updater未执行”是此前检查点的范围。

2026-11-12 ZIP 队列接续：`tests/zip_queue_chain_test.py`从真实公开 backend 的 `start_zip`进入后台线程，运行 `run_zip → flash_zip → TWinstall_zip → 实际 ZIP/摘要/提取 → fork/exec/wait`，随后读取状态、acknowledge 和析构/join。23 项通过，固定 ZIP 时间戳后的修复前/后输入 SHA256 映射完全一致；旧 backend 同组有 5 项失败，报告为 `logs/zip-queue-chain.json`及`logs/zip-queue-before.json`。

复现的两个缺陷是：每次 updater 都会重置传出的 wipe_cache，导致前一个包请求清缓存而后一个包未请求时丢失；WipeByPath 返回失败也没有改变最终 DONE 状态。维护补丁0055为每包使用独立输出并累计请求，队列退出时统一清理；清理失败通过现有 `unable_to_wipe`本地化消息记录，并发布 FAILED。已完成包数保留，不将完成缓存清理当作回滚或重新执行包。

覆盖单/双包、首包/末包/双包清理请求、后包退出失败或非法进度、缺 updater、清理失败、缺文件/空路径、摘要拒绝及显式跳过、签名开启但缺证书拒绝、忙时重复启动/acknowledge、失败后重用、空队列及析构等待。除状态外核对无害 updater 真实写出的执行顺序，失败后后续包不能执行；保留来自失败包的已提交清理请求，与原有语义一致。首次夹具构建遇到标准库 ends 名称冲突和临时文件重名，已修正，不能把这些夹具错误当作生产失败。

DataManager、进度、源文件挂载、缓存清理、块设备解锁、容量刷新、性能与操作反馈是明确替身；缓存marker是清理请求的夹具回执，不证明真实文件系统清理。使用实际公有 backend 头文件，镜像安装虚函数在此套件中为不可调用边界；独立的镜像路由40项回归见`logs/zip-queue-image-regression.json`。本套件是主机原生执行，未启用sanitizer，未定义AB_OTA_UPDATER或TW_OZIP_DECRYPT_KEY；ARM updater、GUI点击、A/B payload/update_engine、OZIP和sideload仍未覆盖。签名正确包的密码学接受由下方独立36项套件证明，不能把两个套件说成同一GUI全链。

当前候选为`recovery-dijun-unified-zip-queue.img`，清理构建和来源核对见`logs/zip-queue-delivery.json`。以下为此前检查点，“尚未连接backend队列”仅指当时。

---

2026-11-12 补充完整传统 ZIP 软件路径：`tests/zip_install_chain_test.py`执行当前 `TWinstall_zip`、实际映射包、ZIP 查询/提取、签名验证、sidecar 摘要、updater 参数构造、fork/exec 和进程回收。使用当前 TWRP 的 package/verifier/asn1 实现、AOSP libziparchive 和真实主机 BoringSSL；私有 chroot 中全部为临时普通文件，无设备或真实分区操作。

36 项全部通过。包括 stored/deflated 包、本地 RSA2048/SHA256 签名接受、错误密钥/篡改/必须签名的无签包/缺证书拒绝、MD5/SHA256 sidecar 核验、损坏/缺失/重复条目、兼容性嵌套 ZIP 读取、提取打开失败、updater 错误退出及非法进度。兼容性用例仅证明当前代码能够读取或拒绝嵌套 ZIP，不是完整 VINTF 验证。密钥只用于本地测试，未写入生产镜像。

这条接续链发现了此前孤立协议测试没有覆盖的实际缺陷：外层安装分派只认通用 `update-binary`，因此 ABI-only 包在提取前就被误判损坏；内部回退循环又在未找到当前 ABI 时退出，可能使用未经成功查询的条目元数据。维护补丁 `0053-zip-updater-abi-selection.patch`让分派和提取共用 `FindUpdaterBinary`：通用文件优先，否则按公布的 abilist 顺序选择，缺少当前项继续查找；abilist 为空或缺失时回退单一 abi 属性，无匹配明确失败。

相同最终测试运行保存的修复前源码，36 项中 6 项失败，分别为首选/第二 ABI、单属性回退、双 ABI 顺序及空列表回退；其余 30 项通过。当前报告为 `logs/zip-install-chain.json`，旧版为 `logs/zip-install-chain-before.json`。双 ABI 反序和通用优先均核对实际执行程序写出的标记，不只核对安装返回值。ABI 后缀程序实际仍为 x86 主机程序，只验证选择，不证明 ARM 程序可执行。进度/属性/卸载为明确替身；本套件未启用 sanitizer，独立 updater 协议的 22 项 sanitizer 回归见 `logs/zip-selection-updater-regression.json`。

最终候选 `recovery-dijun-unified-zip-selection.img`完成 installclean 与 `make -j$(nproc)`（30 并发）构建；750 份来源、六配置封装及补丁重建核对通过。同镜像 profile 9 组/102 阶段调用和 module-state 4 组/24 阶段调用见 `logs/zip-selection-profile-runtime.json`、`logs/zip-selection-module-state.json`，定向交付为 `logs/zip-selection-delivery.json`。继承截图对应的 0048 OTG 发现修正；未改变已获用户正常确认的设置路径。

尚未连接完整 ZIP backend 队列/GUI 点击，也未执行 ARM updater、A/B payload/update_engine、sideload/FUSE/minadbd、真实分区或断电测试。新增 ZIP 套件没有定义 `AB_OTA_UPDATER`，不能由它推断生产 A/B OTA 支持完整。完整 12 组目标保持进行中。

---

以下为补丁0052时的历史检查点，“未执行ZIP”只指当时。

2026-11-12，本轮按任务文档继续安装链路。没有连接设备，全部输出写入一次性主机文件。

`tests/image_install_chain_test.py`执行原始安装后台公开类的start_image、实际线程、run_image、status、acknowledge和析构，并接续原始PartitionManager::FlashImage、FindPartitionByPath、槽位覆盖/后缀、TWPartition::FlashImage/IsSparseImage/FlashSparseImage与真实AOSP libsparse。A/B及非A/B各20场景，共40项通过。除结果状态外还逐字节核对三个不同哨兵文件、写入顺序、原槽位恢复，以及第一槽失败后没有第二槽写入。第二槽同步或关闭失败时，两槽内容可能已经改变，整体必须失败；不承诺双槽原子性。

覆盖单槽、双槽、初始B槽、非slot-select目标、工作中拒绝二次启动与acknowledge、第一/第二槽写入错误、第二槽同步/关闭/容量错误、未知/多个/空目标、缺源、禁用刷写、文件系统目标、容量发现失败、sparse展开越界、文件名推荐及目标列表不可用。设置存储、设备解析、容量ioctl、源文件挂载、UpdateSystemDetails与进度输出为明确夹具；原始slot override执行，但并未执行真实boot-control或硬件槽位解析。ZIP和repacker在此测试中不运行，raw路径以断言防止被意外替代执行；已有65项raw传输测试仍是独立证据，不能称为同一完整链路。

随后`tests/zip_updater_test.py`执行原始update_binary_command→Run_Update_Binary→pipe/fork/execve→主机fixture updater→stdio协议解析→原始WaitForChild。fixture updater只创建私有marker并发送进度/文字/清缓存请求，既不解压ZIP也不操作分区。生产解析器原来直接对缺失字段调用strtof/strtol，空log也向printf传入空指针；错误数值可以进入进度sink。原始代码22场景中14项断言失败，其中缺字段/空log为真实host sanitizer崩溃，非法数值包括测试sink拒绝和未返回失败两种观察，不把它们全部描述成生产崩溃。

维护补丁0052为progress/set_progress校验字段存在、完整数值、有限值及0..1区间；秒数必须非负且不超过INT_MAX。非法进度记录诊断，继续排空子进程输出并等待子进程，最终报告安装失败。空log安全输出空行。pipe/fork/fdopen失败有各自清理；fdopen失败只终止并等待本次fork成功的子进程。流读/关闭失败也报告安装失败。

修正后22项全部通过，正常/签名进度比例、wipe_cache标记、空输出/空log、缺字段、NaN/inf/越界/尾随字符、秒数错误、子进程非零/信号、缺可执行程序、pipe/fork/fdopen错误及未知ZIP类型均覆盖。真实父子进程与文件描述符执行，结束核对无残留描述符及未回收子进程。运行时错误通过syscall wrapper注入；输出sink和日志为主机实现。

本轮仍未执行真实ZIP解压、签名/摘要校验、完整TWinstall_zip→backend队列接续、A/B payload/update_engine、sideload/FUSE/minadbd、GUI点击、ARM64 updater、真实分区或断电。进度协议检查不能替代包兼容性或真实性检查。完整12组目标保持进行中。

## 真实 ARM64 测试 updater

2026-11-12，本轮没有修改生产源码或生成新镜像。当前仍为`recovery-dijun-unified-sideload-reboot.img`，SHA256 `022af2fccb1040b7537b989c9c25d6c57ba844a27f11fae652d1f73bd93a7d2a`，764项构建来源保持匹配。OS4震动调用沿用用户正常确认，不作为本轮排查项。

此前ZIP测试中的ABI后缀文件实际是x86主机程序，只能证明名称选择。本轮新增真正的AArch64动态ELF测试updater，从原始`TWinstall_zip`经过ZIP映射、签名/摘要、选择/解压、`update_binary_command`参数构造、fork、进度管道解析和`WaitForChild`。测试只操作新建私有chroot中的普通文件。

主安装器仍为x86主机编译。唯一跨架构执行替身位于`execve`：检查原目标和完整argv后启动固定QEMU、当前镜像的Android linker/libc以及刚提取的ELF，保留API=3、协议fd和ZIP路径。没有注册主机binfmt，没有用shell或x86程序替换ZIP中的ARM64 ELF。`waitpid`观察器仅记录原始系统调用返回的状态，不替换状态值。它不是完整ARM64 recovery运行。

20项覆盖stored/deflated、合法签名接受与错误密钥/篡改拒绝、SHA256接受/拒绝、ABI后缀选择/不匹配/属性回退、通用updater优先与无ABI属性、提取失败、退出7、非法进度、缺库/缺符号、信号15和先写私有文件后失败。每项核对提取字节与载荷SHA，进入目标程序时记录构造函数初始化值41和真实参数，成功项核对进度管道及result tag，失败前已写内容仍保留。缺符号、缺库必须有具体linker诊断且无main标记；不能仅以失败返回认定测试覆盖正确。20项通过；修改测试入口后原主机36项回归也通过。

首次运行因用clang++编译C夹具而出现C++修饰符号缺失，属于测试错误，已改为C编译器；保留`logs/zip-install-arm64-first-attempt.log`，不作为生产故障。测试编译器、CRT、QEMU及来源清单、ZIP/crypto实现和使用的镜像库均绑定摘要。动态加载仍使用私有目录库路径、默认namespace fallback；缺proc/config产生的警告保留，不宣称目标init namespace通过。

```bash
python3 tests/zip_install_chain_test.py --arm64
python3 tests/zip_install_chain_test.py --report logs/zip-arm64-host-regression.json
python3 scripts/audit_zip_arm64_chain.py
```

报告为`logs/zip-install-arm64.json`、`logs/zip-arm64-host-regression.json`与`logs/zip-arm64-chain-audit.json`，公开摘要为`docs/CURRENT-VALIDATION.json`。离线检查没有执行原厂OTA updater、update_engine或真实payload，也没有接入完整GUI/侧载/块设备、内核挂载或断电。不能据这些无害测试载荷推断所有ARM包兼容，完整12组仍进行中。

<a id="ab-command"></a>

## A/B OTA 命令准备与失败收尾

2026-11-13 新增0064：原update_engine_sideload在ApplyPayload同步拒绝时仍进入loop，并传入空Error；现在使用有效Error并立即返回失败。7项定向通过，旧版4项失败，已实际编译入bounded-maintenance候选。这不是完整payload写入验证，详见[有限维护](archive/BOUNDED-MAINTENANCE.md)。

维护补丁 0062 修正 `abupdate_binary_command` 在 `payload_properties.txt` 提取失败时返回 `false`（数值 0，即 `INSTALL_SUCCESS`）的错误。调用者之前可能因此使用空参数启动子进程。现在返回 `INSTALL_CORRUPT`，失败不发布残留命令；`Run_Update_Binary` 也在 fork 前拒绝成功码配空命令的生成器结果。

更新器使用 ZIP 文件与条目的原始偏移直接读取 payload，不做 ZIP 解压。因此命令准备必须确认 `payload.bin` 为 stored、长度非零、压缩长度等于原长度，且偏移/长度在包范围内。新增这些检查，偏移以明确的 64 位格式输出。properties 为空或含 NUL 时拒绝，避免 argv 截断 headers；正常 deflated properties 仍可解压并接受。不替代 update_engine 对 payload 格式、hash、签名、manifest 或设备更新策略的验证。

`tests/ab_command_chain_test.py` 执行原始 metadata 解析、设备/序列号/增量来源匹配、包映射、真实 AOSP ZIP 查询和解压、命令准备、`Run_Update_Binary` 的 pipe/fork/协议/wait。只在 execve 边界将 update_engine 可执行文件替换为无害主机程序，原 argv 保留；它按真实 ZIP 偏移读取并逐字节验证 2052 字节临时 payload，检查 headers、fd 和进度，返回成功、退出 7 或非法协议，不做更新。

21 场景通过：stored payload、deflated properties、压缩/空/缺失 payload、损坏/空/缺失/含 NUL properties、残留命令清除、metadata 缺失/设备/序列号/来源增量/指纹/OTA类型不匹配、无效/缺失 ZIP、子进程失败/非法进度及空生成命令。所有拒绝场景检查 fork 次数为零；已启动子进程核对回收。修正前同组 8 场景失败，其余拒绝行为沿用原策略，不把全部 21 项记作新缺陷。普通 ZIP 安装 36 项回归通过。

范围：测试父进程和无害更新器均为主机执行；属性和进度为明确替身。未调用真实 update_engine、未运行原厂 OTA payload、未写分区，未包含完整 GUI/ARM64 Recovery/USB/FUSE/快照更新生命周期。原厂 OS2/OS3/OS4 的完整安装兼容仍未验收，整体 12 组任务保持进行中。

最终候选 `recovery-dijun-unified-ab-command.img`，SHA256 `704b58f5e97563ba9747bbf3c8d0129b83e1233581dec2941d837dfb704aceeb`。最终 installclean 后以 `make -j$(nproc)` 30 并发编译，保留 `XRING O1` 加载页显示与 0060 分区操作限制；六 profile 封装通过。本地报告 `logs/ab-command-delivery.json`，公开仓库发布源码/测试/文档与摘要，镜像及原始日志不上传。

<a id="sparse-image"></a>

## Sparse 镜像刷写的容量与完成检查

2026-11-12，按任务文档的安装/刷写验收要求检查真实 `TWPartition::FlashImage` → `IsSparseImage` → `FlashSparseImage`。旧实现只比较输入文件大小与缓存分区大小；sparse 的压缩大小不能限制其展开写入。临时文件实验中，44 字节的 FILL 镜像声明展开为65536字节，旧实现写入32768字节目标并返回成功。没有使用手机或物理块设备。

维护补丁 `0051-sparse-image-capacity-and-commit.patch` 在解析成功后检查实际展开长度，拒绝零长度及超出缓存容量的镜像；再对已打开目标执行 fstat 与 BLKGETSIZE64，拒绝普通文件、未知/零容量或展开越界。容量查询 EINTR 可重试。可选 discard 移到这些检查之后；sparse 对象通过 scope guard 释放。写完必须 fsync 成功且显式 close 成功才报告成功；fsync EINTR 重试，close 错误不重试已释放的描述符。

`tests/sparse_flash_test.py` 在主机编译原始三个生产方法，以及当前 AOSP libsparse 六个源文件和 libbase 的 mapped_file/stringprintf。没有用虚假的 sparse parser 或 writer。20种情况分别在默认配置和可选 discard 配置执行，共40项通过；旧实现同一测试40项中27项断言失败。正常、EINTR、短写均逐字节核对 RAW/FILL/DONT_CARE/RAW 输出和尾部未改内容；DONT_CARE保留已有数据，不承诺清零。越界、容量错误、格式错误和前置拒绝路径核对目标完全未改；第二次写入故障明确保留已经写入的第一块，并返回失败，不能称为回滚。同步/关闭错误即使完整字节已经可读也必须失败。

模拟边界：一个私有普通文件由 fstat/BLKGETSIZE64 描述为块设备，缓存容量发现为夹具；ftruncate模拟块设备拒绝截断。discard仅记录调用，不发送任何ioctl。实际读写、解析、映射、同步以及错误出口执行；没有运行 ARM64 刷写、PartitionManager/GUI 路由、槽位切换或USB。libsparse导入沿用现有 `crc=false`，本次没有新增CRC或内容真实性保证。当前编译未启用discard，不将可选配置检查扩展成设备支持声明。断电、移除中写入、完整ZIP/update-binary/sideload及GUI链路继续未完成。

证据为 `logs/sparse-flash.json`、`logs/sparse-flash-before.json`；raw传输既有65项回归保存为 `logs/sparse-flash-raw-regression.json`。交付镜像和构建/来源审计由后续同名交付报告记录；本页的软件检查不等于实机功能恢复。

<a id="sideload"></a>

## ADB sideload 子进程与取消生命周期

2026-11-12维护补丁0056修正原始侧载核心与GUI2 backend的进程所有权。USB切换失败时原路径直接返回并遗留子进程；GetMiniAdbdPid保留旧PID（fork失败为-1）；界面取消线程和核心均waitpid；SIGPIPE被全进程改为忽略并最终改回默认，覆盖原处理器。

当前实现由侧载核心统一负责SIGKILL和EINTR可重试的waitpid回收，所有已fork出口经过scope guard；PID只在子进程仍归owner所有时发布，回收前在锁内清零。界面仅设置取消标志，并在锁内请求所属会话socket shutdown/SIGTERM，不等待或sleep，也不对FUSE退出文件做可能阻塞的stat。取消早于fork由原子token检查兜底，旧token不能终止新会话；全局session互斥拒绝GUI/脚本重叠使用USB。GetMiniAdbdPid保留给现有脚本调用者，完成时返回0，不能用于外部无锁kill。

状态回复按完整8字节循环send，处理短写、EINTR、零写和错误，使用MSG_NOSIGNAL而非修改全进程SIGPIPE。命令解析要求精确8字节。EPOLLIN和HUP同时出现时先消费缓冲命令。USB SetProperty失败不再进入WaitForProperty；其他恢复语义保持原样。

离线测试tests/sideload_lifecycle_test.py/.cpp从实际源码取完整侧载核心、公开backend头和所有backend方法。实际执行私有socketpair、fork、exec（自身模拟minadbd子进程）、epoll、send、shutdown、kill、wait；系统调用边界注入错误并禁止非本测试子进程PID的信号。USB属性服务、FUSE stat、TWinstall_zip、MTP/缓存/DataManager/操作反馈为明确替身。SIGPIPE处理器、waitid/WNOWAIT确认已缓冲并关闭的peer、waitpid/ECHILD确认已回收均有独立断言。

33场景：安装成功/失败、FUSE缺失/EIO、socket/fork/exec/USB/property失败、wait EINTR、四类epoll失败/超时、错误/截断/未支持命令、重启命令返回、缓冲后关闭、取消、fork前取消、析构、重用、busy、其他token取消、SIGPIPE保留、断开peer回复、两种长度错误、回复EINTR/短写/零写/EIO。当前33通过；旧源码可比31场景29失败，两个正常完整回复测试仍通过。新send专用零写/EIO两项不对旧WriteFully路径注入，避免以未覆盖的边界制造失败；其结果只用于当前实现。多数旧路径共同失败于PID未清零和SIGPIPE处理器被覆盖，29不是29种独立缺陷。旧源码USB失败与wait EINTR另验证有未回收子进程，cancel另验证双wait；测试记录失败后只清理本夹具子进程。旧测试的其他token检查只在新API存在时执行，不能当作旧实现该项已比较。

当前镜像recovery-dijun-unified-sideload-lifecycle.img，SHA256 a5e16b92da91202527714049200ae23c35d13ed2e2d79f6327d55ed2f8afbde3；installclean及make -j$(nproc)30并发，758份来源，六份配置封装核对。镜像仅本地保留，不上传GitHub。

0056时未完成（后续0057进度见下文）：实际minadbd/ADB/FUSE/USB与ZIP updater接续，GUI完整页面交互，安装过程中同步TWinstall_zip或属性等待的有界取消，updater清缓存请求向外传递和缓存失败反馈，脚本路径重复安装及其收尾，重启请求向GUI统一重启入口传递、旧ADB版本错误的精确状态，以及真实USB恢复失败反馈。取消状态不承诺回滚已写内容；token只负责进程/传输退出，不能打断正在执行的同步安装器。保留全部12组整体目标，未连接设备。

同镜像profile9组/102阶段及module-state4组/24调用通过（模块/挂载/属性服务仍为夹具）。公共adb_install头变化使历史ZIP队列报告的来源绑定过期，使用logs/sideload-zip-queue-regression.json重跑23项，保留历史报告而非改写旧摘要。当前范围由scripts/audit_sideload_delivery.py核对。

### minadbd 重启交接

补丁0058让minadbd协议中的Android、bootloader、fastboot和recovery请求，在成功回复命令并成功恢复USB配置后才进入待交接状态。GUI backend在UI线程消费请求，等启动流程、后台命令及侧载worker空闲后，写入`tw_reboot_arg`并使用`twrp.cpp`的统一`Reboot()`路由。ORS不再在核心安装完成后重复刷包，收到重启结果时停止解析脚本，由同一GUI流程处理。

完成状态与running标志在同一mutex下发布，cancel也在该锁内检查状态，防止观察到DONE后的析构取消已经完成的交接。当前回归使用私有进程/socket fixture；最终竞态修复后19项通过，结果见`logs/sideload-reboot.json`，修复前同组15项失败。ACK失败、USB恢复失败、未支持目标、token取消和队列门控均覆盖。Rescue须设置BCB `boot-rescue`，没有映射为普通重启而是明确拒绝。属性、DataManager、sync和最终TwReboot为替身；未验证真实USB、Android minadbd、BCB、完整ORS进程或实体重启。

### 包安装与完成状态

补丁0057让原始AdbInstallPackageHandler把wipe_cache输出交给每个包的状态处理：TWinstall_zip返回后立即尝试/cache，wipe失败将包结果改为INSTALL_ERROR，再将失败状态回复minadbd。多条安装命令各自独立完成清理，未等到队列末尾；后续包请求不会覆盖之前包状态。updater即使返回失败，只要已报告wipe_cache，也仍执行缓存清理，因为其写入可能已经发生。

ORS实际sideload分支以前在twrp_sideload已经调用AdbInstallPackageHandler并安装包后，再次调用TWinstall_zip。补丁移除此重复执行与脚本的第二次cache处理，使用核心返回码，然后沿用核心socket服务和USB清理。GUI sideload页的用户选项清缓存、Dalvik仍是单独的清理操作；错误现在将backend结果设置失败。

新增tests/sideload_package_chain_test.py/.cpp及sideload_package_fixture.cpp。测试从实际AdbInstallPackageHandler/twrp_sideload/GUI backend和ORS分支，接入原始TWinstall_zip、ZIP映射与验证/提取、原始updater protocol/fork/exec、minadbd私有替身及真实8字节socket命令/状态。27场景当前通过、旧实现19失败，精确输入ZIP摘要映射相同。minadbd fixture在读取每次状态ACK之前数cache清理操作，以验证请求已在包确认前处理。涵盖单/多包、第一包wipe和后续包成功/失败、wipe自身失败、updater失败、进度错误、缺失updater、签名拒绝、GUI cache/Dalvik用户选项失败和ORS单次安装。

native minadbd、FUSE由私有chroot文件发布替身模拟；USB属性、mount/cache/Dalvik、DataManager、MTP、操作反馈均为fixture。真实USB端点、kernel FUSE、缓存文件系统、ARM updater、AB payload、GUI点击及设备均未运行。安装或清理失败不回滚已经发生的分区写入。
