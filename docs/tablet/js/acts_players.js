// Players sheet edits - PlayersDetailModal's onButton (docs/js/screens.js),
// folded from its "edit"-pad steps (-5/-1/+1/+5) into one stepper row per the
// players-sheet brief. Log lines are verbatim the twin's. Split out of
// actions.js's single dispatch() (review finding 6, task-4 fix round 1) -
// one of the per-area handlers dispatch() tries in order, `handle` returns
// null for any act it does not own.
export function handle(game, ui, act, arg) {
  if (act === "thr") {
    const [i, n] = arg.split(":").map(Number);
    const p = game.players[i];
    const before = p.threat;
    game.adjustThreat(i, n);
    const after = p.threat;
    if (after !== before) game.logEvent(`P${i + 1} threat ${before} -> ${after}`);
    return after !== before;
  }
  if (act === "commit") {
    const [i, n] = arg.split(":").map(Number);
    const before = game.players[i].commit;
    const next = Math.max(0, before + n);
    if (next !== before) {
      game.setCommit(i, next);
      game.logEvent(`P${i + 1} committed ${next} willpower`);
    }
    return next !== before;
  }
  if (act === "all_thr") { game.adjustAllThreat(Number(arg)); return true; }
  return null;
}
