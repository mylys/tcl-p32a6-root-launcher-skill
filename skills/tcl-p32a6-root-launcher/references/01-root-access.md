# 1. 范围核验与 sserver 按次 Root

## 已验证设备

| 项目 | 本案例 |
|---|---|
| 商品型号 | TCL 55V2 |
| 平台 / device | p32a6，Amlogic T962 |
| 固件 | V8-A962T04-LF1V117 |
| Android | 5.1.1，API 22 |
| 构建 | 20201111；显示为 p32a6-userdebug |
| ABI | armeabi-v7a |
| SELinux | 原机为 Disabled；流程没有关闭它 |

不要把 `dev-keys` 当作持有 TCL 私钥，也不能由 verified boot 属性为空推断已解锁 Bootloader。若平台/API/固件不同，停在只读检查；不能照抄系统写入步骤。

## 准备明确的连接

电视和电脑位于同一受信任网络，电视开启网络调试。只连接自己拥有或获准维护的电视，不扫描其他设备。先确认 USB 硬盘及网络是否通过 USB 网卡连接，以免后续关闭调试影响外设。

以下命令在仓库根目录、同一个终端中执行，替换地址：

```bash
export TV_SERIAL='<电视IP>:5555'
export TV_SCRIPTS="$PWD/skills/tcl-p32a6-root-launcher/scripts"
mkdir -p work backup
adb connect "$TV_SERIAL"
adb -s "$TV_SERIAL" shell id
adb -s "$TV_SERIAL" shell getprop ro.product.device
adb -s "$TV_SERIAL" shell getprop ro.build.version.sdk
adb -s "$TV_SERIAL" shell getprop ro.build.display.id
adb -s "$TV_SERIAL" shell getprop ro.product.cpu.abi
adb -s "$TV_SERIAL" shell getenforce
```

普通 ADB 显示 `uid=2000(shell)` 很正常。先执行 `adb -s "$TV_SERIAL" shell 'su -c id'`：如果已返回 Root，直接走已有 Root 的维护路径，不覆盖已存在的 Root 工具。若 `su` 不存在，再检查此固件的按次入口。

## 机制

本机的厂商 `sserver` 服务监听本地 Unix socket `/dev/socket/sserver`。已有 ADB 可以建立如下转发：

```text
电脑临时 TCP 端口 → ADB → 电视 localfilesystem:/dev/socket/sserver
```

实测该服务会以 Root 执行送入的 shell 命令。它不是新装的 `su`，不需要降级或刷机；这是此固件暴露的高权限命令入口。使用它得到的是按次命令能力，普通 App 并不会因此自动具备 Root 授权入口。

## 仅核验身份

```bash
python3 "$TV_SCRIPTS/tv_bridge.py" \
  --serial "$TV_SERIAL" --method sserver --probe \
  --output work/root-identity.json
```

成功条件是输出中 `root_verified: true`，且命令结果包含 `uid=0(root)`。收到 socket 的 `ok` 不足以证明命令已完成。脚本会使用唯一临时目录并在成功后删除；ADB 转发在结束时移除。

如果 socket 不存在、连接被拒或身份不是 Root，停止这条路线；不要循环尝试、开放公网端口或改用其他设备。Root 探测本身不会修改启动脚本。

## 按次执行经过审阅的脚本

```bash
cat > work/read-only.sh <<'SH'
id
cat /proc/mounts
ls -l /system/bin/install-recovery.sh
SH
python3 "$TV_SCRIPTS/tv_bridge.py" \
  --serial "$TV_SERIAL" --method sserver \
  --script work/read-only.sh --execute --timeout 180 \
  --output work/read-only-result.json
```

`--execute` 是脚本的误操作保护；不要把它视为用户授权的替代。脚本内容能以 Root 执行，执行前应检查实际文件。

长作业会在电视端写入完成状态，电脑轮询该状态。若超时，返回的 `remote_directory` 保留供检查，作业可能仍在运行：不要立即重发同一安装命令，也不要删除那个目录。可通过已有 `su` 或恢复的 sserver 只读检查该目录里的 `out` 和 `status`，确认完成后再清理。

## 先保存基础快照

```bash
adb -s "$TV_SERIAL" shell pm list packages -f > backup/packages-before.txt
adb -s "$TV_SERIAL" shell pm list packages -d > backup/disabled-before.txt
adb -s "$TV_SERIAL" shell getprop > backup/properties-before.txt
adb -s "$TV_SERIAL" shell dumpsys package > backup/packages-state-before.txt
adb -s "$TV_SERIAL" shell content query --uri content://settings/system > backup/settings-system-before.txt
adb -s "$TV_SERIAL" shell content query --uri content://settings/secure > backup/settings-secure-before.txt
adb -s "$TV_SERIAL" shell content query --uri content://settings/global > backup/settings-global-before.txt
```

此旧固件的 `settings list` 可能不可用，使用实际支持的只读接口。快照可能含设备标识和设置，不上传 GitHub。

下一步：[持久 Root](02-persistent-root.md)；只需按次维护时不必继续安装。
