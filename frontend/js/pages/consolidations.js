import { $, el, esc, qs } from "../dom.js";
import { api } from "../api.js";
import { toast } from "../toast.js";
import { state } from "../state.js";

export async function loadConsolidations() {
  const params = { station_id: $("#cStation").value, annee_hydro: $("#cAnnee").value };
  try {
    const rows = await api("/consolidations" + qs(params));
    const byId = Object.fromEntries(state.stationCache.map(s => [s.id, s.code + " · " + s.name]));
    const tb = $("#consBody");
    tb.innerHTML = "";
    if (!rows.length) { tb.innerHTML = '<tr><td colspan="17" class="empty">Aucune consolidation.</td></tr>'; return; }
    const months = ["sept", "octo", "nove", "dece", "janv", "fevr", "mars", "avri", "mai", "juin", "juil", "aout"];
    const n = v => v == null ? "—" : (Math.round(v * 10) / 10);
    rows.forEach(r => {
      const tr = el("tr");
      let cells = `<td>${esc(byId[r.station_id] || r.station_id)}</td><td class="num">${r.annee_hydro}</td>`;
      months.forEach(m => cells += `<td class="num">${n(r[m])}</td>`);
      cells += `<td class="num">${n(r.total)}</td><td class="num">${n(r.normale)}</td><td class="num">${r.pourcentage == null ? "—" : Math.round(r.pourcentage) + "%"}</td>`;
      tr.innerHTML = cells; tb.appendChild(tr);
    });
  } catch (e) { toast(e.detail, "err"); }
}

export function initConsolidations() {
  $("#cApply").onclick = loadConsolidations;
}
