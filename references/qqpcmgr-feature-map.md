# 腾讯电脑管家（QQPCMgr 18.1）清理加速功能全景 — 逆向笔记

来源：2026-08-02 对本机 `C:\Program Files (x86)\Tencent\QQPCMgr\18.1.30302.212` 实机逆向（插件清单 + 配置文件 + 模块 DLL 交叉验证）。

## 安装/数据路径要点

- 程序目录：`C:\Program Files (x86)\Tencent\QQPCMgr\<版本号>\`
- 用户缓存（可清）：`%APPDATA%\Tencent\QQPCMgr\`（radiumv3、QMLauncher、beacon、Download 等）+ `%LOCALAPPDATA%\Tencent\QQPCMgr\`（cef_cache_qmui 等 CEF 缓存）
- 运行期配置在 `%APPDATA%\Tencent\QQPCMgr\`：`SysOpt.ini`（延迟启动清单）、`sysdeepopt.ini`（禁用启动项/服务清单）、`StartupDelayList.dat`（延迟队列）、`ProcRunTimeInfo.xml`（每进程 CPU/IO/运行时间统计——开机时间分析的数据源）、`TimingTaskParam.xml`（定时关机/休息）

## 功能地图（PluginInfo.xml 共 29 个插件）

清理+加速 12 项：安全扫描、杀毒详情、加速详情、安全工具、空间清理、电脑诊所、开机启动项、一键清理、C盘清理、软件搬家、软件卸载、软件弹窗拦截。
其余：多设备管理、账号中心、设备远程（发起/接受）、权限管理、敏感权限保护、管理划词工具、自动防护、管理右键菜单、设置中心（通用/显示/升级/功能提示/偏好/高级/关于 ×7）。

悬浮球"加速火箭"（SpeedupRocket/）另有 14 个小插件：安全风险、模式开关、计算机状态、垃圾清理、网速管理、开机加速、弹窗拦截、右键菜单、默认应用、热键检测、划词开关、工具箱、游戏状态、隐私保护（见 `SpeedupRocket/MiniHomePagePlugins/MiniHomePagePlugin.xml`）。

## 模块证据表

| 功能 | 模块证据 |
|---|---|
| 垃圾清理引擎 | `GarbageCleaner.dll`（1.7MB）+ 悬浮球 GarbageCleanPlugin |
| 磁盘扫描 | `QMDiskScanLogic.dll` |
| 内存整理 | `MemDefrag.dll` + `MemDefragWhiteList.etf`（白名单） |
| 软件搬家 | `VolSnapshot.exe`（卷快照）+ `7z.dll`（压缩迁移） |
| 文件粉碎 | `FileSmashPro.exe` + `FileSmashMenu*.dll`（右键） |
| 开机加速 | `SpeedupRocket/` + `StartupMgrDll.dll` + `StartupDelayList.dat` |
| 启动项策略 | `SysOpt.ini`（延迟）/ `sysdeepopt.ini`（禁用） |
| 网速管理 | `QMNetMon`（23MB）+ `SpeedupNetflowLimit.etf`（限速策略） |
| DNS 优化 | `DNSOptimization.exe` |
| 系统修复 | `QQPCfix.dll` + `Plugins/QMClinicCore` + `Plugins/SystemAidBox`（41MB 反 Rootkit 急救箱） |
| 软件卸载 | `Plugins/SoftUninstall` + `Plugins/FtsysSoftUninstall` |
| 弹窗拦截 | `adfilterlib/` + AdBlockMiniPlugin |
| 安全扫描 | `HPScanUIPlugin` + `SafeScanPluginConf.xml` |
| 漏洞修复 | `TSVulFixInc.exe` + `VulLibInc/` |
| 硬件评测 | `HardwareBenchMark/` |
| 进程管理 | `ProcessManager.dll` |

## 扫描分级体系（SafeScanPluginConf.xml）

6 目录评分制：病毒木马 30 / 高危漏洞 15 / 系统异常 30 / 潜在风险软件 20 / **AI安全扫描 20**（检测本机 AI 工具的高风险 Skills 插件——2026 新功能）/ 感染型全盘扫描 20。
扫描模式按位与：安全扫描 1 / 全盘扫描 2 / 自定义 4 / 感染型专杀 8。
每个子插件带 progress 步进定义（进度条驱动）。

## 方法论（可借鉴的四件套）

1. **先扫描分类，再分级处理**：评分制决定优先级，而非一刀切。
2. **延迟启动代替禁用**：`StartupDelayList.dat` 错峰延迟启动非关键项，开机感知提速且不破坏功能（本机实例：OneDrive、ima.copilot、Chrome、百度网盘 4 项被延迟）。
3. **白名单保护机制**：`MemDefragWhiteList.etf`、`SoftMon.etf`、`SMFilter.etf` 等——整理/清理时跳过白名单进程，避免误伤。
4. **悬浮球常驻引导**：高频操作（垃圾清理/开机加速/网速/弹窗拦截）放桌面随时可点。

## 逆向技巧（对同类国产软件适用）

- 功能清单先读**明文 XML**：`PluginInfo.xml`（插件注册表）、`SafeScanPluginConf.xml`、`MiniHomePagePlugin.xml`、`starttips.xml`——比提取 DLL 字符串快且准。
- **DLL 中文字符串是加密的**（UTF-16 和 UTF-8 提取均为乱码），不要在字符串提取上浪费时间。
- `.etf` 文件是加密配置（头 `ETF\0`），GlobalConfig 同理，读不了就跳过，以 XML 为准。
- 官网 `guanjia.qq.com` 是 JS 渲染（curl 返回 200 但 size 0），不如本地逆向。
