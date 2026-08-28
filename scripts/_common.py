#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jiasu 公共工具 — scripts/ 下各脚本共用。

- free_gb / dir_size：磁盘剩余 / 目录大小（二进制单位 1024^3，与 daily_clean 一致）
- JUNCTION_NAMES：递归扫描时跳过的 junction/reparse 循环名
- expand_path / match_rules：rules.json 规则库解析（deep_scan / health_check / daily_clean 共用）
- run_elevated_ps：写临时 ps1 + Start-Process -Verb RunAs + 结果文件轮询（本机免 UAC 静默）

单一事实源：新增可清缓存规则只改 rules.json，扫描 / 体检 / 清理三处自动生效。
"""
import json
import os
import ctypes
import subprocess
import time

# junction / reparse 循环名 —— 跳过，否则算出上百 GB 的假占用
JUNCTION_NAMES = {
    "Application Data", "Local Settings", "Cookies", "History",
    "Temporary Internet Files", "My Documents", "NetHood", "PrintHood",
    "Recent", "SendTo", "Start Menu", "Templates",
    "$RECYCLE.BIN", "System Volume Information",
}

ENV_PLACEHOLDERS = {
    "%USERPROFILE%": "USERPROFILE",
    "%LOCALAPPDATA%": "LOCALAPPDATA",
    "%APPDATA%": "APPDATA",
    "%TEMP%": "TEMP",
    "%SystemRoot%": "SystemRoot",
    "%ProgramData%": "ProgramData",
}

GB = 1024 ** 3
MB = 1024 ** 2


def free_gb(drive="C:\\"):
    """磁盘剩余空间（GB，二进制单位）。"""
    free = ctypes.c_ulonglong(0)
    ctypes.windll.kernel32.GetDiskFreeSpaceExW(
        ctypes.c_wchar_p(drive), None, None, ctypes.byref(free))
    return free.value / GB


def dir_size(path):
    """递归目录总大小（字节），跳过 junction 循环名，容错权限错误。"""
    total = 0
    try:
        with os.scandir(path) as it:
            for e in it:
                try:
                    if e.name in JUNCTION_NAMES:
                        continue
                    if e.is_file(follow_symlinks=False):
                        total += e.stat(follow_symlinks=False).st_size
                    elif e.is_dir(follow_symlinks=False):
                        total += dir_size(e.path)
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return total


def expand_path(p):
    """把 %XXX% 占位符展开为真实路径；含未定义占位符时返回 None。"""
    for ph, env in ENV_PLACEHOLDERS.items():
        if ph in p:
            val = os.environ.get(env)
            if not val:
                return None
            p = p.replace(ph, val)
    return p.replace("/", os.sep)


def match_rules(rules_file=None):
    """加载 rules.json，逐条解析路径，返回 [(rule, real_path, size_gb, detail)]。

    mode 支持:
      contents     — 目录内容可清（默认）
      file         — 单个文件可清
      cef_cache    — 匹配父目录下 cef_cache_* 子目录（QQPCMgr 专用）
      keep_latest  — 目录下按版本保留最新（只匹配，调用方决定保留逻辑）
    返回按占用大小降序。
    """
    if rules_file is None:
        rules_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.json")
    if not os.path.isfile(rules_file):
        return []
    with open(rules_file, encoding="utf-8") as f:
        data = json.load(f)
    hits = []
    for r in data.get("rules", []):
        real = expand_path(r["path"])
        if not real or not os.path.exists(real):
            continue
        mode = r.get("mode", "contents")
        if mode == "cef_cache":
            try:
                for name in os.listdir(real):
                    if name.startswith("cef_cache_"):
                        sub = os.path.join(real, name)
                        if os.path.isdir(sub):
                            hits.append((r, sub, dir_size(sub) / GB,
                                         f"{r.get('note', '')} [{name}]"))
            except OSError:
                pass
        elif mode == "file":
            try:
                hits.append((r, real, os.path.getsize(real) / GB, r.get("note", "")))
            except OSError:
                pass
        else:
            hits.append((r, real, dir_size(real) / GB, r.get("note", "")))
    hits.sort(key=lambda h: h[2], reverse=True)
    return hits


def run_elevated_ps(script_body, log_path, timeout=900):
    """把操作写进临时 ps1 提权执行（结果落 log_path，本机 ConsentPromptBehaviorAdmin=0 静默）。

    返回结果文件内容；超时返回 "TIMEOUT waiting result"。
    """
    ps = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command"]
    ps1 = os.path.join(os.environ.get("USERPROFILE", ""), "_jiasu_elevated_op.ps1")
    with open(ps1, "w", encoding="utf-8-sig") as f:
        f.write(script_body)
    subprocess.run(ps + [
        f"Start-Process powershell -Verb RunAs -ArgumentList "
        f"'-NoProfile -ExecutionPolicy Bypass -File {ps1}'"
    ], timeout=30)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(log_path):
            with open(log_path, encoding="utf-8-sig") as f:
                return f.read()
        time.sleep(5)
    return "TIMEOUT waiting result"
