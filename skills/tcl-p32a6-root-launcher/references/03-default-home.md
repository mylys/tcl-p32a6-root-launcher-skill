# 3. Leanback 默认桌面替换

本节保留 TCL 原厂 CyberUI，只改变默认 HOME 和开机入口。已获准使用 Root 修改桌面后执行；只要求普通 APK 安装时，不自动调整厂商签名参考。

## 3.1 为什么普通安装失败

固件的 PackageManagerService 在安装过程中检查同一 IntentFilter 是否包含 `MAIN` 与 `HOME`。若是，要求：

1. 待装 APK 签名与 `sys.currentlauncher` 指向的已装应用一致。
2. application metadata 含 `com.tcl.app.type=com.tcl.ui`。

失败时返回 -104，对外显示 `INSTALL_PARSE_FAILED_INCONSISTENT_CERTIFICATES`。这不一定是 APK 损坏。

`persist.sys.matrix.mi.enable=1` 会跳过该限制，但也影响共享的 `compareSignatures`。该属性缓存在 system_server 初始化时，改回属性值不等于运行中的缓存立即恢复。**本方案不修改这个开关。** 如果此前有人开启过它，先恢复为 0 并正常重启，使安装服务重新初始化，不能只依据 getprop 的当前值判断缓存状态。

本方案利用已有 Root，临时将签名参考指向已安装的本地同签名 Leanback，从而允许该桌面的 HOME 更新。这确实是在绕过 TCL 的桌面安装限制，不应包装成普通用户偏好设置。全局 Android 签名校验没有被关闭，事务退出后恢复原参考值。

## 3.2 下载指定兼容版本

已经完成 [环境设置](01-root-access.md)，并设置 `TV_SDK`、`TV_JAVA` 后：

```bash
mkdir -p work/downloads
curl --fail --location \
  'https://github.com/tsynik/LeanbackLauncher/releases/download/v1.63/LeanbackOnFire_v1.63-release.apk' \
  --output work/downloads/LeanbackOnFire-v1.63.apk
python3 "$TV_SCRIPTS/build_launchers.py" \
  --source work/downloads/LeanbackOnFire-v1.63.apk \
  --sdk "$TV_SDK" --java-home "$TV_JAVA" \
  --output work/launcher
```

需要 SDK Platform 25、Build Tools 34.0.0、JDK 17。构建脚本只接受本次核验的官方 APK SHA-256：

```text
98824777eb845204fc82022a88b82dbce9940a802eaa0f55a28b58cdb9e5cacc
```

不匹配时停下检查来源，不去掉哈希检查继续运行。构建产生：

| 文件 | 用途 |
|---|---|
| `leanback-app-local.apk` | 移除 HOME 的普通应用模式，用于首次兼容性验证 |
| `leanback-home-local.apk` | 保留官方 HOME、追加 TCL metadata 的版本 |
| `home-preference.jar` | Android 5 系统默认 HOME API 工具，不是常驻 App |
| `launcher-local.jks`、`signing-password.txt` | 仅本地保存的签名材料 |

两个 APK 使用同一新生成的本地签名。脚本断言除 Manifest 与签名记录外，原始程序代码和资源逐字节不变。**如果电视已经安装了其他人或旧构建签名的 Leanback，必须使用对应原密钥重新签名；不要卸载或清空数据来掩盖签名不匹配。** 初次构建脚本不会读取或传播原案例的私人密钥。

## 3.3 先验证普通应用

```bash
adb -s "$TV_SERIAL" install -r work/launcher/leanback-app-local.apk
adb -s "$TV_SERIAL" shell am start -W -n com.amazon.tv.leanbacklauncher/.MainActivity
```

确认界面渲染、遥控方向键、应用入口和设置可用。此时按 HOME 回原厂桌面是预期行为，因为没有 HOME 声明。应用无法运行时，不继续做默认桌面替换。

在桌面自己的设置和应用菜单中加入常用儿童应用收藏、关闭推荐行；具体收藏由用户选。首次打开课程 App 可能需要隐私同意、登录或付费，不代替用户确认。

## 3.4 更新为 HOME 版本

保存当前默认桌面、属性、应用配置以及实际 APK。不要覆盖其他任务正在修改的设置；停止另一桌面测试版的开机自动拉起，否则会影响验证。

首次目录应不存在；若已存在，先检查是否有未结束的旧作业，勿直接覆盖：

```bash
adb -s "$TV_SERIAL" shell mkdir /data/local/tmp/tcl-home-stage
adb -s "$TV_SERIAL" shell getprop sys.currentlauncher > work/currentlauncher-before.txt
adb -s "$TV_SERIAL" shell getprop persist.sys.launcher.component > work/launcher-component-before.txt
adb -s "$TV_SERIAL" shell getprop persist.sys.matrix.mi.enable
python3 - <<'PY'
from pathlib import Path
import hashlib
p=Path('work/launcher/leanback-home-local.apk')
Path('work/launcher/SHA256SUMS').write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  leanback-home-local.apk\n')
PY
adb -s "$TV_SERIAL" push work/launcher/leanback-home-local.apk /data/local/tmp/tcl-home-stage/leanback-home-local.apk
adb -s "$TV_SERIAL" push work/launcher/SHA256SUMS /data/local/tmp/tcl-home-stage/SHA256SUMS
python3 "$TV_SCRIPTS/tv_bridge.py" --serial "$TV_SERIAL" --method su \
  --script "$TV_SCRIPTS/launcher_transaction.sh" --execute --timeout 300 \
  --output work/home-install.json
```

若仅有按次 Root，将 `--method su` 改为 `--method sserver`。脚本要求 matrix 开关为 0、已安装 Leanback、原参考值属于已知桌面，核对传输后的 SHA-256，再临时改变签名参考、调用正常安装器更新，退出时恢复原值。

如果超时或输出 Failure，不连续重装。确认是否仍有 dex2oat 编译，检查桥接返回的唯一目录和 `/data/local/tmp/tcl-home-stage/install.log`，然后用 `pm path`、设备端 APK 哈希和 HOME 候选列表确认实际结果。案例的旧桥接曾等待超时，但安装随后完成；此仓库使用异步完成标记处理这类长作业。

## 3.5 设置系统默认 HOME

普通 `am start` 只会打开应用。Android 5 的 `pm` 没有 `set-home-activity`，需要系统 API：

```text
getHomeActivities → 核实候选含 Leanback
replacePreferredActivity(MAIN + HOME + DEFAULT, match, candidates, Leanback, user 0)
getHomeActivities → 核实返回 Leanback
```

读取当前默认：

```bash
python3 "$TV_SCRIPTS/home_preference.py" \
  --serial "$TV_SERIAL" --jar work/launcher/home-preference.jar
```

必须看到 CyberUI 和 Leanback 都是 HOME 候选，再设置：

```bash
python3 "$TV_SCRIPTS/home_preference.py" \
  --serial "$TV_SERIAL" --jar work/launcher/home-preference.jar \
  --set leanback --execute --snapshot backup/home-switch-before
```

工具以 Root 调用 PackageManager，确认结果后才设置：

```text
persist.sys.launcher.component=
com.amazon.tv.leanbacklauncher/com.amazon.tv.leanbacklauncher.MainActivity
```

此属性是 TCL 启动时的自定义桌面入口；单独设置它、但 APK 不是有效 HOME 候选，并不能可靠接管桌面。工具不注入按键、不重启；完成后删除自己的临时 JAR。

原厂 CyberUI 必须保持启用。随后按 HOME、从其他 App 返回 HOME、正常重启、观察至少数分钟，并使用实体遥控器验证。完整步骤见 [第 4 篇](04-validation-recovery.md)。

重启后 `sys.currentlauncher` 可能由固件更新为实际默认 Leanback，不能因为它不再是 CyberUI 就判断安装事务没有恢复。区分“安装事务结束时的恢复”和“系统启动后根据默认桌面更新属性”。
