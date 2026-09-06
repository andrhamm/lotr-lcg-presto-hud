// Every tap that changes the game goes through here, and nothing here reads
// the DOM: that is what lets tests/test_tablet.py walk a round under node
// and count the taps.
//
// dispatch() itself is just a dispatch table now - the acts live in six
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

const HANDLERS = [playActs, sheetActs, locpickActs, questActs, playerActs, elimActs];

export const newUi = () => ({
  screen: "play", alloc: null, placed: false, picker: null,
  // Milestone 3: the one modal-overlay slot (null or {kind, ...}), plus the
  // catalog lists two sheets need lazily (locations for the location picker,
  // side quests for its picker) - loaded by app.js, read here only.
  sheet: null, locations: [], sideQuests: [],
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
// players sheet mid-edit) is never yanked away by an elimination that
// happens to land in the same tap.
export function afterTap(game, ui) {
  if (game.pending_elim !== null && !ui.sheet) {
    ui.sheet = { kind: "elim", i: game.pending_elim, level: game.players[game.pending_elim].elimination };
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
