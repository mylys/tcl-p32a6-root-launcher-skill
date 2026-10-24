# 4. 验证、恢复与调试收尾

## 4.1 每层单独验收

1. **普通应用层**：桌面能够渲染、方向键能够移动、儿童应用可打开；不要替用户接受条款、登录或购买。
2. **HOME 层**：系统默认 API 返回 Leanback，按 HOME 后实际前台也是 Leanback。从另一 App 返回一次，不能只证明“已经在桌面时按 HOME”。
3. **重启层**：记录 `/proc/sys/kernel/random/boot_id`，重启后 ID 改变、`sys.boot_completed=1`。读取默认 HOME、Root、停用列表；启动完成后观察数分钟，防止其他开机 App 稍后覆盖。
4. **实体遥控器层**：让使用者实按 HOME、设置、输入源、音量、返回；逐项记录。注入按键不能替代遥控器，输入源菜单能打开也不等于 HDMI 音视频播放都通过。
5. **授权层**：普通测试 App 的拒绝/允许/重启策略分别验证；ADB shell 获得 Root 不算普通 App 弹窗验收。

例：

```bash
adb -s "$TV_SERIAL" shell cat /proc/sys/kernel/random/boot_id > work/boot-id-before.txt
adb -s "$TV_SERIAL" shell input keyevent 3
adb -s "$TV_SERIAL" shell dumpsys activity activities > work/home-activities.txt
adb -s "$TV_SERIAL" reboot
# 等待电视正常启动后重新连接，不高频重试。
adb connect "$TV_SERIAL"
adb -s "$TV_SERIAL" shell getprop sys.boot_completed
adb -s "$TV_SERIAL" shell cat /proc/sys/kernel/random/boot_id
python3 "$TV_SCRIPTS/home_preference.py" --serial "$TV_SERIAL" --jar work/launcher/home-preference.jar
adb -s "$TV_SERIAL" shell pm list packages -d
```

这台固件的 `persist.sys.service.adbd.enable` 是厂商调试开关。若需要重启后继续维护，先读取并记录原值，经当前维护范围允许临时设置 1，完成后恢复原值。不要在另一个仍需连接的任务执行期间关闭它。

```bash
adb -s "$TV_SERIAL" shell getprop persist.sys.service.adbd.enable > work/adbd-before.txt
adb -s "$TV_SERIAL" shell 'su -c "setprop persist.sys.service.adbd.enable 1"'
```

ADB 显示离线时可以做一次 `adb reconnect offline`，再连接明确目标。连接被拒通常是调试服务关闭；请用户在电视重新开启，不扫描其他端口或设备。

## 4.2 恢复原厂默认桌面

保持 CyberUI 已安装启用，执行系统 API 回退：

```bash
python3 "$TV_SCRIPTS/home_preference.py" \
  --serial "$TV_SERIAL" --jar work/launcher/home-preference.jar \
  --set stock --execute --snapshot backup/home-restore-before
adb -s "$TV_SERIAL" shell input keyevent 3
```

脚本将默认 HOME 与厂商持久组件都设为 CyberUI。核实画面后，若切换前 `persist.sys.launcher.component` 为空，可再恢复空值：

```bash
adb -s "$TV_SERIAL" shell "su -c \"setprop persist.sys.launcher.component ''\""
```

非空原值按备份恢复，不照抄空值。不要把备份的整个 `package-restrictions.xml` 直接覆盖回系统，以免覆盖后来其他应用的设置。Leanback 可以继续保留为普通可启动桌面 App；没有必要卸载系统原桌面。

若之前停用了测试桌面，重新启用会保留它的旧自启动选项；先检查选项，防止下次启动再次覆盖前台。本案例只是把独立测试版 `boot_trial.xml` 中 `enabled` 改为 false，保留 App。

## 4.3 移除本次持久 Root

先恢复需要的默认桌面，再移除 Root，以免失去回退需要的权限。电脑端保留的 `work/root-payload/rollback.sh` 与当次生成的哈希绑定，不能使用别人的回退脚本。

```bash
python3 "$TV_SCRIPTS/tv_bridge.py" --serial "$TV_SERIAL" --method sserver \
  --script work/root-payload/rollback.sh --execute --timeout 180 \
  --output work/root-rollback.json
```

回退校验原备份、当前启动文件和 su 哈希，恢复原厂启动脚本并移除本次 su。若固件升级或其他工具改过这些文件，校验失败就停止，避免强行覆盖。当前 daemon 直到重启才退出。

确认回退成功、已授权移除管理器后，可卸载 `me.phh.superuser` 并正常重启；管理器卸载会删除它的授权记录。`/data/su` 可能包含后来其他 Root App 的配置，不自动清空。此操作不会修补厂商原有 sserver 服务。

## 4.4 网络调试收尾

维护完成后按用户的连接需求关闭调试；若仍有明确授权的后续维护或并发任务，先协调再关闭。保存电脑端证据、恢复脚本，删除电视端本次创建且已完成的暂存目录。不要用广泛通配符清理 `/data/local/tmp`。

本机已验证的关闭方式：

```bash
adb -s "$TV_SERIAL" shell 'su -c "setprop persist.sys.service.adbd.enable 0"'
```

此命令可能立即断开 ADB。按电视设置界面关闭 USB/网络调试及撤销已有授权；菜单行为由本机核验，不能把单个属性写入当成已完成所有界面操作。调试关闭不影响已经安装的应用 Root 授权。

在同一明确 IP 上验证连接被拒。网络超时只能说明未收到响应，不能单独证明端口关闭；电视关机、IP 改变、路由故障都可能超时。案例实测是 `Connection refused`。如外设依赖 USB，检查其工作状态。

以后要求电脑重启或维护电视，需要重新开启网络调试。不要为了“以后方便”默认把 ADB 长期开着。
