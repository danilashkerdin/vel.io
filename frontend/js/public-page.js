import { fetchPublicTerritory } from './api.js';

const params = new URLSearchParams(window.location.search);
const id = params.get("t");

if (!id || id === "undefined" || id === "null") {
    document.getElementById("tName").textContent = "Территория не найдена";
    document.getElementById("tArea").textContent = "Не указан ID";
} else {
    load(id);
}

async function load(territoryId) {
    try {
        const res = await fetchPublicTerritory(territoryId);
        if (!res.ok) {
            document.getElementById("tName").textContent = "Территория не найдена";
            document.getElementById("tArea").textContent = res.status === 404 ? "Удалена или не существует" : "Ошибка сервера";
            return;
        }
        const t = await res.json();

        document.getElementById("tName").textContent = t.name || "Безымянный";
        document.getElementById("tArea").textContent = `${(t.area / 1000000).toFixed(2)} км²`;
        document.getElementById("tUser").textContent = `🚴 ${t.username}`;
        document.getElementById("tDesc").textContent = t.description || "";

        if (t.link_url) {
            const link = document.createElement("a");
            link.href = t.link_url;
            link.target = "_blank";
            link.textContent = "🔗 Ссылка";
            link.style.display = "block";
            link.style.marginBottom = "8px";
            link.style.fontSize = "13px";
            link.style.color = "#4CAF50";
            document.getElementById("tDesc").after(link);
        }

        const map = L.map("map", { attributionControl: false }).setView([55.75, 37.61], 12);
        L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
            attribution: "© OpenStreetMap, © CARTO",
        }).addTo(map);
        L.control.attribution({ prefix: false }).addTo(map);

        const layer = L.geoJSON(t.polygon, {
            style: {
                color: t.color || "#4CAF50",
                fillColor: t.color || "#4CAF50",
                fillOpacity: 0.3,
                weight: 2,
            },
        }).addTo(map);

        map.fitBounds(layer.getBounds(), { padding: [30, 30] });
    } catch (e) {
        document.getElementById("tName").textContent = "Ошибка загрузки";
        console.error(e);
    }
}
