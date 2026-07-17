import { updateTerritory } from './api.js';
import { loadTerritories } from './map.js';
import { openModal, closeModals, showToast } from './ui.js';

let selectedTerritoryId = null;
let territoriesData = [];

export function setTerritoriesData(data) {
    territoriesData = data;
}

export function editTerritory(id) {
    const t = territoriesData.find(t => t.id === id);
    if (!t) return;
    selectedTerritoryId = id;
    document.getElementById("editName").value = t.name || "";
    document.getElementById("editColor").value = t.color || "#4CAF50";
    document.getElementById("editImage").value = t.image_url || "";
    document.getElementById("editDescription").value = t.description || "";
    document.getElementById("editLink").value = t.link_url || "";
    openModal("editorModal");
}

export async function saveTerritory() {
    const data = {
        name: document.getElementById("editName").value,
        color: document.getElementById("editColor").value,
        image_url: document.getElementById("editImage").value || null,
        description: document.getElementById("editDescription").value || null,
        link_url: document.getElementById("editLink").value || null,
    };
    try {
        await updateTerritory(selectedTerritoryId, data);
        closeModals();
        showToast("✅ Обновлено", "success");
        loadTerritories();
    } catch (e) {
        showToast(e.message, "error");
    }
}
