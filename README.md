# TCL p32a6：Root 与默认桌面实战

把一台 **Android 5.1.1 的 TCL 55V2 / p32a6** 改成开机进入儿童 Leanback 桌面的完整记录：从厂商 `sserver` 按次 Root，到带授权管理的持久 Root，再到系统原生默认 HOME。

这不是一键适配所有 TCL 的工具。已验证固件为 **V8-A962T04-LF1V117，API 22，ARMv7，20201111**。商品型号相同也可能固件不同，先核验再操作。

## 最终实现

- 按次管理员命令：通过已有 ADB 转发到电视的本地 `sserver` socket，实测 `uid=0(root)`。
- 持久 Root：从源码构建 phh Superuser 管理器和 `su`，保留原厂启动逻辑；普通应用可以请求授权。
- 默认桌面：LeanbackOnFire 1.63 注册为系统默认 HOME，重启自动进入；原厂 CyberUI 保留用于回退。
- 儿童应用收藏首行、关闭推荐行；实体 HOME、设置、输入源键由机主确认正常。

**Root 不会提高 Android API 版本。** 本次尝试的 Projectivy 版本最低需要 API 23，因此没有伪装系统版本或降低其 minSdk，而是选择实际能运行的桌面。

## 教程

按顺序阅读，已有 Root 时可以跳过持久安装：

1. [范围核验与 sserver 按次 Root](skills/tcl-p32a6-root-launcher/references/01-root-access.md)
2. [备份、构建、安装持久 Root](skills/tcl-p32a6-root-launcher/references/02-persistent-root.md)
3. [恢复 HOME 声明并设置默认桌面](skills/tcl-p32a6-root-launcher/references/03-default-home.md)
4. [重启验证、调试收尾与恢复](skills/tcl-p32a6-root-launcher/references/04-validation-recovery.md)
5. [实测证据、适用边界与上游来源](skills/tcl-p32a6-root-launcher/references/05-case-evidence.md)

流程：

```mermaid
flowchart LR
    A[确认设备与授权] --> B[sserver 身份核验]
    B --> C[备份并在电脑校验]
    C --> D[可选：持久 Root 与应用授权]
    D --> E[同签名 Leanback HOME 更新]
    E --> F[系统 HOME 偏好与厂商启动属性]
    F --> G[重启与实体遥控器验证]
    G --> H[保存回退并关闭调试]
```

## 安装为 Codex skill

```bash
git clone https://github.com/mylys/tcl-p32a6-root-launcher-skill.git
cd tcl-p32a6-root-launcher-skill
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
# 若目标目录已存在，先检查已有改动，不要覆盖。
test ! -e "${CODEX_HOME:-$HOME/.codex}/skills/tcl-p32a6-root-launcher" && \
  cp -R skills/tcl-p32a6-root-launcher "${CODEX_HOME:-$HOME/.codex}/skills/"
```

在 Codex 中打开新会话或刷新技能后调用：

```text
使用 $tcl-p32a6-root-launcher 检查我的电视，先核验型号、固件和 Root；
在我的授权范围内配置默认桌面，保留原厂桌面和完整回退方法。
```

技能入口是 [SKILL.md](skills/tcl-p32a6-root-launcher/SKILL.md)，包含适用条件、操作边界及教程路由。

## 文件与验证

`skills/.../scripts/` 提供源码和辅助脚本。构建产物、签名材料及备份放在忽略目录 `work/`、`backup/`，**不要提交 Git**。仓库不提供固件、预编译 Root 安装包、个人签名私钥或设备凭据。

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q skills/tcl-p32a6-root-launcher/scripts
```

实机结果来自 2026-10-23 至 2026-10-24 的一次授权案例。公开脚本已移除私人路径和地址，增加参数、哈希门禁和超时处理；这些整理后的脚本做了本地构建及离线测试，**没有为发布而在电视上重新执行整套 Root 安装**。历史实机证据和发布版测试范围分别说明，不混为一谈。

## 许可

GPL-3.0-or-later，见 [LICENSE](LICENSE)。上游项目与补丁来源见 [NOTICE.md](NOTICE.md)。仅用于自己拥有或明确获准维护的设备。
