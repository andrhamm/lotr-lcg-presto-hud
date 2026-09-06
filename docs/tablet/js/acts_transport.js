// The replay cursor's three doors on the play screen: the strip's transport,
// its tick taps, and (Task 3) the Game Log's "Rewind to selected line" -
// every one of them is GameState.stepThrough() under a different arg. A
// cursor move is not an action: addDelta() sees _replay_moved and records
// nothing, but dispatch still returns true so app.js re-renders and
// Session.record() journals the {op:"s"} cursor write (Divergence D3).
export function handle(game, ui, act, arg) {
  let moved;
  if (act === "rw_first") moved = game.stepThrough({ size: "index", index: -1 });
  else if (act === "rw_last") moved = game.stepThrough({ size: "index", index: game.deltas.length - 1 });
  else if (act === "rw_undo") moved = game.stepThrough({ size: "single", direction: "undo" });
  else if (act === "rw_redo") moved = game.stepThrough({ size: "single", direction: "redo" });
  else if (act === "rw_round_back") moved = game.stepThrough({ size: "round", direction: "undo" });
  else if (act === "rw_round_fwd") moved = game.stepThrough({ size: "round", direction: "redo" });
  else if (act === "rw_index") {
    const i = Number.parseInt(arg, 10);
    moved = Number.isInteger(i) && i >= -1 && i < game.deltas.length
      && game.stepThrough({ size: "index", index: i });
  } else if (act === "rw_tick") {
    const i = game.deltaIndexForView(game.round, arg);
    moved = i >= 0 && game.stepThrough({ size: "index", index: i });
  } else return null;
  if (moved) {
    // Whatever the allocator/sheet was showing described a state that is
    // no longer the live one.
    ui.alloc = null; ui.placed = false;
    if (ui.screen !== "log") ui.sheet = null;
  }
  return !!moved;
}
