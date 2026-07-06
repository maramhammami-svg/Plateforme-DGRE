import { esc } from "./dom.js";
import { api } from "./api.js";
import { toast } from "./toast.js";

const QCOLOR = { ok: "#128A5B", suspect: "#B4780C", aberrant: "#C23A22", manquant: "#7C8A99", inconnu: "#2E7CC4", inactive: "#7C8A99" };

function qcolor(q) {
  const cs = getComputedStyle(document.documentElement);
  const map = { ok: "--ok", suspect: "--warn", aberrant: "--bad", manquant: "--grey", inconnu: "--info", inactive: "--grey" };
  return (cs.getPropertyValue(map[q] || "--info").trim()) || QCOLOR[q] || "#2E7CC4";
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

export async function paintMarkers(holder) {
  try {
    const markers = await api("/dashboard/map");
    holder.layer.clearLayers();
    const pts = [];
    markers.forEach(mk => {
      const cm = L.circleMarker([mk.latitude, mk.longitude], { radius: 7, color: "#fff", weight: 1.5, fillColor: qcolor(mk.quality), fillOpacity: .9 });
      cm.bindPopup(`<b>${esc(mk.code)} · ${esc(mk.name)}</b><br>statut : ${esc(mk.status)}<br>qualité : ${esc(mk.quality)}`);
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
