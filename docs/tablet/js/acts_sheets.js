// Sheets (milestone 3): a modal overlay is UI state, not game state - see
// sheets.js. Every act here just seats ui.sheet; nothing touches `game`.
// open_sqpick is Task 6's own act (its chip already renders in
// sheet_quest.js - it opens nothing until that lands, so it deliberately has
// no case here, or in any other handler, yet). Split out of actions.js's
// single dispatch() (review finding 6, task-4 fix round 1) - one of the
// per-area handlers dispatch() tries in order, `handle` returns null for any
// act it does not own.
export function handle(game, ui, act, arg) {
  if (act === "open_players") { ui.sheet = { kind: "players" }; return true; }
  if (act === "open_staging") { ui.sheet = { kind: "staging" }; return true; }
  if (act === "open_menu") { ui.sheet = { kind: "menu" }; return true; }
  if (act === "open_quest") { ui.sheet = { kind: "quest" }; return true; }
  if (act === "sheet_close") { ui.sheet = null; return true; }
  return null;
}
