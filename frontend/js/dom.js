export const $ = s => document.querySelector(s);
export const el = (t, c) => { const e = document.createElement(t); if (c) e.className = c; return e; };
export const esc = s => (s == null ? "" : String(s)).replace(/[&<>"]/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[m]));
export const pct = v => v == null ? "—" : Math.round(v * 100) + "%";
export const qs = obj => {
  const p = new URLSearchParams();
  for (const k in obj) { if (obj[k] !== "" && obj[k] != null) p.append(k, obj[k]); }
  const s = p.toString();
  return s ? ("?" + s) : "";
};
