---
name: jiasu
description: 触发词"清理电脑/加速电脑"：磁盘深度清理+缓存迁移+开机加速+安全加固。
author: Dabao
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [windows, cleanup, speedup, security, maintenance]
    category: devops
---

# 电脑清理加速（jiasu）

触发条件：用户说**清理电脑 / 加速电脑 / 清理C盘 / 释放空间 / 电脑卡 / 电脑安全 / 电脑加固**等，自动按本流程执行。整合磁盘深度清理（原 windows-system-maintenance）+ 腾讯电脑管家式开机加速四件套（启动项延迟/服务禁用/DNS优化/内存整理）+ 社区优质项目方法论（Sophia 定时清理、Win11Debloat 去预装、optimizerDuck 可逆优化、WindowsClear junction 迁移）。逆向依据见 `references/qqpcmgr-feature-map.md`，社区项目调研见 `references/windows-optimization-projects.md`。

## 安全加固四件套（社区最佳实践，先做）

**任何系统修改前先建还原点**（所有大工具的标准动作）：
```powershell
Checkpoint-Computer -Description "jiasu-before-cleanup" -RestorePointType MODIFY_SETTINGS
```
或 `SystemPropertiesProtection` 手动创建。然后按风险从低到高执行。

### 1. 预装 AppX bloatware 移除（Safe，可逆）
```powershell
# 列出所有预装应用
Get-AppxPackage | Select-Object Name, PackageFullName
# 移除常见 bloatware（用户当前账户；不要删 Store/Calculator/Photos 等常用）
Get-AppxPackage *bing* | Remove-AppxPackage
Get-AppxPackage *xbox* | Remove-AppxPackage
Get-AppxPackage *phone* | Remove-AppxPackage    # Phone Link
Get-AppxPackage *copilot* | Remove-AppxPackage  # Win11
Get-AppxPackage *tiktok* | Remove-AppxPackage
Get-AppxPackage *spotify* | Remove-AppxPackage
Get-AppxPackage *clipchamp* | Remove-AppxPackage
```
**可逆**：全部可从 Microsoft Store 重装。Win11Debloat 有完整清单（`references/windows-optimization-projects.md`）。

### 2. 遥测/隐私禁用（Moderate）
```powershell
# 诊断数据降到最低
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection" /v AllowTelemetry /t REG_DWORD /d 0 /f
# 禁用 DiagTrack（连接用户体验与遥测）服务
sc config DiagTrack start= disabled
sc stop DiagTrack
# 广告 ID / 活动历史
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo" /v Enabled /t REG_DWORD /d 0 /f
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\System" /v EnableActivityFeed /t REG_DWORD /d 0 /f
```
需管理员。注意：某些企业版/教育版策略可能覆盖 AllowTelemetry=0。

### 3. Win11 AI 功能禁用（Moderate，仅 Win11 25H2+ 需要）
```powershell
# Copilot / Recall 注册表禁用
reg add "HKCU\Software\Policies\Microsoft\Windows\WindowsCopilot" /v TurnOffWindowsCopilot /t REG_DWORD /d 1 /f
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsAI" /v DisableAIDataAnalysis /t REG_DWORD /d 1 /f
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsAI" /v DisableRecall /t REG_DWORD /d 1 /f
# AI Fabric 服务设为手动
sc config WSAIFabricSvc start= manual
```
完整移除（含 CBS 包防重装）用 zoicware/RemoveWindowsAI 脚本：`irm https://raw.githubusercontent.com/zoicware/RemoveWindowsAI/main/RemoveWindowsAi.ps1`。

### 4. Defender 安全检查（检查项，不修改）
```powershell
# 实时保护状态
Get-MpComputerStatus | Select-Object RealTimeProtectionEnabled, AntivirusEnabled, AntivirusSignatureLastUpdated
# 内存完整性 / VBS 状态
Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\Microsoft\Windows\DeviceGuard
# 攻击面减少规则
Get-MpPreference | Select-Object AttackSurfaceReductionRules_Ids
```
若 RealTimeProtectionEnabled=False → 提示用户开启（设置→隐私和安全性→Windows 安全中心）。**不要**用脚本强制改 Defender 策略（IME/输入法厂商驱动会误伤）。

## 免 UAC 提权（用户已授权全自动时的标准流程）

**背景**：agent 进程是 UAC 过滤令牌（即使账户是 Administrators 成员）。所有提权路径（schtasks /rl HIGHEST、Register-ScheduledTask XML、Set-ScheduledTask 改 Highest 任务、直接写 HKLM UAC 键）全部被拒或静默降级——**没有任何脚本可绕过第一次 UAC 确认**（Windows 安全模型）。唯一合法方案：用户确认一次 UAC，把 `ConsentPromptBehaviorAdmin` 从 5（默认）改为 0（自动提权），此后所有提权静默。

**一次性配置脚本**（`D:\jiasu_setup_once.ps1`，用户右键→以管理员身份运行，或确认 UAC 弹窗一次）：
1. `Set-ItemProperty HKLM:\...\Policies\System ConsentPromptBehaviorAdmin=0` + `PromptOnSecureDesktop=0`
2. 创建还原点 + 遥测/Copilot/Recall 禁用 + 服务设 manual + 系统残留清理 + WU 缓存 + HermesAutoClean 定时任务 + DISM
3. 结果写 `D:\jiasu_admin_result.txt` 供验证（含"jiasu admin done"标记）

**运行前检测**（避免每次弹窗）：
```powershell
(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System').ConsentPromptBehaviorAdmin
```
- =0 → 已配置，直接 `Start-Process powershell -Verb RunAs ... -File <脚本>` 静默执行
- =5 → 未配置，触发 UAC 弹窗并**明确告知用户看屏幕点【是】**（弹窗会超时消失，consent.exe 进程可检测）；用户不在电脑前则提供脚本路径让用户稍后手动运行

**验证**：`D:\jiasu_admin_result.txt` 存在且含 `[OK]` 行。注意 `Checkpoint-Computer` 可能因系统还原未启用而失败（WARN 可接受）。

**陷阱**：Start-Process -Verb RunAs 会阻塞等待确认（前台会超时，用 background=true）；弹窗无人点会静默超时，事件日志无 4624/4672 记录（这是"未确认"特征，不是没弹）。

## 磁盘清理全流程

### Phase 0 — 扫描

**先广扫，再定点。** 固定目录清单会漏掉最大占用者（真实案例：剪映缓存 36GB 不在常规清单里，常规清单只凑出约 10GB）。第一步永远是扫 C 盘和 D 盘的 `USERPROFILE`、`AppData\Local`、`AppData\Roaming`、`Program Files*`、`ProgramData` 的顶层子目录（列出 ≥0.3GB 的），找出真正的占用大户，再决定清理策略。见 `scripts/deep_scan.py`（直接 `python scripts/deep_scan.py` 运行）。

**别忘了 D 盘**：`D:\Program Files` 和 `D:\Program Files (x86)` 也可能有软件安装。夸克浏览器、美图、腾讯会议等常装到 D 盘，旧版本残留同样可清（Quark 双版本各占 1.3GB，只保留最新版）。

### Phase 1 — 安全清理（立即执行，无需询问）

```bash
# pip / npm / uv 缓存
rm -rf "$LOCALAPPDATA/pip/cache"/*
rm -rf "$APPDATA/pip/cache"/*
npm cache clean --force
rm -rf "$LOCALAPPDATA/uv/cache"/*
rm -rf "$LOCALAPPDATA/npm-cache"/*
rm -rf "$APPDATA/npm-cache"/*

# 系统临时文件
rm -rf "$TEMP"/*
rm -rf /c/Windows/Temp/*
rm -rf /c/Windows/Prefetch/*

# 崩溃转储 / 错误报告
rm -rf "$LOCALAPPDATA/CrashDumps"/*
rm -rf "$LOCALAPPDATA/Microsoft/Windows/WER"/*

# 回收站
powershell -NoProfile -Command "Clear-RecycleBin -DriveLetter C -Force -ErrorAction SilentlyContinue"
```

### 系统残留目录清理（Sophia 定时清理清单，安全可删）

Sophia Script 的清理计划任务覆盖以下路径，Phase 1 之后直接清（都是系统升级/安装残留）：

```bash
# Windows 升级残留（安装新版本后产生，可安全删除）
rm -rf '/c/$WinREAgent'/* '/c/$SysReset'/* '/c/$Windows.~WS'/* '/c/$GetCurrent'/* '/c/ESD'/*
# 厂商预装目录（无内容时为空，Intel 驱动安装包等）
rm -rf /c/Intel/* /c/PerfLogs/*
# 网络服务账户的临时目录（普通清理常漏掉）
rm -rf "/c/Windows/ServiceProfiles/NetworkService/AppData/Local/Temp"/*
# SystemProfile 临时文件（tw-*.tmp 是 Windows Update 任务残留）
rm -rf "/c/Windows/System32/config/systemprofile/AppData/Local"/tw-*.tmp
# Recovery 目录下的日志/回收（保留 WinRE 本体，只删明显垃圾）
```

**注意**：`$WinREAgent` 和 `Recovery` 只在确定系统能正常启动后删；`$Windows.~WS` 是 Windows 升级临时目录（升级完成后自动删，残留可手动清）。

### 定时清理任务（Sophia 同款，一次性配置长期生效）

创建计划任务，每周自动清系统临时目录（免手动）：

```powershell
# 每周日 3:00 清 Windows 临时 + 用户临时 + CrashDumps + Windows Update 缓存
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument '/c "del /q /f /s %TEMP%\* 2>nul & del /q /f /s C:\Windows\Temp\* 2>nul & rd /s /q C:\Windows\SoftwareDistribution\Download 2>nul & mkdir C:\Windows\SoftwareDistribution\Download & del /q /f /s C:\Windows\Prefetch\* 2>nul"'
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 3am
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
Register-ScheduledTask -TaskName "HermesAutoClean" -Action $action -Trigger $trigger -Settings $settings -Force -RunLevel Highest
```
在 bash/MSYS 中执行需写成 `.ps1` 文件再 `powershell -File`（见陷阱 #1）。

### Hermes 每日自动清理（cron，每天凌晨2点）

在 Hermes 里创建 cron 任务，每天凌晨 2 点自动跑一遍**免 UAC 清理**，早晨出报告。标准配置：

```
schedule: "0 2 * * *"
skills:   ["jiasu"]
prompt:   执行 jiasu 技能每日自动清理（免 UAC 模式）：
          1. 运行 scripts/deep_scan.py 广扫 + 记录清理前可用空间
          2. Phase 1 安全清理（pip/npm/uv 缓存、TEMP、Windows Temp、Prefetch、CrashDumps/WER、回收站）
          3. 剪映 User Data/Cache（绝不动 Projects）、浏览器 Cache/Code Cache/GPUCache、
             微信/QQ Image/Video/File 缓存、系统残留目录（$WinREAgent 等）
          4. Hermes/Codex 自有缓存（logs/screenshots、.codex/logs_2.sqlite 等）
          5. 跳过所有需管理员操作（服务禁用、DISM、pagefile、注册表策略、计划任务创建）
          6. 报告：逐项释放 GB + 总量 + 清理后剩余空间（中文简明）
```

**cron 无人值守注意**：
- 只跑免 UAC 部分；管理员操作依赖一次性配置（`ConsentPromptBehaviorAdmin=0`，见"免 UAC 提权"），未配置时全部跳过
- `deep_scan.py` 等脚本在技能目录 `scripts/` 下，cron prompt 里用绝对路径引用（如 `C:\Users\<user>\AppData\Local\hermes\skills\devops\jiasu\scripts\deep_scan.py`）
- 被进程锁定的文件（Python 缓存、mcp-stderr.log）跳过即可，不要强删（见陷阱 #7）
- Hermes cron 版与任务计划程序版（HermesAutoClean 每周日）可并存，互不冲突

### AppData Junction 迁移（WindowsClear 同款，C盘瘦身神器）

大软件（微信/QQ/剪映/浏览器）的 AppData 数据动辄 10-30GB，**迁到 D 盘 + 原位建 Junction 链接**，软件无感（以为还在 C 盘），无需改环境变量。这是 WindowsClear 的核心方案，比 setx 更彻底。

**mklink /J（junction）在 PowerShell 中可正常使用**——之前技能里"mklink 失败"是 git-bash/MSYS 编码问题，用 PowerShell 或 Python 绕开：

```powershell
# 1. 先关软件 → 移动目录（示例：微信数据）
# robocopy /MOVE 带重试，比 move 稳
robocopy "C:\Users\xxx13\Documents\WeChat Files" "D:\AppDataMoved\WeChat Files" /E /MOVE /R:2 /W:1
# 2. 原位建 junction（对应用透明）
New-Item -ItemType Junction -Path "C:\Users\xxx13\Documents\WeChat Files" -Target "D:\AppDataMoved\WeChat Files"
```

```python
# 或用 Python（execute_code 运行，junction 不需要管理员/开发者模式）
import os
os.symlink(r"D:\AppDataMoved\WeChat Files", r"C:\Users\xxx13\Documents\WeChat Files",
           target_is_directory=True)  # Windows 10 1703+ 支持 junction
```

**适用对象**：微信/QQ 聊天数据、剪映 User Data（**先确认 Cache 已清再迁**）、浏览器 User Data、WPS、网盘下载目录。
**红线**：只迁纯数据目录；不迁 Program Files、Windows、.venv 基底、含 DLL/驱动/服务的目录。迁移后验证软件能开再删备份；回滚 = 删 junction + 文件移回。

### 剪映 / 创意软件缓存（视频创作者的头号占用，安全清理）

抖音/视频创作者的 C 盘头号占用往往是**剪映 JianyingPro**，而非常规缓存。
真实案例：剪映缓存 31.79GB（其中语音识别缓存 `recognize` 独占 29.7GB）。

```bash
# 剪映缓存（纯缓存，删后按需自动重建，绝不碰草稿工程）
rm -rf "$LOCALAPPDATA/JianyingPro/User Data/Cache"/*
#   recognize    — 语音识别缓存（最大，常 20-30GB）
#   audioWave    — 音频波形缓存
#   AITextTemplate / effect — AI/特效缓存
# 旧版本 App：Apps/ 下保留版本号最高的一个，删其余（每个 0.4-2GB）
```

**关键红线：`User Data\Cache` 是缓存可删；`User Data\Projects`（草稿工程）绝不能删！**
清理前先确认 Cache 目录里只有 recognize/audioWave/AITextTemplate/effect 这类缓存子目录，
不含 draft/project 字样。`SupplysStore\local-asr-supplies`（ASR 模型）建议保留。

其他创意软件同类缓存：美图 MeituApp、WPS Kingsoft、飞书 Feishu/LarkShell、ima.copilot、
TRAE、百度 baidu 都常有 GB 级缓存目录，广扫命中后按同样逻辑（区分缓存 vs 用户数据）处理。

### Hermes / Codex 自有缓存清理

```bash
# Hermes 缓存（~/.hermes/ 下）
rm -rf "$USERPROFILE/.hermes/logs/screenshots"/*    # 浏览器截图缓存
rm -rf "$USERPROFILE/.hermes/logs/gateway_stdout.log" # 网关输出
rm -f "$USERPROFILE/.hermes/logs"/*.log.[1-9]        # 旧轮转日志
rm -rf "$USERPROFILE/.hermes/tmp"/*                   # 发布/分析临时文件
rm -rf "$USERPROFILE/.hermes/sessions"/*.json         # 旧会话 dump（不是活跃 state.db）
rm -rf "$USERPROFILE/.hermes/cache/terminal"/*        # 终端缓存
# 浏览器缓存（Hermes 内置浏览器 profile）
for bp in "$USERPROFILE/.hermes/browser-profiles"/*; do
  for sub in "Cache" "Code Cache" "GPUCache" "DawnGraphiteCache" "DawnWebGPUCache" "DeferredBrowserMetrics"; do
    rm -rf "$bp/Default/$sub"/* 2>/dev/null
  done
done

# Codex CLI 缓存（.codex 下）
rm -f "$USERPROFILE/.codex/logs_2.sqlite"            # 日志（常 200-300MB）
rm -f "$USERPROFILE/.codex/logs_2.sqlite-wal"
rm -rf "$USERPROFILE/.codex/.tmp"/*                   # 临时文件
rm -rf "$USERPROFILE/.codex/generated_images"/*       # 旧生成图片（200-500MB）
```

Hermes 的 `mcp-stderr.log` 可能被运行中进程锁定（常 40-50MB），重启 Hermes 后自动轮转。
Codex CLI 的 `sessions/`、`plugins/` 目录包含会话历史和插件，不要删除。

### 浏览器缓存（Chrome / Edge，安全可重建）

```bash
for sub in "Cache" "Code Cache" "GPUCache" "Service Worker" "DawnGraphiteCache" "DawnWebGPUCache"; do
  rm -rf "$LOCALAPPDATA/Google/Chrome/User Data/Default/$sub"/*
  rm -rf "$LOCALAPPDATA/Microsoft/Edge/User Data/Default/$sub"/*
done
```

### Phase 2 — .cache 大文件迁移到D盘

`.cache` 通常是最大占用者（huggingface 模型 3-5GB+、codex-runtimes 1-2GB）。

**⚠ 迁移前必做检查**：`codex-runtimes` 中的 Python 可能是当前 `.venv` 的基底。
先用 Python 检查当前 venv 是否依赖它：
```python
import sys
print(sys._base_executable)  # 如果指向 .cache/codex-runtimes/.../python.exe，跳过它！
```
如果 `_base_executable` 指向 `codex-runtimes` 路径，**只迁移其他子目录**
（huggingface, torch, modelscope, opencode 等），不要碰 `codex-runtimes`。
强行迁移会立即破坏当前 venv（症状：`python --version` 正常但任何 import 报
`ModuleNotFoundError: No module named 'encodings'`）。详见 Pitfall #9。

```bash
# 先拷贝到D盘，再删除原文件
mkdir -p /d/cache_backup/

# 安全迁移：跳过 codex-runtimes（如果被 venv 依赖）
cp -r "$USERPROFILE/.cache/huggingface" /d/cache_backup/huggingface
rm -rf "$USERPROFILE/.cache/huggingface"
# 同理处理 torch, modelscope, opencode 等
# codex-runtimes 只在确认不被 venv 依赖时才迁移
```

然后设置环境变量引导工具使用D盘（**不要用 mklink 符号链接**，在 git-bash/MSYS 下会因编码问题失败）：

```bash
setx HUGGINGFACE_HUB_CACHE "D:\cache_backup\huggingface\hub"
setx HF_HOME "D:\cache_backup\huggingface"
setx PIP_CACHE_DIR "D:\cache_backup\pip"
setx UV_CACHE_DIR "D:\cache_backup\uv"
setx TORCH_HOME "D:\cache_backup\torch"
# 新终端窗口生效
```

### Phase 3 — Windows Update 缓存清理

```bash
net stop wuauserv
rm -rf /c/Windows/SoftwareDistribution/Download/*
rm -rf /c/Windows/SoftwareDistribution/DeliveryOptimization/*
net start wuauserv
```

### Phase 4 — 虚拟内存 pagefile.sys 迁移（需管理员 + 重启）

pagefile.sys 常见大小 = RAM 的 0.75~2x（16GB RAM → 12-20GB pagefile）。
Agent 终端通常无管理员权限，用 `references/pagefile_migrate.ps1` 弹 UAC 授权：
```bash
powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File <脚本路径>'"
```
或告知用户手动：Win+R → `sysdm.cpl` → 高级 → 性能设置 → 高级 → 虚拟内存更改。

### 微信/QQ 缓存清理

```bash
find "$APPDATA/Tencent" -type d -name "Image" -exec rm -rf {}/* \;
find "$APPDATA/Tencent" -type d -name "Video" -exec rm -rf {}/* \;
find "$APPDATA/Tencent" -type d -name "File" -exec rm -rf {}/* \;
```

### 腾讯电脑管家自身缓存（本机装了 QQPCMgr 时可清）

```bash
rm -rf "$APPDATA/Tencent/QQPCMgr/radiumv3"/*      # 0.3-1GB 缓存
rm -rf "$APPDATA/Tencent/QQPCMgr/beacon"/*
rm -rf "$APPDATA/Tencent/QQPCMgr/Download"/*
rm -rf "$APPDATA/Tencent/QQPCMgr/QMLauncher"/*
rm -rf "$LOCALAPPDATA/Tencent/QQPCMgr/cef_cache_qmui"/*
rm -rf "$LOCALAPPDATA/Tencent/QQPCMgr/cef_cache_qmaiservice64"/*
```
**注意**：不要删 `$APPDATA/Tencent/QQPCMgr/SysOpt.ini`、`sysdeepopt.ini`（启动加速策略配置，删了加速功能失效）。

## 开机加速四件套（腾讯管家式，新增）

腾讯管家开机加速 = 延迟启动 + 服务禁用 + DNS 优化 + 内存整理。以下是同等效果的手动/脚本化实现。

### 1. 启动项清单（先查后改）

```bash
# 四个启动位置
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
reg query "HKLM\Software\Microsoft\Windows\CurrentVersion\Run"
reg query "HKLM\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"
ls "$APPDATA/Microsoft/Windows/Start Menu/Programs/Startup"
```

分类原则：
- **保留**：输入法、杀毒软件、显卡驱动、硬件工具（必要且轻量）
- **延迟 30-60s**：网盘（百度网盘/OneDrive）、云同步（ima.copilot/WPS）、聊天（QQ/微信）、播放器后台
- **禁用**：明显不需要的自启（旧软件残留、推广项、`--startup-foreground-launch` 类）

### 2. 错峰延迟启动（腾讯管家 StartupDelayList.dat 同款）

用任务计划程序创建 onlogon 延迟任务，然后把原 Run 键项删掉：

```powershell
# 示例：百度网盘延迟 30 秒启动（schtasks 的 /delay 参数支持 onlogon 触发器）
schtasks /create /tn "DelayStart_BaiduNetdisk" /tr "\"C:\Program Files (x86)\Baidu\BaiduNetdisk\BaiduNetdisk.exe\" AutoRun" /sc onlogon /delay 0000:00:30 /f
```
路径含空格时 `/tr` 内用 `\"` 转义。bash 中执行需包一层：`cmd //c 'schtasks /create ...'` 或写成 `.ps1`。
删除原启动项：
```bash
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v BaiduYunGuanjia /f
```
回滚：`schtasks /delete /tn "DelayStart_BaiduNetdisk" /f` + reg add 恢复原值。

### 3. 服务禁用/设手动（参考 sysdeepopt.ini 实测清单）

腾讯管家实测会把以下服务降级为手动（本机 `%APPDATA%/Tencent/QQPCMgr/sysdeepopt.ini` 实锤）：
wpscloudsvr（WPS云服务）、edgeupdate / edgeupdatem / microsoftedgeelevationservice（Edge更新）、mtxxservice（美图）等。

安全做法：**更新类/云同步类服务设 `manual`**（要用时按需拉起），不要轻易 `disabled`：

```powershell
sc config wpscloudsvr start= manual
sc config edgeupdate start= manual
sc config edgeupdatem start= manual
sc config mtxxservice start= manual
```
需管理员（UAC）。先 `sc query wpscloudsvr` 确认服务存在。**红线**：不动杀毒、驱动、Windows 核心服务（wuauserv 除外，见 Phase 3）。

### 4. DNS 优化（可选，需管理员）

```powershell
# 先看当前 DNS 和网卡名
ipconfig /all
# 阿里 223.5.5.5 主 + 腾讯 119.29.29.29 备
netsh interface ip set dns name="以太网" static 223.5.5.5
netsh interface ip add dns name="以太网" 119.29.29.29
```
网卡名可能是中文（"以太网"/"WLAN"），用 `ipconfig` 输出确认。对普通上网感知提升有限，主要对 DNS 解析慢/污染场景有效。

### 5. 内存整理（可选，收益有限）

现代 Windows 内存管理已足够好，腾讯管家的 MemDefrag 主要是清空空闲进程工作集（EmptyWorkingSet），感知收益有限。用户坚持要时：
```powershell
# 清空指定进程的工作集（释放物理内存，进程会按需重新申请）
Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public class M{[DllImport("psapi.dll")]public static extern bool EmptyWorkingSet(IntPtr h);}'
Get-Process | Where-Object {$_.WorkingSet64 -gt 500MB} | ForEach-Object { [M]::EmptyWorkingSet($_.Handle) }
```
默认跳过此项，先做前两项。

### 6. 服务微调清单（optimizerDuck 同款，200+ 服务精选安全项）

以下服务按"更新类/云同步类/遥测类"设 `manual`（要用时按需拉起），**不动杀毒/驱动/核心服务**：

```powershell
# 更新/遥测类（安全设 manual）
sc config wpscloudsvr start= manual        # WPS云服务
sc config edgeupdate start= manual         # Edge 更新
sc config edgeupdatem start= manual
sc config mtxxservice start= manual        # 美图
sc config DiagTrack start= manual          # 遥测（若安全章节没禁）
sc config dmwappushservice start= manual   # WAP推送消息路由（遥测相关）
sc config MapsBroker start= manual         # 离线地图（不常用）
sc config WSearch start= manual            # Windows Search 索引（可选，老机器省资源，搜索变慢）
sc config SysMain start= manual            # Superfetch（HDD 机可关，SSD 无收益）
sc config Fax start= manual
sc config XblAuthManager start= manual     # Xbox（不玩游戏）
sc config XblGameSave start= manual
sc config XboxNetApiSvc start= manual
```

**红线**：不碰 `WinDefend`、`SecurityHealthService`、`wuauserv`（更新缓存清理时临时停）、驱动服务、`AppXSvc`。
服务名以 `sc query` 实际结果为准，不存在的跳过。

### 7. 菜单延迟/视觉特效（Moderate，低风险提速感知）

```powershell
# 菜单显示延迟归零（右键/开始菜单更跟手）
reg add "HKCU\Control Panel\Desktop" /v MenuShowDelay /t REG_SZ /d 0 /f
# 关闭动画/透明度（桌面右键→个性化→性能设置同款，注册表直接改）
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v TaskbarAnimations /t REG_DWORD /d 0 /f
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" /v EnableTransparency /t REG_DWORD /d 0 /f
# 视觉效果整体调为"调整为最佳性能"（会关掉毛玻璃/动画，老机器明显）
```

### 8. 快速启动/休眠（Win11Debloat + optimizerDuck 共识）

```powershell
# 禁用休眠（释放 hiberfil.sys，大小≈RAM 40-75%）
powercfg /h off
# 禁用快速启动（保证完整关机，修复部分驱动/双系统问题；代价是冷启动略慢）
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power" /v HiberbootEnabled /t REG_DWORD /d 0 /f
```
**注意**：这条与"开机加速"目标表面矛盾——快速启动会让"关机后再开机"变快，但会拖慢"重启"且积累系统状态。SSD 机器推荐禁用（完整冷启动也就几秒），HDD 机器保留。

### 9. 系统盘压缩（simeononsecurity diskcompression，省 5-15GB）

```bash
# 压缩 C 盘（对 NTFS 文件透明，读写略降但 SSD 无感知）
compact /c /s /i /q C:\
# 或只压缩 Program Files（风险更低）
compact /c /s /i /q "C:\Program Files"
compact /c /s /i /q "C:\Program Files (x86)"
```
**红线**：不压缩 Windows 目录本体（易出兼容问题）、不压缩含虚拟磁盘/数据库的目录（性能损耗大）。

### 加速结果验证

```bash
# 开机时间（上次开机到现在的秒数）
powershell -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime"
# 或事件日志 100 号事件（启动耗时，毫秒）
powershell -NoProfile -Command "Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Diagnostics-Performance/Operational';Id=100} -MaxEvents 1 | Select-Object -ExpandProperty Message"
```

## DISM 组件清理（Windows Update 备份）

```bash
DISM /online /Cleanup-Image /StartComponentCleanup /ResetBase   # 需管理员
```

## 软件使用审计（找出长期未用的软件）

`scripts/audit_unused_software.ps1` 扫描注册表已装软件 + 安装目录/exe 最后修改时间估算使用时间，
输出三类：60天以上未使用 / 活跃使用 / 无法判断。
```bash
powershell -File scripts/audit_unused_software.ps1 -JsonOut   # 输出 JSON 防乱码，再用 Python 分析
```
**注意**：文件修改时间 ≠ 实际使用时间（自动更新会刷新 mtime）。Edge、VS Installer、FFmpeg 可能被误归类，需人工判断。
常见可卸载：TIM、360压缩、悟空(Wukong)、VS Installer。无卸载程序的软件（如悟空）需手动清注册表+删文件夹（见下）。

## 广扫后的钻查目标（按软件分类）

| 软件 | 路径模式 | 可删（缓存） | 不可删（用户数据/核心） |
|------|----------|-------------|----------------------|
| 剪映 | `JianyingPro/User Data/Cache/*` | recognize, audioWave, AITextTemplate, effect, GeckoCpp, image, fontImage 等全部子目录 | `User Data/Projects`（草稿工程） |
| 美图秀秀 | `MeituApp/XiuXiu/<version>` | 只保留最新版本号目录，删其余 | 最新版本目录 |
| WPS | `Kingsoft/WPS Office/<version>` | 只保留最新版，删其余 | 最新版本目录 |
| WPS | `kingsoft/wps/addons/pool` | 全部（模板池，按需重下载） | `addons/data`（用户数据） |
| 微信 | `Tencent/xwechat/radium/users` | 全部（小程序用户缓存） | — |
| 微信 | `Tencent/xwechat/radium/web` | 全部（WebView 缓存） | — |
| 微信 | `Tencent/xwechat/XPlugin/Plugins` | — | RadiumWMPF, WeChatPlayer 等（核心插件） |
| 腾讯会议 | `Tencent/WeMeet/Global/Data/DynamicResource*` | 全部（按需重下载） | Global/Database（用户数据库） |
| 腾讯会议 | `Tencent/WeMeet/Global/Data/AudioModel` | 全部 | — |
| 腾讯会议 | `Tencent/WeMeet/Global/Data/AvatarModel` | 全部 | — |
| 百度网盘 | `baidu/BaiduNetdisk/module` | — | BrowserEngine, ImageViewer 等（程序模块，不可删） |
| Codex CLI | `.codex/logs_2.sqlite`, `.codex/.tmp`, `.codex/generated_images` | 全部可删（日志+临时+旧图片，常 500MB+） | `sessions/`, `plugins/`（会话和插件） |
| 360安全 | `secoresdk/360se6`（Roaming） | 全部（0.3-0.5GB，SDK缓存） | — |
| ima.copilot | `ima.copilot/User Data/reshub` | 全部 | — |
| ima.copilot | `ima.copilot/User Data/component_crx_cache` | 全部 | — |
| npm | `npm/node_modules`（Roaming 下） | 全部（全局包，可重装） | — |
| TRAE | `TRAE SOLO CN/ModularData/ai-agent/vm` | — | VM 镜像（核心功能） |
| ms-playwright | `ms-playwright/<browser>-<version>` | 每种浏览器只保留版本号最大的，删其余 | 最新版本 |
| QQ电脑管家 | `Tencent/QQPCMgr/radiumv3`（Roaming） | 全部（0.3-1GB 缓存） | `SysOpt.ini`/`sysdeepopt.ini`（加速策略） |
| QQ电脑管家 | `Tencent/QQPCMgr/cef_cache_*`（Local） | 全部（CEF浏览器缓存） | — |
| GreenCore7z | `GreenCore7z`（Roaming） | 全部（压缩软件缓存，0.3-0.5GB） | — |

## 常见陷阱

### 1. PowerShell 在 git-bash/MSYS 中文编码乱码
绝不要在 terminal 工具的 bash 中内联 PowerShell 脚本。正确做法：写成 `.ps1` 文件 → `powershell -File` 执行，或改用 Python。

### 2. Python 路径解析问题
当 `.cache/codex-runtimes` 中有 python.exe 时，PATH 可能解析到它而非系统 Python。
解决：使用完整路径 `/c/Users/xxx13/AppData/Local/Programs/Python/Python312/python.exe`。

### 3. mklink 符号链接在 git-bash/MSYS 失败，但 junction 可用
`cmd //c 'mklink /D ...'` 在中文 Windows + MSYS 下因编码问题经常失败。
**替代方案**：
- 迁移缓存 → 用 `setx` 环境变量重定向（不依赖文件系统链接）
- 迁移 AppData 大目录 → 用 **Junction**（`mklink /J`，见"AppData Junction 迁移"章节）：
  PowerShell `New-Item -ItemType Junction -Path <原路径> -Target <目标>` 或 Python `os.symlink(..., target_is_directory=True)`，均可绕开 MSYS 编码坑。Junction 不需要管理员（Win10 1703+）。

### 4. wmic pagefile 操作需要管理员权限
改为告知用户手动操作或 UAC 提权脚本。

### 5. hiberfil.sys 休眠文件
```bash
powercfg /h off   # 禁用休眠，释放 hiberfil.sys（大小≈RAM 的 40-75%）
```

### 6. ProgramData\Application Data 假 200GB
`C:\ProgramData\Application Data` 是指向 ProgramData 自身的 junction（旧版兼容），
递归扫描会算出上百 GB 的假占用。**扫描时直接跳过 `Application Data` / `Local Settings` 这类 junction 名。**

### 7. Python 删除比 bash rm 更稳
中文路径、超长路径、只读文件用 bash `rm -rf` 常失败。改用 Python
`shutil.rmtree(path, onerror=handler)`，handler 里先 `os.chmod(path, stat.S_IWRITE)` 再重删。
用 `GetDiskFreeSpaceExW` 量清理前后可用空间，逐项报告释放的 GB，输出更可信。

**安全递归删除模板**（跳过被进程锁定的文件）：
```python
def rm_handler(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def safe_rmtree(path):
    skipped = 0
    try:
        with os.scandir(path) as it:
            for e in it:
                try:
                    if e.is_file(follow_symlinks=False):
                        os.chmod(e.path, stat.S_IWRITE)
                        os.unlink(e.path)
                    elif e.is_dir(follow_symlinks=False):
                        safe_rmtree(e.path)
                        try:
                            os.rmdir(e.path)
                        except OSError:
                            skipped += 1
                except (PermissionError, OSError):
                    skipped += 1
    except (PermissionError, OSError):
        skipped += 1
```

### 8. 不要在 terminal 工具中内联 Python 脚本
git-bash/MSYS 中内联 Python 代码时反斜杠会被 bash 预处理导致语法错误。
**最佳做法**：用 `execute_code` 工具运行 Python 脚本（完全避开 MSYS 路径转换）。
**备选**：`write_file` 写成 `.py` → `terminal` 执行。脚本存放位置不要放 `%TEMP%`（Phase 1 会清），放 `%USERPROFILE%` 或项目目录。
**MSYS 路径转换陷阱**：工作目录在 D 盘时 `/c/Users/...` 会被自动转换为 `D:\c\Users\...`（不存在），改用 `cmd //c "..."` 加完整 Windows 路径。
**raw-string 陷阱**：`r"C:\"` 以反斜杠结尾时 `\"` 被解析为转义引号导致语法错误，改用 `"C:/"`。

### 9. 部分删除 Python 运行时会破坏依赖它的虚拟环境
当 `.cache/codex-runtimes` 中的 Python 被部分删除时，基于该 Python 创建的 `.venv` 会彻底失效——
`python --version` 仍能输出，但任何 import 都报 `ModuleNotFoundError: No module named 'encodings'`。
**修复**：从 D 盘备份恢复被删目录（先 `rm -rf` 残留再 `cp -r`）。

### 10. PowerShell 输出到文件再读取避免编码乱码
含中文的 `ConvertTo-Json` 输出会因 UTF-16LE → UTF-8 转换乱码。
正确做法：PowerShell 脚本中用 `Out-File -Encoding UTF8` 写 JSON 文件，Python 用 `encoding='utf-8-sig'` 读取。

### 11. 卸载没有卸载程序的软件（如悟空 Wukong）
部分软件（尤其国产）注册表有 DisplayName 但没有 UninstallString，winget 也无法卸载。
```powershell
reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall" /s /f "关键字"
Start-Process cmd -Verb RunAs -ArgumentList '/c rd /s /q "C:\Program Files\XXXX" && reg delete "HKLM\SOFTWARE\WOW6432Node\...\Uninstall\XXXX" /f' -Wait
```
有 UninstallString 的软件直接用注册表中的卸载命令。

## 参考脚本

- `scripts/daily_clean_no_uac.py` — 每日免 UAC 自动清理脚本（cron 复用）：测量→安全删除→逐项报告释放 GB，覆盖包缓存/临时文件/剪映/浏览器/微信QQ/QQPCMgr/ima/Hermes/Codex 缓存，跳过被锁定文件与需管理员项
- `scripts/deep_scan.py` — 顶层目录广扫，找出真实占用大户（剪映/美图等），跳过 junction
- `scripts/find_installed_apps.py` — 查找软件安装位置（卸载前确认所有残留路径）
- `scripts/audit_unused_software.ps1` — 软件使用审计（60天未用清单）
- `references/disk_scan.py` — C盘关键目录占用扫描
- `references/pagefile_migrate.ps1` — pagefile 迁移到 D 盘（需管理员）
- `references/qqpcmgr-feature-map.md` — 腾讯电脑管家逆向笔记（功能地图/方法论）
- `references/windows-optimization-projects.md` — GitHub 优质清理/加速/安全项目调研（Win11Debloat/Sophia/optimizerDuck/WindowsClear/RemoveWindowsAI 等，含抓取技巧）
