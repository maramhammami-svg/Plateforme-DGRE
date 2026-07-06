import { $ } from "../dom.js";
import { api } from "../api.js";
import { toast } from "../toast.js";

export async function changePassword() {
  const ancien = $("#pOld").value, nouveau = $("#pNew").value;
  if (!ancien || !nouveau) { toast("Renseignez les deux champs.", "err"); return; }
  try {
    await api("/auth/password", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ancien, nouveau }) });
    toast("Mot de passe mis à jour.", "ok"); $("#pOld").value = ""; $("#pNew").value = "";
  } catch (e) { toast(e.detail, "err"); }
}

export function initAccount() {
  $("#pBtn").onclick = changePassword;
}
