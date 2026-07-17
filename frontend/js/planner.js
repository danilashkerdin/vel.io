import { getMap } from './map.js';
import { API } from './config.js';
import { showToast } from './ui.js';

let markers = [];
let routeLine = null;
let previewPolygon = null;
let active = false;

function clear() {
    markers.forEach(m => { try { getMap()?.removeLayer(m); } catch {} });
    markers = [];
    if (routeLine) { try { getMap()?.removeLayer(routeLine); } catch {} routeLine = null; }
    if (previewPolygon) { try { getMap()?.removeLayer(previewPolygon); } catch {} previewPolygon = null; }
    document.getElementById("plannerInfo").textContent = "";
}

export function isPlannerActive() { return active; }

export function startPlanner() {
    if (active) { stopPlanner(); return; }

    const map = getMap();
    if (!map) { return; }

    active = true;
    clear();
    document.getElementById("plannerBar").style.display = "flex";
    document.getElementById("plannerInfo").textContent = "Кликай по карте, чтобы поставить точки маршрута";

    map.on("click", onMapClick);
}

export function stopPlanner() {
    active = false;
    const map = getMap();
    if (map) { map.off("click", onMapClick); }
    clear();
    document.getElementById("plannerBar").style.display = "none";
}

async function onMapClick(e) {
    if (!active) { return; }
    const latlng = e.latlng;
    const marker = L.circleMarker([latlng.lat, latlng.lng], {
        radius: 6, color: "#FF5722", fillColor: "#FF5722", fillOpacity: 1,
    }).addTo(getMap()).bindPopup(`<b>${latlng.lat.toFixed(5)}, ${latlng.lng.toFixed(5)}</b>`);

    markers.push({ marker, lat: latlng.lat, lng: latlng.lng });
    updateRoute();
}

function updateRoute() {
    if (routeLine) { try { getMap()?.removeLayer(routeLine); } catch {} routeLine = null; }
    if (previewPolygon) { try { getMap()?.removeLayer(previewPolygon); } catch {} previewPolygon = null; }

    if (markers.length < 2) { return; }

    const latlngs = markers.map(m => [m.lat, m.lng]);
    routeLine = L.polyline(latlngs, { color: "#FF5722", weight: 3, dashArray: "8,8" }).addTo(getMap());
    document.getElementById("plannerInfo").textContent = `${markers.length} точек. Нажми «Построить маршрут»`;
}

export async function buildRoute() {
    if (markers.length < 3) {
        showToast("Поставь минимум 3 точки для замкнутого маршрута", "error");
        return;
    }

    const pts = markers.map(m => [m.lat, m.lng]);
    document.getElementById("plannerInfo").textContent = "Строим маршрут...";

    try {
        const res = await fetch(`${API}/api/plan-route`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ points: pts }),
        });
        const data = await res.json();
        if (!res.ok) { showToast(data.detail || "Ошибка", "error"); return; }

        if (previewPolygon) { try { getMap()?.removeLayer(previewPolygon); } catch {} }
        previewPolygon = L.geoJSON(data.polygon, {
            style: { color: "#FF5722", fillColor: "#FF5722", fillOpacity: 0.15, weight: 2 },
        }).addTo(getMap());

        if (routeLine) { try { getMap()?.removeLayer(routeLine); } catch {} }
        const routeLatlngs = data.route.map(p => [p[0], p[1]]);
        routeLine = L.polyline(routeLatlngs, { color: "#FF5722", weight: 4 }).addTo(getMap());

        getMap().fitBounds(routeLine.getBounds().pad(0.1));

        document.getElementById("plannerInfo").textContent =
            `📏 ${(data.area / 1_000_000).toFixed(2)} км² · ${data.route.length} точек`;
    } catch (e) {
        showToast("Ошибка: " + e.message, "error");
    }
}

export function initPlanner() {
    document.getElementById("plannerBuildBtn").onclick = buildRoute;
    document.getElementById("plannerClearBtn").onclick = () => { clear(); };
    document.getElementById("plannerCancelBtn").onclick = stopPlanner;
}