import { uploadGpx } from './api.js';
import { loadTerritories, centerOnTerritory } from './map.js';
import { closeModals, openModal, showToast } from './ui.js';
import { showShareModal } from './share.js';
import { isPremium } from './auth.js';

let currentFile = null;

export function setupUpload() {
    const drop = document.getElementById("dropArea");
    const inp = document.getElementById("fileInput");
    const btn = document.getElementById("processBtn");

    drop.onclick = () => inp.click();
    drop.ondragover = e => { e.preventDefault(); drop.classList.add("dragover"); };
    drop.ondragleave = () => drop.classList.remove("dragover");
    drop.ondrop = e => { e.preventDefault(); drop.classList.remove("dragover"); handleFile(e.dataTransfer.files[0]); };
    inp.onchange = e => handleFile(e.target.files[0]);
    btn.onclick = processFile;
}

function handleFile(file) {
    if (!file || !file.name.toLowerCase().endsWith(".gpx")) {
        showToast("Выберите .gpx файл", "error");
        return;
    }

    currentFile = file;
    document.getElementById("fileName").textContent = `📄 ${file.name}`;
    document.getElementById("processBtn").disabled = false;
    document.getElementById("uploadStatus").textContent = "";
}

async function processFile() {
    if (!currentFile) return;

    const btn = document.getElementById("processBtn");
    const status = document.getElementById("uploadStatus");
    const progressFill = document.getElementById("progressFill");
    btn.disabled = true;
    btn.textContent = "Обработка...";
    status.textContent = "";

    let progressInterval = null;

    try {
        document.getElementById("uploadProgress").style.display = "block";
        progressFill.style.width = "0%";

        let progress = 0;
        progressInterval = setInterval(() => {
            progress += Math.random() * 15;
            if (progress > 90) progress = 90;
            progressFill.style.width = progress + "%";
        }, 500);

        let t;
        try {
            const res = await uploadGpx(currentFile);
            t = await res.json();
        } catch (err) {
            if (err.status === 402) {
                setTimeout(() => openModal("referralModal"), 300);
            }
            throw err;
        } finally {
            clearInterval(progressInterval);
            progressInterval = null;
            progressFill.style.width = "100%";
            setTimeout(() => {
                document.getElementById("uploadProgress").style.display = "none";
            }, 500);
        }
        let areaStr = `${(t.area / 1000000).toFixed(2)} км²`;

        let bonusMsg = "";
        if (t.sponsored_rewards && t.sponsored_rewards.length > 0) {
            const lines = t.sponsored_rewards.map(r =>
                `🏪 ${r.business_name}: +${r.your_share_monthly_rub}₽/мес`
            ).join(" · ");
            bonusMsg = ` ${lines}`;
            areaStr += bonusMsg;
        }

        status.textContent = `✅ Захвачено! ${areaStr}`;
        status.className = "success";
        showToast(`🎉 ${areaStr}`, "success");
        currentFile = null;
        document.getElementById("fileName").textContent = "";
        btn.disabled = true;

        setTimeout(() => {
            closeModals();
            showShareModal(t, t.sponsored_rewards);
            loadTerritories();
            centerOnTerritory(t);
        }, 800);
    } catch (e) {
        status.textContent = `❌ ${e.message}`;
        status.className = "error";
        showToast(e.message, "error");
        if (progressInterval) clearInterval(progressInterval);
        document.getElementById("uploadProgress").style.display = "none";
    } finally {
        btn.disabled = false;
        btn.textContent = "Захватить территорию";
    }
}
