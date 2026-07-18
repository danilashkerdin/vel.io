const PRODUCTION_API = "https://vel-io.onrender.com";

const host = window.location.hostname;
const port = window.location.port;

const isCapacitor = typeof (window.Capacitor) !== "undefined";
const isLocal = host === "localhost" || host === "127.0.0.1";

export const API = isCapacitor
    ? PRODUCTION_API
    : (host.includes("onrender.com") || port === "3000")
        ? PRODUCTION_API
        : isLocal
            ? "http://localhost:8000"
            : "";

export const IS_CAPACITOR = isCapacitor;