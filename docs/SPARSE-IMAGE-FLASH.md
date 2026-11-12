# Sparse 镜像刷写的容量与完成检查

2026-11-12，按任务文档的安装/刷写验收要求检查真实 `TWPartition::FlashImage` → `IsSparseImage` → `FlashSparseImage`。旧实现只比较输入文件大小与缓存分区大小；sparse 的压缩大小不能限制其展开写入。临时文件实验中，44 字节的 FILL 镜像声明展开为65536字节，旧实现写入32768字节目标并返回成功。没有使用手机或物理块设备。

维护补丁 `0051-sparse-image-capacity-and-commit.patch` 在解析成功后检查实际展开长度，拒绝零长度及超出缓存容量的镜像；再对已打开目标执行 fstat 与 BLKGETSIZE64，拒绝普通文件、未知/零容量或展开越界。容量查询 EINTR 可重试。可选 discard 移到这些检查之后；sparse 对象通过 scope guard 释放。写完必须 fsync 成功且显式 close 成功才报告成功；fsync EINTR 重试，close 错误不重试已释放的描述符。

`tests/sparse_flash_test.py` 在主机编译原始三个生产方法，以及当前 AOSP libsparse 六个源文件和 libbase 的 mapped_file/stringprintf。没有用虚假的 sparse parser 或 writer。20种情况分别在默认配置和可选 discard 配置执行，共40项通过；旧实现同一测试40项中27项断言失败。正常、EINTR、短写均逐字节核对 RAW/FILL/DONT_CARE/RAW 输出和尾部未改内容；DONT_CARE保留已有数据，不承诺清零。越界、容量错误、格式错误和前置拒绝路径核对目标完全未改；第二次写入故障明确保留已经写入的第一块，并返回失败，不能称为回滚。同步/关闭错误即使完整字节已经可读也必须失败。

模拟边界：一个私有普通文件由 fstat/BLKGETSIZE64 描述为块设备，缓存容量发现为夹具；ftruncate模拟块设备拒绝截断。discard仅记录调用，不发送任何ioctl。实际读写、解析、映射、同步以及错误出口执行；没有运行 ARM64 刷写、PartitionManager/GUI 路由、槽位切换或USB。libsparse导入沿用现有 `crc=false`，本次没有新增CRC或内容真实性保证。当前编译未启用discard，不将可选配置检查扩展成设备支持声明。断电、移除中写入、完整ZIP/update-binary/sideload及GUI链路继续未完成。

证据为 `logs/sparse-flash.json`、`logs/sparse-flash-before.json`；raw传输既有65项回归保存为 `logs/sparse-flash-raw-regression.json`。交付镜像和构建/来源审计由后续同名交付报告记录；本页的软件检查不等于实机功能恢复。
