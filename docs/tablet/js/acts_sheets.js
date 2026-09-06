// Sheets (milestone 3): a modal overlay is UI state, not game state - see
// sheets.js. Every act here just seats ui.sheet; nothing touches `game`.
// open_sqpick (Task 6, the side-quest picker's own opener) has no case here
// because it needs an async catalog load (`await db.sideQuests()`) before it
// can seat ui.sheet - app.js handles it directly, the same way it already
// handles "pick_scenario"/"new_game", rather than through this synchronous
// dispatch table. Split out of actions.js's single dispatch() (review
// finding 6, task-4 fix round 1) - one of the per-area handlers dispatch()
// tries in order, `handle` returns null for any act it does not own.
import { closeQuestSheet } from "./acts_quest.js";

export function handle(game, ui, act, arg) {
  if (act === "open_players") { ui.sheet = { kind: "players" }; return true; }
  if (act === "open_staging") { ui.sheet = { kind: "staging" }; return true; }
  if (act === "open_menu") { ui.sheet = { kind: "menu" }; return true; }
  if (act === "open_quest") { ui.sheet = { kind: "quest" }; return true; }
  if (act === "sheet_close") {
    // The quest sheet's scrim is a plain dismiss for every other sheet, but
    // leaving THIS one by tapping outside it skipped the same resolution
    // check its own Done button runs (review finding I3) - a location/quest/
    // side-quest edit that landed exactly on its points would only offer the
    // guided flow if the player happened to tap Done instead of the scrim.
    if (ui.sheet?.kind === "quest") closeQuestSheet(game);
    ui.sheet = null;
    return true;
  }
  return null;
}
