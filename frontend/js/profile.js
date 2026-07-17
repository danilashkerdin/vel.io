import { openModal, showToast } from './ui.js';
import { API } from './config.js';
import { getMap } from './map.js';

export async function showUserProfile(userId, username) {
    document.getElementById("userProfileTitle").textContent = `👤 ${escapeHtml(username)}`;
    document.getElementById("userProfileContent").innerHTML = "Загрузка...";
    openModal("userProfileModal");

    try {
        const res = await fetch(`${API}/api/users/${userId}/territories?limit=50`);
        if (!res.ok) { document.getElementById("userProfileContent").innerHTML = "<p style='color:var(--color-danger);'>Ошибка загрузки</p>"; return; }
        const territories = await res.json();

        if (!territories.length) {
            document.getElementById("userProfileContent").innerHTML = '<p style="text-align:center;color:var(--color-text-muted);padding:20px;">Пока нет территорий</p>';
            document.getElementById("upTerritories").textContent = "0";
            document.getElementById("upArea").textContent = "0";
            return;
        }

        const totalArea = territories.reduce((s, t) => s + t.area, 0);
        document.getElementById("upTerritories").textContent = territories.length;
        document.getElementById("upArea").textContent = (totalArea / 1_000_000).toFixed(2);

        document.getElementById("userProfileContent").innerHTML = territories.map(t => {
            const areaKm2 = (t.area / 1_000_000).toFixed(2);
            const daysLeft = t.expires_at ? Math.max(0, Math.ceil((new Date(t.expires_at) - Date.now()) / 86400000)) : "∞";
            return `
                <div class="up-item" data-polygon='${JSON.stringify(t.polygon).replace(/'/g, "&apos;")}' style="display:flex;align-items:center;gap:10px;padding:8px 10px;border-bottom:1px solid var(--color-border);cursor:pointer;transition:background 0.2s;">
                    <div style="width:28px;height:28px;border-radius:6px;background:${t.color || '#4CAF50'};flex-shrink:0;"></div>
                    <div style="flex:1;min-width:0;">
                        <div style="font-weight:600;font-size:13px;">${escapeHtml(t.name)}</div>
                        <div style="font-size:11px;color:var(--color-text-muted);">${areaKm2} км² · ${daysLeft === "∞" ? "∞" : daysLeft + " дн"}</div>
                    </div>
                </div>
            `;
        }).join("");

        document.querySelectorAll(".up-item").forEach(el => {
            el.onclick = () => {
                try {
                    const polygon = JSON.parse(el.dataset.polygon.replace(/&apos;/g, "'"));
                    const map = getMap();
                    if (map && polygon) {
                        const bounds = L.geoJSON(polygon).getBounds();
                        map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 });
                        document.querySelectorAll(".modal").forEach(m => m.style.display = "none");
                    }
                } catch {}
            };
        });
    } catch (e) {
        document.getElementById("userProfileContent").innerHTML = `<p style="color:var(--color-danger);">${e.message}</p>`;
    }
}

function escapeHtml(s) {
    if (!s) {return "";}
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}