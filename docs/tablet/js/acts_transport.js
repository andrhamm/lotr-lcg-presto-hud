// The replay cursor's three doors: the strip's transport, its tick taps, and
// (Task 3) the Game Log's "Rewind to selected line" - every one of them is
// GameState.stepThrough() under a different arg. A cursor move is not an
// action: addDelta() sees _replay_moved and records nothing, but dispatch
// still returns true so app.js re-renders and Session.record() journals the
// {op:"s"} cursor write (Divergence D3).

// Whatever the allocator/sheet was showing described a state that is no
// longer the live one. The log screen's own sheet (the export overlay) is
// left standing - the cursor moved under it, which is exactly what its
// transport is for.
function cursorMoved(ui) {
  ui.alloc = null;
  ui.placed = false;
  if (ui.screen !== "log") ui.sheet = null;
}

// A cursor move to a KNOWN index: rw_index, the strip's tick taps, and
// acts_log.js's log_rewind all land here, so the bounds check and the ui
// reset are written once rather than once per caller (task-3 ruling).
// index -1 is the valid "before the first delta" position, not a miss.
export function rewindToIndex(game, ui, i) {
  const moved = Number.isInteger(i) && i >= -1 && i < game.deltas.length
    && game.stepThrough({ size: "index", index: i });
  if (moved) cursorMoved(ui);
  return !!moved;
}

export function handle(game, ui, act, arg) {
  if (act === "rw_index") return rewindToIndex(game, ui, Number.parseInt(arg, 10));
  if (act === "rw_tick") {
    // deltaIndexForView returns -1 for "no delta entered that view this
    // round", which is a MISS here, not a jump to the start of history -
    // so it is filtered before rewindToIndex, which treats -1 as a target.
    const i = game.deltaIndexForView(game.round, arg);
    return i >= 0 && rewindToIndex(game, ui, i);
  }
  let moved;
  if (act === "rw_first") moved = game.stepThrough({ size: "index", index: -1 });
  else if (act === "rw_last") moved = game.stepThrough({ size: "index", index: game.deltas.length - 1 });
  else if (act === "rw_undo") moved = game.stepThrough({ size: "single", direction: "undo" });
  else if (act === "rw_redo") moved = game.stepThrough({ size: "single", direction: "redo" });
  else if (act === "rw_round_back") moved = game.stepThrough({ size: "round", direction: "undo" });
  else if (act === "rw_round_fwd") moved = game.stepThrough({ size: "round", direction: "redo" });
  else return null;
  if (moved) cursorMoved(ui);
  return !!moved;
}
