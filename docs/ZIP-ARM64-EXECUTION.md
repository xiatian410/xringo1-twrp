# ZIP 安装链中的真实 ARM64 测试 updater

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
