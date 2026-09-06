// The new-game picker's ui-only acts (Task 2, milestone 6): the source
// toggle, the cycle list and the player-count/threat steppers. Split out the
// same way every other screen's acts are (actions.js's dispatch() tries each
// per-area handler in order, `handle` returning null for any act it does not
// own) - these never touch the network or create a game, which is what
// keeps pick_scenario/begin_setup in app.js instead of here.
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
    // Back to the top of the drill-in, and no selection: the catalogs are
    // disjoint, so a quest picked from the other source is not in this list
    // at all - leaving it selected would show its detail beside a list that
    // does not contain it.
    ui.picker.drill = "cycles";
    ui.picker.slug = null;
    return true;
  }
  // The left column is a drill-in (M7): a cycle row does not just select a
  // cycle, it ENTERS it - the list becomes that cycle's quests. Re-tapping
  // the cycle you are already in is still a state change, because the list
  // you are looking at is the cycle list.
  if (act === "ng_cycle") {
    ui.picker.cycle = arg;
    ui.picker.drill = "scenarios";
    return true;
  }
  if (act === "ng_cycles") {
    if (ui.picker.drill !== "scenarios") return false;
    ui.picker.drill = "cycles";
    // Everything downstream of the cycle goes with it. Leaving the slug behind
    // left the previous scenario loaded under a list that no longer contained
    // it: its stages still in the rail, its detail still in the pane, its name
    // still in the app bar, and Continue still armed - a state you could start
    // a game from without a visible selection anywhere.
    ui.picker.slug = null;
    ui.picker.stage = "overview";
    return true;
  }
  // The left column's third list: which stage the detail pane is drawing, or
  // "overview" for the whole quest. ui-only, and cheap - the bundle is
  // already pinned, so switching stages reads nothing.
  if (act === "ng_stage") {
    if (ui.picker.stage === arg) return false;
    ui.picker.stage = arg;
    return true;
  }
  // The two ways between the setup steps. Both are ui-only: `begin_setup` is
  // the one act that creates a game, and it stays in app.js (it rebinds
  // `game`, which clears the tagged write queue with it).
  if (act === "go_players") {
    if (!ui.picker.slug) return false;
    ui.screen = "players";
    return true;
  }
  if (act === "go_scenario") {
    ui.screen = "newgame";
    return true;
  }
  if (act === "go_home") {
    ui.screen = "home";
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
  // ov_back moved to acts_overview.js with Task 3 - that module now owns
  // every act the Scenario overview raises, this one owns the picker's.
  return null;
}
