> 历史技术记录：OS4 震动现已由用户确认正常，已解决，不属于当前排查或例行检查。以下旧状态只对应当时的记录。当前进度见 [工作队列](../../WORK-QUEUE.md)。

# FF能力查询中断处理

震动能力查询中断修正：补丁0043让已有FF描述符的只读能力查询遇EINTR/EAGAIN时保留描述符与缓存能力，等待下一轮查询；避免关闭触发input core清理效果，不做无限重试。ENODEV/EBADF仍关闭并重新探测。28项路由/6项后台FF通过，旧代码同组EINTR/EAGAIN两项失败；14项日志ABI通过，8种时长effect字节不变。installclean后make -j$(nproc)30并发构建recovery-dijun-unified-haptics-probe.img，SHA256 `e64e796370ad7983d27692ce22827ab03f72999e68881a1b4fe507247ec48f73`，732来源/封装核对通过；同镜像回放另记。现场没有能力查询EINTR证据，不能认定持续无震动根因或物理修复；设置现场及完整12组继续进行中。

复现：

```bash
python3 tests/haptics_route_test.py --report logs/haptics-probe-route.json
python3 tests/haptics_route_test.py --ff-source backups/haptics-probe-interrupt-pre-fix/twrpminui/force_feedback.cpp --report logs/haptics-probe-before.json
python3 tests/haptics_route_test.py --worker-io --report logs/haptics-probe-worker-ff.json
python3 tests/haptics_request_trace_test.py --route logs/haptics-probe-route.json --route-count 28 --worker-ff logs/haptics-probe-worker-ff.json --worker-count 6 --output logs/haptics-probe-trace-abi.json
python3 scripts/audit_haptics_probe_delivery.py
```

四项新增场景先上传播放500ms效果，随后能力查询持续三次EINTR/EAGAIN：断言查询次数恰好三次、无close/erase/新增上传播放；错误解除后下一请求仍先擦除同一旧效果。ENODEV/EBADF场景明确检查旧描述符关闭一次并重新探测，不产生额外播放。ioctl和write为主机替身，500ms是参数不是测得的电机时长；没有真实信号或内核输入core执行。只有只读查询可保留缓存，上传/播放失败仍沿用既有错误处理，不自动重复请求。

持续EINTR/EAGAIN时暂时继续报告缓存能力，可能延迟发现设备消失；后续正常查询或播放失败仍进入原清理流程。初次设备枚举查询失败不会发布新能力。上游input FF close清理机制另有独立证据，但本次没有证明现场发生过这个故障，也没有改变波形/幅度/增益/校准/保护。

另两项实际owner线程检查以500ms周期执行三次EINTR/EAGAIN能力轮询，期间无关闭、擦除或额外播放，只有stop后才关闭一次；工作线程与主线程以原子状态交互。没有时间加速或手动调用轮询代替后台生命周期。

根因边界：本次没有向真实evdev发送信号，也未证明vendor EVIOCGBIT分支在当前环境会返回EINTR/EAGAIN；这是错误注入证明的防御性所有权修正。已有43次现场完成消息也不包含能力查询结果，因此不能把这一修正解释成持续无震动的已定位根因。所有实机恢复结论继续未验证。


FF查询中断交付收尾：同镜像六版本双槽9组/102次阶段调用通过，732来源、维护文件79+1+3重建一致且0待更新；与f31bbe13候选只有FF库字节改变。28路由/6后台FF/14日志ABI及旧查询2失败对照完成，当前审计logs/haptics-probe-delivery.json。没有实机查询中断或电机恢复证据，物理无震动、现场设置及完整12组仍未完成。
