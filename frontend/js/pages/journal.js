import { $, el, esc } from "../dom.js";
import { api } from "../api.js";
import { toast } from "../toast.js";
import { state } from "../state.js";

function resultBadge(r) {
  return r === "success" ? '<span class="badge b-ok">succès</span>'
    : (r === "denied" ? '<span class="badge b-bad">refusé</span>'
    : (r === "failure" ? '<span class="badge b-bad">échec</span>'
    : `<span class="badge b-info">${esc(r)}</span>`));
}

export async function loadJournal() {
  try {
    const rows = await api("/events?limit=150");
    const tb = $("#journalBody");
    tb.innerHTML = "";
    if (!rows.length) { tb.innerHTML = '<tr><td colspan="10" class="empty">Journal vide.</td></tr>'; return; }
    const newTop = rows[0].id;
    rows.forEach(ev => {
      const tr = el("tr");
      if (ev.id > state.lastTopEventId && state.lastTopEventId > 0) tr.classList.add("flash");
      if (ev.unite_acteur && ev.unite_ressource && ev.unite_acteur !== ev.unite_ressource) tr.classList.add("divergent");
      tr.innerHTML = `<td>${ev.id}</td><td>${esc(ev.actor_username || "—")}</td><td>${esc(ev.role || "")}</td><td>${esc(ev.unite_acteur || "")}</td>
        <td class="act">${esc(ev.action)}</td><td>${esc(ev.resource_type || "")}${ev.resource_id ? (" #" + esc(ev.resource_id)) : ""}</td>
        <td>${esc(ev.unite_ressource || "")}</td><td>${ev.volume ?? ""}</td><td>${esc(ev.channel_ip || "")}</td><td>${resultBadge(ev.result)}</td>`;
      tb.appendChild(tr);
    });
    state.lastTopEventId = newTop;
  } catch (e) { toast(e.detail, "err"); }
}

export function initJournal() {
  $("#jRefresh").onclick = loadJournal;
  $("#jAuto").onchange = e => {
    if (e.target.checked) { state.autoTimer = setInterval(loadJournal, 3000); }
    else if (state.autoTimer) { clearInterval(state.autoTimer); state.autoTimer = null; }
  };
}
