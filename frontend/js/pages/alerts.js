import { $, el, esc, qs } from "../dom.js";
import { api } from "../api.js";
import { toast } from "../toast.js";
import { state } from "../state.js";

// Rafraichissement automatique de l'onglet Alertes : un tick par seconde met a
// jour le bandeau "agent vivant" (calcul local, sans appel API) ; toutes les
// REFRESH_EVERY_TICKS secondes, on recharge alertes + stats + statut agent.
const REFRESH_EVERY_TICKS = 5;
let tickCount = 0;
let agentState = null;        // dernier GET /agent/status (null = indisponible)
let agentStateError = false;
let lastMaxId = null;         // null = pas de reference : aucune notif "nouvelle alerte"

const SEVERITY_BADGE = { critical: ["b-bad", "critique"], high: ["b-warn", "élevée"], medium: ["b-info", "moyenne"] };
const STATUS_BADGE = { open: ["b-bad", "ouverte"], acknowledged: ["b-warn", "acquittée"],
                       resolved: ["b-ok", "résolue"], false_positive: ["b-grey", "faux positif"] };

function severityBadge(s) { const [c, l] = SEVERITY_BADGE[s] || ["b-grey", s]; return `<span class="badge ${c}">${esc(l)}</span>`; }
function statusBadge(s) { const [c, l] = STATUS_BADGE[s] || ["b-grey", s]; return `<span class="badge ${c}">${esc(l)}</span>`; }
function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export async function loadAlertsStats(silent = false) {
  try {
    const stats = await api("/alerts/stats");
    $("#alCritical").textContent = stats.by_severity.critical || 0;
    $("#alHigh").textContent = stats.by_severity.high || 0;
    $("#alMedium").textContent = stats.by_severity.medium || 0;
    $("#alOpen").textContent = stats.by_status.open || 0;
  } catch (e) { if (!silent) toast(e.detail, "err"); }
}

function fmtDuration(sec) {
  sec = Math.max(0, Math.round(sec));
  if (sec < 60) return `${sec} s`;
  const m = Math.floor(sec / 60);
  return m < 60 ? `${m} min ${sec % 60} s` : `${Math.floor(m / 60)} h ${m % 60} min`;
}

function renderAgentStatus() {
  const box = $("#agentStatus");
  if (!box) return;
  let dot = "d-ok", text;
  const st = agentState;
  if (agentStateError || !st) {
    dot = "d-grey";
    text = "Statut de l'agent indisponible.";
  } else if (!st.running) {
    dot = "d-bad";
    text = "Agent arrêté : aucun scan automatique (scan manuel uniquement).";
  } else if (!st.last_scan_at) {
    text = `Agent actif · premier scan dans ≤ ${st.interval_sec} s`;
  } else {
    const elapsed = (Date.now() - Date.parse(st.last_scan_at)) / 1000;
    const next = st.interval_sec - elapsed;
    if (st.last_error) {
      dot = "d-warn";
      text = `Agent actif · dernier scan en échec : ${st.last_error}`;
    } else if (elapsed > st.interval_sec * 2 + 10) {
      dot = "d-warn";
      text = `Agent actif mais aucun scan depuis ${fmtDuration(elapsed)} (thread bloqué ?)`;
    } else {
      text = `Agent actif · dernier scan il y a ${fmtDuration(elapsed)}`
        + ` · prochain ${next > 1 ? "dans ~" + fmtDuration(next) : "imminent"}`
        + ` · ${st.last_scan_new_alerts} nouvelle(s) alerte(s) au dernier scan`
        + ` · ${st.scan_count} scan(s) depuis le démarrage`;
    }
  }
  // Mise a jour en place (pas d'innerHTML) : l'animation .pulse du point ne
  // redemarre pas a chaque seconde.
  box.querySelector(".as-dot").className = `as-dot ${dot}${dot === "d-ok" ? " pulse" : ""}`;
  box.querySelector(".as-text").textContent = text;
}

export async function loadAgentStatus() {
  try { agentState = await api("/agent/status"); agentStateError = false; }
  catch (e) { agentStateError = true; }
  renderAgentStatus();
}

function alertsTabVisible() {
  const sec = $("#tab-alerts");
  return !!sec && !sec.classList.contains("hidden");
}

export function stopAlertsAuto() {
  if (state.alertsTimer) { clearInterval(state.alertsTimer); state.alertsTimer = null; }
}

function alertsTick() {
  // L'onglet n'est plus affiche (ou deconnexion) : on s'arrete, loadAlerts()
  // relancera le timer au prochain affichage de l'onglet.
  if (!state.token || !alertsTabVisible()) { stopAlertsAuto(); return; }
  tickCount += 1;
  if (tickCount % REFRESH_EVERY_TICKS !== 0) { renderAgentStatus(); return; }
  // Le statut de l'agent est toujours rafraichi (sinon le bandeau vieillirait et
  // afficherait a tort "aucun scan depuis...") ; la liste seulement en mode direct.
  if ($("#alAuto").checked) loadAlerts({ silent: true });
  else loadAgentStatus();
}

function startAlertsAuto() {
  if (state.alertsTimer) return;
  tickCount = 0;
  state.alertsTimer = setInterval(alertsTick, 1000);
}

export async function loadAlerts({ silent = false } = {}) {
  startAlertsAuto();
  loadAlertsStats(silent);
  loadAgentStatus();
  const params = { severity: $("#alSeverity").value, status: $("#alStatus").value, per_page: 100 };
  try {
    const rows = await api("/alerts" + qs(params));
    const tb = $("#alertsBody");
    tb.innerHTML = "";
    const maxId = rows.reduce((m, a) => Math.max(m, a.id), 0);
    const fresh = lastMaxId === null ? [] : rows.filter(a => a.id > lastMaxId);
    lastMaxId = maxId;
    if (fresh.length) {
      const a = fresh[0];
      const [, sev] = SEVERITY_BADGE[a.severity] || [null, a.severity];
      toast(fresh.length === 1
        ? `Nouvelle alerte (${sev}) : ${a.rule_name}${a.actor_username ? " · " + a.actor_username : ""}`
        : `${fresh.length} nouvelles alertes détectées par l'agent`, "err");
    }
    const freshIds = new Set(fresh.map(a => a.id));
    if (!rows.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">Aucune alerte.</td></tr>'; return; }
    rows.forEach(a => {
      const tr = el("tr");
      if (freshIds.has(a.id)) tr.classList.add("flash");
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
  } catch (e) { if (!silent) toast(e.detail, "err"); }
}

export async function acknowledgeAlert(id) {
  try {
    await api("/alerts/" + id + "/acknowledge", { method: "PATCH" });
    toast("Alerte acquittée.", "ok"); await loadAlerts();
  } catch (e) { toast(e.detail, "err"); }
}

export async function resolveAlert(id) {
  try {
    await api("/alerts/" + id + "/resolve", { method: "PATCH" });
    toast("Alerte résolue.", "ok"); await loadAlerts();
  } catch (e) { toast(e.detail, "err"); }
}

export async function markFalsePositive(id) {
  try {
    await api("/alerts/" + id + "/false-positive", { method: "PATCH" });
    toast("Alerte marquée faux positif.", "ok"); await loadAlerts();
  } catch (e) { toast(e.detail, "err"); }
}

export async function triggerScan() {
  try {
    const res = await api("/agent/scan", { method: "POST" });
    toast(`Scan terminé : ${res.new_alerts} nouvelle(s) alerte(s).`, "ok");
    await loadAlerts();
  } catch (e) { toast(e.detail, "err"); }
}

function onFilterChange() {
  lastMaxId = null;   // nouveau filtre : pas de fausse notification "nouvelle alerte"
  loadAlerts();
}

export function initAlerts() {
  $("#alSeverity").onchange = onFilterChange;
  $("#alStatus").onchange = onFilterChange;
  $("#alRefresh").onclick = () => loadAlerts();
  $("#alScan").onclick = triggerScan;
}
