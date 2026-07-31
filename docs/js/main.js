// Port of main.py — boot flow, nav stack, modal loop, notifications,
// persistence (localStorage instead of flash), virtual LED strip.
import { pal, bevel, rect } from "./ui.js";
import { GameState, VIEW_LABELS, viewForStep } from "./gamestate.js";
import { step as phaseStep, phase as phaseInfo } from "./phases.js";
import { ScreenPlay } from "./screen_play.js";
import { ScreenPhases, ScreenLog, ScreenSettings, BootScreen, SetupScreen,
         LedModal, ScreenAbout, GameOverScreen, ScenarioSourceScreen,
         PickCycleScreen, ChooseScenarioScreen,
         ScenarioOptionsScreen, FirstRunScreen, LegendScreen , CatalogUnavailableScreen } from "./screens_other.js";
import { EliminationModal, QuestCardModal, SideQuestPickModal,
         ResolutionModal, LocationPickModal,
         QuestingProgressModal, LocationConfigModal } from "./screens.js";
import { loadIndex, loadScenario, cyclesFor, groupByCycle, loadPlayerSideQuests,
         loadIcons, loadTips, loadLocations,
         resumePickerState } from "./quest_catalog.js";

const STATE_KEY = "lotr-hud-state";
const PREFS_KEY = "lotr-hud-prefs";
const canvas = document.getElementById("screen");
const ctx = canvas.getContext("2d");
const clock = () => Math.floor(performance.now());
// Pre-game screens with no live game to animate: LED/notification/elimination
// per-tick housekeeping (below) is skipped while any of these is active.
const PREGAME_ACTIVE = ["boot", "setup", "scenario_source", "pick_cycle",
                        "choose_scenario", "scenario_options", "firstrun", "legend"];

function loadPrefs() {
  try {
    const d = JSON.parse(localStorage.getItem(PREFS_KEY)) ?? {};
    return { brightness: d.brightness ?? 100, scene: d.scene ?? "phase" };
  } catch { return { brightness: 100, scene: "phase" }; }
}
function savePrefs(prefs) { localStorage.setItem(PREFS_KEY, JSON.stringify(prefs)); }

function loadSaved() {
  try {
    const d = JSON.parse(localStorage.getItem(STATE_KEY));
    if (!d) return [null, null];
    const game = GameState.fromDict(d.state);
    // A save with no scenario is from the removed manual/custom mode. There is
    // no view to resume it into, so it is not offered.
    if (!game.scenario?.slug) return [null, null];
    // Built by hand rather than via toLocaleString so it reads identically to
    // the firmware (main.py) regardless of the browser's locale: 12-hour with
    // AM/PM and a 2-digit year, sized for the 280px boot button.
    let when = "earlier session";
    if (d.saved_at) {
      const t = new Date(d.saved_at);
      const h = t.getHours() % 12 || 12;
      when = `${t.getMonth() + 1}/${t.getDate()}/${String(t.getFullYear() % 100).padStart(2, "0")}`
           + ` ${h}:${String(t.getMinutes()).padStart(2, "0")} ${t.getHours() < 12 ? "AM" : "PM"}`;
    }
    return [game, { round: game.round, step: game.step, saved_at: when }];
  } catch { return [null, null]; }
}
function saveState(game) {
  localStorage.setItem(STATE_KEY,
    JSON.stringify({ saved_at: Date.now(), state: game.toDict() }));
}
function clearState() { localStorage.removeItem(STATE_KEY); }

// -- delta replay store ------------------------------------------------------
// Parity: the Replay schema's two columns (backend/lib/dragn/replay.ex).
// Divergence D4 - two stores rather than one row: state.json/STATE_KEY keeps
// its exact shape and every-tap write path, and the history rides in its own
// key. Losing the history must never cost you the game, so every failure here
// is swallowed and simply leaves Back unavailable.
const REPLAY_KEY = "lotr-hud-replay";
function saveReplay(game) {
  try { localStorage.setItem(REPLAY_KEY, JSON.stringify(game.replayToDict())); }
  catch { /* history is expendable; the game is not */ }
}
function loadReplay(game) {
  try { game.replayFromDict(JSON.parse(localStorage.getItem(REPLAY_KEY))); }
  catch { game.replayFromDict(null); }
}
function clearReplay() { localStorage.removeItem(REPLAY_KEY); }
function saveExists() { return localStorage.getItem(STATE_KEY) !== null; }

// virtual LED strip (mirrors leds.py scenes)
const ledEls = [...document.querySelectorAll(".led")];
const GREEN = [20, 160, 40], AMBER = [200, 140, 20], RED = [200, 40, 30];
const TORCH = [200, 110, 25];
function threatColor(t) { return t >= 35 ? RED : t >= 20 ? AMBER : GREEN; }
function dangerColor(players) {
  const living = players.filter(p => !p.eliminated).map(p => p.threat);
  return living.length ? threatColor(Math.max(...living)) : GREEN;
}
function sceneColors(scene, game, tick) {
  if (scene === "off") return Array(7).fill([0, 0, 0]);
  if (scene === "danger") return Array(7).fill(dangerColor(game.players));
  if (scene === "torch") {
    return Array.from({ length: 7 }, (_, i) => {
      const n = (tick * 2654435761 + i * 40503) & 0xffff;
      const f = 70 + (n % 40);
      return TORCH.map(v => Math.min(255, Math.floor(v * f / 100)));
    });
  }
  const ph = phaseInfo(phaseStep(game.step).phase).color;
  const dg = dangerColor(game.players);
  return Array.from({ length: 7 }, (_, i) => (i === 3 ? dg : ph));
}
function updateLeds(game, prefs, tick = 0) {
  const colors = sceneColors(prefs.scene, game, tick);
  const b = prefs.brightness / 100;
  ledEls.forEach((el, i) => {
    const [r, g, bl] = colors[i].map(v => Math.floor(v * b));
    el.style.background = `rgb(${r},${g},${bl})`;
    el.style.boxShadow = (r + g + bl) > 30 ? `0 0 10px 2px rgba(${r},${g},${bl},.55)` : "none";
  });
}

function main() {
  let [savedGame, savedMeta] = loadSaved();
  let game = savedGame ?? new GameState();
  game.clock = clock;
  if (savedGame) loadReplay(game);
  const prefs = loadPrefs();

  const bootImg = new Image();
  bootImg.src = "assets/boot_bg.png";
  bootImg.onload = () => { dirty = true; };

  const screens = {
    play: new ScreenPlay(),
    phases: new ScreenPhases(),
    log: new ScreenLog(),
    settings: new ScreenSettings(prefs),
    boot: new BootScreen(savedMeta, bootImg),
    setup: new SetupScreen(),
    about: new ScreenAbout(),
    firstrun: new FirstRunScreen(),
    legend: new LegendScreen(),
    gameover: new GameOverScreen(),
    scenario_source: new ScenarioSourceScreen(),
    pick_cycle: new PickCycleScreen("official", []),
    choose_scenario: new ChooseScenarioScreen("official", "", []),
    scenario_options: new ScenarioOptionsScreen({}, {}),
  };
  let active = "boot";
  let navStack = [];
  let modal = null;
  let dirty = true;
  // A modal handing off to another modal closes itself first (the router
  // holds one at a time), and some handoffs need a catalog fetch before the
  // replacement exists. Without this the play screen paints in the gap - a
  // visible flash when you tap "+ Side quest" from the Progress modal. While
  // a handoff is in flight the last frame simply stays on screen.
  let modalPending = 0;
  let tick = 0;
  let prevView = game.view;
  const NOTIF_TICKS = 200;
  let notifT = 0;
  let catalogIndex = null;   // cached loadIndex() result (fetched once)
  let iconsCache = null;     // cached loadIcons() result (fetched once; loadIcons()
                              // never rejects, so no extra try/catch needed)
  let tipsCache = null;      // cached loadTips() result (M4-B tips; never rejects
                              // either - lazily loaded both when entering the picker
                              // AND right before each QuestCardModal is built, so a
                              // resumed game that skipped the picker this session
                              // still gets tips - see the two "if (!tipsCache)" sites
                              // below)
  let locationsCache = null; // cached loadLocations() result for the picked
                              // scenario (never rejects either). Fetched on the
                              // first Travel / "+ Add location" tap and kept for
                              // the game - the picked scenario cannot change
                              // mid-game, and a cold union is several fetches.

  function draw() {
    if (modal) modal.draw(ctx, game);
    else {
      screens[active].draw(ctx, game);
      if (!PREGAME_ACTIVE.includes(active)) updateLeds(game, prefs, tick);
    }
  }

  function pressFeedback(b) {
    const t = 2;
    rect(ctx, b.x, b.y, b.w, t, pal.bevel_d);
    rect(ctx, b.x, b.y, t, b.h, pal.bevel_d);
    rect(ctx, b.x, b.y + b.h - t, b.w, t, pal.bevel_l);
    rect(ctx, b.x + b.w - t, b.y, t, b.h, pal.bevel_l);
  }

  // -- the record point ------------------------------------------------------
  // One snapshot before a tap is dispatched, one diff after it settles -
  // mirroring the reference's single process_update call site
  // (game_ui_server.ex). No screen, modal or mutator learns anything about
  // undo.
  //
  // pendingGame guards the handlers that REPLACE `game` (new game, end game):
  // a delta diffed against a snapshot of a different object would be garbage,
  // so those paths simply record nothing.
  let pendingSnap = null, pendingGame = null;

  function beginAction() {
    pendingGame = game;
    pendingSnap = game.beginAction();
  }

  function commitAction() {
    if (pendingSnap && pendingGame === game) game.addDelta(pendingSnap);
    pendingSnap = pendingGame = null;
    saveState(game);
    saveReplay(game);
  }

  function handleTap(x, y) {
    if (modal) {
      for (const b of modal.buttons) {
        if (b.hit(x, y)) {
          pressFeedback(b);
          beginAction();
          setTimeout(() => {
            const result = modal.onButton(b);
            if (result === "close") {
              if (modal instanceof LedModal) savePrefs(prefs);
              else commitAction();
              modal = null;
            } else if (result === "cancel") modal = null;
            dirty = true;
          }, 90);
          return;
        }
      }
      return;
    }
    for (const b of screens[active].buttons) {
      if (b.hit(x, y)) {
        pressFeedback(b);
        beginAction();
        setTimeout(async () => {
          await handleResult(screens[active].onButton(b, game));
          dirty = true;
        }, 90);
        return;
      }
    }
  }

  // Rebuild the quest-picker screens from a resumed game's saved scenario.
  //
  // The picker screens are router-held, not game state, so a resume left them
  // as the empty placeholders the boot path constructed. Everything needed is
  // already in the save (game.scenario carries slug/source/cycle and the
  // chosen mode), so this reads it back and rebuilds all three - Scenario
  // Options for the scenario itself, and the two list screens behind it so
  // backing out further lands on a populated page with the right cycle
  // selected, not on an empty list.
  //
  // Lazy on purpose, at the first tap that needs a picker rather than during
  // resume: the boot path already defers every catalog fetch this way. A
  // resume that never backs out never pays for it. Never throws - a failure
  // leaves the placeholders and the caller falls back to the source page.
  // Re-read a resumed game's stage tree from the catalog.
  //
  // The save carries the scenario's SLUG, not its cards (see
  // GameState.toDict). This is where the assets come back, so a card-data
  // correction reaches a game already in progress instead of stopping at the
  // save boundary.
  //
  // Eager, unlike rehydratePickers below: the pickers are only needed if the
  // player backs out, but the stage tree is what the Quest Cards screen and
  // every flip read, so it should be in place before the first tap that wants
  // it. Best-effort - a custom game has no scenario, a slug can go missing,
  // and fetches fail; any of those leaves whatever fromDict loaded and the
  // game still plays.
  async function rehydrateStages() {
    try {
      const slug = game.scenario?.slug;
      if (!slug) return;
      const data = await loadScenario(slug);
      if (game.rehydrateStages(data?.quest?.stages ?? [])) dirty = true;
    } catch (e) {
      console.warn("resume: could not re-read the stage tree", e);
    }
  }

  async function rehydratePickers() {
    try {
      if (!catalogIndex) catalogIndex = await loadIndex();
      const state = resumePickerState(catalogIndex, game.scenario);
      if (!state) return;
      if (!iconsCache) iconsCache = await loadIcons();
      const data = await loadScenario(state.entry.slug);
      screens.pick_cycle = new PickCycleScreen(state.source, state.cycles);
      const chooser = new ChooseScenarioScreen(state.source, state.cycle,
                                               state.siblings);
      // Land on the scenario the game is actually playing, not the first row.
      chooser.selected = state.entry.slug;
      screens.choose_scenario = chooser;
      screens.scenario_options = new ScenarioOptionsScreen(
        state.entry, data, iconsCache, state.difficulty);
    } catch (e) {
      console.warn("resume: could not rebuild the picker screens", e);
    }
  }

  // async: a couple of result kinds (choose_scenario, scenario_chosen) fetch
  // catalog data before they can finish routing; handleTap above awaits this.
  async function handleResult(result) {
    if (Array.isArray(result)) {
      const kind = result[0];
      if (kind === "goto") {
        let target = result[1];
        // `.scenario?.slug`, NOT `.scenario`: the placeholder is built as
        // `new ScenarioOptionsScreen({}, {})` and `{}` is truthy in JS, so a
        // truthiness check never fired here and the screen rendered its
        // "Unknown scenario" empty state. Python's `not {}` is True, so the
        // two twins disagreed - the firmware bounced to the source page while
        // the web twin showed a blank options screen.
        if (target === "scenario_options" && !screens.scenario_options?.scenario?.slug) {
          // Resumed straight into the game, so the picker screens are still
          // the empty placeholders the boot path built. Rebuild them from the
          // saved scenario instead of making the player pick again; only a
          // game with nothing to rebuild from falls back to the source page.
          await rehydratePickers();
          if (!screens.scenario_options.scenario?.slug) target = "scenario_source";
        }
        if (target === "close") target = navStack.pop() ?? "play";
        else if (["settings", "log", "phases", "about", "firstrun", "legend"].includes(target)) {
          if (active !== target) navStack.push(active);
        } else navStack = [];
        active = target;
      } else if (kind === "modal") {
        modal = result[1];
        // Quest Setup button (first QuestCardModal entry point): screenPlay
        // builds the modal itself, so tips are attached here instead of at
        // construction (mirrors main.py's equivalent "modal" handling).
        if (modal instanceof QuestCardModal) {
          if (!tipsCache) tipsCache = await loadTips();
          modal.tips = tipsCache;
        }
      } else if (kind === "boot") {
        if (result[1] === "resume") { active = "play"; rehydrateStages(); }
        else if (result[1] === "about") { navStack.push("boot"); active = "about"; }
        else { screens.setup.hasSave = saveExists(); active = "setup"; }
      } else if (kind === "open_repo") {
        window.open("https://github.com/andrhamm/lotr-lcg-presto-hud", "_blank");
      } else if (kind === "start_game") {
        const [, threats, first] = result;
        clearState();
        clearReplay();
        game = new GameState(threats.length);
        threats.forEach((t, i) => {
          game.players[i].threat = t;
          game.players[i].starting_threat = t;
        });
        game.first_player = first ?? 0;
        game.clock = clock;
        game.logEvent(`New game: ${threats.length} players, threat ${threats.join("/")}, first P${(first ?? 0) + 1}`);
        saveState(game);
        prevView = game.view;
        active = "scenario_source";
      } else if (kind === "choose_scenario") {
        // Official/Community gate tapped: load (and cache) the whole catalog
        // index, then show that source's cycle list. A missing/unreachable
        // catalog (e.g. docs/data/ not built yet) falls back to the custom/
        // manual flow rather than leaving the tap handler hung on a rejected
        // promise.
        const source = result[1];
        try {
          if (!catalogIndex) catalogIndex = await loadIndex();
          if (!iconsCache) iconsCache = await loadIcons();
          if (!tipsCache) tipsCache = await loadTips();
          screens.pick_cycle = new PickCycleScreen(source, cyclesFor(catalogIndex, source));
          active = "pick_cycle";
        } catch (e) {
          // No silent downgrade: there is no manual mode to fall back to,
          // and an unreadable catalog means docs/data is missing - a bug to
          // see, not to paper over.
          console.error("quest catalog: loadIndex failed", e);
          game.logEvent("Quest catalog unavailable");
          screens.catalog_error = new CatalogUnavailableScreen(e);
          active = "catalog_error";
        }
      } else if (kind === "choose_scenario_list") {
        const [, source, cycle] = result;
        const groups = groupByCycle(catalogIndex?.scenarios ?? [], source);
        const group = groups.find(g => g.cycle === cycle);
        const chooser = new ChooseScenarioScreen(source, cycle, group?.scenarios ?? []);
        // Land on the scenario the player already has, not the first row. This
        // handler rebuilds the screen from scratch, so backing out of Scenario
        // Options used to silently reset the radio to row 1 - the picked
        // scenario was still live one screen away.
        const picked = screens.scenario_options?.scenario?.slug;
        if (picked && chooser.scenarios.some(sc => sc.slug === picked)) {
          chooser.selected = picked;
        }
        screens.choose_scenario = chooser;
        active = "choose_scenario";
      } else if (kind === "goto_pick_cycle") {
        active = "pick_cycle";
      } else if (kind === "scenario_chosen") {
        // Load this one scenario's stage/card data. Kept separate from the
        // loadIndex() fallback above: the whole catalog loaded fine to get
        // here, so a single missing/corrupt scenario file just stays on the
        // chooser rather than derailing the game.
        const slug = result[1];
        try {
          const data = await loadScenario(slug);
          const entry = catalogIndex?.scenarios?.find(s => s.slug === slug) ?? {};
          screens.scenario_options = new ScenarioOptionsScreen(entry, data, iconsCache);
          active = "scenario_options";
        } catch (e) {
          console.error(`quest catalog: loadScenario(${slug}) failed - staying on chooser`, e);
        }
      } else if (kind === "begin_setup") {
        // One picker now: Nightmare is a rung on the difficulty ladder,
        // not a separate Mode.
        const [, difficulty] = result;
        const opts = screens.scenario_options;
        const scn = opts.scenario;
        const scenarioMeta = {
          slug: scn.slug, name: scn.name, pack: scn.pack, cycle: scn.cycle,
          source: scn.source, kind: scn.kind,
          nightmare: difficulty === "Nightmare", mode: difficulty,
          // Precomputed by build_card_data over the sets this scenario actually
          // gathers, so the staging caption can name a real worst case instead
          // of a constant. See stagingRevealEstimate.
          maxCardThreat: scn.maxCardThreat, hasXThreat: scn.hasXThreat,
        };
        game.preloadScenario(scenarioMeta, opts.data?.quest?.stages ?? []);
        game.view = "quest_setup";
        active = "play";
        saveState(game);
            } else if (kind === "save_quit") {
        saveState(game);
        saveReplay(game);
        const [, meta] = loadSaved();
        screens.boot = new BootScreen(meta, bootImg);
        navStack = [];
        active = "boot";
      } else if (kind === "end_game") {
        clearState();
        clearReplay();
        game = new GameState();
        game.clock = clock;
        screens.boot = new BootScreen(null, bootImg);
        navStack = [];
        active = "boot";
      }
    } else if (result) {
      commitAction();
    }
  }

  let lastTapT = 0;
  canvas.addEventListener("pointerdown", ev => {
    // some environments double-dispatch pointerdown for one click
    const now = performance.now();
    if (now - lastTapT < 50) return;
    lastTapT = now;
    const r = canvas.getBoundingClientRect();
    const x = (ev.clientX - r.left) * (480 / r.width);
    const y = (ev.clientY - r.top) * (480 / r.height);
    handleTap(x, y);
  });

  setInterval(() => {
    // reminder + action-window notifications on view change
    if (game.view !== prevView) {
      prevView = game.view;
      // No "Action Window" toast: it fired twice per window (the phase view
      // and its window view share a step) and announced a screen that says so
      // itself. See main.py.
      const msgs = game.dueNotifications().map(([ic, t]) => [ic, t, "amber"]);
      if (msgs.length) {
        screens.play.notif = msgs;
        screens.play.notifFrac = 1.0;
        notifT = NOTIF_TICKS;
        dirty = true;
      }
    }
    // a requested toast (e.g. quest-resolution outcome) overrides view notifs
    if (screens.play.toast) {
      screens.play.notif = screens.play.toast;
      screens.play.notifFrac = 1.0;
      notifT = NOTIF_TICKS;
      screens.play.toast = null;
      dirty = true;
    }
    if (notifT > 0) {
      notifT -= 1;
      const play = screens.play;
      if (!play.notif) notifT = 0;
      else if (notifT === 0) { play.notif = null; dirty = true; }
      else if (notifT % 10 === 0 && !dirty && !modal && active === "play" && play.notifPie) {
        play.notifFrac = notifT / NOTIF_TICKS;
        const [cx, cy, r] = play.notifPie;
        import("./screens.js").then(m => m.drawNotifPie(ctx, cx, cy, r, play.notifFrac, play.notifEdge));
      }
    }
    // elimination confirmation
    if (!modal && !PREGAME_ACTIVE.includes(active) && game.pending_elim !== null) {
      modal = new EliminationModal(game, game.pending_elim);
      dirty = true;
    }
    // Progress-detail quest-row tap (second QuestCardModal entry point): the
    // router replaces one modal at a time, so QuestingProgressModal.onButton
    // closed itself and flagged this instead of returning a modal transition
    // directly - open the card modal now that modal is null.
    if (!modal && active === "play" && game.pending_quest_card) {
      game.pending_quest_card = false;
      // tipsCache may still be cold if this session never visited the
      // picker (e.g. a resumed game) - fetch once, same cache-or-fetch
      // idiom as the side-quest-pick block below, then open the modal.
      modalPending += 1;
      (tipsCache ? Promise.resolve(tipsCache) : loadTips()).then(tips => {
        tipsCache = tips;
        modal = new QuestCardModal(game, tips);
        modalPending -= 1;
        dirty = true;
      });
    }
    // The Progress modal's Location row: open the location's detail sheet.
    // Reopening Progress afterwards is what pending_progress_detail already
    // does for the location picker, so the player lands back where they
    // tapped rather than on the play screen. No catalog fetch needed - the
    // record already carries everything the sheet shows.
    if (!modal && active === "play" && game.pending_location_detail) {
      game.pending_location_detail = false;
      game.pending_progress_detail = true;
      modal = new LocationConfigModal(game);
      dirty = true;
    }
    // Manual progress-edit overflow (QuestingProgressModal close, or the
    // quest row's "Advance" icon): same pending-flag pattern as
    // pending_quest_card above - the modal that detected it had to close
    // first (router holds one modal at a time). No fetch needed here,
    // unlike pending_quest_card above - this path never reads the catalog,
    // since game.stages is already loaded on the model.
    if (!modal && active === "play" && game.pending_resolution) {
      const forced = game.pending_resolution === "forced";
      game.pending_resolution = false;
      modal = new ResolutionModal(game, forced);
      dirty = true;
    }
    // A side-quest ROW's ">" - the sheet with Done and Remove on it, which is
    // a different modal from the add picker below. Neither twin constructed
    // SideQuestsModal at all before this. No fetch: the record already carries
    // everything the sheet shows.
    if (!modal && active === "play" && game.pending_side_quest_detail) {
      game.pending_side_quest_detail = false;
      modal = new SideQuestsModal(game);
      dirty = true;
    }
    // Progress-detail "+ Side quest" tap (SideQuestPickModal entry point):
    // same pending-flag pattern as pending_quest_card above - the picker
    // needs a catalog fetch, which QuestingProgressModal.onButton can't
    // await mid-tap without breaking the modal-replaces-modal invariant, so
    // it flags this instead and the fetch happens here, once modal is null.
    //
    // pending_side_quest_pick is cleared synchronously so a later tick can't
    // re-enter this block while the fetch is in flight. A missing/
    // unreadable catalog (loadPlayerSideQuests() resolves []) skips the
    // picker and keeps today's direct-append behavior instead of showing an
    // empty list.
    if (!modal && active === "play" && game.pending_side_quest_pick) {
      game.pending_side_quest_pick = false;
      modalPending += 1;
      loadPlayerSideQuests().then(entries => {
        if (entries.length) {
          modal = new SideQuestPickModal(game, entries);
        } else {
          const snap = game.beginAction();
          game.side_quests.push({ points: 4, progress: 0 });
          game.logEvent(`Side quest ${game.side_quests.length} added (progress view)`);
          game.addDelta(snap);
          saveState(game);
          saveReplay(game);
        }
        modalPending -= 1;
        dirty = true;
      });
    }
    // Travel, or the Progress modal's "+ Add location" (LocationPickModal
    // entry points): same pending-flag pattern as pending_side_quest_pick
    // above - the picker needs the scenario's gather-list union fetched from
    // the catalog, which neither ScreenPlay.onButton nor a modal's can await
    // mid-tap. pending_location_pick is cleared synchronously so a later tick
    // can't re-enter this block while the fetch is in flight, and the result
    // is cached for the whole game. An empty list (manual game, data/ not
    // built, a quest that gathers no locations) is NOT a fallback here - the
    // modal itself opens straight on its manual stepper, exactly today's
    // behavior.
    if (!modal && active === "play" && game.pending_location_pick) {
      const req = game.pending_location_pick;
      game.pending_location_pick = null;
      modalPending += 1;
      (locationsCache
        ? Promise.resolve(locationsCache)
        : loadLocations(game.scenario?.slug)).then(entries => {
        locationsCache = entries;
        // `idx` says WHICH seat a "change" replaces - the location sheet's
        // "Replaced" passes its own. Dropping it here sent every replacement
        // to seat 0.
        modal = new LocationPickModal(game, req.mode ?? "new", entries,
                                      req.back ?? "play", req.idx ?? 0);
        modalPending -= 1;
        dirty = true;
      });
    }
    // Coming back from the side-quest picker or the location picker: reopen
    // the Progress modal you tapped "+ Side quest" / "+ Add location" from,
    // rather than dropping you on the play screen. Same pending-flag pattern
    // as the one above.
    if (!modal && active === "play" && game.pending_progress_detail) {
      game.pending_progress_detail = false;
      modal = new QuestingProgressModal(game);
      dirty = true;
    }
    // defeat: every player eliminated
    if (!modal && active === "play" && game.pending_elim === null &&
        !game.game_over && game.players.length && game.allEliminated()) {
      const snap = game.beginAction();
      game.setGameOver("defeat");
      game.addDelta(snap);
      saveState(game);
      saveReplay(game);
      dirty = true;
    }
    // game-over screen takes over the play surface
    if (!modal && active === "play" && game.game_over) {
      active = "gameover";
      navStack = [];
      dirty = true;
    }
    // torch flicker
    if (prefs.scene === "torch" && !PREGAME_ACTIVE.includes(active)) {
      if (tick % 10 === 0) updateLeds(game, prefs, tick);
    }
    tick += 1;
    // Hold the last frame while an async modal handoff is in flight, rather
    // than flashing the screen underneath it. dirty stays set, so the redraw
    // happens as soon as the replacement modal exists.
    if (dirty && !(modalPending && !modal)) { draw(); dirty = false; }
  }, 20);

  draw();
}

main();
