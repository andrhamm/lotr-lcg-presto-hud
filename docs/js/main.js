// Port of main.py — boot flow, nav stack, modal loop, notifications,
// persistence (localStorage instead of flash), virtual LED strip.
import { pal, bevel, rect } from "./ui.js";
import { GameState, VIEW_LABELS, viewForStep } from "./gamestate.js";
import { step as phaseStep, phase as phaseInfo } from "./phases.js";
import { ScreenPlay } from "./screen_play.js";
import { ScreenPhases, ScreenLog, ScreenSettings, BootScreen, SetupScreen,
         LedModal, ScreenAbout, GameOverScreen } from "./screens_other.js";
import { EliminationModal } from "./screens.js";

const STATE_KEY = "lotr-hud-state";
const PREFS_KEY = "lotr-hud-prefs";
const canvas = document.getElementById("screen");
const ctx = canvas.getContext("2d");
const clock = () => Math.floor(performance.now());

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
  };
  let active = "boot";
  let navStack = [];
  let modal = null;
  let dirty = true;
  let tick = 0;
  let prevView = game.view;
  const NOTIF_TICKS = 200;
  let notifT = 0;

  function draw() {
    if (modal) modal.draw(ctx, game);
    else {
      screens[active].draw(ctx, game);
      if (active !== "boot" && active !== "setup") updateLeds(game, prefs, tick);
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
        setTimeout(() => { handleResult(screens[active].onButton(b, game)); dirty = true; }, 90);
        return;
      }
    }
  }

  function handleResult(result) {
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
    if (!modal && active !== "boot" && active !== "setup" && game.pending_elim !== null) {
      modal = new EliminationModal(game, game.pending_elim);
      dirty = true;
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
    if (prefs.scene === "torch" && active !== "boot" && active !== "setup") {
      if (tick % 10 === 0) updateLeds(game, prefs, tick);
    }
    tick += 1;
    if (dirty) { draw(); dirty = false; }
  }, 20);

  draw();
}

main();
