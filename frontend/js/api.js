import { API } from './config.js';
import { authHeaders } from './auth.js';

async function _fetch(url, opts = {}) {
    let res;
    try {
        res = await fetch(url, opts);
    } catch (e) {
        const err = new Error(
            e.message === "Failed to fetch"
                ? "Сервер недоступен. Проверьте соединение."
                : e.message || "Сетевая ошибка"
        );
        err.status = 0;
        throw err;
    }
    if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const err = new Error(body.detail || `Ошибка ${res.status}`);
        err.status = res.status;
        err.body = body;
        throw err;
    }
    return res;
}

export async function fetchTerritories(bounds, signal) {
    const url = `${API}/api/territories?north=${bounds.north}&south=${bounds.south}&east=${bounds.east}&west=${bounds.west}`;
    const res = await _fetch(url, { headers: authHeaders(), signal });
    return res.json();
}

export async function uploadGpx(file) {
    const fd = new FormData();
    fd.append("file", file);
    const res = await _fetch(`${API}/api/upload-gpx`, {
        method: "POST",
        headers: authHeaders(),
        body: fd,
    });
    return res;
}

export async function updateTerritory(id, data) {
    const res = await _fetch(`${API}/api/territories/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify(data),
    });
    return res;
}

export async function deleteTerritory(id) {
    const res = await _fetch(`${API}/api/territories/${id}`, {
        method: "DELETE",
        headers: authHeaders(),
    });
    return res;
}

export async function fetchLeaderboard(period = "all", sort = "area") {
    const res = await _fetch(`${API}/api/leaderboard?period=${period}&sort=${sort}`);
    return res.json();
}

export async function fetchMyTerritories() {
    const res = await _fetch(`${API}/api/my-territories`, { headers: authHeaders() });
    return res.json();
}

export async function fetchNotifications() {
    const res = await _fetch(`${API}/api/notifications`, { headers: authHeaders() });
    return res.json();
}

export async function readAllNotifications() {
    await _fetch(`${API}/api/notifications/read-all`, {
        method: "POST",
        headers: authHeaders(),
    });
}

export async function fetchPublicTerritory(id) {
    const res = await _fetch(`${API}/api/territories/public/${id}`);
    return res;
}

export async function login(email, password) {
    return _fetch(`${API}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
    });
}

export async function register(email, username, password, refId) {
    const headers = { "Content-Type": "application/json" };
    if (refId) {
        headers["X-Referral-ID"] = refId;
    }
    return _fetch(`${API}/api/auth/register`, {
        method: "POST",
        headers,
        body: JSON.stringify({ email, password, username }),
    });
}

export async function createStarInvoice(purpose = "premium", extra = {}) {
    const params = new URLSearchParams({ purpose, ...extra });
    const res = await _fetch(`${API}/api/payment/create-star-invoice?${params}`, {
        method: "POST",
        headers: authHeaders(),
    });
    return res.json();
}

export async function fetchPremiumStatus() {
    const res = await _fetch(`${API}/api/payment/status`, {
        headers: authHeaders(),
    });
    return res.json();
}
