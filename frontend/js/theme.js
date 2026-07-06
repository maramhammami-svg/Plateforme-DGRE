import { $ } from "./dom.js";
import { THEME_KEY } from "./state.js";
import { invalidateMaps } from "./map.js";

export function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  localStorage.setItem(THEME_KEY, t);
}

export function initTheme() {
  applyTheme(localStorage.getItem(THEME_KEY) || "dark");
  $("#themeBtn").onclick = () => {
    applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
    invalidateMaps();
  };
}
