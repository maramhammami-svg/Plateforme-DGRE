import { state } from "./state.js";

const API = "";

async function asError(res) {
  let d = null;
  try { d = await res.json(); } catch { /* body not JSON */ }
  return { status: res.status, detail: (d && d.detail) || res.statusText };
}

export async function api(path, opts = {}) {
  const headers = opts.headers || {};
  if (state.token) headers["Authorization"] = "Bearer " + state.token;
  const res = await fetch(API + path, { ...opts, headers });
  if (res.status === 401 && state.me) {
    window.dispatchEvent(new CustomEvent("auth:unauthorized"));
    throw { status: 401, detail: "Session expirée" };
  }
  if (opts.raw) {
    if (!res.ok) throw await asError(res);
    return res;
  }
  let data = null;
  const text = await res.text();
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!res.ok) throw { status: res.status, detail: (data && data.detail) || res.statusText };
  return data;
}
