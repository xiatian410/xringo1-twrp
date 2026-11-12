# 安全服务组合、加载与 ARM64 运行时验证

六份固件的安全服务依次验证依赖查找、服务本体重定位与 namespace 配置。下列镜像、数量及状态属于各阶段的历史输入；当前候选和剩余边界以 [交付报告](../simulation-report.md) 与 [工作队列](WORK-QUEUE.md) 为准。三个阶段均不等于服务启动或解密验收。

## 依赖查找

本轮使用 Android 原始构建输出 `/root/AAA/twrp/out/target/product/O1_asic/recovery.img`，SHA-256 `c282f535b1fdac6f5eafe25ca46116441195affe9d67f4511178a930634c4346`。`imgs/built/recovery-dijun-unified-module-state.img` 当时缺失，没有复制、重命名另一份候选，也没有新构建。测试通过不证明交付目录已恢复。

执行 `python3 tests/profile_linker_arm64_test.py --image /root/AAA/twrp/out/target/product/O1_asic/recovery.img`，得到 [机器报告](../logs/profile-linker-arm64.json)与[运行日志](../logs/profile-linker-arm64.log)。从镜像 cpio 直接提取 linker、Recovery 根目录库和六份 runtime-files/CAS；临时目录只写所需普通文件，验证 CAS 哈希，没有运行设备命令或访问真实输入/块设备。

QEMU 用户态运行实际 ARM64 linker，对每个 profile 的 tee-supplicant、keymint、gatekeeper 使用 `--list`，共18项。逐项确认列出的库位于临时 profile/Recovery 路径；profile 内有同名库时要求选用 profile 库。OS2/OS3 的 tee/keymint/gatekeeper 依赖数为6/31/19，OS4为9/32/19，不含QEMU vDSO。每个 profile 再移除私有 libteecli.so，tee-supplicant的依赖检查必须失败，共6项负向检查。

**18项依赖加载成功不证明安全服务的符号重定位成功。** 该次使用的 bionic `linker_relocate.cpp` 的 `soinfo::relocate` 在 `g_is_ldd` 时直接返回，`linker_main.cpp` 同时跳过构造函数与主程序。测试没有启动这些服务的构造函数、main、Binder 或 TEE，也没有验证真实 MiTEE 路径检查、服务注册或密钥操作。

另用现有 Recovery CRT/libc 编译两个独立 ARM64 动态小程序，并用同一镜像 linker 执行4项对照：

| 程序 | --list | 正常加载执行 |
| --- | --- | --- |
| 有构造函数和 write 调用 | 成功 | 构造函数设置状态后 main 输出精确标记，成功 |
| 引用不存在符号 | 同样成功 | linker以 cannot locate symbol 拒绝 |

这4项证明同一环境可以执行实际动态重定位、构造函数和main，也明确展示`--list`的边界；不能把小程序的重定位结果套用到安全服务。编译器、linker、CRT、QEMU、测试源码、镜像内所有使用文件和bionic参考源码均记录哈希。目标使用android35编译，复用现有Recovery CRT产物，不是完整Android重编译。

QEMU `-L` 和绝对 `LD_LIBRARY_PATH` 是测试用路径替换。日志保留缺少 `/linkerconfig/ld.config.txt` 的警告，使用默认 namespace fallback；没有证明 init 下真实 namespace 或 vendor隔离配置。该阶段尚未覆盖服务本体重定位和运行时 namespace；下文记录后续补充范围。服务初始化和密钥协议仍未完成。

## 服务本体重定位

此前`--list`的18项成功只证明依赖查找：bionic在该模式跳过重定位、构造函数和main。本次执行六份固件的原厂tee-supplicant、KeyMint与Gatekeeper，共18个真实服务加载过程，补上服务本体符号重定位证据。

从当前`recovery-dijun-unified-mtp-directory.img`直接读取linker、公共库、六份runtime-files及CAS原始ELF字节。每个profile在独立临时chroot中使用与init一致的`/vendor/bin/...`、`/system/lib64/mitee`和`LD_LIBRARY_PATH`，并包含镜像原始`/system/etc/ld.config.txt`。QEMU执行原始ARM64 linker；其GDB远程协议仅设置一个执行断点，停止在调用主程序`call_pre_init_constructors`的BL指令之前，核对实际PC与`g_is_ldd=0`。没有替换重定位实现、返回值或服务代码，也不进入服务构造函数/main。

断点通过当前未剥离linker符号与反汇编推导，不按猜测写死；未剥离linker的所有可执行和可写PT_LOAD内容逐字节匹配镜像linker后才使用符号。已剥离版本的ELF头/符号表与未剥离文件不同，因此不将整个文件哈希相同作为前提。读原始`r_debug/link_map`确认实际加载对象，每份文件哈希回溯镜像库或该profile CAS；有私有同名库时必须使用私有版本。

另外每个profile有两项独立负向检查：移除私有libteecli必须缺库失败；只在负向检查的临时tee副本中将未定义符号`dump_buffer`等长改为`bad_missing`，必须由真实linker报缺符号失败。原厂18项正向执行保持精确CAS字节。负向副本不打包、不发布、不替换生产文件。合计30项通过。

```bash
python3 tests/profile_service_relocation_test.py
python3 scripts/audit_profile_service_relocation.py
```

报告为本地`logs/profile-service-relocation.json`与`logs/profile-service-relocation-audit.json`；公开摘要在`docs/CURRENT-VALIDATION.json`。本轮只新增测试/审计/文档，没有生产修改或新构建。镜像仍为`recovery-dijun-unified-mtp-directory.img`，SHA256 `215914df1f8768bf00272f5c10c03b90fa8e624e9b1337fa6801a0ef3e5155b0`，765项来源保持一致。

这不证明服务启动或解密完成：linker自身初始化及IFUNC解析可以执行，但服务构造函数、main、Binder、TEE、TA和密钥操作均未执行。chroot没有真实proc挂载或Android属性区；保留realpath和生成linkerconfig缺失警告。原始ld.config文件存在、目标路径一致，不足以证明完整init/APEX/namespace运行时。精确namespace、合成加密卷和硬件密钥语义仍未完成，完整12组目标保持进行中。OS4震动调用沿用用户正常确认，不作为本轮排查项。

## 运行时库搜索配置

2026-11-12，在上述服务本体重定位基础上，新增对实际linker namespace内存的读取。仍使用当前镜像原始ARM64 linker与六profile原厂服务，停在构造函数前，不执行Binder/TEE/main。

脚本从与镜像执行/可写PT_LOAD字节相同的未剥离linker的DWARF提取`android_namespace_t`成员偏移，再经QEMU调试协议读取默认namespace的名称、隔离标志、环境搜索路径、默认搜索路径和允许路径。字符串/vector解码针对该构建的ARM64 libc++布局，所有内容都有有界长度检查；没有调用目标getter或替换配置读取结果。

六profile各三个原厂服务的观察一致：

| 属性 | 运行时值 |
| --- | --- |
| namespace名称 | `(default)` |
| isolated | false，与镜像配置一致 |
| LD_LIBRARY_PATH | `/system/lib64/mitee`、`/system/lib64` |
| 默认搜索路径 | `/system/lib64/bootstrap`、`/system/lib64` |
| permitted paths | 空 |

bootstrap目录由原始bootstrap linker的`fix_lib_paths`插入，不能只按配置文本预期单个system路径。原先测试的预期因此失败，核对原始实现后修正测试；没有更改生产路径。

为每个profile增加两个配置消费对照，使用tee-supplicant：删除临时chroot中的配置，默认路径实际扩展为bootstrap/system/odm/vendor；在私有配置的搜索路径中加入已创建的`/namespace-proof`目录，内存中出现该路径。最初未创建标记目录时，原始路径解析器丢弃不存在目录，因此检查失败；保存本地`logs/profile-service-namespace-missing-marker.log`，修正夹具后再运行。这些对照证明已采用配置，不能仅凭原配置和fallback同为不隔离就下结论。

`--namespace`共42项：18个原厂服务、12个配置对照、6个缺符号副本和6个缺库拒绝；默认30项重定位回归另行运行。配置改写与缺符号副本都只发生在私有chroot，不进入生产镜像或公开二进制。

```bash
python3 tests/profile_service_relocation_test.py --namespace
python3 tests/profile_service_relocation_test.py
python3 scripts/audit_profile_service_relocation.py --namespace
python3 scripts/audit_profile_service_relocation.py
```

本地报告为`logs/profile-service-namespace.json`与对应`-audit.json`，公开摘要在`docs/CURRENT-VALIDATION.json`。生产代码未修改，沿用mtp-directory镜像`215914df1f8768bf00272f5c10c03b90fa8e624e9b1337fa6801a0ef3e5155b0`、765来源，本轮无新构建。

本证据确认私有chroot中该构建、该文件布局下的实际namespace配置；它不证明真实init、mount namespace、APEX、Android属性区或proc realpath行为。生成linkerconfig缺失警告仍保留，不能据此称配置未使用，也不能据测试成功称完整启动通过。服务初始化、TEE/硬件密钥和合成加密卷仍待完成，完整12组目标继续进行中；OS4震动调用正常确认保持。

## MiTEE 静态组合比较

本节保留 profile 建立阶段的静态结果；后续重定位与 namespace 范围见上文，不将静态结果等同于服务启动或解密验收。

服务、TA、私有库按原厂来源整理；本表记录静态依赖；多版本启动已接入统一候选，未执行真实解密。

| 样本 | system release / SPL | vendor SPL | 私有 DSO 数 | 静态 ELF 结果 |
|---|---|---|---:|---|
| os2-final | 15/2025-08-01 | 2025-08-01 | 24 | S1 dependency/symbol checks passed |
| os2-initial | 15/2025-04-01 | 2025-03-01 | 24 | S1 dependency/symbol checks passed |
| os3-final | 16/2026-09-01 | 2026-09-01 | 24 | S1 dependency/symbol checks passed |
| os3-initial | 16/2025-09-01 | 2025-09-01 | 24 | S1 dependency/symbol checks passed |
| os4-current | 17/2026-09-01 | 2026-09-01 | 26 | S1 dependency/symbol checks passed |
| os4-stable | 17/2026-10-01 | 2026-09-01 | 26 | S1 dependency/symbol checks passed |

OS3 初末版的 41 个安全服务/TA/私有库资产中，40 个字节一致，但一个 TA 不同，系统与 vendor 的 SPL 也不同；仍保留独立档案。OS4 还更换了 tee-supplicant、KeyMint、libteecli 及多项 TA。

OS2 初版 system SPL 为 2025-04-01，vendor SPL 为 2025-03-01，必须分别保留。OS3 的 vendor/ODM 构建 release 仍为 Android 15，不能拿它替代 system 的 Android 16 身份。

DSO 依赖比较采用当前 recovery 配套的 libbinder/libbinder_ndk；其余优先匹配 vendor 私有库，再检查 recovery 共享库。每个进程闭包的强符号差集为零时只记 S1，实际 namespace/服务启动/硬件密钥仍待验证。

[机器报告](crypto-compatibility.json) 保留全部源路径、SHA-256、依赖与符号结果。
[档案清单](../dtsrc/O1_asic_dual/profiles/inventory.json) 下的 profiles 与 content-addressed blobs 已接入 PRODUCT_COPY_FILES；实际镜像脚本模拟见 [启动说明](PROFILE-SELECTION.md)，不等于真实 TEE 成功。

同名 firmware 不自动去重：原厂 ODM 的 cs40l26-a2h.bin、cs40l26-dbc.bin 与 vendor 内容不同，保留两份原路径。ODM 中的触摸固件保留原路径记录，并将其与优先的 ODM Cirrus 固件映射到稳定 RAM 目录 `/lib/firmware`；统一候选在加载匹配的额外模块之前发布该 profile 的固件。

六个档案的资源按内容去重后为 78 份、40,184,830 B；实际压缩镜像容量已单独检查，见 [模拟报告](../simulation-report.md)。

六份 system/build.prop 的 release/SPL 现已从经过分区哈希检查的原文件取得，与 OTA 元数据一致；报告保留文件哈希和全部属性。只读选择组件的 77 场景结果见 [预检说明](PROFILE-SELECTION.md)，HAL 激活和服务启动顺序已接入，实际镜像的 77 次阶段调用通过模拟；后续真实硬件密钥操作仍未验证。

正式版独立使用新 tee-supplicant 和一项 TA，26 个私有 DSO 与旧 OS4 相同。system/vendor SPL 分别为 2026-10-01/2026-09-01，保留原身份。完整差异见[正式版记录](OS4-STABLE-ADAPTATION.md)。
