#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安全卫士：Defender 查杀/签名/状态封装（jiasu 技能安全章节）
用法:
  python defender_scan.py status          # 只读：Defender 状态 + 签名时间
  python defender_scan.py update          # 更新签名（提权，本机免 UAC 静默）
  python defender_scan.py quick           # 快速查杀（提权，5-15 分钟）
  python defender_scan.py full            # 全盘查杀（提权，1-3 小时，放凌晨）
  python defender_scan.py threats         # 隔离区/检测历史
  python defender_scan.py restore         # 恢复向导：检查禁用键+服务+写回源，输出修复脚本
"""
import subprocess, sys, time, os

PS = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command"]
MPCMD = r"C:\Program Files\Windows Defender\MpCmdRun.exe"
LOG = r"C:\Users\xxx13\defender_scan_result.txt"


def run_ps(cmd: str, timeout: int = 300) -> str:
    try:
        r = subprocess.run(PS + [cmd], capture_output=True, timeout=timeout)
        return r.stdout.decode("utf-8", errors="replace") + r.stderr.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


def run_elevated_ps(script_body: str, timeout: int = 900) -> None:
    """把操作写进临时 ps1 提权执行（结果落 LOG，本机 ConsentPromptBehaviorAdmin=0 静默）"""
    ps1 = os.path.join(os.environ["USERPROFILE"], "_defender_op.ps1")
    with open(ps1, "w", encoding="utf-8-sig") as f:
        f.write(script_body)
    subprocess.run(PS + [
        f"Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File {ps1}'"
    ], timeout=30)
    # 等结果文件
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(LOG):
            with open(LOG, encoding="utf-8-sig") as f:
                return f.read()
        time.sleep(5)
    return "TIMEOUT waiting result"


def status():
    out = run_ps("Get-MpComputerStatus | ConvertTo-Json -Depth 3", timeout=120)
    try:
        import json
        d = json.loads(out)
        mode = d.get("AMRunningMode", "?")
        rtp = d.get("RealTimeProtectionEnabled")
        av = d.get("AntivirusEnabled")
        sig = d.get("AntivirusSignatureLastUpdated")
        if isinstance(sig, str) and sig.startswith("/Date("):
            import datetime
            sig = datetime.datetime.fromtimestamp(int(sig[6:-2]) / 1000).strftime("%Y-%m-%d %H:%M")
        print(f"AMRunningMode={mode}  RealTimeProtection={rtp}  AntivirusEnabled={av}")
        print(f"SignatureLastUpdated={sig}")
        if mode == "Not running" or not rtp:
            print("[WARN] Defender 未在运行/实时保护关闭！运行: python defender_scan.py restore")
        else:
            print("[OK] Defender 实时防护正常")
    except Exception as e:
        print(f"[ERR] 解析失败: {e}\n{out[:500]}")


def update():
    body = '"=== sig update $(Get-Date) ===" | Out-File %s -Encoding UTF8; try { Update-MpSignature | Out-Null; "[OK]" | Out-File %s -Append -Encoding UTF8 } catch { "[ERR] $($_.Exception.Message)" | Out-File %s -Append -Encoding UTF8 }' % (LOG, LOG, LOG)
    print(run_elevated_ps(body, 600))


def scan(scan_type: int, label: str):
    # 扫描结果也走 MpCmdRun 的 -DisableRemediation 否？不，正常查杀即可
    body = f'"[start {label}]" | Out-File {LOG} -Encoding UTF8; & "{MPCMD}" -Scan -ScanType {scan_type} 2>&1 | Out-File {LOG} -Append -Encoding UTF8; "[done {label}]" | Out-File {LOG} -Append -Encoding UTF8'
    print(run_elevated_ps(body, 7200))


def threats():
    out = run_ps("Get-MpThreat | Select-Object ThreatName,SeverityID,Resources | Format-List", timeout=120)
    print(out if out.strip() else "无威胁记录")


def restore():
    print("=== Defender 恢复向导（2026-08-28 实战） ===")
    print("背景：QQPCMgr 卸载残留的 QQPCRTP/23734 服务 + 6 个内核驱动会在后台把 Defender 写回禁用。")
    out = run_ps("Get-Service QQPCRTP,23734 -ErrorAction SilentlyContinue | Select-Object Name,Status | Format-Table")
    print("当前 QQPCMgr 残留服务:\n" + out)
    print("修复步骤（写 ps1 提权执行）:")
    print("1. sc stop/config disabled: QQPCRTP, 23734, QMUdisk, QQSysMonX64, TAOKernelDriver, TSSysKit, TcHardWare, Tsnethlpx64")
    print("2. 删 HKLM\\SOFTWARE\\Microsoft\\Windows Defender\\DisableAntiSpyware 与 Policies 下同名键")
    print("3. sc config WinDefend start= auto + Start-Service WinDefend")
    print("4. Set-MpPreference -DisableRealtimeMonitoring $false; Update-MpSignature")
    print("5. 验证 Get-MpComputerStatus AMRunningMode=Normal RTP=True")
    print("6. 重启后删 C:\\Program Files (x86)\\Tencent\\QQPCMgr 残留目录")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"status": status, "update": update, "quick": lambda: scan(1, "quick"),
     "full": lambda: scan(2, "full"), "threats": threats, "restore": restore}.get(cmd, status)()
