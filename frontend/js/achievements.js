import { openModal, closeModals, showToast } from './ui.js'; // eslint-disable-line no-unused-vars
import { API } from './config.js';
import { authHeaders } from './auth.js';

const ACHIEVEMENT_ICONS = {
    first_capture: "🏴",
    territories_5: "📋",
    territories_10: "📋",
    territories_25: "📋",
    area_1: "📏",
    area_10: "📏",
    area_100: "📏",
    premium: "⭐",
    invite_friend: "🤝",
    sponsored_capture: "💰",
    comeback: "🔄",
    first_share: "🔗",
};

export function renderAchievements(data) {
    const unlocked = [];
    const locked = [];
    for (const a of data) {
        if (a.unlocked) {
            unlocked.push(a);
        } else {
            locked.push(a);
        }
    }
    const html = [];
    if (unlocked.length) {
        html.push(`<div class="ach-section-title">Получено</div>`);
        html.push(`<div class="ach-grid">${unlocked.map(renderAchievement).join("")}</div>`);
    }
    if (locked.length) {
        html.push(`<div class="ach-section-title">Доступные</div>`);
        html.push(`<div class="ach-grid">${locked.map(renderAchievement).join("")}</div>`);
    }
    return html.join("");
}

export async function loadAchievements() {
    const content = document.getElementById("achievementsContent");
    content.innerHTML = "Загрузка...";
    try {
        const res = await fetch(`${API}/api/achievements/all`, {
            headers: authHeaders(),
        });
        if (!res.ok) {
            content.innerHTML = `<div class="error">Ошибка загрузки</div>`;
            return;
        }
        const data = await res.json();
        const unlocked = [];
        const locked = [];
        for (const a of data) {
            if (a.unlocked) {
                unlocked.push(a);
            } else {
                locked.push(a);
            }
        }
        const html = [];
        if (unlocked.length) {
            html.push(`<div class="ach-section-title">Получено</div>`);
            html.push(`<div class="ach-grid">${unlocked.map(renderAchievement).join("")}</div>`);
        }
        if (locked.length) {
            html.push(`<div class="ach-section-title">Доступные</div>`);
            html.push(`<div class="ach-grid">${locked.map(renderAchievement).join("")}</div>`);
        }
        content.innerHTML = html.join("");
    } catch (e) {
        content.innerHTML = `<div class="error">Ошибка загрузки</div>`;
    }
}

function renderAchievement(a) {
    const icon = ACHIEVEMENT_ICONS[a.type] || "🏆";
    const pct = Math.round((a.progress || 0) * 100);
    const cls = a.unlocked ? "ach-card ach-unlocked" : "ach-card ach-locked";
    return `<div class="${cls}">
        <div class="ach-icon">${icon}</div>
        <div class="ach-info">
            <div class="ach-title">${escapeHtml(a.title)}</div>
            <div class="ach-progress-row">
                <div class="ach-progress-bar">
                    <div class="ach-progress-fill" style="width:${pct}%"></div>
                </div>
                <span class="ach-progress-label">${escapeHtml(a.progress_label)}</span>
            </div>
        </div>
    </div>`;
}

function escapeHtml(s) {
    if (!s) { return ""; }
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
}