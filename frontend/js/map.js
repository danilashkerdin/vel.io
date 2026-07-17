import { API } from './config.js';
import { authHeaders, getUser } from './auth.js';
import { fetchTerritories } from './api.js';
import { updateStats } from './territories.js';
import { setTerritoriesData } from './editor.js';

let map;
let territoryLayers = [];
let sponsoredLayers = [];
let loadTimeout = null;
let fetchController = null;

export function getMap() {
    return map;
}

export function getTerritoryLayers() {
    return territoryLayers;
}

export function setTerritoryLayers(layers) {
    territoryLayers = layers;
}

export function getPatternId(imageUrl) {
    const defs = document.getElementById("velo-patterns").querySelector("defs");
    const id = 'p-' + btoa(imageUrl).replace(/[^a-zA-Z0-9]/g, '').substring(0, 20);

    if (!document.getElementById(id)) {
        const pattern = document.createElementNS("http://www.w3.org/2000/svg", "pattern");
        pattern.setAttribute("id", id);
        pattern.setAttribute("patternUnits", "objectBoundingBox");
        pattern.setAttribute("width", "1");
        pattern.setAttribute("height", "1");
        pattern.setAttribute("patternContentUnits", "objectBoundingBox");
        const img = document.createElementNS("http://www.w3.org/2000/svg", "image");
        img.setAttribute("href", imageUrl);
        img.setAttribute("width", "1");
        img.setAttribute("height", "1");
        img.setAttribute("preserveAspectRatio", "none");
        pattern.appendChild(img);
        defs.appendChild(pattern);
    }
    return id;
}

function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function createTerritoryLayer(t, user) {
    const hasImage = t.image_url && t.image_url.length > 0;
    const fillColor = hasImage ? 'url(#' + getPatternId(t.image_url) + ')' : (t.color || "#4CAF50");

    const layer = L.geoJSON(t.polygon, {
        style: {
            color: t.color || "#4CAF50",
            fillColor: fillColor,
            fillOpacity: hasImage ? 1 : 0.3,
            weight: 2,
            opacity: 0.8,
        },
    });

    const isOwner = t.user_id === user.id;
    const safeName = escapeHtml(t.name || "Безымянный");
    const safeDesc = escapeHtml(t.description);
    const safeLink = t.link_url ? encodeURI(t.link_url) : null;

    let popupHtml = `<div style="max-width:220px;">`;
    if (t.image_url) {
        popupHtml += `<img src="${encodeURI(t.image_url)}" style="width:100%;border-radius:8px;margin-bottom:6px;">`;
    }
    popupHtml += `<b>${safeName}</b><br>`;
    if (safeDesc) {
        popupHtml += `<p style="margin:4px 0;font-size:13px;">${safeDesc}</p>`;
    }
    popupHtml += `<span style="font-size:12px;">${(t.area / 1000000).toFixed(2)} км²</span><br>`;
    const safeUsername = escapeHtml(t.username);
    if (safeUsername && !isOwner) {
        popupHtml += `<span style="font-size:11px;color:var(--color-text-muted);">👤 ${safeUsername}</span><br>`;
    }
    if (safeLink) {
        popupHtml += `<a href="${safeLink}" target="_blank" rel="noopener noreferrer" style="color:#4CAF50;font-size:12px;">🔗 Ссылка</a><br>`;
    }
    if (isOwner) {
        popupHtml += `
            <button onclick="editTerritory('${t.id}')" style="margin-top:4px;padding:4px 8px;background:#4CAF50;color:white;border:none;border-radius:4px;cursor:pointer;font-size:12px;">✏️</button>
            <button onclick="deleteTerritory('${t.id}')" style="margin-top:4px;padding:4px 8px;background:#f44336;color:white;border:none;border-radius:4px;cursor:pointer;font-size:12px;">🗑</button>
        `;
    }
    popupHtml += `</div>`;

    layer.bindPopup(popupHtml);
    layer._territory_id = t.id;
    return layer;
}

let pinSvgIdCounter = 0;

function createSponsoredMarker(s) {
    const isPoint = s.polygon && s.polygon.type === "Point";
    let layer;

    if (isPoint) {
        const [lng, lat] = s.polygon.coordinates;
        const size = s.icon_size || 32;
        const pinW = size;
        const pinH = Math.round(size * 1.35);
        const cx = pinW / 2;
        const logoR = pinW * 0.38;
        const logoCy = pinW * 0.38;
        const uid = `p${++pinSvgIdCounter}`;

        const pinSvg = `
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${pinW} ${pinH}" width="${pinW}" height="${pinH}">
                <defs>
                    <clipPath id="${uid}c">
                        <circle cx="${cx}" cy="${logoCy}" r="${logoR}"/>
                    </clipPath>
                </defs>
                <path d="M${cx} ${logoCy - logoR}
                    A${logoR} ${logoR} 0 1 1 ${cx - 0.01} ${logoCy - logoR}
                    L${cx} ${pinH - 2} Z"
                    fill="white" stroke="${s.color}" stroke-width="2.5" stroke-linejoin="round"/>
                ${s.image_url ? `<image href="${encodeURI(s.image_url)}" x="${cx - logoR}" y="${logoCy - logoR}" width="${logoR * 2}" height="${logoR * 2}" clip-path="url(#${uid}c)" preserveAspectRatio="xMidYMid slice"/>` : ''}
            </svg>
        `;

        const icon = L.divIcon({
            html: pinSvg,
            iconSize: [pinW, pinH],
            iconAnchor: [cx, pinH - 2],
            popupAnchor: [0, -pinH],
            className: "",
        });

        layer = L.marker([lat, lng], { icon });
    } else {
        layer = L.geoJSON(s.polygon, {
            style: { color: s.color, fillOpacity: 0.2, weight: 2 },
        });
    }

    const safeName = escapeHtml(s.business_name);
    const safeDesc = escapeHtml(s.description);
    const safeLink = s.link_url ? encodeURI(s.link_url) : null;

    let popupHtml = `<div style="max-width:200px;text-align:center;">`;
    if (s.image_url) {
        popupHtml += `<img src="${encodeURI(s.image_url)}" style="width:60px;height:60px;border-radius:50%;object-fit:cover;margin-bottom:6px;">`;
    }
    popupHtml += `<div style="font-weight:600;font-size:14px;">${safeName}</div>`;
    if (safeDesc) {
        popupHtml += `<p style="margin:4px 0;font-size:12px;color:#666;">${safeDesc}</p>`;
    }
    popupHtml += `</div>`;
    if (safeLink) {
        popupHtml += `<a href="${safeLink}" target="_blank" rel="noopener noreferrer" style="display:block;text-align:center;margin-top:6px;padding:8px;background:#4CAF50;color:white;border-radius:6px;text-decoration:none;font-size:13px;">🔗 Открыть сайт</a>`;
    }
    const stars = s.monthly_budget_stars || 0;
    if (stars >= 5000) {
        const contacts = [];
        if (s.contact_phone) contacts.push(`📞 ${escapeHtml(s.contact_phone)}`);
        if (s.contact_telegram) contacts.push(`💬 ${escapeHtml(s.contact_telegram)}`);
        if (s.website) contacts.push(`🌐 <a href="${encodeURI(s.website)}" target="_blank" style="color:var(--color-primary);">${escapeHtml(s.website)}</a>`);
        if (contacts.length) {
            popupHtml += `<div style="margin-top:8px;padding:8px;background:rgba(255,215,0,0.08);border-radius:8px;font-size:12px;line-height:1.6;">${contacts.join("<br>")}</div>`;
        }
    }

    layer.bindPopup(popupHtml);
    layer._sponsored_id = s.id;
    return layer;
}

async function loadSponsored() {
    const b = map.getBounds();
    try {
        const res = await fetch(`${API}/api/sponsored-territories?` + new URLSearchParams({
            north: b.getNorth(),
            south: b.getSouth(),
            east: b.getEast(),
            west: b.getWest(),
        }).toString());
        if (!res.ok) return;
        const sponsored = await res.json();

        const incomingIds = new Set(sponsored.map(s => s.id));
        sponsoredLayers = sponsoredLayers.filter(l => {
            if (!incomingIds.has(l._sponsored_id)) {
                map.removeLayer(l);
                return false;
            }
            return true;
        });

        const existingIds = new Set(sponsoredLayers.map(l => l._sponsored_id));
        sponsored.filter(s => !existingIds.has(s.id)).forEach(s => {
            const layer = createSponsoredMarker(s);
            layer.addTo(map);
            sponsoredLayers.push(layer);
        });
    } catch (e) {
        console.error(e);
    }
}

export async function loadTerritories() {
    const b = map.getBounds();

    // Abort any in-flight request
    if (fetchController) fetchController.abort();
    fetchController = new AbortController();
    const signal = fetchController.signal;

    try {
        const territories = await fetchTerritories({
            north: b.getNorth(),
            south: b.getSouth(),
            east: b.getEast(),
            west: b.getWest(),
        }, signal);

        const user = getUser();
        setTerritoriesData(territories);

        // Diff-based update: remove only layers no longer in response, add only new ones
        const incomingIds = new Set(territories.map(t => t.id));

        territoryLayers = territoryLayers.filter(l => {
            if (!incomingIds.has(l._territory_id)) {
                map.removeLayer(l);
                return false;
            }
            return true;
        });

        const existingIds = new Set(territoryLayers.map(l => l._territory_id));

        territories.filter(t => !existingIds.has(t.id)).forEach(t => {
            const layer = createTerritoryLayer(t, user);
            layer.addTo(map);
            territoryLayers.push(layer);
        });

        updateStats(territories);
        await loadSponsored();
    } catch (e) {
        if (e.name === 'AbortError') return;  // expected, ignore
        console.error(e);
    }
}

function debouncedLoadTerritories() {
    if (loadTimeout) clearTimeout(loadTimeout);
    loadTimeout = setTimeout(loadTerritories, 450);
}

async function getInitialView() {
    try {
        const res = await fetch(`${API}/api/initial-view`, { headers: authHeaders() });
        if (res.ok) return await res.json();
    } catch (e) {
        console.error("Failed to get initial view:", e);
    }
    return { lat: 55.751244, lon: 37.618423, zoom: 12 };
}

export async function initMap() {
    const view = await getInitialView();

    map = L.map("map", { attributionControl: false }).setView([view.lat, view.lon], view.zoom);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
        attribution: "© OpenStreetMap, © CARTO",
    }).addTo(map);
    L.control.attribution({ prefix: false }).addTo(map);

    // SVG для заливки картинками
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", "0");
    svg.setAttribute("height", "0");
    svg.setAttribute("id", "velo-patterns");
    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    svg.appendChild(defs);
    document.body.appendChild(svg);

    loadTerritories();
    map.on("moveend", debouncedLoadTerritories);

    // Если есть bounds — подогнать карту
    if (view.bounds) {
        map.fitBounds([
            [view.bounds.south, view.bounds.west],
            [view.bounds.north, view.bounds.east],
        ], { padding: [30, 30] });
    }
}

/** Центрирует карту на полигоне территории (после загрузки GPX) */
export function centerOnTerritory(territory) {
    if (!map || !territory.polygon) return;
    const layer = L.geoJSON(territory.polygon);
    map.fitBounds(layer.getBounds(), { padding: [30, 30] });
}
