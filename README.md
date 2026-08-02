<!-- README-PROMO:START -->
<p align="center">
  <img src="assets/readme/hero.webp" alt="jiasu：Windows 电脑清理、系统加速与安全加固一体化技能" width="100%" />
  <img src="assets/readme/workflow.webp" alt="jiasu 工作流：深度清理、缓存迁移、开机加速与安全加固" width="100%" />
  <img src="assets/readme/beginner.webp" alt="jiasu 新手指南：先检查再优化，可逆、有边界、不误删" width="100%" />
</p>
<!-- README-PROMO:END -->

# jiasu 加速 — Windows 电脑清理 / 加速 / 安全加固

> Windows Cleaner, Speedup & Security Hardening — 磁盘深度清理 · 缓存迁移 · 开机加速 · 系统安全加固 · 一键式 AI 维护技能

**jiasu** 是一个面向 Windows 的**电脑清理、加速与安全加固一体化技能**（Hermes Agent skill）。输入"清理电脑 / 加速电脑 / 电脑安全"，自动执行完整维护流程：深度磁盘扫描 → 缓存清理 → 大文件迁移 → 开机加速四件套 → 系统安全加固。方法论融合腾讯电脑管家（QQPCMgr）逆向成果与 GitHub 头部开源项目最佳实践（Win11Debloat / Sophia Script / optimizerDuck / WindowsClear）。

## ✨ 核心功能 Features

### 🧹 磁盘深度清理 Disk Deep Cleanup
- **广扫再定点**：扫描 C/D 盘全部顶层目录，找出真实占用大户（真实案例：剪映缓存 36GB 不在常规清单）
- 剪映 / 美图 / WPS / 微信 / QQ / 浏览器 / Codex / Hermes 全量缓存清理（区分缓存 vs 用户数据，绝不误删草稿工程）
- pip / npm / uv 缓存、Windows 临时文件、崩溃转储、回收站一键清理
- **系统残留目录**（Sophia 同款）：`$WinREAgent` / `$SysReset` / `$Windows.~WS` / ESD / PerfLogs
- Windows Update 缓存 + DISM 组件清理
- **定时清理任务**：注册每周自动清理计划任务，长期免维护

### 🚚 大文件迁移 C-Drive Slimming
- `.cache` 缓存迁移 D 盘 + 环境变量重定向（huggingface / torch / uv / pip）
- **AppData Junction 迁移**（WindowsClear 同款）：微信 / QQ / 剪映 / 浏览器数据迁 D 盘 + 原位 Junction 链接，软件无感
- pagefile.sys 虚拟内存迁移 D 盘（UAC 脚本）
- 休眠文件 hiberfil.sys 释放

### ⚡ 开机加速 Boot Speedup
- **启动项错峰延迟**（腾讯管家同款）：schtasks onlogon 延迟启动，替代直接禁用
- **服务微调清单**：13+ 服务设 manual（遥测/更新/云同步/Xbox），红线保护杀毒/驱动/核心
- DNS 优化（阿里 223.5.5.5 + 腾讯 119.29.29.29）
- 菜单延迟归零 / 关闭动画透明 / 快速启动权衡 / 系统盘 compact 压缩
- 内存整理（EmptyWorkingSet）、加速结果验证（开机事件日志）

### 🔒 安全加固 Security Hardening
- 预装 AppX bloatware 移除（Bing/Xbox/PhoneLink/Copilot，全部可逆）
- 遥测/隐私禁用（DiagTrack / AllowTelemetry / 广告 ID）
- Win11 AI 功能禁用（Copilot / Recall，25H2+）
- Defender 实时保护 / VBS / 攻击面规则安全检查
- **任何修改前先建还原点**，可逆性方法论

### 🛡️ 安全红线 Safety First
- 所有操作区分**缓存 vs 用户数据**，红线目录（草稿工程/会话历史/程序模块）绝不触碰
- 服务优化只降级不改杀毒/驱动/Windows 核心
- Junction 迁移只迁纯数据目录，迁移后验证再删备份

## 📦 目录结构 Structure

```
jiasu/
├── SKILL.md                        # 主技能（完整维护流程）
├── scripts/
│   ├── deep_scan.py                # 顶层目录广扫（找占用大户）
│   ├── find_installed_apps.py      # 软件安装位置检索
│   └── audit_unused_software.ps1   # 软件使用审计（60天未用清单）
└── references/
    ├── disk_scan.py                # C盘关键目录占用扫描
    ├── pagefile_migrate.ps1        # pagefile 迁移 D 盘
    ├── qqpcmgr-feature-map.md      # 腾讯电脑管家 18.1 逆向笔记
    └── windows-optimization-projects.md  # GitHub 头部项目调研（Win11Debloat/Sophia/optimizerDuck 等）
```

## 🚀 使用方式 Usage

作为 **Hermes Agent** 技能加载：对 Hermes 说 **"清理电脑"**、**"加速电脑"** 或 **"电脑安全"** 即自动执行完整流程。

也可以直接运行脚本：
```bash
python scripts/deep_scan.py                    # 磁盘广扫
powershell -File scripts/audit_unused_software.ps1 -JsonOut   # 软件使用审计
```

## 🧠 方法论来源 Methodology

- **腾讯电脑管家 18.1 实机逆向**：29 插件功能地图、开机加速四件套（延迟启动/服务禁用/DNS/内存整理）、白名单保护机制
- **Win11Debloat**（54k★）：预装应用移除、遥测禁用、AI 功能关闭
- **Sophia Script**（9.6k★）：150+ 官方文档化配置、定时清理任务
- **optimizerDuck**（7.6k★）：可逆性方法论、风险评级、200+ 服务微调
- **WindowsClear**（979★）：AppData Junction 迁移
- **simeononsecurity**（1.4k★）：STIG 级安全加固、还原点先行

## 📄 License

MIT License · Author: **Dabao**

---

**Keywords:** windows cleanup, windows cleaner, 电脑清理, 加速电脑, C盘清理, 磁盘清理, disk cleanup, disk space, 开机加速, startup optimization, boot speedup, windows speedup, 系统优化, windows optimizer, 安全加固, windows security, security hardening, debloat, telemetry disable, 腾讯电脑管家, QQ电脑管家, appdata migration, junction, cache clean, 缓存清理, ssd optimization, windows 11, windows 10
