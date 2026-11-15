#!/bin/bash
clear
DOMAIN=$(cat /etc/jibsz-tunnel/domain.conf 2>/dev/null || echo "tun.jibfza.my.id")
MODE=$(cat /etc/jibsz-tunnel/mode.conf 2>/dev/null || echo "nat")
PORT=$(cat /etc/jibsz-tunnel/panel_port.conf 2>/dev/null || echo "8488")
echo "============================================================"
echo "   JIBSZ TUNNELING CLI MENU — UBUNTU 22.04 & DEBIAN 12"
echo "   Domain : ${DOMAIN} | Mode : ${MODE} | Web Panel : :${PORT}"
echo "   Telegram : @admj1btnl"
echo "============================================================"
echo " [1] Buat Akun SSH WebSocket"
echo " [2] Buat Akun Xray VLESS"
echo " [3] Buat Akun Xray VMess"
echo " [4] Buat Akun Xray Trojan"
echo " [5] Cek Status Akun & IP Client Online"
echo " [6] Update Token Cloudflare Tunnel (http://localhost:80)"
echo " [7] Restart Semua Service Tunneling"
echo " [0] Keluar"
echo "============================================================"
read -p "Pilih menu [0-7]: " opt
case $opt in
  5)
    echo "--- Daftar IP Client Aktif (CF-Connecting-IP) ---"
    tail -n 25 /var/log/jibsz-tunnel/nginx_access.log 2>/dev/null || echo "Belum ada log trafik."
    ;;
  7)
    systemctl restart nginx xray dropbear cloudflared jibsz-webpanel 2>/dev/null || true
    echo "[OK] Semua service berhasil di-restart."
    ;;
  *)
    echo "Gunakan Web Panel di port :${PORT} untuk manajemen visual penuh."
    ;;
esac
