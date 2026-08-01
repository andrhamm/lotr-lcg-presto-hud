// Port of db.py — the ONLY place the web twin touches storage.
//
// Same three collections, same caching policy, same error contract. The
// backing store differs and cannot be papered over: LittleFS appends natively,
// localStorage has no append at all (setItem rewrites the whole value, and
// throws QuotaExceededError past ~5 MB). That asymmetry is exactly why the
// client is a facade rather than a shared "Store" interface — the firmware
// frames length-prefixed binary records into files, this keeps one array per
// key, and both feed the identical foldLog/foldReplay.
import { foldLog, foldReplay } from "./gamestate.js";
import { loadIndex, loadScenario, loadIcons, loadTips, loadLocations,
         loadPlayerSideQuests } from "./quest_catalog.js";

export const STATE_KEY = "lotr-hud-state";
export const PREFS_KEY = "lotr-hud-prefs";
export const LOG_KEY = "lotr-hud-log";
export const REPLAY_KEY = "lotr-hud-replay";                 // legacy
export const REPLAY_JOURNAL_KEY = "lotr-hud-replay-journal";
export const HISTORY_KEY = "lotr-hud-history";
export const ROLLUP_KEY = "lotr-hud-stats";

const DEFAULT_PREFS = { brightness: 100, scene: "phase" };

function readArray(key) {
  try {
    const v = JSON.parse(localStorage.getItem(key));
    return Array.isArray(v) ? v : [];
  } catch { return []; }
}

function appendAll(key, recs) {
  if (!recs || !recs.length) return;
  try {
    localStorage.setItem(key, JSON.stringify(readArray(key).concat(recs)));
  } catch { /* history is expendable; the game is not */ }
}

export class Session {
  // **Gameplay touches RAM only; storage happens in the background.**
  //
  // A tap calls record(), which appends to an in-memory queue and returns.
  // tick() drains it, and main.js calls tick() only on frames with nothing to
  // draw, so durable work never lands on a frame the player is waiting for.
  // One bounded unit per call, so no single idle frame can stall.
  //
  // The firmware has no threads (Pimoroni disables MICROPY_PY_THREAD for the
  // Presto), so there the idle path IS the background. The browser could use a
  // Worker, but the same queue keeps the two twins reading identically - and
  // the work is small enough that it does not need one.
  constructor() {
    this._queue = [];
    this._owner = null;      // the game the queue describes
    this._stateDirty = false;
    this._idle = 0;          // consecutive ticks with nothing queued
  }

  // Called on EVERY tap. RAM only - never touches storage.
  record(game) {
    if (this._owner !== game) { this._queue = []; this._owner = game; }
    for (const r of game.takeLogAppends()) this._queue.push(["l", r]);
    for (const r of game.takeReplayAppends()) this._queue.push(["r", r]);
    this._stateDirty = true;
    this._idle = 0;          // the player is active again
  }

  // One bounded unit of durable work. Idle frames only. Journal first, state
  // last: the journal is what makes the state reconstructable, and it is cheap.
  tick(game) {
    if (this._owner !== game) return false;
    if (this._queue.length) {
      const batch = this._queue.splice(0, Session.BATCH);
      appendAll(LOG_KEY, batch.filter(([k]) => k === "l").map(([, r]) => r));
      appendAll(REPLAY_JOURNAL_KEY, batch.filter(([k]) => k === "r").map(([, r]) => r));
      this._idle = 0;
      return true;
    }
    if (this._stateDirty) {
      // Wait for a real pause before paying for the checkpoint - on device it
      // is the one expensive operation (~89 ms). Nothing is at risk meanwhile:
      // the journal is already durable and is what reconstructs the state.
      this._idle += 1;
      if (this._idle < Session.IDLE_BEFORE_STATE) return false;
      this.saveState(game);
      this._stateDirty = false;
      this._idle = 0;
      return true;
    }
    return false;
  }

  // Checkpoint now, skipping the idle wait. For flush points.
  forceState(game) {
    if (this._owner === game && this._stateDirty) {
      this.saveState(game);
      this._stateDirty = false;
    }
  }

  // Drain everything - save-and-quit, game over, before a `game` rebind.
  // A flush IS the pause tick() is waiting for, so take the checkpoint now.
  flush(game) { let n = 0; while (this.tick(game) && n < 10000) n += 1; this.forceState(game); }

  pending() { return this._queue.length; }

  saveState(game) {
    try {
      localStorage.setItem(STATE_KEY,
        JSON.stringify({ saved_at: Date.now(), state: game.toDict() }));
    } catch { /* quota */ }
  }

  saveLog(game) { appendAll(LOG_KEY, game.takeLogAppends()); }

  saveReplay(game) { appendAll(REPLAY_JOURNAL_KEY, game.takeReplayAppends()); }

  // What a tap does: queue, and return. The work happens in tick().
  commit(game) { this.record(game); }

  loadState() {
    try { return JSON.parse(localStorage.getItem(STATE_KEY)); }
    catch { return null; }
  }

  loadLog(game) {
    const recs = readArray(LOG_KEY);
    if (!recs.length) return;
    game.log = foldLog(recs);
    game._seq = Math.max(game._seq, ...game.log.map(e => e.seq ?? 0));
  }

  // Prefer the journal; fall back to the pre-journal store and seed it so the
  // next tap appends rather than rewriting.
  loadReplay(game) {
    const ops = readArray(REPLAY_JOURNAL_KEY);
    if (ops.length) {
      const [deltas, step] = foldReplay(ops);
      game.replayFromDict({ deltas, replay_step: step });
      return;
    }
    try {
      game.replayFromDict(JSON.parse(localStorage.getItem(REPLAY_KEY)));
      if (game.deltas.length) {
        localStorage.setItem(REPLAY_JOURNAL_KEY,
                             JSON.stringify(game.seedReplayJournal()));
      }
    } catch { game.replayFromDict(null); }
  }

  exists() { return localStorage.getItem(STATE_KEY) !== null; }

  clear() {
    for (const k of [STATE_KEY, LOG_KEY, REPLAY_KEY, REPLAY_JOURNAL_KEY]) {
      localStorage.removeItem(k);
    }
  }
}
Session.BATCH = 16;              // journal records drained per tick
Session.IDLE_BEFORE_STATE = 3;   // quiet ticks before the state checkpoint

export class History {
  append(record) { appendAll(HISTORY_KEY, [record]); this._bumpRollup(record); }

  scan() { return readArray(HISTORY_KEY); }

  rollup() {
    try {
      return JSON.parse(localStorage.getItem(ROLLUP_KEY))
        ?? { games: 0, wins: 0, rounds: 0, by_scenario: {}, best: null };
    } catch {
      return { games: 0, wins: 0, rounds: 0, by_scenario: {}, best: null };
    }
  }

  // O(1) per finished game: recomputing from a full scan is what makes a stats
  // screen unusable once the history is large.
  _bumpRollup(rec) {
    const r = this.rollup();
    r.games = (r.games ?? 0) + 1;
    if (rec.won) r.wins = (r.wins ?? 0) + 1;
    r.rounds = (r.rounds ?? 0) + (rec.rounds ?? 0);
    const slug = rec.scn ?? "?";
    r.by_scenario = r.by_scenario ?? {};
    const e = r.by_scenario[slug] ?? { played: 0, won: 0 };
    e.played += 1;
    if (rec.won) e.won += 1;
    r.by_scenario[slug] = e;
    if (rec.won && (r.best === null || (rec.rounds ?? 0) < (r.best.rounds ?? Infinity))) {
      r.best = { scn: slug, rounds: rec.rounds, players: rec.players };
    }
    try { localStorage.setItem(ROLLUP_KEY, JSON.stringify(r)); } catch { /* quota */ }
  }

  clear() {
    localStorage.removeItem(HISTORY_KEY);
    localStorage.removeItem(ROLLUP_KEY);
  }
}

export class DataClient {
  constructor() {
    this._index = null;
    this._icons = null;
    this._tips = null;
    this._sideQuests = null;
    this._bundles = {};
    this.session = new Session();
    this.history = new History();
  }

  // PROPAGATES on failure, deliberately — main.js surfaces it as
  // CatalogUnavailableScreen. The reads below never throw: they are optional
  // at runtime, this one is not.
  async index() {
    if (this._index === null) this._index = await loadIndex();
    return this._index;
  }

  async scenario(slug) {
    const b = this._bundles[slug];
    if (b) return b.scenario;
    return loadScenario(slug);
  }

  // Every static datapoint this scenario needs, in one go, pinned for the
  // game. ~10 KB measured, so after this resolves there is not a single
  // catalog read during play.
  async bundle(slug) {
    const have = this._bundles[slug];
    if (have) return have;
    let scn;
    try { scn = await loadScenario(slug); } catch { return null; }
    const b = {
      scenario: scn,
      stages: scn?.quest?.stages ?? [],
      locations: await loadLocations(slug),
      tips: await this.tips(),
    };
    this._bundles = { [slug]: b };   // one scenario at a time
    return b;
  }

  async locations(slug) {
    const b = this._bundles[slug];
    if (b) return b.locations;
    return loadLocations(slug);
  }

  async sideQuests() {
    if (this._sideQuests === null) this._sideQuests = await loadPlayerSideQuests();
    return this._sideQuests;
  }

  async icons() {
    if (this._icons === null) this._icons = await loadIcons();
    return this._icons;
  }

  async tips() {
    if (this._tips === null) this._tips = await loadTips();
    return this._tips;
  }

  releaseGame() { this._bundles = {}; }

  loadPrefs() {
    try {
      const d = JSON.parse(localStorage.getItem(PREFS_KEY)) ?? {};
      return { brightness: d.brightness ?? 100, scene: d.scene ?? "phase" };
    } catch { return { ...DEFAULT_PREFS }; }
  }

  savePrefs(prefs) {
    try { localStorage.setItem(PREFS_KEY, JSON.stringify(prefs)); }
    catch { /* quota */ }
  }
}
