#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重复文件扫描（dupeGuru/jdupes 同款思路，纯 Python 实现，默认只列不删）。

适合: 视频/素材库、下载目录、照片库 —— 跨目录复制常留下大量重复大文件。

算法: 文件大小分组 → 组内比较首 64KB 哈希 → 相同再比较全文 SHA-256。
      分组+二级哈希避免全盘全文哈希，速度可控。

用法:
    python find_duplicates.py "D:/8.9/工作文件夹视频"           # 扫单目录
    python find_duplicates.py "dir1" "dir2"                    # 多目录
    python find_duplicates.py . --min-size 50MB                # 只看大文件
    python find_duplicates.py "dir" --delete --confirm         # 删除每组中除第一个外
    python find_duplicates.py "dir" --delete-to "D:/重复文件"   # 移到回收区(不直接删)

安全: 默认 dry-run 只列重复组。--delete 必须配 --confirm 才执行，
      且每组保留第一个文件（路径字典序最小者），删除其余。
"""
import os
import sys
import shutil
import hashlib
import argparse
from collections import defaultdict

import _common

HEAD_CHUNK = 64 * 1024
FULL_CHUNK = 1024 * 1024
SKIP_EXT = {".lnk", ".tmp", ".log", ".dll", ".exe", ".sys"}


def file_hash(path, full=False):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            if not full:
                data = f.read(HEAD_CHUNK)
                h.update(data)
                return h.hexdigest()
            while True:
                chunk = f.read(FULL_CHUNK)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def scan_dirs(roots, min_size):
    by_size = defaultdict(list)
    total = 0
    for base in roots:
        if not os.path.isdir(base):
            print(f"跳过（不存在）: {base}")
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            # 跳过 junction 循环名；⚠ 必须用 is_reparse 而非 os.path.islink——
            # islink 对 junction 返回 False（只认 symlink），junction 目标会被
            # 重复扫进来当"重复文件"，删错真身
            dirnames[:] = [d for d in dirnames
                           if d not in _common.JUNCTION_NAMES
                           and not _common.is_reparse(os.path.join(dirpath, d))]
            for fn in filenames:
                if os.path.splitext(fn)[1].lower() in SKIP_EXT:
                    continue
                fp = os.path.join(dirpath, fn)
                if _common.is_reparse(fp):
                    continue
                p = fp
                try:
                    sz = os.path.getsize(p)
                except OSError:
                    continue
                if sz >= min_size:
                    by_size[sz].append(p)
                    total += 1
    print(f"扫描完成: {total} 个文件进入分组（≥{min_size/_common.MB:.0f}MB）")
    return by_size


def find_duplicates(by_size):
    """返回 [{'size': int, 'files': [path,...]}] 重复组"""
    groups = []
    for sz, paths in by_size.items():
        if len(paths) < 2:
            continue
        head_groups = defaultdict(list)
        for p in paths:
            h = file_hash(p, full=False)
            if h:
                head_groups[h].append(p)
        for hpaths in head_groups.values():
            if len(hpaths) < 2:
                continue
            full_groups = defaultdict(list)
            for p in hpaths:
                fh = file_hash(p, full=True)
                if fh:
                    full_groups[fh].append(p)
            for fpaths in full_groups.values():
                if len(fpaths) >= 2:
                    groups.append({"size": sz, "files": sorted(fpaths)})
    groups.sort(key=lambda g: -g["size"])
    return groups


def report(groups, show_all=False):
    total_waste = 0
    for g in groups:
        waste = g["size"] * (len(g["files"]) - 1)
        total_waste += waste
        print(f"\n=== {len(g['files'])} 个重复 · 每个 {g['size']/_common.MB:.1f} MB · 可省 {waste/_common.GB:.2f} GB ===")
        for i, f in enumerate(g["files"]):
            mark = "保留" if i == 0 else "  删"
            print(f"  [{mark}] {f}")
    print(f"\n共 {len(groups)} 组重复，总计可释放 {total_waste/_common.GB:.2f} GB")
    return total_waste


def delete_dupes(groups, confirm, move_to=None):
    if not confirm:
        print("--delete 需要同时传 --confirm（安全红线）")
        sys.exit(1)
    if move_to:
        os.makedirs(move_to, exist_ok=True)
    deleted = 0
    failed = 0
    for g in groups:
        for f in g["files"][1:]:  # 保留第一个
            try:
                if move_to:
                    dest = os.path.join(move_to, os.path.basename(f))
                    n = 1
                    while os.path.exists(dest):
                        stem, ext = os.path.splitext(os.path.basename(f))
                        dest = os.path.join(move_to, f"{stem}_{n}{ext}")
                        n += 1
                    # 真移动而非 os.replace：回收区可能与源不在同一卷，
                    # replace 跨卷会抛 OSError 导致 --move-to 实际什么都没移
                    shutil.move(f, dest)
                else:
                    os.chmod(f, 0o666)
                    os.unlink(f)
                deleted += 1
                print(f"  ✂ {f}")
            except OSError as e:
                failed += 1
                print(f"  ✗ {f}: {e}")
    print(f"处理完成: {deleted} 个文件" +
          (f"，失败 {failed} 个" if failed else "") +
          ("（移至回收区）" if move_to else "（已删除）"))


def main():
    ap = argparse.ArgumentParser(description="重复文件扫描（jiasu / dupeGuru 思路）")
    ap.add_argument("dirs", nargs="+", help="要扫描的目录")
    ap.add_argument("--min-size", default="10MB", help="最小文件大小 (默认 10MB)")
    ap.add_argument("--delete", action="store_true", help="删除重复（保留每组第一个）")
    ap.add_argument("--confirm", action="store_true", help="确认删除（必须与 --delete 同用）")
    ap.add_argument("--move-to", default=None, help="移到回收区目录而非直接删除")
    args = ap.parse_args()

    def parse_size(s):
        s = s.strip().upper()
        mult = {"KB": 1024, "MB": 1024**2, "GB": 1024**3}
        for k, m in mult.items():
            if s.endswith(k):
                return int(float(s[:-len(k)]) * m)
        return int(s)

    min_size = parse_size(args.min_size)
    by_size = scan_dirs(args.dirs, min_size)
    groups = find_duplicates(by_size)
    if not groups:
        print("未发现重复文件")
        return
    report(groups)
    if args.delete or args.move_to:
        delete_dupes(groups, args.confirm, args.move_to)


if __name__ == "__main__":
    main()
