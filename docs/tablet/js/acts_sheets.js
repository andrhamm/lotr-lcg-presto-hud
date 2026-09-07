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
  // The quick view's flip. It wraps rather than clamping, so a two-sided card
  // is one repeated tap to compare its faces - which is how you read a quest
  // card at the table.
  if (act === "card_flip") {
    if (ui.sheet?.kind !== "card") return false;
    const n = (ui.sheet.cards?.[ui.sheet.at ?? 0]?.files ?? []).length;
    if (n < 2) return false;
    ui.sheet.face = ((ui.sheet.face ?? 0) + 1) % n;
    return true;
  }
  // Paging through the screen's other cards, in the order the screen shows
  // them. It WRAPS, like the flip does: at the end of an encounter set the
  // next card is the first one, which is how you leaf through a stack. The
  // face resets, because "which side am I on" belongs to the card you were
  // looking at, not to the next one.
  if (act === "card_prev" || act === "card_next") {
    if (ui.sheet?.kind !== "card") return false;
    const n = (ui.sheet.cards ?? []).length;
    if (n < 2) return false;
    const d = act === "card_next" ? 1 : -1;
    ui.sheet.at = ((ui.sheet.at ?? 0) + d + n) % n;
    ui.sheet.face = 0;
    return true;
  }
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
