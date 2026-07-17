import { getMap } from './map.js';
import { showToast } from './ui.js';
import { showShareModal } from './share.js';
import { API } from './config.js';

let recording = false;
let watchId = null;
let points = [];
let pathLayer = null;
let startTime = null;

const STATUS = {
    IDLE: "idle",
    RECORDING: "recording",
    PROCESSING: "processing",
};

let state = STATUS.IDLE;

export function isRecording() {
    return state === STATUS.RECORDING;
}

function getFabBtn() {
    return document.getElementById("fabBtn");
}

function getStatusEl() {
    return document.getElementById("recordStatus");
}

function getStopBtn() {
    return document.getElementById("stopRecordBtn");
}

function updateUI() {
    const statusEl = getStatusEl();
    const fab = getFabBtn();
    const stopBtn = getStopBtn();

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
        if (statusEl) {
            statusEl.textContent = "⏳ Обработка маршрута...";
            statusEl.style.display = "flex";
        }
    } else {
        if (fab) { fab.textContent = "+"; }
        if (stopBtn) { stopBtn.style.display = "none"; }
        if (statusEl) { statusEl.style.display = "none"; }
    }
}

function updatePathOnMap() {
    const map = getMap();
    if (!map) return;

    if (pathLayer) {
        try { map.removeLayer(pathLayer); } catch {}
        pathLayer = null;
    }

    if (points.length < 2) return;

    const latlngs = points.map(p => [p.lat, p.lng]);
    pathLayer = L.polyline(latlngs, {
        color: "#FFD700",
        weight: 4,
        opacity: 0.8,
        smoothFactor: 1,
    }).addTo(map);

    if (points.length === 1) {
        const last = points[points.length - 1];
        L.circleMarker([last.lat, last.lng], {
            radius: 6,
            color: "#FFD700",
            fillColor: "#FFD700",
            fillOpacity: 1,
        }).addTo(pathLayer);
    }
}

function onPositionSuccess(pos) {
    const { latitude, longitude, accuracy } = pos.coords;
    const now = Date.now();

    points.push({
        lat: latitude,
        lng: longitude,
        timestamp: now,
        accuracy: accuracy,
    });

    updatePathOnMap();
    updateUI();
}

function onPositionError(err) {
    console.error("Geolocation error:", err.message);
    showToast("⚠ Ошибка GPS: " + err.message, "error");
    if (err.code === 1) {
        stopRecording("Доступ к геолокации запрещён");
    }
}

export function startRecording() {
    if (state !== STATUS.IDLE) return;
    if (!navigator.geolocation) {
        showToast("⚠ Геолокация не поддерживается браузером", "error");
        return;
    }

    state = STATUS.RECORDING;
    points = [];
    startTime = Date.now();

    document.getElementById("recordContainer").style.display = "block";

    const map = getMap();
    if (map) {
        map.on("click", function blockClick(e) {
            if (state === STATUS.RECORDING) {
                L.DomEvent.stopPropagation(e);
            }
        });
    }

    watchId = navigator.geolocation.watchPosition(
        onPositionSuccess,
        onPositionError,
        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 5000,
        }
    );

    updateUI();
    showToast("🚴 Запись начата! Поехали!", "success");
}

function stopRecording(errorMsg) {
    if (state === STATUS.IDLE) return;

    if (watchId !== null) {
        navigator.geolocation.clearWatch(watchId);
        watchId = null;
    }

    if (errorMsg) {
        state = STATUS.IDLE;
        points = [];
        if (pathLayer) {
            try { getMap()?.removeLayer(pathLayer); } catch {}
            pathLayer = null;
        }
        updateUI();
        document.getElementById("recordContainer").style.display = "none";
        showToast(errorMsg, "error");
        return;
    }

    state = STATUS.PROCESSING;
    updateUI();
    processRecording();
}

export async function stopAndCapture() {
    if (state !== STATUS.RECORDING) return;

    if (watchId !== null) {
        navigator.geolocation.clearWatch(watchId);
        watchId = null;
    }

    if (points.length < 5) {
        showToast("⚠ Слишком мало точек. Нужно минимум 5.", "error");
        state = STATUS.IDLE;
        points = [];
        if (pathLayer) {
            try { getMap()?.removeLayer(pathLayer); } catch {}
            pathLayer = null;
        }
        updateUI();
        document.getElementById("recordContainer").style.display = "none";
        return;
    }

    state = STATUS.PROCESSING;
    updateUI();
    await processRecording();
}

async function processRecording() {
    const token = localStorage.getItem("token");
    if (!token) {
        showToast("❌ Требуется авторизация", "error");
        resetAfterRecording();
        return;
    }

    const payload = {
        points: points.map(p => [p.lat, p.lng, p.timestamp]),
    };

    try {
        const res = await fetch(`${API}/api/capture-ride`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify(payload),
        });

        const data = await res.json();

        if (!res.ok) {
            showToast(data.detail || "Ошибка захвата", "error");
            resetAfterRecording();
            return;
        }

        showToast(`✅ +${(data.area / 1_000_000).toFixed(2)} км²!`, "success");
        showShareModal(data, data.sponsored_rewards);

        const { loadTerritories } = await import('./map.js');
        loadTerritories();
    } catch (e) {
        showToast("❌ " + e.message, "error");
    }

    resetAfterRecording();
}

function resetAfterRecording() {
    state = STATUS.IDLE;
    points = [];
    if (pathLayer) {
        try { getMap()?.removeLayer(pathLayer); } catch {}
        pathLayer = null;
    }
    updateUI();
    document.getElementById("recordContainer").style.display = "none";
}

export function initRecorder() {
    const stopBtn = document.getElementById("stopRecordBtn");
    if (stopBtn) stopBtn.onclick = stopAndCapture;
}