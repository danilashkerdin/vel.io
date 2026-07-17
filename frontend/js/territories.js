import { getUser, isPremium } from './auth.js';

export function updateStats(territories) {
    const user = getUser();
    const my = territories.filter(t => t.user_id === user.id);
    const totalArea = (my.reduce((s, t) => s + t.area, 0) / 1000000).toFixed(2);

    if (isPremium()) {
        document.getElementById("menuStats").innerHTML = `
            <div>⭐ Premium · Безлимитные захваты</div>
            <div style="font-size:12px;color:#999;">Площадь: ${totalArea} км²</div>
        `;
    } else {
        document.getElementById("menuStats").innerHTML = `
            <div>📊 Захвачено: ${my.length}</div>
            <div style="font-size:12px;color:#999;">Площадь: ${totalArea} км² · 1 территория в неделю</div>
        `;
    }
}
