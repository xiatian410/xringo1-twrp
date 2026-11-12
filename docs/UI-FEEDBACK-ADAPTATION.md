# GUI2 反馈次数与取消操作的离线验证

日期：2026-11-11。最新候选与校验和见[模拟报告](../simulation-report.md)。本记录补充[震动调用链](HAPTICS-ADAPTATION.md)，不证明实际电机已经恢复。

## 发现与修正

实际 `accept_click()` 会提交 BUTTON 反馈；五个业务回调又各提交一次：取消 sideload、文件排序、取消安装后倒计时、取消备份、选择转换文件系统。原实现一次点击产生两次震动请求，两个正常点击产生四次。对应 FF 后端会清理上一效果并重新上传，这与实机体感之间仍缺硬件证据。

[0014 补丁](../dtsrc/O1_asic_dual/0014-ui-feedback-and-cancel.patch)移除这五个重复调用，保留公共点击检查的反馈。VALUE_CHANGED 开关、键盘和滑动确认各有独立入口，没有批量删除其反馈。

实际 LVGL 指针回放还暴露两处取消错误：

- 键盘按钮没有接入按下移出取消逻辑。拖出后释放仍会输入并触发反馈。现在复用点击检查，但关闭其默认 BUTTON 反馈；实际输入被接受后，键盘自己的回调只发一次 KEYBOARD 反馈。
- 确认滑块在拖动中被禁用后，RELEASED 仍可能确认；成功后额外收到 RELEASED 也会重复确认。现在只有正在进行的拖动能结束，禁用中的拖动复位到起点；重新启用后仍可正常完成一次。

上述回调的业务边界由替身接收；验证过程没有开始侧载、取消真实备份或转换任何分区。

## 实际运行范围

[Python 驱动](../tests/haptics_ui_test.py)和[C++ 夹具](../tests/haptics_ui_test.cpp)采用：

- 原 `external/lvgl/Android.bp` 所列源文件与实际 `gui2/lv_conf.h`；按内容指纹缓存主机静态库，以 `make -j$(nproc)` 构建。主机自然使用非 ARM NEON 分支。
- 实际 LVGL display、pointer indev、事件分发与软件绘制，向 480×960 内存 framebuffer 输出。
- 实际 GUI2 公共按钮、键盘、确认滑块、点击取消检查、布局辅助函数、SVG 缓存和箭头资源。
- 从实际 `gui2.cpp` 提取五个业务回调、键盘反馈回调和侧载开关回调，保留原函数体。
- 设置与业务 backend、震动硬件接收端替身。GUI2 C++ 部分启用 UBSan；LVGL/ThorVG 库采用普通主机编译，没有把整个依赖库称为 sanitizer 验证。

从指针读取回放正常操作；PRESS_LOST 与额外 RELEASED 用真实 LVGL 事件接口注入，作为异常顺序检查。没有直接操作控件私有状态来代替其生产回调。

## 结果

[当前报告](../logs/haptics-ui.json)：21 场景通过；[同组修改前报告](../logs/haptics-ui-before.json)：11 场景失败。
报告记录生产源码、头文件、测试源码、LVGL 全部参与文件、配置、编译器、静态库与截图哈希。

| 场景组 | 场景数 | 预期 |
|---|---:|---|
| 五个重复反馈回调 | 5 | 一次有效点击，一次 BUTTON 请求，业务回调仍执行 |
| 连续点击与取消 | 5 | 两次点击保留两次；拖出、拖回、PRESS_LOST 不操作；无硬件对象不影响业务 |
| VALUE_CHANGED 开关 | 1 | 一次变更，一次 BUTTON 请求 |
| 实际数字键盘 | 5 | 一次输入一次 KEYBOARD；拖出/拖回取消，禁用 PIN 字段不输入，连续两键不丢失 |
| 实际确认滑块 | 5 | 完整滑动确认一次；未到终点、禁用或重复松手不确认；重新启用可用 |

全部场景实际产生非空 framebuffer。已检查两份夹具截图：[数字键盘](../logs/haptics-ui-frames/keyboard.png)、[确认滑块](../logs/haptics-ui-frames/swipe-complete.png)。它们是组件夹具截图，未展示完整手机页面；没有据此宣称全界面布局已经验收。

`gui2.cpp` 其他多用户入口回归也重新执行，结果见[报告](../logs/ui-feedback-multiuser-routes.json)。

## 边界与后续

本轮证明这些组件的事件顺序和软件反馈次数。它没有启动完整 Android recovery，没有执行 DRM、原厂驱动、TEE 或真实电机。主机截图使用内置字体，未证明设备字体、完整页面布局、所有确认页或物理输入时序。

操作完成反馈的备份/恢复/ZIP 生产调用者现有[独立 64 项回放](OPERATION-FEEDBACK-ADAPTATION.md)。还需覆盖其余页面事件路由、完整页面截图，以及目标文档中的备份/恢复、OTG、合成卷等功能。此前 22 场景验证的“设置 backend→通用震动路由→FF”与此处事件验证互补；没有把两组拼接说成一次真实硬件调用。
