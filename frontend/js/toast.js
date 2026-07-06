import { $, el } from "./dom.js";

export function toast(msg, kind) {
  const d = el("div", kind || "");
  d.textContent = msg;
  $("#toast").appendChild(d);
  setTimeout(() => {
    d.style.opacity = "0";
    d.style.transition = "opacity .4s";
    setTimeout(() => d.remove(), 400);
  }, 3400);
}

export function openModal(html) {
  const bg = el("div", "modal-bg");
  const m = el("div", "modal");
  m.innerHTML = html + '<button class="btn primary">Fermer</button>';
  m.querySelector(".btn").onclick = () => bg.remove();
  bg.onclick = e => { if (e.target === bg) bg.remove(); };
  bg.appendChild(m);
  document.body.appendChild(bg);
}
