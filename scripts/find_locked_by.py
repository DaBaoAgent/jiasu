#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""找出占用指定路径/目录的进程（hellzerg/optimizer 锁句柄工具同款，Restart Manager API）。

清理时遇到"文件被占用删不掉"，先跑这个看谁占着，再决定关闭进程或跳过。

用法:
    python find_locked_by.py "C:/Users/xxx13/AppData/Local/Temp"
    python find_locked_by.py "path1" "path2" "path3"

原理: Windows Restart Manager（rstrtmgr.dll）—— 与应用自报锁不同，
      它通过注册资源让系统枚举所有真正持有句柄的进程。无需管理员。
"""
import ctypes
import ctypes.wintypes as wt
import sys
import os

CCH_RM_MAX_APP_NAME = 255
CCH_RM_MAX_SVC_NAME = 63


class RM_UNIQUE_PROCESS(ctypes.Structure):
    _fields_ = [("dwProcessId", wt.DWORD),
                ("ProcessStartTime", wt.FILETIME)]


class RM_PROCESS_INFO(ctypes.Structure):
    _fields_ = [("Process", RM_UNIQUE_PROCESS),
                ("strAppName", ctypes.c_wchar * (CCH_RM_MAX_APP_NAME + 1)),
                ("strServiceShortName", ctypes.c_wchar * (CCH_RM_MAX_SVC_NAME + 1)),
                ("ApplicationType", wt.UINT),
                ("AppStatus", wt.ULONG),
                ("TSSessionId", wt.DWORD),
                ("bRestartable", wt.BOOL)]


def find_locked(paths):
    rm = ctypes.windll.rstrtmgr
    session = wt.DWORD(0)
    # CCH_RM_SESSION_KEY = 32，strSessionKey 需 33 个 wchar（给小了会缓冲区溢出段错误）
    key = ctypes.create_unicode_buffer(33)
    if rm.RmStartSession(ctypes.byref(session), 0, key) != 0:
        return None

    try:
        # 注册资源（文件路径）
        files = [ctypes.c_wchar_p(os.path.abspath(p)) for p in paths]
        arr = (ctypes.c_wchar_p * len(files))(*files)
        rc = rm.RmRegisterResources(session, len(files), arr, 0, None, 0, None)
        if rc != 0:
            return None

        # 第一次调用拿需要的数量
        needed = wt.UINT(0)
        count = wt.UINT(0)
        reasons = wt.DWORD(0)
        rm.RmGetList(session, ctypes.byref(needed), ctypes.byref(count),
                     None, ctypes.byref(reasons))
        if needed.value == 0:
            return []

        # 第二次调用拿真实列表
        buf = (RM_PROCESS_INFO * needed.value)()
        count = wt.UINT(needed.value)
        rm.RmGetList(session, ctypes.byref(needed), ctypes.byref(count),
                     buf, ctypes.byref(reasons))
        result = []
        for i in range(count.value):
            info = buf[i]
            result.append({
                "pid": info.Process.dwProcessId,
                "name": info.strAppName,
                "service": info.strServiceShortName,
                "restartable": bool(info.bRestartable),
            })
        return result
    finally:
        rm.RmEndSession(session)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    paths = sys.argv[1:]
    print("查询占用: " + " | ".join(paths))
    try:
        procs = find_locked(paths)
    except OSError as e:
        print(f"Restart Manager 调用失败: {e}")
        sys.exit(1)
    if procs is None:
        print("（查询失败，或路径不存在）")
        sys.exit(1)
    if not procs:
        print("✓ 无进程占用这些路径，可以安全删除")
        return
    print(f"\n发现 {len(procs)} 个占用进程:")
    for p in procs:
        restart = "可重启" if p["restartable"] else "不可重启"
        svc = f" [服务: {p['service']}]" if p["service"] else ""
        print(f"  PID {p['pid']:<7} {p['name']}  ({restart}){svc}")
    print("\n处置建议: taskkill /PID <pid> /F  关闭后再清理；重要程序请先保存工作")


if __name__ == "__main__":
    main()
