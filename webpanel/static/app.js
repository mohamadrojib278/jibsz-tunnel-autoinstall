/* ============================================================================
   JIBSZ TUNNELING / J1BTNL - FRONTEND CONTROLLER V3.0 (app.js)
   Fitur: - Generator Config Bug Host / Bug SNI & Wildcard (SSH, VLESS, VMess, Trojan)
          - Tombol 1-Click Unlock & Reset IP untuk akun yang ke-lock limit IP
          - 5 Menu Kiri Atas (Dashboard, Buat Akun, Log Server, Sistem, Setting)
   ============================================================================ */

let pollInterval = null;
let selectedMode = "public";
window.accountsCache = {};

function toggleDrawer(forceState) {
  const drawer = document.getElementById("sidebar-drawer");
  const backdrop = document.getElementById("drawer-backdrop");
  if (!drawer || !backdrop) return;

  const isOpen = typeof forceState === "boolean" ? forceState : !drawer.classList.contains("open");
  if (isOpen) {
    drawer.classList.add("open");
    backdrop.classList.add("open");
  } else {
    drawer.classList.remove("open");
    backdrop.classList.remove("open");
  }
}

function copyText(text, label = "Teks") {
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    showToast(`${label} disalin!`);
  }).catch(() => {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    showToast(`${label} disalin!`);
  });
}

function showToast(msg) {
  let toast = document.getElementById("jibsz-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "jibsz-toast";
    toast.style.cssText =
      "position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:linear-gradient(135deg,#00f2fe,#a855f7);" +
      "color:#060912;font-weight:700;font-size:0.8rem;padding:8px 16px;border-radius:999px;z-index:9999;" +
      "box-shadow:0 6px 20px rgba(0,0,0,0.6);max-width:90vw;text-align:center;";
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.style.display = "block";
  setTimeout(() => {
    toast.style.display = "none";
  }, 2400);
}

function formatBytes(bytes) {
  const b = Number(bytes || 0);
  if (b < 1024) return `${b} B`;
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 ** 3) return `${(b / (1024 ** 2)).toFixed(2)} MB`;
  return `${(b / (1024 ** 3)).toFixed(2)} GB`;
}

/* ============================================================================
   WIZARD INSTALASI
   ============================================================================ */
function selectInstallMode(mode) {
  selectedMode = mode;
  const cardPub = document.getElementById("mode-card-public");
  const cardNat = document.getElementById("mode-card-nat");
  const groupEmail = document.getElementById("group-email");
  const groupCfToken = document.getElementById("group-cf-token");
  const hintBox = document.getElementById("nat-hint-box");
  if (!cardPub || !cardNat) return;

  if (mode === "nat") {
    cardNat.classList.add("selected");
    cardPub.classList.remove("selected");
    groupEmail.style.display = "none";
    groupCfToken.style.display = "block";
    hintBox.style.display = "block";
  } else {
    cardPub.classList.add("selected");
    cardNat.classList.remove("selected");
    groupEmail.style.display = "block";
    groupCfToken.style.display = "none";
    hintBox.style.display = "none";
  }
}

async function startWizardInstallation() {
  const domain = document.getElementById("input-domain").value.trim();
  const email = document.getElementById("input-email").value.trim();
  const cfToken = document.getElementById("input-cf-token").value.trim();

  if (!domain) {
    alert("Masukkan Domain / Subdomain terlebih dahulu!");
    return;
  }
  if (selectedMode === "nat" && !cfToken) {
    alert("Masukkan Cloudflare Tunnel Token (eyJhIjoi...) untuk mode VPS NAT!");
    return;
  }

  const btn = document.getElementById("btn-start-install");
  btn.disabled = true;
  btn.textContent = "⏳ Memulai Instalasi...";

  try {
    const res = await fetch("/api/install/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: selectedMode, domain, email, cf_token: cfToken }),
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "Gagal memulai instalasi.");
      btn.disabled = false;
      btn.textContent = "🚀 Mulai Instalasi Sekarang";
      return;
    }
    showToast("Instalasi berjalan di background!");
    pollInstallationProgress();
    if (!pollInterval) pollInterval = setInterval(pollInstallationProgress, 2000);
  } catch (err) {
    alert("Kesalahan koneksi: " + err);
    btn.disabled = false;
  }
}

async function retrySingleComponent(compId) {
  showToast(`Retry komponen: ${compId}...`);
  await fetch("/api/install/retry", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ component_id: compId }),
  });
  pollInstallationProgress();
}

function mapStatusBadge(status) {
  const s = (status || "pending").toLowerCase();
  if (s === "success") return `<span class="badge badge-success">Berhasil</span>`;
  if (s === "installing") return `<span class="badge badge-installing">Installing</span>`;
  if (s === "failed") return `<span class="badge badge-failed">Gagal</span>`;
  return `<span class="badge badge-pending">Pending</span>`;
}

async function pollInstallationProgress() {
  const container = document.getElementById("components-list");
  if (!container) return;

  try {
    const res = await fetch("/api/install/status");
    const data = await res.json();

    container.innerHTML = data.components.map((c, idx) => {
      const retryBtn = c.status === "failed"
        ? `<button class="btn btn-warning btn-sm" onclick="retrySingleComponent('${c.component_id}')">🔄 Retry</button>`
        : "";
      return `
        <div class="component-item">
          <div class="component-info">
            <h4>${idx + 1}. ${c.name}</h4>
            <p>${c.message || ""}</p>
          </div>
          <div style="display:flex;align-items:center;gap:6px;">
            ${mapStatusBadge(c.status)}
            ${retryBtn}
          </div>
        </div>
      `;
    }).join("");

    const hasFailed = data.components.some(c => c.status === "failed");
    const retryAllBtn = document.getElementById("btn-retry-all-failed");
    if (retryAllBtn) retryAllBtn.style.display = hasFailed ? "inline-flex" : "none";

    const logBox = document.getElementById("install-log-box");
    if (logBox && data.logs) {
      logBox.textContent = data.logs;
      logBox.scrollTop = logBox.scrollHeight;
    }

    if (data.is_installed) {
      window.location.href = "/dashboard";
    }
  } catch (e) {
    console.error("Polling error:", e);
  }
}

/* ============================================================================
   NAVIGASI MENU KIRI ATAS (5 MENU UTAMA V3)
   ============================================================================ */
function switchMenuV2(menuId, titleText) {
  document.querySelectorAll(".tab-pane").forEach(el => {
    el.style.display = "none";
  });
  document.querySelectorAll(".drawer-item").forEach(el => {
    el.classList.remove("active");
  });

  const pane = document.getElementById(`pane-${menuId}`);
  const navBtn = document.getElementById(`nav-${menuId}`);
  const headerTitle = document.getElementById("active-menu-title");

  if (pane) pane.style.display = "block";
  if (navBtn) navBtn.classList.add("active");
  if (headerTitle && titleText) headerTitle.textContent = titleText;

  toggleDrawer(false);
  window.scrollTo({ top: 0, behavior: "smooth" });

  if (menuId === "dashboard") {
    loadOverviewAndSystem();
    loadDashboardUserStats();
  } else if (menuId === "create") {
    loadAccountsSimpleList();
  } else if (menuId === "logs") {
    loadServerLogs();
  } else if (menuId === "system") {
    loadOverviewAndSystem();
  } else if (menuId === "settings") {
    loadBannerAndBackups();
  }
}

/* ============================================================================
   DATA LOADER: OVERVIEW, USER STATS, NETWORK USAGE, & SYSTEM RESOURCE
   ============================================================================ */
async function loadOverviewAndSystem() {
  try {
    const res = await fetch("/api/system/overview");
    const data = await res.json();
    const s = data.system;
    const n = data.network;
    const c = data.account_counts;

    const elTotalAcc = document.getElementById("stat-total-acc");
    if (elTotalAcc) {
      elTotalAcc.textContent = `${data.total_accounts} Akun`;
      document.getElementById("stat-online-ip").textContent = `${data.online_ips} IP Online`;
      document.getElementById("cnt-ssh").textContent = c.ssh || 0;
      document.getElementById("cnt-vmess").textContent = c.vmess || 0;
      document.getElementById("cnt-vless").textContent = c.vless || 0;
      document.getElementById("cnt-trojan").textContent = c.trojan || 0;

      document.getElementById("net-bw-total").textContent = s.bandwidth.total;
      document.getElementById("net-bw-dl").textContent = s.bandwidth.download;
      document.getElementById("net-bw-ul").textContent = s.bandwidth.upload;
      document.getElementById("net-mode-badge").textContent = n.mode;
      document.getElementById("net-domain").textContent = n.domain;
      document.getElementById("net-pub-ip").textContent = n.public_ip;
    }

    const sysCpu = document.getElementById("sys-cpu-val");
    if (sysCpu) {
      sysCpu.textContent = `${s.cpu_percent}% (${s.cpu_cores} Core)`;
      document.getElementById("sys-cpu-bar").style.width = `${Math.min(100, s.cpu_percent)}%`;
      document.getElementById("sys-load-sub").textContent = `Load: ${s.load_avg}`;

      document.getElementById("sys-ram-val").textContent = `${s.ram_used_mb} / ${s.ram_total_mb} MB (${s.ram_percent}%)`;
      document.getElementById("sys-ram-bar").style.width = `${Math.min(100, s.ram_percent)}%`;

      document.getElementById("sys-disk-val").textContent = `${s.disk_used_gb} / ${s.disk_total_gb} GB (${s.disk_percent}%)`;
      document.getElementById("sys-disk-bar").style.width = `${Math.min(100, s.disk_percent)}%`;

      document.getElementById("sys-uptime-val").textContent = s.uptime;
      document.getElementById("sys-os-val").textContent = s.os;
      document.getElementById("sys-kernel-val").textContent = `${s.kernel} (${s.arch})`;
      document.getElementById("sys-host-val").textContent = s.hostname;
      document.getElementById("sys-domain-val").textContent = `${n.domain} (${n.public_ip}:${n.panel_port})`;
    }

    const svcTbody = document.getElementById("service-status-tbody");
    if (svcTbody) {
      svcTbody.innerHTML = data.services.map(item => `
        <tr>
          <td data-label="Service"><strong>${item.name.toUpperCase()}</strong></td>
          <td data-label="Status">
            <span class="badge ${item.status === 'running' ? 'badge-running' : 'badge-stopped'}">
              ${item.status.toUpperCase()}
            </span>
          </td>
          <td data-label="Aksi">
            <button type="button" class="btn btn-primary btn-sm" onclick="restartService('${item.name}')">🔄 Restart</button>
          </td>
        </tr>
      `).join("");
    }
  } catch (err) {
    console.error("Overview error:", err);
  }
}

async function loadDashboardUserStats() {
  const tbody = document.getElementById("dashboard-users-tbody");
  if (!tbody) return;

  try {
    const res = await fetch("/api/monitor/status");
    const data = await res.json();

    if (!data.accounts.length) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#94a3b8;">Belum ada user terdaftar.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.accounts.map(a => {
      const totalUsed = (a.up_bytes || 0) + (a.down_bytes || 0);
      const isOnline = a.connected_ip_count > 0 && a.status === "active";
      const badgeClass = isOnline ? "badge-online" : `badge-${a.status}`;
      const statusText = isOnline ? `ONLINE (${a.connected_ip_count}/${a.ip_limit} IP)` : a.status.toUpperCase();
      const ipPills = a.connected_ips && a.connected_ips.length
        ? a.connected_ips.map(ip => `<span class="ip-pill">${ip}</span>`).join("")
        : `<span style="color:#64748b;">-</span>`;

      const unlockQuickBtn = a.status === "locked"
        ? ` <button type="button" class="btn btn-warning btn-sm" onclick="promptUnlockAccount(${a.id}, '${a.username}', ${a.ip_limit})">🔓 Unlock</button>`
        : "";

      return `
        <tr>
          <td data-label="User"><strong>${a.username}</strong> <span class="badge badge-online">${a.protocol.toUpperCase()}</span></td>
          <td data-label="Status"><span class="badge ${badgeClass}">${statusText}</span>${unlockQuickBtn}</td>
          <td data-label="Trafik">${formatBytes(totalUsed)} / ${a.quota_gb} GB</td>
          <td data-label="IP Client">${ipPills}</td>
          <td data-label="Expired">${a.exp_display}</td>
        </tr>
      `;
    }).join("");
  } catch (e) {
    console.error(e);
  }
}

async function restartService(svcName) {
  showToast(`Me-restart ${svcName}...`);
  await fetch("/api/service/restart", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ service: svcName }),
  });
  loadOverviewAndSystem();
}

/* ============================================================================
   MENU 2: BUAT AKUN SIMPLE + CONFIG BUG SNI / WILDCARD + UNLOCK IP
   ============================================================================ */
function renderCreatedAccountBox(acc) {
  const box = document.getElementById("created-account-output");
  if (!box) return;
  const d = acc.connection_details;
  box.style.display = "block";

  let linksHtml = "";
  if (acc.protocol === "ssh") {
    linksHtml = `
      <div class="form-group">
        <label>1. Payload WS CDN / Cloudflare (Port 80 & 443):</label>
        <div class="copy-box">
          <span>${d.ssh_payload_ntls}</span>
          <button type="button" class="btn btn-primary btn-sm" onclick="copyText('${d.ssh_payload_ntls}', 'Payload WS')">Copy</button>
        </div>
      </div>
      <div class="form-group">
        <label>2. Payload Split Bug Host / SNI (${d.bug_host}):</label>
        <div class="copy-box">
          <span>${d.ssh_payload_split_bug}</span>
          <button type="button" class="btn btn-primary btn-sm" onclick="copyText('${d.ssh_payload_split_bug}', 'Payload Split Bug')">Copy</button>
        </div>
      </div>
      <div class="form-group">
        <label>3. Payload WSS SSL/SNI (Port 443):</label>
        <div class="copy-box">
          <span>${d.ssh_payload_tls}</span>
          <button type="button" class="btn btn-primary btn-sm" onclick="copyText('${d.ssh_payload_tls}', 'Payload WSS')">Copy</button>
        </div>
      </div>
      <div class="form-group">
        <label>4. Format Proxy / Akun HTTP Custom:</label>
        <div class="copy-box">
          <span>${d.ssh_proxy_format}</span>
          <button type="button" class="btn btn-primary btn-sm" onclick="copyText('${d.ssh_proxy_format}', 'Format Proxy')">Copy</button>
        </div>
      </div>
    `;
  } else {
    linksHtml = `
      <div class="form-group">
        <label>🔥 1. Config WS TLS Mode Bug CDN / SNI (Address & SNI: ${d.bug_host}):</label>
        <div class="copy-box">
          <span>${d.uri_bug_cdn_tls}</span>
          <button type="button" class="btn btn-primary btn-sm" onclick="copyText('${d.uri_bug_cdn_tls}', 'Config Bug TLS')">Copy</button>
        </div>
      </div>
      <div class="form-group">
        <label>🔥 2. Config WS Non-TLS Port 80 Mode Bug Host (${d.bug_host}:80):</label>
        <div class="copy-box">
          <span>${d.uri_bug_ntls}</span>
          <button type="button" class="btn btn-primary btn-sm" onclick="copyText('${d.uri_bug_ntls}', 'Config Bug 80')">Copy</button>
        </div>
      </div>
      <div class="form-group">
        <label>🔥 3. Config WS TLS Mode Wildcard (${d.wildcard_host}):</label>
        <div class="copy-box">
          <span>${d.uri_bug_wildcard}</span>
          <button type="button" class="btn btn-primary btn-sm" onclick="copyText('${d.uri_bug_wildcard}', 'Config Wildcard')">Copy</button>
        </div>
      </div>
      <div class="form-group">
        <label>4. Config WS TLS Standar (${d.host}:443):</label>
        <div class="copy-box">
          <span>${d.uri_tls}</span>
          <button type="button" class="btn btn-primary btn-sm" onclick="copyText('${d.uri_tls}', 'Link TLS Standar')">Copy</button>
        </div>
      </div>
      <div class="form-group">
        <label>5. Config gRPC TLS (${d.service_name_grpc}):</label>
        <div class="copy-box">
          <span>${d.uri_grpc}</span>
          <button type="button" class="btn btn-primary btn-sm" onclick="copyText('${d.uri_grpc}', 'Link gRPC')">Copy</button>
        </div>
      </div>
    `;
  }

  const qrHtml = d.qr_svg
    ? `<div style="margin-top:10px;text-align:center;">
         <img src="${d.qr_svg}" alt="QR" style="background:#fff;padding:6px;border-radius:10px;max-width:140px;" />
       </div>`
    : "";

  box.innerHTML = `
    <div class="card-title">
      <span>✅ Config Siap Pakai (${acc.protocol.toUpperCase()} - ${acc.username})</span>
    </div>
    <div style="font-size:0.78rem;display:grid;grid-template-columns:repeat(2,1fr);gap:6px;margin-bottom:10px;">
      <div>Host Server: <code>${d.host}</code></div>
      <div>Bug Host/SNI: <code>${d.bug_host}</code></div>
      <div>Pass/UUID: <code>${acc.secret}</code></div>
      <div>Path WS: <code>${d.path_ws}</code></div>
      <div>Limit: <code>${acc.ip_limit} IP / ${acc.quota_gb} GB</code></div>
      <div>Exp: <code>${acc.exp_display}</code></div>
    </div>
    ${linksHtml}
    ${qrHtml}
  `;
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function submitCreateAccount(event) {
  event.preventDefault();
  const protocol = document.getElementById("acc-protocol").value;
  const username = document.getElementById("acc-username").value.trim();
  const secret = document.getElementById("acc-secret").value.trim();
  const bugHostEl = document.getElementById("acc-bug-host");
  const bugHost = bugHostEl ? bugHostEl.value.trim() : "quiz.int.vidio.com";
  const durationMode = document.getElementById("acc-duration-mode").value;
  const durationValue = parseInt(document.getElementById("acc-duration-val").value || "30", 10);
  const ipLimit = parseInt(document.getElementById("acc-ip-limit").value || "2", 10);
  const quotaGb = parseFloat(document.getElementById("acc-quota-gb").value || "50");

  const res = await fetch("/api/accounts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      protocol,
      username,
      secret,
      bug_host: bugHost || "quiz.int.vidio.com",
      duration_mode: durationMode,
      duration_value: durationValue,
      ip_limit: ipLimit,
      quota_gb: quotaGb,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    alert(data.detail || "Gagal membuat akun.");
    return;
  }
  showToast(`Akun ${username} berhasil dibuat!`);
  renderCreatedAccountBox(data.account);
  loadAccountsSimpleList();
}

async function loadAccountsSimpleList() {
  const tbody = document.getElementById("crud-accounts-tbody");
  if (!tbody) return;

  const bugHostEl = document.getElementById("acc-bug-host");
  const bugHost = bugHostEl ? bugHostEl.value.trim() : "";

  const res = await fetch(`/api/accounts?bug_host=${encodeURIComponent(bugHost)}`);
  const data = await res.json();
  window.accountsCache = {};
  data.accounts.forEach(a => {
    window.accountsCache[a.id] = a;
  });

  if (!data.accounts.length) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#94a3b8;">Belum ada akun.</td></tr>`;
    return;
  }

  tbody.innerHTML = data.accounts.map(a => `
    <tr>
      <td data-label="Akun"><strong>${a.username}</strong> <span class="badge badge-online">${a.protocol.toUpperCase()}</span></td>
      <td data-label="Expired">${a.exp_display}</td>
      <td data-label="Limit">${a.ip_limit} IP / ${a.quota_gb} GB</td>
      <td data-label="Status"><span class="badge badge-${a.status}">${a.status.toUpperCase()}</span></td>
      <td data-label="Aksi" style="display:flex;flex-wrap:wrap;gap:5px;justify-content:flex-end;align-items:center;">
        <button type="button" class="btn btn-primary btn-sm" onclick="renderCreatedAccountBox(window.accountsCache[${a.id}])">📋 Config/Bug</button>
        <button type="button" class="btn btn-warning btn-sm" onclick="promptUnlockAccount(${a.id}, '${a.username}', ${a.ip_limit})">🔓 Unlock/Limit IP</button>
        <button type="button" class="btn btn-success btn-sm" onclick="promptRenewAccount(${a.id}, '${a.username}')">➕ Renew</button>
        <span class="badge badge-cli-only">🔒 Hapus via CLI</span>
      </td>
    </tr>
  `).join("");
}

async function promptUnlockAccount(id, username, currentLimit) {
  const newLimStr = prompt(
    `Unlock akun '${username}' & hapus riwayat IP yang nyangkut.\nMasukkan batas Limit IP baru:`,
    String(currentLimit || 10)
  );
  if (newLimStr === null) return;
  const newLim = parseInt(newLimStr, 10) || currentLimit || 10;

  const res = await fetch(`/api/accounts/${id}/unlock`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ip_limit: newLim }),
  });
  if (res.ok) {
    showToast(`Akun '${username}' berhasil di-unlock (Limit ${newLim} IP)!`);
    loadAccountsSimpleList();
    loadDashboardUserStats();
  }
}

async function promptRenewAccount(id, username) {
  const days = prompt(`Tambah masa aktif '${username}' (hari):`, "30");
  if (!days) return;
  const addDays = parseInt(days, 10);
  if (isNaN(addDays) || addDays <= 0) return;

  await fetch(`/api/accounts/${id}/renew`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ add_days: addDays }),
  });
  showToast(`Masa aktif ${username} diperpanjang!`);
  loadAccountsSimpleList();
}

/* ============================================================================
   MENU 3: LOG SERVER
   ============================================================================ */
async function loadServerLogs() {
  const sel = document.getElementById("log-source-select");
  const box = document.getElementById("server-log-box");
  if (!sel || !box) return;

  const res = await fetch(`/api/logs?source=${encodeURIComponent(sel.value)}&lines=120`);
  const data = await res.json();
  box.textContent = data.content || "Log kosong.";
  box.scrollTop = box.scrollHeight;
}

async function clearServerLogs() {
  const sel = document.getElementById("log-source-select");
  if (!sel) return;
  await fetch(`/api/logs/clear?source=${encodeURIComponent(sel.value)}`, { method: "POST" });
  showToast("Log dibersihkan!");
  loadServerLogs();
}

/* ============================================================================
   MENU 5: SETTING BANNER SSH & BACKUP / RESTORE
   ============================================================================ */
async function loadBannerAndBackups() {
  const bannerInput = document.getElementById("ssh-banner-textarea");
  if (bannerInput) {
    const res = await fetch("/api/settings/banner");
    const data = await res.json();
    bannerInput.value = data.banner_html || "";
  }
  loadBackupList();
}

async function saveSshBanner() {
  const bannerInput = document.getElementById("ssh-banner-textarea");
  if (!bannerInput) return;
  await fetch("/api/settings/banner", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ banner_html: bannerInput.value }),
  });
  showToast("Banner SSH berhasil disimpan & diterapkan!");
}

async function loadBackupList() {
  const tbody = document.getElementById("backup-list-tbody");
  if (!tbody) return;
  const res = await fetch("/api/settings/backups");
  const data = await res.json();

  if (!data.backups.length) {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:#94a3b8;">Belum ada file backup tersimpan.</td></tr>`;
    return;
  }

  tbody.innerHTML = data.backups.map(b => `
    <tr>
      <td data-label="File"><code>${b.filename}</code></td>
      <td data-label="Ukuran">${b.size_kb} KB</td>
      <td data-label="Waktu">${b.created_at}</td>
      <td data-label="Aksi" style="display:flex;gap:6px;justify-content:flex-end;">
        <a class="btn btn-primary btn-sm" href="/api/settings/backup/download/${encodeURIComponent(b.filename)}">⬇️ Unduh</a>
        <button type="button" class="btn btn-warning btn-sm" onclick="restoreLocalBackup('${b.filename}')">♻️ Restore</button>
      </td>
    </tr>
  `).join("");
}

async function createNewBackup() {
  showToast("Membuat arsip backup...");
  const res = await fetch("/api/settings/backup", { method: "POST" });
  const data = await res.json();
  if (res.ok) {
    showToast(`Backup ${data.filename} berhasil dibuat!`);
    loadBackupList();
  }
}

async function restoreLocalBackup(filename) {
  if (!confirm(`Restore data akun & konfigurasi dari '${filename}'?`)) return;
  const res = await fetch("/api/settings/restore-local", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename }),
  });
  if (res.ok) {
    showToast("Restore berhasil diterapkan!");
    loadOverviewAndSystem();
  }
}

async function uploadAndRestoreBackup(event) {
  event.preventDefault();
  const fileInput = document.getElementById("restore-file-input");
  if (!fileInput || !fileInput.files.length) {
    alert("Pilih file backup (.tar.gz) terlebih dahulu!");
    return;
  }
  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  showToast("Mengunggah & me-restore backup...");
  const res = await fetch("/api/settings/restore-upload", {
    method: "POST",
    body: formData,
  });
  const data = await res.json();
  if (!res.ok) {
    alert(data.detail || "Gagal restore backup.");
    return;
  }
  showToast("Backup berhasil di-restore!");
  fileInput.value = "";
  loadBackupList();
}
