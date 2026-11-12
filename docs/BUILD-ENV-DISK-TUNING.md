# 构建机磁盘布局与内存调优

2026-11-12。本文记录维护者编译工作区所在 Debian 13 (trixie) 虚拟机的磁盘重分区、swap 配置和编译负载内核参数。用途是内核树与 TWRP 镜像构建。这些是本机环境配置，不改变任何生产源码、设备树或镜像内容。

环境中 30 个 CPU、约 29 GiB 物理内存，运行在 VMware 虚拟平台。以下数值均为本次实测，不是估计。

## 背景：800 GiB 磁盘只可见 280 GiB

初始症状是 `df -h` 显示根分区 280 GiB，与 800 GiB 磁盘容量不符。排查结论不是磁盘容量不足，而是 MBR 分区表只覆盖到约 300 GiB 处：

| 项 | 重分区前 |
|---|---|
| `/dev/sda` 实际容量 | 858,993,459,200 字节 = 800.0 GiB |
| `sda1` (ext4, `/`) | 597,227,520 扇区 = 284.8 GiB |
| `sda2` 扩展分区 / `sda5` swap | 结束于扇区 629,143,551（约 300 GiB 处） |
| 未分配 | 扇区 629,143,552–1,677,721,599 = **500.0 GiB** |

`df` 报告的是已分区容量，未分配部分不会体现。排查过程中该磁盘容量曾从 400 GiB 变为 800 GiB（`/proc/partitions` 停留在旧值，`blockdev`/`sfdisk` 已是新值），因此判断容量应以 `blockdev --getsize64` 或 `sfdisk -d` 为准，不要用 `/proc/partitions`。

## 重分区：合并为单一根分区

采用"扩大根分区 + swap 移至盘尾"方案。关键约束是 **`sda1` 起始扇区保持 2048 不动**，因此文件系统无需偏移修正。

重分区后布局（`sfdisk -d /dev/sda` 实测）：

```
label: dos
label-id: 0x1ab6cebd
device: /dev/sda
unit: sectors
sector-size: 512

/dev/sda1 : start=        2048, size=  1645805568, type=83, bootable
/dev/sda2 : start=  1645807616, size=    31913984, type=f
/dev/sda5 : start=  1645809664, size=    31911936, type=82
```

| 分区 | 容量 | 对齐 |
|---|---|---|
| `sda1` | 1645805568 扇区 = 784.78 GiB | start/size 均为 2048 扇区(1 MiB) 整数倍 |
| `sda2` (扩展) | 31913984 扇区 | EBR 位于 start，logical 分区从 +2048 起 |
| `sda5` (swap) | 31911936 扇区 = 15.22 GiB，与原值一致 | 贴盘尾，`start + size = 1677721600` |

扩展分区起点按 1 MiB 对齐放在 `swap_start - 2048`，而不是紧贴 logical 分区前 2 扇区。后者虽然能构造出顺序正确的表，但会让扩展分区与 `sda1` 重叠，是无效几何。写入前用脚本校验了六项：`sda1` 起点未变、`sda1` 与扩展分区首尾相接无重叠、扩展分区延至盘尾、swap 贴盘尾、各项 1 MiB 对齐、根分区容量增加。

### 执行要点

swap 用 `mkswap -U` 重建时**保留原 UUID** `0a684da0-68c1-4eca-bf08-4ca2a56adf6c`，因此 `/etc/fstab` 与 `/etc/initramfs-tools/conf.d/resume` 均无需修改。这消除了一整类"改分区后起不来"或"swap 未激活"的故障面。

分区表写入使用 `sfdisk --no-reread --no-tell-kernel`。`sda2`/`sda5` 的起点可由 `partx -u` 热更新；`sda1` 因已挂载无法热改（`partx: error updating partition 1`），必须重启由内核重新读表。

ext4 扩容通过一次性 systemd 单元在重启后自动完成，避免手工介入：

```ini
[Unit]
Description=One-shot grow of ext4 root filesystem after partition table change
After=local-fs.target
RequiresMountsFor=/

[Service]
Type=oneshot
ExecStart=/sbin/resize2fs /dev/sda1
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

该单元幂等：文件系统已占满分区时 `resize2fs` 直接 no-op 退出。确认生效后已删除，避免长期驻留。

### 结果与满占校验

`resize2fs` 以 `on-line resizing` 在线完成，退出码 0。文件系统是否真正占满分区用块数乘块大小与块设备字节数交叉校验：

```
block_count 205725696 × block_size 4096 = 842,652,450,816 字节
blockdev --getsize64 /dev/sda1          = 842,652,450,816 字节
```

两者完全相等，无残余。`df -h /` 由 280G 变为 772G，可用空间由 39G 变为 447G（64 GiB swapfile 占用后）。

`/` 的 UUID `d035e6ef-8fe4-4d39-83c8-da7e1c287628` 未变。

## swap：15.2 GiB 分区 + 64 GiB 文件

合并后磁盘已铺满整盘（`已用到 1677721600`），仅剩 EBR 保留间隙，**没有可用扇区新建 swap 分区**。ext4 只能在线扩容、不能在线缩小，要新建分区必须卸载根文件系统进救援环境离线操作。因此 64 GiB 追加容量采用 swapfile。

swapfile 的硬性要求是无空洞。用 `fallocate` 分配后经 `filefrag -v` 确认 56 个 extent、0 个 hole，权限置为 `0600`，`mkswap` 生成独立 UUID `dbb71344-d04e-4a0d-b825-f3d850fa4469`，与分区 swap 不冲突。

`/etc/fstab` 追加：

```
/swapfile64g	none	swap	sw	0	0
```

持久化验证方式不是只看 `swapon --show`，而是 `swapoff` 后执行 `swapon -a`，确认由 fstab 重新激活且 systemd 生成 `swapfile64g.swap` 单元（状态 `generated`）。

当前 swap 布局：

| 设备 | 大小 | 优先级 | 使用顺序 |
|---|---|---|---|
| `/dev/sda5` (partition) | 15.2 GiB | -2 | 先用 |
| `/swapfile64g` (file) | 64 GiB | -3 | 后用 |

`SwapTotal` = 83,064,824 kB ≈ 79 GiB。优先级由内核按数值从大到小取用，因此分区先填满、再溢出到文件。

### 可用性实测

`swapon` 显示 0B 使用量不能证明 swap 真的可换出。实际测试分配并逐页触碰 40 GiB 内存（超过 29 GiB 物理内存），强制内核换出：

- 40 GiB 分配成功，耗时约 174 秒
- swap 实际占用 1.2 GiB，证明页面确实被换出到 swap
- 释放后内存回落，无 OOM、`dmesg` 无 swap/oom 报错

该测试只验证 swap 可正常换入换出，不涉及休眠或 `resume=` 路径。`conf.d/resume` 仍指向分区 swap 的 UUID；若将来需要休眠，须将 resume 改指 64 GiB swapfile（容量足以容纳 29 GiB 内存）。

## 编译负载内核参数

发行版默认 `vm.swappiness=60` 面向桌面对交互延迟的取舍，不适合编译负载：`make -j$(nproc)` 时约 30 个编译器进程产生大量匿名页，被换出后重新缺页会直接拖慢构建；同时页缓存被挤占，降低源码与头文件的重复读取命中率。

新增 `/etc/sysctl.d/90-build-tuning.conf`：

| 参数 | 默认 | 调整后 | 理由 |
|---|---|---|---|
| `vm.swappiness` | 60 | 10 | 优先保留页缓存，仅在内存压力大时换出匿名页 |
| `vm.dirty_background_ratio` | 10 | 5 | 默认在 29 GiB 内存下约积到 2.9 GiB 脏页才开始后台回写，`out/` 大量写入时会先阻塞再突发回写 |
| `vm.dirty_ratio` | 20 | 15 | 同步回写阈值同步下调，缩短单次写阻塞 |
| `vm.vfs_cache_pressure` | 100 | 50 | 更久保留 dentry/inode 缓存，利于内核树海量头文件查找 |

加载顺序经 `systemd-analyze cat-config sysctl.d` 确认：`/etc/sysctl.d/90-build-tuning.conf` 位于 `/usr/lib/sysctl.d/50-default.conf` 之后、`/etc/sysctl.d/90-override.conf` 之前，不会被发行版默认值覆盖，仅未来自建 override 可覆盖。

## 验证边界

- 未执行一次真实 TWRP/kernel 构建来量化调优收益。`AGENTS.md` 要求最终镜像构建必须 `installclean` + `make -j$(nproc)`，而 `installclean` 会清除现有 `out/` 构建产物（本机约 120 GiB），重建代价与验证几个 sysctl 参数不相称。调优参数的效果尚未在实构中采样对比。
- 未验证休眠/唤醒，`resume=` 仍指向分区 swap。
- 未验证断电或非正常关机后的 ext4 恢复；重分区后文件系统状态为 `clean`，未执行强制断电测试。
- 磁盘容量曾从 400 GiB 变为 800 GiB 的成因未在 VMware 宿主侧确认。本次仅保证 guest 分区表与文件系统已覆盖到当前 800 GiB。
- 这些改动不进入公开镜像、设备树或补丁，仅为本地构建环境配置。

## 重建构建机的操作顺序

1. 以 `blockdev --getsize64` / `sfdisk -d` 确认磁盘实际容量，不要用 `/proc/partitions`。
2. 备份 `sfdisk -d /dev/sda`、`/etc/fstab`、`conf.d/resume`、`dumpe2fs -h` 输出。
3. 计算几何并用脚本校验六项约束（`sda1` 起点不变、无重叠、贴盘尾、1 MiB 对齐、容量增加）。
4. `swapoff` 后 `sfdisk --no-reread --no-tell-kernel` 写入新表。
5. `partx -u` 同步可热更的分区；用保留 UUID 的 `mkswap` 重建盘尾 swap 并 `swapon`。
6. 安装一次性 `resize2fs` 单元，重启，用块数×块大小与 `blockdev` 交叉校验满占。
7. 确认 `df` 后删除一次性单元。
8. 若需追加 swap 而无空闲分区，用 `fallocate` + `filefrag` 确认无空洞后创建 swapfile，写入 fstab 并用 `swapoff`/`swapon -a` 实测持久化。
9. 施加 sysctl 调优，确认加载顺序。

回滚分区表可用备份的 `sfdisk` 脚本，但 **ext4 扩容不可逆**：`resize2fs` 无法缩小已扩容的文件系统，回滚前须确认文件系统仍能装入原尺寸。虚拟机快照是更可靠的回退手段。
