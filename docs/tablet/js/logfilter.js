// Filters over our own log strings (gamestate.js is the only author), and
// the plain-text export. Text predicates, not new logEvent categories -
// ruling R6 in the plan; test_log_filters_sort_real_log_lines drives the
// model so a reworded line fails here rather than silently leaving a filter.
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
export function logText(game) {
  return game.log.map(e => {
    const undone = typeof e.delta_i === "number" && e.delta_i > game.replay_step;
    const t = typeof e.t === "number" ? fmtMs(e.t) : "";
    return `${undone ? "~ " : ""}R${e.round}.${e.step}  ${t}  ${e.text}`;
  }).join("\n");
}
