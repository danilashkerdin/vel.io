import { API } from './config.js';

let map = null;
let drawnLayer = null;
let markerPlaced = false;
let editingId = null;
let zonesData = [];
let tiers = [];

const authHeaders = () => {
    const t = localStorage.getItem("token");
    return t ? { Authorization: `Bearer ${t}` } : {};
};

function escapeHtml(str) {
    if (!str) { return ""; }
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

async function api(path, opts = {}) {
    try {
        const headers = { ...authHeaders() };
        if (opts.body && !(opts.body instanceof FormData)) {
            headers["Content-Type"] = "application/json";
        }
        const res = await fetch(`${API}${path}`, { headers, ...opts });
        if (res.status === 403 || res.status === 401) {
            document.getElementById("adminApp").style.display = "none";
            document.getElementById("adminLogin").style.display = "flex";
            document.getElementById("adminLoginError").textContent = "Сессия истекла";
            document.getElementById("adminLoginError").style.display = "block";
            return null;
        }
        return res;
    } catch (e) {
        console.error("API error:", e);
        return null;
    }
}

async function loginAdmin() {
    const email = document.getElementById("adminEmail").value;
    const password = document.getElementById("adminPassword").value;
    const errorEl = document.getElementById("adminLoginError");

    const res = await fetch(`${API}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
        const e = await res.json();
        errorEl.textContent = e.detail || "Ошибка входа";
        errorEl.style.display = "block";
        return;
    }

    const data = await res.json();
    if (data.email !== "admin@vel.io" && data.user?.email !== "admin@vel.io") {
        errorEl.textContent = "У вас нет прав администратора";
        errorEl.style.display = "block";
        return;
    }

    localStorage.setItem("token", data.token);
    localStorage.setItem("user", JSON.stringify(data.user || data));
    showAdminApp();
}

function logoutAdmin() {
    localStorage.clear();
    document.getElementById("adminApp").style.display = "none";
    document.getElementById("adminLogin").style.display = "flex";
    document.getElementById("adminLoginError").style.display = "none";
}

async function loadTiers() {
    const res = await api("/api/admin/tiers");
    if (!res) {return;}
    tiers = await res.json();
    const sel = document.getElementById("fBudget");
    sel.innerHTML = tiers.map(t =>
        `<option value="${t.stars * 10}">${t.name} — ${(t.stars * 10).toLocaleString()}₽/мес</option>`
    ).join("");
}

async function showAdminApp() {
    document.getElementById("adminLogin").style.display = "none";
    document.getElementById("adminApp").style.display = "flex";
    initMap();
    await loadTiers();
    await loadDashboard();
    await loadZones();
}

function initMap() {
    map = L.map("map", { zoomControl: true, attributionControl: false }).setView([55.751244, 37.618423], 12);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
        attribution: "© OpenStreetMap, © CARTO",
    }).addTo(map);
    L.control.attribution({ prefix: false }).addTo(map);

    map.on("click", (e) => {
        if (!document.getElementById("zoneForm").classList.contains("hidden")) {
            placeMarker(e.latlng);
        }
    });
}

function placeMarker(latlng) {
    if (drawnLayer) {map.removeLayer(drawnLayer);}
    drawnLayer = L.marker(latlng, { draggable: true }).addTo(map);
    markerPlaced = true;
}

function clearDrawing() {
    if (drawnLayer) { map.removeLayer(drawnLayer); drawnLayer = null; }
    markerPlaced = false;
}

async function loadDashboard() {
    const res = await api("/api/admin/dashboard");
    if (!res) {return;}
    const d = await res.json();
    document.getElementById("statActive").textContent = d.active_sponsored;
    document.getElementById("statRevenue").textContent = `${(d.total_monthly_revenue_rub * 0.9).toLocaleString()}₽`;
    document.getElementById("statEarned").textContent = `${d.total_earned_by_users_rub.toLocaleString()}₽`;
    document.getElementById("statPaid").textContent = `${d.total_paid_out_rub.toLocaleString()}₽`;
}

async function loadZones() {
    const res = await api("/api/admin/sponsored-territories");
    if (!res) {return;}
    zonesData = await res.json();

    const el = document.getElementById("zonesList");
    if (zonesData.length === 0) {
        el.innerHTML = '<p style="color:#999;text-align:center;font-size:13px;">Нет спонсорских зон. Нажмите «+ Новая зона» чтобы создать первую.</p>';
        return;
    }

    el.innerHTML = zonesData.map(z => `
        <div class="admin-card ${editingId === z.id ? 'active' : ''}" data-id="${z.id}">
            <div class="name" style="color:${z.color}">${z.business_name}</div>
            <div class="meta">${z.monthly_budget_rub.toLocaleString()}₽/мес · ${z.is_active ? '✅' : '⛔'}</div>
            ${z.current_owner_name ? `<div class="owner">👤 ${z.current_owner_name}</div>` : '<div class="owner" style="color:#999;">Нет владельца</div>'}
        </div>
    `).join("");

    el.querySelectorAll(".admin-card").forEach(card => {
        card.onclick = () => editZone(zonesData.find(z => z.id === card.dataset.id));
    });
}

function editZone(zone) {
    editingId = zone.id;
    document.getElementById("zoneForm").classList.remove("hidden");
    document.getElementById("formTitle").textContent = "✏️ Редактировать зону";
    document.getElementById("fBusinessName").value = zone.business_name;
    document.getElementById("fDescription").value = zone.description || "";
    const sel = document.getElementById("fBudget");
    sel.value = zone.monthly_budget_rub;
    if (!sel.value) {sel.value = tiers.length > 0 ? tiers[0].stars * 10 : 5000;}
    document.getElementById("fColor").value = zone.color;
    document.getElementById("fImage").value = zone.image_url || "";
    document.getElementById("fLink").value = zone.link_url || "";
    document.getElementById("fDeleteBtn").classList.remove("hidden");
    clearDrawing();
    markerPlaced = false;

    if (zone.polygon) {
        if (zone.polygon.type === "Point") {
            const [lng, lat] = zone.polygon.coordinates;
            drawnLayer = L.marker([lat, lng]).addTo(map);
            map.setView([lat, lng], 15);
        } else if (zone.polygon.type === "Polygon") {
            const coords = zone.polygon.coordinates[0].map(c => [c[1], c[0]]);
            drawnLayer = L.polygon(coords, { color: zone.color, weight: 3, fillOpacity: 0.2 }).addTo(map);
            map.fitBounds(drawnLayer.getBounds(), { padding: [40, 40] });
        }
    }

    document.querySelectorAll(".admin-card").forEach(c => c.classList.remove("active"));
    document.querySelector(`.admin-card[data-id="${zone.id}"]`)?.classList.add("active");
}

function showNewZoneForm() {
    editingId = null;
    document.getElementById("zoneForm").classList.remove("hidden");
    document.getElementById("formTitle").textContent = "📍 Новая спонсорская зона";
    document.getElementById("fBusinessName").value = "";
    document.getElementById("fDescription").value = "";
    document.getElementById("fBudget").value = tiers.length > 0 ? tiers[0].stars * 10 : 5000;
    document.getElementById("fColor").value = "#FFD700";
    document.getElementById("fImage").value = "";
    document.getElementById("fLink").value = "";
    document.getElementById("fDeleteBtn").classList.add("hidden");
    clearDrawing();
    document.querySelectorAll(".admin-card").forEach(c => c.classList.remove("active"));
}

async function saveZone() {
    const business_name = document.getElementById("fBusinessName").value.trim();
    if (!business_name) { showToast("Введите название бизнеса"); return; }

    let polygon = null;
    if (markerPlaced && drawnLayer && drawnLayer instanceof L.Marker) {
        const latlng = drawnLayer.getLatLng();
        polygon = { type: "Point", coordinates: [latlng.lng, latlng.lat] };
    } else if (editingId) {
        const existing = zonesData.find(z => z.id === editingId);
        polygon = existing.polygon;
    } else {
        showToast("Поставьте точку на карте (кликните по карте)");
        return;
    }

    const body = {
        business_name,
        description: document.getElementById("fDescription").value.trim(),
        monthly_budget_rub: parseInt(document.getElementById("fBudget").value) || 5000,
        color: document.getElementById("fColor").value,
        image_url: document.getElementById("fImage").value.trim() || null,
        link_url: document.getElementById("fLink").value.trim() || null,
        polygon,
    };

    if (editingId) {
        const res = await api(`/api/admin/sponsored-territories/${editingId}`, {
            method: "PATCH",
            body: JSON.stringify(body),
        });
        if (!res) {return;}
    } else {
        const res = await api("/api/admin/sponsored-territories", {
            method: "POST",
            body: JSON.stringify(body),
        });
        if (!res) {return;}
    }

    cancelForm();
    await loadZones();
    await loadDashboard();
}

function cancelForm() {
    document.getElementById("zoneForm").classList.add("hidden");
    clearDrawing();
    editingId = null;
    document.querySelectorAll(".admin-card").forEach(c => c.classList.remove("active"));
}

async function deleteZone() {
    if (!editingId || !confirm("Удалить спонсорскую зону?")) {return;}
    const res = await api(`/api/admin/sponsored-territories/${editingId}`, { method: "DELETE" });
    if (!res) {return;}
    cancelForm();
    await loadZones();
    await loadDashboard();
}

async function loadPayouts() {
    const el = document.getElementById("payoutsList");
    const [pendingRes, historyRes] = await Promise.all([
        api("/api/admin/payouts/pending"),
        api("/api/admin/payouts/history?limit=10"),
    ]);
    if (!pendingRes) { el.innerHTML = '<p style="color:#999;font-size:13px;">Ошибка загрузки</p>'; return; }

    const pending = await pendingRes.json();
    const history = historyRes && historyRes.ok ? await historyRes.json() : [];

    let html = '';

    // Ожидающие выплаты
    html += `<div style="font-weight:600;font-size:13px;margin-bottom:8px;">💰 Ожидают выплаты</div>`;
    if (pending.length === 0) {
        html += '<p style="color:#999;font-size:12px;margin-bottom:12px;">Нет пользователей с балансом</p>';
    } else {
        html += pending.map(p => `
            <div style="background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:10px;margin-bottom:6px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <div style="font-weight:500;font-size:13px;">${p.username}</div>
                        <div style="font-size:11px;color:#999;">Накоплено: ${p.total_earned_rub}₽</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-weight:bold;color:#4CAF50;font-size:15px;">${p.balance_rub.toLocaleString()}₽</div>
                        <button class="process-payout-btn btn btn-sm btn-primary" data-user="${p.user_id}" data-name="${p.username}" style="margin-top:4px;">✅ Выплатить</button>
                    </div>
                </div>
            </div>
        `).join("");
    }

    // История
    if (history.length > 0) {
        html += `<div style="font-weight:600;font-size:13px;margin:12px 0 8px;">📜 История выплат</div>`;
        html += history.map(h => `
            <div style="font-size:12px;padding:4px 0;border-bottom:1px solid #f0f0f0;display:flex;justify-content:space-between;">
                <span>${h.username}</span>
                <span style="color:${h.status === 'completed' ? '#4CAF50' : '#FF9800'};">${h.amount_rub.toLocaleString()}₽ · ${h.status === 'completed' ? 'Выплачено' : 'Ожидает'}</span>
            </div>
        `).join("");
    }

    el.innerHTML = html;

    el.querySelectorAll(".process-payout-btn").forEach(btn => {
        btn.onclick = async () => {
            const userId = btn.dataset.user;
            const userName = btn.dataset.name;
            if (!confirm(`Выплатить ${userName}? Деньги будут отмечены как выплаченные.`)) {return;}
            const r = await api(`/api/admin/payouts/process/${userId}`, { method: "POST" });
            if (r && r.ok) { showToast("✅ Выплата обработана"); loadPayouts(); loadDashboard(); }
            else { const e = r ? await r.json() : {}; showToast(e.detail || "Ошибка", "error"); }
        };
    });
}

function showToast(msg) {
    const el = document.createElement("div");
    el.textContent = msg;
    el.style.cssText = "position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#333;color:white;padding:8px 16px;border-radius:8px;font-size:13px;z-index:9999;";
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2500);
}

document.addEventListener("DOMContentLoaded", () => {
    const token = localStorage.getItem("token");
    const user = JSON.parse(localStorage.getItem("user") || "{}");
    if (token && user.email === "admin@vel.io") {
        showAdminApp();
    }

    document.getElementById("adminLoginBtn").onclick = loginAdmin;
    document.getElementById("adminLogoutBtn").onclick = logoutAdmin;
    document.getElementById("newZoneBtn").onclick = showNewZoneForm;
    document.getElementById("fSaveBtn").onclick = saveZone;
    document.getElementById("fCancelBtn").onclick = cancelForm;
    document.getElementById("fDeleteBtn").onclick = deleteZone;

    document.getElementById("tabZonesBtn").onclick = () => {
        document.getElementById("sectionZones").style.display = "block";
        document.getElementById("sectionUsers").style.display = "none";
        document.getElementById("sectionPayouts").style.display = "none";
        document.getElementById("tabZonesBtn").style.background = "#4CAF50";
        document.getElementById("tabZonesBtn").style.color = "white";
        document.getElementById("tabUsersBtn").style.background = "#ddd";
        document.getElementById("tabUsersBtn").style.color = "#333";
        document.getElementById("tabPayoutsBtn").style.background = "#ddd";
        document.getElementById("tabPayoutsBtn").style.color = "#333";
    };
    document.getElementById("tabUsersBtn").onclick = () => {
        document.getElementById("sectionZones").style.display = "none";
        document.getElementById("sectionUsers").style.display = "block";
        document.getElementById("sectionPayouts").style.display = "none";
        document.getElementById("tabUsersBtn").style.background = "#4CAF50";
        document.getElementById("tabUsersBtn").style.color = "white";
        document.getElementById("tabZonesBtn").style.background = "#ddd";
        document.getElementById("tabZonesBtn").style.color = "#333";
        document.getElementById("tabPayoutsBtn").style.background = "#ddd";
        document.getElementById("tabPayoutsBtn").style.color = "#333";
        loadUsers();
    };
    document.getElementById("tabPayoutsBtn").onclick = () => {
        document.getElementById("sectionZones").style.display = "none";
        document.getElementById("sectionUsers").style.display = "none";
        document.getElementById("sectionPayouts").style.display = "block";
        document.getElementById("tabPayoutsBtn").style.background = "#4CAF50";
        document.getElementById("tabPayoutsBtn").style.color = "white";
        document.getElementById("tabZonesBtn").style.background = "#ddd";
        document.getElementById("tabZonesBtn").style.color = "#333";
        document.getElementById("tabUsersBtn").style.background = "#ddd";
        document.getElementById("tabUsersBtn").style.color = "#333";
        loadPayouts();
    };

async function loadUsers() {
    const el = document.getElementById("usersList");
    try {
        const data = await api("/api/admin/users?limit=100");
        el.innerHTML = data.map(u => `
            <div style="display:flex;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.06);gap:8px;flex-wrap:wrap;">
                <div style="flex:1;min-width:120px;">
                    <div style="font-weight:600;font-size:13px;">${escapeHtml(u.username)}</div>
                    <div style="font-size:11px;color:#999;">${escapeHtml(u.email)}</div>
                </div>
                <span style="font-size:12px;color:#666;">${u.captures_count} захв.</span>
                <span style="font-size:12px;color:#666;">${u.balance_rub}₽</span>
                ${u.is_premium ? '<span style="font-size:11px;color:#FFD700;">⭐</span>' : ''}
                ${u.is_advertiser ? '<span style="font-size:11px;color:#4CAF50;">📢</span>' : ''}
                <button class="btn btn-sm admin-toggle-premium" data-user-id="${u.id}" data-premium="${u.is_premium}" style="background:${u.is_premium ? '#FF9800' : '#555'};color:#fff;border:none;border-radius:6px;padding:4px 10px;font-size:11px;cursor:pointer;">
                    ${u.is_premium ? 'Снять Premium' : 'Дать Premium'}
                </button>
            </div>
        `).join('');

        el.querySelectorAll(".admin-toggle-premium").forEach(btn => {
            btn.onclick = async () => {
                const userId = btn.dataset.userId;
                const isPremium = btn.dataset.premium === "true";
                await api(`/api/admin/users/${userId}?is_premium=${!isPremium}`, { method: "PATCH" });
                loadUsers();
            };
        });
    } catch (e) {
        el.innerHTML = '<p style="color:#f44336;">Ошибка загрузки</p>';
    }
}

    document.getElementById("adminPassword").addEventListener("keydown", e => {
        if (e.key === "Enter") {loginAdmin();}
    });
});
