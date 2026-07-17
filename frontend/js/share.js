import { openModal, showToast } from './ui.js';
import { API } from './config.js';

let lastSharedTerritory = null;
let lastRewards = null;

function triggerConfetti() {
    const colors = ['#00e676', '#7c4dff', '#00bcd4', '#ffd700', '#ff1744', '#ff9100'];
    for (let i = 0; i < 60; i++) {
        const el = document.createElement('div');
        el.className = 'confetti-piece';
        el.style.left = Math.random() * 100 + 'vw';
        el.style.top = '-10px';
        el.style.background = colors[Math.floor(Math.random() * colors.length)];
        el.style.borderRadius = Math.random() > 0.5 ? '50%' : '2px';
        el.style.width = (6 + Math.random() * 8) + 'px';
        el.style.height = (6 + Math.random() * 8) + 'px';
        el.style.animationDuration = (2 + Math.random() * 2) + 's';
        el.style.animationDelay = (Math.random() * 0.5) + 's';
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 4000);
    }
}

export function showShareModal(territory, rewards = null) {
    lastSharedTerritory = territory;
    lastRewards = rewards;
    let text = `+${(territory.area / 1000000).toFixed(2)} км²`;
    if (rewards && rewards.length > 0) {
        text += `\n🏪 Спонсорские территории:`;
        document.getElementById("shareRewards").style.display = "block";
        document.getElementById("shareRewards").innerHTML = rewards.map(r =>
            `<div style="font-size:13px;margin:4px 0;">🏪 ${r.business_name}: ${r.your_share_monthly_rub}₽/мес</div>`
        ).join("");
    } else {
        document.getElementById("shareRewards").style.display = "none";
    }
    document.getElementById("shareArea").textContent = text;
    openModal("shareModal");
    triggerConfetti();
}

export async function shareTelegram() {
    if (!lastSharedTerritory) {return;}
    const area = (lastSharedTerritory.area / 1000000).toFixed(2);
    const shareUrl = `${API}/og/${lastSharedTerritory.id}?v=${Date.now()}`;
    let text = `🚴 Я захватил ${area} км² на velo.io!`;
    if (lastRewards && lastRewards.length > 0) {
        const total = lastRewards.reduce((s, r) => s + r.your_share_monthly_rub, 0);
        text += `\n🏪 Зарабатываю ${total}₽/мес на спонсорских зонах!`;
    }
    text += `\n\n🚴 Присоединяйся и получай бонус!`;
    window.open(`https://t.me/share/url?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent(text)}`, '_blank');
}

export function shareCopyLink() {
    if (!lastSharedTerritory) {return;}
    const url = `${API}/og/${lastSharedTerritory.id}?v=${Date.now()}`;
    navigator.clipboard.writeText(url).then(() => {
        showToast("🔗 Ссылка скопирована!", "success");
    });
}
