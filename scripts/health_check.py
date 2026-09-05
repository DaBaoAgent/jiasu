# -*- coding: utf-8 -*-
"""jiasu 全面体检脚本（只读，免 UAC）
输出中文体检报告，异常项用 [WARN] 标出。手动触发与每日 cron 复用。
用法: python health_check.py

可清项清单来自 rules.json 规则库（单一事实源，与 deep_scan --rules 一致），
codex-runtimes/codex sessions 单独列红线提示（勿删）。
"""
import os
import re
import subprocess
import sys

import _common

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def re_search_percent(line):
    m = re.search(r"(\d+)%", line)
    return int(m.group(1)) if m else None


def ps(cmd, timeout=60):
    """Run a PowerShell query, return decoded text (编码自适应：本机实测 UTF-8/GBK 都有)."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, timeout=timeout,
        )
        return _common.decode_console(r.stdout + r.stderr).strip()
    except Exception as e:
        return "[ERR] {}".format(e)


WARN = []
INFO = []
OK = []


def check(name, ok_cond, detail, warn_text=None):
    if ok_cond:
        OK.append("{}: {}".format(name, detail))
    else:
        WARN.append("{}: {} {}".format(name, detail, warn_text or ""))


# ---------- 1. 磁盘 ----------
print("===== 1. 磁盘空间 =====")
disk = ps("Get-CimInstance Win32_LogicalDisk -Filter \"DriveType=3\" | ForEach-Object { '{0} {1:N1}G/{2:N1}G {3:N0}%' -f $_.DeviceID,($_.FreeSpace/1GB),($_.Size/1GB),(($_.Size-$_.FreeSpace)/$_.Size*100) }")
for line in disk.splitlines():
    line = line.strip()
    if not line:
        continue
    print("  " + line)
    m = re_search_percent(line)
    if m is not None and m > 85:
        WARN.append("磁盘占用过高: {}".format(line))
    else:
        OK.append("磁盘: {}".format(line))

# ---------- 2. 系统信息 ----------
print("\n===== 2. 系统信息 =====")
sysinfo = ps("$o=Get-CimInstance Win32_OperatingSystem; $c=Get-CimInstance Win32_ComputerSystem; 'OS: {0} {1} | RAM: {2:N1}G | Boot: {3}' -f $o.Caption,$o.Version,($c.TotalPhysicalMemory/1GB),$o.LastBootUpTime")
print("  " + sysinfo)
INFO.append("系统: " + sysinfo)

# ---------- 3. 安全 ----------
print("\n===== 3. 安全状态 =====")
mp = ps("$m=Get-MpComputerStatus; 'Mode: {0} | RealTime: {1} | SigAge: {2}d | Tamper: {3}' -f $m.AMRunningMode,$m.RealTimeProtectionEnabled,$m.AntivirusSignatureAge,$m.IsTamperProtected")
print("  Defender: " + mp)
av = ps("Get-CimInstance -Namespace root\\SecurityCenter2 -ClassName AntiVirusProduct | ForEach-Object { $_.displayName }")
avs = [x for x in av.splitlines() if x.strip()]
print("  杀软: " + (" / ".join(avs) if avs else "无"))
if "[ERR]" in mp:
    INFO.append("Defender 状态查询失败（不算异常）: " + mp)
elif "Passive" in mp or "RealTime: True" in mp:
    OK.append("Defender/杀软: " + mp + " | " + " / ".join(avs))
else:
    WARN.append("杀软实时保护未开启: " + mp)

fw = ps("(Get-NetFirewallProfile | Where-Object {$_.Enabled -eq $false} | Measure-Object).Count")
print("  防火墙关闭的配置文件数: " + fw)
if "[ERR]" in fw or not fw.strip():
    INFO.append("防火墙状态未知: " + fw.strip())  # 查询失败≠防火墙被关，别误报 WARN
elif fw.strip() == "0":
    OK.append("防火墙: 全开")
else:
    WARN.append("防火墙有配置文件关闭: " + fw)

uac = ps("(Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System').ConsentPromptBehaviorAdmin")
print("  UAC自动提权(0=已配): " + uac.strip())
INFO.append("UAC: " + uac.strip())

# ---------- 4. 启动项 ----------
print("\n===== 4. 启动项 =====")
hkcu = ps("(Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' -ErrorAction SilentlyContinue).PSObject.Properties | Where-Object {$_.Name -notmatch '^PS'} | ForEach-Object { $_.Name }")
hklm = ps("(Get-ItemProperty 'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' -ErrorAction SilentlyContinue).PSObject.Properties | Where-Object {$_.Name -notmatch '^PS'} | ForEach-Object { $_.Name }")
startup = ps("Get-ChildItem \"$env:APPDATA\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\" -ErrorAction SilentlyContinue | ForEach-Object { $_.Name }")
print("  HKCU Run: " + (hkcu.replace("\r", " ").replace("\n", " ") or "空"))
print("  HKLM Run: " + (hklm.replace("\r", " ").replace("\n", " ") or "空"))
print("  Startup: " + (startup.replace("\r", " ").replace("\n", " ") or "空"))
INFO.append("启动项: HKCU[{}] HKLM[{}] Startup[{}]".format(
    hkcu.replace("\n", ","), hklm.replace("\n", ","), startup.replace("\n", ",")))

# ---------- 5. 服务 ----------
print("\n===== 5. 关键服务 =====")
svc = ps("Get-Service -Name DiagTrack,edgeupdate,edgeupdatem,wpscloudsvr,SysMain,wuauserv,WinDefend -ErrorAction SilentlyContinue | ForEach-Object { '{0}={1}' -f $_.Name,$_.StartType }")
for s in svc.splitlines():
    s = s.strip()
    if not s:
        continue
    print("  " + s)
    name, _, st = s.partition("=")
    if name == "DiagTrack" and st != "Disabled":
        WARN.append("DiagTrack 应 Disabled: " + st)
    elif name in ("edgeupdate", "edgeupdatem", "wpscloudsvr", "SysMain") and st != "Manual":
        WARN.append("{} 应 Manual: {}".format(name, st))
    elif name == "WinDefend" and st != "Automatic":
        WARN.append("WinDefend 应 Automatic: " + st)
    else:
        OK.append("服务 {}: {}".format(name, st))

# ---------- 6. 还原点 ----------
print("\n===== 6. 还原点 =====")
# 非提权无法查 Get-ComputerRestorePoint（拒绝访问），改用卷监控目录判断系统还原是否启用
sv_dir = os.path.exists(r"C:\System Volume Information")
if sv_dir:
    print("  系统还原: 已启用（卷监控存在；数量需管理员验证，如 0 个请提权建点）")
    OK.append("系统还原: 已启用")
else:
    print("  系统还原: 未检测到卷监控")
    WARN.append("系统还原未启用（建议 Enable-ComputerRestore C: + Checkpoint-Computer 建点）")

# ---------- 7. 大缓存可清项（来自 rules.json，单一事实源）----------
print("\n===== 7. 缓存可清项(>0.5G，rules.json 规则库) =====")
hits = _common.match_rules()
shown = 0
for r, real, size, note in hits:
    if size >= 0.5:
        print("  [{}] {:.2f}G{}".format(r["name"], size, " — " + note if note else ""))
        INFO.append("可清缓存 {}: {:.2f}G".format(r["name"], size))
        shown += 1
if shown == 0:
    print("  （无 ≥0.5G 的可清项）")

# ---------- 7b. 红线提示（仅提示不要删）----------
print("\n===== 7b. 红线提示（勿删） =====")
_up = os.environ.get("USERPROFILE", "")
for name, path in [("codex-runtimes", os.path.join(_up, ".cache", "codex-runtimes")),
                   ("codex sessions", os.path.join(_up, ".codex", "sessions"))]:
    sz = _common.dir_size(path) / _common.GB if os.path.exists(path) else -1
    if sz >= 0.5:
        print("  [{}] {:.2f}G —— venv 基底/会话历史，勿删".format(name, sz))

# ---------- 汇总 ----------
print("\n===== 汇总 =====")
print("正常 {} 项 / 注意 {} 项 / 异常 {} 项".format(len(OK), len(INFO), len(WARN)))
for w in WARN:
    print("  [WARN] " + w)
