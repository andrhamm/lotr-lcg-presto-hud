// The tablet's ONLY DOM-touching file (tests/test_no_stray_io.py's
// localStorage guard covers every other file under docs/tablet/, and this
// one is never imported under node - see tests/test_tablet.py's `node()`
// harness). Everything it calls - layout.js and everything under it - is a
// pure string builder, which is what lets the rest of the client be driven
// and tested outside a browser at all.
//
// Boot, the click-to-dispatch loop, and background persistence. Mirrors
// docs/js/main.js's main() for the pieces this milestone needs: resume vs.
// new game, one perform() call per tap (actions.js's dispatch(), bracketed
// with beginAction()/addDelta() the way main.js's beginAction/commitAction
// bracket onButton), and Session's queue-then-drain persistence - not the
// canvas draw loop or the modal router, neither of which exist here (the
// rail is read-only this milestone; see rail.js).
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS, setBoardTracking } from "../../js/gamestate.js";
import { DataClient } from "../../js/db.js";
import { CATALOG_UNAVAILABLE } from "../../js/viewcopy.js";
import { layout } from "./layout.js";
import { perform, newUi, afterTap } from "./actions.js";

// A finished game is appended to history once. Reset wherever `game` is
// rebound (new game / a fresh scenario pick) - mirrors main.js's own
// `recordedGameOver` (main.js ~127, ~338, ~433).
let recordedGameOver = false;

setWindowPolicy(WINDOW_POLICY_BANDS);
setBoardTracking(true);

// Own prefix: the web twin (docs/js/db.js's default "lotr-hud-") and this
// client never share a save, a log, or prefs - see tests/test_no_stray_io.py.
const db = new DataClient({ prefix: "lotr-tablet-" });

const root = document.getElementById("app");
const clock = () => Math.floor(performance.now());

let game = new GameState();
game.clock = clock;
const ui = newUi();

function render() {
  root.innerHTML = layout(game, ui);
}

// db.index() PROPAGATES on failure (a docs/data/ build that was never run) -
// db.js's own contract, deliberately, per its "PROPAGATES on failure"
// comment. Caught here so a missing catalog lands the player on a working
// picker with the CATALOG_UNAVAILABLE line instead of a blank page.
async function buildPicker() {
  let index = null;
  try { index = await db.index(); }
  catch (e) { console.error("tablet: quest catalog unavailable", e); }
  return { index, players: 2, threats: [25, 25], hasSave: false,
           error: index ? null : CATALOG_UNAVAILABLE };
}

async function boot() {
  const saved = db.session.loadState();
  if (saved) {
    game = GameState.fromDict(saved.state);
    game.clock = clock;
    db.session.loadReplay(game);
    db.session.loadLog(game);
    const b = game.scenario?.slug ? await db.bundle(game.scenario.slug) : null;
    if (b) game.rehydrateStages(b.stages);
    // A save can land exactly between a successful "resolve" and
    // "apply_alloc" (pending_budget > 0, nothing placed yet). ui.alloc is
    // never part of the save (it is UI state, not game state), and pane.js
    // no longer seeds it lazily on render (finding 13) - so without this,
    // resuming into that window would skip straight to the outcome pane and
    // strand the pending progress. Reseed it the same way "resolve" does.
    if (game.pending_budget > 0) ui.alloc = game.autoSplit(game.pending_budget);
    ui.screen = game.game_over ? "gameover" : "play";
    if (game.game_over) recordedGameOver = true;
  } else {
    ui.screen = "newgame";
    ui.picker = await buildPicker();
  }
  render();
}

async function handleAct(act, arg) {
  // "new_game_confirm" is the Menu sheet's confirmed choice (sheet_menu.js) -
  // handled exactly like the game-over screen's "new_game" (task-2 brief).
  if (act === "new_game" || act === "new_game_confirm") {
    db.session.clear();
    recordedGameOver = false;
    ui.sheet = null;
    ui.screen = "newgame";
    ui.picker = await buildPicker();
    render();
    return;
  }
  if (act === "ng_players") {
    const n = Number(arg);
    const threats = ui.picker.threats;
    ui.picker.players = n;
    ui.picker.threats = Array.from({ length: n }, (_, i) => threats[i] ?? 25);
    render();
    return;
  }
  if (act === "ng_threat-" || act === "ng_threat+") {
    const i = Number(arg);
    const d = act === "ng_threat-" ? -1 : 1;
    ui.picker.threats[i] = Math.max(0, (ui.picker.threats[i] ?? 25) + d);
    render();
    return;
  }
  if (act === "pick_scenario") {
    const slug = arg;
    const b = await db.bundle(slug);
    const entry = ui.picker.index?.scenarios?.find(s => s.slug === slug);
    if (!b || !entry) {
      // The catalog changed under us mid-pick (or the bundle fetch failed) -
      // surface it rather than leaving the tap looking like it did nothing.
      ui.picker.error = CATALOG_UNAVAILABLE;
      render();
      return;
    }
    const scenarioMeta = {
      slug: entry.slug, name: entry.name, pack: entry.pack, cycle: entry.cycle,
      source: entry.source, kind: entry.kind,
      nightmare: false, mode: "Standard",
      maxCardThreat: entry.maxCardThreat, hasXThreat: entry.hasXThreat,
    };
    const players = ui.picker.players;
    const threats = ui.picker.threats;
    db.session.clear();
    recordedGameOver = false;
    game = new GameState(players);
    game.clock = clock;
    threats.forEach((t, i) => {
      game.players[i].threat = t;
      game.players[i].starting_threat = t;
    });
    game.logEvent(`New game: ${players} players, threat ${threats.join("/")}, first P1`);
    game.preloadScenario(scenarioMeta, b.stages);
    game.view = "quest_setup";
    ui.sheet = null;
    ui.screen = "play";
    db.session.saveState(game);
    render();
    return;
  }
  const changed = perform(game, ui, act, arg);
  if (!changed) return;
  // Auto-opens the elimination sheet (Task 3) / resolution sheet (Task 7)
  // when the tap that just changed the game triggered one - see actions.js.
  afterTap(game, ui);
  if (game.game_over) {
    ui.screen = "gameover";
    // Record the finished game once, on the transition into the game-over
    // screen, then make it durable - mirrors main.js ~586-592.
    if (!recordedGameOver) {
      recordedGameOver = true;
      db.history.append(game.historyRecord());
      db.session.flush(game);
    }
  }
  db.session.record(game);
  render();
}

root.addEventListener("click", ev => {
  // A sheet's body carries [data-stop] (sheets.js) so a tap that lands on
  // it - anywhere but a real [data-act] button inside it - never bubbles to
  // the scrim's own data-act="sheet_close" and closes the sheet under the
  // player's finger. A tap outside the sheet altogether (on the scrim, or
  // anywhere on the normal play screen, where there is no [data-stop]
  // ancestor at all) is unaffected.
  const stop = ev.target.closest("[data-stop]");
  const btn = ev.target.closest("[data-act]");
  if (stop && (!btn || !stop.contains(btn))) return;
  if (!btn) return;
  handleAct(btn.dataset.act, btn.dataset.arg ?? "");
});

// Gameplay touches RAM only (perform(), above); tick() drains the queue in
// the background - see db.js's Session doc comment. flush() on pagehide so a
// tab close/reload never loses the last few taps' journal entries.
setInterval(() => db.session.tick(game), 250);
window.addEventListener("pagehide", () => db.session.flush(game));

boot();
