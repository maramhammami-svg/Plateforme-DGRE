import { $ } from "./dom.js";
import { loadDashboard } from "./pages/dashboard.js";
import { loadMap } from "./pages/map-tab.js";
import { loadJournal } from "./pages/journal.js";
import { loadReadings } from "./pages/readings.js";
import { loadConsolidations } from "./pages/consolidations.js";
import { loadDocuments } from "./pages/documents.js";
import { loadUsers } from "./pages/accounts.js";

export const TABS = ["dashboard", "map", "journal", "readings", "stations", "consolidations", "documents", "accounts", "account"];

const LOADERS = {
  dashboard: loadDashboard,
  map: loadMap,
  journal: loadJournal,
  readings: loadReadings,
  consolidations: loadConsolidations,
  documents: loadDocuments,
  accounts: loadUsers,
};

export function showTab(name) {
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === name));
  TABS.forEach(n => $("#tab-" + n).classList.toggle("hidden", n !== name));
  const loader = LOADERS[name];
  if (loader) loader();
}

export function initRouter() {
  document.querySelectorAll(".tab").forEach(t => t.onclick = () => showTab(t.dataset.tab));
}
