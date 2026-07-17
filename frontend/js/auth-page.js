import { API } from './config.js';
import { saveUserData } from './auth.js';

let isLogin = true;
let role = "cyclist";

// Реферальный код из URL
const refMatch = window.location.search.match(/[?&]ref=([^&]+)/);
const refId = refMatch ? refMatch[1] : null;
if (refId) {
    const refInput = document.createElement("input");
    refInput.type = "hidden";
    refInput.id = "refId";
    refInput.value = refId;
    document.body.appendChild(refInput);
}

function updateUI() {
    const roleTabs = document.getElementById("roleTabs");
    const usernameField = document.getElementById("username");
    roleTabs.style.display = isLogin ? "none" : "flex";
    document.getElementById("subtitle").textContent = isLogin
        ? "Войдите чтобы захватывать территории"
        : "Создайте аккаунт";
    document.getElementById("submitBtn").textContent = isLogin ? "Войти" : "Зарегистрироваться";
    document.getElementById("toggleBtn").textContent = isLogin
        ? "Нет аккаунта? Зарегистрироваться"
        : "Уже есть аккаунт? Войти";
    usernameField.style.display = (!isLogin && role === "cyclist") ? "block" : "none";
}

document.querySelectorAll(".role-tab").forEach(tab => {
    tab.onclick = () => {
        document.querySelectorAll(".role-tab").forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        role = tab.dataset.role;
        updateUI();
    };
});

document.getElementById("toggleBtn").onclick = () => {
    isLogin = !isLogin;
    if (!isLogin) {
        role = "cyclist";
        document.querySelectorAll(".role-tab").forEach(t => t.classList.remove("active"));
        document.querySelector('.role-tab[data-role="cyclist"]').classList.add("active");
    }
    updateUI();
};

document.getElementById("submitBtn").onclick = async () => {
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;
    const username = document.getElementById("username").value;
    const errorEl = document.getElementById("error");

    errorEl.style.display = "none";

    if (!email || !password || (!isLogin && !username && role !== "advertiser")) {
        errorEl.textContent = "Заполните все поля";
        errorEl.style.display = "block";
        return;
    }

    try {
        let res;
        if (isLogin) {
            res = await fetch(`${API}/api/auth/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password }),
            });
        } else {
            const headers = { "Content-Type": "application/json" };
            const ref = document.getElementById("refId")?.value;
            if (ref) headers["X-Referral-ID"] = ref;
            const regUsername = role === "advertiser" ? email.split("@")[0] : username;
            res = await fetch(`${API}/api/auth/register`, {
                method: "POST",
                headers,
                body: JSON.stringify({
                    email,
                    password,
                    username: regUsername,
                    is_advertiser: role === "advertiser",
                }),
            });
        }

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Ошибка");
        }

        const data = await res.json();
        saveUserData(data);
        window.location.href = "/";
    } catch (e) {
        errorEl.textContent = e.message;
        errorEl.style.display = "block";
    }
};

updateUI();
