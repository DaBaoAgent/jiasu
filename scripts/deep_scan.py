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

公共工具（dir_size/free_gb/JUNCTION_NAMES/match_rules）见 _common.py。
"""
import os
import sys

import _common

RULES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.json")


def scan_children(base, min_gb=0.5):
    """列出 base 下 ≥min_gb 的直接子目录（跳过 junction/reparse），按大小降序。"""
    results = []
    try:
        with os.scandir(base) as it:
            for e in it:
                if not e.is_dir(follow_symlinks=False):
                    continue
                if e.name in _common.JUNCTION_NAMES or _common.is_reparse(e.path):
                    continue
                sz = _common.dir_size(e.path)
                if sz / _common.GB >= min_gb:
                    results.append((sz, e.path))
    except (OSError, PermissionError):
        pass
    results.sort(reverse=True)
    return results


def scan_rules():
    """--rules 模式主流程：输出已知可清项（按占用排序）"""
    print("\n===== rules.json 规则库匹配（已知可清项） =====")
    hits = _common.match_rules(RULES_FILE)
    if not hits:
        print("（无命中）")
        return
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
    print(f"C: free = {_common.free_gb():.2f} GB")
    d_free = _common.free_gb("D:\\")
    print(f"D: free = {d_free:.2f} GB\n")
    for base in bases:
        if os.path.exists(base):
            print(f"=== {base} (folders >= 0.5 GB) ===")
            for sz, path in scan_children(base, 0.5):
                print(f"{sz/_common.GB:8.2f} GB  {path}")
            print()

    # 常见大户的下钻提示
    la = os.environ.get("LOCALAPPDATA", "")
    jy_cache = os.path.join(la, "JianyingPro", "User Data", "Cache")
    if os.path.exists(jy_cache):
        print(f"[hint] 剪映缓存 {_common.dir_size(jy_cache)/_common.GB:.2f} GB @ {jy_cache}")
        print("       -> User Data\\Cache 可删；User Data\\Projects(草稿)不可删")
    for f in ["C:/pagefile.sys", "C:/hiberfil.sys", "C:/swapfile.sys"]:
        if os.path.exists(f):
            try:
                print(f"[hint] {os.path.getsize(f)/_common.GB:.2f} GB  {f}")
            except OSError:
                pass

    if use_rules:
        scan_rules()


if __name__ == "__main__":
    main()
