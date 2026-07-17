import { getUser } from './auth.js';
import { createStarInvoice } from './api.js';
import { openModal, closeModals, closeMenu, showToast } from './ui.js';
import { getMap } from './map.js';
import { API } from './config.js';

let drawLayer = null;
let drawPoint = null;
let drawing = false;
let editingZoneId = null;

export function isAdvertiser() {
    const u = getUser();
    return u?.is_advertiser === true;
}

export function updateAdvertiserUI() {
    const isAdv = isAdvertiser();
    const advertiserSection = document.getElementById("advertiserSection");
    if (advertiserSection) advertiserSection.style.display = isAdv ? "block" : "none";
    const mainSection = document.getElementById("cyclistMainSection");
    if (mainSection) mainSection.style.display = isAdv ? "none" : "block";
    const mySection = document.getElementById("cyclistMySection");
    if (mySection) mySection.style.display = isAdv ? "none" : "block";
}

function showBanner(text) {
    hideBanner();
    const el = document.createElement("div");
    el.id = "drawBanner";
    el.textContent = text;
    el.style.cssText = "position:fixed;top:24px;left:50%;transform:translateX(-50%);z-index:9999;background:rgba(10,10,26,0.96);color:#FFD700;padding:14px 28px;border-radius:12px;font-weight:600;font-size:15px;backdrop-filter:blur(12px);border:1px solid rgba(255,215,0,0.3);box-shadow:0 4px 24px rgba(0,0,0,0.5);pointer-events:none;";
    document.body.appendChild(el);
}
function hideBanner() { document.getElementById("drawBanner")?.remove(); }

// ─── My zones list ───

async function loadAdvertiserZones() {
    const el = document.getElementById("advertiserZonesContent");
    el.innerHTML = "Загрузка...";
    try {
        const token = localStorage.getItem("token");
        const r = await fetch(`${API}/api/my-advertiser-zones`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok) throw new Error((await r.json()).detail || "Ошибка");
        const zones = await r.json();
        if (!zones.length) {
            el.innerHTML = '<p style="color:var(--color-text-muted);text-align:center;">У вас пока нет спонсорских зон</p>';
            return;
        }
        el.innerHTML = zones.map(z => `
            <div class="az-card" data-id="${z.id}">
                <div class="az-card-header">
                    <strong>${z.business_name || "Без названия"}</strong>
                    <span class="az-badge ${z.is_active ? 'az-active' : 'az-inactive'}">${z.is_active ? "Активна" : "Неактивна"}</span>
                </div>
                <div class="az-card-body">
                    ${z.description ? `<p>${z.description}</p>` : ""}
                    <div class="az-card-metrics">
                        <span>⭐ ${z.monthly_budget_stars || (z.monthly_budget_rub / 10).toFixed(0)}</span>
                        <span>👁 ${z.impressions || 0}</span>
                        <span>🖱 ${z.clicks || 0}</span>
                    </div>
                    <div class="az-card-meta">
                        ${z.image_url ? `🖼 <a href="${z.image_url}" target="_blank">изображение</a>` : ""}
                        ${z.link_url ? `🔗 <a href="${z.link_url}" target="_blank">ссылка</a>` : ""}
                    </div>
                </div>
                <div class="az-card-actions">
                    <button class="btn btn-outline az-edit-btn" data-id="${z.id}">✏️</button>
                    <button class="btn btn-outline az-topup-btn" data-id="${z.id}">➕ ⭐</button>
                </div>
            </div>
        `).join("");

        el.querySelectorAll(".az-edit-btn").forEach(btn => {
            btn.onclick = () => openEditZone(btn.dataset.id);
        });
        el.querySelectorAll(".az-topup-btn").forEach(btn => {
            btn.onclick = () => openTopUpZone(btn.dataset.id);
        });
    } catch (e) {
        el.innerHTML = `<p style="color:var(--color-danger);">${e.message}</p>`;
    }
}

let topUpZoneId = null;
function openTopUpZone(zoneId) {
    topUpZoneId = zoneId;
    document.getElementById("topUpStars").value = "";
    openModal("topUpZoneModal");
}

async function handleTopUp() {
    if (!topUpZoneId) return;
    const stars = parseInt(document.getElementById("topUpStars").value);
    if (!stars || stars < 1000) { showToast("Минимум 1000 ⭐", "error"); return; }
    try {
        const payBtn = document.getElementById("confirmTopUpBtn");
        if (payBtn) { payBtn.disabled = true; payBtn.textContent = "⏳ Создание счёта..."; }
        const data = await createStarInvoice("top_up", {
            zone_id: topUpZoneId,
            monthly_budget_stars: stars,
        });
        const url = data?.url;
        if (!url) { showToast("Не удалось получить счёт", "error"); return; }
        if (window.Telegram?.WebApp?.openInvoice) {
            window.Telegram.WebApp.openInvoice(url, (status) => {
                if (status === "paid") showToast("✅ Счёт оплачен!", "success");
                else showToast("❌ Оплата не завершена", "error");
            });
            closeModals();
        } else {
            window.location.href = url;
        }
    } catch (e) {
        showToast(e.message, "error");
    } finally {
        const payBtn = document.getElementById("confirmTopUpBtn");
        if (payBtn) { payBtn.disabled = false; payBtn.textContent = "Создать счёт на оплату"; }
    }
}

// ─── Edit zone ───

async function openEditZone(zoneId) {
    editingZoneId = zoneId;
    const token = localStorage.getItem("token");
    try {
        const r = await fetch(`${API}/api/my-advertiser-zones`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok) throw new Error("Ошибка загрузки");
        const zones = await r.json();
        const zone = zones.find(z => z.id === zoneId);
        if (!zone) throw new Error("Зона не найдена");

        document.getElementById("azBusinessName").value = zone.business_name || "";
        document.getElementById("azDescription").value = zone.description || "";
        document.getElementById("azImageUrl").value = zone.image_url || "";
        document.getElementById("azLinkUrl").value = zone.link_url || "";
        document.getElementById("azColor").value = zone.color || "#FFD700";

        openModal("editAdvertiserZoneModal");
    } catch (e) {
        showToast(e.message, "error");
    }
}

async function saveAdvertiserZone() {
    if (!editingZoneId) return;
    const data = {
        business_name: document.getElementById("azBusinessName").value.trim(),
        description: document.getElementById("azDescription").value.trim(),
        image_url: document.getElementById("azImageUrl").value.trim(),
        link_url: document.getElementById("azLinkUrl").value.trim(),
        color: document.getElementById("azColor").value,
    };
    try {
        const token = localStorage.getItem("token");
        const r = await fetch(`${API}/api/my-advertiser-zones/${editingZoneId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
            body: JSON.stringify(data),
        });
        if (!r.ok) throw new Error((await r.json()).detail || "Ошибка");
        closeModals();
        showToast("✅ Зона обновлена", "success");
        loadAdvertiserZones();
    } catch (e) {
        showToast(e.message, "error");
    }
}

// ─── Place point on map (no overlay, map fully interactive) ───

function clearDraw() {
    if (drawLayer) { try { getMap()?.removeLayer(drawLayer); } catch {} drawLayer = null; }
    drawPoint = null;
    drawing = false;
    const map = getMap();
    if (map) map.off("click", onMapClick);
    hideBanner();
}

function onMapClick(e) {
    if (!drawing) return;
    drawPoint = e.latlng;
    if (drawLayer) { try { getMap()?.removeLayer(drawLayer); } catch {} drawLayer = null; }
    drawLayer = L.marker(e.latlng, {
        icon: L.divIcon({
            className: "az-marker",
            html: "<div style='background:#FFD700;width:14px;height:14px;border-radius:50%;border:2px solid #0a0a1a;box-shadow:0 0 10px rgba(255,215,0,0.6);'></div>",
            iconSize: [18, 18],
            iconAnchor: [9, 9],
        })
    }).addTo(getMap());
    hideBanner();
    drawing = false;
    openModal("sponsoredModal");
    document.getElementById("sponsoredDrawStatus").textContent = `✅ Место выбрано: ${e.latlng.lat.toFixed(5)}, ${e.latlng.lng.toFixed(5)}`;
    setupTierSelector();
}

export function openCreateSponsored() {
    closeMenu?.();
    closeModals();
    clearDraw();
    document.getElementById("sponsoredName").value = "";
    drawing = true;
    const map = getMap();
    if (map) map.on("click", onMapClick);
    showBanner("👆 Кликните на карте, чтобы указать место зоны");
}

function getPlacedPoint() {
    if (!drawPoint) return null;
    return { type: "Point", coordinates: [drawPoint.lng, drawPoint.lat] };
}

function getSelectedTierStars() {
    const selected = document.querySelector(".tier-card.selected");
    return selected ? parseInt(selected.dataset.stars) : 3000;
}

function setupTierSelector() {
    document.querySelectorAll(".tier-card").forEach(card => {
        card.onclick = () => {
            document.querySelectorAll(".tier-card").forEach(c => { c.classList.remove("selected"); c.dataset.selected = "false"; });
            card.classList.add("selected");
            card.dataset.selected = "true";
        };
    });
}

async function handleCreateSponsored() {
    const name = document.getElementById("sponsoredName").value.trim();
    const budget = getSelectedTierStars();
    if (!name) { showToast("Укажите название бизнеса", "error"); return; }
    const polygon = getPlacedPoint();
    if (!polygon) { showToast("Укажите точку на карте", "error"); return; }
    try {
        const payBtn = document.getElementById("sponsoredPayBtn");
        if (payBtn) { payBtn.disabled = true; payBtn.textContent = "⏳ Создание счёта..."; }
        const data = await createStarInvoice("sponsored", {
            business_name: name,
            monthly_budget_stars: budget,
            polygon: JSON.stringify(polygon),
        });
        const url = data?.url;
        if (!url) { showToast("Не удалось получить счёт", "error"); return; }
        window.location.href = url;
    } catch (e) {
        showToast(e.message, "error");
    } finally {
        const payBtn = document.getElementById("sponsoredPayBtn");
        if (payBtn) { payBtn.disabled = false; payBtn.textContent = "💳 Оплатить Stars и создать"; }
    }
}

async function loadAdvertiserDashboard() {
    const el = document.getElementById("advertiserDashboardContent");
    el.innerHTML = "Загрузка...";
    try {
        const token = localStorage.getItem("token");
        const r = await fetch(`${API}/api/advertiser/dashboard`, { headers: { Authorization: `Bearer ${token}` } });
        if (!r.ok) throw new Error((await r.json()).detail || "Ошибка");
        const d = await r.json();
        el.innerHTML = `
            <div class="dashboard-grid">
                <div class="dashboard-card"><div class="dashboard-value">${d.active_zones}</div><div class="dashboard-label">Активные зоны</div></div>
                <div class="dashboard-card"><div class="dashboard-value">${d.total_zones}</div><div class="dashboard-label">Всего зон</div></div>
                <div class="dashboard-card"><div class="dashboard-value">${d.total_spent_stars} ⭐</div><div class="dashboard-label">Потрачено Stars</div></div>
                <div class="dashboard-card"><div class="dashboard-value">${d.total_impressions}</div><div class="dashboard-label">Показы</div></div>
                <div class="dashboard-card"><div class="dashboard-value">${d.total_clicks}</div><div class="dashboard-label">Клики</div></div>
            </div>
            ${d.recent_payments.length ? `
                <h4 style="margin:16px 0 8px;font-size:14px;color:var(--color-text-muted);">Последние платежи</h4>
                ${d.recent_payments.map(p => `
                    <div class="az-card">
                        <div class="az-card-header">
                            <span>${p.purpose === "create_zone" ? "Создание зоны" : "Пополнение"}</span>
                            <span class="az-badge ${p.status === 'completed' ? 'az-active' : 'az-inactive'}">${p.status === 'completed' ? '✅' : '⏳'} ${p.amount_stars} ⭐</span>
                        </div>
                    </div>
                `).join("")}
            ` : ""}
        `;
    } catch (e) {
        el.innerHTML = `<p style="color:var(--color-danger);">${e.message}</p>`;
    }
}

async function loadAdvertiserProfile() {
    try {
        const token = localStorage.getItem("token");
        const r = await fetch(`${API}/api/advertiser/profile`, { headers: { Authorization: `Bearer ${token}` } });
        if (!r.ok) throw new Error((await r.json()).detail || "Ошибка");
        const p = await r.json();
        document.getElementById("advProfileBusinessName").value = p.business_name || "";
        document.getElementById("advProfilePhone").value = p.contact_phone || "";
        document.getElementById("advProfileTelegram").value = p.contact_telegram || "";
        document.getElementById("advProfileWebsite").value = p.website || "";
        document.getElementById("advProfileDescription").value = p.description || "";
    } catch (e) {
        showToast(e.message, "error");
    }
}

async function saveAdvertiserProfile() {
    const data = {
        business_name: document.getElementById("advProfileBusinessName").value.trim() || null,
        contact_phone: document.getElementById("advProfilePhone").value.trim() || null,
        contact_telegram: document.getElementById("advProfileTelegram").value.trim() || null,
        website: document.getElementById("advProfileWebsite").value.trim() || null,
        description: document.getElementById("advProfileDescription").value.trim() || null,
    };
    try {
        const token = localStorage.getItem("token");
        const r = await fetch(`${API}/api/advertiser/profile`, {
            method: "PUT",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
            body: JSON.stringify(data),
        });
        if (!r.ok) throw new Error((await r.json()).detail || "Ошибка");
        closeModals();
        showToast("✅ Профиль бизнеса сохранён", "success");
    } catch (e) {
        showToast(e.message, "error");
    }
}

export function initAdvertiser() {
    document.getElementById("createSponsoredBtn")?.addEventListener("click", openCreateSponsored);
    document.getElementById("myAdvertiserZonesBtn")?.addEventListener("click", () => {
        closeMenu?.();
        openModal("advertiserZonesModal");
        loadAdvertiserZones();
    });
    document.getElementById("advertiserDashboardBtn")?.addEventListener("click", () => {
        closeMenu?.();
        openModal("advertiserDashboardModal");
        loadAdvertiserDashboard();
    });
    document.getElementById("advertiserProfileBtn")?.addEventListener("click", () => {
        closeMenu?.();
        openModal("advertiserProfileModal");
        loadAdvertiserProfile();
    });
    document.getElementById("sponsoredDrawClearBtn")?.addEventListener("click", () => {
        closeModals();
        clearDraw();
        openCreateSponsored();
    });
    document.getElementById("closeSponsoredModal")?.addEventListener("click", clearDraw);
    document.getElementById("sponsoredPayBtn")?.addEventListener("click", handleCreateSponsored);
    document.getElementById("saveAdvertiserZoneBtn")?.addEventListener("click", saveAdvertiserZone);
    document.getElementById("saveAdvertiserProfileBtn")?.addEventListener("click", saveAdvertiserProfile);
    document.getElementById("confirmTopUpBtn")?.addEventListener("click", handleTopUp);
    updateAdvertiserUI();
}
