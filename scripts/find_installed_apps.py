#!/usr/bin/env python3
"""查找软件安装位置 — 扫描 Program Files / AppData / Desktop / Start Menu。

当用户要求卸载某个软件（如 TRAE、openclaw）时，需先确认所有残留位置。
标准路径并不总能命中——TRAE 装在 AppData/Local/Programs，openclaw 是 npm 全局包。
这个脚本覆盖常规安装位 + 快捷方式，比手动 `find` 更快。

用法: python find_installed_apps.py <keyword1> [keyword2...]
示例: python find_installed_apps.py trae openclaw
"""
import os
import sys

def dir_size(path):
    total = 0
    if not os.path.exists(path):
        return 0
    try:
        with os.scandir(path) as it:
            for e in it:
                try:
                    if e.is_file(follow_symlinks=False):
                        total += e.stat().st_size
                    elif e.is_dir(follow_symlinks=False):
                        total += dir_size(e.path)
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return total


def scan_directory(base, keyword, label=""):
    """在 base 目录下查找名称含 keyword 的目录/文件"""
    results = []
    if not os.path.exists(base):
        return results
    try:
        with os.scandir(base) as it:
            for e in it:
                if keyword.lower() in e.name.lower():
                    if e.is_dir(follow_symlinks=False):
                        sz = dir_size(e.path)
                        results.append((sz, e.path))
                    elif e.is_file(follow_symlinks=False):
                        results.append((e.stat().st_size, e.path))
    except (OSError, PermissionError):
        pass
    return results


def scan_recursive(base, keyword, max_depth=3):
    """递归扫描（用于 Start Menu）"""
    results = []
    if not os.path.exists(base):
        return results
    try:
        for root, dirs, files in os.walk(base):
            depth = root[len(base):].count(os.sep)
            if depth > max_depth:
                dirs.clear()
                continue
            for d in dirs:
                if keyword.lower() in d.lower():
                    results.append((0, os.path.join(root, d)))
            for f in files:
                if keyword.lower() in f.lower():
                    results.append((0, os.path.join(root, f)))
    except (OSError, PermissionError):
        pass
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python find_installed_apps.py <keyword1> [keyword2...]")
        sys.exit(1)

    keywords = sys.argv[1:]
    up = os.environ["USERPROFILE"]
    la = os.environ["LOCALAPPDATA"]
    ro = os.environ["APPDATA"]

    search_bases = [
        (f"{la}/Programs", os.path.join(la, "Programs")),
        ("C:/Program Files", "C:/Program Files"),
        ("C:/Program Files (x86)", "C:/Program Files (x86)"),
        (f"{ro}", ro),
        (f"{up}", up),
        ("C:/ProgramData", "C:/ProgramData"),
    ]

    # Start Menu shortcuts
    start_menu = os.path.join(ro, "Microsoft", "Windows", "Start Menu", "Programs")
    # Desktop
    desktop = os.path.join(up, "Desktop")
    # npm global
    npm_global = os.path.join(ro, "npm", "node_modules")

    for kw in keywords:
        print(f"\n{'='*60}")
        print(f"  Searching for: {kw}")
        print(f"{'='*60}")

        found_any = False

        # 1. Standard install dirs
        for label, base in search_bases:
            hits = scan_directory(base, kw, label)
            if hits:
                found_any = True
                print(f"\n  [{label}]")
                for sz, path in sorted(hits, reverse=True):
                    if sz > 0:
                        print(f"    {sz/1e9:7.2f} GB  {path}")
                    else:
                        print(f"           --  {path}")

        # 2. Start Menu
        if os.path.exists(start_menu):
            hits = scan_recursive(start_menu, kw)
            if hits:
                found_any = True
                print(f"\n  [Start Menu]")
                for _, path in hits:
                    print(f"           --  {path}")

        # 3. Desktop
        if os.path.exists(desktop):
            hits = scan_directory(desktop, kw, "Desktop")
            if hits:
                found_any = True
                print(f"\n  [Desktop]")
                for _, path in hits:
                    print(f"           --  {path}")

        # 4. npm global
        if os.path.exists(npm_global):
            hits = scan_directory(npm_global, kw, "npm global")
            if hits:
                found_any = True
                print(f"\n  [npm global node_modules]")
                for sz, path in sorted(hits, reverse=True):
                    if sz > 0:
                        print(f"    {sz/1e9:7.2f} GB  {path}")
                    else:
                        print(f"           --  {path}")

        if not found_any:
            print(f"  (no matches found for '{kw}')")


if __name__ == "__main__":
    main()
