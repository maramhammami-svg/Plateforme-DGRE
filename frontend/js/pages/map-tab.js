import { $ } from "../dom.js";
import { ensureMap, paintMarkers, fmapH } from "../map.js";

export function loadMap() {
  ensureMap("map", fmapH);
  paintMarkers(fmapH, $("#mapGovFilter").value);
}

export function initMapTab() {
  $("#mapGovFilter").onchange = () => paintMarkers(fmapH, $("#mapGovFilter").value);
}
