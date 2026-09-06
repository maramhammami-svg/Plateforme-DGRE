import { $, el, esc, qs } from "../dom.js";
import { api } from "../api.js";
import { toast } from "../toast.js";

const HEALTH_LABEL = { ok: "OK", warning: "Avertissement", critical: "Critique" };
const SENSOR_BADGE = { operational: "b-ok", degraded: "b-warn", offline: "b-bad", unknown: "b-grey" };

function batteryColor(level) {
  if (level == null) return "var(--grey)";
  if (level > 0.6) return "var(--ok)";
  if (level > 0.2) return "var(--warn)";
  return "var(--bad)";
}

function lastTransmissionLabel(hours) {
  if (hours == null) return "Jamais";
  return `il y a ${Math.round(hours)} h`;
}

function renderCard(s) {
  const card = el("div", `shcard sh-${s.health}`);
  const pct = s.battery_level == null ? 0 : Math.round(s.battery_level * 100);
  card.innerHTML = `
    <div class="sh-top">
      <div>
        <div class="sh-name">${esc(s.name)}</div>
        <div class="sh-code mono">${esc(s.code)}${s.governorate ? " · " + esc(s.governorate) : ""}</div>
      </div>
      <i class="sh-dot" title="${esc(HEALTH_LABEL[s.health] || s.health)}"></i>
    </div>
    <div class="row" style="gap:8px; align-items:center; margin:10px 0">
      <div class="bar"><i style="width:${pct}%; background:${batteryColor(s.battery_level)}"></i></div>
      <span class="num mono">${s.battery_level == null ? "—" : pct + "%"}</span>
    </div>
    <div class="sh-row"><span class="badge ${SENSOR_BADGE[s.sensor_status] || "b-grey"}">${esc(s.sensor_status)}</span></div>
    <div class="sh-last">Dernière transmission : ${lastTransmissionLabel(s.silence_hours)}</div>`;
  return card;
}

export async function loadStationHealth() {
  const grid = $("#shGrid");
  try {
    const list = await api("/dashboard/station-health" + qs({ governorate: $("#shGovFilter").value }));
    const counts = { ok: 0, warning: 0, critical: 0 };
    list.forEach(s => { counts[s.health] = (counts[s.health] || 0) + 1; });
    $("#shOk").textContent = counts.ok;
    $("#shWarn").textContent = counts.warning;
    $("#shBad").textContent = counts.critical;
    grid.innerHTML = "";
    if (!list.length) { grid.innerHTML = '<div class="empty">Aucune station dans votre périmètre.</div>'; return; }
    list.forEach(s => grid.appendChild(renderCard(s)));
  } catch (e) { toast(e.detail, "err"); }
}

export function initStationHealth() {
  $("#shGovFilter").onchange = loadStationHealth;
}
