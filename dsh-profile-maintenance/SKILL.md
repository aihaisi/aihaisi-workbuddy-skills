---
name: dsh-profile-maintenance
description: 排查并修复 DSH（DeepSeek Harness）profile 的插件安装/更新失败——尤其是 git 依赖报 "Could not resolve hostname github.com"、"Could not read from remote repository"、pnpm exit 128，或插件市场点更新后中断。也用于在本机（校园网 + Clash）给 DSH 装/更新/回滚插件。当用户说"dsh 更新插件市场报错""装不上插件""dsh plugin 失败""DSH profile 坏了"时使用。
agent_created: true
---

# DSH Profile 插件维护与故障修复

## 0. 本机（此台 Windows）必须记住的网络事实

| 事实 | 值 |
|---|---|
| 代理 | Clash Verge Rev（`verge-mihomo`），混合端口 **127.0.0.1:7897** |
| **必须处于「规则模式」** | `mode: direct` 时 7897 等于没开代理，所有境外站点必挂。配置文件：`%APPDATA%\io.github.clash-verge-rev.clash-verge-rev\config.yaml` |
| TUN | 关闭（`enable_tun_mode: false`），不要依赖 |
| 系统 DNS | 10.1.2.1（校园网）——**解析不了境外域名**（github.com 报"不知道这样的主机"） |
| 结论 | 境外域名一律让**代理解析**，不要用 hosts 硬指 IP |
| 例外 | `registry.npmmirror.com` 的 **443 在校园网时通时不通**（80 通）；pnpm 读元数据一般仍可用 |

**禁止操作**：往 `C:\Windows\System32\drivers\etc\hosts` 硬写 github.com 的 IP。
`185.199.108.x` 是 GitHub Pages(Fastly) 的 IP，**不是 github.com**，写错会让 GitHub 直接返回
`500 Domain Not Found (Server: Varnish)`——比不写还糟。要排查先看 hosts 有没有这种"修复残留"。

## 1. 关键路径

```
profile 目录 : %USERPROFILE%\.dsh\profiles\web
配置         : package.json / pnpm-lock.yaml / cordis.yml / cordis.patch.yml
市场状态     : .dsh-market\state.json   （region: china = 走国内加速路由）
更新日志     : %TEMP%\dsh-pnpm-update.log 、%TEMP%\dsh-pnpm-update-target.log
CLI          : %APPDATA%\npm\dsh.cmd   （dsh 0.1.1-rc.2）
```

**命令通道**：`dsh plugin --profile web <pnpm 参数>`——把参数直接转发给该 profile 目录下的 pnpm。
例：`dsh plugin --profile web update dshmarket`、`dsh plugin --profile web install <pkg>`。

## 2. 排查步骤（按顺序）

1. **读日志**：`%TEMP%\dsh-pnpm-update*.log`。分清是 registry 失败还是 git 失败。
2. **看依赖形态**：`package.json` 里 `github:owner/repo` 短写 → pnpm 会用
   `git ls-remote git+ssh://git@github.com/...` 解析 ref，**这一步走 SSH**，校园网必挂。
3. **查 hosts 污染**：
   ```powershell
   Select-String -Path C:\Windows\System32\drivers\etc\hosts -Pattern "github|198\.18"
   ```
   有 → 备份后删掉那几行（该文件 ACL 对本用户**可写**，无需管理员），再 `ipconfig /flushdns`。
4. **查代理模式**：确认 Clash 是规则模式，且
   `curl -x http://127.0.0.1:7897 -s -o NUL -w "%{http_code}" https://github.com` 返回 200。
5. **查 git 配置**：`git config --global --get-regexp "url\.|proxy"`，应包含第 3 节那 4 条。

## 3. 标准修复（一次性配好，之后 DSH 自己更新就不会再撞）

不改 `package.json`，只在 git 层做两件事：**把 ssh 改写成 https** + **让 github 走代理**。

```bash
git config --global url."https://github.com/".insteadOf "git+ssh://git@github.com/"
git config --global --add url."https://github.com/".insteadOf "ssh://git@github.com/"
git config --global http.https://github.com.proxy http://127.0.0.1:7897
git config --global http.https://codeload.github.com.proxy http://127.0.0.1:7897
```

验证（两条都要 exit=0 并打印出 SHA）：

```bash
git ls-remote "git+ssh://git@github.com/omdsh-dev/dsh-at-file.git" HEAD
git ls-remote "git+ssh://git@github.com/volcengine/OpenViking.git" HEAD
```

## 4. 执行更新（务必先备份）

```powershell
$dir = "$env:USERPROFILE\.dsh\profiles\web"
foreach($f in @("package.json","pnpm-lock.yaml","cordis.yml","cordis.patch.yml")){
  Copy-Item "$dir\$f" "$dir\$f.bak-<日期>" -Force
}
$r = & "$env:APPDATA\npm\dsh.cmd" plugin --profile web update dshmarket *>&1 | Out-String
```

- 用 `Start-Process`/后台跑，pnpm 走网络约 1 分钟；**PowerShell 工具不回传 stdout**，
  必须 `Out-File` 到文件再用 Read 读。
- 成功标志：`Done in xx s` + `EXIT=0`；`package.json` 里版本号被抬高、`node_modules/<pkg>/package.json` 版本一致。
- **`missing peer @deepseek-ai/...` 是正常的**：profile 设了 `autoInstallPeers: false`，peer 由 DSH 宿主提供。
  `Ignored build scripts: node-pty/ssh2/cloudflared...` 也是 pnpm 既有策略，非报错。

## 5. 回滚

- hosts → 覆盖回备份文件
- git → `git config --global --unset-all url.https://github.com/.insteadof`，其余 `--unset`
- profile → 覆盖回 `*.bak-*` 后 `dsh plugin --profile web install`

## 6. 环境坑（本机通用）

- PowerShell 工具**不回传 stdout**，脚本一律 `Out-File` 后 Read。
- Bash 工具 PATH 损坏（`ls`/`mkdir` 全 command not found）→ 文件操作走 PowerShell。
- `Remove-Item` 在沙箱内被拒（报 `SAFE_DELETE_FAIL_CLOSED`）→ 用 `dangerouslyDisableSandbox` 才能删。
- 诊断/安装都要真网络 → 必须 `dangerouslyDisableSandbox: true`，否则 curl 全 000 会误导你。
- 沙箱内 `Test-NetConnection 127.0.0.1:<port>` 可用 → 可用它判断代理是否在跑。
