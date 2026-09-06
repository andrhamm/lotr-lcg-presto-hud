// The Notes sheet's own open act (Task 4, milestone 5) - split out as its
// own per-area handler, the pattern every acts_*.js here follows (see
// acts_rules.js's identical shape/comment for why: dispatch() just tries
// each module in order). Carries no extra state on ui.sheet beyond its
// kind: unlike the Rules sheet's section/term choice, the Notes sheet
// always shows every group for the CURRENT scenario (ui.scenarioSlug, seated
// by app.js), so there is nothing else to stash here.
export function handle(game, ui, act, arg) {
  if (act === "open_notes") {
    ui.sheet = { kind: "notes" };
    return true;
  }
  return null;
}
