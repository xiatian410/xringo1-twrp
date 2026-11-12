# 安全服务运行时库搜索配置

2026-11-12，在[服务本体重定位](PROFILE-SERVICE-RELOCATION.md)基础上，新增对实际linker namespace内存的读取。仍使用当前镜像原始ARM64 linker与六profile原厂服务，停在构造函数前，不执行Binder/TEE/main。

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
