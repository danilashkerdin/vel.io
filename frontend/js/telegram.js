import { API } from './config.js';
import { saveUserData } from './auth.js';

let tg = null;

export function isTelegramWebApp() {
    return !!(
        window.Telegram?.WebApp ||
        window.external?.notify ||
        navigator.userAgent.includes('Telegram')
    );
}

export function getTelegram() {
    if (tg) {return tg;}
    if (window.Telegram?.WebApp) {
        tg = window.Telegram.WebApp;
        return tg;
    }
    return null;
}

export async function waitForTelegram(timeout = 3000) {
    if (window.Telegram?.WebApp) {return window.Telegram.WebApp;}
    const start = Date.now();
    while (Date.now() - start < timeout) {
        await new Promise(r => setTimeout(r, 100));
        if (window.Telegram?.WebApp) {return window.Telegram.WebApp;}
    }
    return null;
}

export function applyTelegramTheme() {
    const t = getTelegram();
    if (!t) {return;}
    t.ready();
    t.expand();

    const theme = t.themeParams || {};
    const isDark = t.colorScheme === 'dark' || theme.bg_color?.startsWith('#1');

    // Применяем Telegram-тему поверх нашей тёмной
    const root = document.documentElement;
    if (theme.bg_color) {root.style.setProperty('--tg-bg', theme.bg_color);}
    if (theme.text_color) {root.style.setProperty('--tg-text', theme.text_color);}
    if (theme.button_color) {root.style.setProperty('--tg-btn', theme.button_color);}
    if (theme.button_text_color) {root.style.setProperty('--tg-btn-text', theme.button_text_color);}
    if (theme.hint_color) {root.style.setProperty('--tg-hint', theme.hint_color);}
    if (theme.link_color) {root.style.setProperty('--tg-link', theme.link_color);}

    // Back button
    t.BackButton.onClick(() => {
        t.close();
    });
}

export async function tryTelegramAuth() {
    const t = getTelegram();
    if (!t) {return null;}

    const initData = t.initData;
    if (!initData) {return null;}

    try {
        const res = await fetch(`${API}/api/auth/telegram`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ init_data: initData }),
        });

        if (!res.ok) {
            console.warn("Telegram auth failed", await res.text());
            return null;
        }

        const data = await res.json();
        saveUserData(data);
        return data;
    } catch (e) {
        console.warn("Telegram auth error", e);
        return null;
    }
}
