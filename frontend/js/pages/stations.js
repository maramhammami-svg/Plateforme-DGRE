import { $, el, esc } from "../dom.js";
import { api } from "../api.js";
import { toast, openModal } from "../toast.js";
import { state } from "../state.js";
import { can, RV } from "../roles.js";

function fillStationSelect(sel, opts = {}) {
  const cur = sel.value;
  sel.innerHTML = opts.allowEmpty ? '<option value="">' + (opts.emptyLabel || "toutes") + '</option>' : "";
  const list = opts.convOnly ? state.stationCache.filter(s => s.type === "conventionnelle") : state.stationCache;
  list.forEach(s => { const o = el("option"); o.value = s.id; o.textContent = s.code + " · " + s.name; sel.appendChild(o); });
  if (cur) sel.value = cur;
}

export async function loadStations() {
  try {
    state.stationCache = await api("/stations");
    fillStationSelect($("#dStation"), { allowEmpty: true });
    fillStationSelect($("#fStation"), { allowEmpty: true });
    fillStationSelect($("#cStation"), { allowEmpty: true });
    fillStationSelect($("#rStation"), { convOnly: true });
    renderStationsTable();
  } catch (e) { toast(e.detail, "err"); }
}

function renderStationsTable() {
  const tb = $("#stationsBody");
  tb.innerHTML = "";
  if (state.stationCache.length === 0) { tb.innerHTML = '<tr><td colspan="8" class="empty">Aucune station dans votre périmètre.</td></tr>'; return; }
  state.stationCache.forEach(s => {
    const tr = el("tr");
    const st = s.status === "active" ? '<span class="badge b-ok">active</span>' : '<span class="badge b-grey">inactive</span>';
    let act = "";
    if (can(RV)) {
      const next = s.status === "active" ? "inactive" : "active";
      act = `<button class="btn sm" data-station-toggle="${s.id}" data-next="${next}">${s.status === "active" ? "Désactiver" : "Activer"}</button>`;
    }
    tr.innerHTML = `<td class="num">${esc(s.code)}</td><td>${esc(s.name)}</td><td>${esc(s.type)}</td><td>${esc(s.parameter)}</td>
      <td>${esc(s.unit)}</td><td>${esc(s.governorate || "")}</td><td>${st}</td><td class="actions">${act}</td>`;
    tb.appendChild(tr);
  });
}

export async function createStation() {
  const lat = parseFloat($("#sLat").value), lon = parseFloat($("#sLon").value);
  const payload = {
    code: $("#sCode").value.trim(), name: $("#sName").value.trim(),
    type: $("#sType").value, parameter: $("#sParameter").value, unit: $("#sUnit").value,
    governorate: $("#sGov").value.trim() || null, latitude: isNaN(lat) ? null : lat, longitude: isNaN(lon) ? null : lon,
    altitude_m: $("#sAlt").value ? Number($("#sAlt").value) : null,
    sampling_interval_min: $("#sSampling").value ? Number($("#sSampling").value) : null,
    unite_id: $("#sUnite").value ? Number($("#sUnite").value) : null,
  };
  if (!payload.code || !payload.name || payload.latitude === null || payload.longitude === null) { toast("Code, nom, latitude et longitude requis.", "err"); return; }
  try {
    const created = await api("/stations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    ["#sCode", "#sName", "#sGov", "#sLat", "#sLon", "#sAlt", "#sSampling", "#sUnite"].forEach(i => $(i).value = "");
    await loadStations();
    if (created.station_key) openModal(`<h3>Station créée</h3><p>Clé machine — à copier maintenant, elle ne sera plus affichée :</p><div class="keybox">${esc(created.station_key)}</div>`);
    else toast("Station créée.", "ok");
  } catch (e) { toast(e.detail, "err"); }
}

export async function toggleStation(id, next) {
  try {
    await api("/stations/" + id, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: next }) });
    toast("Station mise à jour.", "ok");
    await loadStations();
  } catch (e) { toast(e.detail, "err"); }
}

export function initStations() {
  $("#sAddBtn").onclick = createStation;
}
