#!/usr/bin/env bash
# ==============================================================================
# JIBSZ TUNNELING / J1BTNL - DAEMON & CRON MONITOR IP, KUOTA, & AUTO-EXPIRED
# File     : cli/monitor_ip_quota.sh
# Author   : Jibsz Tunneling (@admj1btnl)
# Fix      : Mencegah false-positive auto-lock akibat IP gabungan pada log Nginx
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
from typing import Dict, List

mode_arg = sys.argv[1] if len(sys.argv) > 1 else "--cron"
db_path = "/etc/jibsz/jibsz.db"
nginx_log = "/var/log/jibsz/nginx_access.log"
xray_log = "/var/log/jibsz/xray_access.log"
ssh_ws_json = "/var/log/jibsz/ssh_ws_active.json"

if not os.path.exists(db_path):
    raise SystemExit(0)

conn = sqlite3.connect(db_path, timeout=15.0)
conn.row_factory = sqlite3.Row
now_ts = int(time.time())

# Bersihkan record IP yang sudah tidak aktif lebih dari 3 menit
conn.execute("DELETE FROM active_ips WHERE last_seen < ?", (now_ts - 180,))
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
                m = re.match(r"^user>>>([^@]+)@j1btnl>>>traffic>>>(uplink|downlink)$", name)
                if m and val > 0:
                    uname, direction = m.group(1), m.group(2)
                    col = "up_bytes" if direction == "uplink" else "down_bytes"
                    conn.execute(f"UPDATE accounts SET {col} = {col} + ? WHERE username = ?", (val, uname))
            conn.commit()
    except Exception:
        pass

# 2. Ambil IP terbaru per path dari Nginx log (hanya 1 IP paling akhir per protokol agar tidak false-lock)
latest_nginx_ip_by_path: Dict[str, str] = {}
if os.path.exists(nginx_log):
    try:
        with open(nginx_log, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-100:]
        for line in lines:
            parts = line.split(" ")
            if len(parts) >= 7:
                remote_ip = parts[0].strip()
                cf_ip = parts[2].strip()
                real_ip = cf_ip if (cf_ip and cf_ip != "-" and cf_ip != "127.0.0.1") else remote_ip
                if real_ip and real_ip != "127.0.0.1":
                    if "/vless" in line or "vless-grpc" in line:
                        latest_nginx_ip_by_path["vless"] = real_ip
                    elif "/vmess" in line or "vmess-grpc" in line:
                        latest_nginx_ip_by_path["vmess"] = real_ip
                    elif "/trojan" in line or "trojan-grpc" in line:
                        latest_nginx_ip_by_path["trojan"] = real_ip
                    elif "/ssh-ws" in line or "101" in line:
                        latest_nginx_ip_by_path["ssh"] = real_ip
    except Exception:
        pass

# 3. Kumpulkan IP & Email User dari Xray Access Log (hanya baris terbaru)
if os.path.exists(xray_log):
    try:
        with open(xray_log, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-150:]
        for line in lines:
            if "email:" in line:
                m_email = re.search(r"email:\s*([^\s@]+)@j1btnl", line)
                m_ip = re.search(r"from\s+(?:tcp:|udp:)?([0-9a-fA-F\.:]+):\d+", line)
                if m_email:
                    uname = m_email.group(1)
                    proto = user_proto_map.get(uname, "vless")
                    ip_addr = m_ip.group(1) if m_ip else "127.0.0.1"
                    if ip_addr in ("127.0.0.1", "::1"):
                        nip = latest_nginx_ip_by_path.get(proto)
                        if nip:
                            conn.execute(
                                "INSERT OR REPLACE INTO active_ips (username, protocol, client_ip, last_seen) VALUES (?, ?, ?, ?)",
                                (uname, proto, nip, now_ts),
                            )
                    else:
                        conn.execute(
                            "INSERT OR REPLACE INTO active_ips (username, protocol, client_ip, last_seen) VALUES (?, ?, ?, ?)",
                            (uname, proto, ip_addr, now_ts),
                        )
        conn.commit()
    except Exception:
        pass

# 4. Kumpulkan Koneksi Aktif SSH-WS Proxy
active_ssh_ws_ips: List[str] = []
if os.path.exists(ssh_ws_json):
    try:
        with open(ssh_ws_json, "r", encoding="utf-8") as f:
            ws_items = json.load(f)
        for item in ws_items:
            cip = item.get("client_ip", "")
            if cip and cip != "127.0.0.1":
                active_ssh_ws_ips.append(cip)
    except Exception:
        pass

ssh_users = [r["username"] for r in accounts if r["protocol"] == "ssh" and r["status"] == "active"]
for s_user in ssh_users:
    proc_check = subprocess.run(["pgrep", "-u", s_user], capture_output=True, text=True)
    if proc_check.returncode == 0 and proc_check.stdout.strip():
        ips_to_record = active_ssh_ws_ips or ([latest_nginx_ip_by_path["ssh"]] if "ssh" in latest_nginx_ip_by_path else [])
        for cip in ips_to_record:
            conn.execute(
                "INSERT OR REPLACE INTO active_ips (username, protocol, client_ip, last_seen) VALUES (?, ?, ?, ?)",
                (s_user, "ssh", cip, now_ts),
            )
conn.commit()

if mode_arg == "--sync-only":
    conn.close()
    raise SystemExit(0)

# 5. Penegakan Aturan: Auto-Expire & Auto-Lock Kuota Habis / Multi-Login
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

    if now_ts >= exp_ts:
        conn.execute("UPDATE accounts SET status = 'expired' WHERE id = ?", (aid,))
        if proto == "ssh":
            subprocess.run(["usermod", "-L", uname], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["pkill", "-u", uname], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            xray_needs_reload = True
        enforced_events.append(f"[EXPIRED] {proto.upper()} user '{uname}' expired.")
        continue

    if quota_bytes > 0 and used_bytes >= quota_bytes:
        conn.execute("UPDATE accounts SET status = 'locked' WHERE id = ?", (aid,))
        if proto == "ssh":
            subprocess.run(["usermod", "-L", uname], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["pkill", "-u", uname], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            xray_needs_reload = True
        enforced_events.append(f"[QUOTA-LOCK] {proto.upper()} user '{uname}' quota exceeded.")
        continue

    ip_rows = conn.execute(
        "SELECT DISTINCT client_ip FROM active_ips WHERE username = ? AND protocol = ? AND last_seen >= ?",
        (uname, proto, now_ts - 180),
    ).fetchall()
    active_ip_count = len(ip_rows)

    if ip_lim > 0 and active_ip_count > ip_lim:
        conn.execute("UPDATE accounts SET status = 'locked' WHERE id = ?", (aid,))
        if proto == "ssh":
            subprocess.run(["usermod", "-L", uname], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["pkill", "-u", uname], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            xray_needs_reload = True
        enforced_events.append(f"[MULTI-LOGIN LOCK] {proto.upper()} user '{uname}' ({active_ip_count}/{ip_lim} IP).")

conn.commit()

if xray_needs_reload:
    try:
        sys.path.insert(0, "/opt/jibsz-tunnel/webpanel")
        import app as web_app
        web_app.sync_xray_accounts_to_config()
    except Exception:
        pass

for ev in enforced_events:
    print(ev)

conn.close()
PYEOF
