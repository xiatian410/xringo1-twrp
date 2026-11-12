# OTA 快照 COW 格式的 ARM64 往返验证

本项回答一个具体问题：六份所列原厂 OTA 请求的 **COW v3 / LZ4 / 64 KiB 压缩块**，是否能由当前构建的 Recovery 快照库实际写入、解析并解压读回。它不验证整份 OTA 安装。

## 输入与执行

`tests/ota_cow_roundtrip.py` 核对六份本地 `payload-manifest.pb` 与提取 inventory 的摘要及 metadata 校验记录，读取真实动态分区参数。六份均为 full payload、minor 0，均请求 snapshot / VABC、COW 3、LZ4、65536 字节压缩块；两份 OS4 另设置 `disable_ublk`。OS4 还有当前原型未消费的动态字段 9，显式记录而不忽略成“全字段兼容”。

测试程序链接当前 Android 构建的 **ARM64 `libsnapshot_cow.a`**，使用原构建命令中的 ABI、头文件和链接依赖；仅测试入口保持 assert 开启。固定 QEMU 在私有 chroot 中执行，Android linker 与共享库从当前交付镜像提取并逐文件绑定。

只访问临时普通文件，不创建设备节点、挂载或使用真实分区。私有环境没有真实 `/proc` / linkerconfig，链接器回退警告保留在本地报告；不能外推为真实 init namespace 验证。

## 结果

五个场景通过：

| 场景 | 核对内容 |
| --- | --- |
| 原厂参数往返 | 写入 64 KiB 确定性数据和两个 ZERO 块；Finalize / 关闭后重新 Parse / LZ4 解压，逐字节及主机 SHA-256 核对；压缩数据长度确实小于原始长度 |
| 容量拒绝 | 128 块上限拒绝 129 块请求，Finalize 正确返回 |
| 损坏头 | 改坏 COW magic 后 Parse 拒绝，不生成读回输出 |
| 不支持版本 | version 99 的 writer 创建被拒绝 |
| 不支持压缩器 | 非法压缩算法被拒绝 |

往返同时核对 v3 header、4096 字节 block、65536 最大压缩块、LZ4 标识、ZERO 目标集合，以及已存在标签 41 接受 / 不存在标签 42 拒绝。v3 标签位于 resume buffer，不能套用 v2 的 `GetLastLabel` 行为；恢复标签检查不是 OTA 重启恢复或断电试验。

六份 manifest 参数相同，因此执行一组共享参数往返，不重复执行六份等价夹具。没有发现本段需要修改生产代码的格式缺陷。

## 来源与边界

本地报告：`logs/ota-cow-roundtrip.json`，记录 archive、输入 manifest、工具链、链接依赖、QEMU、镜像库和测试源码摘要。

当前交付为 `recovery-dijun-unified-bounded-maintenance.img`，SHA-256 `218c5edd28c4e458464fc035a73b68808b016598c51e50877b2c0a1b055da3c3`。其旧 775 来源清单**没有历史绑定快照 archive 的摘要**。本测试绑定的是当前构建 archive 与当前 engine 链接输入声明，不据此宣称这些 archive 字节已被历史清单证明等同于交付 engine 内部代码。共享库和 linker 则直接来自交付镜像。

未执行：update_engine payload 解码与签名、SnapshotManager、LP / block-device 元数据、dm-user / UBLK、实际 snapuserd、分区写入、快照合并、OTA 重启与完整 GUI / USB。`disable_ublk` 这里只读取参数，未验证行为。

本批仅新增执行证据与范围说明，无生产补丁、无新镜像。完整任务仍进行中，下一步需推进实际 payload 消费到快照的连接，不继续拆分同类格式叶函数。

## 复现

需完整本地 Android 构建树、六份已校验样本、当前交付镜像和固定 QEMU：

```bash
python3 tests/ota_cow_roundtrip.py
```

公开仓库只发布源码与结果摘要，不包含这些依赖或原始日志。
