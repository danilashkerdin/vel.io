import { fetchNotifications, readAllNotifications } from './api.js';

function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

export async function loadNotifications() {
    try {
        const data = await fetchNotifications();

        // Бейдж
        const badge = document.getElementById("notifBadge");
        if (data.unread > 0) {
            badge.textContent = data.unread;
            badge.style.display = "inline";
        } else {
            badge.style.display = "none";
        }

        const html = data.items.length === 0
            ? '<p style="text-align:center;color:#999;">Нет уведомлений</p>'
            : data.items.map(n => `
                <div style="padding:8px 0;border-bottom:1px solid #eee;font-size:13px;opacity:${n.read ? 0.5 : 1};">
                    ${escapeHtml(n.message)}
                    <div style="font-size:11px;color:#999;margin-top:2px;">${new Date(n.created_at).toLocaleString()}</div>
                </div>
            `).join('');

        document.getElementById("notificationsContent").innerHTML = html;
    } catch (e) {
        document.getElementById("notificationsContent").innerHTML = '<p style="color:#f44336;">Ошибка</p>';
    }
}

export async function readAll() {
    await readAllNotifications();
    loadNotifications();
}
