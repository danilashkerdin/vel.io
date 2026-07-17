const host = window.location.hostname;
const port = window.location.port;
const isLocal = host === "localhost" || host === "127.0.0.1";

// На Render фронт и бэк — разные сервисы с разными доменами
export const API = (host.includes("onrender.com") || port === "3000")
    ? "https://vel-io.onrender.com"
    : isLocal
        ? "http://localhost:8000"
        : "";
