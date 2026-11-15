# 🚀 Jibsz Tunneling AutoInstall & Mobile-First Public Web Panel (J1BTNL Edition)

![Platform](https://img.shields.io/badge/OS-Ubuntu_22.04_%7C_Debian_12-00f2fe?style=for-the-badge&logo=linux)
![Mode](https://img.shields.io/badge/Network-VPS_Public_%7C_VPS_NAT_Cloudflare_Tunnel-7b2ff7?style=for-the-badge&logo=cloudflare)
![Access](https://img.shields.io/badge/Web_Panel-Public_No_Login_%7C_CLI_Only_Delete-10b981?style=for-the-badge)
![Author](https://img.shields.io/badge/Telegram-%40admj1btnl-26A5E4?style=for-the-badge&logo=telegram)

**Jibsz Tunneling / J1BTNL** adalah paket **Autoscript & Web Installer Tunneling Multi-Protokol** dengan tampilan **Mobile-First Dark Glassmorphism** (pas di layar HP Android maupun Desktop) serta **Menu Terminal CLI (`menu` / `jibsz`)** yang sinkron secara real-time menggunakan database SQLite terpusat (`/etc/jibsz/jibsz.db`).

---

## ✨ Fitur Unggulan (Update v2.7 — Mobile Android & Public Dashboard)

1. **Desain Responsif Pas di Android / Mobile**:
   - Dilengkapi **Bottom Navigation App Bar** khas aplikasi Android untuk berpindah antar 3 menu utama dengan satu jempol.
   - Tabel data otomatis berubah menjadi **Mobile Stacked Cards** pada layar HP sehingga tidak perlu menggeser tabel ke kanan/kiri.
2. **Akses Publik Tanpa Login & Proteksi Hapus Akun Khusus CLI**:
   - Halaman utama (`http://<IP-VPS>:<CUSTOM_PORT>`) dapat diakses langsung oleh semua orang **tanpa memerlukan username/password login**.
   - Semua pengguna dapat **membuat akun baru** (SSH WS, VMess, VLESS, Trojan, maupun Trial), menyalin link URI/payload 1-klik, memindai QR Code, memperpanjang masa aktif, serta **memantau seluruh proses, status service, pemakaian kuota, dan IP client aktif** di Dashboard Utama.
   - **Proteksi Keamanan**: Tombol dan API penghapusan akun yang sudah ada **dinonaktifkan sepenuhnya di Web Panel** (`HTTP 403 Forbidden`). Penghapusan akun hanya dapat dilakukan oleh pemilik server melalui **Terminal CLI** (`menu`, `menu-ssh`, `menu-vmess`, `menu-vless`, `menu-trojan`).
3. **Dual Arsitektur Jaringan (VPS IP Public & VPS NAT Cloudflare Tunnel)**:
   - **Mode 1 — VPS IP Public**: Nginx mendengarkan langsung di port `80` (HTTP Non-TLS) dan `443` (TLS/SSL Let's Encrypt otomatis via `acme.sh` dengan fallback self-signed).
   - **Mode 2 — VPS NAT + Cloudflare Tunnel**: Menginstal service `cloudflared` menggunakan token Zero Trust Anda. Nginx mendengarkan di **`127.0.0.1:80` (`localhost:80`)** dan membaca header `CF-Connecting-IP` agar IP asli perangkat client tampil akurat di panel.

---

## ⚡ One-Liner Command Instalasi (GitHub `mohamadrojib278`)

Jalankan perintah berikut sebagai `root` pada VPS Ubuntu 22.04 LTS atau Debian 12 Anda:

```bash
apt update && apt install -y wget curl git unzip && wget -O setup.sh https://raw.githubusercontent.com/mohamadrojib278/jibsz-tunnel-autoinstall/main/setup.sh && chmod +x setup.sh && bash setup.sh
```

Atau langsung menentukan Custom Port Web Panel tanpa prompt interaktif:

```bash
bash setup.sh --port 8080
```

---

## ☁️ Panduan Pengaturan Cloudflare Zero Trust Dashboard (Khusus Mode VPS NAT)

1. Masuk ke **[Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/)** -> pilih **Networks** -> **Tunnels**.
2. Klik **Create a tunnel** -> pilih **Cloudflared** -> beri nama tunnel -> klik **Save tunnel**.
3. Salin **Tunnel Token** (`eyJhIjoi...`) lalu tempelkan pada kolom **Cloudflare Tunnel Token** di Web Wizard Instalasi Jibsz.
4. Pada tab **Public Hostname**, atur:
   - **Subdomain & Domain**: Sesuai domain Cloudflare Anda (misal `sg-nat.domainanda.com`)
   - **Service Type**: **`HTTP`**
   - **URL**: **`localhost:80`** (`http://localhost:80`)
5. Pastikan fitur **WebSockets** dan **gRPC** di dashboard Cloudflare DNS -> Network dalam keadaan **ON**.

---

## 🖥️ Daftar Perintah CLI Terminal (Termasuk Hapus Akun)

Ketik perintah berikut di terminal SSH VPS Anda:

- `menu` atau `jibsz` : Membuka menu utama Jibsz Tunneling.
- `menu-ssh` : Buat akun SSH/WS, Trial, Renew, **Hapus Akun SSH**, Lock/Unlock, Cek IP Client.
- `menu-vmess` : Buat akun VMess, Trial, Renew, **Hapus Akun VMess**, Cek IP Client & Kuota.
- `menu-vless` : Buat akun VLESS, Trial, Renew, **Hapus Akun VLESS**, Cek IP Client & Kuota.
- `menu-trojan` : Buat akun Trojan, Trial, Renew, **Hapus Akun Trojan**, Cek IP Client & Kuota.
- `menu-system` : Ganti Domain, Update Token Cloudflare Tunnel, Ganti Port Web Panel, Restart Service, Backup & Restore.
