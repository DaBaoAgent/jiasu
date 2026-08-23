#!/usr/bin/env python3
"""顶层目录广扫 — 找出 C 盘真实占用大户（剪映/美图/浏览器等）。

固定缓存清单会漏掉最大占用者（真实案例：剪映缓存 36GB 不在常规清单里）。
清理前先跑这个脚本，看清谁在占空间，再决定策略。

用法（用系统 Python，避开 .cache/codex-runtimes 里的 python.exe）:
    /c/Users/<user>/AppData/Local/Programs/Python/Python312/python.exe deep_scan.py
    # 或直接: python deep_scan.py
    python deep_scan.py --rules        # 额外加载 rules.json 规则库，标出已知可清项

--rules 模式（Dism++ 式规则库，2026-08 新增）：
    读取同目录 rules.json，解析 %LOCALAPPDATA% 等占位符，命中即输出
    占用 GB + 风险级 + 说明。新增软件缓存规则只改 rules.json，不用改代码。
"""
import os
import sys
import json
import ctypes

# junction / reparse 循环名 —— 跳过，否则算出上百 GB 的假占用
JUNCTION_NAMES = {"Application Data", "Local Settings", "Cookies", "History",
                  "Temporary Internet Files", "My Documents", "NetHood", "PrintHood",
                  "Recent", "SendTo", "Start Menu", "Templates"}

RULES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.json")

ENV_PLACEHOLDERS = {
    "%USERPROFILE%": "USERPROFILE",
    "%LOCALAPPDATA%": "LOCALAPPDATA",
    "%APPDATA%": "APPDATA",
    "%TEMP%": "TEMP",
    "%SystemRoot%": "SystemRoot",
    "%ProgramData%": "ProgramData",
}


def expand_path(p):
    """把 %XXX% 占位符展开为真实路径；含未定义占位符时返回 None。"""
    for ph, env in ENV_PLACEHOLDERS.items():
        if ph in p:
            val = os.environ.get(env)
            if not val:
                return None
            p = p.replace(ph, val)
    return p.replace("/", os.sep)


def free_gb(drive="C:\\"):
    free = ctypes.c_ulonglong(0)
    ctypes.windll.kernel32.GetDiskFreeSpaceExW(
        ctypes.c_wchar_p(drive), None, None, ctypes.byref(free))
    return free.value / 1e9


def dir_size(path):
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


def scan_children(base, min_gb=0.5):
    results = []
    try:
        with os.scandir(base) as it:
            for e in it:
                if e.is_dir(follow_symlinks=False) and e.name not in JUNCTION_NAMES:
                    sz = dir_size(e.path)
                    if sz / 1e9 >= min_gb:
                        results.append((sz, e.path))
    except (OSError, PermissionError):
        pass
    results.sort(reverse=True)
    return results


def match_rules():
    """加载 rules.json，逐条解析路径，返回命中列表 [(rule, real_path, size_gb, detail)]"""
    if not os.path.isfile(RULES_FILE):
        print(f"[rules] 未找到 {RULES_FILE}，跳过规则匹配", file=sys.stderr)
        return []
    with open(RULES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    hits = []
    for r in data.get("rules", []):
        real = expand_path(r["path"])
        if not real or not os.path.exists(real):
            continue
        if r.get("mode") == "cef_cache":
            # 匹配父目录下 cef_cache_* 子目录（QQPCMgr 专用）
            try:
                for name in os.listdir(real):
                    if name.startswith("cef_cache_"):
                        sub = os.path.join(real, name)
                        if os.path.isdir(sub):
                            hits.append((r, sub, dir_size(sub) / 1e9,
                                         f"{r.get('note','')} [{name}]"))
            except OSError:
                pass
        elif r.get("mode") == "file":
            try:
                hits.append((r, real, os.path.getsize(real) / 1e9, r.get("note", "")))
            except OSError:
                pass
        else:
            hits.append((r, real, dir_size(real) / 1e9, r.get("note", "")))
    return hits


def scan_rules():
    """--rules 模式主流程：输出已知可清项（按占用排序）"""
    print("\n===== rules.json 规则库匹配（已知可清项） =====")
    hits = match_rules()
    if not hits:
        print("（无命中）")
        return
    hits.sort(key=lambda h: h[2], reverse=True)
    for r, real, size, note in hits:
        if size < 0.05:
            continue
        risk = r.get("risk", "safe")
        mode = r.get("mode", "contents")
        extra = f" | {note}" if note else ""
        print(f"{size:8.2f} GB  [{risk}/{mode}] {r['name']}{extra}")
        print(f"            {real}")
    total = sum(h[2] for h in hits)
    print(f"\n规则库可清项合计: {total:.2f} GB（含 moderate 项，清理前逐项确认）")


def main():
    use_rules = "--rules" in sys.argv
    up = os.environ.get("USERPROFILE", "")
    bases = [
        up,
        os.path.join(up, "AppData", "Local"),
        os.path.join(up, "AppData", "Roaming"),
        "C:/Program Files",
        "C:/Program Files (x86)",
        "C:/ProgramData",
        "D:/Program Files",
        "D:/Program Files (x86)",
    ]
    print(f"C: free = {free_gb():.2f} GB")
    d_free = free_gb("D:\\")
    print(f"D: free = {d_free:.2f} GB\n")
    for base in bases:
        if os.path.exists(base):
            print(f"=== {base} (folders >= 0.5 GB) ===")
            for sz, path in scan_children(base, 0.5):
                print(f"{sz/1e9:8.2f} GB  {path}")
            print()

    # 常见大户的下钻提示
    la = os.environ.get("LOCALAPPDATA", "")
    jy_cache = os.path.join(la, "JianyingPro", "User Data", "Cache")
    if os.path.exists(jy_cache):
        print(f"[hint] 剪映缓存 {dir_size(jy_cache)/1e9:.2f} GB @ {jy_cache}")
        print("       -> User Data\\Cache 可删；User Data\\Projects(草稿)不可删")
    for f in ["C:/pagefile.sys", "C:/hiberfil.sys", "C:/swapfile.sys"]:
        if os.path.exists(f):
            try:
                print(f"[hint] {os.path.getsize(f)/1e9:.2f} GB  {f}")
            except OSError:
                pass

    if use_rules:
        scan_rules()


if __name__ == "__main__":
    main()

