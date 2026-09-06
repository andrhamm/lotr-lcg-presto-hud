// The elimination sheet (Task 3) - mirrors EliminationModal.onButton
// (docs/js/screens.js) exactly, log lines included. ui.sheet.i names the
// player throughout; elim_lvl only edits the sheet's own draft level (ui
// state, no delta) until elim_setlvl commits it to the player. Split out of
// actions.js's single dispatch() (review finding 6, task-4 fix round 1) -
// one of the per-area handlers dispatch() tries in order, `handle` returns
// null for any act it does not own.
export function handle(game, ui, act, arg) {
  if (act === "elim_confirm") {
    const { i } = ui.sheet;
    const p = game.players[i];
    game.pending_elim = null;
    game.logEvent(`P${i + 1} eliminated (threat ${p.threat} >= level ${p.elimination})`);
    ui.sheet = null;
    return true;
  }
  if (act === "elim_avert") {
    game.avertElimination(ui.sheet.i);
    ui.sheet = null;
    return true;
  }
  if (act === "elim_lvl") {
    const next = Math.max(20, Math.min(99, ui.sheet.level + Number(arg)));
    if (next === ui.sheet.level) return false;
    ui.sheet.level = next;
    return true;
  }
  if (act === "elim_setlvl") {
    const { i, level } = ui.sheet;
    const p = game.players[i];
    p.elimination = level;
    p.eliminated = p.threat >= p.elimination;
    game.logEvent(`P${i + 1} elimination level set to ${level}`);
    if (p.eliminated) game.logEvent(`P${i + 1} eliminated (threat ${p.threat} >= level ${p.elimination})`);
    game.pending_elim = null;
    ui.sheet = null;
    return true;
  }
  return null;
}
