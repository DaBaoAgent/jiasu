#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jiasu 每日自动清理（免 UAC 模式）：测量 -> 安全删除 -> 逐项报告释放 GB"""
import os, stat, ctypes, re, sys, json

USERPROFILE = os.environ.get('USERPROFILE', 'C:/Users/xxx13')
LOCALAPPDATA = os.environ.get('LOCALAPPDATA', USERPROFILE + '/AppData/Local')
APPDATA = os.environ.get('APPDATA', USERPROFILE + '/AppData/Roaming')
TEMP = os.environ.get('TEMP', LOCALAPPDATA + '/Temp')

def free_gb(drive='C:\\'):
    free = ctypes.c_ulonglong(0)
    ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(drive), ctypes.byref(free), None, None)
    return free.value / 1e9

def dir_size(path):
    total = 0
    try:
        with os.scandir(path) as it:
            for e in it:
                try:
                    if e.is_file(follow_symlinks=False):
                        total += e.stat(follow_symlinks=False).st_size
                    elif e.is_dir(follow_symlinks=False):
                        total += dir_size(e.path)
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return total

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

def rm_full(path):
    """整目录删除（含根），返回释放字节数"""
    before = dir_size(path)
    skipped = rm_contents(path)
    try:
        os.rmdir(path)
    except OSError:
        pass
    return before if skipped == 0 else before  # 近似：删除成功部分

def clean_item(name, path, mode='contents'):
    """测量 -> 删除 -> 返回 (name, before_gb, freed_gb, skipped)"""
    if not path or not os.path.exists(path):
        return (name, 0.0, 0.0, 0)
    before = dir_size(path) if mode == 'contents' else os.path.getsize(path) if os.path.isfile(path) else dir_size(path)
    if mode == 'contents':
        skipped = rm_contents(path)
        after = dir_size(path)
        freed = before - after
    elif mode == 'file':
        try:
            os.chmod(path, stat.S_IWRITE)
            os.unlink(path)
            skipped, freed = 0, before
        except (PermissionError, OSError):
            skipped, freed = 1, 0.0
    return (name, before / 1e9, freed / 1e9, skipped)

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

# ---------- 1. 包管理器缓存 ----------
report("pip cache (Local)", LOCALAPPDATA + "/pip/cache")
report("pip cache (Roaming)", APPDATA + "/pip/cache")
report("uv cache", LOCALAPPDATA + "/uv/cache")
report("npm-cache (Local)", LOCALAPPDATA + "/npm-cache")
report("npm-cache (Roaming)", APPDATA + "/npm-cache")

# ---------- 2. 系统/用户临时文件 ----------
report("TEMP", TEMP)
report("C:/Windows/Temp", "C:/Windows/Temp")
report("C:/Windows/Prefetch", "C:/Windows/Prefetch")
report("CrashDumps", LOCALAPPDATA + "/CrashDumps")
report("WER", LOCALAPPDATA + "/Microsoft/Windows/WER")

# ---------- 3. 系统残留目录 ----------
for d in ["$WinREAgent", "$SysReset", "$Windows.~WS", "$GetCurrent", "ESD"]:
    report("C:/" + d, "C:/" + d)
report("C:/Intel", "C:/Intel")
report("C:/PerfLogs", "C:/PerfLogs")
report("NetworkService Temp", "C:/Windows/ServiceProfiles/NetworkService/AppData/Local/Temp")

# SystemProfile 下 tw-*.tmp（Windows Update 任务残留）
n, before, freed, skipped = clean_item("SystemProfile tw-*.tmp",
    "C:/Windows/System32/config/systemprofile/AppData/Local", 'contents')
# 只统计匹配文件的释放（单独处理）
tw_freed = rm_files_by_pattern("C:/Windows/System32/config/systemprofile/AppData/Local", r'^tw-.*\.tmp$')
if tw_freed > 1e6:
    results.append({'name': 'SystemProfile tw-*.tmp', 'before_gb': round(tw_freed/1e9, 3),
                    'freed_gb': round(tw_freed/1e9, 3), 'skipped': 0})

# ---------- 4. 剪映缓存（绝不碰 Projects）----------
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

# ---------- 5. 浏览器缓存（Chrome / Edge）----------
clean_browser_profiles(LOCALAPPDATA + "/Google/Chrome/User Data", "Chrome")
clean_browser_profiles(LOCALAPPDATA + "/Microsoft/Edge/User Data", "Edge")

# ---------- 6. 微信/QQ Image/Video/File 缓存 ----------
tencent = APPDATA + "/Tencent"
if os.path.isdir(tencent):
    for root, dirs, files in os.walk(tencent):
        dirs[:] = [d for d in dirs if d not in ("SysOpt.ini",)]
        base = os.path.basename(root)
        if base in ("Image", "Video", "File") and "QQPCMgr" not in root:
            report("Tencent/" + base, root)

# ---------- 7. QQPCMgr 自身缓存（保留 SysOpt.ini）----------
for sub in ["radiumv3", "beacon", "Download", "QMLauncher"]:
    report("QQPCMgr/" + sub, APPDATA + "/Tencent/QQPCMgr/" + sub)
for sub in ["cef_cache_qmui", "cef_cache_qmaiservice64"]:
    report("QQPCMgr(Local)/" + sub, LOCALAPPDATA + "/Tencent/QQPCMgr/" + sub)

# ---------- 8. ima.copilot 缓存 ----------
for sub in ["reshub", "component_crx_cache"]:
    report("ima.copilot/" + sub, APPDATA + "/ima.copilot/User Data/" + sub)

# ---------- 9. Hermes 自有缓存 ----------
hermes = USERPROFILE + "/.hermes"
if os.path.isdir(hermes):
    report(".hermes/logs/screenshots", hermes + "/logs/screenshots")
    report(".hermes/tmp", hermes + "/tmp")
    report(".hermes/cache/terminal", hermes + "/cache/terminal")
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
            results.append({'name': '.hermes 旧轮转日志', 'before_gb': round(freed/1e9, 3),
                            'freed_gb': round(freed/1e9, 3), 'skipped': 0})
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
            results.append({'name': '.hermes/sessions 旧 dump', 'before_gb': round(freed/1e9, 3),
                            'freed_gb': round(freed/1e9, 3), 'skipped': 0})
    # Hermes 内置浏览器 profile 缓存
    bps = hermes + "/browser-profiles"
    if os.path.isdir(bps):
        try:
            for bp in os.listdir(bps):
                clean_browser_profiles(os.path.join(bps, bp), ".hermes/browser-profiles/" + bp)
        except OSError:
            pass

# ---------- 10. Codex 自有缓存 ----------
codex = USERPROFILE + "/.codex"
if os.path.isdir(codex):
    for f in ["logs_2.sqlite", "logs_2.sqlite-wal", "logs_2.sqlite-shm"]:
        p = os.path.join(codex, f)
        if os.path.isfile(p):
            report(".codex/" + f, p, 'file')
    report(".codex/.tmp", codex + "/.tmp")
    report(".codex/generated_images", codex + "/generated_images")

# ---------- 汇总 ----------
total_freed = sum(r['freed_gb'] for r in results)
print(json.dumps({'results': results, 'total_freed_gb': round(total_freed, 3),
                  'c_free_before_gb': round(free_gb('C:\\'), 3)}, ensure_ascii=False, indent=1))
