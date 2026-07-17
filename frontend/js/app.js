import { requireAuth, logout, getUser, isPremium, saveUserData } from './auth.js';
import { initMap, loadTerritories } from './map.js';
import { setupUpload } from './upload.js';
import { editTerritory, saveTerritory, setTerritoriesData } from './editor.js';
import { showShareModal, shareTelegram, shareCopyLink } from './share.js';
import { loadLeaderboard, loadMyTerritories, initLeaderboard } from './leaderboard.js';
import { loadNotifications, readAll } from './notifications.js';
import { openModal, closeModals, showToast, openActionSheet, closeActionSheet } from './ui.js';
import { deleteTerritory, createStarInvoice, fetchPremiumStatus } from './api.js';
import { isTelegramWebApp, waitForTelegram, applyTelegramTheme, tryTelegramAuth } from './telegram.js';
import { initAdvertiser, updateAdvertiserUI, isAdvertiser, openCreateSponsored } from './advertiser.js';
import { initRecorder, isRecording, startRecording } from './recorder.js';
import { initPlanner, startPlanner, stopPlanner } from './planner.js';
import { loadActivity, setFlyToHandler } from './activity.js';
import { showUserProfile } from './profile.js';
import { loadAchievements } from './achievements.js';

window.editTerritory = editTerritory;
window.deleteTerritory = async function(id) {
    if (!confirm("Удалить?")) {return;}
    try {
        await deleteTerritory(id);
        showToast("🗑 Удалено", "success");
        loadTerritories();
    } catch (e) {
        showToast(e.message, "error");
    }
};
window.shareTelegram = shareTelegram;
window.shareCopyLink = shareCopyLink;

// ─── Premium ───

async function handleBuyPremium() {
    try {
        const btn = document.getElementById("buyPremiumBtn");
        if (btn) { btn.disabled = true; btn.textContent = "⏳ Создание счёта..."; }
        const data = await createStarInvoice("premium");
        const url = data?.url;
        if (!url) { showToast("Не удалось получить счёт", "error"); return; }
        if (window.Telegram?.WebApp?.openInvoice) {
            window.Telegram.WebApp.openInvoice(url, (status) => {
                if (status === "paid") { showToast("✅ Премиум активирован!", "success"); refreshPremiumStatus(); }
                else {showToast("❌ Оплата не завершена", "error");}
            });
        } else {
            window.location.href = url;
        }
    } catch (e) {
        showToast(e.message, "error");
    } finally {
        const btn = document.getElementById("buyPremiumBtn");
        if (btn) { btn.disabled = false; btn.textContent = "⭐ Купить Premium · 200 ⭐"; }
    }
}

async function refreshPremiumStatus() {
    try {
        const status = await fetchPremiumStatus();
        const user = getUser();
        user.is_premium = status.is_premium;
        user.captures_count = status.captures_count;
        user.captures_remaining = status.captures_remaining;
        user.free_limit = status.free_limit;
        localStorage.setItem("user", JSON.stringify(user));
    } catch (e) {}
}

// ─── Баланс / Доход ───

async function loadBalance(contentId) {
    const c = document.getElementById(contentId || "atabIncome");
    c.innerHTML = "Загрузка...";
    try {
        const { API } = await import('./config.js');
        const headers = { Authorization: `Bearer ${localStorage.getItem("token")}` };
        const [balRes, txRes] = await Promise.all([
            fetch(`${API}/api/balance`, { headers }),
            fetch(`${API}/api/transactions?limit=5`, { headers }),
        ]);
        if (!balRes.ok) { const e = await balRes.json().catch(()=>({})); c.innerHTML = `<p style="color:var(--color-danger);">${e.detail || 'error'}</p>`; return; }
        const data = await balRes.json();
        const txns = txRes.ok ? await txRes.json() : [];
        let html = `<div style="text-align:center;padding:12px 0;"><div class="balance-amount">${data.balance_rub}₽</div><div class="balance-label">Доступно для вывода</div><div style="font-size:11px;color:var(--color-text-light);">Всего заработано: ${data.total_earned_rub}₽</div></div>`;
        if (data.sponsored_territories?.length) {
            html += `<div style="font-weight:600;margin:12px 0 6px;font-size:13px;">🏪 Мои спонсорские зоны</div>${data.sponsored_territories.map(s => `<div style="display:flex;align-items:center;gap:6px;padding:8px 10px;background:rgba(255,215,0,0.05);border:1px solid rgba(255,215,0,0.15);border-radius:8px;margin-bottom:4px;"><div style="width:8px;height:8px;border-radius:50%;background:${s.color};flex-shrink:0;"></div><div style="flex:1;font-size:12px;">${s.business_name}</div><div style="font-size:11px;color:var(--color-primary);font-weight:500;">+${s.your_share_monthly_rub}₽/мес</div></div>`).join('')}`;
        }
        if (data.balance_rub >= 500) { html += `<button id="requestPayoutBtnTab" class="btn btn-primary" style="width:100%;margin-top:8px;">💰 Запросить выплату ${data.balance_rub}₽</button>`; }
        else if (data.balance_rub > 0) { html += `<div style="text-align:center;font-size:12px;color:var(--color-text-light);margin-top:12px;">Минимум для вывода — 500₽</div>`; }
        c.innerHTML = html;
        const w = document.getElementById("requestPayoutBtnTab");
        if (w) { w.onclick = async () => { if (!confirm(`Запросить выплату ${data.balance_rub}₽?`)) {return;} const r = await fetch(`${API}/api/payment/request-payout`, { method: "POST", headers }); if (r.ok) { showToast("💸 Запрос отправлен!"); loadBalance(contentId); } else { const e = await r.json(); showToast(e.detail || "Ошибка", "error"); } }; }
    } catch (e) { c.innerHTML = `<p style="color:var(--color-danger);">${e.message || 'error'}</p>`; }
}

async function loadReferralLink() {
    try {
        const { API } = await import('./config.js');
        const headers = { Authorization: `Bearer ${localStorage.getItem("token")}` };
        const res = await fetch(`${API}/api/referral/link`, { headers });
        if (res.ok) { const data = await res.json(); document.getElementById("referralLinkBox").textContent = data.link; }
        else { throw new Error("fail"); }
    } catch (e) {
        const user = getUser();
        document.getElementById("referralLinkBox").textContent = user?.id ? `${window.location.origin}/?ref=${user.id}` : window.location.origin;
    }
}

function copyReferralLink() {
    const box = document.getElementById("referralLinkBox");
    if (!box?.textContent) {return;}
    navigator.clipboard.writeText(box.textContent).then(() => showToast("📋 Ссылка скопирована!", "success"));
}

function shareReferralTelegram() {
    const link = document.getElementById("referralLinkBox")?.textContent;
    if (!link) {return;}
    window.open(`https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent("🚴 Захватывай территории на Velo.io! "+link)}`, '_blank');
}

// ─── Switch main tabs ───

function switchToTab(name) {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
    document.querySelectorAll(".tab-page").forEach(p => p.style.display = "none");
    const pageId = "tab" + name.charAt(0).toUpperCase() + name.slice(1);
    const page = document.getElementById(pageId);
    if (page) { page.style.display = "flex"; }
    document.getElementById("map").style.display = name === "map" ? "block" : "none";
    document.getElementById("fabBtn").style.display = name === "map" ? "flex" : "none";
    document.getElementById("actionSheet").classList.remove("open");
}

// ─── Activity sub-tabs ───

function switchActivityTab(name) {
    document.querySelectorAll(".atab-btn").forEach(b => b.classList.toggle("active", b.dataset.atab === name));
    document.querySelectorAll(".atab-content").forEach(c => c.classList.toggle("active", c.dataset.atab === name));
    if (name === "achievements") { loadAchievementsContent(); }
    else if (name === "income") { loadBalance("atabIncome"); }
    else if (name === "territories") { loadMyTerritoriesTab(); }
    else if (name === "feed") { loadActivityContent(); }
    else if (name === "leaderboard") { document.getElementById("leaderboardContent").innerHTML = "Загрузка..."; loadLeaderboard(); }
}

async function loadAchievementsContent() {
    const c = document.getElementById("atabAchievements");
    c.innerHTML = "Загрузка...";
    try {
        const { API } = await import('./config.js');
        const headers = { Authorization: `Bearer ${localStorage.getItem("token")}` };
        const res = await fetch(`${API}/api/achievements/all`, { headers });
        if (!res.ok) { c.innerHTML = "Ошибка"; return; }
        const { renderAchievements } = await import('./achievements.js');
        c.innerHTML = renderAchievements(await res.json());
    } catch { c.innerHTML = "Ошибка"; }
}

async function loadMyTerritoriesTab() {
    const c = document.getElementById("atabTerritories");
    c.innerHTML = "Загрузка...";
    try {
        const { API } = await import('./config.js');
        const headers = { Authorization: `Bearer ${localStorage.getItem("token")}` };
        const res = await fetch(`${API}/api/my-territories?limit=100`, { headers });
        if (!res.ok) { c.innerHTML = "Ошибка"; return; }
        const data = await res.json();
        if (!data.length) { c.innerHTML = '<div style="text-align:center;padding:20px;color:var(--color-text-muted);">Нет территорий</div>'; return; }
        c.innerHTML = data.map(t => {
            const expires = t.expires_at ? timeLeft(new Date(t.expires_at)) : "";
            return `<div style="display:flex;align-items:center;gap:10px;padding:10px;border-bottom:1px solid var(--color-border);font-size:13px;">
                <div style="width:10px;height:10px;border-radius:50%;background:${t.color || '#4CAF50'};flex-shrink:0;"></div>
                <div style="flex:1;"><div>${escapeHtml(t.name)}</div><div style="font-size:11px;color:var(--color-text-muted);">${(t.area/1000000).toFixed(2)} км² · ${expires}</div></div>
            </div>`;
        }).join("");
    } catch { c.innerHTML = "Ошибка"; }
}

function timeLeft(date) {
    const diff = date - new Date();
    if (diff <= 0) { return "истекла"; }
    const days = Math.floor(diff / 86400000);
    const hours = Math.floor((diff % 86400000) / 3600000);
    return `${days}д ${hours}ч`;
}

function escapeHtml(s) {
    if (!s) {return "";}
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
}

async function loadActivityContent() {
    const c = document.getElementById("atabFeed");
    c.innerHTML = "Загрузка...";
    try {
        const { API } = await import('./config.js');
        const res = await fetch(`${API}/api/activity?limit=20`);
        if (!res.ok) { c.innerHTML = "Ошибка"; return; }
        const data = await res.json();
        if (!data.length) { c.innerHTML = '<div style="text-align:center;padding:20px;color:var(--color-text-muted);">Пока ничего</div>'; return; }
        c.innerHTML = data.map(a => {
            const ts = new Date(a.created_at);
            const timeAgo = Math.round((Date.now() - ts) / 60000);
            const label = timeAgo < 1 ? "только что" : timeAgo < 60 ? `${timeAgo} мин назад` : `${Math.floor(timeAgo / 60)} ч назад`;
            return `<div style="display:flex;align-items:center;gap:10px;padding:10px;border-bottom:1px solid var(--color-border);font-size:13px;">
                <div style="font-size:24px;">🚴</div>
                <div style="flex:1;"><strong>${escapeHtml(a.username)}</strong> захватил ${(a.area/1000000).toFixed(2)} км²</div>
                <div style="font-size:11px;color:var(--color-text-muted);">${label}</div>
            </div>`;
        }).join("");
    } catch { c.innerHTML = "Ошибка"; }
}

// ─── Init ───

document.addEventListener("DOMContentLoaded", async () => {
    const isTG = isTelegramWebApp();
    if (isTG) {
        await waitForTelegram();
        applyTelegramTheme();
        const auth = await tryTelegramAuth();
        if (!auth) {
            document.body.innerHTML = '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100dvh;padding:24px;background:#0a0a1a;color:#fff;text-align:center;"><div style="font-size:48px;margin-bottom:16px;">🚴</div><h2 style="font-family:\'Space Grotesk\',sans-serif;margin-bottom:8px;">Velo.io</h2><p style="color:var(--color-text-muted);font-size:14px;margin-bottom:24px;">Не удалось авторизоваться</p><button onclick="window.Telegram?.WebApp?.close()" style="padding:14px 24px;background:var(--gradient-primary);border:none;border-radius:12px;color:#0a0a1a;font-weight:700;font-size:14px;cursor:pointer;">Закрыть</button></div>';
            return;
        }
    } else {
        requireAuth();
    }

    if (new URLSearchParams(window.location.search).get("premium") === "success") {
        await refreshPremiumStatus();
        showToast("⭐ Премиум активирован!", "success");
        window.history.replaceState({}, "", window.location.pathname);
    }

    const user = getUser();
    document.getElementById("profileUsername").textContent = user?.username || "";

    // Main tab switching
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.onclick = () => switchToTab(btn.dataset.tab);
    });

    // Activity sub-tabs
    document.querySelectorAll(".atab-btn").forEach(btn => {
        btn.onclick = () => switchActivityTab(btn.dataset.atab);
    });

    // Init
    initMap();
    setupUpload();
    initLeaderboard();
    initRecorder();
    initPlanner();
    initAdvertiser();
    loadNotifications();

    // FAB / bottom sheet
    document.getElementById("fabBtn").onclick = async () => {
        if (isAdvertiser()) { openCreateSponsored(); return; }
        if (isRecording()) { const { stopAndCapture } = await import('./recorder.js'); stopAndCapture(); return; }
        openActionSheet();
    };
    document.getElementById("bsOverlay").onclick = closeActionSheet;
    document.getElementById("bsRecordBtn").onclick = () => { closeActionSheet(); startRecording(); };
    document.getElementById("bsUploadBtn").onclick = () => { closeActionSheet(); openModal("uploadModal"); };
    document.getElementById("bsPlannerBtn").onclick = () => { closeActionSheet(); startPlanner(); };

    // Profile list
    document.getElementById("pfPremium").onclick = () => { 
        if (isPremium()) { showToast("⭐ Премиум уже активен", "success"); }
        else { openModal("premiumModal"); }
    };
    document.getElementById("pfReferral").onclick = () => { openModal("referralModal"); loadReferralLink(); };
    document.getElementById("pfContacts").onclick = () => { openModal("contactsModal"); };
    document.getElementById("pfNotifications").onclick = () => { openModal("notificationsModal"); loadNotifications(); };
    document.getElementById("pfLogout").onclick = logout;

    // Activity tab: load feed by default on first switch to it
    document.querySelector('.tab-btn[data-tab="activity"]').onclick = () => {
        switchToTab("activity");
        if (!document.getElementById("atabFeed").innerHTML.trim() || document.getElementById("atabFeed").innerHTML === "Загрузка...") {
            switchActivityTab("feed");
        }
    };

    // Modal bindings
    document.querySelectorAll(".modal-close").forEach(b => b.onclick = closeModals);
    document.querySelectorAll(".modal").forEach(m => m.onclick = e => { if (e.target === m) { closeModals(); }});
    document.getElementById("overlay").onclick = closeModals;
    document.getElementById("saveEditBtn").onclick = saveTerritory;
    document.getElementById("buyPremiumBtn").onclick = handleBuyPremium;
    document.getElementById("shareTelegramBtn").onclick = shareTelegram;
    document.getElementById("shareCopyBtn").onclick = shareCopyLink;
    document.getElementById("copyReferralBtn").onclick = copyReferralLink;
    document.getElementById("shareReferralTelegram").onclick = shareReferralTelegram;
    document.getElementById("readAllBtn").onclick = readAll;

    // Notification polling
    setInterval(loadNotifications, 60000);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) { loadNotifications(); } });

    // Service worker
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/sw.js').catch(() => {});
        });
    }

    // Onboarding
    if (!localStorage.getItem("onboarding_done")) {
        setTimeout(() => openModal("onboardingModal"), 300);
        document.getElementById("startBtn").onclick = () => { closeModals(); localStorage.setItem("onboarding_done", "1"); };
    }
});