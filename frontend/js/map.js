import { esc, qs } from "./dom.js";
import { api } from "./api.js";
import { toast } from "./toast.js";

const QCOLOR = { ok: "#128A5B", suspect: "#B4780C", aberrant: "#C23A22", manquant: "#7C8A99", inconnu: "#2E7CC4", inactive: "#7C8A99" };

function qcolor(q) {
  const cs = getComputedStyle(document.documentElement);
  const map = { ok: "--ok", suspect: "--warn", aberrant: "--bad", manquant: "--grey", inconnu: "--info", inactive: "--grey" };
  return (cs.getPropertyValue(map[q] || "--info").trim()) || QCOLOR[q] || "#2E7CC4";
}

const STATUS_BADGE = { active: "b-ok", inactive: "b-grey" };
const QUALITY_BADGE = { ok: "b-ok", suspect: "b-warn", aberrant: "b-bad", manquant: "b-grey", inconnu: "b-info", inactive: "b-grey" };
const SENSOR_BADGE = { operational: "b-ok", degraded: "b-warn", offline: "b-bad", unknown: "b-grey" };
const HEALTH_BADGE = { ok: "b-ok", warning: "b-warn", critical: "b-bad" };

function batteryColor(level) {
  if (level == null) return "var(--grey)";
  if (level > 0.6) return "var(--ok)";
  if (level > 0.2) return "var(--warn)";
  return "var(--bad)";
}

const HEALTH_LABEL = { ok: "OK", warning: "Avertissement", critical: "Critique" };

function lastTransmissionLabel(hours) {
  if (hours == null) return "Jamais";
  return `il y a ${Math.round(hours)} h`;
}

export const dmapH = {};
export const fmapH = {};

export function ensureMap(id, holder) {
  if (!holder.map) {
    holder.map = L.map(id).setView([34.0, 9.5], 6);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: "© OpenStreetMap" }).addTo(holder.map);
    holder.layer = L.layerGroup().addTo(holder.map);
  }
  setTimeout(() => holder.map.invalidateSize(), 60);
}

export async function paintMarkers(holder, governorate) {
  try {
    const markers = await api("/dashboard/map" + qs({ governorate }));
    holder.layer.clearLayers();
    const pts = [];
    markers.forEach(mk => {
      const cm = L.circleMarker([mk.latitude, mk.longitude], { radius: 7, color: "#fff", weight: 1.5, fillColor: qcolor(mk.quality), fillOpacity: .9 });
      let html = `
        <div class="mpop">
          <div class="mpop-name">${esc(mk.name)}</div>
          <div class="mpop-code">${esc(mk.code)}</div>
          <div class="mpop-row"><span class="mpop-label">Statut</span><span class="badge ${STATUS_BADGE[mk.status] || "b-grey"}">${esc(mk.status)}</span></div>
          <div class="mpop-row"><span class="mpop-label">Qualité</span><span class="badge ${QUALITY_BADGE[mk.quality] || "b-info"}">${esc(mk.quality)}</span></div>`;
      if (mk.type === "automatique") {
        const pct = mk.battery_level == null ? null : Math.round(mk.battery_level * 100);
        html += `
          <div class="mpop-sep"></div>
          <div class="mpop-row"><span class="mpop-label">Capteur</span><span class="badge ${SENSOR_BADGE[mk.sensor_status] || "b-grey"}">${esc(mk.sensor_status)}</span></div>
          <div class="mpop-row"><span class="mpop-label">Batterie</span><div class="bar mpop-bar"><i style="width:${pct ?? 0}%; background:${batteryColor(mk.battery_level)}"></i></div><span class="mono">${pct == null ? "—" : pct + "%"}</span></div>
          <div class="mpop-row"><span class="mpop-label">Transmission</span><span>${lastTransmissionLabel(mk.silence_hours)}</span></div>
          <div class="mpop-row"><span class="mpop-label">Santé</span><span class="badge ${HEALTH_BADGE[mk.health] || "b-grey"}">${esc(HEALTH_LABEL[mk.health] || mk.health)}</span></div>`;
      }
      html += `</div>`;
      cm.bindPopup(html);
      cm.addTo(holder.layer);
      pts.push([mk.latitude, mk.longitude]);
    });
    if (pts.length) holder.map.fitBounds(pts, { padding: [30, 30], maxZoom: 9 });
  } catch (e) { toast(e.detail, "err"); }
}

export function invalidateMaps() {
  if (dmapH.map) setTimeout(() => dmapH.map.invalidateSize(), 60);
  if (fmapH.map) setTimeout(() => fmapH.map.invalidateSize(), 60);
}
