# Jibsz Tunneling Autoscript & Web Installer (VPS Public & VPS NAT Cloudflare Tunnel)

Paket instalasi lengkap **SSH WebSocket, VLESS, VMess, dan Trojan** dengan **Web Installer Wizard di Custom Port** serta **Dashboard Manajemen & Monitoring IP Client Real-Time**.
Kompatibel dengan **Ubuntu 22.04 LTS** dan **Debian 12 (Bookworm)**.

- **Author / Brand**: Jibsz Tunneling (`J1BTNL`)
- **Telegram**: [@admj1btnl](https://t.me/admj1btnl)

## Fitur Utama
1. **Bootstrap Web Installer di Custom Port**:
   - Pertama kali diinstal, script membuka halaman web di **Custom Port** pilihan Anda (`http://IP-VPS:PORT`) untuk memulai instalasi tunneling.
2. **Dual Mode (VPS Public & VPS NAT Cloudflare Tunnel)**:
   - **Mode VPS NAT**: Menggunakan Token Cloudflare Tunnel yang diarahkan ke `http://localhost:80` (Nginx internal meneruskan `CF-Connecting-IP` agar IP asli client terbaca).
   - **Mode VPS IP Public**: Menggunakan Nginx direct port `80` & `443` dengan SSL Let's Encrypt otomatis.
3. **Indikator Status Instalasi Per Layanan**:
   - Menampilkan status **Berhasil / Gagal** secara terpisah untuk **SSH, VLESS, VMess, dan Trojan** beserta tombol **Retry**.
4. **Transisi Otomatis ke Dashboard Utama**:
   - Setelah keempat protokol berhasil diinstal, halaman utama otomatis berubah menjadi:
     - **Menu Dashboard** (Status sistem, RAM/CPU, Bandwidth, Status Service)
     - **Menu Buat Akun** (Generate akun SSH WS, VLESS, VMess, Trojan + Link URI & Payload)
     - **Menu Status Akun & IP Client** (Monitoring akun yang sedang digunakan, kuota, dan daftar IP asli client yang sedang login)
5. **Full Menu CLI (`menu`)**:
   - Ketik `menu` di terminal VPS untuk mengelola akun dan server lewat SSH.

## Cara Upload ke GitHub & Instalasi di VPS

1. Ekstrak file `jibsz-tunnel-autoinstall.zip` dan upload seluruh isinya ke repositori GitHub Anda (contoh: `https://github.com/mohamadrojib278/jibsz-tunnel-autoinstall`).
2. Jalankan perintah instalasi berikut di VPS Ubuntu 22.04 atau Debian 12 (sebagai `root`):

```bash
apt update && apt install -y curl wget unzip && wget -O setup.sh https://raw.githubusercontent.com/mohamadrojib278/jibsz-tunnel-autoinstall/main/setup.sh && chmod +x setup.sh && ./setup.sh
```

## Pengaturan Cloudflare Zero Trust (Khusus VPS NAT)
1. Buka dashboard **Cloudflare Zero Trust** -> **Networks** -> **Tunnels**.
2. Buat tunnel baru (`Cloudflared`), lalu salin **Token Tunnel** (`eyJhIjoi...`) ke halaman Web Installer Anda.
3. Pada tab **Public Hostname**, tambahkan domain/subdomain Anda dan arahkan ke:
   - **Service Type**: `HTTP`
   - **URL**: `localhost:80`
