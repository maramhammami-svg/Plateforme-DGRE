import { initTheme } from "./theme.js";
import { initAuth } from "./auth.js";
import { initRouter } from "./router.js";
import { initDashboard } from "./pages/dashboard.js";
import { initReadings, correctReading, showVersions, validateReading, deleteReading } from "./pages/readings.js";
import { initStations, toggleStation } from "./pages/stations.js";
import { initConsolidations } from "./pages/consolidations.js";
import { initDocuments, downloadDoc } from "./pages/documents.js";
import { initAccounts, patchUser, unlockUser, resetUser } from "./pages/accounts.js";
import { initAccount } from "./pages/account.js";
import { initJournal } from "./pages/journal.js";

initTheme();
initRouter();
initDashboard();
initReadings();
initStations();
initConsolidations();
initDocuments();
initAccounts();
initAccount();
initJournal();
initAuth();

document.addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  if (b.dataset.correct) correctReading(b.dataset.correct, b.dataset.val);
  else if (b.dataset.versions) showVersions(b.dataset.versions);
  else if (b.dataset.validate) validateReading(b.dataset.validate, b.dataset.dec);
  else if (b.dataset.delete) deleteReading(b.dataset.delete);
  else if (b.dataset.stationToggle) toggleStation(b.dataset.stationToggle, b.dataset.next);
  else if (b.dataset.doc) downloadDoc(b.dataset.doc);
  else if (b.dataset.toggleActive) patchUser(b.dataset.toggleActive, { is_active: Number(b.dataset.next) });
  else if (b.dataset.unlock) unlockUser(b.dataset.unlock);
  else if (b.dataset.reset) resetUser(b.dataset.reset);
});
document.addEventListener("change", e => { const s = e.target; if (s.dataset && s.dataset.roleFor) patchUser(s.dataset.roleFor, { role: s.value }); });
