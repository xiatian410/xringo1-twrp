> 历史技术记录：OS4 震动现已由用户确认正常，已解决，不属于当前排查或例行检查。以下旧状态只对应当时的记录。当前进度见 [工作队列](WORK-QUEUE.md)。

# GUI 震动后台执行与资源回收

2026-11-11，当前统一候选为 `recovery-dijun-unified-haptics-worker.img`（历史文件当前缺失）。本轮修正已确认的同步设备调用路径，没有连接手机，也没有确认物理震动恢复。原厂初始化与效果模拟的范围见[生命周期记录](HAPTICS-LIFECYCLE-EMULATION.md)。

## 修改原因与行为

原先 GUI 按钮、键盘及硬件设置通过 `twrp_hardware_settings` 同步探测能力并调用 minui。FF 在新请求前擦除旧效果；原厂擦除 worker 可能等待“效果时长 + 500 ms”。即使只查询能力，也可能等待同一把 FF 锁。

[0027 补丁](../dtsrc/O1_asic_dual/patches/0027-gui-haptics-worker.patch)新增 `haptics_controller`，由 recovery main 创建并显式交给 GUI 硬件 backend。设备探测、播放与 FF 描述符释放都由它的单一 worker 执行，GUI 提交请求时不等待设备 I/O。非 GUI 操作完成调用者已在业务 worker 中运行，继续保留同步返回路径；不会为每次操作创建额外线程。

待办最多一条，后到的反馈替代尚未开始的旧反馈；等待超过 250 ms 的待办丢弃，避免阻塞解除后补播过时点击。已经开始的请求不会被强行中断。后台空闲时每 500 ms 刷新能力；正在执行的设备 I/O 会推迟刷新，界面读取缓存；初始化尚未探测完成或设备消失时入口可能暂时不可见，重新进入设置可读取最新状态。此缓存属于软件能力检测，不代表电机实际有输出。

设备请求失败时记录诊断，并设置可消费的错误状态。GUI 主循环读取该状态，使用现有本地化硬件错误文案显示；后台不访问 LVGL。多次失败可合并为一次提示，不把请求已接受当成硬件播放成功。

GUI 退出在销毁图形资源之前调用 `stop_haptics()`：禁止新请求、丢弃待办、等待已开始 I/O 返回、由 worker 关闭 FF 描述符，再 join。main 在 GUI 初始化失败或正常返回后也执行 stop，析构重复 stop 安全；并发 stop 的 join 被串行化。没有 detached worker。关闭描述符后的实际内核效果释放由 input core 负责，本轮没有模拟 input core。

**退出仍可能等待内核 I/O。** 不可返回的内核调用不能由 C++ 线程安全强杀；本改动没有提供退出墙钟上限，也没有证明永久阻塞时可及时退出。已有非 GUI 业务 worker 可与 GUI worker 竞争 minui 的 FF 锁；GUI 方法不持有该锁，但后台反馈与退出时间仍受其影响。

## 主机回归

[16 项报告](../logs/haptics-worker.json)、[执行日志](../logs/haptics-worker.log)编译实际控制器、实际硬件 backend 与生产接口头，以真实线程运行。probe/play/release 是设备边界替身；测试保持设备回调门闩关闭，再要求 GUI 方法完成，证明它们不依赖该 I/O 返回。ASan/UBSan 启用。

- 探测和播放阻塞时，能力查询、提交、设置与错误轮询仍返回。
- 5000 次连续请求仅保留最新待办；过期请求丢弃。
- 正在探测/播放时 stop 等待门闩，解除后正确 join；队列丢弃、并发及重复 stop、释放一次。
- 失败提示只消费一次，失败后可恢复；设备初始缺失、晚注册、拔除与恢复。
- 三通道时长、禁用、零时长、非法时长及 stop 后请求拒绝。

这些场景没有执行真实 ioctl、内核调度或电机；原有实际 backend→minui router→FF 的 22 项 ioctl 替身测试、21 项实际 LVGL 控件回放、64 项完成反馈回归在当前源码上通过。原厂驱动 120 项与生命周期 90 项也更新了当前 FF 源码绑定；它们不能合并称为完整硬件验收。

另有[4 项生产 FF 联调](../logs/haptics-worker-ff.json)：实际控制器→硬件 backend→minui 路由→FF 代码执行，`EVIOCRMFF` 被门闩阻塞时查询与 5000 次提交仍完成；stop 丢弃待办、等待已开始请求完成后关闭描述符。上传/播放错误进入后台错误状态且没有转投 LED；重复 stop 不重复关闭。ioctl/属性/设备文件仍是替身，不执行内核 input core。该套件与原有 22 项路由共用[夹具](../tests/haptics_route_test.cpp)。

## 构建与同镜像证据

已按 `make -j$(nproc) installclean`、`make -j$(nproc) recoveryimage` 执行最终构建，30 并发。[构建日志](../logs/build-haptics-worker-final.log)、`镜像检查`（历史文件当前缺失）、`707 份来源指纹`（历史文件当前缺失）保留。

镜像 SHA-256：`d25a4b8a7324af6daa451c52417193a4a77ba7f3e3df5a62d00084b32ed90c30`。总大小 104,857,600 B，压缩 ramdisk 76,626,119 B，封装/填充预算 28,225,536 B，六套 profile 与 78 个去重 blob。

同镜像[启动脚本回放](../logs/haptics-worker-profile-runtime.json)完成六包两槽位及失败场景 77 次阶段调用；[init 检查](../logs/haptics-worker-init-verification.json)、[12 项基础策略](../logs/haptics-worker-policy-regression.json)、[53 项 USB 策略](../logs/haptics-worker-helper-policy.json)通过。以上为离线检查，不替代内核启动、TEE、USB 或电机验证。

## 复现与后续

```bash
python3 tests/haptics_worker_test.py
python3 tests/haptics_route_test.py
python3 tests/haptics_route_test.py --worker-io --report logs/haptics-worker-ff.json
python3 tests/haptics_ui_test.py
python3 tests/operation_feedback_test.py
python3 scripts/audit_unified_delivery.py
```

完整电源/复位/固件 probe、start/stop worker、IRQ、真实 input core/workqueue 与整页 GUI 业务仍待补齐。物理电机保持 U，继续仅使用固件与主机模拟推进。

后续触摸顺序候选为 `recovery-dijun-unified-module-state.img`，详见[触摸排查](OS4-TOUCH-FAILURE.md)。本页 worker 构建与证据保留为历史，不代表触摸已经恢复。
