import { ensureMap, paintMarkers, fmapH } from "../map.js";

export function loadMap() {
  ensureMap("map", fmapH);
  paintMarkers(fmapH);
}
