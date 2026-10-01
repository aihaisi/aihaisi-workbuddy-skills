---
name: mumu-emulator-adb-control
description: 用 ADB 通道操作本机网易 MuMu 模拟器——截图看画面、点击/滑动/输入文字、启动与关闭应用、安装 APK、配模拟器代理让 Play 商店可用、执行 root shell、取控件树拿坐标。当用户说"操作我的模拟器""在模拟器里点一下""模拟器截图""帮我在模拟器里装个应用""模拟器上不了网/Play 商店打不开""MuMu 自动化/挂机/脚本"时使用。
agent_created: true
---

# MuMu 模拟器 ADB 控制

## 0. 本机事实（2026-09-23 实测）

| 事实 | 值 |
|---|---|
| 安装目录 | `D:\MuMuPlayer`（网易 MuMu 模拟器） |
| 引擎版本目录 | `nx_device\12.0\`、`nx_device\15.0\`（当前运行的是 15.0） |
| adb 可执行 | `D:\MuMuPlayer\nx_device\15.0\shell\adb.exe`（用它连 15.0 实例；另有 `nx_main\adb.exe`） |
| 实例 | `vms\MuMuPlayer-12.0-0`（未运行）、`vms\MuMuPlayer-15.0-1`（**当前运行**） |
| 实例 ADB 端口 | **16416**（写在 `vms\<实例>\configs\vm_config.json` → `vm.nat.port_forward.adb.host_port`） |
| 连接方式 | `adb connect 127.0.0.1:16416` |
| 设备身份 | model `2206122SC`（伪装小米 12S Pro），`product:unicorn`；Android 15 / SDK 35 |
| 架构 | `abilist = x86_64,arm64-v8a,x86`，`ro.product.cpu.abi = x86_64`；**但 Play 会装 arm64-v8a 版应用，靠 MuMu 的 ARM 转译跑，实测正常** |
| root | **已开**（`vm.root: "true"`，且装有 KernelSU `me.weishu.kernelsu`） |
| adb 调试 | `shell_config.json` → `player.advanced.adb_debug.mode = "2"`（远程连接模式） |
| 屏幕 | `SurfaceOrientation: 1` = **横屏**，逻辑分辨率 **1920×1080**（`wm size` 报的 1080×1920 是竖屏物理值，**不要直接用**） |
| 密度 | dpi 280 |
| **模拟器内网** | 本机 `10.0.2.15/24`，**宿主网关 = `10.0.2.2`**（QEMU/slirp 约定） |
| Google 账号 | 模拟器内**已登录** `aihaisi735@gmail.com`，Play 商店 / GMS / GSF 齐全 |

⚠️ 用户口头说的"UU 模拟器"实际指 **MuMu 模拟器**；机器上另有 `UU加速器`（网易 UU，网络加速器，不是模拟器），别搞混。

## 1. 三条铁律（踩过坑）

### 铁律一：connect 和后续命令必须写在同一条命令里
每次 shell 调用是**独立进程**，adb server 不跨命令存活（下一条命令会重新 `daemon not running; starting now`，之前 connect 的 device 记录随之丢失 → `device '127.0.0.1:16416' not found`）。
**正确做法**：一条 PowerShell 里 `connect` → `Start-Sleep -Milliseconds 1000` → 所有操作，中间不返回。
详细报错原文见 `references/pitfalls.md`。

### 铁律二：截图必须走 /sdcard 中转
```
adb -s 127.0.0.1:16416 shell screencap -p /sdcard/_s.png
adb -s 127.0.0.1:16416 pull /sdcard/_s.png <本地路径>
```
不要 `shell screencap -p > file`（二进制被 shell 换行转换破坏）。`exec-out` 在本机也不要用。

### 铁律三：坐标按 1920×1080 横屏算
设备是横屏运行。`uiautomator dump` 出来的 `bounds` 已经是**当前旋转下的逻辑坐标**（实测 `设置` 图标 = `[543,929][682,1035]`，中心 `(612,982)`，`input tap 612 982` 一次命中），可直接 tap，无需换算。

## 2. 通道打通（标准开场）

```powershell
$adb = "D:\MuMuPlayer\nx_device\15.0\shell\adb.exe"
$s   = "127.0.0.1:16416"
& $adb connect $s
Start-Sleep -Milliseconds 1000
& $adb devices                      # 出现 "127.0.0.1:16416  device" 即通
& $adb -s $s shell screencap -p /sdcard/_s.png
& $adb -s $s pull /sdcard/_s.png "$env:USERPROFILE\WorkBuddy\Claw\outputs\mumu-screen.png"
```
再用 Read 工具读那张 png 就能"看到"画面。**端口可能因新建实例而变**——先读 `vm_config.json` 确认，别硬编码。

## 3. ★ 模拟器网络与代理（上不了网/Play 商店打不开时看这里）

**症状**：Play 商店转圈或显示"请重试"，`logcat` 出现
`AuthPII: getToken() -> NETWORK_ERROR ... oauth2:https://www.googleapis.com/auth/googleplay`；
模拟器内 `ping 8.8.8.8` 通、能解析境外域名，但 `nc -z play.googleapis.com 443` **超时**。

**根因**：MuMu 走 NAT（slirp），**模拟器的流量不经过宿主机的系统代理设置**（注册表 `ProxyServer=127.0.0.1:7897` 对模拟器无效）；宿主 Clash 没开 TUN 时，模拟器就直接裸连 → 境外全挂。

**解法（一条命令，实测有效）**：给模拟器设全局 HTTP 代理，指向**宿主网关 `10.0.2.2`** 上的 Clash 混合端口：

```
adb -s $s shell settings put global http_proxy 10.0.2.2:7897
```

- 宿主的 Clash 只监听 `127.0.0.1:7897` 也没关系：slirp 转发时以宿主本机为源，Clash 收得到。
- **Google 服务会读这个设置**——实测设完 Play 商店立刻正常加载、能拉取首页和详情页。
- 恢复直连：`settings put global http_proxy :0`。
- 前置条件：宿主 Clash Verge **必须开着**（`verge-mihomo` 进程存在 + 7897 在监听）。自检：
  `curl.exe -x http://127.0.0.1:7897 -s -o NUL -w "%{http_code}" https://www.google.com/generate_204` 应返回 204。

### ⚠️ 铁律：代理是临时开关，用完立刻撤

`settings put global http_proxy` 是**全局**的——不只影响 Google，模拟器里**所有** App 的 WebView / 网络栈都会走它。
一旦 Clash 关掉（或节点挂掉），模拟器会**整体瘫痪**：连国内站点都打不开，WebView 抛
`net::ERR_PROXY_CONNECTION_FAILED`，用户会误判成"游戏/登录坏了"。

**实测（2026-09-23 17:10）**：用户登录王者荣耀走 QQ OAuth（`openmobile.qq.com/oauth2.0/m_authorize`）报此错。
诊断——宿主只有 `clash-verge-service`（服务，**≠ Clash 在工作**），7897 无监听；
模拟器 `nc -z 10.0.2.2 7897` → `Connection refused`，而 `nc -z openmobile.qq.com 443` → **通**（直连本来是好的）。
撤掉代理后 8 个腾讯登录域名全部 OK（`openmobile.qq.com` / `graph.qq.com` / `ssl.ptlogin2.qq.com` /
`xui.ptlogin2.qq.com` / `msdk.qq.com` / `imgcache.qq.com` / `open.weixin.qq.com` / `dnf.qq.com`）。

**所以**：把配代理当成"拨一次开关"——装完东西/用完立刻 `:0` 还原，**不要让它常驻**。
判断 Clash 真的可用（`clash-verge-service` 存在 ≠ 可用）：7897 有监听 **且** 上面那条 curl 返回 204。

**想长期共存**（Play 商店 + 国内应用都要）可加排除列表让国内域名直连，但兼容性因 App 而异，不如临时开关可靠：
```
settings put global http_proxy_exclusion_list "qq.com,tencent.com,weixin.qq.com"
```

**宿主机侧诊断口诀**：`Get-Process | ? ProcessName -match "clash|mihomo|verge"` 看内核在不在；
`Get-NetTCPConnection -State Listen | ? LocalPort -eq 7897` 看端口；
`Get-NetAdapter | ? InterfaceDescription -match "TUN|Mihomo"` 看 TUN 有没有开（本机默认**没开**，所以别指望 TUN）。

## 4. ★ 用 Play 商店装应用（推荐路径）

前提：§3 的代理已配好。**优先走 Play**——官方签名、自动匹配架构与版本、后续可更新。

```
# 1) 打开详情页（务必带 -p，否则会弹"打开方式"选择器）
adb -s $s shell "am start -a android.intent.action.VIEW -d 'market://details?id=<包名>' -p com.android.vending"

# 2) 等 20~25 秒加载（首次可能更久），dump 控件树找"安装"按钮并 tap
# 3) 轮询等安装完成
adb -s $s shell pm list packages <包名>       # 出现即装好
# 4) 启动
adb -s $s shell monkey -p <包名> -c android.intent.category.LAUNCHER 1
```

**经验值**：
- Play 详情页的"安装"按钮 `clickable=false`（是内层 TextView），但 `input tap` 点它的中心**照样生效**，不用去找父容器。
- 首次启动 Play 商店会弹"想要随时了解最新动态吗？"通知引导 → 先 `tap` "以后再说"再干活。
- 下载完成后页面按钮会从"安装"变"打开/卸载"，`pm list packages` 是最可靠的完工判据。
- 实测 Edge（`com.microsoft.emmx`）：Play 只下 **122 MB**（x86_64 拆分包的对应体积）而非商店页标的 252 MB 通用包，装好后 `primaryCpuAbi=arm64-v8a`，运行流畅。

## 5. 常用操作

| 目的 | 命令（`$s` 同上报设备） |
|---|---|
| 点击 | `& $adb -s $s shell input tap 612 982` |
| 滑动 | `& $adb -s $s shell input swipe 960 540 300 540 300` |
| 输入文字 | `& $adb -s $s shell input text 'hello'`（中文不可靠，改用 `am broadcast` 或 ADBKeyBoard） |
| 返回 / 主页 / 最近任务 | `input keyevent 4` / `3` / `187` |
| 熄屏唤醒 | `input keyevent 224`(唤醒) `223`(休眠) |
| 启动应用 | `& $adb -s $s shell monkey -p com.tencent.KiHan -c android.intent.category.LAUNCHER 1` |
| 用链接打开某应用 | `& $adb -s $s shell "am start -a android.intent.action.VIEW -d 'https://www.bing.com' -p com.microsoft.emmx"` |
| 强制停止 | `& $adb -s $s shell am force-stop <包名>` |
| 当前前台页 | `& $adb -s $s shell dumpsys window | Select-String mCurrentFocus` |
| 已装第三方包 | `& $adb -s $s shell pm list packages -3` |
| 查应用版本/ABI | `& $adb -s $s shell dumpsys package <包名> | Select-String "versionName|primaryCpuAbi"` |
| 装 APK | `& $adb -s $s install -r "<本地apk>"` |
| 设置/查询代理 | `settings put global http_proxy 10.0.2.2:7897` / `settings get global http_proxy`（⚠️ **用完立刻 `:0` 还原**，理由见 §3 铁律；国内应用不要挂代理） |
| 取控件树 | `uiautomator dump /sdcard/_ui.xml` 再 pull（见 §6） |
| 取日志 | `& $adb -s $s shell logcat -d -t 400` |
| root shell | 已 root，`& $adb -s $s shell su -c "命令"`（部分场景 KernelSU 会弹授权） |

本机模拟器已装应用（2026-09-23）：`com.microsoft.emmx`（Microsoft Edge）、`com.tencent.KiHan`（王者荣耀）、`com.supercell.brawlstars`（荒野乱斗）、`me.weishu.kernelsu`、`com.nemu.googleinstaller`。桌面 launcher 是 `app.lawnchair`。

## 6. 拿精确坐标（点不准时用）

```
adb -s $s shell uiautomator dump /sdcard/_ui.xml
adb -s $s pull /sdcard/_ui.xml <本地>
```
然后用 `scripts/ui_nodes.py` 解析（XML 是单行巨串，Grep 会整行返回 2 万字符，**必须用脚本解析**）：

```
$env:USERPROFILE\.workbuddy\binaries\python\versions\3.13.12\python.exe \
  scripts\ui_nodes.py <dump.xml> <out.txt>
```
输出形如 `[543,929][682,1035] center=(612,982) click=true TextView text='设置'`。
**本机 PowerShell 不回传 stdout**，脚本一律写文件，再用 Read 读回。

## 7. 实例管理

`D:\MuMuPlayer\nx_main\MuMuManager.exe` 是官方命令行管理器（启停实例、查信息），`mumu-cli.exe` 亦同。
**用法参数未实测**，需要动实例前先 `MuMuManager.exe --help` 自己确认，不要照抄网上版本号不同的写法。
用户手动开模拟器最省事——不要为了跑命令擅自重启他的实例。

## 8. 安全边界

- 只做用户明确要求的操作。**账号登录、支付/充值、删档、卸载用户应用**一律先问再动。
- 不擅自关闭模拟器/重启实例（用户可能挂着游戏或正在挂机）。
- 自动化点击前先 `screencap` 确认当前在哪一屏，"盲点"是搞坏状态的主因。
- 临时产物统一丢 `$env:USERPROFILE\WorkBuddy\Claw\outputs\`；`/sdcard/_*.png` 这类中转文件可留着，别用 Remove-Item（沙箱内常被拒）。
- ⚠️ **不要在宿主机上用 curl/浏览器去外部 CDN 下 APK**：本机沙箱会拦（实测 `imtt2.dd.qq.com:80` 被拦且用户拒绝）。要么走 Play 商店，要么让用户自己下载后给路径。境外下载源（APKPure/APKMirror/小米商店 app.mi.com）在无代理时全部不可达。

## 9. 已验证记录

**2026-09-23 基础控制**：截图看桌面 → uiautomator dump 取坐标 → `input tap 612 982` 打开系统设置（`mCurrentFocus` 变为 `com.android.settings`）→ `input keyevent 4` 返回 launcher。
证据图：`outputs\mumu-screen.png`、`outputs\mumu-step1-settings.png`。

**2026-09-23 装 Edge 全流程（端到端成功）**：
1. 诊断出 Play 商店打不开的根因 = 模拟器不走宿主系统代理
2. `settings put global http_proxy 10.0.2.2:7897` → Play 商店立刻可用
3. `market://details?id=com.microsoft.emmx`（带 `-p com.android.vending`）打开详情页
4. dump 控件树 → `input tap 189 514` 点"安装" → 122 MB 下载约 1 分钟 → `pm list packages` 确认装好
5. 跳过 Edge 首次运行三步向导（设为默认浏览器 → 登录同步 → 隐私确认），每步都是 `input tap` 点"以后再说"/"确认"
6. 实测打开 bing.com、google.com、baidu.com **全部正常**，代理对浏览器生效

证据图：`outputs\mumu-edge-page.png`、`mumu-installing.png`、`mumu-edge-running.png`、`mumu-edge-home.png`、`mumu-edge-bing2.png`、`mumu-edge-google.png`、`mumu-edge-baidu.png`。
