# 镜像路由与 ZIP 安装链离线验收

2026-11-13 A/B命令修正：0062 将payload_properties提取失败从成功码改为INSTALL_CORRUPT，拒绝空/NUL headers、压缩/空/越界payload，fork前防御空执行命令。真实ZIP/原命令与pipe/fork/wait接续21项通过，旧版同组8失败，普通ZIP36项回归通过。无害主机程序替代更新器，不执行真实OTA。installclean后30并发构建ab-command候选，SHA256 704b58f5e97563ba9747bbf3c8d0129b83e1233581dec2941d837dfb704aceeb，六profile封装通过；继承XRING O1及NV限制。见docs/AB-COMMAND-VALIDATION.md，完整12组保持进行中，源码文档同步GitHub、编译文件不上传。

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
