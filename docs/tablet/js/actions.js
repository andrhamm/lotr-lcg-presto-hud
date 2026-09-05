// Every tap that changes the game goes through here, and nothing here reads
// the DOM: that is what lets tests/test_tablet.py walk a round under node
// and count the taps.
import { VIEW_ORDER } from "../../js/gamestate.js";
import { resolve as resolveX } from "../../js/xtargets.js";
import { xIsAuto, questShowsPointsStepper } from "./sheet_quest.js";

// Clamp a stepped value the way every progress/points editor in the twin
// does (QuestingProgressModal._clampAdj, docs/js/screens.js): floor 0,
// ceiling `cap` unless cap is null/0, which means "no printed target" and
// falls back to a generous 0..99 rather than pinning the value at zero.
function clampAdj(cur, delta, cap = null) {
  const hi = !cap || cap <= 0 ? 99 : cap;
  return Math.max(0, Math.min(hi, cur + delta));
}

export const newUi = () => ({
  screen: "play", alloc: null, placed: false, picker: null,
  // Milestone 3: the one modal-overlay slot (null or {kind, ...}), plus the
  // catalog lists two sheets need lazily (locations for the location picker,
  // side quests for its picker) - loaded by app.js, read here only.
  sheet: null, locations: [], sideQuests: [],
});

// Lazily seat ui.alloc the first time an alloc act runs against a resolved
// budget - the resolution pane (Task 5) does the same on its first render,
// so whichever comes first wins and the other finds it already there.
function ensureAlloc(game, ui) {
  ui.alloc ??= game.autoSplit(game.pending_budget);
  return ui.alloc;
}

// arg for alloc+/alloc-/alloc_reset targets "quest" or "side:<i>".
function allocKey(arg) {
  return arg.startsWith("side:")
    ? { key: "side", idx: Number(arg.slice("side:".length)) }
    : { key: "quest", idx: null };
}

// Shared by open_locpick and lReplace (Task 5): the location-picker sheet's
// full shape, per the task-5 brief - `manual` starts revealed when there is
// no catalog list to show at all (LocationPickModal's own ctor: `this.step
// = this.entries.length ? "list" : "manual"`), otherwise null (list first).
function openLocPick(ui, mode, idx, back) {
  ui.sheet = {
    kind: "locpick", mode, idx, back, selected: null, page: 0,
    manual: (ui.locations ?? []).length ? null : { points: 3, contrib: 2 },
  };
}

// dispatch(game, ui, act, arg) -> boolean, true when the game or ui changed
// and a re-render + Session.record() are due. Unknown acts return false and
// never throw.
export function dispatch(game, ui, act, arg) {
  if (act === "advance") {
    game.advanceView();
    ui.alloc = null;
    ui.placed = false;
    return true;
  }
  if (act === "back") {
    const moved = game.backView();
    if (moved) ui.placed = false;
    return moved;
  }
  if (act === "flip_to_b") {
    const pts = game.flipToB();
    game.logEvent(`Setup complete - round 1 begins (quest ${game.questLabel()} needs ${pts})`);
    game.enterView(VIEW_ORDER[0]);
    game._snapshotRound();
    return true;
  }
  if (act === "wp-") { const before = game.willpower; return game.setWillpower(game.willpower - 1) !== before; }
  if (act === "wp+") { const before = game.willpower; return game.setWillpower(game.willpower + 1) !== before; }
  if (act === "stg-") { const before = game.staging; return game.setStaging(game.staging - 1) !== before; }
  if (act === "stg+") { const before = game.staging; return game.setStaging(game.staging + 1) !== before; }
  if (act === "resolve") {
    game.enterView("quest_resolution");
    if (!game.quest_resolved) {
      const r = game.resolveQuest(game.willpower, game.staging);
      ui.alloc = null;
      if (r.outcome === "success") {
        game.pending_budget = r.budget;
        // Seed the allocator preview the moment a resolve succeeds - pane.js
        // (Task 5 / finding 13) only READS ui.alloc now, it never creates it,
        // so something upstream of the first render has to. ensureAlloc()
        // below stays as the alloc acts' own lazy fallback (a resumed save
        // caught between "resolve" and "apply_alloc" reaches alloc+/-/reset
        // with ui.alloc already null).
        ui.alloc = game.autoSplit(r.budget);
      }
    }
    return true;
  }
  if (act === "alloc+" || act === "alloc-") {
    // Cascade ported from screen_play.js's onButton ("ap"/"am"): this.alloc
    // -> ui.alloc, btn.id's [key, idx] -> allocKey(arg).
    const a = ensureAlloc(game, ui);
    const before = JSON.stringify(a);
    const used = a.locations.reduce((x, y) => x + y, 0) + a.quest
      + a.side_quests.reduce((x, y) => x + y, 0);
    const locRoom = game.active_locations.map(l => Math.max(0, l.points - l.progress));
    const { key, idx } = allocKey(arg);
    const qCur = key === "side" ? game.side_quests[idx].progress : game.quest.progress;
    const qPts = key === "side" ? game.side_quests[idx].points : game.quest.points;
    const qRoom = Math.max(0, qPts - qCur);
    const nowQ = key === "side" ? a.side_quests[idx] : a.quest;
    const bumpQ = d => key === "side" ? (a.side_quests[idx] += d) : (a.quest += d);
    if (act === "alloc+") {                 // + : active locations fill first
      if (used < game.pending_budget) {     // budget spent -> no mutation at all
        let filled = false;
        for (let i = 0; i < locRoom.length; i++) {
          if (a.locations[i] < locRoom[i]) { a.locations[i] += 1; filled = true; break; }
        }
        if (!filled && nowQ < qRoom) bumpQ(1);   // locations full -> the quest itself
      }
    } else if (nowQ > 0) {
      // - : pull back the quest first, then unwind the location fill - last
      // seat first, the reverse of the order '+' filled them in.
      bumpQ(-1);
    } else {
      const overflow = a.quest + a.side_quests.reduce((x, y) => x + y, 0);
      if (overflow === 0) {
        for (let i = a.locations.length - 1; i >= 0; i--) {
          if (a.locations[i] > 0) { a.locations[i] -= 1; break; }
        }
      }
    }
    // Every branch above can fall through without touching `a` (budget
    // spent, nothing placed yet, or overflow blocking the location pull-
    // back) - compare the snapshot rather than trusting which branch ran,
    // so a no-op tap reports false and skips the delta/re-render.
    return JSON.stringify(a) !== before;
  }
  if (act === "alloc_reset") {
    const a = ensureAlloc(game, ui);
    const before = JSON.stringify(a);
    a.locations = a.locations.map(() => 0);
    a.quest = 0;
    a.side_quests = a.side_quests.map(() => 0);
    return JSON.stringify(a) !== before;
  }
  if (act === "apply_alloc") {
    const a = ensureAlloc(game, ui);
    const used = a.locations.reduce((x, y) => x + y, 0) + a.quest
      + a.side_quests.reduce((x, y) => x + y, 0);
    const discard = game.pending_budget - used;
    const completed = game.placeProgress(a);
    let msg = `Placed ${used} progress`;
    if (discard > 0) msg += `, discarded ${discard} (over capacity)`;
    if (completed.length) msg += ` (${completed.join(", ")})`;
    game.logEvent(msg);
    game.pending_budget = 0;
    ui.alloc = null;
    ui.placed = true;
    // Under bands the resolution view is its own window - unlike the twin,
    // do NOT enter aw_quest_resolution here. Next hands off to travel, and
    // game.pending_resolution (a catalog concern) is left as the model set
    // it for milestone 3's sheet to consume.
    return true;
  }
  if (act === "eng-" || act === "eng+") {
    const i = Number(arg);
    const d = act === "eng-" ? -1 : 1;
    const before = game.players[i].engaged;
    return game.setEngaged(i, game.players[i].engaged + d) !== before;
  }
  if (act === "stgen-") { const before = game.staging_enemies; return game.setStagingEnemies(game.staging_enemies - 1) !== before; }
  if (act === "stgen+") { const before = game.staging_enemies; return game.setStagingEnemies(game.staging_enemies + 1) !== before; }
  if (act === "stgloc-") { const before = game.staging_locations; return game.setStagingLocations(game.staging_locations - 1) !== before; }
  if (act === "stgloc+") { const before = game.staging_locations; return game.setStagingLocations(game.staging_locations + 1) !== before; }
  if (act === "stg5") {
    // The staging editor's ±5 step - stg+/stg- above already cover ±1.
    const before = game.staging;
    return game.setStaging(game.staging + Number(arg)) !== before;
  }
  if (act === "skip") { return game.skipTo(arg) !== null; }
  if (act === "endround") { game.endRound(); return true; }

  // Sheets (milestone 3): a modal overlay is UI state, not game state - see
  // sheets.js. open_sqpick is Task 6's own act (its chip already renders in
  // sheet_quest.js, per the task-4 brief - it opens nothing until that
  // lands, so it deliberately has no case here yet).
  if (act === "open_players") { ui.sheet = { kind: "players" }; return true; }
  if (act === "open_staging") { ui.sheet = { kind: "staging" }; return true; }
  if (act === "open_menu") { ui.sheet = { kind: "menu" }; return true; }
  if (act === "open_quest") { ui.sheet = { kind: "quest" }; return true; }
  if (act === "sheet_close") { ui.sheet = null; return true; }

  // The location picker (Task 5). Every caller dispatches this same act -
  // the quest sheet's "+ Add location" chip (sheet_quest.js, no arg at all)
  // and the Travel pane's own CTA (pane.js) - distinguished only by `arg`,
  // "<mode>:<idx>:<back>" (idx/back default the same way an empty `commit`/
  // `thr` field would: absent means "the common case", here mode "new",
  // idx 0, back "quest" - exactly what the already-landed quest-sheet chip
  // needs since it renders with no arg at all).
  if (act === "open_locpick") {
    const [modeArg, idxArg, backArg] = (arg || "").split(":");
    openLocPick(ui, modeArg || "new", idxArg ? Number(idxArg) : 0, backArg || "quest");
    return true;
  }

  // The quest sheet (Task 4) - folds QuestingProgressModal, LocationConfig-
  // Modal and QuestConfigModal (docs/js/screens.js) into one sheet. Every
  // stepper here is a KEYED tally (a run of taps rewrites one log row, same
  // as thr/commit above) rather than the twin's "one summary line on close"
  // pattern - see sheet_quest.js for the render side and the controller
  // notes this was briefed from for the exact log/key strings.
  if (act === "quest_done") {
    ui.sheet = null;
    // Left for Task 7's own sheet to consume - it opens on this flag exactly
    // the way the elimination sheet opens on pending_elim (afterTap, below).
    if (game.needsResolution()) game.pending_resolution = "auto";
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
    if (loc.threatKind === "x") return false;   // lX± owns this location's threat instead
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
    const i = Number(arg);
    if (i >= game.active_locations.length) return false;
    const loc = game.active_locations[i];
    if (loc.threatKind !== "x" || !loc.threatX || xIsAuto(loc.threatX)) return false;
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
    // logging itself - the location picker (Task 5) does that when a new
    // one lands, via locpick_travel/locpick_save below.
    const idx = Number(arg);
    openLocPick(ui, "change", idx, "quest");
    return true;
  }

  // The location picker's own acts (Task 5) - mirrors LocationPickModal's
  // onButton/_commit (docs/js/screens.js) with no "how it arrived" toggle:
  // arrival is read off `ui.sheet.back` instead (see the module comment in
  // sheet_locpick.js). `back === "play"` means the players are paying the
  // travel cost (the Travel pane's own CTA); anything else (the quest
  // sheet's "+ Add location") is a card effect. changeLocation() never reads
  // arrival at all (its log line is the same either way), so this uniform
  // rule is exactly as safe for mode "change" as it is for "new".
  if (act === "locpick_row") {
    if (ui.sheet?.kind !== "locpick") return false;
    ui.sheet.selected = arg;
    return true;
  }
  if (act === "locpick_manual") {
    if (ui.sheet?.kind !== "locpick" || ui.sheet.manual) return false;
    ui.sheet.manual = { points: 3, contrib: 2 };
    return true;
  }
  if (act === "locpick_pts" || act === "locpick_contrib") {
    const m = ui.sheet?.kind === "locpick" ? ui.sheet.manual : null;
    if (!m) return false;
    const key = act === "locpick_pts" ? "points" : "contrib";
    const hi = act === "locpick_pts" ? 30 : 9;
    const lo = act === "locpick_pts" ? 1 : 0;
    const next = Math.max(lo, Math.min(hi, m[key] + Number(arg)));
    if (next === m[key]) return false;
    m[key] = next;
    return true;
  }
  if (act === "locpick_travel") {
    const sheet = ui.sheet;
    if (sheet?.kind !== "locpick" || sheet.selected === null) return false;
    const e = (ui.locations ?? []).find(x => x.id === sheet.selected);
    if (!e) return false;
    const arrival = sheet.back === "play" ? "travel" : "effect";
    const entry = { ...e, arrival };
    if (sheet.mode === "new") game.travelTo(e.points ?? 0, e.threat ?? 0, e.name, entry);
    else game.changeLocation(e.points ?? 0, e.threat ?? 0, e.name, sheet.idx, entry);
    ui.sheet = sheet.back === "quest" ? { kind: "quest" } : null;
    return true;
  }
  if (act === "locpick_save") {
    const sheet = ui.sheet;
    if (sheet?.kind !== "locpick" || !sheet.manual) return false;
    const { points, contrib } = sheet.manual;
    const arrival = sheet.back === "play" ? "travel" : "effect";
    const entry = { arrival };
    // A manual entry has no catalog row to carry a threat, but the
    // contribution stepper's own caption says the same thing: "its threat
    // leaves the staging area while it is active" - so that number IS the
    // location's threat once it is seated (LocationPickModal._commit's own
    // rule, verbatim: without this, travelling took N out of staging and
    // "Back to staging" put 0 back).
    if (contrib) entry.threat = contrib;
    if (sheet.mode === "new") game.travelTo(points, contrib, null, entry);
    else game.changeLocation(points, contrib, null, sheet.idx, entry);
    ui.sheet = sheet.back === "quest" ? { kind: "quest" } : null;
    return true;
  }
  if (act === "locpick_cancel") {
    const sheet = ui.sheet;
    if (sheet?.kind !== "locpick") return false;
    ui.sheet = sheet.back === "quest" ? { kind: "quest" } : null;
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

  // Players sheet edits - PlayersDetailModal's onButton (docs/js/screens.js),
  // folded from its "edit"-pad steps (-5/-1/+1/+5) into one stepper row per
  // the players-sheet brief. Log lines are verbatim the twin's.
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

  // The elimination sheet (Task 3) - mirrors EliminationModal.onButton
  // (docs/js/screens.js) exactly, log lines included. ui.sheet.i names the
  // player throughout; elim_lvl only edits the sheet's own draft level
  // (ui state, no delta) until elim_setlvl commits it to the player.
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
    ui.sheet.level = Math.max(20, Math.min(99, ui.sheet.level + Number(arg)));
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

  return false;
}

// The elimination sheet (Task 3) and the resolution sheet (Task 7) both open
// themselves rather than being tapped open - after ANY tap changes the game,
// app.js calls this so the right one appears without every act above having
// to know about it. `!ui.sheet` means an already-open sheet (e.g. the
// players sheet mid-edit) is never yanked away by an elimination that
// happens to land in the same tap.
export function afterTap(game, ui) {
  if (game.pending_elim !== null && !ui.sheet) {
    ui.sheet = { kind: "elim", i: game.pending_elim, level: game.players[game.pending_elim].elimination };
  }
}

// One tap, bracketed the way main.js brackets it: snapshot before, delta
// after. addDelta() returns false for a no-op action (nothing changed) and
// for a window that held a replay cursor move; either way the caller still
// decides whether to persist from `changed`.
//
// The defeat check runs BETWEEN dispatch and addDelta, not after both (as
// app.js used to do it) - main.js's own tick loop brackets its equivalent
// check with its own beginAction/addDelta pair (see main.js ~581-585), and
// doing it any other way here would leave the game_over transition outside
// this tap's delta, so undo() could rewind the tap but never the defeat.
export function perform(game, ui, act, arg) {
  const snap = game.beginAction();
  const changed = dispatch(game, ui, act, arg);
  if (changed && !game.game_over && game.players.length && game.allEliminated()) {
    game.setGameOver("defeat");
  }
  if (changed) game.addDelta(snap);
  return changed;
}
