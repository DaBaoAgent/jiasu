#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jiasu 公共工具 — scripts/ 下各脚本共用。

- free_gb / dir_size：磁盘剩余 / 目录大小（二进制单位 1024^3，与 daily_clean 一致）
- is_reparse / JUNCTION_NAMES：递归扫描/删除时跳过 junction/reparse point（防穿透删目标、防假占用）
- decode_console：控制台输出统一解码（本机 netsh/powershell 可能输出 UTF-8 或 GBK，先试 UTF-8 再试 GBK）
- expand_path / match_rules：rules.json 规则库解析（deep_scan / health_check / daily_clean 共用）
- run_elevated_ps：写临时 ps1 + Start-Process -Verb RunAs + 完成标记轮询（本机免 UAC 静默）

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

# FILE_ATTRIBUTE_REPARSE_POINT (0x400) — junction/symlink 标志位
FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def is_reparse(path):
    """路径（目录/文件）是否为 reparse point（junction / symlink）。

    删除/扫描必须跳过：rm_contents 穿透 junction 会删到目标真身（数据丢失级），
    dir_size 穿透会重复计数/假占用（ProgramData/Application Data 类）。
    """
    try:
        st = os.lstat(path)
        return bool(getattr(st, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return True  # 拿不到属性时按"不可碰"处理（保守）


def decode_console(raw):
    """控制台命令输出统一解码。

    本机实测：netsh / powershell 在不同宿主下分别输出 UTF-8 或 GBK，
    单一按 GBK 解码会直接抛 UnicodeDecodeError（dns_tool 曾因此整体失效）。
    先严格试 UTF-8，再严格试 GBK，都失败才带 replace 兜底。
    """
    if raw is None:
        return ""
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def free_gb(drive="C:\\"):
    """磁盘剩余空间（GB，二进制单位）。"""
    free = ctypes.c_ulonglong(0)
    ctypes.windll.kernel32.GetDiskFreeSpaceExW(
        ctypes.c_wchar_p(drive), None, None, ctypes.byref(free))
    return free.value / GB


def dir_size(path):
    """递归目录总大小（字节），跳过 junction/reparse 循环名，容错权限错误。"""
    total = 0
    try:
        with os.scandir(path) as it:
            for e in it:
                try:
                    if e.name in JUNCTION_NAMES:
                        continue
                    if e.is_dir(follow_symlinks=False):
                        if is_reparse(e.path):
                            continue
                        total += dir_size(e.path)
                    elif e.is_file(follow_symlinks=False):
                        total += e.stat(follow_symlinks=False).st_size
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
    规则可选字段 min_age_days：contents 清理时跳过 mtime 更新的文件（Temp 防误删运行中文件）。
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


def run_elevated_ps(script_body, log_path, timeout=900, done_marker=None):
    """把操作写进临时 ps1 提权执行（结果落 log_path，本机 ConsentPromptBehaviorAdmin=0 静默）。

    done_marker: 提权脚本结束时应输出该标记（如 "[DONE]"）；给出后轮询直到文件含标记。
    launcher 不等待提权进程（全盘查杀 1-3 小时，等会被外层超时误杀）——
    它只负责确认 UAC：用户拒绝/启动失败立即返回错误；成功则立刻返回并进入结果轮询，
    轮询上限 = timeout（quick 查杀 5-15 分钟、full 1-3 小时都够）。

    返回结果文件内容；UAC 被拒/启动失败返回 "UAC_DECLINED ..."；超时 "TIMEOUT waiting result"。
    """
    ps = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command"]
    ps1 = os.path.join(os.environ.get("USERPROFILE", ""), "_jiasu_elevated_op.ps1")
    with open(ps1, "w", encoding="utf-8-sig") as f:
        f.write(script_body)
    launcher = (
        "try { Start-Process powershell -Verb RunAs -WindowStyle Hidden -ErrorAction Stop "
        f"-ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"{ps1}\"' }} "
        "catch { Write-Output ('UAC_FAIL: ' + $_.Exception.Message); exit 1 }"
    )
    try:
        r = subprocess.run(ps + [launcher], capture_output=True, timeout=120)
    except subprocess.TimeoutExpired:
        return "TIMEOUT waiting UAC confirm (120s) — 用户可能未点确认"
    out = (r.stdout or b"").decode("utf-8", errors="replace")
    err = (r.stderr or b"").decode("utf-8", errors="replace")
    if r.returncode != 0 or "UAC_FAIL" in out:
        low = (out + err).lower()
        if "canceled by the user" in low or "用户取消" in (out + err):
            return "UAC_DECLINED: 用户拒绝了 UAC 弹窗，操作未执行"
        return f"UAC_DECLINED: 提权启动失败 (exit={r.returncode}) {(out + err).strip()[:300]}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(log_path):
            with open(log_path, encoding="utf-8-sig") as f:
                content = f.read()
            if done_marker is None or done_marker in content:
                return content
        time.sleep(5)
    return "TIMEOUT waiting result"


