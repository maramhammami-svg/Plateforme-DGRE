import { $, el, esc } from "../dom.js";
import { api } from "../api.js";
import { toast } from "../toast.js";

export async function loadDocuments() {
  try {
    const rows = await api("/documents");
    const tb = $("#docsBody");
    tb.innerHTML = "";
    if (!rows.length) { tb.innerHTML = '<tr><td colspan="7" class="empty">Aucun document.</td></tr>'; return; }
    rows.forEach(d => {
      const tr = el("tr"); const created = d.created_at ? String(d.created_at).slice(0, 10) : "";
      tr.innerHTML = `<td class="num">${d.id}</td><td>${esc(d.nom)}</td><td class="num">${d.owner_id}</td><td class="num">${d.unite_id ?? ''}</td>
        <td class="num">${d.taille_ko}</td><td class="num">${esc(created)}</td><td class="actions"><button class="btn sm" data-doc="${d.id}">Télécharger</button></td>`;
      tb.appendChild(tr);
    });
  } catch (e) { toast(e.detail, "err"); }
}

export async function downloadDoc(id) {
  try { const d = await api("/documents/" + id); toast(`Accès accordé : ${d.nom}`, "ok"); }
  catch (e) { toast(e.status === 403 ? "Accès refusé (hors de votre unité) — journalisé." : e.detail, "err"); }
}

export async function createDoc() {
  const nom = $("#docNom").value.trim(); const size = Number($("#docSize").value || 0);
  if (!nom) { toast("Nom requis.", "err"); return; }
  try {
    await api("/documents", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nom, taille_ko: size }) });
    toast("Document déposé.", "ok"); $("#docNom").value = ""; $("#docSize").value = ""; await loadDocuments();
  } catch (e) { toast(e.detail, "err"); }
}

export function initDocuments() {
  $("#docAddBtn").onclick = createDoc;
}
