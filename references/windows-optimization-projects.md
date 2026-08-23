# Windows 清理/加速/安全优质开源项目调研 — 提炼笔记

来源：2026-08-02 GitHub API 搜索（web_search/web_extract 因 Tavily 401 不可用，改用 GitHub API + raw 抓取，走本机代理 127.0.0.1:15715）。

## 项目清单与要点

### 1. Raphire/Win11Debloat (54k★) — 去预装应用/关遥测
PowerShell 单脚本，可逆。核心能力：
- 移除预装 AppX 应用（Bing、GameBar、PhoneLink 等）
- 禁用遥测/诊断数据/活动历史/广告 ID/定位
- 禁用 Copilot、Windows Recall、Click to Do（AI 三件套）
- 禁用视觉效果（透明度/动画）提升响应
- 禁用 Storage Sense、禁用快速启动（保证完整关机）
- 恢复旧式右键菜单（Win11 用户喜欢）
- 全部可 revert（几乎都能从 Store 重装）

### 2. farag2/Sophia-Script-for-Windows (9.6k★) — 150+ 官方文档化配置
最权威的 Windows 微调模块（2014 年至今，全部用微软官方 API/注册表）。
**定时清理任务**（最值得抄）——创建计划任务定期清理：
- `%SystemDrive%\$WinREAgent`、`$SysReset`、`$Windows.~WS`、`$GetCurrent`、`ESD`
- `%SystemDrive%\Intel`、`PerfLogs`、`Recovery`
- `%SystemRoot%\ServiceProfiles\NetworkService\AppData\Local\Temp`
- `%LOCALAPPDATA%\CrashDumps`
- `%SystemRoot%\System32\config\systemprofile\AppData\Local\tw-*.tmp`
- `%SystemRoot%\SoftwareDistribution\Download`（单独任务）
- 另建 Temp 任务清临时目录
- 每个函数都有恢复默认对应函数（**可逆性是标配**）
- 移动用户文件夹位置（Desktop/Documents/Downloads/Music/Pictures/Videos，不移动文件只改注册表指向）
- 卸载 UWP 应用时显示本地化包名
- DNS-over-HTTPS 一键启用（Cloudflare/Google/Quad9/AdGuard/OpenDNS）
- 安装 VC++ 2015-2026 x86/x64 + .NET Desktop Runtime

### 3. simeononsecurity/Windows-Optimize-Harden-Debloat (1.4k★) — STIG 级安全加固
DoD STIG + NSA 建议的自动化。安全侧最全：
- 参数化运行（-windows -defender -firewall -removebloatware -disabletelemetry -privacy -imagecleanup -diskcompression 等 30+ 开关）
- **先要求系统还原点/备份**（方法论）
- BitLocker 加固（需先关再开）、禁用 RDP、禁用 Thunderbolt
- Sysmon 审计、PowerShell 日志加固、SMB/SSL 加固
- AppLocker（audit only）、Device Guard/VBS
- **diskcompression：压缩系统盘**（compact /c，可省 5-15GB）
- 注意：重口味，仅个人电脑用默认项，STIG 项（禁用 Administrator/PIN/Microsoft 账户）不适合普通用户

### 4. itsfatduck/optimizerDuck (7.6k★) — 优化工具（风险分级 + 可逆）
.NET 单 exe，30+ tweaks / 6 类。最值得抄的设计：
- **每次更改写 revert 文件**（%LocalAppData%\optimizerDuck\Revert\），一键回滚
- **风险评级**：每个 tweak 标 Safe/Moderate/Risky
- 200+ Windows 服务启动类型微调（Bloatware & Services 类）
- Service host 分组调优（按 RAM）、进程优先级、键盘延迟、多媒体调度器
- 禁用休眠 + 快速启动、USB 选择性暂停、自定义高性能电源计划、关电源节流
- MenuShowDelay 归零（菜单显示延迟）、禁视觉特效
- GPU 注册表 tweak（AMD/NVIDIA/Intel 电源状态/时钟门控/显示延迟）
- 内置 Startup Manager / Scheduled Tasks / Disk Cleanup / Bloatware Remover（AppX 带风险徽章）

### 5. tanaer/WindowsClear (979★) — C盘 AppData Junction 迁移
Rust 写的 C 盘瘦身工具，**核心是 junction 迁移**：
- 扫 %LOCALAPPDATA% + %APPDATA% 找 >10% 占用大户 → 迁到 D 盘 → 原位建 Junction 链接
- Junction 对应用透明（软件以为还在 C 盘），无需重配环境变量
- Restart Manager 自动结束占用进程；迁移失败自动回滚
- **对我们技能的启示**：之前 SKILL.md 说"不要用 mklink"是因为 git-bash/MSYS 里 `cmd //c mklink` 中文编码失败。但 mklink /J（junction，非符号链接）本身可用：用 PowerShell `New-Item -ItemType Junction` 或 Python `os.symlink(target, link, target_is_directory=True)`（Windows 10 1703+ junction 不需要管理员/开发者模式）可绕开编码问题。

### 6. zoicware/RemoveWindowsAI (12.6k★) — 移除 Win11 AI 功能
Win11 25H2 起 AI 功能越来越多，脚本全移除：
- 禁用 Copilot/Recall/Input Insights/Copilot in Edge/Paint AI/照片 AI 等 14 类注册表项
- 移除 AI AppX 包（含 Nonremovable）+ CBS 组件存储里的 AI 包
- 自装 Windows Update 包防止 AI 功能被重装
- 建计划任务：更新后检查并再次移除
- 仅 Win11 25H2+ 需要；Win10 用户跳过

### 7. BCUninstaller/Bulk-Crap-Uninstaller (20k★) — 批量卸载残留清理
GUI 批量卸载器。卸载后深度扫描残留（注册表+文件+服务），检测隐藏/孤儿应用。

### 8. ChrisTitusTech/winutil (60.7k★) — 一站式 Windows 工具（2026-08-24 新增调研）
PowerShell 模块化脚本（MIT），最活跃的 Windows 优化项目。四个主 tab：
- **Install**：winget 批量安装/卸载常用软件（curated 列表，Get Installed 反查已装）
- **Tweaks**：预设配置文件（Microsoft/Standard/Hardcore 分级）、一键套用/还原
- **Fixes**（最值得抄）：SFC /scannow、DISM RestoreHealth、Windows Update 修复（重置服务+缓存）、网络栈重置、打印机修复、.NET 修复
- **Updates**：Windows 更新策略控制（暂停/阻止/恢复）
- 社区驱动：PR 持续并入新 tweak（如 Edge 移除、Copilot 移除、地理位置服务禁用）

### 9. hellzerg/optimizer (18.3k★) — Windows 优化器（2026-08-24 新增调研）
.NET 单 exe（GPL-3.0），网络/系统/隐私全功能。最值得抄的：
- **DNS 工具**：ping 测延迟、SHODAN IP 查询、预设 DNS 快速切换、flush DNS
- **文件锁句柄识别终止**（Identify file lock handles）——清理"占用中"文件的标准答案
- HOSTS 编辑、系统变量路径编辑、右键菜单自定义、Run 对话框自定义命令
- **静默运行模板文件**（silent run using a template）——脚本化无人值守
- Office 遥测禁用、HPET 禁用、UTC 时间、Defender 禁用（safe-mode 方案）
- 停 Windows 自动更新（10/11）

### 10. Chuyu-Team/Dism-Multi-language (20.2k★) — Dism++（2026-08-24 新增调研）
国产老牌系统工具（2022 后停更但规则持续维护）。最值得抄的：
- **空间回收 = 可扩展清理规则库**：清理规则是数据文件，用户可加规则（如新增"NuGet 包缓存"规则）；自动判断环境跳过不适用的
- 系统备份/还原、启动项管理、Appx 管理、驱动/更新管理、镜像处理
- 注意：非 Windows 原生 API 多，Chris Titus 建议安全环境慎用；对我们价值在规则库设计而非工具本身

### 11. builtbybel/Bloatynosy (5.6k★) + Winpilot（2026-08-24 新增调研）
Win11 去臃肿 GUI，MIT。核心：OOBE 后一键配置助手（Fresh11）、插件引擎、debloat 能力深度集成。思路：装机后"一键全部配置" vs 我们的一次性配置脚本（ConsentPromptBehaviorAdmin=0 + 还原点 + 清理任务），方向一致可互相印证。

### 12. arsenetar/dupeguru (~4k★) + jdupes（2026-08-24 新增调研）
重复文件查找（跨平台，Python）。三种模式：Files（SHA-256 内容哈希）、Picture（感知哈希+EXIF）、Music（AcoustID 指纹）。分层过滤（大小→哈希→内容）保证速度；删除默认进回收站+预览确认。jdupes 是 C 实现 CLI 版。思路已并入 `find_duplicates.py`（三级过滤哈希、默认只列、--move-to 回收区）。

## 提炼整合建议（已并入 jiasu）

| 来源 | 并入 jiasu 的内容 |
|---|---|
| Sophia | 定时清理任务清单（$WinREAgent/$SysReset/$Windows.~WS/$GetCurrent/ESD/PerfLogs/NetworkService Temp/tw-*.tmp）+ 计划任务方案 |
| WindowsClear | Junction 迁移 AppData 大文件夹（PowerShell New-Item -ItemType Junction 方案，绕开 MSYS 编码坑）|
| optimizerDuck | 可逆性方法论（改前导出 reg 备份）、风险分级、服务微调清单、MenuShowDelay/视觉特效/快速启动、电源计划 |
| Win11Debloat | AppX bloatware 移除命令、AI 功能禁用（Copilot/Recall）|
| simeononsecurity | 先建还原点、Defender 安全检查、compact /c 压缩系统盘 |
| RemoveWindowsAI | Win11 AI 注册表禁用键清单（仅 25H2+）|
| winutil (60.7k★) | 系统修复工具集（SFC/DISM RestoreHealth/WU 重置/网络重置 → system_repair.ps1）；winget 批量卸载（uninstall_by_audit.py）|
| hellzerg/optimizer (18.3k★) | DNS 备份/预设/延迟测试/恢复（dns_tool.py）；锁文件句柄查询（find_locked_by.py，Restart Manager API）|
| Dism++ (20.2k★) | 清理规则数据化（rules.json，deep_scan --rules 自动匹配，新增软件只改规则文件）|
| Sophia | 用户文件夹 Known Folder 重定向（redirect_known_folders.ps1，-Undo 可逆）|
| dupeGuru/jdupes | 重复文件扫描（find_duplicates.py，三级过滤哈希，默认只列不删）|

**可逆性统一保障（2026-08-24）**：backup_revert.py 在每次修改前建快照（reg export 全部相关键 + 服务启动类型 + 生成 undo.ps1），一键回滚；revert/ 目录已 gitignore（含注册表隐私数据）。

## 代理/抓取技巧（GitHub 调研用）

- web_search/web_extract 的 Tavily key 失效时（401），**GitHub API 可用**：`api.github.com/search/repositories?q=...&sort=stars` 不需要认证（限流 60/h）
- raw 文件：`raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>`
- 本机走代理：`http://127.0.0.1:15715`（注册表 ProxyServer）
- Python urllib 配 ProxyHandler 稳定；curl 在 MSYS 下 HTTP 200 但 0 字节（代理交互问题），用 Python 代替
- Bing/DDG/Google 搜索均被限流或握手超时，GitHub API 是最稳路径
