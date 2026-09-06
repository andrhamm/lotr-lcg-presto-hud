// The new-game picker's ui-only acts (Task 2, milestone 6): the source
// toggle, the cycle list, the player-count/threat steppers, and the
// Scenario overview's own Back button. Split out the same way every other
// screen's acts are (actions.js's dispatch() tries each per-area handler in
// order, `handle` returning null for any act it does not own) - these never
// touch the network or create a game, which is what keeps pick_scenario/
// begin_setup in app.js instead of here.
//
// ng_players/ng_threat± are moved verbatim from app.js's old hand-rolled
// `if` chain (task-2 brief) - app.js only ever wanted the async acts
// (pick_scenario, begin_setup) left inline; these never awaited anything.
import { cyclesFor } from "../../js/quest_catalog.js";

export function handle(game, ui, act, arg) {
  if (act === "ng_source") {
    const source = arg;
    if (ui.picker.source === source) return false;
    ui.picker.source = source;
    // Switching source resets the cycle selection to that source's own
    // first cycle - the Official/Community catalogs are disjoint (they
    // never share a cycle name), so the previous cycle would otherwise
    // point at a group the new source doesn't have.
    ui.picker.cycle = cyclesFor(ui.picker.index ?? {}, source)[0]?.cycle ?? null;
    return true;
  }
  if (act === "ng_cycle") {
    if (ui.picker.cycle === arg) return false;
    ui.picker.cycle = arg;
    return true;
  }
  if (act === "ng_players") {
    const n = Number(arg);
    if (n === ui.picker.players) return false;
    const threats = ui.picker.threats;
    ui.picker.players = n;
    ui.picker.threats = Array.from({ length: n }, (_, i) => threats[i] ?? 25);
    return true;
  }
  if (act === "ng_threat-" || act === "ng_threat+") {
    const i = Number(arg);
    const d = act === "ng_threat-" ? -1 : 1;
    const before = ui.picker.threats[i] ?? 25;
    const after = Math.max(0, before + d);
    ui.picker.threats[i] = after;
    return after !== before;
  }
  // The Scenario overview's Back button (Task 3 may move this into
  // acts_overview.js once that module exists - for now it lives here since
  // layout.js's placeholder is this task's own responsibility). Keeps the
  // picker's own state (source/cycle/players/threats) exactly as the player
  // left it - only pick_scenario mutates ui.overview, and a fresh pick
  // overwrites it wholesale, so there is nothing to clean up here.
  if (act === "ov_back") {
    ui.screen = "newgame";
    return true;
  }
  return null;
}
