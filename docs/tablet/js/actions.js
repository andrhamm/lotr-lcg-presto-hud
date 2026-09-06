// Every tap that changes the game goes through here, and nothing here reads
// the DOM: that is what lets tests/test_tablet.py walk a round under node
// and count the taps.
//
// dispatch() itself is just a dispatch table now - the acts live in seven
// per-area modules (review finding 6, task-4 fix round 1: this file was 413
// lines and three more sheets were coming). Each exports `handle(game, ui,
// act, arg)` returning null when it does not own the act, a boolean
// otherwise - dispatch() tries them in order and is the only thing that
// turns "nobody claimed it" into `false`.
import { handle as playActs } from "./acts_play.js";
import { handle as sheetActs } from "./acts_sheets.js";
import { handle as locpickActs } from "./acts_locpick.js";
import { handle as questActs } from "./acts_quest.js";
import { handle as playerActs } from "./acts_players.js";
import { handle as elimActs } from "./acts_elim.js";
import { handle as sqpickActs } from "./acts_sqpick.js";
import { handle as resolveActs } from "./acts_resolve.js";
import { handle as sailingActs } from "./acts_sailing.js";
import { handle as transportActs } from "./acts_transport.js";
import { handle as logActs } from "./acts_log.js";
import { handle as rulesActs } from "./acts_rules.js";

const HANDLERS = [playActs, sheetActs, locpickActs, questActs, playerActs, elimActs,
                  sqpickActs, resolveActs, sailingActs, transportActs, logActs, rulesActs];

export const newUi = () => ({
  screen: "play", alloc: null, placed: false, picker: null,
  // Milestone 3: the one modal-overlay slot (null or {kind, ...}), plus the
  // catalog lists two sheets need lazily (locations for the location picker,
  // side quests for its picker) - loaded by app.js, read here only.
  sheet: null, locations: [], sideQuests: [],
  // Milestone 5: the parsed Rules Reference excerpts (db.rulesText()),
  // seated once at boot alongside the rest of the static catalog data -
  // null when the build has no rules_text.json (same optional-at-runtime
  // contract as tips/icons/locations).
  rules: null,
  // Milestone 4: the Game Log screen's own two pieces of state - which filter
  // is showing, and the `seq` of the selected row (null for none). Seated
  // here rather than only by open_log so every renderer can read it without
  // a guard, and re-seated by open_log so a fresh visit starts clean.
  log: { filter: "all", sel: null },
});

// Lazily seat ui.alloc the first time an alloc act runs against a resolved
// budget - the resolution pane (Task 5) does the same on its first render,
// so whichever comes first wins and the other finds it already there.
// Exported for acts_play.js (the alloc acts' own home) - a plain function
// declaration, so the circular import (acts_play.js imports this back from
// here) resolves fine: function declarations are hoisted across the whole
// module graph before any module's body runs.
export function ensureAlloc(game, ui) {
  ui.alloc ??= game.autoSplit(game.pending_budget);
  return ui.alloc;
}

// dispatch(game, ui, act, arg) -> boolean, true when the game or ui changed
// and a re-render + Session.record() are due. Unknown acts return false and
// never throw.
export function dispatch(game, ui, act, arg) {
  for (const handle of HANDLERS) {
    const result = handle(game, ui, act, arg);
    if (result !== null) return result;
  }
  return false;
}

// The elimination sheet (Task 3) and the resolution sheet (Task 7) both open
// themselves rather than being tapped open - after ANY tap changes the game,
// app.js calls this so the right one appears without every act above having
// to know about it. `!ui.sheet` means an already-open sheet (e.g. the
// players sheet mid-edit) is never yanked away by an elimination - or a
// resolution - that happens to land in the same tap.
//
// Elimination is checked FIRST, the way main.js's router orders the same
// two (its pending_elim block sits above its pending_resolution one) - a
// player leaving the game changes what the resolution flow is even about.
// An unconsumed resolution flag is left standing rather than dropped: the
// next tap that closes the sheet in the way (elim_confirm, say) runs this
// again and opens it then, exactly like the twin's router picking the flag
// up on a later tick.
export function afterTap(game, ui) {
  // R8 (Task 3, Game Log): the log screen drives its own rewind flow and
  // never wants an elimination/resolution sheet popping up over it - harmless
  // today (no act reaches this screen state yet), but the guard lands with
  // the transport rather than waiting for the screen that needs it.
  if (ui.screen === "log") return;
  if (game.pending_elim !== null && !ui.sheet) {
    ui.sheet = { kind: "elim", i: game.pending_elim, level: game.players[game.pending_elim].elimination };
  }
  if (game.pending_resolution && !ui.sheet) {
    // "forced" is the quest row's own Advance entry (the twin's
    // pending_resolution = "forced"): resolve the quest step even when
    // progress has not reached the target. "auto" - placeProgress, or the
    // quest sheet's Done - is the ordinary at-its-points case.
    ui.sheet = { kind: "resolve", forced: game.pending_resolution === "forced",
                 branchPick: null, skippedSide: [] };
    game.pending_resolution = false;
  }
}

// One tap, bracketed the way main.js brackets it: snapshot before, delta
// after. addDelta() returns false for a no-op action (nothing changed) and
// for a window that held a replay cursor move; either way the caller still
// decides whether to persist from `changed`.
//
// The defeat check runs BETWEEN dispatch and addDelta, not after both (as
// app.js used to do it) - main.js's own tick loop brackets its equivalent
// check with its own beginAction/addDelta pair (see main.js ~581-585), and
// doing it any other way here would leave the game_over transition outside
// this tap's delta, so undo() could rewind the tap but never the defeat.
export function perform(game, ui, act, arg) {
  const snap = game.beginAction();
  const changed = dispatch(game, ui, act, arg);
  if (changed && !game.game_over && game.players.length && game.allEliminated()) {
    game.setGameOver("defeat");
  }
  if (changed) game.addDelta(snap);
  return changed;
}
