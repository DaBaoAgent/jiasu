#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DNS 工具（hellzerg/optimizer DNS 模块同款）：备份 / 快速切换 / 延迟测试 / 恢复。

优化 DNS 前先备份原配置；切换后可测延迟对比；不满意一键恢复。

用法:
    python dns_tool.py backup                 # 备份当前 DNS 配置 -> revert/dns_backup_<ts>.json
    python dns_tool.py list                   # 列出预设 DNS
    python dns_tool.py test                   # 测试当前 DNS 延迟
    python dns_tool.py test --all             # 对比全部预设 DNS 延迟
    python dns_tool.py set aliyun             # 切换到预设 DNS（需管理员）
    python dns_tool.py set 223.5.5.5 119.29.29.29   # 自定义主/备
    python dns_tool.py restore                # 恢复最近一次备份（需管理员）

预设: aliyun=223.5.5.5+223.6.6.6  tencent=119.29.29.29+119.28.28.28
      114=114.114.114.114  baidu=180.76.76.76
      cloudflare=1.1.1.1+1.0.0.1  google=8.8.8.8+8.8.4.4  adguard=94.140.14.14+94.140.15.15
"""
import os
import sys
import json
import glob
import time
import socket
import struct
import random
import subprocess
from datetime import datetime

import _common

PRESETS = {
    "aliyun": ["223.5.5.5", "223.6.6.6"],
    "tencent": ["119.29.29.29", "119.28.28.28"],
    "114": ["114.114.114.114", "114.114.115.115"],
    "baidu": ["180.76.76.76"],
    "cloudflare": ["1.1.1.1", "1.0.0.1"],
    "google": ["8.8.8.8", "8.8.4.4"],
    "adguard": ["94.140.14.14", "94.140.15.15"],
}
BACKUP_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "revert"))


def run_ps(cmd, timeout=60):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                           capture_output=True, timeout=timeout)
        return r.returncode, _common.decode_console(r.stdout + r.stderr)
    except Exception as e:
        return -1, str(e)


def get_adapters():
    """列出活动网卡及其当前 IPv4 DNS，返回 [{name, ifindex, dns:[...]}]。

    主路径：PowerShell Get-NetAdapter + Get-DnsClientServerAddress（结构化、免本地化解析）。
    坑（已踩，别走回头路）：netsh 文本解析在中文宿主下不可靠——
      1) 输出编码随宿主变化（本机 UTF-8、别机 GBK），按 GBK 解码曾直接抛
         UnicodeDecodeError 使本工具整体静默失效；
      2) "InterfaceMetric: 25" 的行被 "Interface" 前缀规则误当成新网卡；
      3) 中文格式「接口 "以太网" 的配置」带引号，name= 直接透传会引号嵌套失败。
    netsh 仅作 PowerShell 不可用时的后备（修复上述三点后仍受限于本地化文本）。
    """
    rc, out = run_ps(
        "Get-NetAdapter | Where-Object { $_.Status -eq 'Up' } | ForEach-Object { "
        "$d = (Get-DnsClientServerAddress -InterfaceIndex $_.ifIndex -AddressFamily IPv4 "
        "-ErrorAction SilentlyContinue).ServerAddresses; "
        "'{0}|{1}' -f $_.Name, ($d -join ',') }")
    if rc == 0 and out.strip():
        adapters = []
        for line in out.splitlines():
            line = line.strip()
            if not line or "|" not in line:
                continue
            name, _, dns = line.rpartition("|")
            if not name or name.lower() == "name":
                continue  # 表头
            adapters.append({"name": name.strip(), "ifindex": None,
                             "dns": [d.strip() for d in dns.split(",") if d.strip()]})
        if adapters:
            return adapters
    # ---- 后备：netsh 文本解析（老系统无 Get-NetAdapter 时）----
    try:
        p = subprocess.run(["netsh", "interface", "ip", "show", "config"],
                           capture_output=True, timeout=30)
        out = _common.decode_console(p.stdout)
    except Exception:
        return []
    adapters, cur = [], None
    for line in out.splitlines():
        line_s = line.strip()
        is_cn_title = (line_s.startswith("接口") or line_s.startswith("适配器"))
        is_en_title = line_s.lower().startswith("configuration for interface")
        if is_cn_title or is_en_title:
            if cur:
                adapters.append(cur)
            if is_en_title:
                name = line_s.rsplit("interface", 1)[-1].strip()
            else:
                name = line_s.split(" ", 1)[-1].strip()
            if name.startswith('"'):
                end = name.find('"', 1)
                name = name[1:end] if end > 0 else name.strip('"')
            cur = {"name": name, "ifindex": None, "dns": []}
        elif cur and ("DNS 服务器" in line_s or "DNS Servers" in line_s or "DNS Server" in line_s):
            val = line_s.split(":", 1)[-1].strip()
            if val:
                cur["dns"].append(val)
    if cur:
        adapters.append(cur)
    return [a for a in adapters
            if a["name"] and "loopback" not in a["name"].lower()]


def dns_query_latency(server, host="www.baidu.com", timeout=2.0):
    """直接 UDP 查 DNS 拿 A 记录，测往返耗时（比 ping 准，不受 ICMP 拦截影响）"""
    tid = random.randint(0, 0xFFFF)
    q = struct.pack(">HHHHHH", tid, 0x0100, 1, 0, 0, 0)
    for part in host.split("."):
        q += bytes([len(part)]) + part.encode()
    q += b"\x00" + struct.pack(">HH", 1, 1)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    t0 = time.time()
    try:
        s.sendto(q, (server, 53))
        data, _ = s.recvfrom(512)
        return (time.time() - t0) * 1000
    except (socket.timeout, OSError):
        return None
    finally:
        s.close()


def test_servers(servers):
    results = []
    for srv in servers:
        samples = []
        for _ in range(3):
            ms = dns_query_latency(srv)
            if ms is not None:
                samples.append(ms)
        if samples:
            results.append((srv, sum(samples) / len(samples), min(samples)))
        else:
            results.append((srv, None, None))
    return results


def backup():
    adapters = get_adapters()
    if not adapters:
        print("未获取到网卡配置（netsh/PowerShell 解析失败？）")
        sys.exit(1)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fpath = os.path.join(BACKUP_DIR, f"dns_backup_{ts}.json")
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(adapters, f, ensure_ascii=False, indent=1)
    print(f"已备份当前 DNS -> {fpath}")
    for a in adapters:
        print(f"  {a['name']}: {', '.join(a['dns']) if a['dns'] else '(自动/DHCP)'}")
    return fpath


def _ps_set_dns(name, server):
    rc, _ = run_ps(f'netsh interface ip set dns name="{name}" static {server}')
    return rc


def _ps_add_dns(name, server):
    rc, _ = run_ps(f'netsh interface ip add dns name="{name}" {server}')
    return rc


def _ps_dhcp_dns(name):
    rc, _ = run_ps(f'netsh interface ip set dns name="{name}" source=dhcp')
    return rc


def _flush_dns():
    subprocess.run(["ipconfig", "/flushdns"], capture_output=True)


def restore():
    files = sorted(glob.glob(os.path.join(BACKUP_DIR, "dns_backup_*.json")))
    if not files:
        print("没有备份。先跑: python dns_tool.py backup")
        sys.exit(1)
    fpath = files[-1]
    with open(fpath, encoding="utf-8") as f:
        saved = json.load(f)
    print(f"恢复 {fpath}:")
    for a in saved:
        name = a["name"]
        if not a["dns"]:
            rc = _ps_dhcp_dns(name)
            print(f"  {name}: 恢复为 DHCP 自动获取")
        else:
            primary, *rest = a["dns"]
            rc = _ps_set_dns(name, primary)
            if rc == 0:
                for extra in rest:
                    _ps_add_dns(name, extra)
            print(f"  {'OK' if rc == 0 else 'FAIL(需管理员, 可能失败)'} {name}")
    _flush_dns()
    print("完成。已 flushdns 刷新解析缓存")


def set_dns(servers):
    adapters = get_adapters()
    if not adapters:
        print("未获取到网卡配置（netsh/PowerShell 解析失败？）")
        sys.exit(1)
    primary, *rest = servers
    for a in adapters:
        name = a["name"]
        rc1 = _ps_set_dns(name, primary)
        if rc1 != 0:
            print(f"  FAIL {name}: 设置失败（需管理员权限，UAC 提权后重试）")
            continue
        for extra in rest:
            _ps_add_dns(name, extra)
        print(f"  OK {name}: -> {', '.join(servers)}")
    _flush_dns()
    print("完成。切换前已建议先 backup；不满意可 restore。")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    action = args[0]
    if action == "backup":
        backup()
    elif action == "list":
        print("预设 DNS:")
        for name, servers in PRESETS.items():
            print(f"  {name:<12} {', '.join(servers)}")
    elif action == "test":
        if "--all" in args:
            servers = [s for v in PRESETS.values() for s in v]
        else:
            adapters = get_adapters()
            servers = [d for a in adapters for d in a["dns"]] or ["223.5.5.5"]
        print("测试 DNS 延迟 (查 www.baidu.com):")
        for srv, avg, best in test_servers(servers):
            if avg is None:
                print(f"  {srv:<18} 超时/不可达")
            else:
                print(f"  {srv:<18} avg {avg:6.1f} ms  best {best:5.1f} ms")
    elif action == "set":
        if len(args) >= 3:
            set_dns(args[1:])
        elif len(args) == 2 and args[1] in PRESETS:
            set_dns(PRESETS[args[1]])
        else:
            print("用法: set <preset名|ip1 [ip2]>")
            sys.exit(1)
    elif action == "restore":
        restore()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
