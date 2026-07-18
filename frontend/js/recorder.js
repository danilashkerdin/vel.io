import { getMap } from './map.js';
import { showToast } from './ui.js';
import { showShareModal } from './share.js';
import { API } from './config.js';
const IS_CAPACITOR = window.__IS_CAPACITOR__ || false;

const STATUS = { IDLE: "idle", RECORDING: "recording", PROCESSING: "processing" };
let state = STATUS.IDLE;
let watchId = null;
let points = [];
let pathLayer = null;
let userMarker = null;
let startTime = null;
let wasInBackground = false;
let lastKnownPosition = null;
let capWatcher = null;

export function isRecording() { return state === STATUS.RECORDING; }

function updateUI() {
    const statusEl = document.getElementById("recordStatus");
    const fab = document.getElementById("fabBtn");
    const stopBtn = document.getElementById("stopRecordBtn");

    if (state === STATUS.RECORDING) {
        if (fab) { fab.textContent = "⏹"; }
        if (stopBtn) { stopBtn.style.display = "flex"; }
        if (statusEl) {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            const min = Math.floor(elapsed / 60);
            const sec = elapsed % 60;
            statusEl.innerHTML = `🔴 Запись... ${String(min).padStart(2, "0")}:${String(sec).padStart(2, "0")} (${points.length} точек)`;
            statusEl.style.display = "flex";
        }
    } else if (state === STATUS.PROCESSING) {
        if (fab) { fab.textContent = "⏳"; }
        if (stopBtn) { stopBtn.style.display = "none"; }
        if (statusEl) { statusEl.textContent = "⏳ Обработка маршрута..."; statusEl.style.display = "flex"; }
    } else {
        if (fab) { fab.textContent = "+"; }
        if (stopBtn) { stopBtn.style.display = "none"; }
        if (statusEl) { statusEl.style.display = "none"; }
    }
}

function clearLayers() {
    const map = getMap();
    if (pathLayer) { try { map?.removeLayer(pathLayer); } catch {} pathLayer = null; }
    if (userMarker) { try { map?.removeLayer(userMarker); } catch {} userMarker = null; }
}

function updatePathOnMap() {
    const map = getMap();
    if (!map) { return; }
    clearLayers();
    if (points.length < 2) { return; }
    const latlngs = points.map(p => [p.lat, p.lng]);
    pathLayer = L.polyline(latlngs, { color: "#FFD700", weight: 4, opacity: 0.8, smoothFactor: 1 }).addTo(map);
    const last = points[points.length - 1];
    if (userMarker) {
        userMarker.setLatLng([last.lat, last.lng]);
    } else {
        const icon = L.divIcon({ html: '<div style="width:20px;height:20px;background:#FFD700;border:3px solid #fff;border-radius:50%;box-shadow:0 0 8px rgba(0,0,0,0.4);"></div>', iconSize: [20, 20], iconAnchor: [10, 10], className: "" });
        userMarker = L.marker([last.lat, last.lng], { icon, zIndexOffset: 10000 }).addTo(map);
    }
}

function distMeters(lat1, lng1, lat2, lng2) {
    const R = 6371000;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLng / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function addPoint(lat, lng, accuracy) {
    const now = Date.now();
    const prev = points[points.length - 1];

    if (prev) {
        const dt = (now - prev.timestamp) / 1000;
        const d = distMeters(prev.lat, prev.lng, lat, lng);
        const speedKmh = dt > 0 ? (d / dt) * 3.6 : 0;

        if (d < 1.5) return;

        if (speedKmh < 3) return;
    }

    lastKnownPosition = { lat, lng, timestamp: now, accuracy: accuracy || 0 };
    points.push(lastKnownPosition);
    updatePathOnMap();
    updateUI();
}

function onPositionSuccess(pos) {
    const { latitude, longitude, accuracy } = pos.coords;
    addPoint(latitude, longitude, accuracy);
}

function onPositionError(err) {
    console.error("Geolocation error:", err.message);
    if (err.code === 1) { stopRecording("Доступ к геолокации запрещён"); }
}

function getCapacitorGeolocation() {
    try {
        const cap = window.Capacitor;
        if (cap?.Plugins?.Geolocation) return cap.Plugins.Geolocation;
    } catch {}
    return null;
}

async function startWatch() {
    const capGeo = IS_CAPACITOR ? getCapacitorGeolocation() : null;

    if (capGeo) {
        if (capWatcher) {
            try { await capWatcher.remove(); } catch {}
            capWatcher = null;
        }
        capWatcher = await capGeo.watchPosition(
            { enableHighAccuracy: true, timeout: 5000 },
            (pos, err) => {
                if (err) { onPositionError(err); return; }
                if (pos) {
                    addPoint(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy);
                }
            }
        );
        return;
    }

    if (watchId !== null) {
        navigator.geolocation.clearWatch(watchId);
    }
    watchId = navigator.geolocation.watchPosition(onPositionSuccess, onPositionError, {
        enableHighAccuracy: true,
        timeout: 5000,
        maximumAge: 3000,
    });
}

function stopWatch() {
    if (capWatcher) {
        try { capWatcher.remove(); } catch {}
        capWatcher = null;
    }
    if (watchId !== null) { navigator.geolocation.clearWatch(watchId); watchId = null; }
    if (IS_CAPACITOR && window.Capacitor?.Plugins?.BackgroundGeolocation) {
        window.Capacitor.Plugins.BackgroundGeolocation.stop();
    }
}

export function startRecording() {
    if (state !== STATUS.IDLE) { return; }
    if (!navigator.geolocation) {
        showToast("⚠ Геолокация не поддерживается браузером", "error");
        return;
    }

    state = STATUS.RECORDING;
    points = [];
    startTime = Date.now();
    wasInBackground = false;

    document.getElementById("recordContainer").style.display = "block";

    startWatch();

    if (IS_CAPACITOR && window.Capacitor?.Plugins?.BackgroundGeolocation) {
        window.Capacitor.Plugins.BackgroundGeolocation.start();
    }

    updateUI();
    showToast("🚴 Запись начата! Поехали!", "success");
}

function stopRecording(errorMsg) {
    if (state === STATUS.IDLE) { return; }
    stopWatch();
    if (errorMsg) {
        state = STATUS.IDLE; points = []; clearLayers(); updateUI();
        document.getElementById("recordContainer").style.display = "none";
        showToast(errorMsg, "error");
        return;
    }
    state = STATUS.PROCESSING;
    updateUI();
    processRecording();
}

export async function stopAndCapture() {
    if (state !== STATUS.RECORDING) { return; }
    stopWatch();
    if (points.length < 5) {
        showToast("⚠ Слишком мало точек. Нужно минимум 5.", "error");
        state = STATUS.IDLE; points = []; clearLayers(); updateUI();
        document.getElementById("recordContainer").style.display = "none";
        return;
    }
    state = STATUS.PROCESSING;
    updateUI();
    await processRecording();
}

async function processRecording() {
    const token = localStorage.getItem("token");
    if (!token) { showToast("❌ Требуется авторизация", "error"); resetAfterRecording(); return; }

    const payload = { points: points.map(p => [p.lat, p.lng, p.timestamp]) };

    try {
        const res = await fetch(`${API}/api/capture-ride`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
            body: JSON.stringify(payload),
            keepalive: true,
        });
        const data = await res.json();
        if (!res.ok) { showToast(data.detail || "Ошибка захвата", "error"); resetAfterRecording(); return; }
        showToast(`✅ +${(data.area / 1_000_000).toFixed(2)} км²!`, "success");
        showShareModal(data, data.sponsored_rewards);
        const { loadTerritories } = await import('./map.js');
        loadTerritories();
    } catch (e) { showToast("❌ " + e.message, "error"); }

    resetAfterRecording();
}

function resetAfterRecording() {
    state = STATUS.IDLE; points = []; clearLayers(); updateUI();
    document.getElementById("recordContainer").style.display = "none";
}

window.__backgroundLocation = (lat, lng, accuracy, timestamp) => {
    if (state !== STATUS.RECORDING) return;
    addPoint(lat, lng, accuracy);
};

export function initRecorder() {
    const stopBtn = document.getElementById("stopRecordBtn");
    if (stopBtn) { stopBtn.onclick = stopAndCapture; }

    document.addEventListener("visibilitychange", () => {
        if (state !== STATUS.RECORDING) { return; }
        if (document.hidden) {
            wasInBackground = true;
            stopWatch();
            updateUI();
        } else if (wasInBackground) {
            wasInBackground = false;
            if (lastKnownPosition) {
                points.push({ ...lastKnownPosition, timestamp: Date.now() });
                updatePathOnMap();
            }
            startWatch();
            updateUI();
        }
    });
}