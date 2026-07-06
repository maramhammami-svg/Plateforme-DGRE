import { $, el, esc, pct, qs } from "../dom.js";
import { api } from "../api.js";
import { toast } from "../toast.js";
import { can, REV } from "../roles.js";
import { ensureMap, paintMarkers, dmapH } from "../map.js";
import { loadFluxFeed } from "../flux.js";

export async function loadDashboard() {
  const params = {
    annee_hydro: $("#dAnnee").value, date_from: $("#dFrom").value, date_to: $("#dTo").value,
    station_id: $("#dStation").value, status: $("#dStatus").value, quality_flag: $("#dQuality").value,
  };
  try {
    const s = await api("/dashboard/summary" + qs(params));
    $("#kPending").textContent = s.pending_count;
    $("#kAnom").textContent = s.quality_anomalies;
    $("#kActive").textContent = s.stations_active;
    $("#kInactive").textContent = s.stations_inactive;
    const tb = $("#complBody");
    tb.innerHTML = "";
    if (!s.completeness || !s.completeness.length) { tb.innerHTML = '<tr><td colspan="4" class="empty">Aucune station.</td></tr>'; }
    else s.completeness.forEach(c => {
      const tr = el("tr");
      const w = Math.round((c.completude_journaliere || 0) * 100);
      tr.innerHTML = `<td class="num">${esc(c.code)}</td><td>${esc(c.name)}</td><td class="num">${pct(c.completude_mensuelle)}</td>
        <td><div class="row" style="gap:8px;align-items:center"><div class="bar"><i style="width:${w}%"></i></div><span class="num">${pct(c.completude_journaliere)}</span></div></td>`;
      tb.appendChild(tr);
    });
  } catch (e) { toast(e.detail, "err"); }
  loadDmap();
  if (can(REV)) loadFluxFeed();
}

function loadDmap() {
  ensureMap("dmap", dmapH);
  paintMarkers(dmapH);
}

export function initDashboard() {
  $("#dApply").onclick = loadDashboard;
}
