#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""软件使用审计 → winget 批量卸载（winutil Install tab 同款思路，默认 dry-run）。

前置: 先跑 audit_unused_software.ps1 -JsonOut 生成 _app_analysis.json
      （字段: Name/Location/UninstallString/LastActivity/DaysIdle）

用法:
    python uninstall_by_audit.py                        # 列出 idle>60 天未用的软件
    python uninstall_by_audit.py --idle 90              # 自定义闲置阈值
    python uninstall_by_audit.py --json <path>          # 指定审计 JSON 路径
    python uninstall_by_audit.py --apply "TIM"          # 真正卸载（注册表 UninstallString 优先）
    python uninstall_by_audit.py --apply "TIM" --winget # 强制走 winget

安全: 默认只列不卸；--apply 才执行。无 UninstallString 的软件（如悟空）走 winget，
      winget 也卸不掉时给出注册表残留清理指引（见 SKILL.md 陷阱 #11）。
"""
import os
import sys
import json
import shutil
import subprocess

IDLE_DEFAULT = 60
SYSTEM_HINTS = ["Edge", "OneDrive"]  # 误判高发项，仅提示不自动卸


def run(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=120)
        out = (p.stdout + p.stderr).decode("gbk", errors="replace")
        return p.returncode, out
    except Exception as e:
        return -1, str(e)


def load_apps(path="_app_analysis.json"):
    if not os.path.isfile(path):
        print(f"未找到 {path}。先执行: powershell -File scripts/audit_unused_software.ps1 -JsonOut")
        sys.exit(1)
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    return data if isinstance(data, list) else [data]


def winget_id(name):
    """查询应用对应的 winget 包 ID，找不到返回 None"""
    rc, out = run(["winget", "list", "--name", name, "--accept-source-agreements"])
    if rc != 0:
        return None
    for line in out.splitlines()[2:]:  # 跳过表头
        parts = line.split()
        if len(parts) >= 2 and parts[0].lower() == name.lower():
            return parts[1]
    # winget list 输出列宽不定，退化：拿第二列
    for line in out.splitlines()[2:]:
        parts = line.split()
        if len(parts) >= 3:
            return parts[1]
    return None


def list_idle(apps, idle):
    print(f"=== 闲置 >{idle} 天（共 {len(apps)} 个应用）===")
    idle_apps = [a for a in apps if a.get("DaysIdle", -1) > idle]
    if not idle_apps:
        print("（无）")
        return
    for a in sorted(idle_apps, key=lambda x: -x.get("DaysIdle", 0)):
        flag = ""
        if any(h in a["Name"] for h in SYSTEM_HINTS):
            flag = "  [系统组件,慎卸]"
        print(f"{a.get('DaysIdle'):>5}d  {a['Name']}{flag}")
        if a.get("Location"):
            print(f"        {a['Location']}")
    print("\n卸载命令示例:")
    print('  python uninstall_by_audit.py --apply "TIM"   # 按名称卸载')


def apply_uninstall(apps, name, force_winget=False):
    matches = [a for a in apps if name.lower() in a["Name"].lower()]
    if not matches:
        print(f"审计 JSON 中找不到匹配 '{name}' 的应用")
        sys.exit(1)
    for a in matches:
        print(f"\n>>> 卸载: {a['Name']} (闲置 {a.get('DaysIdle')}d)")
        ok = False
        us = (a.get("UninstallString") or "").strip().strip('"')
        if us and not force_winget:
            print(f"  用注册表卸载命令: {us}")
            rc, out = run(us.split(" ")[0:1] + [us.split(" ", 1)[1]] if " " in us else [us])
            # 卸载器多为 GUI，直接启动即可；静默参数各软件不同，无法统一
            print(f"  已启动卸载器 (exit={rc})。GUI 窗口出现后按提示完成。")
            ok = True
        else:
            wid = winget_id(a["Name"])
            if wid:
                print(f"  winget uninstall --id {wid}")
                rc, out = run(["winget", "uninstall", "--id", wid, "--silent",
                               "--accept-source-agreements", "--disable-interactivity"])
                print(f"  winget exit={rc}: {out.strip()[:200]}")
                ok = rc == 0
            else:
                print("  winget 未找到该包。国产无卸载程序的软件需手动: "
                      "删 Program Files 目录 + 清 Uninstall 注册表键（见 SKILL.md 陷阱 #11）")
        if ok:
            print("  ✓ 处理完成")


def main():
    args = [a for a in sys.argv[1:]]
    jpath = "_app_analysis.json"
    idle = IDLE_DEFAULT
    apply_name = None
    force_winget = False
    if "--json" in args:
        jpath = args[args.index("--json") + 1]
    if "--idle" in args:
        idle = int(args[args.index("--idle") + 1])
    if "--apply" in args:
        apply_name = args[args.index("--apply") + 1]
    force_winget = "--winget" in args

    apps = load_apps(jpath)
    if apply_name:
        apply_uninstall(apps, apply_name, force_winget)
    else:
        list_idle(apps, idle)


if __name__ == "__main__":
    main()
