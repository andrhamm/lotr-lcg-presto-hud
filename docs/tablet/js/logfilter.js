// What a log row IS - undone, rewindable, in this filter - and the plain-text
// export. Filters over our own log strings (gamestate.js is the only author):
// text predicates, not new logEvent categories - ruling R6 in the plan;
// test_log_filters_sort_real_log_lines drives the model so a reworded line
// fails here rather than silently leaving a filter.
//
// The predicates live HERE, not in screen_log.js, because three surfaces ask
// the same question - the log screen's rows, the rail's last-four block, and
// acts_log.js answering "Rewind to selected line" - and an act importing a
// predicate out of a renderer had the dependency backwards.
import { fmtMs } from "../../js/gamestate.js";
export const FILTERS = ["all", "threat", "quest", "phases", "skips"];
const RE = {
  threat: /threat|elimination/i,
  quest: /quest|progress|location|stage|explored|travel|advance/i,
  skips: /^Skipped /,
};
export function matches(filter, e) {
  if (filter === "all") return true;
  if (filter === "phases") return (e.cat ?? "move") === "phase";
  return RE[filter]?.test(e.text) ?? false;
}

// Undone: the row belongs to a redo future the cursor has stepped back past -
// still in the log, greyed, until an edit truncates it (gamestate.js's
// addDelta). Rewindable: it carries a delta index that is still in the
// window - delta_i can go NEGATIVE after the MAX_SAVED_DELTAS front-trim
// (gamestate.js "may go negative: not a target"), which is exactly the row
// whose delta the journal no longer holds.
export const isUndone = (game, e) =>
  typeof e.delta_i === "number" && e.delta_i > game.replay_step;
export const isRewindable = (game, e) =>
  typeof e.delta_i === "number" && e.delta_i >= 0 && e.delta_i < game.deltas.length;

export function logText(game) {
  return game.log.map(e => {
    const t = typeof e.t === "number" ? fmtMs(e.t) : "";
    return `${isUndone(game, e) ? "~ " : ""}R${e.round}.${e.step}  ${t}  ${e.text}`;
  }).join("\n");
}
