# 震动用户态请求诊断

震动生产请求诊断补齐：维护补丁0040在后台owner记录begin/end/expired、请求序号/时长/队龄/替换计数/耗时，在FF层记录实际type/waveform/period/magnitude和擦除/上传/播放/close的开始结束、实际返回值、独立保存的errno、单调时间与PID/TID。提交入口不执行日志I/O；周期能力probe正常不打日志。GUI与FF序号是不同空间，只能结合线程/时间定位，不能认定跨调用者严格关联。日志可能拖慢worker，不提供阻塞输出的实时保证；accepted仅系统调用边界，不等于电机。24项路由/4项后台FF/16项owner/14项日志ABI核对通过，8种时长effect字节与旧捕获一致。新增擦除失败和短写模拟；短写不再误报旧errno。installclean后make -j$(nproc)30并发新候选recovery-dijun-unified-haptics-request-trace.img，SHA256 `610f4acc2534cbd3fdd95f6733257efa52329435569df5230c4ea1a9c3326a8d`，726来源与封装/新二进制核对通过；同镜像profile另记。未改波形、幅度、增益、校准或触发实机操作，震动与完整12组仍未完成。

现有现场日志证明43次SINE上传/start/mailbox完成，但没有对应用户态调用者或GUI动作。此次仅补证据入口，不用额外成功模拟解释电机静音，也不默认要求用户重刷或再测。

日志均进入现有Recovery标准日志：

```text
GUI2 haptics: request=1 phase=begin duration_ms=80 age_ms=0 replaced=0 monotonic_ms=...
FF haptics: request=1 type=81 waveform=90 period_ms=8 magnitude=64 cirrus=1
FF haptics: request=1 phase=upload-begin ... pid=... tid=...
FF haptics: request=1 phase=upload-end result=0 errno=0 ...
FF haptics: request=1 phase=play-end result=24 errno=0 ...
GUI2 haptics: request=1 phase=end accepted=1 elapsed_ms=...
```

以上为格式示例，不是设备输出。成功的24是ARM64/Linux input_event字节数，不能当作电机反馈。FF close的request固定0，表示描述符生命周期，可能发生在探测设备消失、错误清理或退出；close返回0也不能证明内核erase成功。

读取时按PID/TID、phase和单调时间排序；stdout/stderr采集可能不同步。GUI request每次接受submit递增，FF request每次正时长调用递增，两者不会在同步完成反馈等额外caller存在时自动一一对应。replaced记录合并掉的pending次数；expired只表示队龄超过250ms，不是驱动拒绝。stop丢弃pending沿用原逻辑，未增加其单独日志。默认500ms能力轮询没有每次正常输出，避免闲时刷屏。

errno在系统调用后立即保存，日志时间查询/格式化不会覆盖错误说明；正数短写保留实际字节数和errno0，另报short input event write。日志本身为同步stdio，虽不在GUI提交入口，阻塞输出仍可拖慢owner或持FF锁线程；主机非阻塞检查不能证明所有设备I/O均有界。

复现入口：

```bash
python3 tests/haptics_route_test.py --report logs/haptics-request-trace-route.json
python3 tests/haptics_route_test.py --worker-io --report logs/haptics-request-trace-worker-ff.json
python3 tests/haptics_worker_test.py
python3 tests/haptics_request_trace_test.py
```

实际生产source编译，sysfs/input/属性/ioctl为显式替身；owner使用实际线程/门控，latest-only记录第二次request5002/replaced5000，过期同计数且age>=250ms。8种时长的48字节effect与既有捕获完整相同，input_event只核对有效payload，不假设时间戳有物理意义。没有执行真实evdev/input core/IRQ/DSP或电机。


请求诊断候选交付收尾：同镜像六版本双槽回放9组/102次阶段调用通过，726份构建来源保持一致，维护文件重建76+1+3且0待更新。14项日志与ABI、24项路由、4项后台FF、16项owner检查通过；交付审计入口`python3 scripts/audit_haptics_request_trace_delivery.py`，结果`logs/haptics-request-trace-delivery.json`。这是诊断候选，未确认触摸、现场设置保存或物理震动恢复，完整12组继续进行中。
