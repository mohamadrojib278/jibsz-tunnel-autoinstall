#!/usr/bin/env bash
# ==============================================================================
# JIBSZ TUNNELING / J1BTNL - MAIN CLI & SYSTEM MENU (cli/menu.sh)
# Author   : Jibsz Tunneling (@admj1btnl)
# Perintah : menu, jibsz, menu-system
# Sinkron  : Database SQLite (/etc/jibsz/jibsz.db) & Web Panel
# ==============================================================================

set -u

INSTALL_DIR="/opt/jibsz-tunnel"
CONFIG_DIR="/etc/jibsz"
LOG_DIR="/var/log/jibsz"
DB_FILE="${CONFIG_DIR}/jibsz.db"
BACKUP_DIR="/root/jibsz-backups"

C_RESET="\033[0m"
C_CYAN="\033[1;36m"
C_PURPLE="\033[1;35m"
C_GREEN="\033[1;32m"
C_YELLOW="\033[1;33m"
C_RED="\033[1;31m"
C_WHITE="\033[1;37m"

get_setting() {
    sqlite3 "${DB_FILE}" "SELECT value FROM settings WHERE key='$1' LIMIT 1;" 2>/dev/null || echo ""
}

set_setting() {
    sqlite3 "${DB_FILE}" "INSERT OR REPLACE INTO settings (key, value) VALUES ('$1', '$2');" 2>/dev/null || true
}

svc_badge() {
    local svc="$1"
    if systemctl is-active --quiet "$svc" 2>/dev/null || pgrep -f "$svc" >/dev/null 2>&1; then
        echo -e "${C_GREEN}RUNNING${C_RESET}"
    else
        echo -e "${C_RED}STOPPED${C_RESET}"
    fi
}

show_header() {
    clear
    local os_name kernel uptime_str ram_usage cpu_cores domain pub_ip mode panel_port
    os_name=$(grep '^PRETTY_NAME=' /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"')
    [[ -z "$os_name" ]] && os_name="$(uname -s) $(uname -r)"
    kernel=$(uname -r)
    uptime_str=$(uptime -p 2>/dev/null | sed 's/up //')
    ram_usage=$(free -m | awk '/Mem:/ {printf "%d MB / %d MB (%.1f%%)", $3, $2, ($3/$2)*100}')
    cpu_cores=$(nproc 2>/dev/null || echo "1")
    domain=$(get_setting "domain")
    [[ -z "$domain" ]] && domain="Belum diatur"
    pub_ip=$(get_setting "public_ip")
    [[ -z "$pub_ip" ]] && pub_ip="127.0.0.1"
    mode=$(get_setting "install_mode")
    panel_port=$(get_setting "panel_port")

    local mode_label="VPS IP Public (Direct 80/443)"
    [[ "$mode" == "nat" ]] && mode_label="VPS NAT + Cloudflare Tunnel (localhost:80)"

    local cnt_ssh cnt_vmess cnt_vless cnt_trojan
    cnt_ssh=$(sqlite3 "${DB_FILE}" "SELECT COUNT(*) FROM accounts WHERE protocol='ssh' AND status='active';" 2>/dev/null || echo 0)
    cnt_vmess=$(sqlite3 "${DB_FILE}" "SELECT COUNT(*) FROM accounts WHERE protocol='vmess' AND status='active';" 2>/dev/null || echo 0)
    cnt_vless=$(sqlite3 "${DB_FILE}" "SELECT COUNT(*) FROM accounts WHERE protocol='vless' AND status='active';" 2>/dev/null || echo 0)
    cnt_trojan=$(sqlite3 "${DB_FILE}" "SELECT COUNT(*) FROM accounts WHERE protocol='trojan' AND status='active';" 2>/dev/null || echo 0)

    echo -e "${C_PURPLE}╔══════════════════════════════════════════════════════════════════════╗${C_RESET}"
    echo -e "${C_PURPLE}║${C_CYAN}         🚀 JIBSZ TUNNELING / J1BTNL — CLI MANAGEMENT PANEL 🚀        ${C_PURPLE}║${C_RESET}"
    echo -e "${C_PURPLE}║${C_WHITE}          Credit Telegram: @admj1btnl | GitHub: mohamadrojib278       ${C_PURPLE}║${C_RESET}"
    echo -e "${C_PURPLE}╠══════════════════════════════════════════════════════════════════════╣${C_RESET}"
    echo -e "${C_PURPLE}║${C_WHITE} OS / Kernel   : ${C_CYAN}${os_name} (${kernel})${C_RESET}"
    echo -e "${C_PURPLE}║${C_WHITE} RAM / CPU     : ${C_YELLOW}${ram_usage} | ${cpu_cores} Core${C_RESET}"
    echo -e "${C_PURPLE}║${C_WHITE} Uptime Server : ${C_GREEN}${uptime_str}${C_RESET}"
    echo -e "${C_PURPLE}║${C_WHITE} Mode Jaringan : ${C_PURPLE}${mode_label}${C_RESET}"
    echo -e "${C_PURPLE}║${C_WHITE} Domain / IP   : ${C_CYAN}${domain}${C_WHITE} (${pub_ip})${C_RESET}"
    echo -e "${C_PURPLE}║${C_WHITE} URL Web Panel : ${C_YELLOW}http://${pub_ip}:${panel_port}${C_RESET}"
    echo -e "${C_PURPLE}╠══════════════════════════════════════════════════════════════════════╣${C_RESET}"
    echo -e "${C_PURPLE}║${C_WHITE} NGINX : $(svc_badge nginx) | XRAY : $(svc_badge xray) | SSH-WS : $(svc_badge ssh_ws_proxy.py) | CF-TUNNEL : $(svc_badge cloudflared)${C_RESET}"
    echo -e "${C_PURPLE}║${C_WHITE} Akun Aktif    : SSH [${C_GREEN}${cnt_ssh}${C_WHITE}] • VMess [${C_GREEN}${cnt_vmess}${C_WHITE}] • VLESS [${C_GREEN}${cnt_vless}${C_WHITE}] • Trojan [${C_GREEN}${cnt_trojan}${C_WHITE}]${C_RESET}"
    echo -e "${C_PURPLE}╚══════════════════════════════════════════════════════════════════════╝${C_RESET}"
}

# ==============================================================================
# SUB-MENU SYSTEM (menu-system)
# ==============================================================================
menu_system() {
    while true; do
        show_header
        echo -e "${C_CYAN}  [ MENU SYSTEM & PENGATURAN SERVER ]${C_RESET}"
        echo -e "  ${C_YELLOW}[1]${C_WHITE} Ganti Domain / Subdomain Server & Perbarui Nginx/SSL"
        echo -e "  ${C_YELLOW}[2]${C_WHITE} Update Token Cloudflare Zero Trust Tunnel (Mode VPS NAT)"
        echo -e "  ${C_YELLOW}[3]${C_WHITE} Ganti Custom Port Web Panel Jibsz"
        echo -e "  ${C_YELLOW}[4]${C_WHITE} Restart Semua Service Tunneling & Web Panel"
        echo -e "  ${C_YELLOW}[5]${C_WHITE} Jalankan Auto-Delete / Lock Expired & Multi-Login Sekarang"
        echo -e "  ${C_YELLOW}[6]${C_WHITE} Backup Database Akun & Konfigurasi (/root/jibsz-backups)"
        echo -e "  ${C_YELLOW}[7]${C_WHITE} Restore Database Akun & Konfigurasi"
        echo -e "  ${C_YELLOW}[0]${C_WHITE} Kembali ke Menu Utama / Keluar"
        echo -e "${C_PURPLE}────────────────────────────────────────────────────────────────────────${C_RESET}"
        read -rp "  Pilih opsi [0-7]: " sys_opt

        case "$sys_opt" in
            1)
                read -rp "  Masukkan Domain / Subdomain baru: " new_domain
                if [[ -n "$new_domain" ]]; then
                    set_setting "domain" "$new_domain"
                    bash "${INSTALL_DIR}/backend/installer_engine.sh" --component nginx
                    bash "${INSTALL_DIR}/backend/installer_engine.sh" --component tunnel_ssl
                    echo -e "  ${C_GREEN}Domain berhasil diperbarui ke ${new_domain}!${C_RESET}"
                fi
                read -rp "  Tekan Enter untuk melanjutkan..."
                ;;
            2)
                read -rp "  Masukkan Cloudflare Tunnel Token baru (eyJhIjoi...): " new_token
                if [[ -n "$new_token" ]]; then
                    set_setting "install_mode" "nat"
                    set_setting "cf_token" "$new_token"
                    bash "${INSTALL_DIR}/backend/installer_engine.sh" --component nginx
                    bash "${INSTALL_DIR}/backend/installer_engine.sh" --component tunnel_ssl
                    echo -e "  ${C_GREEN}Token Cloudflare Tunnel berhasil diperbarui dan cloudflared di-restart!${C_RESET}"
                fi
                read -rp "  Tekan Enter untuk melanjutkan..."
                ;;
            3)
                read -rp "  Masukkan Custom Port Web Panel baru (81-65535): " new_port
                if [[ "$new_port" =~ ^[0-9]+$ ]] && (( new_port >= 81 && new_port <= 65535 )) && (( new_port != 443 )); then
                    set_setting "panel_port" "$new_port"
                    sed -i "s/^PANEL_PORT=.*/PANEL_PORT=${new_port}/" "${CONFIG_DIR}/panel.env" 2>/dev/null || true
                    sed -i "s/--port [0-9]\+/--port ${new_port}/g" /etc/systemd/system/jibsz-webpanel.service 2>/dev/null || true
                    systemctl daemon-reload 2>/dev/null || true
                    systemctl restart jibsz-webpanel 2>/dev/null || true
                    iptables -I INPUT -p tcp --dport "${new_port}" -j ACCEPT 2>/dev/null || true
                    echo -e "  ${C_GREEN}Port Web Panel berhasil diubah ke ${new_port}!${C_RESET}"
                else
                    echo -e "  ${C_RED}Port tidak valid!${C_RESET}"
                fi
                read -rp "  Tekan Enter untuk melanjutkan..."
                ;;
            4)
                echo -e "  ${C_CYAN}Me-restart seluruh layanan...${C_RESET}"
                for s in nginx xray ssh dropbear ssh-ws cloudflared badvpn-udpgw cron jibsz-webpanel; do
                    systemctl restart "$s" 2>/dev/null || true
                done
                echo -e "  ${C_GREEN}Semua service telah di-restart!${C_RESET}"
                read -rp "  Tekan Enter untuk melanjutkan..."
                ;;
            5)
                bash "${INSTALL_DIR}/cli/monitor_ip_quota.sh" --cron
                echo -e "  ${C_GREEN}Pengecekan akun expired, kuota, dan multi-login selesai dijalankan!${C_RESET}"
                read -rp "  Tekan Enter untuk melanjutkan..."
                ;;
            6)
                mkdir -p "${BACKUP_DIR}"
                local ts_file="${BACKUP_DIR}/jibsz-backup-$(date '+%Y%m%d-%H%M%S').tar.gz"
                tar -czf "$ts_file" "${CONFIG_DIR}" /usr/local/etc/xray/config.json 2>/dev/null || true
                echo -e "  ${C_GREEN}Backup berhasil disimpan di: ${ts_file}${C_RESET}"
                read -rp "  Tekan Enter untuk melanjutkan..."
                ;;
            7)
                echo -e "  Daftar file backup di ${BACKUP_DIR}:"
                ls -1 "${BACKUP_DIR}"/*.tar.gz 2>/dev/null || echo "  (Belum ada file backup)"
                read -rp "  Masukkan path lengkap file backup (.tar.gz) untuk di-restore: " restore_path
                if [[ -f "$restore_path" ]]; then
                    tar -xzf "$restore_path" -C /
                    systemctl restart xray nginx ssh-ws jibsz-webpanel 2>/dev/null || true
                    echo -e "  ${C_GREEN}Database & konfigurasi berhasil di-restore!${C_RESET}"
                else
                    echo -e "  ${C_RED}File tidak ditemukan.${C_RESET}"
                fi
                read -rp "  Tekan Enter untuk melanjutkan..."
                ;;
            0)
                break
                ;;
            *)
                ;;
        esac
    done
}

# Jika dipanggil langsung sebagai menu-system
if [[ "$(basename "$0")" == "menu-system" || "${1:-}" == "system" ]]; then
    menu_system
    exit 0
fi

# ==============================================================================
# MENU INTERAKTIF UTAMA (menu / jibsz)
# ==============================================================================
while true; do
    show_header
    echo -e "${C_CYAN}  [ DAFTAR MENU MANAJEMEN JIBSZ TUNNELING ]${C_RESET}"
    echo -e "  ${C_YELLOW}[1]${C_WHITE} Menu SSH & OpenVPN WebSocket (${C_GREEN}menu-ssh${C_WHITE})"
    echo -e "  ${C_YELLOW}[2]${C_WHITE} Menu VMess Xray WS & gRPC    (${C_GREEN}menu-vmess${C_WHITE})"
    echo -e "  ${C_YELLOW}[3]${C_WHITE} Menu VLESS Xray WS & gRPC    (${C_GREEN}menu-vless${C_WHITE})"
    echo -e "  ${C_YELLOW}[4]${C_WHITE} Menu Trojan Xray WS & gRPC   (${C_GREEN}menu-trojan${C_WHITE})"
    echo -e "  ${C_YELLOW}[5]${C_WHITE} Cek Monitoring IP Client & Kuota Real-Time"
    echo -e "  ${C_YELLOW}[6]${C_WHITE} Menu System, Domain, CF Token, & Backup (${C_GREEN}menu-system${C_WHITE})"
    echo -e "  ${C_YELLOW}[0]${C_WHITE} Keluar dari Menu"
    echo -e "${C_PURPLE}────────────────────────────────────────────────────────────────────────${C_RESET}"
    read -rp "  Pilih menu [0-6]: " main_opt

    case "$main_opt" in
        1)
            bash "${INSTALL_DIR}/cli/manage_ssh.sh"
            ;;
        2)
            bash "${INSTALL_DIR}/cli/manage_xray.sh" vmess
            ;;
        3)
            bash "${INSTALL_DIR}/cli/manage_xray.sh" vless
            ;;
        4)
            bash "${INSTALL_DIR}/cli/manage_xray.sh" trojan
            ;;
        5)
            bash "${INSTALL_DIR}/cli/monitor_ip_quota.sh" --report
            read -rp "  Tekan Enter untuk kembali ke menu..."
            ;;
        6)
            menu_system
            ;;
        0|q|exit)
            clear
            exit 0
            ;;
        *)
            ;;
    esac
done
