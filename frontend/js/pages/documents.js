import { $, el, esc } from "../dom.js";
import { api } from "../api.js";
import { toast } from "../toast.js";

let uniteCache = [];
let userCache = [];

function partagesLabel(partages) {
  if (!partages || !partages.length) return "—";
  return partages.map(p => esc(p.nom) + (p.type === "unite" ? " (unité)" : "")).join(", ");
}

export async function loadDocuments() {
  try {
    const rows = await api("/documents");
    const tb = $("#docsBody");
    tb.innerHTML = "";
    if (!rows.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">Aucun document.</td></tr>'; return; }
    rows.forEach(d => {
      const tr = el("tr"); const created = d.created_at ? String(d.created_at).slice(0, 10) : "";
      tr.innerHTML = `<td class="num">${d.id}</td><td>${esc(d.nom)}</td><td class="num">${d.owner_id}</td><td class="num">${d.unite_id ?? ''}</td>
        <td class="num">${d.taille_ko}</td><td>${partagesLabel(d.partages)}</td><td class="num">${esc(created)}</td><td class="actions"><button class="btn sm" data-doc="${d.id}">Télécharger</button></td>`;
      tb.appendChild(tr);
    });
  } catch (e) { toast(e.detail, "err"); }
}

export async function downloadDoc(id) {
  try {
    const res = await api("/documents/" + id, { raw: true });
    const blob = await res.blob();
    const cd = res.headers.get("Content-Disposition") || "";
    const match = /filename="?([^"]+)"?/.exec(cd);
    const filename = match ? match[1] : ("document-" + id);
    const url = URL.createObjectURL(blob);
    const a = el("a"); a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  } catch (e) { toast(e.status === 403 ? "Accès refusé (hors de votre périmètre) — journalisé." : e.detail, "err"); }
}

async function loadDirectories() {
  try {
    uniteCache = await api("/unites");
    userCache = await api("/admin/users/directory");
  } catch (e) { toast(e.detail, "err"); return; }
  const uSel = $("#docShareUnites"); uSel.innerHTML = "";
  uniteCache.forEach(u => { const o = el("option"); o.value = u.id; o.textContent = u.nom; uSel.appendChild(o); });
  const pSel = $("#docShareUsers"); pSel.innerHTML = "";
  userCache.forEach(u => { const o = el("option"); o.value = u.id; o.textContent = u.full_name || u.username; pSel.appendChild(o); });
}

function selectedValues(sel) { return [...sel.selectedOptions].map(o => o.value); }

export async function createDoc() {
  const file = $("#docFile").files[0];
  if (!file) { toast("Choisissez un fichier.", "err"); return; }
  const fd = new FormData();
  fd.append("file", file);
  selectedValues($("#docShareUnites")).forEach(v => fd.append("partage_unite_ids", v));
  selectedValues($("#docShareUsers")).forEach(v => fd.append("partage_user_ids", v));
  try {
    await api("/documents", { method: "POST", body: fd });
    toast("Document déposé.", "ok");
    $("#docFile").value = "";
    $("#docShareUnites").selectedIndex = -1;
    $("#docShareUsers").selectedIndex = -1;
    await loadDocuments();
  } catch (e) { toast(e.detail, "err"); }
}

export function initDocuments() {
  $("#docAddBtn").onclick = createDoc;
  loadDirectories();
}
