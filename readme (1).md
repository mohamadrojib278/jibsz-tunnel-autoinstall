&lt;div align=&quot;center&quot;&gt;

&lt;!-- Animated Cyber Wave Header --&gt;
&lt;img width=&quot;100%&quot; src=&quot;https://capsule-render.vercel.app/api?type=waving&amp;color=0:040711,45:0ea5e9,100:a855f7&amp;height=220&amp;section=header&amp;text=JIBSZ%20TUNNELS&amp;fontSize=58&amp;fontColor=ffffff&amp;animation=twinkling&amp;fontAlignY=38&amp;desc=J1BTNL%20Multi-Protocol%20Tunneling%20%E2%80%A2%20Web%20Panel%20V4.9%20%E2%80%A2%20VPS%20%26%20Railway&amp;descAlignY=60&amp;descSize=16&quot; alt=&quot;Jibsz Tunnels Header&quot; /&gt;

&lt;!-- Animated Typing Subtitle --&gt;
&lt;a href=&quot;https://github.com/mohamadrojib278/jibsz-tunnel-autoinstall&quot;&gt;
  &lt;img src=&quot;https://readme-typing-svg.demolab.com?font=JetBrains+Mono&amp;weight=700&amp;size=20&amp;duration=2600&amp;pause=900&amp;color=00F2FE&amp;center=true&amp;vCenter=true&amp;width=760&amp;lines=SSH+WebSocket+%E2%80%A2+VLESS+%E2%80%A2+VMess+%E2%80%A2+Trojan;Public+Read-Only+Panel+%2B+Admin+Login+Control;VPS+IP+Public+%E2%80%A2+VPS+NAT+Cloudflare+%E2%80%A2+Railway+Docker;Auto-Block+Device+%26+Kuota+%E2%80%A2+Long-Term+Stability&quot; alt=&quot;Jibsz Tunnels Typing Animation&quot; /&gt;
&lt;/a&gt;

<br/>







&lt;p&gt;
  &lt;strong&gt;Jibsz Tunnels (J1BTNL Edition)&lt;/strong&gt; adalah paket &lt;b&gt;Autoscript Tunneling Multi-Protokol&lt;/b&gt;, &lt;b&gt;Web Panel Mobile-First&lt;/b&gt; dengan akses publik read-only + login admin, serta dukungan penuh &lt;b&gt;VPS IP Public&lt;/b&gt;, &lt;b&gt;VPS NAT (Cloudflare Zero Trust)&lt;/b&gt;, dan &lt;b&gt;Railway Docker Single-Port&lt;/b&gt;.
&lt;/p&gt;

&lt;/div&gt;

## ✨ Fitur Unggulan

- **Web Panel Publik + Login Admin:** Semua orang dapat membuka panel tanpa login untuk melihat **Dashboard**, **Buat Akun**, dan **Sistem**, sementara seluruh perubahan sensitif terkunci khusus untuk **Admin**.
- **Hostname Dinamis Otomatis:** Badge hostname di pojok kanan atas otomatis mengikuti domain atau IP yang sedang dibuka di browser, lengkap dengan salin 1-klik.
- **Auto-Block Device & Kuota Real-Time:** Memblokir akun otomatis (Xray & Linux SSH) saat jumlah IP/perangkat aktif melewati `Devices Limit` atau pemakaian trafik mencapai `Quota GB`.
- **Stabilitas Jangka Panjang (Anti-Lemot & Anti-Lockout):** Pembacaan log hemat RAM (`tail` byte-seek), `logrotate` + auto-truncate 10 MB, `RotatingFileHandler`, `flock` + `timeout` pada cron, `asyncio.to_thread` non-blocking, proteksi `OOMScoreAdjust=-1000` untuk `sshd`, dan pembuatan Swap 1 GB otomatis untuk VPS RAM kecil.
- **Fleksibel Versi Core:** Mendukung **Xray-core `v26.11.9`** (default) dengan opsi rollback 1-perintah ke **`v1.8.24` LTS** untuk kompatibilitas maksimal DarkTunnel & HTTP Custom, plus auto-upgrade **OpenSSH & Dropbear** resmi distro.
- **Database Terpusat & CLI Sinkron:** Menggunakan SQLite WAL (`/etc/jibsz/jibsz.db`) yang sinkron real-time antara Web Panel dan menu terminal CLI (`menu` / `jibsz`).

## 🔐 Matriks Hak Akses (Publik vs Admin)

| Fitur / Menu | Publik (Tanpa Login) | Admin (Login) |
| :--- | :---: | :---: |
| **Dashboard** (Statistik, Traffic, Daftar Akun, Copy Config) | ✅ Akses Penuh | ✅ Akses Penuh |
| **Buat Akun** (SSH WS, VLESS, VMess, Trojan) | ✅ Limit Default Server | ✅ Bebas Atur Limit |
| **Sistem** (CPU, RAM, Disk, Status Service) | ✅ Read-Only | ✅ + Restart Service |
| **Ubah Limit Device & Limit Kuota** (Edit Rules) | ❌ Diblokir (`403`) | ✅ Akses Penuh |
| **Renew & Reset Usage Akun** | ❌ Diblokir (`403`) | ✅ Akses Penuh |
| **Hapus Akun dari Web Panel** | ❌ Diblokir (`403`) | ✅ Akses Penuh |
| **Log Server Real-Time & Clear Log** | ❌ Tersembunyi (`403`) | ✅ Akses Penuh |
| **Setting Banner SSH, Default Limit, Backup/Restore, Ganti Password** | ❌ Tersembunyi (`403`) | ✅ Akses Penuh |

> **Kredensial Admin Bawaan:** Username `admin` | Password `jibsz123` (segera ubah melalui menu **Setting & Backup** setelah login).

## 🌐 Arsitektur Protokol & Routing Path

| Protokol | Transport | Path / Service | Port Internal | Keterangan |
| :--- | :--- | :--- | :---: | :--- |
| **Web Panel** | HTTP / HTTPS | `/` | `8080` / `8081` | FastAPI + Uvicorn |
| **SSH WebSocket** | WS / WSS | `/ssh-ws` | `10015` → `109` / `22` | Dropbear & OpenSSH |
| **VLESS** | WS / gRPC | `/vless` / `vless-grpc` | `10001` / `10004` | Xray-core |
| **VMess** | WS / gRPC | `/vmess` / `vmess-grpc` | `10002` / `10005` | Xray-core |
| **Trojan** | WS / gRPC | `/trojan` / `trojan-grpc` | `10003` / `10006` | Xray-core |

## ⚡ Instalasi di VPS (Ubuntu 22.04 / Debian 12)

Jalankan perintah berikut sebagai `root` pada VPS IP Public atau VPS NAT:

```bash
apt update && apt install -y wget curl git unzip && wget -O setup.sh https://raw.githubusercontent.com/mohamadrojib278/jibsz-tunnel-autoinstall/main/setup.sh && chmod +x setup.sh && bash setup.sh
```

**Opsi Custom Port & Pilih Versi Xray-core:**

```bash
# Menentukan port web panel khusus (misal untuk VPS NAT)
bash setup.sh --port 8080

# Rollback atau pilih Xray-core v1.8.24 LTS (kompatibilitas DarkTunnel / HTTP Custom)
bash setup.sh --xray-version v1.8.24
```

## ☁️ Pengaturan VPS NAT (Cloudflare Zero Trust)

1. Buka **Cloudflare Zero Trust Dashboard** → **Networks** → **Tunnels** → **Create a tunnel**.
2. Salin **Tunnel Token** (`eyJhIjoi...`) ke Web Wizard instalasi Jibsz saat pertama kali dibuka.
3. Pada tab **Public Hostname**, arahkan domain/subdomain kamu ke Service Type **`HTTP`** dengan URL **`localhost:80`**.
4. Pastikan fitur **WebSockets** dan **gRPC** di menu Cloudflare **DNS → Network** berstatus **ON**.

## 🚂 Deploy ke Railway (Docker Single-Port)

Versi Railway menjalankan **Web Panel + VLESS WS + VMess WS + Trojan WS + SSH-WS** sekaligus dalam satu port `$PORT` tanpa memerlukan `systemd`.

1. Upload isi folder `jibsz-tunnel-railway/` ke repositori GitHub kamu.
2. Di dashboard **Railway**, pilih **New Project → Deploy from GitHub Repo** (`Dockerfile` & `railway.json` otomatis terdeteksi).
3. Masuk ke **Settings → Networking → Generate Domain** (atau tambahkan Custom Domain).
4. Masuk ke **Volumes → Add Volume** dengan Mount Path **`/data`** agar database akun dan pengaturan tidak hilang saat redeploy.

| Environment Variable | Default | Fungsi |
| :--- | :--- | :--- |
| `ADMIN_USER` | `admin` | Username login admin Web Panel |
| `ADMIN_PASS` | `jibsz123` | Password login admin Web Panel |
| `PANEL_DOMAIN` | `RAILWAY_PUBLIC_DOMAIN` | Custom domain opsional untuk config akun |
| `XRAY_VERSION` *(Build Arg)* | `v26.11.9` | Versi Xray-core (bisa diubah ke `v1.8.24`) |

## 🖥️ Perintah Terminal CLI (VPS)

| Perintah | Fungsi |
| :--- | :--- |
| `menu` atau `jibsz` | Membuka menu utama manajemen server & monitoring |
| `menu-ssh` | Kelola akun SSH WebSocket |
| `menu-vless` / `menu-vmess` / `menu-trojan` | Kelola akun Xray per protokol |
| `menu-autodel` | Konfigurasi & jalankan Auto-Delete akun expired/idle |

&lt;div align=&quot;center&quot;&gt;

&lt;!-- Animated Wave Footer --&gt;
&lt;img width=&quot;100%&quot; src=&quot;https://capsule-render.vercel.app/api?type=waving&amp;color=0:a855f7,55:0ea5e9,100:040711&amp;height=120&amp;section=footer&quot; alt=&quot;Jibsz Tunnels Footer&quot; /&gt;

**Built with ⚡ by [Jibsz Tunnels (J1BTNL)](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Fmohamadrojib278)** • Contact Telegram: **[@admj1btnl](https://www.google.com/search?q=https%3A%2F%2Ft.me%2Fadmj1btnl)**

&lt;/div&gt;
