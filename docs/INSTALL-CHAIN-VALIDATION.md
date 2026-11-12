# 镜像路由与 ZIP 安装链离线验收

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
