#!/bin/bash
# ==========================================================================
# JIBSZ TUNNELING MODULAR INSTALLER ENGINE (SSH, VLESS, VMESS, TROJAN)
# ==========================================================================
MODE=$1        # "nat" or "public"
DOMAIN=$2
CF_TOKEN=$3

mkdir -p /etc/jibsz-tunnel /var/log/jibsz-tunnel
echo "${DOMAIN}" > /etc/jibsz-tunnel/domain.conf
echo "${MODE}" > /etc/jibsz-tunnel/mode.conf

# 1. Install Nginx & Configure localhost:80 (NAT) or 80/443 (Public)
apt-get install -y nginx dropbear
if [ "${MODE}" = "nat" ]; then
  cp /opt/jibsz-tunnel/backend/nginx_nat.conf /etc/nginx/conf.d/jibsz.conf
  rm -f /etc/nginx/sites-enabled/default
  systemctl restart nginx

  # Install Cloudflared Tunnel -> http://localhost:80
  curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
  echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" | tee /etc/apt/sources.list.d/cloudflared.list
  apt-get update && apt-get install -y cloudflared
  cloudflared service uninstall 2>/dev/null || true
  cloudflared service install "${CF_TOKEN}"
  systemctl restart cloudflared
else
  sed "s/DOMAIN_PLACEHOLDER/${DOMAIN}/g" /opt/jibsz-tunnel/backend/nginx_public.conf > /etc/nginx/conf.d/jibsz.conf
  rm -f /etc/nginx/sites-enabled/default
  systemctl restart nginx
fi

# 2. Configure Dropbear & SSH WebSocket (:2082)
sed -i 's/NO_START=1/NO_START=0/g' /etc/default/dropbear 2>/dev/null || true
sed -i 's/DROPBEAR_PORT=22/DROPBEAR_PORT=143/g' /etc/default/dropbear 2>/dev/null || true
systemctl restart dropbear

# 3. Install Xray-Core (VLESS, VMess, Trojan)
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install
cp /opt/jibsz-tunnel/backend/xray_config.json /usr/local/etc/xray/config.json
systemctl restart xray

touch /etc/jibsz-tunnel/installed.lock
echo "ALL_PROTOCOLS_INSTALLED=1" > /etc/jibsz-tunnel/installed.lock
