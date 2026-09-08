import { $, el, esc, qs } from "../dom.js";
import { api } from "../api.js";
import { toast } from "../toast.js";

const SEVERITY_BADGE = { critical: ["b-bad", "critique"], high: ["b-warn", "élevée"], medium: ["b-info", "moyenne"] };
const STATUS_BADGE = { open: ["b-bad", "ouverte"], acknowledged: ["b-warn", "acquittée"],
                       resolved: ["b-ok", "résolue"], false_positive: ["b-grey", "faux positif"] };

function severityBadge(s) { const [c, l] = SEVERITY_BADGE[s] || ["b-grey", s]; return `<span class="badge ${c}">${esc(l)}</span>`; }
function statusBadge(s) { const [c, l] = STATUS_BADGE[s] || ["b-grey", s]; return `<span class="badge ${c}">${esc(l)}</span>`; }
function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export async function loadAlertsStats() {
  try {
    const stats = await api("/alerts/stats");
    $("#alCritical").textContent = stats.by_severity.critical || 0;
    $("#alHigh").textContent = stats.by_severity.high || 0;
    $("#alMedium").textContent = stats.by_severity.medium || 0;
    $("#alOpen").textContent = stats.by_status.open || 0;
  } catch (e) { toast(e.detail, "err"); }
}

export async function loadAlerts() {
  loadAlertsStats();
  const params = { severity: $("#alSeverity").value, status: $("#alStatus").value, per_page: 100 };
  try {
    const rows = await api("/alerts" + qs(params));
    const tb = $("#alertsBody");
    tb.innerHTML = "";
    if (!rows.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">Aucune alerte.</td></tr>'; return; }
    rows.forEach(a => {
      const tr = el("tr");
      let act = "";
      if (a.status === "open") {
        act = `<button class="btn sm" data-ack="${a.id}">Acquitter</button>
               <button class="btn sm" data-resolve="${a.id}">Résoudre</button>
               <button class="btn sm" data-fp="${a.id}">Faux positif</button>`;
      } else if (a.status === "acknowledged") {
        act = `<button class="btn sm" data-resolve="${a.id}">Résoudre</button>
               <button class="btn sm" data-fp="${a.id}">Faux positif</button>`;
      }
      tr.innerHTML = `<td class="num">${a.id}</td><td>${severityBadge(a.severity)}</td><td>${statusBadge(a.status)}</td>
        <td>${esc(a.rule_name)}</td><td>${esc(a.actor_username || "—")}</td><td>${esc(a.description)}</td>
        <td class="num">${fmtDate(a.created_at)}</td><td class="actions">${act}</td>`;
      tb.appendChild(tr);
    });
  } catch (e) { toast(e.detail, "err"); }
}

export async function acknowledgeAlert(id) {
  try {
    await api("/alerts/" + id + "/acknowledge", { method: "PATCH" });
    toast("Alerte acquittée.", "ok"); await loadAlerts(); await loadAlertsStats();
  } catch (e) { toast(e.detail, "err"); }
}

export async function resolveAlert(id) {
  try {
    await api("/alerts/" + id + "/resolve", { method: "PATCH" });
    toast("Alerte résolue.", "ok"); await loadAlerts(); await loadAlertsStats();
  } catch (e) { toast(e.detail, "err"); }
}

export async function markFalsePositive(id) {
  try {
    await api("/alerts/" + id + "/false-positive", { method: "PATCH" });
    toast("Alerte marquée faux positif.", "ok"); await loadAlerts(); await loadAlertsStats();
  } catch (e) { toast(e.detail, "err"); }
}

export async function triggerScan() {
  try {
    const res = await api("/agent/scan", { method: "POST" });
    toast(`Scan terminé : ${res.new_alerts} nouvelle(s) alerte(s).`, "ok");
    await loadAlerts(); await loadAlertsStats();
  } catch (e) { toast(e.detail, "err"); }
}

export function initAlerts() {
  $("#alSeverity").onchange = loadAlerts;
  $("#alStatus").onchange = loadAlerts;
  $("#alRefresh").onclick = loadAlerts;
  $("#alScan").onclick = triggerScan;
}
