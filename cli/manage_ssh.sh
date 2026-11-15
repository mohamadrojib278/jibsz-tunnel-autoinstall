#!/usr/bin/env bash
# ==============================================================================
# JIBSZ TUNNELING / J1BTNL - SSH & WEBSOCKET CLI MANAGER (cli/manage_ssh.sh)
# Author   : Jibsz Tunneling (@admj1btnl)
# Perintah : menu-ssh
# Sinkron  : Database SQLite (/etc/jibsz/jibsz.db) & Linux System Users
# ==============================================================================

set -u

INSTALL_DIR="/opt/jibsz-tunnel"
CONFIG_DIR="/etc/jibsz"
DB_FILE="${CONFIG_DIR}/jibsz.db"

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

print_ssh_account_Summary() {
    local user="$1"
    local pass="$2"
    local exp_disp="$3"
    local ip_lim="$4"
    local quota_gb="$5"
    local domain pub_ip
    domain=$(get_setting "domain")
    pub_ip=$(get_setting "public_ip")
    [[ -z "$domain" ]] && domain="$pub_ip"

    echo ""
    echo -e "${C_PURPLE}╔══════════════════════════════════════════════════════════════════════╗${C_RESET}"
    echo -e "${C_PURPLE}║${C_GREEN}              DETAIL AKUN SSH & WEBSOCKET (J1BTNL EDITION)            ${C_PURPLE}║${C_RESET}"
    echo -e "${C_PURPLE}╠══════════════════════════════════════════════════════════════════════╣${C_RESET}"
    echo -e "  Host / Domain      : ${C_CYAN}${domain}${C_RESET}"
    echo -e "  IP Public VPS      : ${C_CYAN}${pub_ip}${C_RESET}"
    echo -e "  Username           : ${C_YELLOW}${user}${C_RESET}"
    echo -e "  Password           : ${C_YELLOW}${pass}${C_RESET}"
    echo -e "  Port OpenSSH       : 22"
    echo -e "  Port Dropbear      : 109, 143"
    echo -e "  Port SSH WS (TLS)  : 443"
    echo -e "  Port SSH WS (NTLS) : 80"
    echo -e "  Port BadVPN UDPGW  : 7300"
    echo -e "  Path WebSocket     : ${C_GREEN}/ssh-ws${C_RESET} (atau ${C_GREEN}/${C_RESET})"
    echo -e "  Limit IP / Kuota   : ${ip_lim} IP / ${quota_gb} GB"
    echo -e "  Masa Aktif s/d     : ${C_CYAN}${exp_disp}${C_RESET}"
    echo -e "${C_PURPLE}╠══════════════════════════════════════════════════════════════════════╣${C_RESET}"
    echo -e "  ${C_WHITE}Payload HTTP Custom / DarkTunnel (WS Non-TLS 80 & CF Tunnel):${C_RESET}"
    echo -e "  ${C_GREEN}GET /ssh-ws HTTP/1.1[crlf]Host: ${domain}[crlf]Upgrade: websocket[crlf]Connection: Upgrade[crlf][crlf]${C_RESET}"
    echo -e "${C_PURPLE}╠══════════════════════════════════════════════════════════════════════╣${C_RESET}"
    echo -e "  ${C_WHITE}Credit Telegram : @admj1btnl | Jibsz Tunneling${C_RESET}"
    echo -e "${C_PURPLE}╚══════════════════════════════════════════════════════════════════════╝${C_RESET}"
}

create_ssh_cli() {
    local is_trial="${1:-0}"
    local user pass days mins ip_limit quota_gb exp_ts exp_disp exp_linux

    if [[ "$is_trial" == "1" ]]; then
        user="trialssh$(shuf -i 100-999 -n 1)"
        pass="123"
        read -rp "  Durasi Trial SSH dalam menit [default: 60]: " mins
        mins="${mins:-60}"
        ip_limit=2
        quota_gb=2
        exp_ts=$(( $(date +%s) + (mins * 60) ))
        exp_disp=$(date -d "@${exp_ts}" '+%Y-%m-%d %H:%M')
        exp_linux=$(date -d "+2 days" '+%Y-%m-%d')
    else
        read -rp "  Masukkan Username SSH baru : " user
        [[ -z "$user" ]] && return
        read -rp "  Masukkan Password SSH      : " pass
        [[ -z "$pass" ]] && pass="12345"
        read -rp "  Masa Aktif (hari) [30]     : " days
        days="${days:-30}"
        read -rp "  Limit IP Login [2]         : " ip_limit
        ip_limit="${ip_limit:-2}"
        read -rp "  Limit Kuota (GB) [50]      : " quota_gb
        quota_gb="${quota_gb:-50}"
        exp_ts=$(( $(date +%s) + (days * 86400) ))
        exp_disp=$(date -d "@${exp_ts}" '+%Y-%m-%d %H:%M')
        exp_linux=$(date -d "@$(( exp_ts + 86400 ))" '+%Y-%m-%d')
    fi

    local exists
    exists=$(sqlite3 "${DB_FILE}" "SELECT COUNT(*) FROM accounts WHERE username='${user}';")
    if [[ "$exists" -gt 0 ]]; then
        echo -e "  ${C_RED}Error: Username '${user}' sudah ada di database!${C_RESET}"
        return
    fi

    # Buat user sistem Linux
    useradd -e "${exp_linux}" -s /bin/false -M "${user}" 2>/dev/null || usermod -e "${exp_linux}" "${user}" 2>/dev/null || true
    echo "${user}:${pass}" | chpasswd 2>/dev/null || true

    # Simpan ke database SQLite agar langsung muncul di Web Panel
    sqlite3 "${DB_FILE}" "INSERT INTO accounts (protocol, username, secret, exp_timestamp, exp_display, is_trial, ip_limit, quota_gb, status) VALUES ('ssh', '${user}', '${pass}', ${exp_ts}, '${exp_disp}', ${is_trial}, ${ip_limit}, ${quota_gb}, 'active');"

    print_ssh_account_Summary "$user" "$pass" "$exp_disp" "$ip_limit" "$quota_gb"
}

renew_ssh_cli() {
    echo -e "  ${C_CYAN}Daftar Akun SSH Terdaftar:${C_RESET}"
    sqlite3 -header -column "${DB_FILE}" "SELECT id, username, exp_display, ip_limit, quota_gb, status FROM accounts WHERE protocol='ssh';"
    echo ""
    read -rp "  Masukkan Username SSH yang akan diperpanjang: " user
    [[ -z "$user" ]] && return
    read -rp "  Tambah masa aktif berapa hari? [30]: " add_days
    add_days="${add_days:-30}"

    local curr_exp
    curr_exp=$(sqlite3 "${DB_FILE}" "SELECT exp_timestamp FROM accounts WHERE username='${user}' AND protocol='ssh';")
    if [[ -z "$curr_exp" ]]; then
        echo -e "  ${C_RED}Akun SSH '${user}' tidak ditemukan.${C_RESET}"
        return
    fi

    local now_ts base_ts new_ts new_disp new_linux
    now_ts=$(date +%s)
    base_ts=$(( curr_exp > now_ts ? curr_exp : now_ts ))
    new_ts=$(( base_ts + (add_days * 86400) ))
    new_disp=$(date -d "@${new_ts}" '+%Y-%m-%d %H:%M')
    new_linux=$(date -d "@$(( new_ts + 86400 ))" '+%Y-%m-%d')

    usermod -e "${new_linux}" -U "${user}" 2>/dev/null || true
    sqlite3 "${DB_FILE}" "UPDATE accounts SET exp_timestamp=${new_ts}, exp_display='${new_disp}', status='active', is_trial=0 WHERE username='${user}' AND protocol='ssh';"
    echo -e "  ${C_GREEN}Akun SSH '${user}' berhasil diperpanjang hingga ${new_disp}!${C_RESET}"
}

delete_ssh_cli() {
    sqlite3 -header -column "${DB_FILE}" "SELECT id, username, exp_display, status FROM accounts WHERE protocol='ssh';"
    echo ""
    read -rp "  Masukkan Username SSH yang akan dihapus: " user
    [[ -z "$user" ]] && return

    pkill -u "$user" 2>/dev/null || true
    userdel -f "$user" 2>/dev/null || true
    sqlite3 "${DB_FILE}" "DELETE FROM accounts WHERE username='${user}' AND protocol='ssh';"
    sqlite3 "${DB_FILE}" "DELETE FROM active_ips WHERE username='${user}' AND protocol='ssh';"
    echo -e "  ${C_GREEN}Akun SSH '${user}' berhasil dihapus dari sistem & Web Panel.${C_RESET}"
}

lock_unlock_ssh_cli() {
    sqlite3 -header -column "${DB_FILE}" "SELECT id, username, status FROM accounts WHERE protocol='ssh';"
    echo ""
    read -rp "  Masukkan Username SSH untuk Lock/Unlock: " user
    [[ -z "$user" ]] && return

    local st
    st=$(sqlite3 "${DB_FILE}" "SELECT status FROM accounts WHERE username='${user}' AND protocol='ssh';")
    if [[ "$st" == "active" ]]; then
        usermod -L "$user" 2>/dev/null || true
        pkill -u "$user" 2>/dev/null || true
        sqlite3 "${DB_FILE}" "UPDATE accounts SET status='locked' WHERE username='${user}' AND protocol='ssh';"
        echo -e "  ${C_YELLOW}Akun '${user}' telah DIKUNCI (Locked).${C_RESET}"
    elif [[ -n "$st" ]]; then
        usermod -U "$user" 2>/dev/null || true
        sqlite3 "${DB_FILE}" "UPDATE accounts SET status='active' WHERE username='${user}' AND protocol='ssh';"
        echo -e "  ${C_GREEN}Akun '${user}' telah DIBUKA (Active).${C_RESET}"
    else
        echo -e "  ${C_RED}Akun tidak ditemukan.${C_RESET}"
    fi
}

check_ssh_login_cli() {
    bash "${INSTALL_DIR}/cli/monitor_ip_quota.sh" --sync-only
    echo ""
    echo -e "${C_CYAN}  [ DAFTAR AKUN SSH & IP CLIENT ASLI YANG SEDANG TERHUBUNG ]${C_RESET}"
    sqlite3 -header -column "${DB_FILE}" "
        SELECT a.username AS Username,
               a.status AS Status,
               a.ip_limit AS Limit_IP,
               COUNT(i.client_ip) AS Login_IP_Count,
                IFNULL(GROUP_CONCAT(i.client_ip, ', '), '-') AS Client_Real_IPs
        FROM accounts a
        LEFT JOIN active_ips i ON a.username = i.username AND a.protocol = i.protocol AND i.last_seen >= (strftime('%s','now') - 300)
        WHERE a.protocol = 'ssh'
        GROUP BY a.username;
    "
    echo ""
}

while true; do
    clear
    echo -e "${C_PURPLE}╔══════════════════════════════════════════════════════════════════════╗${C_RESET}"
    echo -e "${C_PURPLE}║${C_CYAN}           MENU MANAJEMEN SSH & WEBSOCKET (JIBSZ / J1BTNL)            ${C_PURPLE}║${C_RESET}"
    echo -e "${C_PURPLE}╚══════════════════════════════════════════════════════════════════════╝${C_RESET}"
    echo -e "  ${C_YELLOW}[1]${C_WHITE} Buat Akun SSH / WebSocket Baru"
    echo -e "  ${C_YELLOW}[2]${C_WHITE} Buat Akun Trial SSH (Menit)"
    echo -e "  ${C_YELLOW}[3]${C_WHITE} Perpanjang Masa Aktif Akun SSH (Renew)"
    echo -e "  ${C_YELLOW}[4]${C_WHITE} Hapus Akun SSH (Delete)"
    echo -e "  ${C_YELLOW}[5]${C_WHITE} Kunci / Buka Kunci Akun SSH (Lock / Unlock)"
    echo -e "  ${C_YELLOW}[6]${C_WHITE} Cek User Login & IP Client Asli (CF-Connecting-IP)"
    echo -e "  ${C_YELLOW}[0]${C_WHITE} Kembali ke Menu Utama"
    echo -e "${C_PURPLE}────────────────────────────────────────────────────────────────────────${C_RESET}"
    read -rp "  Pilih opsi [0-6]: " opt
    case "$opt" in
        1) create_ssh_cli 0; read -rp "  Tekan Enter untuk lanjut..." ;;
        2) create_ssh_cli 1; read -rp "  Tekan Enter untuk lanjut..." ;;
        3) renew_ssh_cli; read -rp "  Tekan Enter untuk lanjut..." ;;
        4) delete_ssh_cli; read -rp "  Tekan Enter untuk lanjut..." ;;
        5) lock_unlock_ssh_cli; read -rp "  Tekan Enter untuk lanjut..." ;;
        6) check_ssh_login_cli; read -rp "  Tekan Enter untuk lanjut..." ;;
        0) break ;;
        *) ;;
    esac
done
