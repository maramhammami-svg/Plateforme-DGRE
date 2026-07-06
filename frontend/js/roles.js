import { state } from "./state.js";

export const RW = ["agent", "responsable", "administrateur"];
export const RV = ["responsable", "administrateur"];
export const REV = ["directeur", "administrateur"];

export function can(list) { return state.me && list.includes(state.me.role); }
