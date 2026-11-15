# 🚀 Jibsz Tunneling AutoInstall & Web Panel (J1BTNL Edition)

![Platform](https://img.shields.io/badge/OS-Ubuntu_22.04_%7C_Debian_12-00f2fe?style=for-the-badge&logo=linux)
![Mode](https://img.shields.io/badge/Network-VPS_Public_%7C_VPS_NAT_Cloudflare_Tunnel-7b2ff7?style=for-the-badge&logo=cloudflare)
![Protocols](https://img.shields.io/badge/Protocols-SSH_WS_%7C_VMess_%7C_VLESS_%7C_Trojan-10b981?style=for-the-badge)
![Author](https://img.shields.io/badge/Telegram-%40admj1btnl-26A5E4?style=for-the-badge&logo=telegram)

**Jibsz Tunneling / J1BTNL** adalah paket **Autoscript & Web Installer Tunneling Multi-Protokol** modern dengan antarmuka **Web Panel Dark Glassmorphism** serta **Menu Terminal CLI (`menu` / `jibsz`)** yang sinkron secara real-time menggunakan database SQLite terpusat (`/etc/jibsz/jibsz.db`).

Dirancang khusus agar berjalan stabil di **Ubuntu 22.04 LTS (Jammy)** dan **Debian 12 (Bookworm)** (`x86_64`), baik pada **VPS IP Public** maupun **VPS NAT** (menggunakan **Custom Port Web Panel** + **Cloudflare Zero Trust Tunnel Token**).

---

## ✨ Fitur Utama

1. **Dual Arsitektur Jaringan**:
   - **Mode 1 — VPS IP Public**: Nginx mendengarkan langsung di port `80` (HTTP Non-TLS) dan `443` (TLS/SSL Let's Encrypt otomatis via `acme.sh` / Certbot dengan fallback self-signed).
   - **Mode 2 — VPS NAT + Cloudflare Tunnel**: Menginstal service `cloudflared` menggunakan token Zero Trust Anda. Nginx mendengarkan secara eksklusif di **`127.0.0.1:80` (`localhost:80`)** sebagai entry point utama dari Cloudflare Tunnel tanpa bentrok dengan Custom Port Web Panel.
2. **Web Wizard Instalasi Real-Time di Custom Port**:
   - Bootstrap cepat di terminal (`setup.sh`) hanya meminta **Custom Port Web Panel** (misal `8080`, `2052`, atau port NAT forwarded) dan kredensial Admin.
   - Proses instalasi 6 komponen utama (**Nginx Reverse Proxy**, **Cloudflare Tunnel / SSL**, **SSH Tunneling + Dropbear + BadVPN UDPGW**, **VLESS**, **VMess**, **Trojan**) dipantau langsung dari browser dengan live log dan tombol **Retry Komponen Gagal**.
3. **Transisi Otomatis ke Dashboard Manajemen**:
   - Begitu seluruh komponen utama berstatus **Berhasil**, halaman utama otomatis beralih ke **Dashboard Manajemen 3 Menu**:
     - **Menu 1: Dashboard Utama** (OS, Kernel, Uptime, CPU, RAM, Disk, Bandwidth `vnStat`, Status Service + Restart, Ringkasan Akun).
     - **Menu 2: Buat Akun & Manajemen Akun (CRUD)** (SSH/WS, VMess, VLESS, Trojan, Trial menit/jam, Masa Aktif hari, Limit IP, Limit Kuota GB, 1-Click Copy URI `vmess://`, `vless://`, `trojan://`, Payload HTTP Custom/DarkTunnel, & QR Code SVG/Canvas).
     - **Menu 3: Status Akun & Monitoring IP Client Real-Time** (Deteksi IP asli perangkat client via header `CF-Connecting-IP` & `X-Forwarded-For`, pemakaian kuota Upload/Download via Xray Stats API, serta **Auto-Kick / Auto-Lock Multi-Login**).
4. **Sinkronisasi Penuh Web Panel & CLI Terminal**:
   - Ketik `menu` atau `jibsz` di terminal VPS untuk mengakses sub-menu lengkap (`menu-ssh`, `menu-vmess`, `menu-vless`, `menu-trojan`, `menu-system`) yang membaca dan menulis langsung ke database SQLite yang sama dengan Web Panel.

---

## ⚡ One-Liner Command Instalasi (GitHub `mohamadrojib278`)

Jalankan perintah berikut sebagai `root` pada VPS Ubuntu 22.04 LTS atau Debian 12 Anda:

```bash
apt update && apt install -y wget curl git unzip && wget -O setup.sh https://raw.githubusercontent.com/mohamadrojib278/jibsz-tunnel-autoinstall/main/setup.sh && chmod +x setup.sh && bash setup.sh
```

Atau jika Anda meng-clone repositori secara langsung:

```bash
git clone https://github.com/mohamadrojib278/jibsz-tunnel-autoinstall.git && cd jibsz-tunnel-autoinstall && chmod +x setup.sh && ./setup.sh
```

Anda juga dapat langsung menyertakan argumen non-interaktif (Custom Port, Username Admin, Password Admin):

```bash
bash setup.sh --port 8080 --user admin --pass Jibsz2026!
```

---

## ☁️ Panduan Pengaturan Cloudflare Zero Trust Dashboard (Khusus Mode VPS NAT)

Jika Anda menggunakan **VPS NAT** (tanpa IP Public dedicated atau port 80/443 tertutup oleh provider NAT), ikuti langkah berikut di dashboard Cloudflare Zero Trust:

1. Masuk ke **[Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/)** -> pilih menu **Networks** -> **Tunnels**.
2. Klik **Create a tunnel** -> pilih konektor **Cloudflared** -> beri nama tunnel (misalnya `jibsz-nat-tunnel`) -> klik **Save tunnel**.
3. Pada halaman **Install and run a connector**, salin **Tunnel Token** (string panjang yang diawali dengan `eyJhIjoi...`). Token ini yang akan Anda tempelkan pada kolom **Cloudflare Tunnel Token** di Web Wizard Instalasi Jibsz.
4. Klik **Next** untuk masuk ke tab **Public Hostname**, lalu atur seperti berikut:
   - **Subdomain**: Isi subdomain yang diinginkan (misal `tunnel` atau `sg-nat`)
   - **Domain**: Pilih domain Cloudflare Anda (misal `domainanda.com`)
   - **Path**: *(Kosongkan agar menangkap seluruh path `/ssh-ws`, `/vmess`, `/vless`, `/trojan`, dan gRPC)*
   - **Service Type**: Pilih **`HTTP`**
   - **URL**: Isi **`localhost:80`** (sehingga menjadi **`http://localhost:80`**)
5. Klik **Save hostname**.
6. Pastikan di menu Cloudflare Dashboard utama (DNS -> Network) fitur **WebSockets** dan **gRPC** dalam keadaan **ON (Aktif)**.

---

## 🗂️ Arsitektur Routing Internal (`localhost:80` & Custom Port)

| Layanan / Protokol | Path / ServiceName | Port Internal Backend | Entry Point Nginx |
| :--- | :--- | :--- | :--- |
| **Web Panel & Wizard UI** | `/` (FastAPI Web UI) | `0.0.0.0:<CUSTOM_PORT>` | Akses langsung `http://<IP-VPS>:<CUSTOM_PORT>` |
| **Nginx Entry Point (NAT)** | Semua Path Tunneling | `127.0.0.1:80` | Menerima trafik dari `cloudflared` (`CF-Connecting-IP`) |
| **Nginx Entry Point (Public)** | Semua Path Tunneling | `0.0.0.0:80` & `0.0.0.0:443` | Menerima trafik HTTP & TLS langsung |
| **SSH WebSocket Proxy** | `/ssh-ws` atau `/` | `127.0.0.1:10015` | Proxy Python ke Dropbear (`127.0.0.1:109`) / OpenSSH (`22`) |
| **VLESS WebSocket** | `/vless` | `127.0.0.1:10001` | Xray-core Inbound VLESS WS (XUDP aktif) |
| **VMess WebSocket** | `/vmess` | `127.0.0.1:10002` | Xray-core Inbound VMess WS (XUDP aktif) |
| **Trojan WebSocket** | `/trojan` | `127.0.0.1:10003` | Xray-core Inbound Trojan WS |
| **VLESS gRPC** | `vless-grpc` | `127.0.0.1:10004` | Xray-core Inbound VLESS gRPC |
| **VMess gRPC** | `vmess-grpc` | `127.0.0.1:10005` | Xray-core Inbound VMess gRPC |
| **Trojan gRPC** | `trojan-grpc` | `127.0.0.1:10006` | Xray-core Inbound Trojan gRPC |
| **Xray Stats & Handler API** | API gRPC Internal | `127.0.0.1:10085` | Perhitungan kuota per-akun & statistik real-time |
| **BadVPN UDPGW** | UDP Gateway | `127.0.0.1:7300` | Mendukung panggilan suara/video & game UDP di SSH |

---

## 🖥️ Daftar Perintah CLI Terminal

Setelah proses bootstrap selesai, Anda dapat mengetik perintah berikut kapan saja di terminal SSH VPS:

- `menu` atau `jibsz` : Membuka menu interaktif utama Jibsz Tunneling.
- `menu-ssh` : Buat akun SSH/WS, Trial SSH, Renew, Hapus, Lock/Unlock, Cek User Login & IP Client.
- `menu-vmess` : Buat akun VMess, Trial, Renew, Hapus, Cek User Login & IP Client, Cek Kuota.
- `menu-vless` : Buat akun VLESS, Trial, Renew, Hapus, Cek User Login & IP Client, Cek Kuota.
- `menu-trojan` : Buat akun Trojan, Trial, Renew, Hapus, Cek User Login & IP Client, Cek Kuota.
- `menu-system` : Ganti Domain, Update Token Cloudflare Tunnel, Ganti Custom Port Web Panel, Restart Semua Service, Auto-Delete Expired Accounts, Backup & Restore Akun.

---

## 📁 Struktur Direktori Proyek

```text
jibsz-tunnel-autoinstall/
├── README.md                  # Dokumentasi lengkap & one-liner command install dari GitHub
├── setup.sh                   # Script utama bootstrapper & installer awal
├── backend/
│   ├── installer_engine.sh    # Script modular instalasi SSH, Xray (VMess/VLESS/Trojan), Nginx, Cloudflared
│   ├── nginx_nat.conf         # Template Nginx listen 127.0.0.1:80 (real_ip_header CF-Connecting-IP)
│   ├── nginx_public.conf      # Template Nginx listen 80 & 443 SSL
│   ├── xray_config.json       # Template Xray-core multi-protocol + API Stats untuk kuota & IP tracking
│   └── ssh_ws_proxy.py        # Python WebSocket-to-SSH/Dropbear proxy (mendukung header CF-Connecting-IP)
├── webpanel/
│   ├── app.py                 # Backend Web Panel (FastAPI/Flask) untuk Wizard Instalasi & Dashboard
│   ├── requirements.txt       # Daftar package Python
│   ├── static/                # CSS/JS (Dark Glassmorphism UI)
│   │   ├── style.css
│   │   └── app.js
│   └── templates/
│       ├── install.html       # Halaman pertama: Pilih Mode (Public/NAT CF Token) + Status Instalasi
│       └── dashboard.html     # Halaman utama pasca-instalasi: Dashboard, Buat Akun, Status Akun & IP Client
└── cli/
    ├── menu.sh                # Menu utama terminal CLI
    ├── manage_ssh.sh          # Modul manajemen SSH CLI
    ├── manage_xray.sh         # Modul manajemen VMess, VLESS, Trojan CLI
    └── monitor_ip_quota.sh    # Daemon/cron pengecekan IP client aktif, kuota Xray API, & auto-expired
```

---

## 👤 Kredit & Kontributor

- **Developer / Branding**: **Jibsz Tunneling / J1BTNL**
- **GitHub Repository**: [`github.com/mohamadrojib278`](https://github.com/mohamadrojib278)
- **Telegram Contact**: [`@admj1btnl`](https://t.me/admj1btnl)
