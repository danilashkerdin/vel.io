import { fetchLeaderboard, fetchMyTerritories } from './api.js';
import { getUser } from './auth.js';

let _period = "all";
let _sort = "area";

function escapeHtml(str) {
    if (!str) {return "";}
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function timeLeft(expiresAt) {
    if (!expiresAt) { return { text: "∞", color: "" }; }
    const diff = new Date(expiresAt) - Date.now();
    if (diff <= 0) { return { text: "Истекла", color: "#f44336" }; }
    const days = Math.floor(diff / 86400000);
    const hours = Math.floor((diff % 86400000) / 3600000);
    if (days > 0) { return { text: `${days} д ${hours} ч`, color: days > 7 ? "#4CAF50" : "#FF9800" }; }
    return { text: `${hours} ч ${Math.floor((diff % 3600000) / 60000)} мин`, color: "#f44336" };
}

function setActive(btnId) {
    document.querySelectorAll(".lb-toggle").forEach(b => b.classList.remove("active"));
    const btn = document.getElementById(btnId);
    if (btn) { btn.classList.add("active"); }
}

export async function loadLeaderboard(period, sort) {
    if (period !== undefined) { _period = period; }
    if (sort !== undefined) { _sort = sort; }
    try {
        const data = await fetchLeaderboard(_period, _sort);
        const user = getUser();
        const html = data.length === 0
            ? '<p style="text-align:center;color:#999;">Пока никто не захватил территорию</p>'
            : data.map((u, i) => `
                <div style="display:flex;align-items:center;padding:8px 0;border-bottom:1px solid #eee;">
                    <span style="font-weight:bold;width:30px;color:#999;">${i + 1}</span>
                    <span style="flex:1;font-weight:${escapeHtml(u.username) === escapeHtml(user.username) ? 'bold' : 'normal'};">
                        ${escapeHtml(u.username)}${u.username === user.username ? ' ← вы' : ''}
                    </span>
                    <span style="color:#666;font-size:13px;text-align:right;">
                        ${(u.total_area / 1000000).toFixed(2)} км²<br>
                        <span style="font-size:11px;color:#999;">${u.territories_count} тер.</span>
                    </span>
                </div>
            `).join('');
        document.getElementById("leaderboardContent").innerHTML = html;
    } catch (e) {
        document.getElementById("leaderboardContent").innerHTML = '<p style="color:#f44336;">Ошибка загрузки</p>';
    }
}

export function initLeaderboard() {
    document.querySelectorAll(".lb-period-btn").forEach(btn => {
        btn.onclick = () => {
            setActive(btn.id);
            loadLeaderboard(btn.dataset.period, _sort);
        };
    });
    document.querySelectorAll(".lb-sort-btn").forEach(btn => {
        btn.onclick = () => {
            setActive(btn.id);
            loadLeaderboard(_period, btn.dataset.sort);
        };
    });
}

export async function loadMyTerritories() {
    try {
        const data = await fetchMyTerritories();
        const html = data.length === 0
            ? '<p style="text-align:center;color:#999;">У вас пока нет территорий</p>'
            : data.map(t => `
                <div style="display:flex;align-items:center;padding:8px 0;border-bottom:1px solid #eee;gap:8px;">
                    <div style="width:12px;height:12px;border-radius:3px;background:${t.color || '#4CAF50'};flex-shrink:0;"></div>
                    <div style="flex:1;min-width:0;">
                        <div style="font-size:13px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(t.name) || 'Безымянный'}</div>
                        <div style="font-size:11px;color:#999;">${new Date(t.created_at).toLocaleDateString()} ${timeLeft(t.expires_at).text !== "∞" ? `· <span style="color:${timeLeft(t.expires_at).color};">${timeLeft(t.expires_at).text}</span>` : ''}</div>
                    </div>
                    <span style="font-size:12px;color:#666;white-space:nowrap;">${(t.area / 1000000).toFixed(2)} км²</span>
                </div>
            `).join('');
        document.getElementById("myTerritoriesContent").innerHTML = html;
    } catch (e) {
        document.getElementById("myTerritoriesContent").innerHTML = '<p style="color:#f44336;">Ошибка загрузки</p>';
    }
}