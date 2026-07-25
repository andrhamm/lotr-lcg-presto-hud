// Port of main.py — boot flow, nav stack, modal loop, notifications,
// persistence (localStorage instead of flash), virtual LED strip.
import { pal, bevel, rect } from "./ui.js";
import { GameState, VIEW_LABELS, viewForStep } from "./gamestate.js";
import { step as phaseStep, phase as phaseInfo } from "./phases.js";
import { ScreenPlay } from "./screen_play.js";
import { ScreenPhases, ScreenLog, ScreenSettings, BootScreen, SetupScreen,
         LedModal, ScreenAbout, GameOverScreen, ScenarioSourceScreen,
         PickCycleScreen, ChooseScenarioScreen,
         ScenarioOptionsScreen } from "./screens_other.js";
import { EliminationModal, QuestCardModal, SideQuestPickModal } from "./screens.js";
import { loadIndex, loadScenario, cyclesFor, groupByCycle, loadPlayerSideQuests,
         loadIcons, loadTips } from "./quest_catalog.js";

const STATE_KEY = "lotr-hud-state";
const PREFS_KEY = "lotr-hud-prefs";
const canvas = document.getElementById("screen");
const ctx = canvas.getContext("2d");
const clock = () => Math.floor(performance.now());
// Pre-game screens with no live game to animate: LED/notification/elimination
// per-tick housekeeping (below) is skipped while any of these is active.
const PREGAME_ACTIVE = ["boot", "setup", "scenario_source", "pick_cycle",
                        "choose_scenario", "scenario_options"];

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
    const when = d.saved_at ? new Date(d.saved_at).toLocaleString() : "earlier session";
    return [game, { round: game.round,
                    phase: VIEW_LABELS[game.view] ?? phaseStep(game.step).phase,
                    saved_at: when }];
  } catch { return [null, null]; }
}
function saveState(game) {
  localStorage.setItem(STATE_KEY,
    JSON.stringify({ saved_at: Date.now(), state: game.toDict() }));
}
function clearState() { localStorage.removeItem(STATE_KEY); }
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

  function handleTap(x, y) {
    if (modal) {
      for (const b of modal.buttons) {
        if (b.hit(x, y)) {
          pressFeedback(b);
          setTimeout(() => {
            const result = modal.onButton(b);
            if (result === "close") {
              if (modal instanceof LedModal) savePrefs(prefs);
              else saveState(game);
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
        setTimeout(async () => {
          await handleResult(screens[active].onButton(b, game));
          dirty = true;
        }, 90);
        return;
      }
    }
  }

  // async: a couple of result kinds (choose_scenario, scenario_chosen) fetch
  // catalog data before they can finish routing; handleTap above awaits this.
  async function handleResult(result) {
    if (Array.isArray(result)) {
      const kind = result[0];
      if (kind === "goto") {
        let target = result[1];
        if (target === "close") target = navStack.pop() ?? "play";
        else if (["settings", "log", "phases", "about"].includes(target)) {
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
        if (result[1] === "resume") active = "play";
        else if (result[1] === "about") { navStack.push("boot"); active = "about"; }
        else { screens.setup.hasSave = saveExists(); active = "setup"; }
      } else if (kind === "open_repo") {
        window.open("https://github.com/andrhamm/lotr-lcg-presto-hud", "_blank");
      } else if (kind === "start_game") {
        const [, threats, first] = result;
        clearState();
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
          console.error("quest catalog: loadIndex failed - falling back to custom quest", e);
          game.logEvent("Quest catalog unavailable - continuing with custom/manual setup");
          game.scenario = null;
          game.view = "setup_game";
          active = "play";
          saveState(game);
        }
      } else if (kind === "choose_scenario_list") {
        const [, source, cycle] = result;
        const groups = groupByCycle(catalogIndex?.scenarios ?? [], source);
        const group = groups.find(g => g.cycle === cycle);
        screens.choose_scenario = new ChooseScenarioScreen(source, cycle, group?.scenarios ?? []);
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
        const [, difficulty, mode] = result;
        const opts = screens.scenario_options;
        const scn = opts.scenario;
        const scenarioMeta = {
          slug: scn.slug, name: scn.name, pack: scn.pack, cycle: scn.cycle,
          source: scn.source, kind: scn.kind,
          nightmare: mode === "Nightmare", mode: difficulty,
        };
        game.preloadScenario(scenarioMeta, opts.data?.quest?.stages ?? []);
        game.view = "quest_setup";
        active = "play";
        saveState(game);
      } else if (kind === "start_custom") {
        game.scenario = null;
        game.view = "setup_game";
        active = "play";
      } else if (kind === "save_quit") {
        saveState(game);
        const [, meta] = loadSaved();
        screens.boot = new BootScreen(meta, bootImg);
        navStack = [];
        active = "boot";
      } else if (kind === "end_game") {
        clearState();
        game = new GameState();
        game.clock = clock;
        screens.boot = new BootScreen(null, bootImg);
        navStack = [];
        active = "boot";
      }
    } else if (result) {
      saveState(game);
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
      const msgs = game.dueNotifications().map(([ic, t]) => [ic, t, "amber"]);
      if (game.actionWindowOpen()) msgs.push(["LEADERSHIP", "Action Window", "purple"]);
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
      (tipsCache ? Promise.resolve(tipsCache) : loadTips()).then(tips => {
        tipsCache = tips;
        modal = new QuestCardModal(game, tips);
        dirty = true;
      });
    }
    // Progress-detail "+ Side quest" tap (SideQuestPickModal entry point):
    // same pending-flag pattern as pending_quest_card above - the picker
    // needs a catalog fetch, which QuestingProgressModal.onButton can't
    // await mid-tap without breaking the modal-replaces-modal invariant, so
    // it flags this instead and the fetch happens here, once modal is null.
    // pending_side_quest_pick is cleared synchronously so a later tick can't
    // re-enter this block while the fetch is in flight. A missing/
    // unreadable catalog (loadPlayerSideQuests() resolves []) skips the
    // picker and keeps today's direct-append behavior instead of showing an
    // empty list.
    if (!modal && active === "play" && game.pending_side_quest_pick) {
      game.pending_side_quest_pick = false;
      loadPlayerSideQuests().then(entries => {
        if (entries.length) {
          modal = new SideQuestPickModal(game, entries);
        } else {
          game.side_quests.push({ points: 4, progress: 0 });
          game.logEvent(`Side quest ${game.side_quests.length} added (progress view)`);
          saveState(game);
        }
        dirty = true;
      });
    }
    // defeat: every player eliminated
    if (!modal && active === "play" && game.pending_elim === null &&
        !game.game_over && game.players.length && game.allEliminated()) {
      game.setGameOver("defeat");
      saveState(game);
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
    if (dirty) { draw(); dirty = false; }
  }, 20);

  draw();
}

main();
