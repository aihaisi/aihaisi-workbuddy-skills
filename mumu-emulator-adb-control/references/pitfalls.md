# 踩坑实录（本机实测原文）

## 坑一：adb server 不跨命令存活

**症状**：一条命令里 `adb connect 127.0.0.1:16416` 成功返回 `connected to 127.0.0.1:16416`、`adb devices` 也能看到设备；
但**下一条**命令里所有 adb 调用全部失败：

```
adb.exe : * daemon not running; starting now at tcp:5037
* daemon started successfully
adb.exe: device '127.0.0.1:16416' not found
adb: error: failed to get feature set: device '127.0.0.1:16416' not found
```

可见 `daemon not running` 又出现了一次——说明每次工具调用都是**全新的进程环境**，上一个 adb server 已不存在，之前 connect 的 TCP 设备记录随之丢失。

**解法**：`connect` 与所有后续操作写在**同一条**命令内，中间不 return。
`input` / `screencap` / `dumpsys` / `pm` 全部跟在同一个 `& $adb -s <serial> ...` 串里。
serial 用**完整 `127.0.0.1:16416`**，不要用 `-e`（模拟器简写不一定认）。

**副作用**：连上后第一次操作会慢 1~3 秒（等 server 起）。必要时 `Start-Sleep -Milliseconds 1000` 再发命令。

## 坑二：PowerShell 把 adb 的 stderr 当异常渲染

adb 把 `* daemon not running`、`1 file pulled, 0 skipped` 这类信息写在 **stderr**，
PowerShell 5.1 收到 native command 的 stderr 会当错误渲染成一大段红字：

```
adb.exe : /sdcard/_probe.png: 1 file pulled, 0 skipped. 65.5 MB/s (1851763 bytes in 0.027s)
所在位置 行:456 字符: 1
+ & $adb -s $s pull ...
+ CategoryInfo : NotSpecified: (...) [], RemoteException
```

**这不是失败**——exit code 仍是 0，动作已做完。看 `file pulled` 行判断成功即可，别被红字骗去重试。
想干净些可以 `2>&1 | Out-File`（本技能所有脚本都这么写）。

## 坑三：本机 PowerShell 不回传 stdout

命令 exit 0 但输出为空。所有需要看结果的命令都必须**自己写文件**（`Out-File -Encoding UTF8`），
再用 Read 工具读回。含中文的文件名在回显里会乱码，但文件内容正常，不要被误导。

## 坑四：不要用 `grep` 解析 uiautomator dump

dump 出来的 XML 是**一整行**（约 29 KB / 2 万+ 字符），行内 grep 会把整行吐出来（还会被 2000 字符截断）。
用 `scripts/ui_nodes.py` 按 `<node>` 标签切分后逐条输出。

## 坑五：`wm size` 会骗人

`wm size` 返回 `Physical size: 1080x1920`，但设备实际是**横屏**（`SurfaceOrientation: 1`），
真实逻辑坐标系是 **1920×1080**。按 1080×1920 去点会点飞。
判断当前朝向：`adb -s $s shell dumpsys input | grep -i SurfaceOrientation`（0=竖屏，1=横屏，2 或 3=反横屏/反竖屏）。

## 坑六：模拟器端口不是固定的

端口写在每个实例的 `vms\<实例名>\configs\vm_config.json`：

```json
"nat": { "port_forward": { "adb": { "guest_ip": "10.0.2.15", "host_port": "16416" } } }
```

本机 `MuMuPlayer-15.0-1` = **16416**，`MuMuPlayer-12.0-0` 是另一个端口。
新建实例、重建实例后端口会变——每次先读配置，不要硬编码。

## 坑七：多版本 adb 混用

`nx_device\12.0\shell\adb.exe` 版本较旧，`devices` 直接列空；用 **`nx_device\15.0\shell\adb.exe`**（与运行中的实例同源）才连得上。
`nx_main\adb.exe` 是主程序用的另一个副本。

## 坑八：PowerShell 会拦"嵌套 shell"

下面这种写法**直接被执行策略拒绝**（报 `Spawning a non-PowerShell shell from the PowerShell tool bypasses command validation`）：

```powershell
& $adb -s $s shell 'export http_proxy=http://10.0.2.2:7897; busybox wget -q -O - -T 10 http://...'
```

`export` / `busybox ...` 这类被判定为"从 PowerShell 里起了一个非 PowerShell shell"。
**改用单条 adb 子命令**（`settings`、`pm`、`am`、`input`、`screencap`），或直接用 `am start` 打开浏览器去验证网络，不要拼 shell 脚本。

## 坑九：PowerShell 双引号里的 `$?` 会被自己吃掉

```powershell
& $adb -s $s shell "nc -z -w 6 host 443; echo exit=$?"   # 错
```
PowerShell 先把 `$?` 展开成 `True`/`False` 再传给 adb，日志里会看到 `echo exit=True` 这种废话。
要拿被控端的退出码，**整体命令用单引号**：`'nc -z -w 6 host 443; echo exit=$?'`。

## 坑十：模拟器流量不走宿主系统代理（Play 商店打不开的头号原因）

现象：`ping 8.8.8.8` 通、境外域名能解析，但 `nc -z play.googleapis.com 443` 超时；Play 商店报
`AuthPII: getToken() -> NETWORK_ERROR`。
原因：MuMu 走 NAT，不读宿主注册表里的 `ProxyServer=127.0.0.1:7897`；Clash 没开 TUN 时模拟器直接裸连。
解法：`settings put global http_proxy 10.0.2.2:7897`（`10.0.2.2` = slirp 映射的宿主）。详见 SKILL.md §3。

## 坑十一：宿主机下载 APK 会被沙箱拦

实测从 `imtt2.dd.qq.com:80` 下应用宝 APK 时被沙箱拦截（`SANDBOX EXECUTION REJECTED BY USER`，intercept 记录 `imtt2.dd.qq.com:80`）。
**不要重试、不要换等价通道**。装应用优先走模拟器内的 Play 商店（§4），或让用户自己下载后给路径用 `adb install`。
另外：无代理时境外源（APKPure / APKMirror / github）全 000，小米商店 `app.mi.com` 也不可达；国内商店页面能开但**不直出 APK 直链**（链接藏在 JS 里）。

## 坑十二：全局代理是双刃剑 —— Clash 一关，整个模拟器陪葬

坑十的解法（`settings put global http_proxy 10.0.2.2:7897`）**必须配套"用完撤掉"**，否则后患更大。

**症状**：模拟器里打开国内页面（实测 QQ 登录页）报

```
网页无法打开
位于 https://openmobile.qq.com/oauth2.0/m_authorize?...
net::ERR_PROXY_CONNECTION_FAILED
```

`ERR_PROXY_CONNECTION_FAILED` = **连代理服务器本身失败**，跟目标站点无关。

**实测链条（2026-09-23 17:10）**：

| 检查 | 结果 |
|---|---|
| `Get-Process ? ProcessName -match clash\|mihomo\|verge` | 只有 `clash-verge-service`（服务），**无 `verge-mihomo` 内核** |
| `Get-NetTCPConnection -State Listen ? LocalPort -eq 7897` | **无监听** |
| 宿主 `curl -x http://127.0.0.1:7897 https://www.baidu.com` | `code=000` |
| 模拟器 `settings get global http_proxy` | `10.0.2.2:7897`（上轮留下的） |
| 模拟器 `nc -z 10.0.2.2 7897` | **Connection refused** |
| 模拟器 `nc -z openmobile.qq.com 443` | **exit=0，通** |

→ 网络本来是好的，是那条常驻代理把所有 WebView 流量拖进了死胡同。

**规矩**：

1. 配代理只当"拨一次开关"，**用完立刻** `settings put global http_proxy :0` 还原。
2. 每次要配代理前先确认 Clash 真在工作：**7897 有监听** + `curl -x http://127.0.0.1:7897 ... /generate_204` 返回 **204**。
   ⚠️ **`clash-verge-service` 进程存在 ≠ Clash 在工作**——那只是后台服务，内核（`verge-mihomo`）没跑时端口是空的。这是最容易误判的一点。
3. 看到 `ERR_PROXY_CONNECTION_FAILED` 先查 `settings get global http_proxy`，**不要**去查目标站点或 DNS。
4. 国内应用（腾讯系登录、微信、国内游戏）不需要代理；模拟器默认应保持**无代理**状态。

**若确实需要长期共存**（Play 商店 + 国内应用都要），可用排除列表：

```
adb -s $s shell settings put global http_proxy_exclusion_list "qq.com,tencent.com,weixin.qq.com"
```

WebView 会读它，但**不同 App 支持程度不一**，可靠性不如"临时开关"策略。清空：`settings put global http_proxy_exclusion_list null`。

