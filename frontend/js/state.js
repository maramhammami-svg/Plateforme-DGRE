export const TOKEN_KEY = "dgre_token";
export const THEME_KEY = "dgre_theme";

export const state = {
  token: localStorage.getItem(TOKEN_KEY) || null,
  me: null,
  stationCache: [],
  governorateCache: null,
  autoTimer: null,
  fluxTimer: null,
  lastTopEventId: 0,
};
