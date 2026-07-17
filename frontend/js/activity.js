import { openModal, showToast } from './ui.js';
import { API } from './config.js';

export async function loadActivity() {
    const container = document.getElementById("activityContent");
    if (!container) return;
    container.innerHTML = "Загрузка...";

    try {
        const res = await fetch(`${API}/api/activity?limit=30`);
        if (!res.ok) { container.innerHTML = "<p style='color:var(--color-danger);'>Ошибка загрузки</p>"; return; }
        const items = await res.json();

        if (!items.length) {
            container.innerHTML = '<p style="text-align:center;color:var(--color-text-muted);padding:20px;">Пока никто ничего не захватил</p>';
            return;
        }

        container.innerHTML = items.map(item => {
            const areaKm2 = (item.area / 1_000_000).toFixed(2);
            const timeAgo = timeSince(item.created_at);
            const polygonStr = item.polygon ? JSON.stringify(item.polygon).replace(/"/g, '&quot;') : '';
            return `
                <div class="activity-item" data-id="${item.id}" data-user-id="${item.user_id || ''}" data-polygon="${polygonStr}" style="display:flex;align-items:center;gap:10px;padding:10px 12px;border-bottom:1px solid var(--color-border);transition:background 0.2s;">
                    <div style="width:36px;height:36px;border-radius:50%;background:var(--gradient-primary);display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;">🚴</div>
                    <div style="flex:1;min-width:0;">
                        <div style="font-weight:600;font-size:13px;">${escapeHtml(item.name)}</div>
                        <div style="font-size:12px;color:var(--color-text-muted);"><span class="activity-username">${escapeHtml(item.username)}</span> · ${areaKm2} км²</div>
                    </div>
                    <div style="font-size:11px;color:var(--color-text-light);white-space:nowrap;">${timeAgo}</div>
                </div>
            `;
        }).join("");

        container.querySelectorAll(".activity-item").forEach(el => {
            el.onclick = () => {
                const id = el.dataset.id;
                const polygon = el.dataset.polygon ? JSON.parse(el.dataset.polygon) : null;
                if (id && flyToTerritory) {
                    closeModals?.();
                    flyToTerritory(id, polygon);
                }
            };
        });

        container.querySelectorAll(".activity-username").forEach(el => {
            const itemId = el.closest(".activity-item")?.dataset.id;
            const userId = el.closest(".activity-item")?.dataset.userId;
            if (userId) {
                el.style.cursor = "pointer";
                el.style.color = "var(--color-primary)";
                el.addEventListener("click", (e) => {
                    e.stopPropagation();
                    closeModals?.();
                    showUserProfile(userId, el.textContent);
                });
            }
        });
    } catch (e) {
        container.innerHTML = `<p style="color:var(--color-danger);">${e.message}</p>`;
    }
}

let flyToTerritory = null;

export function setFlyToHandler(fn) {
    flyToTerritory = fn;
}

function closeModals() {
    document.querySelectorAll(".modal").forEach(m => m.style.display = "none");
}

function escapeHtml(s) {
    if (!s) return "";
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function timeSince(dateStr) {
    const now = Date.now();
    const then = new Date(dateStr).getTime();
    const diff = Math.floor((now - then) / 1000);
    if (diff < 60) return "только что";
    if (diff < 3600) return `${Math.floor(diff / 60)} мин назад`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} ч назад`;
    if (diff < 604800) return `${Math.floor(diff / 86400)} дн назад`;
    return new Date(dateStr).toLocaleDateString();
}