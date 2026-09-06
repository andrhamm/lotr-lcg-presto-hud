// Non-render home for the printed-X predicates shared by actions.js/
// acts_quest.js (the controller, which must refuse steppers it does not own)
// and sheet_quest.js (the render side, which must pick the shape to draw).
// Before this split sheet_quest.js (a render module) exported these and the
// controller imported from it - backwards layering a render module should
// never be a dependency of the code that runs before anything renders
// (review finding 7, task-4 fix round 1).
import { autoFor, AUTO_ENEMIES, AUTO_STAGING_LOCATIONS } from "../../js/xtargets.js";
import { boardTracking } from "../../js/gamestate.js";

// Whether a location's printed X is answered by a tracked value (no
// stepper) or needs the player to supply a count via lX± - mirrors
// LocationConfigModal's threatShape exactly (docs/js/screens.js): the three
// always-on auto targets (players/stage/highestThreat) are never gated, but
// AUTO_ENEMIES/AUTO_STAGING_LOCATIONS only count as "auto" when this client
// actually tracks the board (boardTracking()) - otherwise the player
// supplies the count exactly like an untracked target does.
export function xIsAuto(threatX) {
  const auto = autoFor(threatX?.target);
  if (!auto) return false;
  const trackerBacked = auto === AUTO_ENEMIES || auto === AUTO_STAGING_LOCATIONS;
  return !trackerBacked || boardTracking();
}

// QuestConfigModal (docs/js/screens.js) shows its points stepper for every
// mode except "condition" (no printed target - the card's own advance
// sentence covers that stage instead) and "formula" (X-driven; stepping the
// pre-resolution printed 0 would invite "fixing" a number the card never
// printed). Undefined mode is a manual/custom game, which has always been
// freely editable.
export function questShowsPointsStepper(game) {
  const mode = game.quest.mode;
  return mode !== "condition" && mode !== "formula";
}

// The location threat row's shape - LocationConfigModal's own threatShape
// switch (docs/js/screens.js) plus one case the twin does not need: its
// onButton keeps a stepper live even with no coded spec at all (a tap turns
// an unknown X into a real value), where the tablet's lThr± is refused
// outright for every threatKind "x" location instead (acts_quest.js) - so
// nothing here may put a stepper where that refusal lands, or the button
// just sits there dead (review finding 1, the bug this module was cut to
// fix in the first place).
//   "plain" an ordinary printed number - the usual editable stepper
//   "blank" threatKind "x" with no coded spec at all - read-only, no digits
//           (never a 0 the card did not print)
//   "auto"  a tracked value answers it - read-only, no stepper
//   "count" the player supplies a count via lX± - read-only value PLUS that
//           labelled stepper
//   "bare"  the count IS the value - one stepper, no second row (finding 3:
//           a plain value+count pair would just print the same number twice)
export function xShape(loc) {
  if (loc.threatKind !== "x") return "plain";
  const x = loc.threatX;
  if (!x) return "blank";
  if (xIsAuto(x)) return "auto";
  if ((x.mul ?? 1) === 1 && !x.add) return "bare";
  return "count";
}
