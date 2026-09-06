// Sheets (milestone 3): a modal overlay is UI state, not game state - see
// sheets.js. Every act here just seats ui.sheet; nothing touches `game`.
// open_sqpick (Task 6, the side-quest picker's own opener) has no case here
// because it needs an async catalog load (`await db.sideQuests()`) before it
// can seat ui.sheet - app.js handles it directly, the same way it already
// handles "pick_scenario"/"new_game", rather than through this synchronous
// dispatch table. Split out of actions.js's single dispatch() (review
// finding 6, task-4 fix round 1) - one of the per-area handlers dispatch()
// tries in order, `handle` returns null for any act it does not own.
export function handle(game, ui, act, arg) {
  if (act === "open_players") { ui.sheet = { kind: "players" }; return true; }
  if (act === "open_staging") { ui.sheet = { kind: "staging" }; return true; }
  if (act === "open_menu") { ui.sheet = { kind: "menu" }; return true; }
  if (act === "open_quest") { ui.sheet = { kind: "quest" }; return true; }
  if (act === "sheet_close") { ui.sheet = null; return true; }
  return null;
}
