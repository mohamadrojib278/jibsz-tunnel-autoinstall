#!/usr/bin/env bash
# ==============================================================================
# JIBSZ TUNNELING / J1BTNL - XRAY MULTI-PROTOCOL CLI MANAGER (cli/manage_xray.sh)
# Author   : Jibsz Tunneling (@admj1btnl)
# Perintah : menu-vmess, menu-vless, menu-trojan
# Sinkron  : Database SQLite (/etc/jibsz/jibsz.db) & /usr/local/etc/xray/config.json
# ==============================================================================

set -u

INSTALL_DIR="/opt/jibsz-tunnel"
CONFIG_DIR="/etc/jibsz"
DB_FILE="${CONFIG_DIR}/jibsz.db"
XRAY_CFG="/usr/local/etc/xray/config.json"

C_RESET="\033[0m"
C_CYAN="\033[1;36m"
C_PURPLE="\033[1;35m"
C_GREEN="\033[1;32m"
C_YELLOW="\033[1;33m"
C_RED="\033[1;31m"
C_WHITE="\033[1;37m"

# Tentukan protokol dari argumen atau nama symlink pemanggil (menu-vmess / menu-vless / menu-trojan)
CALLER_NAME="$(basename "$0")"
PROTO="${1:-}"
if [[ -z "$PROTO" ]]; then
    case "$CALLER_NAME" in
        *vmess*)  PROTO="vmess" ;;
        *vless*)  PROTO="vless" ;;
        *trojan*) PROTO="trojan" ;;
        *)        PROTO="vless" ;;
    esac
fi
PROTO="${PROTO,,}"

get_setting() {
    sqlite3 "${DB_FILE}" "SELECT value FROM settings WHERE key='$1' LIMIT 1;" 2>/dev/null || echo ""
}

sync_xray_config() {
    python3 - << 'PYEOF'
import json, os, sqlite3, subprocess

db_path = "/etc/jibsz/jibsz.db"
cfg_path = "/usr/local/etc/xray/config.json"

if not os.path.exists(cfg_path):
    raise SystemExit(0)

with open(cfg_path, "r", encoding="utf-8") as f:
    cfg = json.load(f)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT protocol, username, secret FROM accounts WHERE status='active' AND protocol IN ('vless','vmess','trojan')"
).fetchall()

vless_c, vmess_c, trojan_c = [], [], []
for r in rows:
    email = f"{r['username']}@j1btnl"
    if r["protocol"] == "vless":
        vless_c.append({"id": r["secret"], "email": email, "level": 0})
    elif r["protocol"] == "vmess":
        vmess_c.append({"id": r["secret"], "alterId": 0, "email": email, "level": 0})
    elif r["protocol"] == "trojan":
        trojan_c.append({"password": r["secret"], "email": email, "level": 0})

for inb in cfg.get("inbounds", []):
    t = inb.get("tag", "")
    if t in ("vless-ws", "vless-grpc"):
        inb.setdefault("settings", {})["clients"] = vless_c
    elif t in ("vmess-ws", "vmess-grpc"):
        inb.setdefault("settings", {})["clients"] = vmess_c
    elif t in ("trojan-ws", "trojan-grpc"):
        inb.setdefault("settings", {})["clients"] = trojan_c

with open(cfg_path + ".tmp", "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=2)
os.replace(cfg_path + ".tmp", cfg_path)
subprocess.run(["systemctl", "restart", "xray"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
PYEOF
}

print_xray_links() {
    local proto="$1"
    local user="$2"
    local secret="$3"
    local exp_disp="$4"
    local ip_lim="$5"
    local quota_gb="$6"
    local domain pub_ip
    domain=$(get_setting "domain")
    pub_ip=$(get_setting "public_ip")
    [[ -z "$domain" ]] && domain="$pub_ip"

    local uri_tls uri_ntls uri_grpc
    if [[ "$proto" == "vmess" ]]; then
        local json_tls json_ntls json_grpc
        json_tls=$(printf '{"v":"2","ps":"%s-WS-TLS-J1BTNL","add":"%s","port":"443","id":"%s","aid":"0","scy":"auto","net":"ws","type":"none","host":"%s","path":"/vmess","tls":"tls","sni":"%s"}' "$user" "$domain" "$secret" "$domain" "$domain")
        json_ntls=$(printf '{"v":"2","ps":"%s-WS-NTLS-J1BTNL","add":"%s","port":"80","id":"%s","aid":"0","scy":"auto","net":"ws","type":"none","host":"%s","path":"/vmess","tls":"none"}' "$user" "$domain" "$secret" "$domain")
        json_grpc=$(printf '{"v":"2","ps":"%s-gRPC-J1BTNL","add":"%s","port":"443","id":"%s","aid":"0","scy":"auto","net":"grpc","type":"gun","host":"%s","path":"vmess-grpc","tls":"tls","sni":"%s"}' "$user" "$domain" "$secret" "$domain" "$domain")
        uri_tls="vmess://$(printf "%s" "$json_tls" | base64 -w 0)"
        uri_ntls="vmess://$(printf "%s" "$json_ntls" | base64 -w 0)"
        uri_grpc="vmess://$(printf "%s" "$json_grpc" | base64 -w 0)"
    elif [[ "$proto" == "vless" ]]; then
        uri_tls="vless://${secret}@${domain}:443?path=%2Fvless&security=tls&encryption=none&host=${domain}&type=ws&sni=${domain}#${user}-VLESS-TLS-J1BTNL"
        uri_ntls="vless://${secret}@${domain}:80?path=%2Fvless&security=none&encryption=none&host=${domain}&type=ws#${user}-VLESS-NTLS-J1BTNL"
        uri_grpc="vless://${secret}@${domain}:443?mode=gun&security=tls&encryption=none&type=grpc&serviceName=vless-grpc&sni=${domain}#${user}-VLESS-gRPC-J1BTNL"
    else
        uri_tls="trojan://${secret}@${domain}:443?path=%2Ftrojan&security=tls&host=${domain}&type=ws&sni=${domain}#${user}-TROJAN-TLS-J1BTNL"
        uri_ntls="trojan://${secret}@${domain}:80?path=%2Ftrojan&security=none&host=${domain}&type=ws#${user}-TROJAN-NTLS-J1BTNL"
        uri_grpc="trojan://${secret}@${domain}:443?mode=gun&security=tls&type=grpc&serviceName=trojan-grpc&sni=${domain}#${user}-TROJAN-gRPC-J1BTNL"
    fi

    echo ""
    echo -e "${C_PURPLE}╔══════════════════════════════════════════════════════════════════════╗${C_RESET}"
    echo -e "${C_PURPLE}║${C_GREEN}             DETAIL AKUN XRAY ${proto^^} (J1BTNL EDITION)             ${C_PURPLE}║${C_RESET}"
    echo -e "${C_PURPLE}╠══════════════════════════════════════════════════════════════════════╣${C_RESET}"
    echo -e "  Remarks / Username : ${C_YELLOW}${user}${C_RESET}"
    echo -e "  Host / Domain      : ${C_CYAN}${domain}${C_RESET}"
    echo -e "  IP Public VPS      : ${C_CYAN}${pub_ip}${C_RESET}"
    echo -e "  UUID / Password    : ${C_YELLOW}${secret}${C_RESET}"
    echo -e "  Port TLS / CDN     : 443"
    echo -e "  Port Non-TLS       : 80"
    echo -e "  Path WebSocket     : ${C_GREEN}/${proto}${C_RESET}"
    echo -e "  ServiceName gRPC   : ${C_GREEN}${proto}-grpc${C_RESET}"
    echo -e "  Limit IP / Kuota   : ${ip_lim} IP / ${quota_gb} GB"
    echo -e "  Masa Aktif s/d     : ${C_CYAN}${exp_disp}${C_RESET}"
    echo -e "${C_PURPLE}╠══════════════════════════════════════════════════════════════════════╣${C_RESET}"
    echo -e "  ${C_WHITE}Link WS TLS (Port 443 / Cloudflare CDN):${C_RESET}"
    echo -e "  ${C_GREEN}${uri_tls}${C_RESET}"
    echo ""
    echo -e "  ${C_WHITE}Link WS Non-TLS (Port 80):${C_RESET}"
    echo -e "  ${C_GREEN}${uri_ntls}${C_RESET}"
    echo ""
    echo -e "  ${C_WHITE}Link gRPC TLS (Port 443):${C_RESET}"
    echo -e "  ${C_GREEN}${uri_grpc}${C_RESET}"
    echo -e "${C_PURPLE}╠══════════════════════════════════════════════════════════════════════╣${C_RESET}"
    echo -e "  ${C_WHITE}Credit Telegram : @admj1btnl | Jibsz Tunneling${C_RESET}"
    echo -e "${C_PURPLE}╚══════════════════════════════════════════════════════════════════════╝${C_RESET}"
}

create_xray_cli() {
    local is_trial="${1:-0}"
    local user secret days mins ip_limit quota_gb exp_ts exp_disp

    if [[ "$is_trial" == "1" ]]; then
        user="trial${PROTO}$(shuf -i 100-999 -n 1)"
        secret=$(cat /proc/sys/kernel/random/uuid)
        read -rp "  Durasi Trial ${PROTO^^} dalam menit [default: 60]: " mins
        mins="${mins:-60}"
        ip_limit=2
        quota_gb=2
        exp_ts=$(( $(date +%s) + (mins * 60) ))
        exp_disp=$(date -d "@${exp_ts}" '+%Y-%m-%d %H:%M')
    else
        read -rp "  Masukkan Username ${PROTO^^} baru : " user
        [[ -z "$user" ]] && return
        read -rp "  Custom UUID/Password (kosong = otomatis): " secret
        [[ -z "$secret" ]] && secret=$(cat /proc/sys/kernel/random/uuid)
        read -rp "  Masa Aktif (hari) [30]            : " days
        days="${days:-30}"
        read -rp "  Limit IP Login [2]                : " ip_limit
        ip_limit="${ip_limit:-2}"
        read -rp "  Limit Kuota Bandwidth (GB) [50]   : " quota_gb
        quota_gb="${quota_gb:-50}"
        exp_ts=$(( $(date +%s) + (days * 86400) ))
        exp_disp=$(date -d "@${exp_ts}" '+%Y-%m-%d %H:%M')
    fi

    local exists
    exists=$(sqlite3 "${DB_FILE}" "SELECT COUNT(*) FROM accounts WHERE username='${user}';")
    if [[ "$exists" -gt 0 ]]; then
        echo -e "  ${C_RED}Error: Username '${user}' sudah terdaftar!${C_RESET}"
        return
    fi

    sqlite3 "${DB_FILE}" "INSERT INTO accounts (protocol, username, secret, exp_timestamp, exp_display, is_trial, ip_limit, quota_gb, status) VALUES ('${PROTO}', '${user}', '${secret}', ${exp_ts}, '${exp_disp}', ${is_trial}, ${ip_limit}, ${quota_gb}, 'active');"
    sync_xray_config
    print_xray_links "$PROTO" "$user" "$secret" "$exp_disp" "$ip_limit" "$quota_gb"
}

renew_xray_cli() {
    sqlite3 -header -column "${DB_FILE}" "SELECT id, username, exp_display, ip_limit, quota_gb, status FROM accounts WHERE protocol='${PROTO}';"
    echo ""
    read -rp "  Masukkan Username ${PROTO^^} yang akan diperpanjang: " user
    [[ -z "$user" ]] && return
    read -rp "  Tambah masa aktif berapa hari? [30]: " add_days
    add_days="${add_days:-30}"

    local curr_exp
    curr_exp=$(sqlite3 "${DB_FILE}" "SELECT exp_timestamp FROM accounts WHERE username='${user}' AND protocol='${PROTO}';")
    if [[ -z "$curr_exp" ]]; then
        echo -e "  ${C_RED}Akun tidak ditemukan.${C_RESET}"
        return
    fi

    local now_ts base_ts new_ts new_disp
    now_ts=$(date +%s)
    base_ts=$(( curr_exp > now_ts ? curr_exp : now_ts ))
    new_ts=$(( base_ts + (add_days * 86400) ))
    new_disp=$(date -d "@${new_ts}" '+%Y-%m-%d %H:%M')

    sqlite3 "${DB_FILE}" "UPDATE accounts SET exp_timestamp=${new_ts}, exp_display='${new_disp}', status='active', is_trial=0 WHERE username='${user}' AND protocol='${PROTO}';"
    sync_xray_config
    echo -e "  ${C_GREEN}Akun ${PROTO^^} '${user}' berhasil diperpanjang hingga ${new_disp}!${C_RESET}"
}

delete_xray_cli() {
    sqlite3 -header -column "${DB_FILE}" "SELECT id, username, exp_display, status FROM accounts WHERE protocol='${PROTO}';"
    echo ""
    read -rp "  Masukkan Username ${PROTO^^} yang akan dihapus: " user
    [[ -z "$user" ]] && return

    sqlite3 "${DB_FILE}" "DELETE FROM accounts WHERE username='${user}' AND protocol='${PROTO}';"
    sqlite3 "${DB_FILE}" "DELETE FROM active_ips WHERE username='${user}' AND protocol='${PROTO}';"
    sync_xray_config
    echo -e "  ${C_GREEN}Akun ${PROTO^^} '${user}' berhasil dihapus.${C_RESET}"
}

check_xray_quota_ip_cli() {
    bash "${INSTALL_DIR}/cli/monitor_ip_quota.sh" --sync-only
    echo ""
    echo -e "${C_CYAN}  [ MONITORING KUOTA & IP CLIENT ASLI - PROTOKOL ${PROTO^^} ]${C_RESET}"
    sqlite3 -header -column "${DB_FILE}" "
        SELECT a.username AS Username,
               a.status AS Status,
               printf('%.2f MB', (a.up_bytes + a.down_bytes) / 1048576.0) AS Pemakaian,
               printf('%.1f GB', a.quota_gb) AS Limit_Kuota,
               COUNT(i.client_ip) || '/' || a.ip_limit AS IP_Login,
               IFNULL(GROUP_CONCAT(i.client_ip, ', '), '-') AS Client_Real_IPs
        FROM accounts a
        LEFT JOIN active_ips i ON a.username = i.username AND a.protocol = i.protocol AND i.last_seen >= (strftime('%s','now') - 300)
        WHERE a.protocol = '${PROTO}'
        GROUP BY a.username;
    "
    echo ""
}

while true; do
    clear
    echo -e "${C_PURPLE}╔══════════════════════════════════════════════════════════════════════╗${C_RESET}"
    echo -e "${C_PURPLE}║${C_CYAN}           MENU MANAJEMEN XRAY ${PROTO^^} (WS & gRPC - J1BTNL)           ${C_PURPLE}║${C_RESET}"
    echo -e "${C_PURPLE}╚══════════════════════════════════════════════════════════════════════╝${C_RESET}"
    echo -e "  ${C_YELLOW}[1]${C_WHITE} Buat Akun ${PROTO^^} Baru"
    echo -e "  ${C_YELLOW}[2]${C_WHITE} Buat Akun Trial ${PROTO^^} (Menit)"
    echo -e "  ${C_YELLOW}[3]${C_WHITE} Perpanjang Masa Aktif Akun ${PROTO^^} (Renew)"
    echo -e "  ${C_YELLOW}[4]${C_WHITE} Hapus Akun ${PROTO^^} (Delete)"
    echo -e "  ${C_YELLOW}[5]${C_WHITE} Cek User Login, IP Client Asli, & Pemakaian Kuota ${PROTO^^}"
    echo -e "  ${C_YELLOW}[0]${C_WHITE} Kembali ke Menu Utama"
    echo -e "${C_PURPLE}────────────────────────────────────────────────────────────────────────${C_RESET}"
    read -rp "  Pilih opsi [0-5]: " opt
    case "$opt" in
        1) create_xray_cli 0; read -rp "  Tekan Enter untuk lanjut..." ;;
        2) create_xray_cli 1; read -rp "  Tekan Enter untuk lanjut..." ;;
        3) renew_xray_cli; read -rp "  Tekan Enter untuk lanjut..." ;;
        4) delete_xray_cli; read -rp "  Tekan Enter untuk lanjut..." ;;
        5) check_xray_quota_ip_cli; read -rp "  Tekan Enter untuk lanjut..." ;;
        0) break ;;
        *) ;;
    esac
done
