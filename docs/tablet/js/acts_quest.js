// The quest sheet's own acts (Task 4) - folds QuestingProgressModal,
// LocationConfigModal and QuestConfigModal (docs/js/screens.js) into one
// sheet. Every stepper here is a KEYED tally (a run of taps rewrites one log
// row, same as thr/commit in acts_players.js) rather than the twin's "one
// summary line on close" pattern - see sheet_quest.js for the render side.
// Split out of actions.js's single dispatch() (review finding 6, task-4 fix
// round 1) - one of the per-area handlers dispatch() tries in order, `handle`
// returns null for any act it does not own.
import { resolve as resolveX } from "../../js/xtargets.js";
import { xIsAuto, questShowsPointsStepper, xShape } from "./xshape.js";
import { openLocPick } from "./acts_locpick.js";

// Clamp a stepped value the way every progress/points editor in the twin
// does (QuestingProgressModal._clampAdj, docs/js/screens.js): floor 0,
// ceiling `cap` unless cap is null/0, which means "no printed target" and
// falls back to a generous 0..99 rather than pinning the value at zero.
function clampAdj(cur, delta, cap = null) {
  const hi = !cap || cap <= 0 ? 99 : cap;
  return Math.max(0, Math.min(hi, cur + delta));
}

// Shared tail for "leaving the quest sheet" - used by both quest_done (the
// sheet's own Done button) and acts_sheets.js's sheet_close when the sheet
// it is dismissing is this one (review finding I3) - one function, so the
// two paths can never drift.
//
// needsResolution() alone, unconditionally - NOT QuestingProgressModal's own
// "close" case (docs/js/screens.js ~1463-1475), which runs it only when
// `g.stages.length`, and falls back to a quest-only check otherwise. That
// branch exists there because the twin's own lP+/lP- (onButton's "lP-"/"lP+"
// case, ~1398) auto-explores a done location IMMEDIATELY when there is no
// stage tree, so by close time a custom game never has location overflow
// left to defer. This client's lP+/lP- (above) never does that - every
// game, catalog or custom, defers ALL overflow (location, quest, side quest)
// to this close-time check - so needsResolution() itself, which never reads
// `stages`, is already the right - and already crash-safe - test for both.
// The actual empty-`stages` crash this milestone's review flagged (I2) was
// resolve_step.js indexing into the stage tree once resolution opens, fixed
// there; nothing here needs a stages.length branch to avoid it.
export function closeQuestSheet(game) {
  if (game.needsResolution()) game.pending_resolution = "auto";
}

export function handle(game, ui, act, arg) {
  if (act === "quest_done") {
    ui.sheet = null;
    // Left for Task 7's own sheet to consume - it opens on this flag exactly
    // the way the elimination sheet opens on pending_elim (afterTap, in
    // actions.js).
    closeQuestSheet(game);
    return true;
  }
  if (act === "quest_force") {
    // The quest row's own "Advance anyway" (QuestConfigModal's "force_adv",
    // docs/js/screens.js ~2244-2249, ~2290): only offered when the game has
    // a stage tree at all - a custom game already has its own "Advance stage"
    // button for the no-stages case, and has no guided resolution flow to
    // open here. Sets the SAME flag the twin's force_adv sets
    // (pending_resolution = "forced"); afterTap (actions.js) opens the
    // resolution sheet on it exactly like the ordinary "auto" case, and
    // resolve_step.js's `sheet.forced` is what lets the quest step fire even
    // though progress has not reached the target.
    if (!game.stages.length) return false;
    // Milestone 3 re-review, defence in depth: not reachable from the UI (the
    // button only renders inside the quest sheet), but the handler itself
    // should not act on another sheet's act name landing here by accident.
    if (ui.sheet?.kind !== "quest") return false;
    ui.sheet = null;
    game.pending_resolution = "forced";
    return true;
  }
  if (act === "qP-" || act === "qP+") {
    // A condition stage (docs/js/screens.js's "cond" row) has no printed
    // target - flipToB never gives one - so nothing here claims one either.
    if (game.quest.mode === "condition") return false;
    const before = game.quest.progress;
    const next = clampAdj(before, act === "qP+" ? 1 : -1, game.quest.points);
    if (next === before) return false;
    game.quest.progress = next;
    game.logEvent(`Quest progress ${next}`, "tally", "qp");
    return true;
  }
  if (act === "qPts-" || act === "qPts+") {
    if (!questShowsPointsStepper(game)) return false;
    const before = game.quest.points;
    const next = Math.max(0, Math.min(30, before + (act === "qPts+" ? 1 : -1)));
    if (next === before) return false;
    game.quest.points = next;
    game.logEvent(`Quest points ${next}`, "tally", "qpts");
    return true;
  }
  if (act === "lP-" || act === "lP+") {
    const i = Number(arg);
    if (i >= game.active_locations.length) return false;
    const loc = game.active_locations[i];
    const before = loc.progress;
    const next = clampAdj(before, act === "lP+" ? 1 : -1, loc.points);
    if (next === before) return false;
    loc.progress = next;
    game.logEvent(`Location ${i + 1} progress ${next}`, "tally", `lp${i}`);
    return true;
  }
  if (act === "lPts-" || act === "lPts+") {
    const i = Number(arg);
    if (i >= game.active_locations.length) return false;
    const loc = game.active_locations[i];
    const before = loc.points;
    const next = Math.max(1, Math.min(30, before + (act === "lPts+" ? 1 : -1)));
    if (next === before) return false;
    loc.points = next;
    game.logEvent(`Location ${i + 1} points ${next}`, "tally", `lpts${i}`);
    return true;
  }
  if (act === "lThr-" || act === "lThr+") {
    const i = Number(arg);
    if (i >= game.active_locations.length) return false;
    const loc = game.active_locations[i];
    if (xShape(loc) !== "plain") return false;   // lX± owns every printed-X shape instead
    const before = loc.threat ?? 0;
    const next = Math.max(0, Math.min(30, before + (act === "lThr+" ? 1 : -1)));
    if (next === before) return false;
    loc.threat = next;
    game.logEvent(`Location ${i + 1} threat ${next}`, "tally", `lthr${i}`);
    return true;
  }
  if (act === "lX-" || act === "lX+") {
    // The printed-X count stepper: the player supplies the count (how many
    // damaged characters, etc.), this recomputes the threat it resolves to -
    // LocationConfigModal's "count" branch and its _save, mirrored exactly
    // (store the count, not just the result, so it survives a board change).
    // Owns both the "count" shape (value + count are different numbers) and
    // "bare" (the count IS the value, sheet_quest.js's single stepper) -
    // xShape's own two cases for a stepper the player drives themselves.
    const i = Number(arg);
    if (i >= game.active_locations.length) return false;
    const loc = game.active_locations[i];
    const shape = xShape(loc);
    if (shape !== "count" && shape !== "bare") return false;
    const before = loc.threatCount ?? 0;
    const next = Math.max(0, Math.min(60, before + (act === "lX+" ? 1 : -1)));
    if (next === before) return false;
    loc.threatCount = next;
    loc.threat = resolveX(loc.threatX, { count: next, ...game.xContext() }) ?? 0;
    game.logEvent(`Location ${i + 1} count ${next}`, "tally", `lx${i}`);
    return true;
  }
  if (act === "lExplored") {
    // LocationConfigModal's "explored" branch, verbatim string included -
    // any seat can leave this way regardless of its own progress, unlike the
    // auto-explore exploreLocationIfDone() does elsewhere.
    const i = Number(arg);
    if (i >= game.active_locations.length) return false;
    game.active_locations.splice(i, 1);
    game.logEvent("Active location Explored");
    return true;
  }
  if (act === "lToStaging") {
    // LocationConfigModal's "tostaging" branch: the record carries the
    // card's own threat, so staging gets the right number back rather than a
    // guess, and progress is never zeroed (RR: it is not lost by returning).
    const i = Number(arg);
    if (i >= game.active_locations.length) return false;
    const [loc] = game.active_locations.splice(i, 1);
    const back = loc.threat ?? 0;
    game.staging += back;
    game.logEvent(`Active location to staging (+${back} threat, ${loc.progress ?? 0} progress kept)`);
    return true;
  }
  if (act === "lReplace") {
    // LocationConfigModal's "replaced" branch opens the picker rather than
    // logging itself - acts_locpick.js's own acts do that when a new one
    // lands (locpick_travel/locpick_save).
    const idx = Number(arg);
    openLocPick(ui, "change", idx, "quest");
    return true;
  }
  if (act === "sP-" || act === "sP+") {
    const i = Number(arg);
    if (i >= game.side_quests.length) return false;
    const sq = game.side_quests[i];
    const before = sq.progress;
    const next = clampAdj(before, act === "sP+" ? 1 : -1, sq.points);
    if (next === before) return false;
    sq.progress = next;
    game.logEvent(`Side quest ${i + 1} progress ${next}`, "tally", `sp${i}`);
    return true;
  }
  if (act === "sPts-" || act === "sPts+") {
    const i = Number(arg);
    if (i >= game.side_quests.length) return false;
    const sq = game.side_quests[i];
    const before = sq.points;
    const next = Math.max(1, Math.min(30, before + (act === "sPts+" ? 1 : -1)));
    if (next === before) return false;
    sq.points = next;
    game.logEvent(`Side quest ${i + 1} points ${next}`, "tally", `spts${i}`);
    return true;
  }
  if (act === "sRemove") {
    // SideQuestsModal's "rm" branch, verbatim string.
    const i = Number(arg);
    if (i >= game.side_quests.length) return false;
    game.side_quests.splice(i, 1);
    game.logEvent(`Side quest ${i + 1} removed`);
    return true;
  }
  return null;
}
