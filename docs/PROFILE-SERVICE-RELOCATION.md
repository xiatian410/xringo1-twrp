# 六份固件安全服务本体的 ARM64 重定位

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
