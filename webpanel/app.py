#!/usr/bin/env python3
"""
JIBSZ TUNNELING / J1BTNL - FASTAPI WEB PANEL & INSTALLER BACKEND (app.py)
Author  : Jibsz Tunneling (@admj1btnl)
GitHub  : https://github.com/mohamadrojib278/jibsz-tunnel-autoinstall
Akses   : Public Access (Tanpa Login) — Buat Akun & Pantau Semua Proses Aktif.
          Fitur Hapus Akun dikunci khusus melalui Terminal CLI (menu / jibsz).
"""

import base64
import datetime
import io
import json
import os
import platform
import secrets
import shutil
import sqlite3
import subprocess
import time
import urllib.parse
import uuid
from typing import Optional, Dict, Any, List

import psutil
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

try:
    import qrcode
    import qrcode.image.svg
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTALL_DIR = os.environ.get("INSTALL_DIR", "/opt/jibsz-tunnel")
CONFIG_DIR = os.environ.get("CONFIG_DIR", "/etc/jibsz")
LOG_DIR = os.environ.get("LOG_DIR", "/var/log/jibsz")
DB_PATH = os.environ.get("DB_PATH", os.path.join(CONFIG_DIR, "jibsz.db"))
LOCK_FILE = os.path.join(CONFIG_DIR, "installed.lock")
XRAY_CONFIG_PATH = "/usr/local/etc/xray/config.json"

app = FastAPI(
    title="Jibsz Tunneling / J1BTNL Public Web Panel",
    description="Public Web Installer & Multi-Protocol Tunneling Dashboard (@admj1btnl)",
    version="2.7.0",
)

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


# ==============================================================================
# DATABASE HELPERS
# ==============================================================================
def get_db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def get_setting(key: str, default: str = "") -> str:
    try:
        with get_db() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default
    except Exception:
        return default


def set_setting(key: str, value: str) -> None:
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()


def is_system_installed() -> bool:
    if os.path.exists(LOCK_FILE) or get_setting("is_installed", "0") == "1":
        return True
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM component_status "
                "WHERE component_id IN ('ssh','vless','vmess','trojan') AND status='success'"
            ).fetchone()
            if row and row["cnt"] == 4:
                set_setting("is_installed", "1")
                return True
    except Exception:
        pass
    return False


# ==============================================================================
# PYDANTIC SCHEMAS
# ==============================================================================
class InstallStartRequest(BaseModel):
    mode: str  # "public" atau "nat"
    domain: str
    email: Optional[str] = "admin@j1btnl.local"
    cf_token: Optional[str] = ""


class RetryComponentRequest(BaseModel):
    component_id: str  # "nginx", "tunnel_ssl", "ssh", "vless", "vmess", "trojan", atau "all_failed"


class ServiceActionRequest(BaseModel):
    service: str  # "nginx", "xray", "ssh", "dropbear", "ssh-ws", "cloudflared", "cron"


class CreateAccountRequest(BaseModel):
    protocol: str  # "ssh", "vmess", "vless", "trojan"
    username: str
    secret: Optional[str] = ""  # Password untuk SSH, UUID/Password untuk Xray (kosong = auto UUID)
    duration_mode: str = "days"  # "days", "trial_minutes", "trial_hours"
    duration_value: int = 30
    ip_limit: int = 2
    quota_gb: float = 50.0


class RenewAccountRequest(BaseModel):
    add_days: int = 30
    quota_gb: Optional[float] = None
    ip_limit: Optional[int] = None


# ==============================================================================
# HELPER PROVISIONING AKUN (SSH LINUX & XRAY JSON SYNC)
# ==============================================================================
def sync_xray_accounts_to_config() -> None:
    """Sinkronkan seluruh akun aktif VMess, VLESS, dan Trojan dari SQLite ke /usr/local/etc/xray/config.json."""
    if not os.path.exists(XRAY_CONFIG_PATH):
        template_path = os.path.join(INSTALL_DIR, "backend", "xray_config.json")
        if os.path.exists(template_path):
            os.makedirs(os.path.dirname(XRAY_CONFIG_PATH), exist_ok=True)
            shutil.copyfile(template_path, XRAY_CONFIG_PATH)
        else:
            return

    try:
        with open(XRAY_CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return

    with get_db() as conn:
        rows = conn.execute(
            "SELECT protocol, username, secret FROM accounts WHERE status = 'active' AND protocol IN ('vless','vmess','trojan')"
        ).fetchall()

    vless_clients = []
    vmess_clients = []
    trojan_clients = []

    for r in rows:
        email_tag = f"{r['username']}@j1btnl"
        if r["protocol"] == "vless":
            vless_clients.append({"id": r["secret"], "email": email_tag, "level": 0})
        elif r["protocol"] == "vmess":
            vmess_clients.append({"id": r["secret"], "alterId": 0, "email": email_tag, "level": 0})
        elif r["protocol"] == "trojan":
            trojan_clients.append({"password": r["secret"], "email": email_tag, "level": 0})

    for inbound in cfg.get("inbounds", []):
        tag = inbound.get("tag", "")
        if tag in ("vless-ws", "vless-grpc"):
            inbound.setdefault("settings", {})["clients"] = vless_clients
        elif tag in ("vmess-ws", "vmess-grpc"):
            inbound.setdefault("settings", {})["clients"] = vmess_clients
        elif tag in ("trojan-ws", "trojan-grpc"):
            inbound.setdefault("settings", {})["clients"] = trojan_clients

    tmp_cfg = f"{XRAY_CONFIG_PATH}.tmp"
    with open(tmp_cfg, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp_cfg, XRAY_CONFIG_PATH)

    subprocess.run(["systemctl", "restart", "xray"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def provision_linux_ssh_user(username: str, password: str, exp_date_str: str) -> None:
    """Buat atau perbarui akun sistem Linux untuk SSH / Dropbear."""
    check = subprocess.run(["id", "-u", username], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if check.returncode != 0:
        subprocess.run(
            ["useradd", "-e", exp_date_str, "-s", "/bin/false", "-M", username],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.run(
            ["usermod", "-e", exp_date_str, username],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    chpasswd_proc = subprocess.Popen(["chpasswd"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chpasswd_proc.communicate(input=f"{username}:{password}".encode("utf-8"))


def lock_unlock_linux_ssh_user(username: str, lock: bool) -> None:
    flag = "-L" if lock else "-U"
    subprocess.run(["usermod", flag, username], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if lock:
        subprocess.run(["pkill", "-u", username], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def generate_qr_svg_data_uri(data_text: str) -> str:
    """Hasilkan Data URI SVG untuk QR Code konfigurasi."""
    if not HAS_QRCODE or not data_text:
        return ""
    try:
        factory = qrcode.image.svg.SvgPathImage
        img = qrcode.make(data_text, image_factory=factory, box_size=8, border=2)
        buf = io.BytesIO()
        img.save(buf)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/svg+xml;base64,{b64}"
    except Exception:
        return ""


def build_account_connection_details(account: Dict[str, Any]) -> Dict[str, Any]:
    """Bangun link URI (vmess://, vless://, trojan://), payload SSH WS, & QR Code."""
    domain = get_setting("domain", "localhost") or get_setting("public_ip", "127.0.0.1")
    pub_ip = get_setting("public_ip", "127.0.0.1")
    mode = get_setting("install_mode", "public")
    proto = account["protocol"]
    user = account["username"]
    secret = account["secret"]

    details: Dict[str, Any] = {
        "host": domain,
        "ip_public": pub_ip,
        "mode": "VPS NAT + Cloudflare Tunnel" if mode == "nat" else "VPS IP Public",
        "port_tls": 443,
        "port_ntls": 80,
        "path_ws": f"/{proto}" if proto != "ssh" else "/ssh-ws",
        "service_name_grpc": f"{proto}-grpc" if proto != "ssh" else "-",
        "uri_tls": "",
        "uri_ntls": "",
        "uri_grpc": "",
        "ssh_payload_ntls": "",
        "ssh_payload_tls": "",
        "qr_svg": "",
    }

    if proto == "ssh":
        details["ssh_payload_ntls"] = (
            f"GET /ssh-ws HTTP/1.1[crlf]"
            f"Host: {domain}[crlf]"
            f"Upgrade: websocket[crlf]"
            f"Connection: Upgrade[crlf]"
            f"User-Agent: JibszTunnel/2.7 (@admj1btnl)[crlf][crlf]"
        )
        details["ssh_payload_tls"] = (
            f"GET wss://{domain}/ssh-ws HTTP/1.1[crlf]"
            f"Host: {domain}[crlf]"
            f"Upgrade: websocket[crlf]"
            f"Connection: Upgrade[crlf][crlf]"
        )
        details["uri_tls"] = f"ssh://{user}:{secret}@{domain}:443#{user}-J1BTNL"
        details["uri_ntls"] = f"ssh://{user}:{secret}@{domain}:80#{user}-J1BTNL"
        details["qr_svg"] = generate_qr_svg_data_uri(details["uri_tls"])

    elif proto == "vmess":
        vmess_tls_obj = {
            "v": "2",
            "ps": f"{user}-WS-TLS-J1BTNL",
            "add": domain,
            "port": "443",
            "id": secret,
            "aid": "0",
            "scy": "auto",
            "net": "ws",
            "type": "none",
            "host": domain,
            "path": "/vmess",
            "tls": "tls",
            "sni": domain,
        }
        vmess_ntls_obj = {
            "v": "2",
            "ps": f"{user}-WS-NTLS-J1BTNL",
            "add": domain,
            "port": "80",
            "id": secret,
            "aid": "0",
            "scy": "auto",
            "net": "ws",
            "type": "none",
            "host": domain,
            "path": "/vmess",
            "tls": "none",
        }
        vmess_grpc_obj = {
            "v": "2",
            "ps": f"{user}-gRPC-J1BTNL",
            "add": domain,
            "port": "443",
            "id": secret,
            "aid": "0",
            "scy": "auto",
            "net": "grpc",
            "type": "gun",
            "host": domain,
            "path": "vmess-grpc",
            "tls": "tls",
            "sni": domain,
        }
        details["uri_tls"] = "vmess://" + base64.b64encode(json.dumps(vmess_tls_obj).encode("utf-8")).decode("ascii")
        details["uri_ntls"] = "vmess://" + base64.b64encode(json.dumps(vmess_ntls_obj).encode("utf-8")).decode("ascii")
        details["uri_grpc"] = "vmess://" + base64.b64encode(json.dumps(vmess_grpc_obj).encode("utf-8")).decode("ascii")
        details["qr_svg"] = generate_qr_svg_data_uri(details["uri_tls"])

    elif proto == "vless":
        tag_tls = urllib.parse.quote(f"{user}-VLESS-TLS-J1BTNL")
        tag_ntls = urllib.parse.quote(f"{user}-VLESS-NTLS-J1BTNL")
        tag_grpc = urllib.parse.quote(f"{user}-VLESS-gRPC-J1BTNL")
        details["uri_tls"] = (
            f"vless://{secret}@{domain}:443?path=%2Fvless&security=tls&encryption=none"
            f"&host={domain}&type=ws&sni={domain}#{tag_tls}"
        )
        details["uri_ntls"] = (
            f"vless://{secret}@{domain}:80?path=%2Fvless&security=none&encryption=none"
            f"&host={domain}&type=ws#{tag_ntls}"
        )
        details["uri_grpc"] = (
            f"vless://{secret}@{domain}:443?mode=gun&security=tls&encryption=none"
            f"&type=grpc&serviceName=vless-grpc&sni={domain}#{tag_grpc}"
        )
        details["qr_svg"] = generate_qr_svg_data_uri(details["uri_tls"])

    elif proto == "trojan":
        tag_tls = urllib.parse.quote(f"{user}-TROJAN-TLS-J1BTNL")
        tag_ntls = urllib.parse.quote(f"{user}-TROJAN-NTLS-J1BTNL")
        tag_grpc = urllib.parse.quote(f"{user}-TROJAN-gRPC-J1BTNL")
        details["uri_tls"] = (
            f"trojan://{secret}@{domain}:443?path=%2Ftrojan&security=tls"
            f"&host={domain}&type=ws&sni={domain}#{tag_tls}"
        )
        details["uri_ntls"] = (
            f"trojan://{secret}@{domain}:80?path=%2Ftrojan&security=none"
            f"&host={domain}&type=ws#{tag_ntls}"
        )
        details["uri_grpc"] = (
            f"trojan://{secret}@{domain}:443?mode=gun&security=tls"
            f"&type=grpc&serviceName=trojan-grpc&sni={domain}#{tag_grpc}"
        )
        details["qr_svg"] = generate_qr_svg_data_uri(details["uri_tls"])

    return details


# ==============================================================================
# RUTE UTAMA PUBLIK (TANPA KREDENSIAL LOGIN)
# ==============================================================================
@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    """
    Halaman utama dapat diakses langsung oleh semua orang tanpa login.
    Otomatis beralih dari Wizard Instalasi ke Dashboard Utama saat instalasi selesai.
    """
    if is_system_installed() and request.query_params.get("wizard") != "1":
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "domain": get_setting("domain", "Belum diatur"),
                "install_mode": get_setting("install_mode", "public"),
                "panel_port": get_setting("panel_port", "8080"),
                "public_ip": get_setting("public_ip", "127.0.0.1"),
            },
        )
    return templates.TemplateResponse(
        "install.html",
        {
            "request": request,
            "domain": get_setting("domain", ""),
            "acme_email": get_setting("acme_email", "admin@j1btnl.local"),
            "cf_token": get_setting("cf_token", ""),
            "install_mode": get_setting("install_mode", "public"),
            "panel_port": get_setting("panel_port", "8080"),
            "public_ip": get_setting("public_ip", "127.0.0.1"),
        },
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def force_dashboard(request: Request):
    if not is_system_installed():
        return RedirectResponse(url="/")
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "domain": get_setting("domain", "Belum diatur"),
            "install_mode": get_setting("install_mode", "public"),
            "panel_port": get_setting("panel_port", "8080"),
            "public_ip": get_setting("public_ip", "127.0.0.1"),
        },
    )


# ==============================================================================
# API TAHAP 1: WIZARD INSTALASI & LIVE PROGRESS PER KOMPONEN (PUBLIC ACCESS)
# ==============================================================================
@app.post("/api/install/start")
async def start_installation(payload: InstallStartRequest):
    mode = payload.mode.lower().strip()
    if mode not in ("public", "nat"):
        raise HTTPException(status_code=400, detail="Mode harus 'public' atau 'nat'.")
    domain = payload.domain.strip()
    if not domain:
        raise HTTPException(status_code=400, detail="Domain / Subdomain wajib diisi.")
    if mode == "nat" and not (payload.cf_token or "").strip():
        raise HTTPException(status_code=400, detail="Cloudflare Tunnel Token wajib diisi untuk mode VPS NAT.")

    set_setting("install_mode", mode)
    set_setting("domain", domain)
    set_setting("acme_email", (payload.email or "admin@j1btnl.local").strip())
    if mode == "nat":
        set_setting("cf_token", (payload.cf_token or "").strip())

    with get_db() as conn:
        conn.execute("UPDATE component_status SET status='pending', message='Dalam antrean instalasi...'")
        conn.commit()

    engine_script = os.path.join(INSTALL_DIR, "backend", "installer_engine.sh")
    subprocess.Popen(
        ["/bin/bash", engine_script, "--all"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return {"status": "started", "mode": mode, "domain": domain}


@app.post("/api/install/retry")
async def retry_component(payload: RetryComponentRequest):
    comp = payload.component_id.strip()
    engine_script = os.path.join(INSTALL_DIR, "backend", "installer_engine.sh")

    if comp == "all_failed":
        subprocess.Popen(
            ["/bin/bash", engine_script, "--retry-failed"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    else:
        with get_db() as conn:
            conn.execute(
                "UPDATE component_status SET status='installing', message='Mengulangi instalasi komponen...' WHERE component_id=?",
                (comp,),
            )
            conn.commit()
        subprocess.Popen(
            ["/bin/bash", engine_script, "--component", comp],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    return {"status": "retrying", "component_id": comp}


@app.get("/api/install/status")
async def get_installation_status():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT component_id, name, status, message, updated_at FROM component_status "
            "ORDER BY CASE component_id "
            "WHEN 'nginx' THEN 1 WHEN 'tunnel_ssl' THEN 2 WHEN 'ssh' THEN 3 "
            "WHEN 'vless' THEN 4 WHEN 'vmess' THEN 5 WHEN 'trojan' THEN 6 ELSE 7 END"
        ).fetchall()
        components = [dict(r) for r in rows]

    log_file = os.path.join(LOG_DIR, "install.log")
    logs = ""
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                logs = "".join(lines[-80:])
        except Exception:
            logs = ""

    return {
        "is_installed": is_system_installed(),
        "mode": get_setting("install_mode", "public"),
        "domain": get_setting("domain", ""),
        "components": components,
        "logs": logs,
    }


# ==============================================================================
# API MENU 1: DASHBOARD UTAMA (INFO VPS, JARINGAN, SERVICE STATUS, RINGKASAN AKUN)
# ==============================================================================
def check_service_running(svc_name: str) -> bool:
    proc_map = {
        "nginx": "nginx",
        "xray": "xray",
        "ssh": "sshd",
        "dropbear": "dropbear",
        "ssh-ws": "ssh_ws_proxy.py",
        "cloudflared": "cloudflared",
        "cron": "cron",
    }
    res = subprocess.run(
        ["systemctl", "is-active", "--quiet", svc_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if res.returncode == 0:
        return True
    pattern = proc_map.get(svc_name, svc_name)
    pgrep_res = subprocess.run(["pgrep", "-f", pattern], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return pgrep_res.returncode == 0


def get_vnstat_bandwidth() -> Dict[str, str]:
    try:
        out = subprocess.check_output(["vnstat", "--json"], stderr=subprocess.DEVNULL, timeout=3).decode("utf-8")
        data = json.loads(out)
        ifaces = data.get("interfaces", [])
        if ifaces:
            total = ifaces[0].get("traffic", {}).get("total", {})
            rx = total.get("rx", 0)
            tx = total.get("tx", 0)
            return {
                "download": f"{rx / (1024**3):.2f} GB",
                "upload": f"{tx / (1024**3):.2f} GB",
                "total": f"{(rx + tx) / (1024**3):.2f} GB",
            }
    except Exception:
        pass
    net_io = psutil.net_io_counters()
    rx_gb = net_io.bytes_recv / (1024**3)
    tx_gb = net_io.bytes_sent / (1024**3)
    return {
        "download": f"{rx_gb:.2f} GB",
        "upload": f"{tx_gb:.2f} GB",
        "total": f"{(rx_gb + tx_gb):.2f} GB",
    }


def get_os_pretty_name() -> str:
    if os.path.exists("/etc/os-release"):
        with open("/etc/os-release", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    return f"{platform.system()} {platform.release()}"


@app.get("/api/system/overview")
async def system_overview():
    boot_ts = psutil.boot_time()
    uptime_sec = int(time.time() - boot_ts)
    days, rem = divmod(uptime_sec, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    uptime_str = f"{days}d {hours}h {minutes}m"

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    cpu_pct = psutil.cpu_percent(interval=0.1)
    load1, load5, load15 = os.getloadavg()

    mode = get_setting("install_mode", "public")
    service_list = ["nginx", "xray", "ssh", "dropbear", "ssh-ws", "cron"]
    if mode == "nat":
        service_list.insert(5, "cloudflared")

    services = [
        {
            "name": svc,
            "status": "running" if check_service_running(svc) else "stopped",
        }
        for svc in service_list
    ]

    with get_db() as conn:
        counts = {"ssh": 0, "vmess": 0, "vless": 0, "trojan": 0}
        for row in conn.execute("SELECT protocol, COUNT(*) AS cnt FROM accounts WHERE status='active' GROUP BY protocol"):
            counts[row["protocol"]] = row["cnt"]

    return {
        "system": {
            "os": get_os_pretty_name(),
            "kernel": platform.release(),
            "uptime": uptime_str,
            "cpu_percent": cpu_pct,
            "cpu_cores": psutil.cpu_count(logical=True) or 1,
            "load_avg": f"{load1:.2f} / {load5:.2f} / {load15:.2f}",
            "ram_used_mb": int(mem.used / (1024**2)),
            "ram_total_mb": int(mem.total / (1024**2)),
            "ram_percent": mem.percent,
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_percent": disk.percent,
            "bandwidth": get_vnstat_bandwidth(),
        },
        "network": {
            "public_ip": get_setting("public_ip", "127.0.0.1"),
            "mode": "VPS NAT + Cloudflare Tunnel" if mode == "nat" else "VPS IP Public",
            "mode_code": mode,
            "domain": get_setting("domain", "localhost"),
            "panel_port": get_setting("panel_port", "8080"),
        },
        "services": services,
        "account_counts": counts,
    }


@app.post("/api/service/restart")
async def restart_service(payload: ServiceActionRequest):
    allowed = {"nginx", "xray", "ssh", "dropbear", "ssh-ws", "cloudflared", "cron", "badvpn-udpgw"}
    svc = payload.service.strip()
    if svc not in allowed:
        raise HTTPException(status_code=400, detail="Service tidak dikenal.")
    subprocess.run(["systemctl", "restart", svc], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    return {"service": svc, "status": "running" if check_service_running(svc) else "stopped"}


# ==============================================================================
# API MENU 2: BUAT AKUN & MANAJEMEN AKUN (TANPA HAPUS VIA WEB - HAPUS HANYA CLI)
# ==============================================================================
@app.get("/api/accounts")
async def list_accounts():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM accounts ORDER BY id DESC").fetchall()
        ip_rows = conn.execute(
            "SELECT username, protocol, client_ip, last_seen FROM active_ips WHERE last_seen >= ?",
            (int(time.time()) - 300,),
        ).fetchall()

    ip_map: Dict[str, List[str]] = {}
    for ir in ip_rows:
        key = f"{ir['protocol']}:{ir['username']}"
        ip_map.setdefault(key, []).append(ir["client_ip"])

    result = []
    for r in rows:
        item = dict(r)
        key = f"{item['protocol']}:{item['username']}"
        connected_ips = sorted(list(set(ip_map.get(key, []))))
        item["connected_ips"] = connected_ips
        item["connected_ip_count"] = len(connected_ips)
        item["connection_details"] = build_account_connection_details(item)
        result.append(item)

    return {"accounts": result}


@app.post("/api/accounts")
async def create_account(payload: CreateAccountRequest):
    proto = payload.protocol.lower().strip()
    if proto not in ("ssh", "vmess", "vless", "trojan"):
        raise HTTPException(status_code=400, detail="Protokol harus ssh, vmess, vless, atau trojan.")

    username = payload.username.strip()
    if not username or not username.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Username hanya boleh berisi huruf, angka, '-', atau '_'.")

    secret = (payload.secret or "").strip()
    if proto == "ssh":
        if not secret:
            secret = secrets.token_hex(4)
    else:
        if not secret:
            secret = str(uuid.uuid4())

    now_ts = int(time.time())
    is_trial = 0
    if payload.duration_mode == "trial_minutes":
        exp_ts = now_ts + (max(1, payload.duration_value) * 60)
        is_trial = 1
    elif payload.duration_mode == "trial_hours":
        exp_ts = now_ts + (max(1, payload.duration_value) * 3600)
        is_trial = 1
    else:
        exp_ts = now_ts + (max(1, payload.duration_value) * 86400)

    exp_dt = datetime.datetime.fromtimestamp(exp_ts)
    exp_display = exp_dt.strftime("%Y-%m-%d %H:%M")
    exp_date_linux = (exp_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    with get_db() as conn:
        exists = conn.execute("SELECT id FROM accounts WHERE username = ?", (username,)).fetchone()
        if exists:
            raise HTTPException(status_code=409, detail=f"Username '{username}' sudah terdaftar.")

        conn.execute(
            """
            INSERT INTO accounts (protocol, username, secret, exp_timestamp, exp_display, is_trial, ip_limit, quota_gb, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
            """,
            (proto, username, secret, exp_ts, exp_display, is_trial, max(1, payload.ip_limit), max(0.0, payload.quota_gb)),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM accounts WHERE username = ?", (username,)).fetchone()

    if proto == "ssh":
        provision_linux_ssh_user(username, secret, exp_date_linux)
    else:
        sync_xray_accounts_to_config()

    acc_dict = dict(row)
    acc_dict["connection_details"] = build_account_connection_details(acc_dict)
    return {"status": "created", "account": acc_dict}


@app.put("/api/accounts/{account_id}/renew")
async def renew_account(account_id: int, payload: RenewAccountRequest):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Akun tidak ditemukan.")

        base_ts = max(int(time.time()), int(row["exp_timestamp"]))
        new_exp_ts = base_ts + (max(1, payload.add_days) * 86400)
        exp_dt = datetime.datetime.fromtimestamp(new_exp_ts)
        exp_display = exp_dt.strftime("%Y-%m-%d %H:%M")

        new_quota = payload.quota_gb if payload.quota_gb is not None else row["quota_gb"]
        new_ip_limit = payload.ip_limit if payload.ip_limit is not None else row["ip_limit"]

        conn.execute(
            """
            UPDATE accounts
            SET exp_timestamp = ?, exp_display = ?, quota_gb = ?, ip_limit = ?, status = 'active', is_trial = 0
            WHERE id = ?
            """,
            (new_exp_ts, exp_display, new_quota, new_ip_limit, account_id),
        )
        conn.commit()

    if row["protocol"] == "ssh":
        exp_date_linux = (exp_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        provision_linux_ssh_user(row["username"], row["secret"], exp_date_linux)
        lock_unlock_linux_ssh_user(row["username"], lock=False)
    else:
        sync_xray_accounts_to_config()

    return {"status": "renewed", "exp_display": exp_display}


@app.post("/api/accounts/{account_id}/toggle-lock")
async def toggle_lock_account(account_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Akun tidak ditemukan.")

        new_status = "locked" if row["status"] == "active" else "active"
        conn.execute("UPDATE accounts SET status = ? WHERE id = ?", (new_status, account_id))
        conn.commit()

    if row["protocol"] == "ssh":
        lock_unlock_linux_ssh_user(row["username"], lock=(new_status == "locked"))
    else:
        sync_xray_accounts_to_config()

    return {"status": new_status, "username": row["username"]}


@app.delete("/api/accounts/{account_id}")
async def delete_account_blocked_on_web(account_id: int):
    """
    Sesuai kebijakan keamanan Public Dashboard Jibsz Tunneling:
    Penghapusan akun melalui Web Panel dinonaktifkan dan HANYA dapat dilakukan melalui Terminal CLI.
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Penghapusan akun dinonaktifkan di Web Panel demi keamanan akses publik. "
            "Silakan hapus akun melalui Terminal CLI VPS (ketik: menu, menu-ssh, menu-vmess, menu-vless, atau menu-trojan)."
        ),
    )


# ==============================================================================
# API MENU 3: STATUS AKUN YANG DIGUNAKAN & MONITORING IP CLIENT REAL-TIME
# ==============================================================================
@app.get("/api/monitor/status")
async def monitor_accounts_and_ips():
    """Jalankan sinkronisasi cepat monitor_ip_quota.sh lalu kembalikan data akun & IP client aktif."""
    monitor_script = os.path.join(INSTALL_DIR, "cli", "monitor_ip_quota.sh")
    if os.path.exists(monitor_script):
        subprocess.run(["/bin/bash", monitor_script, "--sync-only"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return await list_accounts()


@app.post("/api/monitor/enforce")
async def enforce_multi_login_and_quota():
    """Jalankan Auto-Kick / Auto-Lock Multi-Login & Expired Check sekarang."""
    monitor_script = os.path.join(INSTALL_DIR, "cli", "monitor_ip_quota.sh")
    out = ""
    if os.path.exists(monitor_script):
        proc = subprocess.run(["/bin/bash", monitor_script, "--cron"], capture_output=True, text=True)
        out = proc.stdout
    return {"status": "enforced", "details": out}
