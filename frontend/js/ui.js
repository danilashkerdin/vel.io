export function toggleMenu() {
    document.getElementById("sideMenu").classList.toggle("open");
    document.getElementById("overlay").classList.toggle("visible");
}

export function closeMenu() {
    document.getElementById("sideMenu").classList.remove("open");
    document.getElementById("overlay").classList.remove("visible");
}

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
