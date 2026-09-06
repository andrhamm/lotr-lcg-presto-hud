// The sailing test sheet (Task 8) - mirrors SailingModal.onButton
// (docs/js/screens.js) exactly, log lines included. `d` nudges the sheet's
// own draft wheel count `v` (ui state, no delta, same as the quest sheet's
// live steppers) clamped to -3..8 - the twin's own onButton clamp, NOT the
// 0..3 heading-index clamp sheet_sailing.js's RESULT preview uses. `apply`
// commits `-v` to game.heading via shiftHeading() (a positive v is wheels
// found - shift ON-course, so the delta the model applies is the negative
// of the draft) with the twin's own why strings verbatim; a draft of 0
// closes with no shift and no log line, matching the twin's "if (v !== 0)"
// guard. `cancel` (and the sheet's own scrim tap, routed through the shared
// sheet_close act in acts_sheets.js) discards the draft the same way.
// Split out (review finding 6 pattern, task-4 fix round 1) as its own
// per-area handler dispatch() tries in order - `handle` returns null for
// any act it does not own.
export function handle(game, ui, act, arg) {
  if (act === "open_sailing") {
    ui.sheet = { kind: "sailing", v: 0 };
    return true;
  }
  if (act === "sail_d") {
    if (ui.sheet?.kind !== "sailing") return false;
    ui.sheet.v = Math.max(-3, Math.min(8, ui.sheet.v + Number(arg)));
    return true;
  }
  if (act === "sail_apply") {
    if (ui.sheet?.kind !== "sailing") return false;
    const { v } = ui.sheet;
    if (v !== 0) {
      const why = v > 0
        ? `${v} wheel${v > 1 ? "s" : ""} found (sailing test)`
        : "card effect";
      game.shiftHeading(-v, why);
    }
    ui.sheet = null;
    return true;
  }
  if (act === "sail_cancel") {
    if (ui.sheet?.kind !== "sailing") return false;
    ui.sheet = null;
    return true;
  }
  return null;
}
