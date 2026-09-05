// Every tap that changes the game goes through here, and nothing here reads
// the DOM: that is what lets tests/test_tablet.py walk a round under node
// and count the taps.
import { VIEW_ORDER } from "../../js/gamestate.js";

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
  // sheets.js. open_quest is Task 4's own act (its chip already renders in
  // the rail, per the task-2 brief - it opens nothing until sheet_quest.js
  // lands, so it deliberately has no case here yet).
  if (act === "open_players") { ui.sheet = { kind: "players" }; return true; }
  if (act === "open_staging") { ui.sheet = { kind: "staging" }; return true; }
  if (act === "open_menu") { ui.sheet = { kind: "menu" }; return true; }
  if (act === "sheet_close") { ui.sheet = null; return true; }

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
