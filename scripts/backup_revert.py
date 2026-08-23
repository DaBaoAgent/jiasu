#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jiasu 可逆性保障（optimizerDuck revert 机制同款）— 改系统前的快照 + undo 生成器。

任何注册表/服务修改前先跑 `python backup_revert.py backup`：
  1. reg export 所有技能会碰的注册表键 → revert/<timestamp>/
  2. 记录服务启动类型（sc qc）→ services.txt
  3. 生成 undo_<timestamp>.ps1（reg import + sc config 一键回滚）
  4. 输出备份目录路径，供 agent 记录

用法:
    python backup_revert.py backup          # 建快照 + 生成 undo 脚本（改系统前调用）
    python backup_revert.py list            # 列出已有备份
    python backup_revert.py apply <dir>     # 应用指定备份的 undo 脚本（需管理员）

无管理员权限时 backup 依然可用（reg export HKCU/HKLM 读 + sc qc 读都不需要提权）。
"""
import os
import sys
import json
import shutil
import subprocess
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVERT_ROOT = os.path.join(SKILL_DIR, "revert")

# 技能会修改的注册表键（reg export 整个键，含所有子值）
REG_KEYS = [
    r"HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection",      # 遥测 AllowTelemetry
    r"HKCU\Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo",  # 广告 ID
    r"HKLM\SOFTWARE\Policies\Microsoft\Windows\System",              # 活动历史 EnableActivityFeed
    r"HKCU\Software\Policies\Microsoft\Windows\WindowsCopilot",      # Copilot 开关
    r"HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsAI",           # Recall/AI 开关
    r"HKCU\Control Panel\Desktop",                                   # MenuShowDelay
    r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",  # TaskbarAnimations
    r"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", # EnableTransparency
    r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power",  # HiberbootEnabled
    r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",  # Known Folder 重定向
    r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",           # 用户启动项
    r"HKLM\Software\Microsoft\Windows\CurrentVersion\Run",           # 系统启动项
    r"HKLM\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run",
]

# 技能会调整启动类型的服务（manual/disabled）
SERVICES = [
    "wpscloudsvr", "edgeupdate", "edgeupdatem", "mtxxservice",
    "DiagTrack", "dmwappushservice", "MapsBroker", "WSearch",
    "SysMain", "Fax", "XblAuthManager", "XblGameSave", "XboxNetApiSvc",
    "WSAIFabricSvc",
]

# sc qc START_TYPE 数值 → 启动类型名（用于 undo 恢复）
START_TYPE_NAMES = {2: "auto", 3: "demand", 4: "disabled"}


def run(cmd):
    """运行命令，返回 (exit_code, stdout_text)。GBK 输出转 UTF-8。"""
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=60)
        out = p.stdout.decode("gbk", errors="replace") + p.stderr.decode("gbk", errors="replace")
        return p.returncode, out
    except Exception as e:
        return -1, str(e)


def backup():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bdir = os.path.join(REVERT_ROOT, ts)
    os.makedirs(bdir, exist_ok=True)

    exported, failed = [], []
    for key in REG_KEYS:
        fname = key.replace("\\", "__").replace(":", "") + ".reg"
        fpath = os.path.join(bdir, fname)
        rc, out = run(["reg", "export", key, fpath, "/y"])
        if rc == 0 and os.path.isfile(fpath) and os.path.getsize(fpath) > 0:
            exported.append(key)
        else:
            failed.append(key)
            if os.path.isfile(fpath):
                os.unlink(fpath)

    svc_lines = []
    for svc in SERVICES:
        rc, out = run(["sc", "qc", svc])
        if rc == 0:
            for line in out.splitlines():
                if "START_TYPE" in line:
                    svc_lines.append(f"{svc}\t{line.strip()}")
                    break
        else:
            failed.append(svc)

    with open(os.path.join(bdir, "services.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(svc_lines))

    # 生成 undo.ps1
    undo = ["# jiasu undo - 由 backup_revert.py 生成，一键回滚所有修改",
            "# 用法: powershell -ExecutionPolicy Bypass -File undo_%s.ps1 （需管理员）" % ts, ""]
    for key in exported:
        fname = key.replace("\\", "__").replace(":", "") + ".reg"
        undo.append(f'reg import "{os.path.join(bdir, fname)}"')
    for line in svc_lines:
        svc, start = line.split("\t", 1)
        stype = None
        for tok in start.split():
            if tok.isdigit() and int(tok) in START_TYPE_NAMES:
                stype = START_TYPE_NAMES[int(tok)]
        if stype:
            undo.append(f'sc config {svc} start= {stype}')
    undo.append("")
    undo.append("Write-Host '回滚完成。建议重启一次系统。'")
    with open(os.path.join(bdir, f"undo_{ts}.ps1"), "w", encoding="utf-8") as f:
        f.write("\n".join(undo))

    manifest = {
        "timestamp": ts,
        "exported_reg_keys": exported,
        "failed_keys": failed,
        "services_recorded": len(svc_lines),
    }
    with open(os.path.join(bdir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    print(f"快照已建: {bdir}")
    print(f"  注册表键导出 {len(exported)}/{len(REG_KEYS)}，服务记录 {len(svc_lines)}/{len(SERVICES)}")
    if failed:
        print(f"  跳过（不存在或无权限）: {', '.join(failed[:8])}")
    print(f"  undo 脚本: {os.path.join(bdir, 'undo_%s.ps1') % ts}")
    return bdir


def list_backups():
    if not os.path.isdir(REVERT_ROOT):
        print("（无备份）")
        return
    dirs = sorted(d for d in os.listdir(REVERT_ROOT)
                  if os.path.isdir(os.path.join(REVERT_ROOT, d)))
    if not dirs:
        print("（无备份）")
        return
    print("已有快照:")
    for d in dirs:
        mf = os.path.join(REVERT_ROOT, d, "manifest.json")
        extra = ""
        if os.path.isfile(mf):
            with open(mf, encoding="utf-8") as f:
                data = json.load(f)
            extra = f"  reg={len(data['exported_reg_keys'])} svc={data['services_recorded']}"
        print(f"  {d}{extra}")


def apply(bdir):
    bdir = os.path.join(REVERT_ROOT, bdir) if not os.path.isabs(bdir) else bdir
    if not os.path.isdir(bdir):
        print(f"备份目录不存在: {bdir}")
        sys.exit(1)
    undos = [f for f in os.listdir(bdir) if f.startswith("undo_") and f.endswith(".ps1")]
    if not undos:
        print(f"{bdir} 下没有 undo 脚本")
        sys.exit(1)
    target = os.path.join(bdir, undos[0])
    print(f"执行: {target}")
    print("需要管理员权限；若弹 UAC 请点【是】。")
    rc, out = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                   "-Command", f"Start-Process powershell -Verb RunAs -ArgumentList "
                   f"'-NoProfile -ExecutionPolicy Bypass -File \"{target}\"' -Wait"])
    print(out)
    if rc == 0:
        print("已提交回滚（提权窗口结果见上）")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    action = sys.argv[1]
    if action == "backup":
        backup()
    elif action == "list":
        list_backups()
    elif action == "apply" and len(sys.argv) >= 3:
        apply(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
