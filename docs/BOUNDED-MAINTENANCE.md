# 第6、7、8、10、11、12组有限维护

2026-11-13 用户指定当前仅维护这些组，并补查刷新页生命周期、解决中央摄像头遮挡温度。其他组不在本轮扩展范围；历史12组未闭环清单保留，不据本批宣称全部适配完成。OS4震动正常确认不变。

## 生产修正

| 组 | 本批结果 |
|---|---|
| 6 文件系统工具 | 0063修正ext Resize预留长度的符号溢出/无符号下溢；按实际字节先扣预留再向下取KiB，拒绝预留超过容量、正长度超过容量及不足1KiB的结果。保留先Repair再Resize的行为。 |
| 7 RTC | 当前28项状态读取/时钟失败回归通过。六份原厂RTC回调56项的相关来源未变，直接复用；未增加任意偏移或修改原厂模块。冷启动/hctosys、实际漂移仍未验收。 |
| 8 视频 | 原录屏故障恢复6场景和12.5秒多Cluster/关键帧时间轴3组的全部绑定来源仍一致，复用结果。检查显示shadow/present入口、停止/join/错误返回，无本批已复现的新缺陷，不改codec。ARM64实际codec、全分辨率性能、小时级稳定性仍未验收。 |
| 10 启动/逻辑分区 | 新镜像原始init文件经host_init_verifier检查，重新进行该镜像profile激活脚本有限回放；配置/挂载/属性/模块/Binder为显式边界。这不是完整内核/init/LP启动。 |
| 11 温度 | 0063将温度紧接时间/录屏标记，且限定在屏幕左半区内，中央留空；空间不足隐藏，不覆盖其他文字。动态读数和电量来源不变。 |
| 12 OTA/A/B与GUI | 0064为ApplyPayload传入有效Error对象；同步拒绝时直接返回具体错误，未设置错误时回退kError，不再进入不会收到完成通知的事件循环。 |

0063为Recovery补丁；0064将system/update_engine基线a4c7444f722bada4e3880a5e38b42b9aa4ee37a4纳入维护系列。两者均由series.json重建核对，不改AVB/vbmeta。有限检查只操作临时普通文件，没有代理设备操作。

## 定向验证与范围

- 温度11场景通过，修正前同组10项违反位置断言；覆盖12/24小时、电量隐藏、Wi-Fi/录屏、不同宽度和主题。实际LVGL/provider/controller执行，字体/读数/显示flush为替身。温度不进入中央区域；不是测量开孔几何或实机验收。
- 扩容16场景通过，修正前7失败；按真实`int length_`测试INT_MIN、等于/超过容量、字节取整、容量缺失、工具缺失/失败。生成命令只记录，不运行resize工具。原Repair的146个返回码断言回归通过。
- OTA同步拒绝7场景通过，修正前4失败；原始header解析/错误出版方法和原ApplyUpdatePayload执行。错误格式和重复headers在旧实现触发空Error解引用；其他同步拒绝错误地进入loop。服务、调度和loop明确替代，尚未执行真实payload写入或快照更新。
- 刷新页生命周期三种调度通过，包括8次重入，执行原worker/progress适配、实际page_host/scaffold/router/PUSH/POP/完成按钮。确认终态更新、动作显示、返回、删除和无孤立控件。路由组装、tick、扫描和显示为替身，不是完整Android GUI/DRM。

刷新现场仍为“日志约5.15秒完成，画面未结束”；有限生命周期检查没有复现根因，因此没有增加所谓刷新卡死修复。现有运行文字可能是历史console行，仍需实际画面才能判别。调查见[刷新页说明](REFRESH-STUCK-INVESTIGATION.md)。

## 本批交付

`imgs/built/recovery-dijun-unified-bounded-maintenance.img`

SHA256 `218c5edd28c4e458464fc035a73b68808b016598c51e50877b2c0a1b055da3c3`

最终`installclean`后使用`make -j$(nproc)`30并发构建，775份来源绑定；保留XRING O1加载页及NV/OTG修正。原始update_engine_sideload与libgui2均实际重新编译、链接、安装。六profile封装与新二进制核对通过。源码、测试、配置和文档同步GitHub，镜像、编译文件和原始设备日志不上传。

本地定向交付核对入口：`scripts/audit_bounded_maintenance.py`。本轮有限维护交付不等于原有全部12组或上述六组的所有硬件边界完成；不继续无限增加同类模拟。
