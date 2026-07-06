import { $, el, esc } from "../dom.js";
import { api } from "../api.js";
import { toast, openModal } from "../toast.js";

const ROLES = ["agent", "observateur", "analyste", "responsable", "directeur", "administrateur"];

export async function loadUsers() {
  try {
    const rows = await api("/admin/users");
    const tb = $("#usersBody");
    tb.innerHTML = "";
    rows.forEach(u => {
      const tr = el("tr");
      const roleSel = `<select data-role-for="${u.id}">${ROLES.map(r => `<option value="${r}"${r === u.role ? " selected" : ""}>${r}</option>`).join("")}</select>`;
      const actBtn = `<button class="btn sm" data-toggle-active="${u.id}" data-next="${u.is_active ? 0 : 1}">${u.is_active ? "Désactiver" : "Activer"}</button>`;
      const lockBtn = u.locked ? `<button class="btn sm" data-unlock="${u.id}">Déverrouiller</button>` : "";
      const resetBtn = `<button class="btn sm" data-reset="${u.id}">Réinit. mdp</button>`;
      tr.innerHTML = `<td class="num">${u.id}</td><td>${esc(u.username)}</td><td>${esc(u.full_name || "")}</td><td>${roleSel}</td>
        <td>${u.is_active ? '<span class="badge b-ok">oui</span>' : '<span class="badge b-grey">non</span>'}</td>
        <td>${u.locked ? '<span class="badge b-bad">verrouillé</span>' : '<span class="badge b-grey">non</span>'}</td>
        <td class="actions">${actBtn} ${lockBtn} ${resetBtn}</td>`;
      tb.appendChild(tr);
    });
  } catch (e) { toast(e.detail, "err"); }
}

export async function createUser() {
  const payload = {
    username: $("#uUser").value.trim(), password: $("#uPass").value, full_name: $("#uFull").value.trim() || null,
    role: $("#uRole").value, unite_id: $("#uUnite").value ? Number($("#uUnite").value) : null, superviseur_id: $("#uSup").value ? Number($("#uSup").value) : null,
  };
  if (!payload.username || !payload.password) { toast("Identifiant et mot de passe requis.", "err"); return; }
  try {
    await api("/admin/users", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    toast("Compte créé.", "ok"); ["#uUser", "#uPass", "#uFull", "#uUnite", "#uSup"].forEach(i => $(i).value = ""); await loadUsers();
  } catch (e) { toast(e.detail, "err"); }
}

export async function patchUser(id, body) {
  try {
    await api("/admin/users/" + id, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    toast("Compte mis à jour.", "ok"); await loadUsers();
  } catch (e) { toast(e.detail, "err"); }
}

export async function unlockUser(id) {
  try { await api("/admin/users/" + id + "/unlock", { method: "POST" }); toast("Compte déverrouillé.", "ok"); await loadUsers(); }
  catch (e) { toast(e.detail, "err"); }
}

export async function resetUser(id) {
  if (!confirm("Réinitialiser le mot de passe ? Un nouveau sera généré et affiché une seule fois.")) return;
  try {
    const r = await api("/admin/users/" + id + "/reset-password", { method: "POST" });
    openModal(`<h3>Mot de passe réinitialisé — ${esc(r.username)}</h3><p>Nouveau mot de passe — à transmettre maintenant, non restocké :</p><div class="keybox">${esc(r.nouveau_mot_de_passe)}</div>`);
    await loadUsers();
  } catch (e) { toast(e.detail, "err"); }
}

export function initAccounts() {
  $("#uAddBtn").onclick = createUser;
}
