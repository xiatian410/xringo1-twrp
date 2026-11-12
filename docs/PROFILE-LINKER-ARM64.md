# 六版本安全服务依赖与 ARM64 linker 执行

2026-11-12更新：当前镜像新增[服务本体重定位检查](PROFILE-SERVICE-RELOCATION.md)，18个原厂服务加载停在构造函数前、6项缺符号和6项缺库检查通过；补上此处历史测试未执行的服务本体符号重定位。仍不证明完整init namespace、服务注册或解密。以下保留当时镜像和`--list`证据范围。

本轮使用 Android 原始构建输出 `/root/AAA/twrp/out/target/product/O1_asic/recovery.img`，SHA-256 `c282f535b1fdac6f5eafe25ca46116441195affe9d67f4511178a930634c4346`。`imgs/built/recovery-dijun-unified-module-state.img` 当前缺失，没有复制、重命名另一份候选，也没有新构建。测试通过不证明交付目录已恢复。

执行 `python3 tests/profile_linker_arm64_test.py --image /root/AAA/twrp/out/target/product/O1_asic/recovery.img`，得到 [机器报告](../logs/profile-linker-arm64.json)与[运行日志](../logs/profile-linker-arm64.log)。从镜像 cpio 直接提取 linker、Recovery 根目录库和六份 runtime-files/CAS；临时目录只写所需普通文件，验证 CAS 哈希，没有运行设备命令或访问真实输入/块设备。

QEMU 用户态运行实际 ARM64 linker，对每个 profile 的 tee-supplicant、keymint、gatekeeper 使用 `--list`，共18项。逐项确认列出的库位于临时 profile/Recovery 路径；profile 内有同名库时要求选用 profile 库。OS2/OS3 的 tee/keymint/gatekeeper 依赖数为6/31/19，OS4为9/32/19，不含QEMU vDSO。每个 profile 再移除私有 libteecli.so，tee-supplicant的依赖检查必须失败，共6项负向检查。

**18项依赖加载成功不证明安全服务的符号重定位成功。** 当前 bionic `linker_relocate.cpp` 的 `soinfo::relocate` 在 `g_is_ldd` 时直接返回，`linker_main.cpp` 同时跳过构造函数与主程序。测试没有启动这些服务的构造函数、main、Binder 或 TEE，也没有验证真实 MiTEE 路径检查、服务注册或密钥操作。

另用现有 Recovery CRT/libc 编译两个独立 ARM64 动态小程序，并用同一镜像 linker 执行4项对照：

| 程序 | --list | 正常加载执行 |
| --- | --- | --- |
| 有构造函数和 write 调用 | 成功 | 构造函数设置状态后 main 输出精确标记，成功 |
| 引用不存在符号 | 同样成功 | linker以 cannot locate symbol 拒绝 |

这4项证明同一环境可以执行实际动态重定位、构造函数和main，也明确展示`--list`的边界；不能把小程序的重定位结果套用到安全服务。编译器、linker、CRT、QEMU、测试源码、镜像内所有使用文件和bionic参考源码均记录哈希。目标使用android35编译，复用现有Recovery CRT产物，不是完整Android重编译。

QEMU `-L` 和绝对 `LD_LIBRARY_PATH` 是测试用路径替换。日志保留缺少 `/linkerconfig/ld.config.txt` 的警告，使用默认 namespace fallback；没有证明 init 下真实 namespace 或 vendor隔离配置。仍待完成：服务本体完整符号重定位而不进入硬件初始化、精确运行时 namespace、合成加密卷与密钥协议。触摸 P0、震动以及完整适配目标继续未完成。
