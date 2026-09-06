// The resolution sheet's own acts (Task 7) - mirrors ResolutionModal.onButton
// (docs/js/screens.js) one for one, log strings included. Split out of
// actions.js's single dispatch() like every other sheet's handler (review
// finding 6, task-4 fix round 1) - `handle` returns null for any act it does
// not own.
//
// The twin recomputes `this.step` at the end of every branch; nothing here
// does, because the sheet holds no step of its own: sheet_resolve.js
// re-derives on the next render and each act below re-derives what it needs
// from the same deriveResolveStep(). One function answers both sides, so the
// button a player sees and the state the act reads can never disagree.
//
// What is NOT ported: "more_card". The canvas modal truncates card text to
// fit 480x480 and hands the cut a way into the quest-card modal; this sheet
// scrolls and prints every face in full, so there is no cut to escape.
import { deriveResolveStep } from "./resolve_step.js";

const ACTS = new Set(["res_flip", "res_location", "res_branch", "res_random",
                      "res_advance", "res_victory", "res_not_yet",
                      "res_side_done", "res_side_skip", "res_close"]);

export function handle(game, ui, act, arg) {
  if (!ACTS.has(act)) return null;
  // A res_* act with no resolution sheet open is a stale tap (a re-render
  // races a close): claim it, change nothing.
  if (ui.sheet?.kind !== "resolve") return false;
  if (act === "res_close") { ui.sheet = null; return true; }
  // Every act below mutates something the step named, so each one checks it
  // is still the step on screen rather than trusting the button.
  const st = deriveResolveStep(game, ui);
  if (act === "res_flip") {
    if (st?.kind !== "reveal") return false;
    game.flipToB();
    return true;
  }
  if (act === "res_location") {
    if (st?.kind !== "location") return false;
    // Explores every ready seat and credits the excess to the quest card
    // (rulebook p.15) - the model owns both the rule and its log line.
    game.resolveLocationOverflow();
    return true;
  }
  if (act === "res_branch") {
    if (st?.kind !== "branch") return false;
    const i = Number(arg);
    if (!(i >= 0 && i < st.cards.length)) return false;
    ui.sheet.branchPick = i;
    return true;
  }
  if (act === "res_random") {
    // "Random" is a printed property of the fork (the stage's own `branch`
    // kind), so the roll is the app's to make - Math.random, exactly like
    // the twin's randomize_branch. Tests drive res_branch instead of
    // stubbing this.
    if (st?.kind !== "branch") return false;
    ui.sheet.branchPick = Math.floor(Math.random() * st.cards.length);
    return true;
  }
  if (act === "res_advance") {
    if (st?.kind !== "advance") return false;
    game.clearAndAdvance(st.card_idx);
    // Both flags are spent: the forced entry has done its one job, and the
    // pick belonged to the fork just taken, not to the next one.
    ui.sheet.forced = false;
    ui.sheet.branchPick = null;
    return true;
  }
  if (act === "res_victory") {
    if (st?.kind !== "victory") return false;
    // The ONLY setGameOver in this sheet. app.js takes it from here: the
    // tap's own perform() sees game_over and moves to the gameover screen.
    game.setGameOver("victory");
    ui.sheet = null;
    return true;
  }
  if (act === "res_not_yet") {
    if (st?.kind !== "victory") return false;
    // Must CLOSE, not re-derive. The step recomputes to the same victory
    // while progress >= points, so leaving the sheet open put the identical
    // screen back and the tap read as a no-op - the player pressed it three
    // times in the 2026-07-30 playtest before reaching for DONE.
    game.logEvent("Victory declined - the stage is not defeated yet");
    ui.sheet = null;
    return true;
  }
  if (act === "res_side_done") {
    if (st?.kind !== "side_quest") return false;
    game.logEvent(`Side quest ${st.idx + 1} completed (resolution)`);
    game.side_quests.splice(st.idx, 1);
    return true;
  }
  if (act === "res_side_skip") {
    if (st?.kind !== "side_quest") return false;
    // By identity, not index - a later splice shifts every index after it
    // (resolve_step.js reads this list the same way).
    ui.sheet.skippedSide = (ui.sheet.skippedSide ?? []).concat([game.side_quests[st.idx]]);
    return true;
  }
  return false;
}
