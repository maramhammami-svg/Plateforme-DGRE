import { esc, qs } from "./dom.js";
import { api } from "./api.js";
import { toast } from "./toast.js";

const QCOLOR = { ok: "#128A5B", suspect: "#B4780C", aberrant: "#C23A22", manquant: "#7C8A99", inconnu: "#2E7CC4", inactive: "#7C8A99" };

function qcolor(q) {
  const cs = getComputedStyle(document.documentElement);
  const map = { ok: "--ok", suspect: "--warn", aberrant: "--bad", manquant: "--grey", inconnu: "--info", inactive: "--grey" };
  return (cs.getPropertyValue(map[q] || "--info").trim()) || QCOLOR[q] || "#2E7CC4";
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
      let html = `<b>${esc(mk.code)} · ${esc(mk.name)}</b><br>statut : ${esc(mk.status)}<br>qualité : ${esc(mk.quality)}`;
      if (mk.type === "automatique") {
        const pct = mk.battery_level == null ? "—" : Math.round(mk.battery_level * 100) + "%";
        html += `<br>capteur : ${esc(mk.sensor_status)}`
          + `<br>batterie : ${pct}`
          + `<br>dernière transmission : ${lastTransmissionLabel(mk.silence_hours)}`
          + `<br>santé : ${esc(HEALTH_LABEL[mk.health] || mk.health)}`;
      }
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
