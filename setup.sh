#!/bin/bash
# ==========================================================================
# JIBSZ TUNNELING BOOTSTRAPPER — UBUNTU 22.04 & DEBIAN 12
# Credit Telegram: @admj1btnl
# ==========================================================================
set -e

if [ "$(id -u)" != "0" ]; then
  echo "[ERROR] Script ini harus dijalankan sebagai root (sudo su)!"
  exit 1
fi

echo "============================================================"
echo "   JIBSZ TUNNELING — WEB INSTALLER BOOTSTRAPPER"
echo "   Support: Ubuntu 22.04 LTS & Debian 12 (Bookworm)"
echo "   Telegram: @admj1btnl"
echo "============================================================"

# Fix DNS Resolver agar apt dan git tidak gagal di VPS NAT
chattr -i /etc/resolv.conf 2>/dev/null || true
cat <<EOF > /etc/resolv.conf
nameserver 1.1.1.1
nameserver 8.8.8.8
EOF

read -p "Masukkan Custom Port untuk Halaman Web Installer/Panel [default: 8488]: " PANEL_PORT
PANEL_PORT=${PANEL_PORT:-8488}

apt-get update -y
apt-get install -y python3 python3-pip python3-venv curl wget jq unzip net-tools lsof cron

mkdir -p /etc/jibsz-tunnel /opt/jibsz-tunnel/webpanel/templates /opt/jibsz-tunnel/backend /var/log/jibsz-tunnel
echo "${PANEL_PORT}" > /etc/jibsz-tunnel/panel_port.conf

cp -r webpanel/* /opt/jibsz-tunnel/webpanel/ 2>/dev/null || true
cp -r backend/* /opt/jibsz-tunnel/backend/ 2>/dev/null || true
cp cli/menu.sh /usr/local/bin/menu 2>/dev/null || true
chmod +x /usr/local/bin/menu /opt/jibsz-tunnel/backend/*.sh 2>/dev/null || true

pip3 install --break-system-packages flask >/dev/null 2>&1 || pip3 install flask >/dev/null 2>&1

cat <<EOF > /etc/systemd/system/jibsz-webpanel.service
[Unit]
Description=Jibsz Tunneling Web Installer & Dashboard Panel
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/jibsz-tunnel/webpanel
ExecStart=/usr/bin/python3 /opt/jibsz-tunnel/webpanel/app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable jibsz-webpanel
systemctl restart jibsz-webpanel

VPS_IP=$(curl -s4 ifconfig.me || hostname -I | awk '{print $1}')
echo ""
echo "============================================================"
echo " [BERHASIL] Halaman Web Installer telah aktif!"
echo " Silakan buka URL berikut di browser untuk mulai instalasi:"
echo " -> http://${VPS_IP}:${PANEL_PORT}"
echo "============================================================"
