// The Rules modal (Task 3): one act, open_rules, seats ui.sheet with either
// a Rules Reference section id ("6.2", from a band's own chip - primitives.js)
// or a glossary term ("term:Player Elimination", from the elimination
// sheet's own chip - sheet_elim.js). sheet_rules.js reads whichever ui.sheet
// carries; this never touches `game` at all - the sheet is pure catalog
// lookup, nothing here is state a delta needs to replay.
//
// Opening this sheet from INSIDE another sheet (the elimination sheet's own
// Rules chip is the only case today) REPLACES that sheet rather than
// stacking one on top of the other - acceptable because the flag the other
// sheet was reacting to (game.pending_elim) is untouched by this act, so
// actions.js's afterTap() re-opens it the instant this sheet's own
// sheet_close (acts_sheets.js) clears ui.sheet back to null. See
// tests/test_tablet.py's elim -> rules -> elim round trip.
//
// Split out as its own per-area handler (the pattern every acts_*.js here
// follows) rather than folded into acts_sheets.js's open_* cases - those are
// all synchronous "just seat a kind" acts too, but this one carries a second
// piece of state (which section/term) acts_sheets.js's shape has no room
// for.
export function handle(game, ui, act, arg) {
  if (act === "open_rules") {
    ui.sheet = arg.startsWith("term:")
      ? { kind: "rules", term: arg.slice("term:".length) }
      : { kind: "rules", section: arg };
    return true;
  }
  return null;
}
