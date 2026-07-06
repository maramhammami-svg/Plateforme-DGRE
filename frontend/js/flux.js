import { $, el, esc } from "./dom.js";
import { api } from "./api.js";

function resultDot(r) { return r === "success" ? "d-ok" : (r === "denied" || r === "failure" ? "" : "d-warn"); }

export async function loadFluxStrip() {
  try {
    const rows = await api("/events?limit=200");
    let ok = 0, dn = 0, fa = 0;
    rows.forEach(e => { if (e.result === "success") ok++; else if (e.result === "denied") dn++; else if (e.result === "failure") fa++; });
    $("#fsOk").textContent = ok; $("#fsDenied").textContent = dn; $("#fsFail").textContent = fa;
  } catch (e) { /* silencieux : ne pas gêner la topbar si /events échoue */ }
}

export async function loadFluxFeed() {
  try {
    const rows = await api("/events?limit=20");
    const feed = $("#fluxFeed");
    feed.innerHTML = "";
    if (!rows.length) { feed.innerHTML = '<div class="empty">Aucun événement.</div>'; return; }
    rows.forEach(ev => {
      const row = el("div", "ev " + (ev.result === "denied" ? "denied" : (ev.result === "failure" ? "failure" : "")));
      const dotCls = resultDot(ev.result);
      const dotStyle = dotCls ? "" : 'style="background:var(--bad)"';
      const meta = [ev.actor_username || "—", ev.resource_type ? (ev.resource_type + (ev.resource_id ? " #" + ev.resource_id : "")) : "", ev.channel_ip || ""].filter(Boolean).join(" · ");
      row.innerHTML = `<span class="dot ${dotCls}" ${dotStyle}></span>
        <div><span class="act">${esc(ev.action)}</span><div class="meta">${esc(meta)}</div></div>
        <div class="rt">${esc(ev.result)}<br>#${ev.id}</div>`;
      feed.appendChild(row);
    });
  } catch (e) { /* silencieux, comme la version d'origine */ }
}
