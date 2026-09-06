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
import { perform, dispatch, newUi, afterTap } from "./actions.js";
import { logText } from "./logfilter.js";
import { imagePrefix, cyclesFor } from "../../js/quest_catalog.js";
import { imageUrls } from "./cardimage.js";
import { overviewFor } from "./newgame.js";

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
  // The Game Log's row list is the one scrolling region whose position is not
  // implied by the markup, and innerHTML rebuilds it from scratch on every
  // render, so it comes back at scrollTop 0 every time. Opening the log
  // should land on the NEWEST lines (the bottom); once a row is selected,
  // that row is what the player is working with, so it is what stays in
  // view - it may be hundreds of rows up.
  if (ui.screen !== "log") return;
  const rows = root.querySelector(".log-rows");
  if (!rows) return;
  const sel = rows.querySelector(".is-sel");
  if (sel) sel.scrollIntoView({ block: "center" });
  else rows.scrollTop = rows.scrollHeight;
}

// db.index() PROPAGATES on failure (a docs/data/ build that was never run) -
// db.js's own contract, deliberately, per its "PROPAGATES on failure"
// comment. Caught here so a missing catalog lands the player on a working
// picker with the CATALOG_UNAVAILABLE line instead of a blank page.
async function buildPicker() {
  let index = null;
  try { index = await db.index(); }
  catch (e) { console.error("tablet: quest catalog unavailable", e); }
  // The card-art prefix rides along with the index the picker already had to
  // read - see seatImagePrefix() for the resume path, which has no picker.
  ui.imagePrefix = imagePrefix(index);
  // Milestone 6 (Task 2): the tablet-density picker starts on the Official
  // source, its first cycle selected - cyclesFor() degrades to [] for a
  // null/empty index, same as every other catalog-optional read here.
  const source = "official";
  const cycle = index ? (cyclesFor(index, source)[0]?.cycle ?? null) : null;
  return { index, players: 2, threats: [25, 25], source, cycle,
           error: index ? null : CATALOG_UNAVAILABLE };
}

// The pinned card-image URL prefix (Task 6). Needed on BOTH boot paths: a
// resumed game never builds a picker, but it can still open the location
// picker mid-round, and that is where the card art shows. db.index()
// PROPAGATES on failure (db.js's contract), and it caches, so this is one
// read shared with buildPicker() - caught here the same way, because a
// catalog that will not load must cost the player captions, not the app.
async function seatImagePrefix() {
  try { ui.imagePrefix = imagePrefix(await db.index()); }
  catch (e) { ui.imagePrefix = null; }
}

// Warm the image cache for the scenario the players just committed to (Task
// 6): every card db.bundle() pins, in one message, while they are still
// laying out heroes. Fire-and-forget by design - there is no controller at
// all on the very first load (the worker activates after this page did), the
// browser may have no service workers, and a failure here costs a hotlink on
// the first location picker, never a tap. Nothing awaits it.
function prefetchCardImages(bundle) {
  try {
    const urls = imageUrls(bundle, ui.imagePrefix);
    if (urls.length) {
      navigator.serviceWorker?.controller?.postMessage({ type: "prefetch", urls });
    }
  } catch (e) { /* no worker, or a browser that refuses to post */ }
}

async function boot() {
  // Rules text is static catalog data, not per-game state - scenario-
  // independent, so it is seated once here regardless of which branch
  // below runs, the same way db.bundle()'s pieces are seated per-game.
  // Degrades to null on any catalog failure (db.rulesText()'s contract).
  ui.rules = await db.rulesText();
  const saved = db.session.loadState();
  if (saved) {
    game = GameState.fromDict(saved.state);
    game.clock = clock;
    db.session.loadReplay(game);
    db.session.loadLog(game);
    const b = game.scenario?.slug ? await db.bundle(game.scenario.slug) : null;
    if (b) game.rehydrateStages(b.stages);
    // The location picker (Task 5) reads ui.locations, never fetches its
    // own - db.bundle() already carries loadLocations()'s list (~10 KB,
    // pinned for the game per its own comment), so a resume just needs to
    // seat it. `b` is null for a bare/manual game with no scenario at all,
    // and loadLocations degrades to [] on any catalog failure - either way
    // the picker still opens, straight to its manual entry.
    ui.locations = b?.locations ?? [];
    // The Notes panel/sheet (Task 4) - the whole tips.json map plus the
    // current scenario's own slug, so notes.js's notesFor()/allNotes() can
    // index it (db.bundle()'s "tips" field is the WHOLE map, not a per-
    // scenario slice - db.js's own comment). Both null for a bare/manual
    // game with no scenario at all (`b` null above), same degrade-to-
    // "no panel" contract as an absent tips.json.
    ui.tips = b?.tips ?? null;
    ui.scenarioSlug = game.scenario?.slug ?? null;
    await seatImagePrefix();
    // A save can land exactly between a successful "resolve" and
    // "apply_alloc" (pending_budget > 0, nothing placed yet). ui.alloc is
    // never part of the save (it is UI state, not game state), and pane.js
    // no longer seeds it lazily on render (finding 13) - so without this,
    // resuming into that window would skip straight to the outcome pane and
    // strand the pending progress. Reseed it the same way "resolve" does.
    if (game.pending_budget > 0) ui.alloc = game.autoSplit(game.pending_budget);
    // pending_elim/pending_resolution are part of the saved state (review
    // finding M6) - a save that landed with one unanswered showed no prompt
    // at all on resume, because afterTap only ran after a live tap
    // (actions.js), never on boot. Seat it before the first render, exactly
    // like every other tap does.
    afterTap(game, ui);
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
  if (act === "pick_scenario") {
    // Milestone 6 (Task 2): picking a scenario no longer starts the game -
    // it opens the Scenario overview (Task 3 renders it; layout.js carries
    // a placeholder until then) so the player sees the difficulty ladder,
    // stages and cards before committing. ng_players/ng_threat± moved out
    // to acts_newgame.js (ui-only, ui.picker edits) - this stays here
    // because it awaits db.bundle().
    const slug = arg;
    const b = await db.bundle(slug);
    const overview = overviewFor(ui.picker.index, slug, b);
    if (!b || !overview.entry) {
      // The catalog changed under us mid-pick (or the bundle fetch failed) -
      // surface it rather than leaving the tap looking like it did nothing.
      ui.picker.error = CATALOG_UNAVAILABLE;
      render();
      return;
    }
    ui.locations = b.locations ?? [];
    // Same two fields as the resume path above (Task 4) - seated here too
    // since a fresh pick never goes through boot()'s branch at all.
    ui.tips = b.tips ?? null;
    ui.scenarioSlug = overview.entry.slug;
    prefetchCardImages(b);
    ui.overview = overview;
    ui.sheet = null;
    ui.screen = "overview";
    render();
    return;
  }
  if (act === "begin_setup") {
    // The other half of what pick_scenario used to do in one step (Task 2):
    // this is where the game object itself is actually created, so this is
    // where the queue gets cleared/tagged - see CLAUDE.md's "queue is tagged
    // with its game object" rule. ui.overview.difficulty is the Scenario
    // overview's own ladder pick (Task 3; "Standard" until then, seated by
    // overviewFor()).
    const { entry, bundle, difficulty } = ui.overview;
    const scenarioMeta = {
      slug: entry.slug, name: entry.name, pack: entry.pack, cycle: entry.cycle,
      source: entry.source, kind: entry.kind,
      nightmare: difficulty === "Nightmare", mode: difficulty,
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
    game.preloadScenario(scenarioMeta, bundle.stages);
    game.view = "quest_setup";
    ui.sheet = null;
    ui.screen = "play";
    db.session.saveState(game);
    render();
    return;
  }
  if (act === "copy_log") {
    // The clipboard is the only browser API this client asks the platform
    // for, so it is handled here rather than as an act: acts_*.js are pure.
    // A refusal (no permission, an insecure origin, a browser with no
    // navigator.clipboard at all) is swallowed and nothing re-renders - the
    // readonly textarea right beside the button still holds the text to
    // select by hand, which is the fallback the sheet was built around.
    navigator.clipboard?.writeText(logText(game)).catch(() => {});
    return;
  }
  if (act === "open_sqpick") {
    // Lazy, like ui.locations above - db.sideQuests() caches after its first
    // call (DataClient's own _sideQuests), so a second "+ Side quest" tap
    // never refetches. loadPlayerSideQuests() degrades to [] on any catalog
    // failure rather than throwing, so this never leaves the sheet unopened
    // - only the picker's rows are empty and its Manual entry chip is the
    // one way forward (sheet_sqpick.js's own empty-catalog branch).
    ui.sideQuests = await db.sideQuests();
    ui.sheet = { kind: "sqpick", sphere: null, selected: null, page: 0 };
    render();
    return;
  }
  if (ui.screen === "newgame" || ui.screen === "overview") {
    // The picker's own edits (ng_source/ng_cycle/ng_players/ng_threat±) and
    // the overview placeholder's ov_back are ui-only (acts_newgame.js) -
    // never touch `game` at all. They must NOT go through perform()/
    // db.session.record(): `game` here can still be the PREVIOUS,
    // already-finished GameState ("new_game" clears the session but does
    // not rebind `game` - only begin_setup does), and a queued write tagged
    // to it would resurrect a save the player just asked to leave behind
    // (CLAUDE.md's "the queue is tagged with its game object" hazard - a
    // rebind is what is supposed to drop it, and none has happened yet).
    const changed = dispatch(game, ui, act, arg);
    if (changed) render();
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

// Task 5's set icons (seticon.js) and Task 6b's card images both render a
// plain <img> that can fail to load (a set name whose slug the icon pack
// has no SVG under, a card-art hotlink that doesn't resolve) - this is the
// one place that catches it, for both. `error` events on <img> don't
// bubble, so this must be capture-phase to see them at all; the wrapper
// (.seticon/.card-frame), not the <img> itself, is what actually swaps in
// the fallback glyph (style.css's `.is-missing` pair of rules).
root.addEventListener("error", ev => {
  const img = ev.target;
  if (img?.tagName === "IMG") img.closest(".seticon, .card-frame")?.classList.add("is-missing");
}, true);

// Gameplay touches RAM only (perform(), above); tick() drains the queue in
// the background - see db.js's Session doc comment. flush() on pagehide so a
// tab close/reload never loses the last few taps' journal entries.
setInterval(() => db.session.tick(game), 250);
window.addEventListener("pagehide", () => db.session.flush(game));

// The service worker (Task 6): this client's offline shell and its card-image
// cache. Registered from here rather than from index.html so the SCOPE is
// derived instead of written down - GitHub Pages serves the site under
// /lotr-lcg-presto-hud/tablet/, not /tablet/, and a hard-coded "/tablet/"
// would be rejected there (a worker's scope can never be broader than its
// own directory). new URL("./", swUrl) IS that directory, on either host.
// Every failure is swallowed: no service worker support, an insecure origin,
// a file:// preview - the client works exactly as it did before, just
// without a cache.
if ("serviceWorker" in navigator) {
  const swUrl = new URL("../sw.js", import.meta.url);
  navigator.serviceWorker.register(swUrl, { scope: new URL("./", swUrl).href })
    .catch(() => {});
}

boot();
