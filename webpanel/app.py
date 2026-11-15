#!/usr/bin/env python3
"""
JIBSZ TUNNELING / J1BTNL - FASTAPI WEB PANEL & INSTALLER BACKEND V3.0 (app.py)
Author  : Jibsz Tunneling (@admj1btnl)
GitHub  : https://github.com/mohamadrojib278/jibsz-tunnel-autoinstall
Fitur   : - Dukungan Penuh Config / Bug Host / Bug SNI & Wildcard untuk SSH, VLESS, VMess, Trojan
          - Tombol 1-Click Unlock & Reset IP untuk akun yang terkunci Limit IP
          - Anti-Cache Headers & Self-Contained V3 UI
          - Akses Publik Tanpa Login | Hapus Akun Hanya Lewat CLI
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
import tarfile
import time
import urllib.parse
import uuid
from typing import Optional, Dict, Any, List

import psutil
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, status
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTALL_DIR = os.environ.get("INSTALL_DIR", "/opt/jibsz-tunnel")
CONFIG_DIR = os.environ.get("CONFIG_DIR", "/etc/jibsz")
LOG_DIR = os.environ.get("LOG_DIR", "/var/log/jibsz")
DB_PATH = os.environ.get("DB_PATH", os.path.join(CONFIG_DIR, "jibsz.db"))
LOCK_FILE = os.path.join(CONFIG_DIR, "installed.lock")
BANNER_FILE = os.path.join(CONFIG_DIR, "banner.txt")
BACKUP_DIR = "/root/jibsz-backups"
XRAY_CONFIG_PATH = "/usr/local/etc/xray/config.json"

app = FastAPI(
    title="Jibsz Tunneling / J1BTNL Public Web Panel V3.0",
    description="Bug SNI Ready & Compact Mobile-First Tunneling Dashboard V3.0 (@admj1btnl)",
    version="3.0.0",
)


@app.middleware("http")
async def disable_cloudflare_and_browser_cache(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


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


def format_bytes_human(num_bytes: float) -> str:
    b = float(max(0.0, num_bytes))
    if b < 1024:
        return f"{int(b)} B"
    if b < 1024 ** 2:
        return f"{b / 1024:.2f} KB"
    if b < 1024 ** 3:
        return f"{b / (1024 ** 2):.2f} MB"
    if b < 1024 ** 4:
        return f"{b / (1024 ** 3):.2f} GB"
    return f"{b / (1024 ** 4):.2f} TB"


# ==============================================================================
# PYDANTIC SCHEMAS
# ==============================================================================
class InstallStartRequest(BaseModel):
    mode: str
    domain: str
    email: Optional[str] = "admin@j1btnl.local"
    cf_token: Optional[str] = ""


class RetryComponentRequest(BaseModel):
    component_id: str


class ServiceActionRequest(BaseModel):
    service: str


class CreateAccountRequest(BaseModel):
    protocol: str
    username: str
    secret: Optional[str] = ""
    duration_mode: str = "days"
    duration_value: int = 30
    ip_limit: int = 2
    quota_gb: float = 50.0
    bug_host: Optional[str] = "quiz.int.vidio.com"


class RenewAccountRequest(BaseModel):
    add_days: int = 30
    quota_gb: Optional[float] = None
    ip_limit: Optional[int] = None


class UnlockAccountRequest(BaseModel):
    ip_limit: Optional[int] = None


class BannerUpdateRequest(BaseModel):
    banner_html: str


class RestoreLocalRequest(BaseModel):
    filename: str


# ==============================================================================
# HELPER PROVISIONING AKUN & GENERATOR CONFIG BUG SNI / WILDCARD
# ==============================================================================
def sync_xray_accounts_to_config() -> None:
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
    if not HAS_QRCODE or not data_text:
        return ""
    try:
        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(data_text)
        qr.make(fit=True)
        matrix = qr.get_matrix()
        size = len(matrix)
        scale = 6
        dim = size * scale
        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {dim} {dim}" width="{dim}" height="{dim}" shape-rendering="crispEdges">',
            f'<rect width="{dim}" height="{dim}" fill="#ffffff"/>',
        ]
        for r_idx, row in enumerate(matrix):
            for c_idx, val in enumerate(row):
                if val:
                    svg_parts.append(
                        f'<rect x="{c_idx * scale}" y="{r_idx * scale}" width="{scale}" height="{scale}" fill="#000000"/>'
                    )
        svg_parts.append("</svg>")
        svg_bytes = "".join(svg_parts).encode("utf-8")
        return "data:image/svg+xml;base64," + base64.b64encode(svg_bytes).decode("ascii")
    except Exception:
        return ""


def build_account_connection_details(account: Dict[str, Any], bug_host: str = "") -> Dict[str, Any]:
    """
    Bangun link URI lengkap (Standard, Mode Bug CDN/Host, Mode Bug SNI, & Mode Wildcard)
    untuk SSH WS, VLESS, VMess, dan Trojan.
    """
    domain = get_setting("domain", "localhost") or get_setting("public_ip", "127.0.0.1")
    pub_ip = get_setting("public_ip", "127.0.0.1")
    mode = get_setting("install_mode", "public")
    proto = account["protocol"]
    user = account["username"]
    secret = account["secret"]
    bug = (bug_host or get_setting("default_bug", "quiz.int.vidio.com")).strip() or "quiz.int.vidio.com"
    wildcard_host = f"{bug}.{domain}"

    details: Dict[str, Any] = {
        "host": domain,
        "ip_public": pub_ip,
        "bug_host": bug,
        "wildcard_host": wildcard_host,
        "mode": "VPS NAT + CF Tunnel" if mode == "nat" else "VPS IP Public",
        "port_tls": 443,
        "port_ntls": 80,
        "path_ws": f"/{proto}" if proto != "ssh" else "/ssh-ws",
        "service_name_grpc": f"{proto}-grpc" if proto != "ssh" else "-",
        "uri_tls": "",
        "uri_ntls": "",
        "uri_bug_cdn_tls": "",
        "uri_bug_ntls": "",
        "uri_bug_wildcard": "",
        "uri_grpc": "",
        "ssh_payload_ntls": "",
        "ssh_payload_tls": "",
        "ssh_payload_split_bug": "",
        "ssh_proxy_format": "",
        "qr_svg": "",
    }

    if proto == "ssh":
        details["ssh_payload_ntls"] = (
            f"GET /ssh-ws HTTP/1.1[crlf]"
            f"Host: {domain}[crlf]"
            f"Upgrade: websocket[crlf]"
            f"Connection: Upgrade[crlf]"
            f"User-Agent: [ua][crlf][crlf]"
        )
        details["ssh_payload_tls"] = (
            f"GET wss://{domain}/ssh-ws HTTP/1.1[crlf]"
            f"Host: {domain}[crlf]"
            f"X-Online-Host: {bug}[crlf]"
            f"Upgrade: websocket[crlf]"
            f"Connection: Upgrade[crlf][crlf]"
        )
        details["ssh_payload_split_bug"] = (
            f"GET http://{bug}/ HTTP/1.1[crlf]"
            f"Host: {bug}[crlf][crlf][split]"
            f"GET /ssh-ws HTTP/1.1[crlf]"
            f"Host: {domain}[crlf]"
            f"Upgrade: websocket[crlf]"
            f"Connection: Upgrade[crlf][crlf]"
        )
        details["ssh_proxy_format"] = f"Proxy/Bug: {bug}:80 atau SSL/SNI: {bug}:443 | Akun: {domain}:443@{user}:{secret}"
        details["uri_tls"] = f"ssh://{user}:{secret}@{domain}:443#{user}-J1BTNL"
        details["uri_ntls"] = f"ssh://{user}:{secret}@{bug}:80#{user}-BUG-J1BTNL"
        details["qr_svg"] = generate_qr_svg_data_uri(details["uri_tls"])

    elif proto == "vmess":
        def encode_vmess(ps_label: str, add_host: str, port_str: str, host_hdr: str, path_str: str, tls_str: str, sni_str: str, net_str: str = "ws", type_str: str = "none") -> str:
            obj = {
                "v": "2",
                "ps": ps_label,
                "add": add_host,
                "port": port_str,
                "id": secret,
                "aid": "0",
                "scy": "auto",
                "net": net_str,
                "type": type_str,
                "host": host_hdr,
                "path": path_str,
                "tls": tls_str,
                "sni": sni_str,
                "alpn": "http/1.1" if net_str == "ws" else "h2",
                "fp": "chrome",
            }
            return "vmess://" + base64.b64encode(json.dumps(obj).encode("utf-8")).decode("ascii")

        details["uri_tls"] = encode_vmess(f"{user}-WS-TLS", domain, "443", domain, "/vmess", "tls", domain)
        details["uri_ntls"] = encode_vmess(f"{user}-WS-NTLS", domain, "80", domain, "/vmess", "none", "")
        details["uri_bug_cdn_tls"] = encode_vmess(f"{user}-BUG-CDN-TLS", bug, "443", domain, "/vmess", "tls", bug)
        details["uri_bug_ntls"] = encode_vmess(f"{user}-BUG-NTLS-80", bug, "80", domain, "/vmess", "none", "")
        details["uri_bug_wildcard"] = encode_vmess(f"{user}-WILDCARD-TLS", bug, "443", wildcard_host, "/vmess", "tls", wildcard_host)
        details["uri_grpc"] = encode_vmess(f"{user}-gRPC-TLS", bug, "443", domain, "vmess-grpc", "tls", domain, net_str="grpc", type_str="gun")
        details["qr_svg"] = generate_qr_svg_data_uri(details["uri_bug_cdn_tls"])

    elif proto == "vless":
        t_tls = urllib.parse.quote(f"{user}-VLESS-TLS")
        t_ntls = urllib.parse.quote(f"{user}-VLESS-NTLS")
        t_bug_tls = urllib.parse.quote(f"{user}-VLESS-BUG-TLS")
        t_bug_ntls = urllib.parse.quote(f"{user}-VLESS-BUG-80")
        t_wild = urllib.parse.quote(f"{user}-VLESS-WILDCARD")
        t_grpc = urllib.parse.quote(f"{user}-VLESS-gRPC")

        details["uri_tls"] = (
            f"vless://{secret}@{domain}:443?path=%2Fvless&security=tls&encryption=none"
            f"&host={domain}&type=ws&sni={domain}&fp=chrome&allowInsecure=1#{t_tls}"
        )
        details["uri_ntls"] = (
            f"vless://{secret}@{domain}:80?path=%2Fvless&security=none&encryption=none"
            f"&host={domain}&type=ws#{t_ntls}"
        )
        details["uri_bug_cdn_tls"] = (
            f"vless://{secret}@{bug}:443?path=%2Fvless&security=tls&encryption=none"
            f"&host={domain}&type=ws&sni={bug}&fp=chrome&allowInsecure=1#{t_bug_tls}"
        )
        details["uri_bug_ntls"] = (
            f"vless://{secret}@{bug}:80?path=%2Fvless&security=none&encryption=none"
            f"&host={domain}&type=ws#{t_bug_ntls}"
        )
        details["uri_bug_wildcard"] = (
            f"vless://{secret}@{bug}:443?path=%2Fvless&security=tls&encryption=none"
            f"&host={wildcard_host}&type=ws&sni={wildcard_host}&fp=chrome&allowInsecure=1#{t_wild}"
        )
        details["uri_grpc"] = (
            f"vless://{secret}@{bug}:443?mode=gun&security=tls&encryption=none"
            f"&type=grpc&serviceName=vless-grpc&sni={domain}&fp=chrome&allowInsecure=1#{t_grpc}"
        )
        details["qr_svg"] = generate_qr_svg_data_uri(details["uri_bug_cdn_tls"])

    elif proto == "trojan":
        t_tls = urllib.parse.quote(f"{user}-TROJAN-TLS")
        t_ntls = urllib.parse.quote(f"{user}-TROJAN-NTLS")
        t_bug_tls = urllib.parse.quote(f"{user}-TROJAN-BUG-TLS")
        t_bug_ntls = urllib.parse.quote(f"{user}-TROJAN-BUG-80")
        t_wild = urllib.parse.quote(f"{user}-TROJAN-WILDCARD")
        t_grpc = urllib.parse.quote(f"{user}-TROJAN-gRPC")

        details["uri_tls"] = (
            f"trojan://{secret}@{domain}:443?path=%2Ftrojan&security=tls"
            f"&host={domain}&type=ws&sni={domain}&fp=chrome&allowInsecure=1#{t_tls}"
        )
        details["uri_ntls"] = (
            f"trojan://{secret}@{domain}:80?path=%2Ftrojan&security=none"
            f"&host={domain}&type=ws#{t_ntls}"
        )
        details["uri_bug_cdn_tls"] = (
            f"trojan://{secret}@{bug}:443?path=%2Ftrojan&security=tls"
            f"&host={domain}&type=ws&sni={bug}&fp=chrome&allowInsecure=1#{t_bug_tls}"
        )
        details["uri_bug_ntls"] = (
            f"trojan://{secret}@{bug}:80?path=%2Ftrojan&security=none"
            f"&host={domain}&type=ws#{t_bug_ntls}"
        )
        details["uri_bug_wildcard"] = (
            f"trojan://{secret}@{bug}:443?path=%2Ftrojan&security=tls"
            f"&host={wildcard_host}&type=ws&sni={wildcard_host}&fp=chrome&allowInsecure=1#{t_wild}"
        )
        details["uri_grpc"] = (
            f"trojan://{secret}@{bug}:443?mode=gun&security=tls"
            f"&type=grpc&serviceName=trojan-grpc&sni={domain}&fp=chrome&allowInsecure=1#{t_grpc}"
        )
        details["qr_svg"] = generate_qr_svg_data_uri(details["uri_bug_cdn_tls"])

    return details


# ==============================================================================
# RUTE UTAMA PUBLIK
# ==============================================================================
@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    if is_system_installed():
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "domain": get_setting("domain", "Belum diatur"),
                "install_mode": get_setting("install_mode", "public"),
                "panel_port": get_setting("panel_port", "8080"),
                "public_ip": get_setting("public_ip", "127.0.0.1"),
                "cache_v": str(int(time.time())),
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
            "cache_v": str(int(time.time())),
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
            "cache_v": str(int(time.time())),
        },
    )


# ==============================================================================
# API TAHAP 1: WIZARD INSTALASI
# ==============================================================================
@app.post("/api/install/start")
async def start_installation(payload: InstallStartRequest):
    if is_system_installed():
        raise HTTPException(status_code=403, detail="Instalasi sudah selesai. Wizard telah dinonaktifkan.")
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
# API SYSTEM & NETWORK OVERVIEW
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
    vn_rx = 0
    vn_tx = 0
    try:
        out = subprocess.check_output(["vnstat", "--json"], stderr=subprocess.DEVNULL, timeout=3).decode("utf-8")
        data = json.loads(out)
        for iface in data.get("interfaces", []):
            if iface.get("name") == "lo":
                continue
            total = iface.get("traffic", {}).get("total", {})
            vn_rx += int(total.get("rx", 0))
            vn_tx += int(total.get("tx", 0))
    except Exception:
        pass

    ps_rx = 0
    ps_tx = 0
    try:
        per_nic = psutil.net_io_counters(pernic=True)
        for nic_name, counters in per_nic.items():
            if nic_name == "lo":
                continue
            ps_rx += int(counters.bytes_recv)
            ps_tx += int(counters.bytes_sent)
    except Exception:
        net_io = psutil.net_io_counters()
        ps_rx = int(net_io.bytes_recv)
        ps_tx = int(net_io.bytes_sent)

    rx = max(vn_rx, ps_rx)
    tx = max(vn_tx, ps_tx)
    return {
        "download": format_bytes_human(rx),
        "upload": format_bytes_human(tx),
        "total": format_bytes_human(rx + tx),
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
    try:
        load1, load5, load15 = os.getloadavg()
    except Exception:
        load1, load5, load15 = 0.0, 0.0, 0.0

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
            if row["protocol"] in counts:
                counts[row["protocol"]] = row["cnt"]
        total_accounts = sum(counts.values())
        online_ips = conn.execute(
            "SELECT COUNT(DISTINCT client_ip) AS cnt FROM active_ips WHERE last_seen >= ?",
            (int(time.time()) - 300,),
        ).fetchone()["cnt"]

    return {
        "system": {
            "os": get_os_pretty_name(),
            "kernel": platform.release(),
            "arch": platform.machine(),
            "hostname": platform.node(),
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
            "mode": "VPS NAT + CF Tunnel" if mode == "nat" else "VPS IP Public",
            "mode_code": mode,
            "domain": get_setting("domain", "localhost"),
            "panel_port": get_setting("panel_port", "8080"),
        },
        "services": services,
        "account_counts": counts,
        "total_accounts": total_accounts,
        "online_ips": online_ips,
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
# API MENU BUAT AKUN, UNLOCK IP, & STATISTIK USER (HAPUS HANYA VIA CLI)
# ==============================================================================
@app.get("/api/accounts")
async def list_accounts(bug_host: str = ""):
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
        item["connection_details"] = build_account_connection_details(item, bug_host=bug_host)
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

    bug_host = (payload.bug_host or "quiz.int.vidio.com").strip()
    if bug_host:
        set_setting("default_bug", bug_host)

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
    acc_dict["connection_details"] = build_account_connection_details(acc_dict, bug_host=bug_host)
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
        conn.execute("DELETE FROM active_ips WHERE username = ?", (row["username"],))
        conn.commit()

    if row["protocol"] == "ssh":
        exp_date_linux = (exp_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        provision_linux_ssh_user(row["username"], row["secret"], exp_date_linux)
        lock_unlock_linux_ssh_user(row["username"], lock=False)
    else:
        sync_xray_accounts_to_config()

    return {"status": "renewed", "exp_display": exp_display}


@app.post("/api/accounts/{account_id}/unlock")
async def unlock_account_and_reset_ip(account_id: int, payload: UnlockAccountRequest):
    """Buka kunci akun (Unlock), bersihkan riwayat IP yang nyangkut, dan perbarui Limit IP."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Akun tidak ditemukan.")

        new_ip_limit = payload.ip_limit if (payload.ip_limit and payload.ip_limit > 0) else row["ip_limit"]
        conn.execute("DELETE FROM active_ips WHERE username = ?", (row["username"],))
        conn.execute(
            "UPDATE accounts SET status = 'active', ip_limit = ? WHERE id = ?",
            (new_ip_limit, account_id),
        )
        conn.commit()

    if row["protocol"] == "ssh":
        lock_unlock_linux_ssh_user(row["username"], lock=False)
    else:
        sync_xray_accounts_to_config()

    return {"status": "unlocked", "username": row["username"], "ip_limit": new_ip_limit}


@app.delete("/api/accounts/{account_id}")
async def delete_account_blocked_on_web(account_id: int):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Hapus akun dinonaktifkan di Web Panel. Gunakan CLI: menu, menu-ssh, menu-vmess, menu-vless, atau menu-trojan.",
    )


@app.get("/api/monitor/status")
async def monitor_accounts_and_ips():
    monitor_script = os.path.join(INSTALL_DIR, "cli", "monitor_ip_quota.sh")
    if os.path.exists(monitor_script):
        subprocess.run(["/bin/bash", monitor_script, "--sync-only"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return await list_accounts()


# ==============================================================================
# API MENU 3: LOG SERVER
# ==============================================================================
LOG_SOURCES = {
    "xray_access": os.path.join(LOG_DIR, "xray_access.log"),
    "xray_error": os.path.join(LOG_DIR, "xray_error.log"),
    "nginx_access": os.path.join(LOG_DIR, "nginx_access.log"),
    "ssh_ws": os.path.join(LOG_DIR, "ssh_ws.log"),
    "cloudflared": os.path.join(LOG_DIR, "cloudflared.log"),
    "monitor": os.path.join(LOG_DIR, "monitor.log"),
}


@app.get("/api/logs")
async def get_server_logs(source: str = "xray_access", lines: int = 100):
    target_path = LOG_SOURCES.get(source, LOG_SOURCES["xray_access"])
    content = ""
    if os.path.exists(target_path):
        try:
            with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
                all_lines = f.readlines()
                content = "".join(all_lines[-min(max(20, lines), 300):])
        except Exception as exc:
            content = f"Gagal membaca log: {exc}"
    else:
        content = f"File log ({target_path}) belum berisi data."

    return {"source": source, "path": target_path, "content": content}


@app.post("/api/logs/clear")
async def clear_server_log(source: str = "xray_access"):
    target_path = LOG_SOURCES.get(source)
    if target_path and os.path.exists(target_path):
        with open(target_path, "w", encoding="utf-8") as f:
            f.write("")
    return {"status": "cleared", "source": source}


# ==============================================================================
# API MENU 5: SETTING BANNER SSH & BACKUP / RESTORE
# ==============================================================================
DEFAULT_BANNER = (
    '<font color="#00f2fe"><b>====================================================</b></font><br>\n'
    '<font color="#a855f7"><b>        🚀 JIBSZ TUNNELING / J1BTNL SERVER 🚀       </b></font><br>\n'
    '<font color="#00f2fe"><b>====================================================</b></font><br>\n'
    '<font color="#10b981"><b> • No DDoS / No Flooding / No Torrent / No Spam     </b></font><br>\n'
    '<font color="#f59e0b"><b> • Support & Credit Telegram : @admj1btnl           </b></font><br>\n'
    '<font color="#00f2fe"><b>====================================================</b></font>'
)


@app.get("/api/settings/banner")
async def get_ssh_banner():
    if os.path.exists(BANNER_FILE):
        try:
            with open(BANNER_FILE, "r", encoding="utf-8", errors="ignore") as f:
                return {"banner_html": f.read()}
        except Exception:
            pass
    return {"banner_html": DEFAULT_BANNER}


@app.post("/api/settings/banner")
async def save_ssh_banner(payload: BannerUpdateRequest):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(BANNER_FILE, "w", encoding="utf-8") as f:
        f.write(payload.banner_html)
    subprocess.run(["systemctl", "restart", "dropbear"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["systemctl", "reload", "ssh"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"status": "saved"}


@app.get("/api/settings/backups")
async def list_backups():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    files = []
    for fname in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if fname.endswith(".tar.gz"):
            fpath = os.path.join(BACKUP_DIR, fname)
            files.append({
                "filename": fname,
                "size_kb": round(os.path.getsize(fpath) / 1024, 1),
                "created_at": datetime.datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M:%S"),
            })
    return {"backups": files}


@app.post("/api/settings/backup")
async def create_backup_archive():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    fname = f"jibsz-backup-{ts}.tar.gz"
    fpath = os.path.join(BACKUP_DIR, fname)

    with tarfile.open(fpath, "w:gz") as tar:
        if os.path.exists(CONFIG_DIR):
            tar.add(CONFIG_DIR, arcname="etc/jibsz")
        if os.path.exists(XRAY_CONFIG_PATH):
            tar.add(XRAY_CONFIG_PATH, arcname="usr/local/etc/xray/config.json")

    return {"status": "created", "filename": fname}


@app.get("/api/settings/backup/download/{filename}")
async def download_backup_archive(filename: str):
    safe_name = os.path.basename(filename)
    fpath = os.path.join(BACKUP_DIR, safe_name)
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="File backup tidak ditemukan.")
    return FileResponse(fpath, media_type="application/gzip", filename=safe_name)


@app.post("/api/settings/restore-local")
async def restore_from_local_backup(payload: RestoreLocalRequest):
    safe_name = os.path.basename(payload.filename)
    fpath = os.path.join(BACKUP_DIR, safe_name)
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="File backup tidak ditemukan.")

    with tarfile.open(fpath, "r:gz") as tar:
        tar.extractall(path="/")

    sync_xray_accounts_to_config()
    return {"status": "restored", "filename": safe_name}


@app.post("/api/settings/restore-upload")
async def restore_from_uploaded_backup(file: UploadFile = File(...)):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    safe_name = f"uploaded-{int(time.time())}-{os.path.basename(file.filename or 'backup.tar.gz')}"
    fpath = os.path.join(BACKUP_DIR, safe_name)

    content = await file.read()
    with open(fpath, "wb") as f:
        f.write(content)

    try:
        with tarfile.open(fpath, "r:gz") as tar:
            tar.extractall(path="/")
        sync_xray_accounts_to_config()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Format arsip backup tidak valid: {exc}")

    return {"status": "restored", "filename": safe_name}
