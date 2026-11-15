#!/usr/bin/env bash
# ==============================================================================
# JIBSZ TUNNELING / J1BTNL - DAEMON & CRON MONITOR IP, KUOTA, & AUTO-EXPIRED
# File     : cli/monitor_ip_quota.sh
# Author   : Jibsz Tunneling (@admj1btnl)
# Fitur    : 1. Tarik trafik Upload/Download per akun dari Xray Stats API (10085)
#            2. Ekstrak IP Client Asli dari Nginx Real-IP Log (CF-Connecting-IP),
#               Xray Access Log, dan SSH-WS Active Connections
#            3. Auto-Kick / Auto-Lock akun yang melanggar Limit IP atau Limit Kuota
#            4. Auto-Expire akun yang melewati masa aktif
# ==============================================================================

set -u

INSTALL_DIR="/opt/jibsz-tunnel"
CONFIG_DIR="/etc/jibsz"
LOG_DIR="/var/log/jibsz"
DB_FILE="${CONFIG_DIR}/jibsz.db"

MODE_ARG="${1:---cron}"

python3 - "$MODE_ARG" << 'PYEOF'
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from typing import Dict, Set, Tuple

mode_arg = sys.argv[1] if len(sys.argv) > 1 else "--cron"
db_path = "/etc/jibsz/jibsz.db"
nginx_log = "/var/log/jibsz/nginx_access.log"
xray_log = "/var/log/jibsz/xray_access.log"
ssh_ws_json = "/var/log/jibsz/ssh_ws_active.json"
xray_cfg_path = "/usr/local/etc/xray/config.json"

if not os.path.exists(db_path):
    raise SystemExit(0)

conn = sqlite3.connect(db_path, timeout=15.0)
conn.row_factory = sqlite3.Row
now_ts = int(time.time())

# Bersihkan record IP yang sudah tidak aktif lebih dari 5 menit
conn.execute("DELETE FROM active_ips WHERE last_seen < ?", (now_ts - 300,))
conn.commit()

accounts = conn.execute("SELECT * FROM accounts").fetchall()
user_proto_map: Dict[str, str] = {r["username"]: r["protocol"] for r in accounts}

# 1. Tarik Statistik Kuota Xray API (127.0.0.1:10085)
if os.path.exists("/usr/local/bin/xray"):
    try:
        proc = subprocess.run(
            ["/usr/local/bin/xray", "api", "statsquery", "--server=127.0.0.1:10085", "-reset=true"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            stats_data = json.loads(proc.stdout)
            for item in stats_data.get("stat", []):
                name = item.get("name", "")
                val = int(item.get("value", 0))
                # Format: user>>>username@j1btnl>>>traffic>>>uplink / downlink
                m = re.match(r"^user>>>([^@]+)@j1btnl>>>traffic>>>(uplink|downlink)$", name)
                if m and val > 0:
                    uname, direction = m.group(1), m.group(2)
                    col = "up_bytes" if direction == "uplink" else "down_bytes"
                    conn.execute(f"UPDATE accounts SET {col} = {col} + ? WHERE username = ?", (val, uname))
            conn.commit()
    except Exception:
        pass

# 2. Kumpulkan IP Client Asli dari Nginx Real-IP Log (CF-Connecting-IP)
recent_nginx_ips_by_path: Dict[str, Set[str]] = {
    "ssh": set(),
    "vless": set(),
    "vmess": set(),
    "trojan": set(),
}

if os.path.exists(nginx_log):
    try:
        with open(nginx_log, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-400:]
        for line in lines:
            # Format: $remote_addr - $http_cf_connecting_ip [$time_local] "$request" ...
            parts = line.split(" ")
            if len(parts) >= 7:
                remote_ip = parts[0].strip()
                cf_ip = parts[2].strip()
                real_ip = cf_ip if (cf_ip and cf_ip != "-" and cf_ip != "127.0.0.1") else remote_ip
                if real_ip and real_ip != "127.0.0.1":
                    if "/vless" in line or "vless-grpc" in line:
                        recent_nginx_ips_by_path["vless"].add(real_ip)
                    elif "/vmess" in line or "vmess-grpc" in line:
                        recent_nginx_ips_by_path["vmess"].add(real_ip)
                    elif "/trojan" in line or "trojan-grpc" in line:
                        recent_nginx_ips_by_path["trojan"].add(real_ip)
                    elif "/ssh-ws" in line or "101" in line:
                        recent_nginx_ips_by_path["ssh"].add(real_ip)
    except Exception:
        pass

# 3. Kumpulkan IP & Email User dari Xray Access Log
if os.path.exists(xray_log):
    try:
        with open(xray_log, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-500:]
        for line in lines:
            if "email:" in line:
                m_email = re.search(r"email:\s*([^\s@]+)@j1btnl", line)
                m_ip = re.search(r"from\s+(?:tcp:|udp:)?([0-9a-fA-F\.:]+):\d+", line)
                if m_email:
                    uname = m_email.group(1)
                    proto = user_proto_map.get(uname, "vless")
                    ip_addr = m_ip.group(1) if m_ip else "127.0.0.1"
                    if ip_addr in ("127.0.0.1", "::1") and recent_nginx_ips_by_path.get(proto):
                        # Pasangkan dengan IP asli CF-Connecting-IP terbaru dari Nginx pada path protokol tersebut
                        for nip in recent_nginx_ips_by_path[proto]:
                            conn.execute(
                                "INSERT OR REPLACE INTO active_ips (username, protocol, client_ip, last_seen) VALUES (?, ?, ?, ?)",
                                (uname, proto, nip, now_ts),
                            )
                    elif ip_addr not in ("127.0.0.1", "::1"):
                        conn.execute(
                            "INSERT OR REPLACE INTO active_ips (username, protocol, client_ip, last_seen) VALUES (?, ?, ?, ?)",
                            (uname, proto, ip_addr, now_ts),
                        )
        conn.commit()
    except Exception:
        pass

# 4. Kumpulkan Koneksi Aktif SSH / Dropbear & SSH-WS Proxy
active_ssh_ws_ips = []
if os.path.exists(ssh_ws_json):
    try:
        with open(ssh_ws_json, "r", encoding="utf-8") as f:
            ws_items = json.load(f)
        for item in ws_items:
            cip = item.get("client_ip", "")
            if cip and cip != "127.0.0.1":
                active_ssh_ws_ips.append(cip)
                # Update byte counter untuk akun SSH aktif
    except Exception:
        pass

# Cek sesi login SSH di sistem via who / ps / journal
ssh_users = [r["username"] for r in accounts if r["protocol"] == "ssh" and r["status"] == "active"]
for s_user in ssh_users:
    proc_check = subprocess.run(["pgrep", "-u", s_user], capture_output=True, text=True)
    if proc_check.returncode == 0 and proc_check.stdout.strip():
        ips_to_record = active_ssh_ws_ips or list(recent_nginx_ips_by_path["ssh"])
        for cip in ips_to_record:
            conn.execute(
                "INSERT OR REPLACE INTO active_ips (username, protocol, client_ip, last_seen) VALUES (?, ?, ?, ?)",
                (s_user, "ssh", cip, now_ts),
            )
conn.commit()

# Jika hanya diminta sinkronisasi cepat dari Web Panel / CLI
if mode_arg == "--sync-only":
    conn.close()
    raise SystemExit(0)

# 5. Penegakan Aturan: Auto-Expire, Auto-Lock Kuota Habis, & Auto-Kick/Lock Multi-Login
xray_needs_reload = False
enforced_events = []

accounts = conn.execute("SELECT * FROM accounts WHERE status = 'active'").fetchall()
for acc in accounts:
    aid = acc["id"]
    uname = acc["username"]
    proto = acc["protocol"]
    exp_ts = int(acc["exp_timestamp"])
    ip_lim = int(acc["ip_limit"])
    quota_bytes = int(float(acc["quota_gb"]) * (1024 ** 3))
    used_bytes = int(acc["up_bytes"]) + int(acc["down_bytes"])

    # Cek Expired
    if now_ts >= exp_ts:
        conn.execute("UPDATE accounts SET status = 'expired' WHERE id = ?", (aid,))
        if proto == "ssh":
            subprocess.run(["usermod", "-L", uname], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["pkill", "-u", uname], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            xray_needs_reload = True
        enforced_events.append(f"[EXPIRED] {proto.upper()} user '{uname}' telah melewati masa aktif dan dinonaktifkan.")
        continue

    # Cek Kuota Bandwidth
    if quota_bytes > 0 and used_bytes >= quota_bytes:
        conn.execute("UPDATE accounts SET status = 'locked' WHERE id = ?", (aid,))
        if proto == "ssh":
            subprocess.run(["usermod", "-L", uname], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["pkill", "-u", uname], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            xray_needs_reload = True
        enforced_events.append(f"[QUOTA-LOCK] {proto.upper()} user '{uname}' melebihi kuota ({acc['quota_gb']} GB) -> Locked.")
        continue

    # Cek Multi-Login IP Client
    ip_rows = conn.execute(
        "SELECT DISTINCT client_ip FROM active_ips WHERE username = ? AND protocol = ? AND last_seen >= ?",
        (uname, proto, now_ts - 300),
    ).fetchall()
    active_ip_count = len(ip_rows)

    if ip_lim > 0 and active_ip_count > ip_lim:
        conn.execute("UPDATE accounts SET status = 'locked' WHERE id = ?", (aid,))
        if proto == "ssh":
            subprocess.run(["usermod", "-L", uname], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["pkill", "-u", uname], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            xray_needs_reload = True
        ips_str = ", ".join(r["client_ip"] for r in ip_rows)
        enforced_events.append(
            f"[MULTI-LOGIN KICK/LOCK] {proto.upper()} user '{uname}' login dari {active_ip_count} IP ({ips_str}) > Limit {ip_lim} IP -> Locked."
        )

conn.commit()

if xray_needs_reload and os.path.exists(xray_cfg_path):
    # Sinkronkan ulang config.json Xray agar akun yang expired/locked langsung terputus
    try:
        with open(xray_cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        active_rows = conn.execute(
            "SELECT protocol, username, secret FROM accounts WHERE status='active' AND protocol IN ('vless','vmess','trojan')"
        ).fetchall()
        vless_c, vmess_c, trojan_c = [], [], []
        for r in active_rows:
            em = f"{r['username']}@j1btnl"
            if r["protocol"] == "vless":
                vless_c.append({"id": r["secret"], "email": em, "level": 0})
            elif r["protocol"] == "vmess":
                vmess_c.append({"id": r["secret"], "alterId": 0, "email": em, "level": 0})
            elif r["protocol"] == "trojan":
                trojan_c.append({"password": r["secret"], "email": em, "level": 0})
        for inb in cfg.get("inbounds", []):
            t = inb.get("tag", "")
            if t in ("vless-ws", "vless-grpc"):
                inb.setdefault("settings", {})["clients"] = vless_c
            elif t in ("vmess-ws", "vmess-grpc"):
                inb.setdefault("settings", {})["clients"] = vmess_c
            elif t in ("trojan-ws", "trojan-grpc"):
                inb.setdefault("settings", {})["clients"] = trojan_c
        with open(xray_cfg_path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        os.replace(xray_cfg_path + ".tmp", xray_cfg_path)
        subprocess.run(["systemctl", "restart", "xray"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

if mode_arg == "--report":
    print("==========================================================================")
    print("       STATUS AKUN, KUOTA BANDWIDTH, & IP CLIENT ASLI (J1BTNL)           ")
    print("==========================================================================")
    all_rows = conn.execute("SELECT * FROM accounts ORDER BY protocol, username").fetchall()
    if not all_rows:
        print("  Belum ada akun terdaftar.")
    for r in all_rows:
        ips = conn.execute(
            "SELECT DISTINCT client_ip FROM active_ips WHERE username=? AND protocol=? AND last_seen >= ?",
            (r["username"], r["protocol"], now_ts - 300),
        ).fetchall()
        ip_list = [x["client_ip"] for x in ips]
        used_mb = (r["up_bytes"] + r["down_bytes"]) / (1024 ** 2)
        print(
            f" • [{r['protocol'].upper():6}] {r['username']:14} | Status: {r['status'].upper():7} | "
            f"Kuota: {used_mb:7.2f} MB / {r['quota_gb']} GB | IP ({len(ip_list)}/{r['ip_limit']}): {', '.join(ip_list) or '-'}"
        )
    print("==========================================================================")

for ev in enforced_events:
    print(ev)

conn.close()
PYEOF
