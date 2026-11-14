/* ============================================================================
   JIBSZ TUNNELING / J1BTNL - FRONTEND CONTROLLER (app.js)
   Mengelola Wizard Instalasi Real-Time & Dashboard Manajemen 3 Menu
   ============================================================================ */

let pollInterval = null;
let selectedMode = "public";

// Helper Copy ke Clipboard
function copyText(text, label = "Teks") {
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    showToast(`${label} berhasil disalin ke clipboard!`);
  }).catch(() => {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    showToast(`${label} berhasil disalin!`);
  });
}

function showToast(msg) {
  let toast = document.getElementById("jibsz-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "jibsz-toast";
    toast.style.cssText =
      "position:fixed;bottom:24px;right:24px;background:linear-gradient(135deg,#00f2fe,#a855f7);" +
      "color:#070b14;font-weight:700;padding:12px 20px;border-radius:12px;z-index:9999;box-shadow:0 8px 25px rgba(0,0,0,0.5);";
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.style.display = "block";
  setTimeout(() => {
    toast.style.display = "none";
  }, 2600);
}

/* ============================================================================
   BAGIAN 1: WIZARD INSTALASI (install.html)
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
  btn.textContent = "⏳ Memulai Proses Instalasi...";

  try {
    const res = await fetch("/api/install/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: selectedMode,
        domain: domain,
        email: email,
        cf_token: cfToken,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "Gagal memulai instalasi.");
      btn.disabled = false;
      btn.textContent = "🚀 Mulai Instalasi Sekarang";
      return;
    }
    showToast("Proses instalasi dimulai di background!");
    pollInstallationProgress();
    if (!pollInterval) {
      pollInterval = setInterval(pollInstallationProgress, 2000);
    }
  } catch (err) {
    alert("Kesalahan koneksi: " + err);
    btn.disabled = false;
  }
}

async function retrySingleComponent(compId) {
  showToast(`Mengulangi instalasi komponen: ${compId}...`);
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
  if (s === "installing") return `<span class="badge badge-installing">Installing...</span>`;
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
          <div style="display:flex;align-items:center;gap:10px;">
            ${mapStatusBadge(c.status)}
            ${retryBtn}
          </div>
        </div>
      `;
    }).join("");

    const hasFailed = data.components.some(c => c.status === "failed");
    const retryAllBtn = document.getElementById("btn-retry-all-failed");
    if (retryAllBtn) {
      retryAllBtn.style.display = hasFailed ? "inline-flex" : "none";
    }

    const logBox = document.getElementById("install-log-box");
    if (logBox && data.logs) {
      logBox.textContent = data.logs;
      logBox.scrollTop = logBox.scrollHeight;
    }

    if (data.is_installed) {
      const banner = document.getElementById("install-complete-banner");
      if (banner) banner.style.display = "block";
      setTimeout(() => {
        window.location.href = "/dashboard";
      }, 2500);
    }
  } catch (e) {
    console.error("Polling error:", e);
  }
}

/* ============================================================================
   BAGIAN 2: DASHBOARD MANAJEMEN 3 MENU (dashboard.html)
   ============================================================================ */
function switchDashboardTab(tabId) {
  document.querySelectorAll(".tab-pane").forEach(el => {
    el.style.display = "none";
  });
  document.querySelectorAll(".nav-tab").forEach(el => {
    el.classList.remove("active");
  });

  const targetPane = document.getElementById(`pane-${tabId}`);
  const targetBtn = document.getElementById(`tab-btn-${tabId}`);
  if (targetPane) targetPane.style.display = "block";
  if (targetBtn) targetBtn.classList.add("active");

  if (tabId === "menu1") loadSystemOverview();
  if (tabId === "menu2") loadAccountsCRUD();
  if (tabId === "menu3") loadMonitorIPStatus();
}

async function loadSystemOverview() {
  const sysContainer = document.getElementById("sys-overview-cards");
  if (!sysContainer) return;

  try {
    const res = await fetch("/api/system/overview");
    const data = await res.json();
    const s = data.system;
    const n = data.network;
    const c = data.account_counts;

    document.getElementById("val-os").textContent = s.os;
    document.getElementById("val-kernel").textContent = `Kernel: ${s.kernel}`;
    document.getElementById("val-uptime").textContent = s.uptime;
    document.getElementById("val-cpu").textContent = `${s.cpu_percent}% (${s.cpu_cores} Core)`;
    document.getElementById("val-load").textContent = `Load: ${s.load_avg}`;
    document.getElementById("val-ram").textContent = `${s.ram_used_mb} / ${s.ram_total_mb} MB (${s.ram_percent}%)`;
    document.getElementById("val-disk").textContent = `${s.disk_used_gb} / ${s.disk_total_gb} GB (${s.disk_percent}%)`;
    document.getElementById("val-bw-total").textContent = s.bandwidth.total;
    document.getElementById("val-bw-sub").textContent = `DL: ${s.bandwidth.download} | UL: ${s.bandwidth.upload}`;

    document.getElementById("val-net-ip").textContent = n.public_ip;
    document.getElementById("val-net-mode").textContent = n.mode;
    document.getElementById("val-net-domain").textContent = n.domain;
    document.getElementById("val-net-port").textContent = n.panel_port;

    document.getElementById("cnt-ssh").textContent = c.ssh || 0;
    document.getElementById("cnt-vmess").textContent = c.vmess || 0;
    document.getElementById("cnt-vless").textContent = c.vless || 0;
    document.getElementById("cnt-trojan").textContent = c.trojan || 0;

    const svcTbody = document.getElementById("service-status-tbody");
    if (svcTbody) {
      svcTbody.innerHTML = data.services.map(item => `
        <tr>
          <td><strong>${item.name.toUpperCase()}</strong></td>
          <td>
            <span class="badge ${item.status === 'running' ? 'badge-running' : 'badge-stopped'}">
              ${item.status.toUpperCase()}
            </span>
          </td>
          <td>
            <button class="btn btn-primary btn-sm" onclick="restartService('${item.name}')">🔄 Restart</button>
          </td>
        </tr>
      `).join("");
    }
  } catch (err) {
    console.error("Gagal memuat overview:", err);
  }
}

async function restartService(svcName) {
  showToast(`Me-restart service ${svcName}...`);
  await fetch("/api/service/restart", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ service: svcName }),
  });
  loadSystemOverview();
}

function renderCreatedAccountBox(acc) {
  const box = document.getElementById("created-account-output");
  if (!box) return;
  const d = acc.connection_details;
  box.style.display = "block";

  let linksHtml = "";
  if (acc.protocol === "ssh") {
    linksHtml = `
      <div class="form-group">
        <label>Payload HTTP Custom / DarkTunnel (WS Non-TLS Port 80 & Cloudflare):</label>
        <div class="copy-box">
          <span>${d.ssh_payload_ntls}</span>
          <button class="btn btn-primary btn-sm" onclick="copyText('${d.ssh_payload_ntls}', 'Payload WS')">Copy</button>
        </div>
      </div>
      <div class="form-group">
        <label>Payload WSS TLS (Port 443):</label>
        <div class="copy-box">
          <span>${d.ssh_payload_tls}</span>
          <button class="btn btn-primary btn-sm" onclick="copyText('${d.ssh_payload_tls}', 'Payload WSS TLS')">Copy</button>
        </div>
      </div>
    `;
  } else {
    linksHtml = `
      <div class="form-group">
        <label>Link URI Port 443 (TLS / WebSocket CDN Cloudflare & Public):</label>
        <div class="copy-box">
          <span>${d.uri_tls}</span>
          <button class="btn btn-primary btn-sm" onclick="copyText('${d.uri_tls}', 'URI TLS 443')">Copy</button>
        </div>
      </div>
      <div class="form-group">
        <label>Link URI Port 80 (Non-TLS / WebSocket):</label>
        <div class="copy-box">
          <span>${d.uri_ntls}</span>
          <button class="btn btn-primary btn-sm" onclick="copyText('${d.uri_ntls}', 'URI Non-TLS 80')">Copy</button>
        </div>
      </div>
      <div class="form-group">
        <label>Link URI gRPC (Port 443 ServiceName: ${d.service_name_grpc}):</label>
        <div class="copy-box">
          <span>${d.uri_grpc}</span>
          <button class="btn btn-primary btn-sm" onclick="copyText('${d.uri_grpc}', 'URI gRPC')">Copy</button>
        </div>
      </div>
    `;
  }

  const qrHtml = d.qr_svg
    ? `<div style="margin-top:14px;text-align:center;">
         <p style="font-size:0.82rem;color:#94a3b8;margin-bottom:6px;">Scan QR Code Konfigurasi:</p>
         <img src="${d.qr_svg}" alt="QR Code" style="background:#fff;padding:8px;border-radius:12px;max-width:190px;" />
       </div>`
    : "";

  box.innerHTML = `
    <div class="card-title">
      <span>✅ Detail Akun Berhasil Dibuat (${acc.protocol.toUpperCase()} - ${acc.username})</span>
    </div>
    <div class="grid-2">
      <div>
        <p><strong>Host / Domain:</strong> <code>${d.host}</code></p>
        <p><strong>IP Public VPS:</strong> <code>${d.ip_public}</code></p>
        <p><strong>Mode Server:</strong> ${d.mode}</p>
        <p><strong>Username:</strong> <code>${acc.username}</code></p>
        <p><strong>Password / UUID:</strong> <code>${acc.secret}</code></p>
      </div>
      <div>
        <p><strong>Port TLS / CDN:</strong> <code>443</code> | <strong>Non-TLS:</strong> <code>80</code></p>
        <p><strong>Path WebSocket:</strong> <code>${d.path_ws}</code></p>
        <p><strong>ServiceName gRPC:</strong> <code>${d.service_name_grpc}</code></p>
        <p><strong>Limit IP / Kuota:</strong> ${acc.ip_limit} IP / ${acc.quota_gb} GB</p>
        <p><strong>Masa Aktif s/d:</strong> ${acc.exp_display}</p>
      </div>
    </div>
    <div style="margin-top:14px;">
      ${linksHtml}
      ${qrHtml}
    </div>
  `;
}

async function submitCreateAccount(event) {
  event.preventDefault();
  const protocol = document.getElementById("acc-protocol").value;
  const username = document.getElementById("acc-username").value.trim();
  const secret = document.getElementById("acc-secret").value.trim();
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
  showToast(`Akun ${username} (${protocol.toUpperCase()}) berhasil dibuat!`);
  renderCreatedAccountBox(data.account);
  loadAccountsCRUD();
}

window.accountsCache = {};

async function loadAccountsCRUD() {
  const tbody = document.getElementById("crud-accounts-tbody");
  if (!tbody) return;

  const res = await fetch("/api/accounts");
  const data = await res.json();
  window.accountsCache = {};
  data.accounts.forEach(a => {
    window.accountsCache[a.id] = a;
  });

  if (!data.accounts.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:#94a3b8;">Belum ada akun yang dibuat.</td></tr>`;
    return;
  }

  tbody.innerHTML = data.accounts.map(a => `
    <tr>
      <td><span class="badge badge-online">${a.protocol.toUpperCase()}</span></td>
      <td><strong>${a.username}</strong></td>
      <td><code>${a.secret}</code></td>
      <td>${a.exp_display}</td>
      <td>${a.ip_limit} IP / ${a.quota_gb} GB</td>
      <td><span class="badge badge-${a.status}">${a.status.toUpperCase()}</span></td>
      <td style="display:flex;flex-wrap:wrap;gap:6px;">
        <button class="btn btn-primary btn-sm" onclick="renderCreatedAccountBox(window.accountsCache[${a.id}])">📋 Detail/QR</button>
        <button class="btn btn-success btn-sm" onclick="promptRenewAccount(${a.id}, '${a.username}')">➕ Renew</button>
        <button class="btn btn-warning btn-sm" onclick="toggleLockAccount(${a.id})">${a.status === 'locked' ? '🔓 Unlock' : '🔒 Lock'}</button>
        <button class="btn btn-danger btn-sm" onclick="deleteAccount(${a.id}, '${a.username}')">🗑️ Hapus</button>
      </td>
    </tr>
  `).join("");
}

async function promptRenewAccount(id, username) {
  const days = prompt(`Perpanjang masa aktif akun '${username}' berapa hari?`, "30");
  if (!days) return;
  const addDays = parseInt(days, 10);
  if (isNaN(addDays) || addDays <= 0) return;

  await fetch(`/api/accounts/${id}/renew`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ add_days: addDays }),
  });
  showToast(`Masa aktif ${username} berhasil ditambah ${addDays} hari!`);
  loadAccountsCRUD();
}

async function toggleLockAccount(id) {
  await fetch(`/api/accounts/${id}/toggle-lock`, { method: "POST" });
  showToast("Status Lock/Unlock akun diperbarui.");
  loadAccountsCRUD();
  loadMonitorIPStatus();
}

async function deleteAccount(id, username) {
  if (!confirm(`Yakin ingin menghapus akun '${username}' secara permanen?`)) return;
  await fetch(`/api/accounts/${id}`, { method: "DELETE" });
  showToast(`Akun ${username} telah dihapus.`);
  loadAccountsCRUD();
  loadMonitorIPStatus();
}

/* ============================================================================
   MENU 3: MONITORING STATUS AKUN, PEMAKAIAN KUOTA, & IP CLIENT REAL-TIME
   ============================================================================ */
function formatBytes(bytes) {
  const b = Number(bytes || 0);
  if (b < 1024) return `${b} B`;
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(2)} KB`;
  if (b < 1024 ** 3) return `${(b / (1024 ** 2)).toFixed(2)} MB`;
  return `${(b / (1024 ** 3)).toFixed(2)} GB`;
}

async function loadMonitorIPStatus() {
  const tbody = document.getElementById("monitor-ip-tbody");
  if (!tbody) return;

  const res = await fetch("/api/monitor/status");
  const data = await res.json();

  if (!data.accounts.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:#94a3b8;">Belum ada akun terdaftar.</td></tr>`;
    return;
  }

  tbody.innerHTML = data.accounts.map(a => {
    const totalUsed = (a.up_bytes || 0) + (a.down_bytes || 0);
    const isOnline = a.connected_ip_count > 0 && a.status === "active";
    const statusLabel = isOnline ? "ONLINE / DIGUNAKAN" : a.status.toUpperCase();
    const badgeClass = isOnline ? "badge-online" : `badge-${a.status}`;

    const ipPills = a.connected_ips && a.connected_ips.length
      ? a.connected_ips.map(ip => `<span class="ip-pill">${ip}</span>`).join("")
      : `<span style="color:#64748b;font-size:0.8rem;">Tidak ada koneksi aktif</span>`;

    return `
      <tr>
        <td><span class="badge badge-online">${a.protocol.toUpperCase()}</span></td>
        <td><strong>${a.username}</strong></td>
        <td><span class="badge ${badgeClass}">${statusLabel}</span></td>
        <td>
          <div>UL: ${formatBytes(a.up_bytes)} | DL: ${formatBytes(a.down_bytes)}</div>
          <div style="color:#00f2fe;font-weight:600;">Total: ${formatBytes(totalUsed)} / ${a.quota_gb} GB</div>
        </td>
        <td>${ipPills}</td>
        <td><strong>${a.connected_ip_count}</strong> / ${a.ip_limit} IP</td>
        <td>
          <button class="btn btn-warning btn-sm" onclick="toggleLockAccount(${a.id})">
            ${a.status === 'locked' ? '🔓 Unlock' : '🔒 Kick & Lock'}
          </button>
        </td>
      </tr>
    `;
  }).join("");
}

async function triggerEnforceMultiLogin() {
  showToast("Menjalankan pengecekan Auto-Kick / Auto-Lock Multi-Login & Kuota...");
  await fetch("/api/monitor/enforce", { method: "POST" });
  loadMonitorIPStatus();
}
