// Every tap that changes the game goes through here, and nothing here reads
// the DOM: that is what lets tests/test_tablet.py walk a round under node
// and count the taps.
import { VIEW_ORDER } from "../../js/gamestate.js";

export const newUi = () => ({ screen: "play", alloc: null, placed: false, picker: null });

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
  if (act === "skip") { return game.skipTo(arg) !== null; }
  if (act === "endround") { game.endRound(); return true; }
  return false;
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
