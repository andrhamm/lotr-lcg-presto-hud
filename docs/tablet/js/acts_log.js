// The Game Log screen's own acts (milestone 4, Task 3). Five of the six are
// ui-only - they change what renders, nothing about the game - and return
// true so app.js re-renders. The sixth, log_rewind, moves the replay cursor,
// and it does that through acts_transport.js's rewindToIndex(): one code path
// for every cursor move, so the ui reset that has to follow one can never be
// forgotten here.
import { afterTap } from "./actions.js";
import { rewindToIndex } from "./acts_transport.js";
import { FILTERS } from "./logfilter.js";
import { isRewindable } from "./screen_log.js";

export function handle(game, ui, act, arg) {
  if (act === "open_log") {
    // A fresh visit starts unfiltered with nothing selected: the filter and
    // the selection are about the trip, not the game.
    ui.screen = "log";
    ui.log = { filter: "all", sel: null };
    return true;
  }
  if (act === "log_close") {
    // afterTap declines to open anything while ui.screen === "log" (R8), so
    // an elimination or resolution that fell due during a rewind has been
    // waiting on its flag. Leaving the screen is when it gets its prompt -
    // hence the screen change FIRST, then afterTap. Imported from actions.js
    // the same way acts_play.js imports ensureAlloc: function declarations
    // hoist across the module graph, so the cycle resolves.
    ui.screen = "play";
    afterTap(game, ui);
    return true;
  }
  if (act === "log_filter") {
    if (!FILTERS.includes(arg) || ui.log.filter === arg) return false;
    // The selection is dropped with the filter: a row selected under "All"
    // may not be on screen under "Phases", and a live Rewind button naming a
    // line the player can no longer see is worse than re-picking it.
    ui.log.filter = arg;
    ui.log.sel = null;
    return true;
  }
  if (act === "log_sel") {
    const seq = Number.parseInt(arg, 10);
    if (!Number.isInteger(seq)) return false;
    ui.log.sel = ui.log.sel === seq ? null : seq;   // tapping the row again clears it
    return true;
  }
  if (act === "log_rewind") {
    const e = ui.log.sel === null ? null : game.log.find(r => r.seq === ui.log.sel);
    // No selection, a selection that vanished (a truncation dropped the row),
    // or a row whose delta the journal no longer holds: nothing to move to.
    if (!e || !isRewindable(game, e)) return false;
    return rewindToIndex(game, ui, e.delta_i);
  }
  if (act === "export_log") {
    ui.sheet = { kind: "export" };
    return true;
  }
  return null;
}
