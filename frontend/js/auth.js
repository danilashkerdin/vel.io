export function getToken() {
    return localStorage.getItem("token");
}

export function getUser() {
    return JSON.parse(localStorage.getItem("user") || "{}");
}

export function requireAuth() {
    if (!getToken()) window.location.href = "/auth.html";
}

export function logout() {
    localStorage.clear();
    window.location.href = "/auth.html";
}

export function authHeaders() {
    return { Authorization: `Bearer ${getToken()}` };
}

export function saveUserData(data) {
    const { token, ...user } = data;
    if (token) localStorage.setItem("token", token);
    localStorage.setItem("user", JSON.stringify(user));
}

export function isPremium() {
    return getUser().is_premium === true;
}

export function getCapturesRemaining() {
    const u = getUser();
    if (u.is_premium) return -1;
    return u.captures_remaining ?? u.free_limit ?? 1;
}

export function getFreeLimit() {
    return getUser().free_limit ?? 1;
}
