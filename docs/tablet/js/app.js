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
import { imagePrefix, cyclesFor, groupByCycle } from "../../js/quest_catalog.js";
import { imageUrls } from "./cardimage.js";
import { overviewFor, scenarioMetaFor } from "./overview.js";

// A finished game is appended to history once. Reset wherever `game` is
// rebound (new game / a fresh scenario pick) - mirrors main.js's own
// `recordedGameOver` (main.js ~127, ~338, ~433).
let recordedGameOver = false;

// Where "Resume game" goes: the screen boot() would have landed on before the
// landing screen existed. Held here rather than recomputed from `game` at tap
// time so the two can never disagree about a game that ended in the save.
let resumeTarget = "play";

// The app is meant to fill the iPad. Two routes, and neither is a meta tag
// that Safari reads for a plain tab (there isn't one):
//
//   - Add to Home Screen. The manifest's `display: standalone` and
//     `apple-mobile-web-app-capable` are what make that launch chrome-free;
//     iOS reads them when the icon is added, so an icon added before they
//     shipped keeps the old behaviour until it is re-added.
//   - Element.requestFullscreen(), supported on arbitrary elements in Safari
//     on iPadOS 16.4+ (not on iPhone, where only <video> may go fullscreen).
//     It needs a user gesture, which is why this is called from the landing
//     screen's own CTA rather than at boot.
//
// Best-effort throughout: a browser without the API, a gesture the engine
// declines to honour, or a user who leaves fullscreen again all just leave
// the app running in the chrome it has. Nothing here may throw into a tap.
function goFullscreen() {
  try {
    const el = document.documentElement;
    if (document.fullscreenElement || !document.fullscreenEnabled) return;
    (el.requestFullscreen ?? el.webkitRequestFullscreen)?.call(el)?.catch?.(() => {});
  } catch { /* not available; the app is unaffected */ }
}

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

// Update the live DOM to match `next` IN PLACE, reusing every node that has
// not changed.
//
// render() used to be `root.innerHTML = layout(...)`, which throws the entire
// document away and builds a new one on every tap. That is why selecting a
// stage made the whole screen flash and every icon and card picture reload:
// the <img> elements were not re-fetched (they are cached) but they WERE new
// elements, so each one decoded and painted again from scratch.
//
// `isEqualNode` is the whole trick - it is a deep structural comparison, so an
// untouched subtree is recognised in one call and skipped entirely, images and
// all. Only the nodes that actually differ are touched, and an element that
// survives keeps its identity: its scroll position, and the decoded picture
// inside it.
//
// Nothing here is a framework. It reconciles by POSITION, which is right for
// this client because every list it draws is rendered in a stable order from
// the same source - and a mis-pairing would cost a repaint, never correctness,
// since the attributes and text are overwritten from `next` either way.
function morph(dst, src) {
  if (dst.isEqualNode(src)) return;
  if (dst.nodeType !== src.nodeType || dst.nodeName !== src.nodeName) {
    dst.replaceWith(src.cloneNode(true));
    return;
  }
  if (dst.nodeType === Node.TEXT_NODE || dst.nodeType === Node.COMMENT_NODE) {
    dst.data = src.data;
    return;
  }
  for (const a of [...dst.attributes]) {
    if (!src.hasAttribute(a.name)) dst.removeAttribute(a.name);
  }
  for (const a of src.attributes) {
    if (dst.getAttribute(a.name) !== a.value) dst.setAttribute(a.name, a.value);
  }
  const dn = [...dst.childNodes];
  const sn = [...src.childNodes];
  for (let i = 0; i < Math.max(dn.length, sn.length); i++) {
    if (!sn[i]) { dn[i].remove(); continue; }
    if (!dn[i]) { dst.appendChild(sn[i].cloneNode(true)); continue; }
    morph(dn[i], sn[i]);
  }
}

// The host element's OWN attributes are the page's, not the render's (#app
// carries the id index.html ships and every fixed-position rule keys off it),
// so only its children are reconciled.
function morphChildren(dst, src) {
  const dn = [...dst.childNodes];
  const sn = [...src.childNodes];
  for (let i = 0; i < Math.max(dn.length, sn.length); i++) {
    if (!sn[i]) { dn[i].remove(); continue; }
    if (!dn[i]) { dst.appendChild(sn[i].cloneNode(true)); continue; }
    morph(dn[i], sn[i]);
  }
}

function render() {
  const next = document.createElement("div");
  next.innerHTML = layout(game, ui);
  morphChildren(root, next);
  markRoute();
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
// comment. Caught here, once, so a missing catalog costs the player the
// picker's rows (and the overview's metadata) rather than the whole page.
// db.index() caches, so every caller below shares the one read.
async function catalogIndex() {
  try { return await db.index(); }
  catch (e) { console.error("tablet: quest catalog unavailable", e); return null; }
}

async function buildPicker() {
  const index = await catalogIndex();
  // The card-art prefix rides along with the index the picker already had to
  // read - the resume path (boot()) reads the same one for itself.
  ui.imagePrefix = imagePrefix(index);
  // Milestone 6 (Task 2): the tablet-density picker starts on the Official
  // source, its first cycle selected - cyclesFor() degrades to [] for a
  // null/empty index, same as every other catalog-optional read here.
  const source = "official";
  const cycle = index ? (cyclesFor(index, source)[0]?.cycle ?? null) : null;
  // `drill`/`slug` are the master/detail chooser's own state (M7): which of
  // the left column's two lists is showing, and which quest the detail on
  // the right belongs to. A fresh picker starts at the top of the drill-in
  // with nothing selected, so the detail side shows its instruction.
  return { index, players: 2, threats: [25, 25], source, cycle,
           drill: "cycles", slug: null, stage: "overview", locked: false,
           error: index ? null : CATALOG_UNAVAILABLE };
}

// Warm the image cache for the scenario the players just committed to (Task
// 6): the whole bundle db.bundle() pins - the scenario's own set AND every
// set it gathers, not only the own-set cards the overview's Cards grid
// shows - in one message, while they are still laying out heroes. Fired
// from begin_setup, not pick_scenario - the spec says "Begin setup
// prefetches", and milestone 6's Task 2 split the one act in two: picking
// now only OPENS the Scenario overview, which a player may well back out of
// to read another quest. Prefetching there spent the bandwidth on every
// scenario browsed rather than the one committed to (M5 final review).
// Fire-and-forget by design - there is no controller at
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

// WHERE THE PLAYER IS, as a small record the next launch can restore. Only
// the fields that decide what is on screen: the screen itself, and the setup
// flow's own position in its lists. Not the sheet - a modal restored on top
// of a recovery reload is a trap, not a convenience - and not any of the
// per-game seats (ui.overview, ui.locations, ui.tips), which are rebuilt from
// the slug because they are 10 KB of catalog, not navigation.
function currentRoute() {
  const p = ui.picker ?? {};
  return {
    screen: ui.screen,
    source: p.source ?? null, cycle: p.cycle ?? null,
    drill: p.drill ?? null, slug: p.slug ?? null, stage: p.stage ?? null,
    players: p.players ?? null, threats: p.threats ?? null,
  };
}

// A TAP MUST NEVER TOUCH STORAGE (CLAUDE.md). So render() only marks the
// route dirty in RAM, and the same background interval that drains the
// session queue is what writes it - on a frame with nothing else to do, and
// only when it actually changed.
let routeDirty = null;
function markRoute() {
  const next = JSON.stringify(currentRoute());
  if (next !== routeDirty?.json) routeDirty = { json: next };
}
function flushRoute() {
  if (!routeDirty) return;
  const { json } = routeDirty;
  routeDirty = null;
  try { db.route.save(JSON.parse(json)); } catch (e) { /* never a tap's problem */ }
}

// Put the player back where they were. Everything here degrades to the
// landing screen rather than to a broken view: a route naming a play screen
// with no save behind it, a setup screen whose scenario has left the catalog,
// a corrupt record - all of them just fall through.
async function restoreRoute(haveGame) {
  const r = db.route.load();
  const screen = r?.screen;
  if (!screen || screen === "home") return false;
  if (screen === "play" || screen === "log" || screen === "gameover") {
    if (!haveGame) return false;
    // The game itself decides whether it is over, never the route.
    ui.screen = game.game_over ? "gameover" : (screen === "gameover" ? "play" : screen);
    return true;
  }
  if (screen !== "newgame" && screen !== "players" && screen !== "overview") return false;
  ui.picker = await buildPicker();
  if (ui.picker.error) return false;
  if (r.source) ui.picker.source = r.source;
  if (r.cycle) ui.picker.cycle = r.cycle;
  if (r.drill) ui.picker.drill = r.drill;
  if (Number.isFinite(r.players)) ui.picker.players = r.players;
  if (Array.isArray(r.threats) && r.threats.length) ui.picker.threats = r.threats;
  // A screen that shows a scenario needs that scenario's bundle back. If it
  // no longer resolves, keep the list and drop the selection rather than
  // stranding the player on a step whose subject is missing.
  // seatScenario resets the stage to the overview, so the remembered one is
  // reapplied after it - not before.
  if (r.slug && !(await seatScenario(r.slug))) {
    ui.picker.slug = null;
    ui.picker.error = null;
    ui.screen = "newgame";
    return true;
  }
  if (ui.picker.slug && r.stage) ui.picker.stage = r.stage;
  ui.screen = ui.picker.slug ? screen : "newgame";
  return true;
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
    // The pinned card-image URL prefix (M5, Task 6) is needed on BOTH boot
    // paths: a resumed game never builds a picker, but it can still open the
    // location picker mid-round, and that is where the card art shows.
    const index = await catalogIndex();
    ui.imagePrefix = imagePrefix(index);
    // The read-only Scenario overview (M6, Task 3) the QUEST zone's stage
    // pill opens mid-game. Seated HERE, at boot, for the same reason the
    // bundle's other pieces are: opening a reference screen must not cost a
    // catalog read mid-round. `entry` is null when the index failed to load
    // - the render falls back to the save's own scenario name - and the seat
    // is skipped entirely for a bare/manual game with no bundle at all,
    // which is what open_overview declines on.
    if (b && game.scenario?.slug) {
      ui.overview = overviewFor(index, game.scenario.slug, b, {
        difficulty: game.scenario.mode ?? "Standard", readonly: true,
      });
    }
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
    // M7: a save no longer lands straight in the game. The landing screen
    // shows it as "Resume game" with a stamp saying which quest and how far
    // in - a player who wants a different game had no way to say so before,
    // and one coming back to this one loses a single tap.
    resumeTarget = game.game_over ? "gameover" : "play";
    ui.home = { resume: {
      name: game.scenario?.name ?? null,
      round: game.round,
      savedAt: saved.saved_at ?? null,
    } };
  } else {
    ui.home = { resume: null };
  }
  ui.screen = "home";
  // The landing screen is where a COLD launch lands. A reload is not a cold
  // launch - the player was looking at something - so the route puts them
  // back, and only falls through to home when it cannot.
  await restoreRoute(!!saved);
  render();
}

// Seat a scenario's bundle and mark it as the chooser's selection. Its own
// function because two things reach it: the player tapping a row, and
// entering a cycle (which auto-picks that cycle's first quest, so the detail
// side is never empty once you are inside a cycle).
//
// It awaits db.bundle(), which is why it lives here and not in
// acts_newgame.js with the rest of the chooser's ui-only acts.
async function seatScenario(slug) {
  // Already showing this one? Then this tap changed nothing, and re-seating it
  // would still cost a full render - root.innerHTML is replaced wholesale, so
  // every card and icon <img> is torn down and re-resolved, which is the flash
  // you see when you tap the row that is already selected.
  if (ui.picker?.slug === slug && ui.overview?.slug === slug) return true;
  const b = await db.bundle(slug);
  const overview = overviewFor(ui.picker.index, slug, b);
  if (!b || !overview.entry) {
    // The catalog changed under us mid-pick (or the bundle fetch failed) -
    // surface it rather than leaving the tap looking like it did nothing.
    ui.picker.error = CATALOG_UNAVAILABLE;
    return false;
  }
  ui.locations = b.locations ?? [];
  // Same two fields as boot()'s resume path (Task 4) - seated here too since
  // a fresh pick never goes through that branch at all.
  ui.tips = b.tips ?? null;
  ui.scenarioSlug = overview.entry.slug;
  ui.overview = overview;
  ui.sheet = null;
  // Picking does not LEAVE the chooser (M7): the detail fills the right two
  // thirds of the same screen, so comparing three quests in a cycle costs
  // three taps rather than three taps and three Backs. ui.picker.slug is
  // what marks the selected row and what gates the Continue CTA -
  // newgame.js will not draw a detail whose slug the picker is not
  // actually pointing at.
  ui.picker.slug = overview.entry.slug;
  // Picking a DIFFERENT scenario drops the lock: the lock says "this is the
  // one", and it cannot go on saying that about a quest you just moved off.
  ui.picker.locked = false;
  ui.picker.locking = false;
  // A freshly picked scenario always opens on its overview: it is the first
  // row of the stage list and the whole-quest view, and carrying the previous
  // scenario's stage number across would land on a stage this quest may not
  // even have.
  ui.picker.stage = "overview";
  return true;
}

// The tap. Seating is separate because boot() restores a pick without one.
async function pickScenario(slug) {
  const before = ui.picker?.slug;
  const seated = await seatScenario(slug);
  // Nothing moved: same scenario, same seat, no error to show.
  if (seated && before === ui.picker?.slug && !ui.picker?.error) return;
  render();
}

// The first quest of a cycle, in the order the chooser lists them - the same
// groupByCycle the render uses, so "first" cannot mean two different things.
function firstScenarioOf(cycle) {
  const source = ui.picker?.source ?? "official";
  const group = groupByCycle(ui.picker?.index?.scenarios ?? [], source)
    .find(g => g.cycle === cycle);
  return group?.scenarios?.[0]?.slug ?? null;
}

async function handleAct(act, arg) {
  // The landing screen's two ways in. Both are the first real tap of the
  // session, which is what makes them the right place to ask for fullscreen:
  // the Fullscreen API requires a user gesture, and this is the only gesture
  // guaranteed to happen before the player is looking at the board.
  if (act === "home_new" || act === "home_resume") {
    goFullscreen();
    if (act === "home_resume") {
      ui.screen = resumeTarget;
      render();
      return;
    }
    ui.picker = await buildPicker();
    ui.screen = "newgame";
    render();
    return;
  }
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
  if (act === "pick_scenario") { await pickScenario(arg); return; }
  if (act === "begin_setup") {
    // The other half of what pick_scenario used to do in one step (Task 2):
    // this is where the game object itself is actually created, so this is
    // where the queue gets cleared/tagged - see CLAUDE.md's "queue is tagged
    // with its game object" rule. ui.overview.difficulty is the Scenario
    // overview's own ladder pick (Task 3), and scenarioMetaFor() - pure, in
    // overview.js - is what turns it into the game's own `nightmare`/`mode`.
    const { entry, bundle, difficulty } = ui.overview;
    const scenarioMeta = scenarioMetaFor(entry, difficulty);
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
    prefetchCardImages(bundle);
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
  // The corner reload (layout.js). Everything the app knows is durable in
  // storage - the state checkpoint, the log, the delta journal - so a reload
  // is a re-render from the save, never a loss. Flush first so a checkpoint
  // still sitting in the background queue is on disk before the page goes.
  if (act === "reload_app") {
    try { db.session.flush(game); } catch (e) { /* nothing queued, or no game */ }
    flushRoute();   // the interval may not have reached this tap yet
    // A HARD reload, because a plain one is not enough here: sw.js serves the
    // shell stale-while-revalidate, which is right for a cold start (the app
    // opens instantly, the new version lands in the background) and wrong for
    // a button whose entire job is "give me the current code" - it would hand
    // back the previous version every single time, and the fix would look
    // like it had not shipped.
    //
    // Dropping the SHELL cache is enough: the next fetch has nothing to serve
    // from and goes to the network. The image cache is deliberately left
    // alone - it holds megabytes of card art that has not gone stale, and
    // re-downloading it is exactly what a player on hotel wifi does not want
    // from a recovery button.
    //
    // Cache Storage is same-origin from the page, so this needs no round trip
    // through the worker; a browser with no caches API at all just reloads.
    (async () => {
      try {
        const keys = await caches.keys();
        await Promise.all(keys.filter(k => /shell/.test(k)).map(k => caches.delete(k)));
      } catch (e) { /* no Cache Storage, or a browser that refuses */ }
      location.reload();
    })();
    return;
  }
  if (ui.screen === "home" || ui.screen === "players"
      || ui.screen === "newgame" || ui.screen === "overview") {
    // The picker's own edits (ng_source/ng_cycle/ng_players/ng_threat±,
    // acts_newgame.js) and the Scenario overview's (ov_difficulty/ov_back/
    // ov_close, acts_overview.js) are ui-only - they never touch `game` at
    // all. They must NOT go through perform()/db.session.record(): `game`
    // here can still be the PREVIOUS, already-finished GameState ("new_game"
    // clears the session but does not rebind `game` - only begin_setup
    // does), and a queued write tagged
    // to it would resurrect a save the player just asked to leave behind
    // (CLAUDE.md's "the queue is tagged with its game object" hazard - a
    // rebind is what is supposed to drop it, and none has happened yet).
    const changed = dispatch(game, ui, act, arg);
    // ng_lock only raised `locking`, so the rows are still on screen wearing
    // the class that folds them away. Let that run, then settle to the locked
    // state - which is what actually removes them. Timed here rather than on
    // an animationend listener because the renderers are pure string builders
    // and own no elements to listen on; the duration is style.css's own.
    if (changed && act === "ng_lock") {
      render();
      // style.css's own fold duration (240ms) plus newgame.js's biggest
      // stagger (160ms, capped): settling sooner would cut the fold off
      // mid-collapse on the rows nearest the top, which are the last to go.
      setTimeout(() => {
        if (!ui.picker?.locking) return;
        ui.picker.locking = false;
        ui.picker.locked = true;
        render();
      }, 420);
      return;
    }
    // Entering a cycle auto-picks its first quest, so the detail side is
    // never blank once you are inside one: the list and the detail always
    // describe the same thing. It is a second act on one tap rather than a
    // branch inside ng_cycle because it awaits db.bundle() - dispatch()'s
    // handlers are pure and synchronous by contract.
    if (changed && act === "ng_cycle") {
      const first = firstScenarioOf(ui.picker.cycle);
      if (first) { await pickScenario(first); return; }
    }
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
  // The card quick view is the one act that needs more than an act and an
  // arg: it carries the card's face image FILENAMES, so the modal needs no
  // lookup table and every render function stays pure. Read off the element
  // that was tapped rather than threaded through a seat nothing else wants.
  if (btn.dataset.act === "open_card") {
    const files = (btn.dataset.files ?? "").split(",").filter(Boolean);
    if (!files.length) return;
    ui.sheet = { kind: "card", name: btn.dataset.arg ?? "",
                 caption: btn.dataset.caption ?? "", files, face: 0 };
    render();
    return;
  }
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
  if (img?.tagName !== "IMG") return;
  // A set icon can carry a fallback chain (seticon.js's iconSlugs): the pack
  // files a handful of sets under a different title than the one FFG prints,
  // so a 404 on the printed name is not yet a missing icon. Shift the next
  // candidate off data-alt and retry; only an empty chain means the glyph.
  const alt = img.dataset?.alt;
  if (alt) {
    const [next, ...rest] = alt.split(",");
    img.dataset.alt = rest.join(",");
    if (!img.dataset.alt) delete img.dataset.alt;
    img.src = next;
    return;
  }
  img.closest(".seticon, .card-frame")?.classList.add("is-missing");
}, true);

// Gameplay touches RAM only (perform(), above); tick() drains the queue in
// the background - see db.js's Session doc comment. flush() on pagehide so a
// tab close/reload never loses the last few taps' journal entries.
setInterval(() => { db.session.tick(game); flushRoute(); }, 250);
window.addEventListener("pagehide", () => { db.session.flush(game); flushRoute(); });

// The service worker (Task 6): this client's offline shell and its card-image
// cache. Registered from here rather than from index.html so the SCOPE is
// derived instead of written down. sw.js lives at the SITE ROOT (Task 1 of
// the hosting plan moved it there - a worker's scope can never be broader
// than its own directory, and the root is what lets it also cover /presto/,
// the Presto web twin, alongside this client). That root is either the
// origin itself (lotrlcg.app) or a subpath (GitHub Pages serves the mirror
// under /lotr-lcg-presto-hud/) - new URL("./", swUrl) IS that directory on
// either host, which is why the scope is derived rather than written down.
// docs/sw.js's isShellOrData mirrors this same derivation from self.location
// so the two agree on what "the site directory" means.
// Every failure is swallowed: no service worker support, an insecure origin,
// a file:// preview - the client works exactly as it did before, just
// without a cache.
if ("serviceWorker" in navigator) {
  const swUrl = new URL("../../sw.js", import.meta.url);
  navigator.serviceWorker.register(swUrl, { scope: new URL("./", swUrl).href })
    .catch(() => {});
}

// A diagnostic for the one surface no inspector can reach: the app running
// standalone on the iPad, where there is no Safari, no dev tools and no
// remote debugging. `?debug=1` paints the numbers that decide the layout -
// the several heights iOS can disagree about, and the safe-area insets it
// reports - straight onto the screen, so a screenshot IS the measurement.
//
// Off unless asked for, appended after the app rather than inside it, and it
// reads nothing it could change.
function debugOverlay() {
  if (!/(^|[?&])debug=1(&|$)/.test(location.search)) return;
  const el = document.createElement("pre");
  el.className = "debug-overlay";
  // "Is this even the new code?" is the first question any layout report has
  // to answer, and on a device with no inspector there is no other way to ask
  // it. The stylesheet's own BYTE LENGTH is the answer, read out of resource
  // timing rather than fetched - this file may not fetch (the no-stray-IO
  // guard, and rightly: a stray fetch is how a screen grows its own cache).
  // The length changes with every edit, so it identifies the build; and
  // transferSize 0 means the bytes came from a cache rather than the wire,
  // which is the other half of "am I looking at something stale".
  let cacheNames = [];
  caches?.keys?.().then(k => { cacheNames = k; }).catch(() => {});
  const cssEntry = () => performance.getEntriesByType?.("resource")
    ?.find(e => e.name.endsWith("style.css")) ?? null;
  const read = () => {
    const cs = getComputedStyle(document.documentElement);
    const box = document.getElementById("app").getBoundingClientRect();
    const pane = document.querySelector(".pane")?.getBoundingClientRect();
    const cta = document.querySelector(".cta-row")?.getBoundingClientRect();
    const round = n => Math.round(n * 10) / 10;
    el.textContent = [
      `innerHeight        ${innerHeight}`,
      `visualViewport     ${round(visualViewport?.height ?? -1)}`,
      `documentElement    ${document.documentElement.clientHeight}`,
      `body               ${round(document.body.getBoundingClientRect().height)}`,
      `#app               ${round(box.top)} .. ${round(box.bottom)}  (h ${round(box.height)})`,
      `.pane              ${pane ? round(pane.top) + " .. " + round(pane.bottom) : "-"}`,
      `.cta-row           ${cta ? round(cta.top) + " .. " + round(cta.bottom) : "-"}`,
      `sa top/right/btm/left  ${cs.getPropertyValue("--sa-top").trim()} / ${cs.getPropertyValue("--sa-right").trim()} / ${cs.getPropertyValue("--sa-bottom").trim()} / ${cs.getPropertyValue("--sa-left").trim()}`,
      `standalone         ${!!navigator.standalone || matchMedia("(display-mode: standalone)").matches}`,
      `sw controlling     ${!!navigator.serviceWorker?.controller}`,
      `caches             ${cacheNames.join(" ") || "-"}`,
      `style.css bytes    ${cssEntry()?.decodedBodySize ?? "?"}  (from ${cssEntry()?.transferSize ? "network" : "cache"})`,
    ].join("\n");
  };
  read();
  document.body.appendChild(el);
  addEventListener("resize", read);
  visualViewport?.addEventListener("resize", read);
  setInterval(read, 1000);
}

boot();
debugOverlay();
