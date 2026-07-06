import { $ } from "./dom.js";
import { state, TOKEN_KEY } from "./state.js";
import { api } from "./api.js";
import { toast } from "./toast.js";
import { can, RW, RV, REV } from "./roles.js";
import { showTab } from "./router.js";
import { loadStations } from "./pages/stations.js";
import { loadFluxStrip } from "./flux.js";

function initials(u) { return (u.full_name || u.username || "?").split(/\s+/).map(w => w[0]).slice(0, 2).join("").toUpperCase(); }

function landingTab() {
  if (state.me.role === "agent" || state.me.role === "observateur") return "readings";
  if (state.me.role === "administrateur") return "accounts";
  return "dashboard";
}

export async function doLogin() {
  const u = $("#liUser").value.trim(), p = $("#liPass").value;
  if (!u || !p) { toast("Saisissez vos identifiants.", "err"); return; }
  try {
    const data = await api("/auth/login", { method: "POST", body: new URLSearchParams({ username: u, password: p }) });
    state.token = data.access_token; localStorage.setItem(TOKEN_KEY, state.token);
    await boot();
  } catch (e) { toast(e.detail || "Connexion impossible.", "err"); }
}

export function doLogout() {
  state.token = null; state.me = null; localStorage.removeItem(TOKEN_KEY);
  if (state.autoTimer) { clearInterval(state.autoTimer); state.autoTimer = null; }
  if (state.fluxTimer) { clearInterval(state.fluxTimer); state.fluxTimer = null; }
  $("#appView").classList.add("hidden"); $("#whoBox").classList.add("hidden"); $("#fluxStrip").classList.add("hidden");
  $("#loginView").classList.remove("hidden");
}

window.addEventListener("auth:unauthorized", () => { doLogout(); toast("Session expirée", "err"); });

export async function boot() {
  state.me = await api("/auth/me");
  $("#whoName").textContent = state.me.full_name || state.me.username;
  $("#whoRole").textContent = state.me.role;
  $("#whoAv").textContent = initials(state.me);
  $("#whoBox").classList.remove("hidden");
  $("#loginView").classList.add("hidden");
  $("#appView").classList.remove("hidden");

  document.querySelectorAll('[data-need="admin"]').forEach(n => n.classList.toggle("hidden", state.me.role !== "administrateur"));
  document.querySelectorAll('[data-need="events"]').forEach(n => n.classList.toggle("hidden", !can(REV)));
  $("#readingWriteCard").classList.toggle("hidden", !can(RW));
  $("#stationCreateCard").classList.toggle("hidden", !can(RV));
  $("#fluxCard").classList.toggle("hidden", !can(REV));
  $("#dashCols").classList.toggle("solo", !can(REV));
  $("#dashScope").textContent = "année hydro 2024 (sept → août) · périmètre selon votre rôle";

  await loadStations();
  if (can(REV)) { $("#fluxStrip").classList.remove("hidden"); loadFluxStrip(); state.fluxTimer = setInterval(loadFluxStrip, 8000); }
  showTab(landingTab());
}

export function initAuth() {
  $("#loginBtn").onclick = doLogin;
  $("#liPass").addEventListener("keydown", e => { if (e.key === "Enter") doLogin(); });
  $("#logoutBtn").onclick = doLogout;
  if (state.token) { boot().catch(() => doLogout()); }
}
