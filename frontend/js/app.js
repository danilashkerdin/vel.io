import { requireAuth, logout, getUser, isPremium, saveUserData } from './auth.js';
import { API } from './config.js';
import { initMap, loadTerritories } from './map.js';
import { setupUpload } from './upload.js';
import { editTerritory, saveTerritory, setTerritoriesData } from './editor.js';
import { showShareModal, shareTelegram, shareCopyLink } from './share.js';
import { loadLeaderboard, loadMyTerritories, initLeaderboard } from './leaderboard.js';
import { loadNotifications, readAll } from './notifications.js';
import { toggleMenu, closeMenu, openModal, closeModals, showToast } from './ui.js';
import { deleteTerritory, createStarInvoice, fetchPremiumStatus } from './api.js';
import { isTelegramWebApp, waitForTelegram, applyTelegramTheme, tryTelegramAuth } from './telegram.js';
import { initAdvertiser, updateAdvertiserUI, isAdvertiser, openCreateSponsored } from './advertiser.js';
import { initRecorder, isRecording, startRecording } from './recorder.js';
import { initPlanner, startPlanner, isPlannerActive, stopPlanner } from './planner.js';
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

function updatePremiumMenu() {
    const menuPremium = document.getElementById("menuPremium");
    if (isPremium()) {
        menuPremium.innerHTML = "⭐ Премиум активен";
        menuPremium.className = "menu-item";
    } else {
        menuPremium.innerHTML = "⭐ Купить Premium";
        menuPremium.className = "menu-item menu-premium";
    }
}

// ─── Баланс / Доход ───

async function loadBalance() {
    const content = document.getElementById("balanceContent");
    content.innerHTML = "Загрузка...";

    try {
        const { API } = await import('./config.js');
        const headers = { Authorization: `Bearer ${localStorage.getItem("token")}` };

        const [balRes, txRes] = await Promise.all([
            fetch(`${API}/api/balance`, { headers }),
            fetch(`${API}/api/transactions?limit=5`, { headers }),
        ]);
        if (!balRes.ok) { const err = await balRes.json().catch(()=>({})); content.innerHTML = `<p style="color:var(--color-danger);">${err.detail || 'Ошибка загрузки'}</p>`; return; }

        const data = await balRes.json();
        const txns = txRes.ok ? await txRes.json() : [];

        let html = `
            <div style="text-align:center;padding:12px 0;">
                <div class="balance-amount">${data.balance_rub}₽</div>
                <div class="balance-label">Доступно для вывода</div>
                <div style="font-size:11px;color:var(--color-text-light);">Всего заработано: ${data.total_earned_rub}₽</div>
            </div>
        `;

        // Спонсорские территории
        if (data.sponsored_territories && data.sponsored_territories.length > 0) {
            html += `
                <div style="font-weight:600;margin:12px 0 6px;font-size:13px;">🏪 Мои спонсорские зоны</div>
                ${data.sponsored_territories.map(s => `
                    <div style="display:flex;align-items:center;gap:6px;padding:8px 10px;background:rgba(255,215,0,0.05);border:1px solid rgba(255,215,0,0.15);border-radius:8px;margin-bottom:4px;">
                        <div style="width:8px;height:8px;border-radius:50%;background:${s.color};flex-shrink:0;"></div>
                        <div style="flex:1;font-size:12px;">${s.business_name}</div>
                        <div style="font-size:11px;color:var(--color-primary);font-weight:500;">+${s.your_share_monthly_rub}₽/мес</div>
                    </div>
                `).join('')}
            `;
        }

        // Выплаты
        if (data.balance_rub >= 500) {
            html += `
                <div style="font-weight:600;margin:12px 0 6px;font-size:13px;">💸 Вывести средства</div>
                <button id="requestPayoutBtn" class="btn btn-primary">💰 Запросить выплату ${data.balance_rub}₽</button>
            `;
        } else if (data.balance_rub > 0) {
            html += `<div style="text-align:center;font-size:12px;color:var(--color-text-light);margin-top:12px;">Минимум для вывода — 500₽</div>`;
        }

        // История
        if (txns.length > 0) {
            html += `<div style="font-weight:600;margin:12px 0 6px;font-size:13px;">📜 Последние операции</div>`;
            html += txns.map(t => `
                <div style="display:flex;justify-content:space-between;padding:5px 0;font-size:12px;border-bottom:1px solid var(--color-border);">
                    <span style="color:var(--color-text-muted);">${t.description}</span>
                    <span style="font-weight:500;color:${t.amount_rub > 0 ? 'var(--color-primary)' : 'var(--color-danger)'};">${t.amount_rub > 0 ? '+' : ''}${t.amount_rub}₽</span>
                </div>
            `).join('');
        }

        content.innerHTML = html;

        // Event listeners
        const withdrawBtn = document.getElementById("requestPayoutBtn");
        if (withdrawBtn) {
            withdrawBtn.onclick = async () => {
                if (!confirm(`Запросить выплату ${data.balance_rub}₽? Администратор обработает запрос.`)) {return;}
                const r = await fetch(`${API}/api/payment/request-payout`, { method: "POST", headers });
                if (r.ok) { showToast("💸 Запрос на выплату отправлен администратору!", "success"); loadBalance(); }
                else { const e = await r.json(); showToast(e.detail || "Ошибка", "error"); }
            };
        }

    } catch (e) {
        content.innerHTML = `<p style="color:var(--color-danger);">${e.message || 'Ошибка загрузки'}</p>`;
    }
}

// ─── Реферальная система ───

let _referralLink = "";

async function loadReferralLink() {
    try {
        const { API } = await import('./config.js');
        const headers = { Authorization: `Bearer ${localStorage.getItem("token")}` };
        const res = await fetch(`${API}/api/referral/link`, { headers });
        if (res.ok) {
            const data = await res.json();
            _referralLink = data.link;
            document.getElementById("referralLinkBox").textContent = _referralLink;
        } else {
            throw new Error("Не удалось получить реферальную ссылку");
        }
    } catch (e) {
        const user = getUser();
        _referralLink = user?.id ? `${window.location.origin}/?ref=${user.id}` : window.location.origin;
        document.getElementById("referralLinkBox").textContent = _referralLink;
    }
}

function copyReferralLink() {
    if (!_referralLink) {return;}
    navigator.clipboard.writeText(_referralLink).then(() => {
        showToast("📋 Ссылка скопирована!", "success");
    });
}

function shareReferralTelegram() {
    if (!_referralLink) {return;}
    const text = `🚴 Захватывай территории на Velo.io! Я уже там. Переходи по ссылке:\n${_referralLink}`;
    window.open(`https://t.me/share/url?url=${encodeURIComponent(_referralLink)}&text=${encodeURIComponent(text)}`, '_blank');
}

// ─── Init ───

document.addEventListener("DOMContentLoaded", async () => {
    const __IS_CAPACITOR__ = window.__IS_CAPACITOR__ || false;
    const isPWA = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
    // Telegram Mini App: логин через initData
    const isTG = isTelegramWebApp();
    if (isTG) {
        // Ждём SDK (загружается асинхронно)
        await waitForTelegram();
        applyTelegramTheme();
        const auth = await tryTelegramAuth();
        if (!auth) {
            // В Mini App не редиректим на auth.html — показываем inline-ошибку
            document.body.innerHTML = `
                <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100dvh;padding:24px;background:#0a0a1a;color:#fff;text-align:center;">
                    <div style="font-size:48px;margin-bottom:16px;">🚴</div>
                    <h2 style="font-family:'Space Grotesk',sans-serif;margin-bottom:8px;">Velo.io</h2>
                    <p style="color:var(--color-text-muted);font-size:14px;margin-bottom:24px;">Не удалось авторизоваться. Попробуй открыть через Menu Button бота <strong>@vel_io_bot</strong>.</p>
                    <button onclick="window.Telegram?.WebApp?.close()" style="padding:14px 24px;background:var(--gradient-primary);border:none;border-radius:12px;color:#0a0a1a;font-weight:700;font-size:14px;cursor:pointer;">Закрыть</button>
                </div>
            `;
            return;
        }
    } else {
        requireAuth();
    }

    const params = new URLSearchParams(window.location.search);
    if (params.get("premium") === "success") {
        await refreshPremiumStatus();
        showToast("⭐ Премиум активирован!", "success");
        window.history.replaceState({}, "", window.location.pathname);
    }
    const user = getUser();
    document.getElementById("menuUsername").textContent = user.username || "";
    const freeLimit = user.free_limit || 1;
    const bonuses = user.referral_bonuses || 0;
    const limitEl = document.getElementById("premiumFreeLimit");
    if (limitEl) {
        limitEl.textContent = freeLimit;
        if (bonuses > 0) {
            limitEl.textContent += ` (+${bonuses} за рефералов)`;
        }
    }

    initMap();
    setupUpload();
    updatePremiumMenu();
    initAdvertiser();
    initRecorder();
    initLeaderboard();
    initPlanner();

    if (!localStorage.getItem("onboarding_done")) {
        setTimeout(() => openModal("onboardingModal"), 300);
        const finishOnboarding = () => {
            closeModals();
            localStorage.setItem("onboarding_done", "1");
        };
        document.getElementById("startBtn").onclick = finishOnboarding;
    }
    setFlyToHandler(async (id, polygon) => {
        closeModals();
        const map = (await import('./map.js')).getMap();
        if (map && polygon) {
            try {
                const bounds = L.geoJSON(polygon).getBounds();
                map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 });
            } catch {}
        }
    });

    document.getElementById("burgerBtn").onclick = toggleMenu;
    document.getElementById("closeMenuBtn").onclick = closeMenu;
    document.getElementById("overlay").onclick = () => { closeMenu(); closeModals(); };
    document.getElementById("fabBtn").onclick = async () => {
        closeMenu();
        if (isRecording()) {
            const { stopAndCapture } = await import('./recorder.js');
            stopAndCapture();
            return;
        }
        if (isAdvertiser()) {openCreateSponsored();}
        else {startRecording();}
    };
    document.getElementById("menuUploadBtn").onclick = () => { closeMenu(); openModal("uploadModal"); };
    document.getElementById("menuPlannerBtn").onclick = () => { closeMenu(); startPlanner(); };
    document.getElementById("menuRecordBtn").onclick = () => { closeMenu(); startRecording(); };
    document.getElementById("menuActivity").onclick = () => { closeMenu(); openModal("activityModal"); loadActivity(); };
    document.getElementById("menuLeaderboard").onclick = () => { closeMenu(); openModal("leaderboardModal"); loadLeaderboard(); };
    document.getElementById("menuPremium").onclick = () => {
        closeMenu();
        if (isPremium()) {showToast("⭐ Премиум уже активен", "success");}
        else {openModal("premiumModal");}
    };
    document.getElementById("menuBalance").onclick = () => { closeMenu(); openModal("balanceModal"); loadBalance(); };
    document.getElementById("menuAchievements").onclick = () => { closeMenu(); openModal("achievementsModal"); loadAchievements(); };
    document.getElementById("menuReferral").onclick = () => { closeMenu(); openModal("referralModal"); loadReferralLink(); };
    document.getElementById("menuContacts").onclick = () => { closeMenu(); openModal("contactsModal"); };
    document.getElementById("menuLogout").onclick = logout;
    document.getElementById("saveEditBtn").onclick = saveTerritory;
    document.getElementById("menuMyTerritories").onclick = () => { closeMenu(); openModal("myTerritoriesModal"); loadMyTerritories(); };
    document.getElementById("menuNotifications").onclick = () => { closeMenu(); openModal("notificationsModal"); loadNotifications(); };
    document.getElementById("readAllBtn").onclick = readAll;
    document.getElementById("buyPremiumBtn").onclick = handleBuyPremium;
    document.getElementById("shareTelegramBtn").onclick = shareTelegram;
    document.getElementById("shareCopyBtn").onclick = shareCopyLink;
    document.getElementById("copyReferralBtn").onclick = copyReferralLink;
    document.getElementById("shareReferralTelegram").onclick = shareReferralTelegram;

    let notifInterval = null;
    function startNotifPolling() {
        if (notifInterval) {return;}
        notifInterval = setInterval(loadNotifications, 60000);
    }
    function stopNotifPolling() {
        if (notifInterval) { clearInterval(notifInterval); notifInterval = null; }
    }
    loadNotifications();
    startNotifPolling();
    document.addEventListener("visibilitychange", () => {
        if (document.hidden) {stopNotifPolling();}
        else { loadNotifications(); startNotifPolling(); }
    });

    // Keep Render free instance alive
    setInterval(() => { fetch(`${API}/api/health`).catch(() => {}); }, 60000);

    document.querySelectorAll(".modal-close").forEach(b => b.onclick = closeModals);
    document.querySelectorAll(".modal").forEach(m => m.onclick = e => { if (e.target === m) {closeModals();} });

    // Баннер установки нативного приложения
    if (!__IS_CAPACITOR__) {
        if (!isPWA && !isTG) {
            const banner = document.getElementById("installBanner");
            const closeBtn = document.getElementById("installBannerClose");
            const installBtn = document.getElementById("installAppBtn");

            installBtn.onclick = () => {
                if (navigator.share) {
                    navigator.share({
                        title: "Velo.io",
                        text: "🚴 Захватывай территории на Velo.io!",
                        url: "https://vel-io.onrender.com"
                    });
                } else {
                    window.open("https://vel-io.onrender.com", "_blank");
                }
                banner.style.display = "none";
                localStorage.setItem("install_banner_dismissed", "1");
            };
            closeBtn.onclick = () => {
                banner.style.display = "none";
                localStorage.setItem("install_banner_dismissed", "1");
            };

            if (!localStorage.getItem("install_banner_dismissed")) {
                setTimeout(() => { banner.style.display = "block"; }, 5000);
            }
        } else if (isTG) {
            const banner = document.getElementById("installBanner");
            const closeBtn = document.getElementById("installBannerClose");
            const installBtn = document.getElementById("installAppBtn");

            if (isTG) {
                document.querySelector(".install-banner-text").textContent = "📱 Открыть в нативном приложении";
                installBtn.textContent = "Установить";
                const botUsername = "vel_io_bot";
                const appUrl = "https://vel-io.onrender.com";
                (async () => {
                    const { isAndroid, isIOS } = await import('./telegram.js');
                    if (isAndroid()) {
                        installBtn.onclick = () => {
                            window.open("https://rustore.ru/app/io.velo.app", "_blank");
                            banner.style.display = "none";
                        };
                    } else if (isIOS()) {
                        installBtn.onclick = () => {
                            window.open("https://apps.apple.com/app/idXXXXXXXXX", "_blank");
                            banner.style.display = "none";
                        };
                    } else {
                        installBtn.onclick = () => {
                            window.open(appUrl, "_blank");
                            banner.style.display = "none";
                        };
                    }
                })();
            }

            closeBtn.onclick = () => {
                banner.style.display = "none";
                localStorage.setItem("install_banner_dismissed", "1");
            };
            if (!localStorage.getItem("install_banner_dismissed")) {
                setTimeout(() => { banner.style.display = "block"; }, 3000);
            }
        }
    }

    // iOS Safari — PWA установка
    if (isTG || __IS_CAPACITOR__ || isPWA) {
        // не показываем в TG / нативном / PWA
    } else if (/iPad|iPhone|iPod/.test(navigator.userAgent) && !localStorage.getItem("ios_pwa_hint_dismissed")) {
        setTimeout(() => {
            const hint = document.getElementById("iosPwaHint");
            if (hint) {
                hint.classList.add("visible");
                document.getElementById("overlay").classList.add("visible");
                document.getElementById("iosPwaHintClose").onclick = () => {
                    hint.classList.remove("visible");
                    document.getElementById("overlay").classList.remove("visible");
                };
                document.getElementById("iosPwaHintGotIt").onclick = () => {
                    hint.classList.remove("visible");
                    document.getElementById("overlay").classList.remove("visible");
                };
                localStorage.setItem("ios_pwa_hint_dismissed", "1");
            }
        }, 4000);
    }

    if (!__IS_CAPACITOR__ && 'serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/sw.js')
                .then((reg) => {
                    console.log('[SW] Registered with scope:', reg.scope);
                    reg.addEventListener('updatefound', () => {
                        const newWorker = reg.installing;
                        if (!newWorker) {return;}
                        newWorker.addEventListener('statechange', () => {
                            if (newWorker.state === 'activated' && navigator.serviceWorker.controller) {
                                showToast("🔄 Обновление загружено. Обновите страницу.", "success");
                            }
                        });
                    });
                })
                .catch((err) => console.warn('[SW] Registration failed:', err));
        });
    }
});
