#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jiasu 每日自动清理（免 UAC 模式）：测量 -> 安全删除 -> 逐项报告释放 GB

清理来源（单一事实源，2026-08-29 重构）:
  1) rules.json 规则库中 risk=safe 且 mode in (contents/file/cef_cache) 的项
     —— 新增软件缓存规则只改 rules.json，本脚本自动生效，无需改代码
  2) 内置复杂逻辑（rules.json 表达不了的）: 剪映 Projects 安全检查、
     浏览器 profile 缓存展开、微信/QQ Image/Video/File 递归、Hermes/Codex 特殊项

用法:
    python daily_clean_no_uac.py            # 默认：规则库 + 内置复杂项（cron 用）
    python daily_clean_no_uac.py --rules    # 只清规则库（调试/验证规则用）

公共工具（dir_size/free_gb/match_rules）见 _common.py。
"""
import os
import stat
import re
import sys
import json
import ctypes

import _common

USERPROFILE = os.environ.get('USERPROFILE', 'C:/Users/xxx13')
LOCALAPPDATA = os.environ.get('LOCALAPPDATA', USERPROFILE + '/AppData/Local')
APPDATA = os.environ.get('APPDATA', USERPROFILE + '/AppData/Roaming')
TEMP = os.environ.get('TEMP', LOCALAPPDATA + '/Temp')

# 清理前可用空间（脚本开头测量；结尾测的是 after，2026-08-29 合并本地实战修复）
c_free_start_gb = round(_common.free_gb('C:\\'), 3)


def rm_contents(path):
    """删除目录下所有内容（保留根目录），返回跳过的条目数"""
    skipped = 0
    try:
        with os.scandir(path) as it:
            for e in it:
                try:
                    if e.is_file(follow_symlinks=False):
                        os.chmod(e.path, stat.S_IWRITE)
                        os.unlink(e.path)
                    elif e.is_dir(follow_symlinks=False):
                        skipped += rm_contents(e.path)
                        try:
                            os.rmdir(e.path)
                        except OSError:
                            skipped += 1
                except (PermissionError, OSError):
                    skipped += 1
    except (PermissionError, OSError):
        skipped += 1
    return skipped


def rm_files_by_pattern(path, pattern):
    """按文件名正则删除文件（保留目录），返回释放字节数"""
    freed = 0
    try:
        for name in os.listdir(path):
            if re.search(pattern, name):
                p = os.path.join(path, name)
                try:
                    sz = os.path.getsize(p)
                    os.chmod(p, stat.S_IWRITE)
                    os.unlink(p)
                    freed += sz
                except (PermissionError, OSError):
                    pass
    except (PermissionError, OSError):
        pass
    return freed


def clean_item(name, path, mode='contents'):
    """测量 -> 删除 -> 返回 (name, before_gb, freed_gb, skipped)"""
    if not path or not os.path.exists(path):
        return (name, 0.0, 0.0, 0)
    before = _common.dir_size(path) if mode == 'contents' else os.path.getsize(path) if os.path.isfile(path) else _common.dir_size(path)
    if mode == 'contents':
        skipped = rm_contents(path)
        after = _common.dir_size(path)
        freed = before - after
    elif mode == 'file':
        try:
            os.chmod(path, stat.S_IWRITE)
            os.unlink(path)
            skipped, freed = 0, before
        except (PermissionError, OSError):
            skipped, freed = 1, 0.0
    return (name, before / _common.GB, freed / _common.GB, skipped)


results = []


def report(name, path, mode='contents'):
    n, before, freed, skipped = clean_item(name, path, mode)
    if before > 0.001 or freed > 0.001:
        results.append({'name': n, 'before_gb': round(before, 3),
                        'freed_gb': round(freed, 3), 'skipped': skipped})


CACHE_SUBS = ["Cache", "Code Cache", "GPUCache", "DawnGraphiteCache",
              "DawnWebGPUCache", "Service Worker", "DeferredBrowserMetrics"]


def clean_browser_profiles(base, label):
    """对 base 下所有 profile 目录（Default/Profile N）清理缓存子目录"""
    if not os.path.isdir(base):
        return
    try:
        profiles = [os.path.join(base, d) for d in os.listdir(base)
                    if os.path.isdir(os.path.join(base, d))]
    except OSError:
        return
    for prof in profiles:
        for sub in CACHE_SUBS:
            p = os.path.join(prof, sub)
            if os.path.isdir(p):
                report(f"{label}/{os.path.basename(prof)}/{sub}", p)


def clean_by_rules():
    """规则库清理：risk=safe 且 mode in (contents/file/cef_cache)。
    keep_latest（旧版本保留逻辑）与 moderate（需人工确认）跳过。
    """
    hits = _common.match_rules()
    for r, real, size, note in hits:
        risk = r.get("risk", "safe")
        mode = r.get("mode", "contents")
        if risk != "safe":
            continue
        if mode == "keep_latest":
            continue  # 旧版本保留逻辑在内置剪映块/手动指引，不自动删
        report(r["name"], real, "file" if mode == "file" else "contents")


RULES_ONLY = "--rules" in sys.argv

# ---------- 1. 规则库（简单缓存项，单一事实源）----------
clean_by_rules()

if not RULES_ONLY:
    # ---------- 2. SystemProfile 下 tw-*.tmp（Windows Update 任务残留）----------
    n, before, freed, skipped = clean_item("SystemProfile tw-*.tmp",
        "C:/Windows/System32/config/systemprofile/AppData/Local", 'contents')
    # 只统计匹配文件的释放（单独处理）
    tw_freed = rm_files_by_pattern("C:/Windows/System32/config/systemprofile/AppData/Local", r'^tw-.*\.tmp$')
    if tw_freed > 1e6:
        results.append({'name': 'SystemProfile tw-*.tmp', 'before_gb': round(tw_freed/_common.GB, 3),
                        'freed_gb': round(tw_freed/_common.GB, 3), 'skipped': 0})

    # ---------- 3. 剪映缓存（绝不碰 Projects）----------
    jianying = LOCALAPPDATA + "/JianyingPro/User Data"
    if os.path.isdir(jianying + "/Cache"):
        # 先确认 Cache 下没有 Projects/draft 字样
        try:
            names = os.listdir(jianying + "/Cache")
        except OSError:
            names = []
        bad = [n for n in names if re.search(r'project|draft', n, re.I)]
        if bad:
            print("WARN: Jianying Cache 含疑似工程目录，跳过: %s" % bad)
        else:
            for sub in names:
                report("Jianying Cache/" + sub, jianying + "/Cache/" + sub)
    # 旧版本 App 清理（保留版本号最高者）
    apps_dir = LOCALAPPDATA + "/JianyingPro/Apps"
    if os.path.isdir(apps_dir):
        try:
            versions = [d for d in os.listdir(apps_dir)
                        if os.path.isdir(os.path.join(apps_dir, d)) and re.search(r'\d', d)]
        except OSError:
            versions = []
        if len(versions) > 1:
            def vkey(name):
                return tuple(int(x) for x in re.findall(r'\d+', name) or [0])
            keep = max(versions, key=vkey)
            for v in versions:
                if v != keep:
                    report("Jianying old App " + v, os.path.join(apps_dir, v))

    # ---------- 4. 浏览器缓存（Chrome / Edge）----------
    clean_browser_profiles(LOCALAPPDATA + "/Google/Chrome/User Data", "Chrome")
    clean_browser_profiles(LOCALAPPDATA + "/Microsoft/Edge/User Data", "Edge")

    # ---------- 5. 微信/QQ Image/Video/File 缓存（递归）----------
    tencent = APPDATA + "/Tencent"
    if os.path.isdir(tencent):
        for root, dirs, files in os.walk(tencent):
            dirs[:] = [d for d in dirs if d not in ("SysOpt.ini",)]
            base = os.path.basename(root)
            if base in ("Image", "Video", "File") and "QQPCMgr" not in root:
                report("Tencent/" + base, root)

    # ---------- 6. Hermes 自有缓存（特殊项；screenshots/tmp/terminal 走规则库）----------
    hermes = USERPROFILE + "/.hermes"
    if os.path.isdir(hermes):
        gw = hermes + "/logs/gateway_stdout.log"
        if os.path.isfile(gw):
            report(".hermes/gateway_stdout.log", gw, 'file')
        # 旧轮转日志 *.log.1 *.log.2 ...
        logs_dir = hermes + "/logs"
        if os.path.isdir(logs_dir):
            freed = 0
            try:
                for name in os.listdir(logs_dir):
                    m = re.match(r'.+\.log\.\d+$', name)
                    if m:
                        p = os.path.join(logs_dir, name)
                        try:
                            sz = os.path.getsize(p)
                            os.chmod(p, stat.S_IWRITE)
                            os.unlink(p)
                            freed += sz
                        except (PermissionError, OSError):
                            pass
            except OSError:
                pass
            if freed > 1e6:
                results.append({'name': '.hermes 旧轮转日志', 'before_gb': round(freed/_common.GB, 3),
                                'freed_gb': round(freed/_common.GB, 3), 'skipped': 0})
        # 旧会话 dump（仅 *.json，不动 state.db）
        sess = hermes + "/sessions"
        if os.path.isdir(sess):
            freed = 0
            try:
                for name in os.listdir(sess):
                    if name.endswith('.json'):
                        p = os.path.join(sess, name)
                        try:
                            sz = os.path.getsize(p)
                            os.chmod(p, stat.S_IWRITE)
                            os.unlink(p)
                            freed += sz
                        except (PermissionError, OSError):
                            pass
            except OSError:
                pass
            if freed > 1e6:
                results.append({'name': '.hermes/sessions 旧 dump', 'before_gb': round(freed/_common.GB, 3),
                                'freed_gb': round(freed/_common.GB, 3), 'skipped': 0})
        # Hermes 内置浏览器 profile 缓存
        bps = hermes + "/browser-profiles"
        if os.path.isdir(bps):
            try:
                for bp in os.listdir(bps):
                    clean_browser_profiles(os.path.join(bps, bp), ".hermes/browser-profiles/" + bp)
            except OSError:
                pass

    # ---------- 7. Codex 自有缓存（特殊项；logs_2.sqlite/.tmp/generated_images 走规则库）----------
    codex = USERPROFILE + "/.codex"
    if os.path.isdir(codex):
        for f in ["logs_2.sqlite-wal", "logs_2.sqlite-shm"]:
            p = os.path.join(codex, f)
            if os.path.isfile(p):
                report(".codex/" + f, p, 'file')

# ---------- 回收站（SHEmptyRecycleBinW，API 不返回释放量，记 -1 不计入总量）----------

def empty_recycle_bin(drive='C:'):
    try:
        # SHERB_NOCONFIRMATION|SHERB_NOPROGRESSUI|SHERB_NOSOUND = 0x7
        return ctypes.windll.shell32.SHEmptyRecycleBinW(None, drive, 0x7) == 0
    except Exception:
        return False

if empty_recycle_bin('C:'):
    results.append({'name': '回收站(C:)', 'before_gb': -1, 'freed_gb': -1, 'skipped': 0})
    # before_gb=-1 表示已清空但大小未知（API 不返回释放量），汇总时不计入总量

# ---------- 汇总 ----------
total_freed = sum(r['freed_gb'] for r in results if r['freed_gb'] > 0)
print(json.dumps({'results': results, 'total_freed_gb': round(total_freed, 3),
                  'c_free_before_gb': c_free_start_gb,
                  'c_free_after_gb': round(_common.free_gb('C:\\'), 3)}, ensure_ascii=False, indent=1))
