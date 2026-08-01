#!/usr/bin/env python3
"""顶层目录广扫 — 找出 C 盘真实占用大户（剪映/美图/浏览器等）。

固定缓存清单会漏掉最大占用者（真实案例：剪映缓存 36GB 不在常规清单里）。
清理前先跑这个脚本，看清谁在占空间，再决定策略。

用法（用系统 Python，避开 .cache/codex-runtimes 里的 python.exe）:
    /c/Users/<user>/AppData/Local/Programs/Python/Python312/python.exe deep_scan.py
    # 或直接: python deep_scan.py
"""
import os
import ctypes

# junction / reparse 循环名 —— 跳过，否则算出上百 GB 的假占用
JUNCTION_NAMES = {"Application Data", "Local Settings", "Cookies", "History",
                  "Temporary Internet Files", "My Documents", "NetHood", "PrintHood",
                  "Recent", "SendTo", "Start Menu", "Templates"}


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


def main():
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
    d_free = free_gb("D:\\\\")
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


if __name__ == "__main__":
    main()
