<!-- README-PROMO:START -->
<p align="center">
  <img src="assets/readme/hero.webp" alt="jiasu：Windows 电脑清理、系统加速与安全加固一体化技能" width="100%" />
  <img src="assets/readme/workflow.webp" alt="jiasu 工作流：深度清理、缓存迁移、开机加速与安全加固" width="100%" />
  <img src="assets/readme/beginner.webp" alt="jiasu 新手指南：先检查再优化，可逆、有边界、不误删" width="100%" />
</p>
<!-- README-PROMO:END -->

# jiasu 加速 — Windows 电脑清理 / 加速 / 安全加固

> Windows Cleaner, Speedup & Security Hardening — 磁盘深度清理 · 缓存迁移 · 开机加速 · 系统安全加固 · Defender 查杀 · 一键式 AI 维护技能

**jiasu** 是一个面向 Windows 的**电脑清理、加速与安全加固一体化技能**（Hermes Agent skill）。输入"清理电脑 / 加速电脑 / 杀毒 / 安全体检"，自动执行完整维护流程：深度磁盘扫描 → 缓存清理 → 大文件迁移 → 开机加速四件套 → 系统安全加固 → Defender 查杀防护。方法论融合腾讯电脑管家（QQPCMgr）逆向成果与 GitHub 头部开源项目最佳实践（Win11Debloat / Sophia Script / optimizerDuck / WindowsClear / winutil）。

## ✨ 核心功能 Features

### 🧹 磁盘深度清理 Disk Deep Cleanup
- **广扫再定点**：`deep_scan.py` 扫描 C/D 盘全部顶层目录，找出真实占用大户（真实案例：剪映缓存 36GB 不在常规清单）
- **规则库驱动（单一事实源）**：`rules.json` 数据化 40+ 条已知缓存规则，扫描 / 体检 / 每日清理三处自动生效；新增软件缓存规则只改 rules.json
- 剪映 / 美图 / WPS / 微信 / QQ / 浏览器 / Codex / Hermes 全量缓存清理（区分缓存 vs 用户数据，绝不误删草稿工程）
- **每日自动清理**（cron + `daily_clean_no_uac.py`）：免 UAC，逐项报告释放 GB
- **系统残留目录**（Sophia 同款）：`$WinREAgent` / `$SysReset` / `$Windows.~WS` / ESD / PerfLogs
- Windows Update 缓存 + DISM 组件清理
- **重复文件扫描**：`find_duplicates.py` 三级哈希过滤，默认只列，`--delete` 需 `--confirm`

### 🚚 大文件迁移 C-Drive Slimming
- `.cache` 缓存迁移 D 盘 + 环境变量重定向（huggingface / torch / uv / pip）
- **AppData Junction 迁移**（WindowsClear 同款）：微信 / QQ / 剪映 / 浏览器数据迁 D 盘 + 原位 Junction 链接，软件无感
- pagefile.sys 虚拟内存迁移 D 盘（UAC 脚本）
- 休眠文件 hiberfil.sys 释放
- **用户文件夹重定向**：`redirect_known_folders.ps1` 一键把 Desktop/Documents 等指向 D 盘（可 -Undo 回滚）

### ⚡ 开机加速 Boot Speedup
- **启动项错峰延迟**（腾讯管家同款）：schtasks onlogon 延迟启动，替代直接禁用
- **服务微调清单**：13+ 服务设 manual（遥测/更新/云同步/Xbox），红线保护杀毒/驱动/核心
- DNS 优化（`dns_tool.py`：备份 / 预设切换 / UDP 延迟测试 / 一键恢复）
- 菜单延迟归零 / 关闭动画透明 / 快速启动权衡 / 系统盘 compact 压缩
- 内存整理（EmptyWorkingSet）、加速结果验证（开机事件日志）

### 🔒 安全加固 Security Hardening
- 预装 AppX bloatware 移除（Bing/Xbox/PhoneLink/Copilot，全部可逆）
- 遥测/隐私禁用（DiagTrack / AllowTelemetry / 广告 ID）
- Win11 AI 功能禁用（Copilot / Recall，25H2+）
- **可逆性保障**：`backup_revert.py` 修改前 reg export + 服务快照 + 一键 undo 回滚（revert/ 已 gitignore）

### 🛡️ 安全卫士 Defender Security
- **查杀/签名/状态**：`defender_scan.py` 封装 Defender（快速/全盘查杀、签名更新、隔离区、恢复向导）
- **启动项三路审计**（Autoruns 思路）：注册表 Run 键 + 启动文件夹 + 计划任务 + 自动服务交叉检查
- 防火墙审计（入站规则 + 监听端口暴露面）
- **系统修复**：`system_repair.ps1` SFC / DISM RestoreHealth / WU 重置 / 网络重置
- **每日安全守护 cron**：查杀 + 签名更新 + 审计，异常项 [WARN] 报告

### 🩺 健康体检 Health Check
- `health_check.py` 只读全面体检：磁盘 / 安全 / 启动项 / 服务 / 还原点 / 缓存可清项，异常 [WARN] 标出，可进 cron
- **锁文件句柄查询**：`find_locked_by.py`（Restart Manager API）找出谁占用删不掉的文件
- **软件使用审计**：`audit_unused_software.ps1` + `uninstall_by_audit.py` 找 60 天未用软件，接 winget 批量卸载

### 🛡️ 安全红线 Safety First
- 所有操作区分**缓存 vs 用户数据**，红线目录（草稿工程/会话历史/程序模块）绝不触碰
- 服务优化只降级不改杀毒/驱动/Windows 核心
- Junction 迁移只迁纯数据目录，迁移后验证再删备份

## 📦 目录结构 Structure

```
jiasu/
├── SKILL.md                        # 主技能（完整维护流程）
├── scripts/
│   ├── _common.py                  # 公共工具（目录大小/磁盘剩余/junction 跳过/规则库匹配/提权）
│   ├── daily_clean_no_uac.py       # 每日免 UAC 自动清理（规则库 + 内置复杂逻辑，cron 复用）
│   ├── deep_scan.py                # 顶层目录广扫（找占用大户）；--rules 附加规则库匹配
│   ├── rules.json                  # 清理规则库（单一事实源，40+ 条，新增软件只改此文件）
│   ├── health_check.py             # 只读全面体检（中文报告 + [WARN]）
│   ├── defender_scan.py            # 安全卫士：Defender 查杀/签名/状态/恢复向导
│   ├── backup_revert.py            # 可逆性保障：快照 + undo 一键回滚
│   ├── dns_tool.py                 # DNS 优化：备份/预设切换/延迟测试/恢复
│   ├── find_duplicates.py          # 重复文件扫描（默认只列）
│   ├── find_locked_by.py           # 锁文件句柄查询
│   ├── find_installed_apps.py      # 软件安装位置检索
│   ├── uninstall_by_audit.py       # 审计结果接 winget 批量卸载
│   ├── audit_unused_software.ps1   # 软件使用审计（60天未用清单）
│   ├── redirect_known_folders.ps1  # 用户文件夹重定向 D 盘（可回滚）
│   └── system_repair.ps1           # 系统修复（SFC/DISM/WU 重置/网络重置）
└── references/
    ├── pagefile_migrate.ps1        # pagefile 迁移 D 盘
    ├── qqpcmgr-feature-map.md      # 腾讯电脑管家 18.1 逆向笔记
    └── windows-optimization-projects.md  # GitHub 头部项目调研（Win11Debloat/Sophia/optimizerDuck 等）
```

## 🚀 使用方式 Usage

作为 **Hermes Agent** 技能加载：对 Hermes 说 **"清理电脑"**、**"加速电脑"**、**"杀毒"** 或 **"安全体检"** 即自动执行完整流程。

也可以直接运行脚本：
```bash
python scripts/health_check.py                    # 全面体检（只读）
python scripts/deep_scan.py --rules               # 磁盘广扫 + 规则库匹配
python scripts/daily_clean_no_uac.py              # 每日自动清理（免 UAC）
python scripts/defender_scan.py quick             # Defender 快速查杀
python scripts/dns_tool.py test --all             # DNS 延迟对比
python scripts/find_duplicates.py "D:/素材库"      # 重复文件扫描
python scripts/backup_revert.py backup            # 修改前建快照
powershell -File scripts/audit_unused_software.ps1 -JsonOut   # 软件使用审计
```

## 🧠 方法论来源 Methodology

- **腾讯电脑管家 18.1 实机逆向**：29 插件功能地图、开机加速四件套（延迟启动/服务禁用/DNS/内存整理）、白名单保护机制
- **Win11Debloat**（54k★）：预装应用移除、遥测禁用、AI 功能关闭
- **Sophia Script**（9.6k★）：150+ 官方文档化配置、定时清理任务
- **optimizerDuck**（7.6k★）：可逆性方法论、风险评级、200+ 服务微调
- **WindowsClear**（979★）：AppData Junction 迁移
- **winutil**（Chris Titus）：系统修复、软件批量管理
- **simeononsecurity**（1.4k★）：STIG 级安全加固、还原点先行

## 📄 License

MIT License · Author: **Dabao**

---

**Keywords:** windows cleanup, windows cleaner, 电脑清理, 加速电脑, C盘清理, 磁盘清理, disk cleanup, disk space, 开机加速, startup optimization, boot speedup, windows speedup, 系统优化, windows optimizer, 安全加固, windows security, security hardening, debloat, telemetry disable, defender, 杀毒, 查杀, 腾讯电脑管家, QQ电脑管家, appdata migration, junction, cache clean, 缓存清理, ssd optimization, windows 11, windows 10
