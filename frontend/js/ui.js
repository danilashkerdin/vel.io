export function openModal(id) {
    document.getElementById(id).classList.add("visible");
    document.getElementById("overlay").classList.add("visible");
}

export function closeModals() {
    document.querySelectorAll(".modal.visible").forEach(m => m.classList.remove("visible"));
    document.getElementById("overlay").classList.remove("visible");
}

export function showToast(msg, type = "success") {
    const t = document.createElement("div");
    t.className = `toast ${type}`;
    t.textContent = msg;
    document.getElementById("toastContainer").appendChild(t);
    setTimeout(() => t.remove(), 3000);
}

export function openActionSheet() {
    document.getElementById("actionSheet").classList.add("open");
}

export function closeActionSheet() {
    document.getElementById("actionSheet").classList.remove("open");
}

export function switchTab(name) {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
    document.querySelectorAll(".tab-page").forEach(p => p.style.display = p.id === "tab" + name.charAt(0).toUpperCase() + name.slice(1) ? "flex" : "none");
    if (name === "map") {
        document.getElementById("map").style.display = "block";
        setTimeout(() => document.getElementById("map")?.invalidated?.() || window.dispatchEvent(new Event("resize")), 100);
    } else {
        document.getElementById("map").style.display = "none";
    }
}