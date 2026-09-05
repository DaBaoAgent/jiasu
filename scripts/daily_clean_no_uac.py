#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jiasu 每日自动清理（免 UAC 模式）：测量 -> 安全删除 -> 逐项报告释放 GB

清理来源（单一事实源，2026-09-05 重构）:
  1) rules.json 规则库中 risk=safe 且 mode in (contents/file/cef_cache) 的项
     —— 新增软件缓存规则只改 rules.json，本脚本自动生效，无需改代码
  2) 内置复杂逻辑（rules.json 表达不了的）: 剪映 Projects 安全检查、
     浏览器 profile 缓存展开、微信/QQ Image/Video/File 递归、Hermes/Codex 特殊项

用法:
    python daily_clean_no_uac.py            # 默认：规则库 + 内置复杂项（cron 用）
    python daily_clean_no_uac.py --rules    # 只清规则库（调试/验证规则用）

硬红线（2026-09-05 用户确认，最高优先级）——本脚本永不：
  × 删除任何软件本体/旧版本目录（剪映 Apps、美图、WPS、ms-playwright 等版本目录只报告不动）
  × 清微信/QQ 的 File/（聊天接收文件）与 msg/ 子树（用户数据）
  × 执行 rules.json 中 risk=moderate 或 mode=keep_latest 的规则
只清可再生纯缓存。改动本脚本时不得放宽以上红线。
"""
import os
import stat
import re
import sys
import json
import ctypes
import time

import _common

USERPROFILE = os.environ.get('USERPROFILE', 'C:/Users/xxx13')
LOCALAPPDATA = os.environ.get('LOCALAPPDATA', USERPROFILE + '/AppData/Local')
APPDATA = os.environ.get('APPDATA', USERPROFILE + '/AppData/Roaming')
TEMP = os.environ.get('TEMP', LOCALAPPDATA + '/Temp')

results = []


def rm_contents(path, min_age_days=None, _is_root=True):
    """删除目录下所有内容（保留根目录），返回 (跳过条数, 跳过字节)。

    - junction/reparse point 一律不进不删（穿透 junction 会删到目标真身——
      数据丢失级；本技能推荐给微信等数据目录建 junction 迁移，防护必须常开）。
      _is_root=True 时连"根路径本身是链接"也拒绝进入：os.scandir(junction)
      会穿透枚举目标内容并逐个删除，rules.json 规则路径可能命中用户自建链接
    - min_age_days：mtime 距今不足 N 天的文件跳过（Temp 里可能有活跃文件）；
      只对文件生效（目录 mtime 常因增删条目而刷新，不代表内容新旧）
    """
    if _is_root and _common.is_reparse(path):
        return 1, 0
    skipped = 0
    skipped_bytes = 0
    cutoff = time.time() - min_age_days * 86400 if min_age_days else None
    try:
        with os.scandir(path) as it:
            for e in it:
                try:
                    if e.is_file(follow_symlinks=False):
                        st = e.stat(follow_symlinks=False)
                        if cutoff and st.st_mtime > cutoff:
                            skipped += 1
                            skipped_bytes += st.st_size
                            continue
                        os.chmod(e.path, stat.S_IWRITE)
                        os.unlink(e.path)
                    elif e.is_dir(follow_symlinks=False):
                        if _common.is_reparse(e.path):
                            skipped += 1
                            continue
                        s, b = rm_contents(e.path, min_age_days, _is_root=False)
                        skipped += s
                        skipped_bytes += b
                        try:
                            os.rmdir(e.path)
                        except OSError:
                            skipped += 1
                    else:
                        # symlink 文件等未知类型：不碰
                        skipped += 1
                except (PermissionError, OSError):
                    skipped += 1
    except (PermissionError, OSError):
        skipped += 1
    return skipped, skipped_bytes


def rm_files_by_pattern(path, pattern):
    """按文件名正则删除文件（保留目录），返回释放字节数。不碰 reparse point。"""
    if _common.is_reparse(path):
        return 0
    freed = 0
    try:
        for name in os.listdir(path):
            if not re.search(pattern, name):
                continue
            p = os.path.join(path, name)
            try:
                if os.path.isdir(p) and _common.is_reparse(p):
                    continue
                sz = os.path.getsize(p)
                os.chmod(p, stat.S_IWRITE)
                os.unlink(p)
                freed += sz
            except (PermissionError, OSError):
                pass
    except (PermissionError, OSError):
        pass
    return freed


def clean_item(name, path, mode='contents', min_age_days=None):
    """测量 -> 删除 -> 返回 (name, before_gb, freed_gb, skipped)"""
    if not path or not os.path.exists(path):
        return (name, 0.0, 0.0, 0)
    if mode == 'file':
        try:
            before = os.path.getsize(path)
        except OSError:
            return (name, 0.0, 0.0, 0)
        if _common.is_reparse(path):
            return (name, before / _common.GB, 0.0, 1)
        try:
            os.chmod(path, stat.S_IWRITE)
            os.unlink(path)
            skipped, freed = 0, before
        except (PermissionError, OSError):
            skipped, freed = 1, 0.0
    else:
        before = _common.dir_size(path)
        skipped, skipped_bytes = rm_contents(path, min_age_days)
        after = _common.dir_size(path)
        freed = max(0, before - after)
    return (name, before / _common.GB, freed / _common.GB, skipped)


def report(name, path, mode='contents', min_age_days=None):
    n, before, freed, skipped = clean_item(name, path, mode, min_age_days)
    if before > 0.001 or freed > 0.001:
        results.append({'name': n, 'before_gb': round(before, 3),
                        'freed_gb': round(freed, 3), 'skipped': skipped})


CACHE_SUBS = ["Cache", "Code Cache", "GPUCache", "DawnGraphiteCache",
              "DawnWebGPUCache", "Service Worker", "DeferredBrowserMetrics"]


def clean_browser_profiles(base, label):
    """对 base 下所有 profile 目录（Default/Profile N）清理缓存子目录"""
    if not os.path.isdir(base) or _common.is_reparse(base):
        return
    try:
        profiles = [os.path.join(base, d) for d in os.listdir(base)
                    if os.path.isdir(os.path.join(base, d))]
    except OSError:
        return
    for prof in profiles:
        if _common.is_reparse(prof):
            continue
        for sub in CACHE_SUBS:
            p = os.path.join(prof, sub)
            if os.path.isdir(p) and not _common.is_reparse(p):
                report(f"{label}/{os.path.basename(prof)}/{sub}", p)


def clean_by_rules():
    """规则库清理：risk=safe 且 mode in (contents/file/cef_cache)。
    keep_latest（会删软件旧版本目录）与 moderate（需人工确认）跳过。
    min_age_days 规则字段：跳过 mtime 太新的文件（Temp 防误删）。
    红线：永不删软件本体/旧版本目录。
    """
    hits = _common.match_rules()
    for r, real, size, note in hits:
        risk = r.get("risk", "safe")
        mode = r.get("mode", "contents")
        if risk != "safe":
            continue
        if mode == "keep_latest":
            continue  # 旧版本保留逻辑在内置剪映块/手动指引，不自动删
        report(r["name"], real, "file" if mode == "file" else "contents",
               min_age_days=r.get("min_age_days"))


def main():
    rules_only = "--rules" in sys.argv
    # 清理前的 C 盘剩余空间（放最前，供前后对比报告）
    c_free_before_gb = _common.free_gb('C:\\')

    # ---------- 1. 规则库（简单缓存项，单一事实源）----------
    clean_by_rules()

    if not rules_only:
        # ---------- 2. SystemProfile 下 tw-*.tmp（Windows Update 任务残留）----------
        # 只删匹配 tw-*.tmp 的文件；绝不能 clean_item(contents) 整目录清——
        # systemprofile/AppData/Local 下有系统服务数据，不是纯缓存（历史 bug 已修）
        tw_dir = "C:/Windows/System32/config/systemprofile/AppData/Local"
        tw_freed = rm_files_by_pattern(tw_dir, r'^tw-.*\.tmp$')
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
                    p = jianying + "/Cache/" + sub
                    if os.path.isdir(p) and _common.is_reparse(p):
                        print("WARN: Jianying Cache 子目录是链接，跳过: %s" % sub)
                        continue
                    report("Jianying Cache/" + sub, p)

        # 旧版本 App 目录（软件本体，红线不删）：只报告占用，提示手动卸载
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
                        sz = _common.dir_size(os.path.join(apps_dir, v)) / _common.GB
                        print("INFO: 剪映旧版本 App %s 占 %.2f GB（红线不自动删软件，可手动卸载）"
                              % (v, sz))

        # ---------- 4. 浏览器缓存（Chrome / Edge）----------
        clean_browser_profiles(LOCALAPPDATA + "/Google/Chrome/User Data", "Chrome")
        clean_browser_profiles(LOCALAPPDATA + "/Microsoft/Edge/User Data", "Edge")

        # ---------- 5. 微信/QQ Image/Video 缓存（递归；File=聊天接收文件不碰）----------
        # 红线双保险：File/msg 走 os.walk 剪枝 + report() 前二次校验绝对路径段，
        # 防止未来有人把 File 加进别的清理入口（两处都要挡住）
        tencent = APPDATA + "/Tencent"
        if os.path.isdir(tencent):
            for root, dirs, files in os.walk(tencent):
                base = os.path.basename(root)
                if base == "File" or base == "msg":
                    dirs[:] = []
                    continue
                if base in ("Image", "Video") and "QQPCMgr" not in root:
                    parts = {p.upper() for p in os.path.normpath(root).split(os.sep)}
                    if "FILE" in parts or "MSG" in parts:
                        continue  # 双保险：Image/Video 出现在 File/msg 子树内部时绝不碰
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

        # ---------- 8. 回收站（SHEmptyRecycleBinW，API 不返回释放量，记 -1 不计入总量）----------
        if empty_recycle_bin('C:'):
            results.append({'name': '回收站(C:)', 'before_gb': -1, 'freed_gb': -1, 'skipped': 0})
            # before_gb=-1 表示已清空但大小未知（API 不返回释放量），汇总时不计入总量

    # ---------- 汇总 ----------
    total_freed = sum(r['freed_gb'] for r in results if r['freed_gb'] > 0)
    total_skipped = sum(r['skipped'] for r in results)
    print(json.dumps({'results': results, 'total_freed_gb': round(total_freed, 3),
                      'total_skipped': total_skipped,
                      'c_free_before_gb': round(c_free_before_gb, 3),
                      'c_free_after_gb': round(_common.free_gb('C:\\'), 3)},
                     ensure_ascii=False, indent=1))


def empty_recycle_bin(drive='C:'):
    """清空回收站（2026-08-29 实战修复恢复；SHERB_NOCONFIRMATION|NOPROGRESSUI|NOSOUND=0x7）"""
    try:
        return ctypes.windll.shell32.SHEmptyRecycleBinW(None, drive, 0x7) == 0
    except Exception:
        return False


if __name__ == "__main__":
    main()
