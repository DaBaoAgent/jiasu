# disk_scan.py — 扫描C盘关键目录占用
# 用法: python disk_scan.py

import os

def get_size_mb(path):
    """递归计算目录总大小(MB), 不存在返回0"""
    if not os.path.exists(path):
        return 0
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except (OSError, PermissionError):
                    pass
    except PermissionError:
        pass
    return round(total / (1024*1024), 1)

user = os.environ.get("USERPROFILE", "C:/Users/xxx13")
local = os.environ.get("LOCALAPPDATA", f"{user}/AppData/Local")
appdata = os.environ.get("APPDATA", f"{user}/AppData/Roaming")

folders = [
    ("User Temp",       f"{local}/Temp"),
    ("Windows Temp",    "C:/Windows/Temp"),
    ("WinUpdate Cache", "C:/Windows/SoftwareDistribution"),
    ("Downloads",       f"{user}/Downloads"),
    ("pip Cache",       f"{local}/pip/cache"),
    ("npm Cache",       f"{local}/npm-cache"),
    ("npm Cache(Roam)", f"{appdata}/npm-cache"),
    ("uv Cache",        f"{local}/uv/cache"),
    ("Chrome Cache",    f"{local}/Google/Chrome/User Data/Default/Cache"),
    ("Edge Cache",      f"{local}/Microsoft/Edge/User Data/Default/Cache"),
    ("Tencent(微信QQ)", f"{appdata}/Tencent"),
    ("WeChat Files",    f"{user}/Documents/WeChat Files"),
    ("User .cache",     f"{user}/.cache"),
    ("CrashDumps",      f"{local}/CrashDumps"),
    ("Prefetch",        "C:/Windows/Prefetch"),
    ("NuGet Cache",     f"{user}/.nuget/packages"),
]

print(f"{'Name':<25} {'Size(MB)':>10}  Path")
print("-" * 90)
for name, path in folders:
    size = get_size_mb(path)
    marker = "!!!" if size > 1000 else ("**" if size > 100 else "")
    if size > 0:
        print(f"{name:<25} {size:>10.1f} {marker}  {path}")

# 系统大文件
print(f"\n=== 系统大文件 ===")
for f in ["C:/hiberfil.sys", "C:/pagefile.sys", "C:/swapfile.sys"]:
    if os.path.exists(f):
        size = os.path.getsize(f) / (1024*1024)
        print(f"  {size:>10.1f} MB  {f}")

# .cache 子目录展开
print(f"\n=== .cache 子目录 ===")
cache = f"{user}/.cache"
if os.path.exists(cache):
    for item in sorted(os.listdir(cache)):
        p = os.path.join(cache, item)
        if os.path.isdir(p):
            sz = get_size_mb(p)
            print(f"  {sz:>8.1f} MB  {item}")

# 磁盘空间汇总
import ctypes
print(f"\n=== 磁盘空间 ===")
for drive in ["C:", "D:", "E:"]:
    free = ctypes.c_ulonglong(0)
    total = ctypes.c_ulonglong(0)
    ok = ctypes.windll.kernel32.GetDiskFreeSpaceExW(
        ctypes.c_wchar_p(drive + chr(92)),
        None, ctypes.byref(total), ctypes.byref(free))
    if ok:
        free_gb = free.value / (1024**3)
        total_gb = total.value / (1024**3)
        print(f"  {drive} Total={total_gb:.0f}GB  Free={free_gb:.1f}GB  ({free_gb/total_gb*100:.0f}%)")
