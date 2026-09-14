import { $, el, esc, qs } from "../dom.js";
import { api } from "../api.js";
import { toast, openModal } from "../toast.js";
import { state } from "../state.js";
import { can, RW, RV } from "../roles.js";

function statusBadge(s) { return s === "validated" ? '<span class="badge b-ok">validé</span>' : (s === "rejected" ? '<span class="badge b-bad">rejeté</span>' : '<span class="badge b-warn">en attente</span>'); }
function qualityBadge(q) { if (!q) return ""; const c = q === "ok" ? "b-ok" : (q === "aberrant" ? "b-bad" : (q === "manquant" ? "b-grey" : "b-warn")); return `<span class="badge ${c}">${esc(q)}</span>`; }
function staleCorrectionBadge(r) {
  if (r.status !== "validated" || r.valeur_recalculee == null || r.valeur_validee == null) return "";
  if (r.valeur_recalculee === r.valeur_validee) return "";
  return ' <span class="badge b-warn" title="La valeur recalculee differe de la valeur officielle : revalidez pour appliquer ce changement">correction en attente</span>';
}

export async function loadReadings() {
  const params = { station_id: $("#fStation").value, date_from: $("#fFrom").value, date_to: $("#fTo").value, status: $("#fStatus").value, quality_flag: $("#fQuality").value };
  try {
    const rows = await api("/readings" + qs(params));
    const byId = Object.fromEntries(state.stationCache.map(s => [s.id, s.code + " · " + s.name]));
    const tb = $("#readingsBody");
    tb.innerHTML = "";
    if (!rows.length) { tb.innerHTML = '<tr><td colspan="9" class="empty">Aucun relevé.</td></tr>'; return; }
    rows.forEach(r => {
      const tr = el("tr");
      let act = `<button class="btn sm" data-versions="${r.id}">Historique</button>`;
      if (can(RW)) act = `<button class="btn sm" data-correct="${r.id}" data-val="${r.valeur_recalculee ?? ''}">Corriger</button> ` + act;
      if (can(RV)) act += ` <button class="btn sm" data-context="${r.id}" data-ctx-station="${r.station_id}" data-ctx-date="${r.date}">Contexte</button>
                          <button class="btn sm" data-validate="${r.id}" data-dec="validate">Valider</button>
                          <button class="btn sm" data-validate="${r.id}" data-dec="reject">Rejeter</button>
                          <button class="btn sm" data-delete="${r.id}">Supprimer</button>`;
      tr.innerHTML = `<td class="num">${r.id}</td><td>${esc(byId[r.station_id] || r.station_id)}</td><td class="num">${esc(r.date)}</td>
        <td class="num">${r.valeur_recalculee ?? '—'}</td><td class="num">${r.valeur_validee ?? '—'}${staleCorrectionBadge(r)}</td><td>${esc(r.source || '')}</td>
        <td>${statusBadge(r.status)}</td><td>${qualityBadge(r.quality_flag)}</td><td class="actions">${act}</td>`;
      tb.appendChild(tr);
    });
  } catch (e) { toast(e.detail, "err"); }
}

export async function addReading() {
  const sid = $("#rStation").value, date = $("#rDate").value, val = parseFloat($("#rValue").value);
  if (!sid) { toast("Choisissez une station.", "err"); return; }
  if (!date || isNaN(val)) { toast("Date et valeur requises.", "err"); return; }
  try {
    await api("/readings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ station_id: Number(sid), date, valeur: val }) });
    toast("Relevé enregistré.", "ok"); $("#rValue").value = ""; await loadReadings();
  } catch (e) { toast(e.detail, "err"); }
}

export async function correctReading(id, current) {
  const v = prompt("Nouvelle valeur :", current); if (v === null) return;
  const val = parseFloat(v); if (isNaN(val)) { toast("Valeur invalide.", "err"); return; }
  const reason = prompt("Raison (facultatif) :", "") || null;
  try {
    await api("/readings/" + id, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ valeur_recalculee: val, raison: reason }) });
    toast("Relevé corrigé (en attente).", "ok"); await loadReadings();
  } catch (e) { toast(e.detail, "err"); }
}

export async function validateReading(id, decision) {
  try {
    await api("/readings/" + id + "/validate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision }) });
    toast(decision === "validate" ? "Relevé validé." : "Relevé rejeté.", "ok"); await loadReadings();
  } catch (e) { toast(e.detail, "err"); }
}

export async function deleteReading(id) {
  if (!confirm("Supprimer ce relevé ?")) return;
  try { await api("/readings/" + id, { method: "DELETE", raw: true }); toast("Relevé supprimé.", "ok"); await loadReadings(); }
  catch (e) { toast(e.detail, "err"); }
}

export async function showContext(id, stationId, dateStr) {
  try {
    const d = new Date(dateStr + "T00:00:00Z");
    const from = new Date(d); from.setUTCDate(from.getUTCDate() - 7);
    const to = new Date(d); to.setUTCDate(to.getUTCDate() - 1);
    const fmt = x => x.toISOString().slice(0, 10);
    const rows = await api(`/readings?station_id=${stationId}&date_from=${fmt(from)}&date_to=${fmt(to)}`);
    const byDate = Object.fromEntries(rows.map(r => [r.date, r]));
    let html = `<h3>7 jours precedents (releve #${id})</h3>`;
    html += '<div class="scroll-x"><table><thead><tr><th>Date</th><th>Valeur</th><th>Qualite</th></tr></thead><tbody>';
    for (let i = 7; i >= 1; i--) {
      const dd = new Date(d); dd.setUTCDate(dd.getUTCDate() - i);
      const ds = fmt(dd);
      const r = byDate[ds];
      html += `<tr><td>${ds}</td><td class="num">${r ? (r.valeur_recalculee ?? '—') : '—'}</td><td>${r ? qualityBadge(r.quality_flag) : '<span class="badge b-grey">absent</span>'}</td></tr>`;
    }
    html += '</tbody></table></div>';
    openModal(html);
  } catch (e) { toast(e.detail, "err"); }
}

export async function showVersions(id) {
  try {
    const vers = await api("/readings/" + id + "/versions");
    let html = `<h3>Historique du relevé #${id}</h3>`;
    if (!vers.length) html += '<p class="empty">Aucune modification.</p>';
    else {
      html += '<div class="scroll-x"><table><thead><tr><th>v</th><th>Avant</th><th>Après</th><th>Statut</th><th>Raison</th><th>Post-valid.</th></tr></thead><tbody>';
      vers.forEach(v => html += `<tr><td class="num">${v.version_no}</td><td class="num">${v.ancienne_val ?? '—'}</td><td class="num">${v.nouvelle_val ?? '—'}</td>
        <td>${esc(v.old_status ?? '')}→${esc(v.new_status ?? '')}</td><td>${esc(v.raison || "")}</td><td>${v.post_validation ? '<span class="badge b-bad">oui</span>' : ''}</td></tr>`);
      html += '</tbody></table></div>';
    }
    openModal(html);
  } catch (e) { toast(e.detail, "err"); }
}

export async function importCSV() {
  const f = $("#rFile").files[0]; if (!f) { toast("Choisissez un fichier CSV.", "err"); return; }
  const fd = new FormData(); fd.append("file", f);
  try {
    const res = await api("/raw-readings/import", { method: "POST", body: fd });
    toast(`Import : ${res.inserted} insérés, ${res.rejected} rejetés.`, "ok"); $("#rFile").value = ""; await loadReadings();
  } catch (e) { toast(e.detail, "err"); }
}

export async function exportCSV() {
  try {
    const res = await api("/readings/export", { raw: true }); const blob = await res.blob(); const url = URL.createObjectURL(blob);
    const a = el("a"); a.href = url; a.download = "releves.csv"; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url); toast("Export téléchargé.", "ok");
  } catch (e) { toast(e.detail, "err"); }
}

export function initReadings() {
  $("#rDate").value = new Date().toISOString().slice(0, 10);
  $("#rAddBtn").onclick = addReading;
  $("#rImportBtn").onclick = importCSV;
  $("#rExportBtn").onclick = exportCSV;
  $("#fApply").onclick = loadReadings;
}
