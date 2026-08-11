// Port of gamestate.py — method-for-method. Keep the two in lockstep:
// web-first changes land here, then mirror into gamestate.py.
import { STEP_ORDER, step as phaseStep } from "./phases.js";
// Copy is GENERATED from viewcopy.py so the twins cannot drift.
import { VIEW_LABELS, SETUP_TIP, OUTCOME } from "./viewcopy.js";
import { autoFor, resolve as resolveX } from "./xtargets.js";
export { VIEW_LABELS, SETUP_TIP };

export const MAX_PLAYERS = 4;
export const DEFAULT_ELIMINATION = 50;
export const DEFAULT_START_THREAT = 25;

// A window view is "aw_" + the view whose step it follows. They are real views
// rather than screen-local state so that undo, save/resume and delta replay
// all work on them for free - snapshot() already carries `view` and `step`.
export const VIEW_ORDER = ["resource", "aw_resource",
  "planning",
  "quest_commit", "aw_quest_commit",
  "quest_staging", "aw_quest_staging",
  "quest_resolution", "aw_quest_resolution",
  "travel", "aw_travel",
  "enc_optional", "aw_enc_optional",
  "enc_checks", "aw_enc_checks",
  "combat_shadow", "combat_enemy", "combat_player",
  "refresh", "aw_refresh",
  "round_end"];

export const WINDOW_PREFIX = "aw_";
export const isWindowView = v => v.startsWith(WINDOW_PREFIX);
export const phaseViewOf = v =>
  isWindowView(v) ? v.slice(WINDOW_PREFIX.length) : v;
// Single predicate so the frequency policy is one function. Every window is
// always in the flow; "once per game" or "off" would be a change here alone.
export const windowAfter = v =>
  (WINDOW_PREFIX + v) in VIEW_STEP ? WINDOW_PREFIX + v : null;

// NOT the same as isWindowView. The aw_ screens are the interstitial windows,
// but Combat's two windows ARE its phase views: phases.js marks 6.E (enemy
// attacks) and 6.P (player attacks) as action windows and neither has an aw_
// screen. Asking the naming convention instead of the turn sequence would miss
// both - exactly the windows a combat skip passes over.
export const isActionWindow = v => {
  const st = VIEW_STEP[v];
  return !!(st && phaseStep(st).action_window);
};

// The whole safety rule for skipping. An action window is a player's
// opportunity to act, and a phase-locked ability can ONLY be initiated during
// a window of its own phase (RR). Jumping past the final window of a phase
// silently removes an opportunity someone may have been holding a card for,
// and the compiled catalog says that is not hypothetical: 34 distinct cards
// print "Combat Action:", 35 "Planning Action:", 32 "Quest Action:".
//
// So a skip never lands on its nominal destination. It lands here.
export function lastWindowBefore(target) {
  const i = VIEW_ORDER.indexOf(target);
  if (i < 0) return null;
  for (let j = i - 1; j >= 0; j--) {
    if (isActionWindow(VIEW_ORDER[j])) return VIEW_ORDER[j];
  }
  return null;
}

// Contextual skips. Each is something the PLAYER asserts about the table, not
// something the app infers: nothing here tracks enemies, and a tracker that
// guessed would eventually guess wrong in the direction of skipping a phase
// that mattered.
//
// `to` is the nominal destination; the skip lands on lastWindowBefore(to).
export const SKIPS = [
  {
    id: "combat_empty",
    // Offered ONLY from the encounter window, never from enc_checks itself:
    // from the phase view this would jump the player over aw_enc_checks, the
    // encounter phase's OWN window, which they have not had yet. A skip may
    // pass windows on the way to its landing; it must never eat the window of
    // the phase the player is standing in.
    from: ["aw_enc_checks"],
    to: "refresh",
    label: "No enemies. Skip combat.",
    claim: "No enemies are engaged and none are in staging.",
  },
];

export const skipsFrom = view => SKIPS.filter(s => s.from.includes(view));

export const VIEW_STEP = {
  quest_setup: "0.0", resource: "1.R", planning: "2.P", quest_sailing: "3.1",
  quest_commit: "3.2",
  quest_staging: "3.3", quest_resolution: "3.4", travel: "4.2",
  enc_optional: "5.2", enc_checks: "5.3", combat_shadow: "6.2",
  combat_enemy: "6.E", combat_player: "6.P", refresh: "7.R",
};
// Window views share the step they follow: the window IS that step's window.
VIEW_STEP["round_end"] = "0.1";
for (const pv of ["resource", "quest_commit", "quest_staging",
                  "quest_resolution", "travel", "enc_optional",
                  "enc_checks", "refresh"]) {
  VIEW_STEP["aw_" + pv] = VIEW_STEP[pv];
}



const PHASE_VIEW = {
  Beginning: "resource", Resource: "resource",
  Planning: "planning", Quest: "quest_commit", Travel: "travel",
  Encounter: "enc_optional", Combat: "combat_shadow", Refresh: "refresh",
  End: "refresh",
};
// Built from PHASE views only. A blanket inversion is last-wins, so the
// window views would capture their shared step and a phases-screen jump to
// 3.3 would land on the window instead of Staging.
const STEP_VIEW = {};
for (const [v, s] of Object.entries(VIEW_STEP)) if (!isWindowView(v)) STEP_VIEW[s] = v;
STEP_VIEW["5.3"] = "enc_checks";
STEP_VIEW["5.4"] = "enc_checks";
STEP_VIEW["6.11"] = "combat_player";
STEP_VIEW["0.0"] = "resource";

export function viewForStep(stepId) {
  if (stepId in STEP_VIEW) return STEP_VIEW[stepId];
  return PHASE_VIEW[phaseStep(stepId).phase];
}

export function fmtMs(ms) {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}m${String(s % 60).padStart(2, "0")}s`;
}


// Heading card facings, best -> worst (Grey Havens rulebook p.5). Only
// the sun facing is "on-course"; the rest are "off-course". Facing names
// are the official ones card text uses: "off-course (Cloudy, Rainy, or
// Stormy)". [term, icon, facing name, degree phrase]
export const HEADINGS = [
  ["On-course", "SUN", "Sunny", "best possible setting"],
  ["Off-course", "CLOUD", "Cloudy", "1 step off-course"],
  ["Off-course", "RAIN", "Rainy", "2 steps off-course"],
  ["Off-course", "STORM", "Stormy", "worst possible setting"],
];


// ---------------------------------------------------------------------------
// Delta replay engine.
//
// Ported at parity from DragnCards (seastan/DragnCards @ a79716f9),
// backend/lib/dragncards_game/ui/game_ui.ex: get_delta/2, delta/2,
// apply_delta/3, apply_delta_list/3. See
// docs/superpowers/plans/2026-07-26-delta-replay-parity.md for the four
// deliberate divergences.
//
// A delta mirrors the shape of the state it describes. Every changed leaf is a
// two-element [old, new] pair, which is what lets ONE apply function serve both
// directions: index 0 undoes, index 1 redoes.
// ---------------------------------------------------------------------------

export const REMOVED = ":removed";   // sentinel: key absent on this side
export const MAX_SAVED_DELTAS = 500; // ~47 KB, ~31 rounds. The reference caps
                                     // at 5 for non-supporters
                                     // (game.ex trim_saved_deltas/2); we have
                                     // no paywall, just a bound.

// Rebuild (deltas, replay_step) from the append-only replay journal. The two
// operations that are NOT appends are recorded as tombstones and replayed
// here: {op:"t",to} an undo-truncation, {op:"x",n} a MAX_SAVED_DELTAS front
// trim, {op:"s",i} a cursor move. Mirror of gamestate.py's fold_replay.
export function foldReplay(ops) {
  let deltas = [];
  let step = -1;
  for (const o of ops) {
    if (o.op === "d") { deltas.push(o.d); step = deltas.length - 1; }
    else if (o.op === "t") {
      deltas = deltas.slice(0, o.to ?? 0);
      if (step > deltas.length - 1) step = deltas.length - 1;
    } else if (o.op === "x") { deltas = deltas.slice(o.n ?? 0); step -= (o.n ?? 0); }
    else if (o.op === "s") { step = o.i ?? -1; }
  }
  if (step < -1) step = -1;
  if (step > deltas.length - 1) step = deltas.length - 1;
  return [deltas, step];
}

// Rebuild `game.log` from the append-only log store.
//
// The store records log EVENTS, not final rows, because logEvent is not purely
// append: a keyed tally rewrites its own row in place so a run of eight stepper
// taps stays one line. Replaying has to apply the identical rule - a record
// whose (key, round, step) matches the last retained row REPLACES it - or the
// same run comes back as eight rows. Mirror of gamestate.py's fold_log; kept
// beside logEvent because the two rules must agree.
export function foldLog(records) {
  const out = [];
  for (const r of records) {
    const prev = out.length ? out[out.length - 1] : null;
    if (r.key !== undefined && r.key !== null && prev
        && prev.key === r.key && prev.round === r.round && prev.step === r.step) {
      out[out.length - 1] = { ...r };
    } else {
      out.push({ ...r });
    }
  }
  return out;
}

function isMap(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function deepEqual(a, b) {
  if (a === b) return true;
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((x, i) => deepEqual(x, b[i]));
  }
  if (isMap(a) && isMap(b)) {
    const ka = Object.keys(a), kb = Object.keys(b);
    return ka.length === kb.length && ka.every(k => k in b && deepEqual(a[k], b[k]));
  }
  return false;
}

// Recursion happens only when BOTH sides are maps. Elixir's map_diff has the
// same guard (`when is_map(vala) and is_map(valb)`), so a list is an atomic
// primitive and changes wholesale - which is why snapshot() keys its
// collections instead of listing them, exactly as the reference models
// everything as groupById/cardById/stackById.
// -- phase-relative rebasing -----------------------------------------------
//
// The rule, from the original TODO card: "all stat changes / events are
// recorded for the given phase. if you click the back button and make a
// change, the 'final' values for that page are adjusted, the next page always
// bases stat changes relative to the final values from the previous phase."
//
// So a phase owns the AMOUNT it changed each stat by, not the value it left
// behind. Separate from getDelta/applyDelta on purpose - those are the
// DragnCards replay port and are ABSOLUTE by design, because undo means "put
// it back exactly as it was", the opposite of rebasing.
export const PHASE_NAV_KEYS = ["view", "step", "round"];

// Structural diff where numbers carry HOW MUCH they moved. Leaves are
// ["+", amount] for numbers and ["=", value] for everything else - a bool, a
// string or a null has no meaningful "+".
export function relDelta(old, cur) {
  if (JSON.stringify(old) === JSON.stringify(cur)) return null;
  const bothObj = old && cur && typeof old === "object" && typeof cur === "object" &&
                  !Array.isArray(old) && !Array.isArray(cur);
  if (bothObj) {
    const out = {};
    for (const k of Object.keys(cur)) {
      if (!(k in old)) { out[k] = ["=", cur[k]]; continue; }
      const d = relDelta(old[k], cur[k]);
      if (d !== null) out[k] = d;
    }
    for (const k of Object.keys(old)) if (!(k in cur)) out[k] = ["x", null];
    return Object.keys(out).length ? out : null;
  }
  if (typeof old === "boolean" || typeof cur === "boolean") return ["=", cur];
  if (typeof old === "number" && typeof cur === "number") return ["+", cur - old];
  return ["=", cur];
}

// Replay a relDelta onto `state` in place; returns state.
export function applyRel(state, rel) {
  if (!state || !rel || typeof state !== "object" || typeof rel !== "object") return state;
  for (const [k, v] of Object.entries(rel)) {
    if (!Array.isArray(v)) {
      if (state[k] && typeof state[k] === "object") applyRel(state[k], v);
      continue;
    }
    const [op, val] = v;
    if (op === "x") delete state[k];
    else if (op === "+") {
      const base = typeof state[k] === "number" ? state[k] : 0;
      state[k] = base + val;
    } else state[k] = val;
  }
  return state;
}

export function getDelta(old, cur) {
  if (deepEqual(old, cur)) return null;
  if (isMap(old) && isMap(cur)) {
    const out = {};
    for (const k of Object.keys(old)) {
      if (!(k in cur)) out[k] = [old[k], REMOVED];
      else {
        const d = getDelta(old[k], cur[k]);
        if (d !== null) out[k] = d;
      }
    }
    for (const k of Object.keys(cur)) {
      if (!(k in old)) out[k] = [REMOVED, cur[k]];
    }
    return Object.keys(out).length ? out : null;
  }
  return [old, cur];
}

// direction "undo" takes each pair's index 0, "redo" its index 1. A chosen
// value of REMOVED deletes the key. Mirrors the reference's
// `if is_map(map) and is_map(delta)` guard by returning state untouched when
// either side is not a map.
export function applyDelta(state, delta, direction) {
  if (!isMap(state) || !isMap(delta)) return state;
  const idx = direction === "undo" ? 0 : 1;
  for (const [k, v] of Object.entries(delta)) {
    if (k === "_delta_metadata") continue;
    if (isMap(v)) applyDelta(state[k], v, direction);
    else {
      const val = v[idx];
      if (val === REMOVED) delete state[k];
      else state[k] = val;
    }
  }
  return state;
}

export function applyDeltaList(state, deltaList, direction) {
  for (const d of deltaList) applyDelta(state, d, direction);
  return state;
}

export class Player {
  constructor(label, startingThreat = 0) {
    this.label = label;
    this.threat = startingThreat;
    this.starting_threat = startingThreat;
    this.threat_per_round = 1;
    this.eliminated = false;
    this.elimination = DEFAULT_ELIMINATION;
    this.commit = 0;
  }
}

export class GameState {
  // Fallback only, for a game with no catalog scenario loaded (manual setup, or
  // a save from before maxCardThreat was emitted). The real number comes from
  // the scenario itself - see stagingRevealEstimate.
  static STAGING_HIGH_PER_PLAYER = 3;

  constructor(playerCount = 4, startingThreat = 0,
              eliminationThreat = DEFAULT_ELIMINATION) {
    this.elimination_threat = eliminationThreat;
    this.players = [];
    for (let i = 0; i < playerCount; i++) {
      const p = new Player(`P${i + 1}`, startingThreat);
      p.elimination = eliminationThreat;
      this.players.push(p);
    }
    // The one-time setup phase precedes round 1. Always the CATALOG one:
    // there is no manual/custom quest mode. The game is out of print, so the
    // card data can be complete, and an escape hatch that let a player
    // hand-enter quest points was a second, worse source of truth.
    this.view = "quest_setup";
    this.clock = null;
    this._round_snap = null;
    this.round = 1;
    this.first_player = 0;
    this.step = STEP_ORDER[0];
    this.quest = { stage_n: 1, side: "A", points: 0, progress: 0 };
    this.scenario = null;        // preloaded quest-picker scenario metadata
    this.stages = [];            // preloaded quest stage/card data
    this.stage_idx = 0;          // index into this.stages
    this.card_idx = 0;           // index into stages[stage_idx].cards
    // A LIST, and the default is still one. Rules Reference, "Active
    // Location": "There can only be one active location at a time", and "The
    // players cannot travel if another location card is active." FIVE printed
    // cards override that in their own text (Fisherman's Dock, The Gates of
    // Moria, Ruined Tower, Dark Passages, ALeP's Widfast), which is why the
    // state has to hold two. Order is load-bearing: progress fills them in
    // list order before it reaches the quest card.
    this.active_locations = [];
    this.side_quests = [];       // {points, progress, name?} - name is optional
                                  // (absent/null on old saves)
    this.willpower = 0;          // questing total; normally the sum of the
                                 // per-player commits
    // True once the TOTAL has been set directly to something the per-player
    // commits do not add up to. There are two ways into this number - the
    // player widgets and the Questing For stepper - and they must never
    // quietly disagree: while this is set the pills show "?" instead of a
    // breakdown that is no longer true, and opening the players view adopts
    // the breakdown again (see resyncWillpower).
    this.willpower_detached = false;
    this.staging = 0;
    this.pending_budget = 0;
    this.pending_elim = null;
    this.pending_quest_card = false;   // Progress-detail quest-row tap wants
                                        // QuestCardModal opened once the
                                        // Progress-detail modal has closed
                                        // (router replaces one modal at a
                                        // time - see main.js's setInterval)
    this.pending_side_quest_pick = false;  // Progress-detail "+ Side quest"
    // Set by SideQuestPickModal on the way out so the router reopens the
    // Progress modal you tapped "+ Side quest" from, instead of dropping you
    // back on the play screen. Same pending-flag pattern.
    this.pending_progress_detail = false;
    // Set by the Progress modal's location row. A modal cannot open another
    // modal, so the router (main.js) opens LocationConfigModal on the next
    // tick, exactly like pending_location_pick.
    this.pending_location_detail = false;
    // Progress screen's "History" button: the log is a screen, not a modal, so
    // the router does the nav once the modal has closed.
    this.pending_progress_history = false;
    // Progress row ">" on the quest: opens QuestConfigModal (the editor),
    // which links on to the read-only card.
    this.pending_quest_config = false;
    // Progress row ">" on a SIDE QUEST: opens SideQuestsModal, where Done and
    // Remove live. Distinct from pending_side_quest_pick, which opens the ADD
    // picker - the row's chevron used to raise that one, so a row could never
    // reach its own done/remove.
    this.pending_side_quest_detail = false;
                                        // tap wants SideQuestPickModal opened
                                        // once the Progress-detail modal has
                                        // closed (same pending-flag pattern
                                        // as pending_quest_card above)
    // Travel / "+ Add location" wants LocationPickModal opened once the
    // current screen or modal has let go. null, or
    // {mode: "new"|"change", back: "play"|"progress"} - the picker needs a
    // catalog fetch (the gather-list union, see loadLocations) that neither a
    // screen's onButton nor a modal's can await mid-tap, and `back` is how it
    // knows whether to return you to the play screen or reopen the Progress
    // modal.
    this.pending_location_pick = null;
    this.quest_resolved = false;
    this.quest_outcome = null;      // "success" | "fail" | "tie" - last resolution
    this.quest_outcome_n = 0;       // progress gained / threat taken
    this.quest_history = [];        // by-round chart data, capped at last 20
    // Phase-relative rebasing, round-scoped. _phase_bases[view] is the state
    // as that view was ENTERED; _phase_deltas[view] is how much it moved
    // things by the time it was left. See relDelta above.
    this._phase_bases = {};
    this._phase_deltas = {};
    this.sailed_this_round = false;  // the winds have shifted for this one
    this.sailing = false;
    this.heading = 0;
    this.game_over = null;
    this.pending_stage = null;
    this.pending_resolution = false;  // false | "auto" | "forced" - catalog
                                       // game wants ResolutionModal opened
                                       // once the current modal has closed
                                       // (same pending-flag pattern as
                                       // pending_quest_card above)
    this.log = [];
    this._seq = 0;
    // -- delta replay (parity: DragnCards gameui["deltas"]/["replayStep"])
    this.deltas = [];        // oldest-first; getDelta output + _delta_metadata
    this.replay_step = -1;   // cursor INTO deltas, not a stack pointer:
                             // -1 = before the first delta, and deltas are
                             // never popped
    // The log ENTRIES produced by the current action. Replaces a
    // log.slice(-n) that assumed every entry of an action sits at the
    // tail - false the moment logEvent coalesces into an earlier row.
    this._action_entries = [];
    // Log rows created OR rewritten by the current action, drained by
    // takeLogAppends() at the commit point. The log lives in its own
    // append-only store rather than inside the save: it was 96% of
    // state.json and was rewritten in full on every tap.
    this._log_appends = [];
    // Replay-journal ops produced by the current action, drained at the
    // commit point. The replay store used to be a whole-file rewrite of every
    // delta on every tap - 42 KB and 875 ms by round 10 on the device - so it
    // is append-only now, and undo/compaction are recorded as tombstones
    // rather than by rewriting history. See foldReplay.
    this._replay_appends = [];
    this._last_phase_logged = null;
    this.messages = [];      // this action's log text, drained into the delta.
                             // Mirrors game["messages"].
    this._replay_moved = false;  // a cursor move happened inside the current
                                 // recording window - see addDelta
  }

  _now() { return this.clock ? this.clock() : null; }

  // `cat` classifies the entry so the Log screen can filter it:
  //   "move"  something happened in the game. The DEFAULT, deliberately -
  //           anything a caller forgets to tag stays visible.
  //   "phase" a phase transition. Identical every round, carries no game
  //           state, and the R<round>.<step> column already says it.
  //   "tally" a number being dialled in on a stepper.
  //
  // `key` coalesces a tally. A run of taps on one stepper is ONE decision, not
  // eight: committing 8 willpower used to write eight rows, and setting staging
  // to 7 wrote five more. With a key, a repeat within the same (round, step)
  // rewrites its own row in place instead of appending.
  //
  // Bounded by (key, round, step) on purpose, and broken by any intervening
  // entry - re-opening a stepper later starts a NEW row, so *when* each change
  // happened stays visible, which is the point of a log.
  logEvent(text, cat = "move", key = null) {
    const prev = this.log.length ? this.log[this.log.length - 1] : null;
    if (key !== null && prev && prev.key === key
        && prev.round === this.round && prev.step === this.step) {
      this._seq += 1;
      prev.seq = this._seq;
      prev.text = text;
      prev.t = this._now();
      if (this.messages.length) this.messages[this.messages.length - 1] = text;
      else this.messages.push(text);
      this._log_appends.push(prev);
      return prev;
    }
    this._seq += 1;
    const entry = { seq: this._seq, round: this.round, step: this.step,
                    text, t: this._now(), cat };
    if (key !== null) entry.key = key;
    this.log.push(entry);
    this.messages.push(text);
    this._action_entries.push(entry);
    this._log_appends.push(entry);
    return entry;
  }

  // Rows this action created or rewrote, then clear. Call AFTER addDelta,
  // which stamps `delta_i` onto the new rows.
  takeLogAppends() {
    const out = this._log_appends;
    this._log_appends = [];
    return out;
  }

  adjustThreat(index, delta) {
    const p = this.players[index];
    const was = p.eliminated;
    p.threat = Math.max(0, p.threat + delta);
    p.eliminated = p.threat >= p.elimination;
    if (p.eliminated && !was) this.pending_elim = index;
    return p.threat;
  }

  avertElimination(index) {
    const p = this.players[index];
    p.threat = Math.max(0, p.elimination - 5);
    p.eliminated = false;
    if (this.pending_elim === index) this.pending_elim = null;
    this.logEvent(`P${index + 1} avoided elimination (card effect) - threat set to ${p.threat}`);
  }

  // Worst printed threat on ONE revealed card, times the living players.
  //
  // This was `living * STAGING_HIGH_PER_PLAYER` with the constant pinned at 3,
  // so it showed the same "+3" for every scenario ever published - a constant
  // wearing the costume of a calculation, and wrong for The Oath, whose Spider
  // Den prints 4. build_card_data.py now answers the question per scenario at
  // build time, across the sets the scenario actually gathers, and stamps it on
  // the index entry preloadScenario stores as this.scenario.
  stagingRevealEstimate() {
    const living = this.players.filter(p => !p.eliminated).length;
    const worst = (this.scenario ?? {}).maxCardThreat;
    return living * (worst ? worst : GameState.STAGING_HIGH_PER_PLAYER);
  }

  // True when the pool holds a card whose printed threat is a literal X. Then
  // the estimate is a floor, not a ceiling, and the caption has to say so
  // rather than quote a number it knows can be exceeded.
  stagingEstimateIsFloor() {
    return Boolean((this.scenario ?? {}).hasXThreat);
  }

  setCommit(index, value) {
    this.players[index].commit = Math.max(0, value);
    this.willpower = this.players.reduce((a, p) => a + p.commit, 0);
    this.willpower_detached = false;
  }

  // Set the committed-willpower total, logging the change. A setter rather
  // than a bare assignment because three entry points write this - the
  // quest_commit and quest_staging steppers and the willpower counter modal -
  // and all three used to assign straight to the field, so none of them
  // appeared in the log.
  setWillpower(value) {
    const v = Math.max(0, value);
    // Solo has no breakdown to lose: with one player the total IS that
    // player's commit, so write it through. An identity, not a heuristic, and
    // deliberately keyed on players.length rather than "one player not
    // eliminated" - an eliminated player's stored commit is still real data.
    let detached;
    if (this.players.length === 1) {
      this.players[0].commit = v;
      detached = false;
    } else {
      // Setting the total directly is the one way the two sources can disagree
      // - unless the value happens to match the sum, in which case nothing is
      // out of sync and there is nothing to flag.
      detached = v !== this.players.reduce((n, p) => n + p.commit, 0);
    }
    if (v !== this.willpower) {
      // Two different facts, so two different sentences. Once the total is
      // set directly the per-player breakdown is unknown, and the log must
      // not imply one it does not have.
      this.logEvent(detached
        ? `Players committed ${v} willpower to the quest`
        : `Willpower total ${v}, matching the player breakdown`, "tally", "wp");
      this.willpower = v;
    }
    this.willpower_detached = detached;
    return this.willpower;
  }

  // Same three entry points as setWillpower, same reason.
  setStaging(value) {
    const v = Math.max(0, value);
    if (v !== this.staging) {
      // State phrasing, not "%d -> %d". Coalescing rewrites the row in place,
      // and a delta phrasing would then claim the run started wherever the last
      // tap happened to be.
      this.logEvent(`Staging area threat ${v}`, "tally", "stg");
      this.staging = v;
    }
    return this.staging;
  }

  // Adopt the per-player breakdown as the total, but ONLY when the two already
  // agree.
  //
  // This used to overwrite the total unconditionally, and PlayersDetailModal
  // called it from its constructor. So opening the players view during the
  // quest phase - exactly what a Doomed keyword, Caught in a Web or a failed
  // quest pushes you to do, to record the threat - silently threw away a
  // committed total and replaced it with a stale sum. A solo player committed
  // 11 willpower, tapped in +1 threat, and resolved the quest against 0. Found
  // in the 2026-07-30 playtest of The Oath.
  //
  // A view that shows numbers must not rewrite them. Reconciliation still
  // happens where it belongs: setCommit recomputes the total and clears the
  // flag the moment a breakdown is actually edited.
  resyncWillpower() {
    if (this.willpower_detached) return this.willpower;
    const total = this.players.reduce((n, p) => n + p.commit, 0);
    if (total !== this.willpower) {
      this.logEvent(`Willpower total ${this.willpower} -> ${total} (re-synced to the players)`);
    }
    this.willpower = total;
    this.willpower_detached = false;
    return total;
  }

  _totalProgress() {
    let n = this.quest.progress;
    for (const l of this.active_locations) n += l.progress;
    for (const s of this.side_quests) n += s.progress;
    return n;
  }

  _snapshotRound() {
    this._round_snap = { t: this._now(),
                         threats: this.players.map(p => p.threat),
                         progress: this._totalProgress(),
                         quest: this.quest.progress };
  }

  // -- phase-relative bookkeeping ------------------------------------------
  _phaseProjection() {
    const m = this.snapshot();
    for (const k of PHASE_NAV_KEYS) delete m[k];
    return m;
  }

  // Close the current view's phase: store how much it moved things.
  _recordPhaseDelta() {
    const base = this._phase_bases[this.view];
    if (!base) return;
    const d = relDelta(base, this._phaseProjection());
    if (d) this._phase_deltas[this.view] = d;
    else delete this._phase_deltas[this.view];
  }

  // Put live state back to what it was when `view` was entered - which is by
  // definition the previous phase's final values.
  _restorePhaseEntry(view) {
    const base = this._phase_bases[view];
    if (!base) return false;
    this.loadSnapshot({ ...this.snapshot(), ...base });
    return true;
  }

  // Closes the outgoing phase's delta, then re-applies the incoming view's own
  // delta relative to wherever the numbers now stand. `rebase` is false only
  // for backView, which restores rather than replays.
  enterView(v, rebase = true) {
    this._recordPhaseDelta();
    this.view = v;
    this.step = VIEW_STEP[v];
    // A window is not a new phase, so it does not claim to be one in the log:
    // the "Phase:" lines are how a reader reconstructs a round, and eight
    // extra false starts per round would drown them.
    if (v === "round_end") {
      this.logEvent(`End of Round ${this.round}`);
    } else if (isWindowView(v)) {
      // Action windows are no longer logged at all. A window is not a state
      // change, its own screen names it, and the R<round>.<step> column already
      // carries the step - it was 8 of the ~21 rows a round produced, every
      // round, identically.
    } else {
      // And a phase is logged only when the PHASE changes, not on every view
      // transition. VIEW_ORDER has 21 entries but only 12 distinct phases.
      const phase = VIEW_LABELS[v] ?? v;
      if (phase !== this._last_phase_logged) {
        this._last_phase_logged = phase;
        this.logEvent(`Phase: ${phase}`, "phase");
      }
    }
    // 7.3 and 7.4 happen on ARRIVAL at refresh, before its window opens.
    if (v === "refresh") this.applyRefresh();

    if (v === VIEW_ORDER[0]) {
      // A round boundary. endRound() has banked the stats, bumped the counter
      // and re-derived the willpower total, so no phase of the closed round
      // has a base worth rebasing onto.
      this._phase_bases = {};
      this._phase_deltas = {};
    }
    // The base is taken AFTER any arrival effect, so applyRefresh's threat
    // raise and the sailing shift stay out of the phase delta - both are
    // once-per-round arrival effects with their own idempotence guards, and
    // replaying them relatively would raise threat a second time.
    this._phase_bases[v] = this._phaseProjection();
    if (rebase) {
      const d = this._phase_deltas[v];
      if (d) this.loadSnapshot(applyRel(this.snapshot(), d));
    }
  }

  nextView() {
    if (this.view === "quest_sailing") return "quest_commit";
    const i = VIEW_ORDER.indexOf(this.view);
    let nxt = VIEW_ORDER[(i + 1) % VIEW_ORDER.length];
    // Resolution is entered only by a successful resolve, so the staging
    // window hands straight to travel.
    if (this.view === "aw_quest_staging") nxt = "travel";
    if (this.view === "planning" && this.sailing) nxt = "quest_sailing";
    return nxt;
  }

  // nextView() drives navigation; this drives the CTA label. They differ
  // because a phase view's button must still read "Next: Questing: Staging"
  // even when the tap lands on that phase's window first.
  nextPhaseView() {
    let v = this.nextView(), seen = 0;
    while (isWindowView(v) && seen < VIEW_ORDER.length) {
      const i = VIEW_ORDER.indexOf(v);
      v = VIEW_ORDER[(i + 1) % VIEW_ORDER.length];
      if (v === "quest_resolution") v = "travel";
      seen++;
    }
    return v;
  }

  // Take a contextual skip, landing on the last window before its target.
  //
  // Three things this deliberately is NOT: automatic (the app does not track
  // enemies, so the player asserts it); silent (the skipped span is named in
  // the log); or a one-way door (it goes through enterView like every other
  // transition, so it sits in the same delta bracket and undo restores it).
  //
  // Returns the view landed on, or null if the skip is not offered here.
  skipTo(skipId) {
    const skip = skipsFrom(this.view).find(s => s.id === skipId);
    if (!skip) return null;
    const landing = lastWindowBefore(skip.to);
    if (!landing || landing === this.view) return null;

    const i = VIEW_ORDER.indexOf(this.view), j = VIEW_ORDER.indexOf(landing);
    if (j <= i) return null;
    const passed = VIEW_ORDER.slice(i + 1, j);
    this.logEvent(`Skipped ${passed.length ? passed.join(", ") : "nothing"} - ${skip.claim}`);
    this.enterView(landing);
    return landing;
  }

  advanceView() {
    if (this.view === "quest_setup") {
      // The one-time setup view leads into round 1 and is never revisited. A
      // catalog game normally leaves it through the screen's "flip_to_b" CTA,
      // which flips 1A -> 1B first; this is the generic path, kept so
      // advanceView is total over every view.
      this.logEvent(`Setup complete - round 1 begins (quest ${this.questLabel()} needs ${this.quest.points})`);
      this.enterView(VIEW_ORDER[0]);
      this._snapshotRound();
      return;
    }
    if (this.view === "quest_sailing") { this.enterView("quest_commit"); return; }
    const nxt = this.nextView();
    this.enterView(nxt);
    // A Sailing test begins by shifting one step off-course (rulebook p.6).
    // That is an ARRIVAL effect, once per round - backing out to Planning and
    // coming forward again is one arrival, not two. Guarded the same way and
    // for the same reason as applyRefresh's refresh_applied, and the flag is
    // in snapshot() so undo restores it with the heading.
    if (nxt === "quest_sailing" && !this.sailed_this_round) {
      this.sailed_this_round = true;
      this.shiftHeading(1, "winds shift");
    }
  }

  // Where backView() would go from here, without going there.
  //
  // The inverse of nextView(), and derived from the PHASE SEQUENCE rather than
  // from a history of screens visited. Back means "the previous phase view" -
  // what the forward arrow means, read backwards. Two consequences worth
  // stating, because an earlier draft kept a visited-screens stack and got
  // both wrong: nothing has to be recorded for it to work, so a resumed game
  // has Back on the first frame; and it can never reopen a modal flow, because
  // a modal is not a view.
  prevView() {
    const v = this.view;
    if (v === "quest_setup") return null;    // its Back leaves the game
    if (v === "quest_sailing") return "planning";
    if (v === "quest_commit") return this.sailing ? "quest_sailing" : "planning";
    // Entered from quest_staging by resolving, never through the staging
    // window - see the play screen's stage_advance CTA.
    if (v === "quest_resolution") return "quest_staging";
    const i = VIEW_ORDER.indexOf(v);
    // A closed round is a hard floor: endRound() has already banked its stats,
    // bumped the counter and re-derived the willpower total.
    return i <= 0 ? null : VIEW_ORDER[i - 1];
  }

  canGoBack() {
    // Not canUndo(): Back is navigation. The two answered the same question
    // only by accident - canUndo() is true from the first tap of the game
    // onward, so Back was offered at the top of every round, where the only
    // thing behind you is a round that has already been closed out.
    return this.prevView() !== null;
  }

  // Navigation, not undo - but the values it lands on are the PREVIOUS phase's
  // final ones, which is the same thing as this phase's entry state. What this
  // phase changed is not thrown away: it was banked as a relative delta, and
  // walking forward again re-applies it on top of whatever the earlier phase
  // now says. So correcting an upstream count moves everything downstream with
  // it instead of overwriting it.
  backView() {
    const prev = this.prevView();
    if (prev === null) return false;
    if (this.view === "quest_resolution") this.unresolveQuest();
    const leaving = this.view;
    this._recordPhaseDelta();
    this._restorePhaseEntry(leaving);
    // Straight assignment, not enterView: going back must not re-log the
    // phase, re-run its arrival effect, or reset the base of the view being
    // returned to - that base is what makes ITS delta come out right.
    this.view = prev;
    this.step = VIEW_STEP[prev];
    return true;
  }

  // Reopen a resolved quest so advancing runs the comparison again.
  // resolveQuest() latches quest_resolved and the play screen only resolves
  // `if (!game.quest_resolved)`, so without this a staging count corrected
  // after backing out would still resolve against the old numbers.
  //
  // This is a TRACKER: a player who miscounted may retcon, including out of an
  // elimination. So a fail's threat raise is taken back rather than being a
  // reason to refuse to move.
  unresolveQuest() {
    if (!this.quest_resolved) return false;
    if (this.quest_outcome === "fail") {
      const n = this.quest_outcome_n;
      this.players.forEach((p, i) => {
        // Who took the raise, worked back from the state it produced.
        // resolveQuest raised the LIVING only, and `eliminated` is purely
        // threat >= elimination, so a player is still eliminated after the
        // reversal exactly when they were already eliminated before it.
        if (!p.eliminated || p.threat - n < p.elimination) this.adjustThreat(i, -n);
      });
      // adjustThreat raises the prompt but never lowers it, and the player it
      // was raised for may be back under their level now.
      if (this.pending_elim !== null &&
          !this.players[this.pending_elim].eliminated) this.pending_elim = null;
    }
    if (this.quest_history.length) this.quest_history.pop();
    // A resolution is DERIVED from willpower vs staging, so it must be
    // recomputed rather than replayed - drop the phase delta that would
    // otherwise re-apply the old outcome on the way forward.
    delete this._phase_deltas.quest_resolution;
    this.quest_resolved = false;
    this.quest_outcome = null;
    this.quest_outcome_n = 0;
    this.pending_budget = 0;
    this.logEvent("Quest resolution reopened");
    return true;
  }

  headingLabel() { return HEADINGS[this.heading][0]; }

  headingDesc() {
    const [term, , facing] = HEADINGS[this.heading];
    return `${term} (${facing})`;
  }

  shiftHeading(delta, why = "") {
    const to = Math.max(0, Math.min(HEADINGS.length - 1, this.heading + delta));
    if (to === this.heading) return false;
    const was = this.headingDesc();
    this.heading = to;
    const dir = delta > 0 ? "off-course" : "on-course";
    this.logEvent(`Sailing: heading ${was} -> ${this.headingDesc()}` +
                  ` (shifted ${dir}${why ? ", " + why : ""})`);
    return true;
  }

  allEliminated() { return this.players.every(p => p.eliminated); }

  gameDuration() {
    const t0 = this.log.length ? this.log[0].t : null;
    const now = this._now();
    return (t0 !== null && now !== null) ? fmtMs(now - t0) : null;
  }

  // A finished game, in the shape the history store keeps. ~220 B, which is
  // what makes appending one per game free forever. Deliberately a flat
  // summary rather than the whole save: the stats screens aggregate over
  // these, and reading 4000 full saves back took 15.9 s on device.
  historyRecord() {
    const scn = this.scenario ?? {};
    return {
      scn: scn.slug ?? null,
      name: scn.name ?? null,
      mode: scn.mode ?? null,
      source: scn.source ?? null,
      players: this.players.length,
      won: !!(this.game_over && this.game_over.result === "victory"),
      rounds: this.round,
      duration: this.game_over?.duration ?? null,
      threats: this.players.map(p => p.threat),
      eliminated: this.players.filter(p => p.eliminated).length,
    };
  }

  setGameOver(result) {
    if (this.game_over) return;
    this.game_over = { result, round: this.round, duration: this.gameDuration() };
    this.logEvent(result === "victory"
      ? "GAME OVER - Victory! The final quest stage is complete"
      : "GAME OVER - Defeat. All players are eliminated");
  }

  _applyTravelStaging(contribution) {
    if (contribution > 0 && this.staging > 0) {
      const before = this.staging;
      this.staging = Math.max(0, this.staging - contribution);
      this.logEvent(`Staging area threat ${before} -> ${this.staging} (traveled location)`);
    }
  }

  // The new active location. `name` is the catalog card name when the player
  // picked one (LocationPickModal's list step); manual entry passes null and
  // the object keeps exactly the two keys it always had, so old saves and
  // hand-entered locations stay indistinguishable from today's - every label
  // site reads .name with a generic fallback.
  // Mirrors gamestate.py LOC_META / _seat_location. Every key is optional and
  // absent for a manual entry, so a hand-typed location and an old save stay
  // byte-identical to what they were.
  //
  // `threat` is the location's staging contribution, stored rather than only
  // passed to _applyTravelStaging because putting the location BACK into
  // staging has to add the same number again, and by then the caller no longer
  // has it.
  //
  // `*Kind` / `*Formula` say why a stat has no number - see
  // quest_catalog.locationsFor - so the Progress screen can show the card's
  // own definition of X instead of a 0 it made up.
  static LOC_META = ["threat", "pointsKind", "pointsX",
                     "threatKind", "threatX", "threatCount"];

  _seatLocation(points, name, meta = null) {
    const loc = { points, progress: 0 };
    for (const k of GameState.LOC_META) {
      const v = (meta ?? {})[k];
      if (v !== null && v !== undefined) loc[k] = v;
    }
    if (name) loc.name = name;
    // An AUTO X resolves the moment the card is placed. The other two shapes
    // wait for a count the player supplies on the row sheet, but "X is the
    // number of players" has no control to wait for - there is nothing to ask
    // - so without this the location would sit at no threat at all and
    // under-report the staging total.
    const auto = resolveX(loc.threatX, {
      players: this.players.length,
      stage: this.quest.stage_n ?? 1,
      highestThreat: Math.max(0, ...this.players.map((p) => p.threat)),
    });
    if (auto !== null && autoFor(loc.threatX?.target)) loc.threat = auto;
    return loc;
  }

  travelTo(points, contribution = 0, name = null, meta = null) {
    // Appends. Travelling with one already active is how the second one
    // arrives; changeLocation is what replaces a seat.
    this.active_locations.push(this._seatLocation(points, name, meta));
    // Only claim a travel when the players actually paid the cost. A card effect
    // can make a location active without one, and the log is the game's record.
    // The mechanics are identical either way (RR: "the active location acts as a
    // buffer", so its threat leaves the staging total regardless).
    const verb = (meta ?? {}).arrival === "effect"
      ? "Placed as active location:" : "Traveled to";
    this.logEvent(`${verb} ${name || "new location"} (${points} quest points)`);
    this._applyTravelStaging(contribution);
  }

  changeLocation(points, contribution = 0, name = null, idx = 0, meta = null) {
    // Replaces ONE seat, not the whole row: with two actives, "a card effect
    // replaces the active location" names one of them, and discarding the
    // other alongside it would silently drop its progress.
    const old = idx < this.active_locations.length ? this.active_locations[idx] : null;
    const seat = this._seatLocation(points, name, meta);
    if (old) this.active_locations[idx] = seat;
    else this.active_locations.push(seat);
    const newLabel = name || "new";
    if (old) {
      this.logEvent(`Changed active location (${old.name || "old"} at ${old.progress}/${old.points} discarded) -> ${newLabel} (${points} quest points)`);
    } else {
      this.logEvent(`Changed active location -> ${newLabel} (${points} quest points)`);
    }
    this._applyTravelStaging(contribution);
  }

  // Any location at its quest points is Explored - removed from the row.
  // Back to front, so removing one does not shift the index of a later one
  // still being checked.
  exploreLocationIfDone() {
    let done = false;
    for (let i = this.active_locations.length - 1; i >= 0; i--) {
      const loc = this.active_locations[i];
      if (loc.points > 0 && loc.progress >= loc.points) {
        this.logEvent(`Active location Explored (${loc.progress}/${loc.points}) - removed`);
        this.active_locations.splice(i, 1);
        done = true;
      }
    }
    return done;
  }

  actionWindowOpen() { return phaseStep(this.step).action_window; }

  // Steps 7.3 and 7.4. Called from enterView() when the refresh view is
  // entered, because RR puts both BEFORE the refresh action window (the chart
  // runs 7.3, 7.4, ACTION WINDOW, 7.5). Idempotent via refresh_applied, which
  // is in snapshot(), so back restores the threat and the flag together.
  applyRefresh() {
    if (this.refresh_applied) return false;
    for (let i = 0; i < this.players.length; i++) {
      if (!this.players[i].eliminated) {
        this.adjustThreat(i, this.players[i].threat_per_round);
      }
    }
    this.first_player = (this.first_player + 1) % this.players.length;
    this.refresh_applied = true;
    this.logEvent(`Refresh: threat raised, first player -> P${this.first_player + 1}`);
    return true;
  }

  // Close the round out. 7.3 and 7.4 are NOT here - they belong to
  // applyRefresh(). This is 0.1 -> 0.0.
  endRound() {
    const snap = this._round_snap;
    if (snap) {
      const parts = [];
      if (snap.t !== null && this._now() !== null) parts.push(fmtMs(this._now() - snap.t));
      this.players.forEach((p, i) => {
        const d = p.threat - snap.threats[i];
        if (d) parts.push(`P${i + 1} ${d > 0 ? "+" : ""}${d}`);
      });
      const pd = this._totalProgress() - snap.progress;
      if (pd) parts.push(`quest ${pd > 0 ? "+" : ""}${pd}`);
      this.logEvent(`Round ${this.round} ended: ${parts.length ? parts.join(", ") : "no changes"}`);
    }
    this.round += 1;
    // commits persist as next round's defaults; refresh the derived total
    this.willpower = this.players.reduce((a, p) => a + p.commit, 0);
    this.willpower_detached = false;
    this.quest_resolved = false;
    this.quest_outcome = null;
    this.refresh_applied = false;      // arm the next round's 7.3 / 7.4
    this.sailed_this_round = false;    // ...and the next round's winds
    this.logEvent(`New round ${this.round} begins`);
    this.enterView(VIEW_ORDER[0]);
    this._snapshotRound();
  }

  // Load a quest-picker scenario: scn is metadata (slug/name/pack/...),
  // stages is the stage/card tree. Resets quest to stage 1 side A.
  // Replace the in-memory stage tree with a freshly-read one. Refuses the
  // swap when the new tree cannot host the position the game is already at -
  // stage_idx/card_idx index into it. Never touches `quest`, where the live
  // stage number, side, points and progress are, so refreshing does not
  // disturb play. Mirror of gamestate.py's rehydrate_stages.
  rehydrateStages(stages) {
    if (!stages || !stages.length) return false;
    if (this.stage_idx >= stages.length) return false;
    const cards = (stages[this.stage_idx] || {}).cards || [];
    if (this.card_idx >= cards.length) return false;
    this.stages = stages;
    return true;
  }

  preloadScenario(scn, stages) {
    this.scenario = scn;
    this.stages = JSON.parse(JSON.stringify(stages));
    this.stage_idx = 0;
    this.card_idx = 0;
    const st = this.stages[0];
    this.quest.stage_n = st.stage;
    this.quest.side = "A";
    this.quest.points = 0;
    this.quest.progress = 0;
    this.sailing = !!st.cards[0].sailing;
  }

  // 1A -> 1B: load the current card's questPoints as side B's target.
  //
  // `mode` says whether that target is real. ~177 stage cards print no quest
  // points at all: they advance on a condition (an enemy defeated, an
  // objective claimed, a pile of resource tokens) rather than by filling a
  // bar, and drawing 0/0 for them is a lie. `advance` / `lose` carry the
  // card's own sentence about how the stage ends, distilled from its printed
  // text - see tools/build_advancement.py.
  //
  //   "points"     a real printed target; fill the bar
  //   "condition"  no target exists; show the sentence instead
  //   "formula"    the card computes one in its own text
  flipToB() {
    const card = this.stages[this.stage_idx].cards[this.card_idx];
    this.quest.side = "B";
    this.quest.points = card.questPoints;
    const kind = card.questPointsKind, coded = card.questPointsX;
    if (coded) {
      this.quest.mode = "formula";
      this.quest.x = coded;
    } else if (kind === "na" || (!card.questPoints && kind)) {
      this.quest.mode = "condition";
      delete this.quest.x;
    } else {
      this.quest.mode = "points";
      delete this.quest.x;
    }
    for (const k of ["advance", "lose"]) {
      if (card[k]) this.quest[k] = card[k];
      else delete this.quest[k];
    }
    return this.quest.points;
  }

  questLabel() { return `${this.quest.stage_n}${this.quest.side}`; }

  autoSplit(budget) {
    // Fill the active location, then the quest - each capped at its own
    // quest points. Side quests are left untouched; any overflow beyond
    // location + quest capacity is discarded.
    const alloc = { locations: this.active_locations.map(() => 0), quest: 0,
                    side_quests: this.side_quests.map(() => 0) };
    let remaining = budget;
    // In list order: RR p.15 fills the active location(s) before the quest
    // card, and with two the first one seated soaks it up first.
    this.active_locations.forEach((loc, i) => {
      const room = Math.max(0, loc.points - loc.progress);
      alloc.locations[i] = Math.min(remaining, room);
      remaining -= alloc.locations[i];
    });
    const qroom = Math.max(0, this.quest.points - this.quest.progress);
    alloc.quest = Math.min(remaining, qroom);
    return alloc;
  }

  needsResolution() {
    // True if the active location, the quest, or any side quest is
    // currently at/over its own (positive) quest points - the trigger for
    // the guided resolution flow after a manual progress edit.
    if (this.active_locations.some(l => l.points > 0 && l.progress >= l.points)) return true;
    if (this.quest.points > 0 && this.quest.progress >= this.quest.points) return true;
    return this.side_quests.some(s => s.points > 0 && s.progress >= s.points);
  }

  resolveLocationOverflow() {
    // Active location(s) at/over their points: explore them (rulebook p.15),
    // crediting any excess progress to the quest card. Returns the total
    // excess credited, 0 if nothing was ready. Back to front, so removing one
    // does not shift the index of a later one still being checked.
    let total = 0;
    for (let i = this.active_locations.length - 1; i >= 0; i--) {
      const loc = this.active_locations[i];
      if (loc.points <= 0 || loc.progress < loc.points) continue;
      const excess = loc.progress - loc.points;
      this.logEvent(`Active location Explored (${loc.progress}/${loc.points})` +
                    (excess ? ` - ${excess} excess to quest` : ""));
      this.active_locations.splice(i, 1);
      total += excess;
    }
    if (total) this.quest.progress += total;
    return total;
  }

  clearAndAdvance(cardIdx = 0) {
    // Clear the current (side-B) stage and reveal the next stage's side A.
    // Per the rulebook (p.22), excess quest progress does NOT carry to the
    // next stage - it is discarded, so progress always resets to 0.
    // cardIdx selects the branch alternative when the next stage has more
    // than one card (default 0). Returns false (no mutation) if there is
    // no next stage - the caller should treat that as victory.
    if (this.stage_idx + 1 >= this.stages.length) return false;
    const was = this.questLabel();
    const excess = this.quest.progress - this.quest.points;
    if (excess > 0) {
      this.logEvent(`Quest ${was} cleared (${excess} excess discarded - does not carry over)`);
    } else {
      this.logEvent(`Quest ${was} cleared`);
    }
    this.stage_idx += 1;
    this.card_idx = cardIdx;
    const st = this.stages[this.stage_idx];
    this.quest.stage_n = st.stage;
    this.quest.side = "A";
    this.quest.points = 0;
    this.quest.progress = 0;
    this.sailing = !!st.cards[cardIdx].sailing;
    return true;
  }

  placeProgress(alloc) {
    const completed = [];
    // Back to front: an explored location is removed, and going forward would
    // shift the index of every later one still to be credited.
    const locs = alloc.locations ?? [];
    for (let i = this.active_locations.length - 1; i >= 0; i--) {
      const n0 = locs[i] ?? 0;
      if (!n0) continue;
      const loc = this.active_locations[i];
      loc.progress += n0;
      if (loc.progress >= loc.points) {
        completed.push("Active Location explored");
        this.active_locations.splice(i, 1);
      }
    }
    let n = alloc.quest ?? 0;
    if (n) {
      this.quest.progress += n;
      if (this.quest.points > 0 && this.quest.progress >= this.quest.points) {
        const was = this.questLabel();
        if (this.stages.length) {
          // Catalog game: defer ALL advance mechanics (branch choice,
          // reveal, flip) to ResolutionModal - see
          // docs/superpowers/plans/2026-07-24-quest-picker-bresolve.md.
          this.pending_resolution = "auto";
        } else {
          const excess = this.quest.progress - this.quest.points;
          this._advanceQuestStage();
          this.quest.points = 0;
          this.pending_stage = { cleared: was, excess };
        }
        completed.push(`Quest ${was} cleared`);
      }
    }
    for (let i = this.side_quests.length - 1; i >= 0; i--) {
      const add = (alloc.side_quests ?? [])[i] ?? 0;
      if (!add) continue;
      this.side_quests[i].progress += add;
      if (this.side_quests[i].progress >= this.side_quests[i].points) {
        completed.push(`Side quest ${i + 1} completed`);
        this.side_quests.splice(i, 1);
      }
    }
    return completed;
  }

  _advanceQuestStage() {
    if (this.quest.side === "A") this.quest.side = "B";
    else { this.quest.side = "A"; this.quest.stage_n += 1; }
    this.quest.progress = 0;
  }

  // What resolution WOULD do right now, without doing it. The staging
  // window's copy is conditional on this, and the view must not re-derive the
  // comparison - resolveQuest() owns that rule, and two copies drift.
  //
  // room is remaining quest points PLUS unfilled active-location capacity,
  // because progress fills the location first and its overflow flows on to
  // the quest (RR 3.4). Testing the quest card alone would tell a player
  // their willpower is wasted while a location is still soaking it up.
  questPreview() {
    const diff = this.willpower - this.staging;
    const outcome = diff > 0 ? "success" : (diff < 0 ? "fail" : "tie");
    let room = Math.max(0, this.quest.points - this.quest.progress);
    for (const loc of this.active_locations) {
      room += Math.max(0, loc.points - loc.progress);
    }
    return [outcome, Math.abs(diff), room];
  }

  resolveQuest(willpower, staging) {
    const diff = willpower - staging;
    this.quest_resolved = true;
    let outcome, n, result;
    if (diff > 0) {
      outcome = "success"; n = diff;
      result = { outcome, budget: n };
    } else if (diff < 0) {
      const shortfall = -diff;
      this.players.forEach((p, i) => { if (!p.eliminated) this.adjustThreat(i, shortfall); });
      this.logEvent(OUTCOME.toast_fail.replace("%d", shortfall));
      outcome = "fail"; n = shortfall;
      result = { outcome, threat: n };
    } else {
      this.logEvent("Quest unsuccessful - tie, no change");
      outcome = "tie"; n = 0;
      result = { outcome };
    }
    this.quest_outcome = outcome;
    this.quest_outcome_n = n;
    // `stage` is what the History chart rules a gold vertical on: without it
    // the chart can show the rounds but not where the quest advanced, which is
    // the one thing that explains a sudden jump in the staging line. Entries
    // written before this exist without the key, so every reader uses
    // `?? `/optional access rather than assuming it.
    this.quest_history.push({
      round: this.round, willpower, staging, outcome, n, heading: this.heading,
      stage: this.quest.stage_n ?? 1 });
    if (this.quest_history.length > 20) {
      this.quest_history = this.quest_history.slice(-20);
    }
    return result;
  }

  // -- delta replay ------------------------------------------------------
  // The seam between our object graph and the reference's map model.
  // DragnCards' `game` IS a map, so it diffs itself; snapshot()/loadSnapshot()
  // are the one adapter parity requires.
  //
  // Collections become index-keyed maps because getDelta recurses into maps
  // only - the same reason the reference models everything as
  // groupById/cardById/stackById.

  snapshot() {
    const keyed = xs => Object.fromEntries(xs.map((x, i) => [String(i), { ...x }]));
    return {
      players: Object.fromEntries(this.players.map((p, i) => [String(i), {
        threat: p.threat, eliminated: p.eliminated,
        commit: p.commit }])),
      quest: { ...this.quest },
      active_locations: keyed(this.active_locations),
      side_quests: keyed(this.side_quests),
      quest_history: keyed(this.quest_history),
      willpower: this.willpower,
      willpower_detached: this.willpower_detached,
      staging: this.staging,
      sailing: this.sailing,
      heading: this.heading,
      pending_budget: this.pending_budget,
      pending_stage: this.pending_stage ? { ...this.pending_stage } : null,
      pending_elim: this.pending_elim,
      round: this.round,
      first_player: this.first_player,
      view: this.view,
      step: this.step,
      stage_idx: this.stage_idx,
      card_idx: this.card_idx,
      quest_resolved: this.quest_resolved,
      refresh_applied: this.refresh_applied,
      sailed_this_round: this.sailed_this_round,
      quest_outcome: this.quest_outcome,
      quest_outcome_n: this.quest_outcome_n,
      game_over: this.game_over ? { ...this.game_over } : null,
    };
  }

  loadSnapshot(m) {
    const unkeyed = o => Object.keys(o).sort((a, b) => a - b).map(k => ({ ...o[k] }));
    this.players.forEach((p, i) => {
      const pd = m.players[String(i)];
      if (!pd) return;
      p.threat = pd.threat;
      p.eliminated = pd.eliminated;
      p.commit = pd.commit;
    });
    this.willpower_detached = m.willpower_detached ?? false;
    this.quest = { ...m.quest };
    this.active_locations = unkeyed(m.active_locations);
    this.side_quests = unkeyed(m.side_quests);
    this.quest_history = unkeyed(m.quest_history);
    this.willpower = m.willpower;
    this.staging = m.staging;
    this.sailing = m.sailing;
    this.heading = m.heading;
    this.pending_budget = m.pending_budget;
    this.pending_stage = m.pending_stage ? { ...m.pending_stage } : null;
    this.pending_elim = m.pending_elim;
    this.round = m.round;
    this.first_player = m.first_player;
    this.view = m.view;
    this.step = m.step;
    this.stage_idx = m.stage_idx;
    this.card_idx = m.card_idx;
    this.quest_resolved = m.quest_resolved;
    this.refresh_applied = m.refresh_applied;
    // ??: deltas recorded before the flag existed carry no such key, and a
    // snapshot is replayed as a whole map.
    this.sailed_this_round = m.sailed_this_round ?? false;
    this.quest_outcome = m.quest_outcome;
    this.quest_outcome_n = m.quest_outcome_n;
    this.game_over = m.game_over ? { ...m.game_over } : null;
  }

  // Open a recording window: clear the message buffer and return the snapshot
  // to hand back to addDelta().
  //
  // The clear matters. Without it, anything logged before the window opens
  // (game setup, a round summary, a modal that logged and returned) would be
  // drained into the next delta's metadata and stamped with its index - so the
  // Log screen would offer a jump target that does not undo those lines. The
  // reference has the same boundary: game_ui_server.ex zeroes game["messages"]
  // before dispatching an action.
  beginAction() {
    this.messages = [];
    this._action_entries = [];
    this._replay_moved = false;
    return this.snapshot();
  }

  // Parity: game_ui.ex add_delta/2. Returns true when a delta was recorded.
  //
  // Divergence D2: the reference advances replayStep before it knows whether
  // the diff is non-nil, so a no-op action leaves the cursor one past the end
  // and silently swallows the next undo. We only advance on a real delta.
  //
  // Navigating the history is NOT an action. If the window contained a cursor
  // move, the "change" this would diff is the undo itself - which would append
  // it as a fresh delta, destroy the redo future, and make the log claim an
  // action happened that never did. The reference is immune by construction:
  // step_through is a separate GenServer call from game_action, so its
  // add_delta is never reached. We have one choke point, so we need the guard.
  addDelta(prevSnapshot) {
    if (this._replay_moved) {
      this._replay_moved = false;
      this.messages = [];
      return false;
    }
    const d = getDelta(prevSnapshot, this.snapshot());
    if (d === null) { this.messages = []; return false; }
    d._delta_metadata = { unix_ms: this._now(), log_messages: this.messages };
    // A fresh action after an undo discards the redo future. The journal
    // cannot un-append, so record the truncation instead.
    if (this.replay_step + 1 < this.deltas.length) {
      this._replay_appends.push({ op: "t", to: this.replay_step + 1 });
    }
    this.deltas = this.deltas.slice(0, this.replay_step + 1);
    this.deltas.push(d);
    this._replay_appends.push({ op: "d", d });
    this.replay_step = this.deltas.length - 1;
    // Stamp this action's log entries with their delta index so the Log screen
    // can offer a jump target per row without matching on text. logEvent
    // appends to log and messages together, so the last N entries are ours.
    for (const e of this._action_entries) e.delta_i = this.replay_step;
    this._action_entries = [];
    this.messages = [];
    if (this.deltas.length > MAX_SAVED_DELTAS) {
      const drop = this.deltas.length - MAX_SAVED_DELTAS;
      this.deltas = this.deltas.slice(drop);
      this.replay_step -= drop;
      for (const e of this.log) {
        if ("delta_i" in e) e.delta_i -= drop;   // may go negative: not a target
      }
      this._replay_appends.push({ op: "x", n: drop });
    }
    this._replay_appends.push({ op: "s", i: this.replay_step });
    return true;
  }

  // Journal ops this action produced, then clear.
  takeReplayAppends() {
    const out = this._replay_appends;
    this._replay_appends = [];
    return out;
  }

  // The ops that would rebuild the CURRENT history from empty - used when the
  // journal is first created for a game that already has deltas.
  seedReplayJournal() {
    const ops = this.deltas.map(d => ({ op: "d", d }));
    ops.push({ op: "s", i: this.replay_step });
    return ops;
  }

  canUndo() { return this.replay_step >= 0; }
  canRedo() { return this.replay_step < this.deltas.length - 1; }

  undo() {                                   // parity: game_ui.ex undo/1
    if (!this.canUndo()) return false;
    const m = this.snapshot();
    applyDelta(m, this.deltas[this.replay_step], "undo");
    this.loadSnapshot(m);
    this.replay_step -= 1;
    this._replay_moved = true;
    return true;
  }

  redo() {                                   // parity: game_ui.ex redo/1
    if (!this.canRedo()) return false;
    const m = this.snapshot();
    applyDelta(m, this.deltas[this.replay_step + 1], "redo");
    this.loadSnapshot(m);
    this.replay_step += 1;
    this._replay_moved = true;
    return true;
  }

  // Named stepReplay, not step: `this.step` is already the phase step id and a
  // method of that name would be shadowed by the constructor's assignment.
  stepReplay(direction) {                    // parity: game_ui.ex step/2
    if (direction === "undo") return this.undo();
    if (direction === "redo") return this.redo();
    return false;
  }

  applyDeltasUntilIndex(target) {
    let moved = false;
    while (this.replay_step > target && this.undo()) moved = true;
    while (this.replay_step < target && this.redo()) moved = true;
    return moved;
  }

  // Divergence D1: the reference reads roundNumber off the gameui wrapper
  // (game_ui.ex:1017, :1027) where the key does not exist, so its halt
  // condition compares nil to nil and never fires. We read the live round.
  applyDeltasUntilRoundChange(direction) {
    const roundInit = this.round;
    let moved = false;
    while (this.stepReplay(direction)) {
      moved = true;
      if (this.round !== roundInit) break;
    }
    return moved;
  }

  stepThrough(options) {                     // parity: game_ui.ex step_through/2
    const size = options && options.size;
    let moved;
    if (size === "single") moved = this.stepReplay(options.direction);
    else if (size === "round") moved = this.applyDeltasUntilRoundChange(options.direction);
    else if (size === "index") moved = this.applyDeltasUntilIndex(options.index);
    else return false;
    // replay_step is WRITTEN, not recomputed (Divergence D3), so a cursor
    // move has to reach the journal too.
    if (moved) this._replay_appends.push({ op: "s", i: this.replay_step });
    return moved;
  }

  // -- replay persistence ------------------------------------------------
  // Parity: the Replay schema's two columns (backend/lib/dragn/replay.ex) -
  // game_json and deltas. Divergence D4: two stores rather than one row,
  // because the device writes flash, not Postgres, and state.json is rewritten
  // on every tap. toDict()/fromDict() are untouched.
  //
  // Divergence D3: replay_step is written, not recomputed. The reference
  // derives count(deltas)-1 on load while game_json holds whatever the current
  // state was, so saving mid-undo reloads a cursor claiming end-of-history over
  // a state several steps back.
  replayToDict() {
    return { deltas: this.deltas, replay_step: this.replay_step };
  }

  // Rewrite a pre-list delta's `active_location` onto `active_locations`.
  //
  // A delta mirrors the shape of the state it describes, so renaming the field
  // renamed every recorded delta out from under undo: applying one would set a
  // stray `active_location` key and leave the real seat list untouched - a
  // silent wrong-undo rather than a crash, which is worse.
  //
  // The old side was a bare record or null; the new one is the keyed map
  // snapshot() emits, so seat 0 carries the whole change:
  //
  //   [null, rec] -> {"0": [REMOVED, rec]}     a location arrived
  //   [rec, null] -> {"0": [rec, REMOVED]}     it left
  //   {progress: [0, 1]} -> {"0": {progress: [0, 1]}}   it changed
  static _migrateDelta(delta) {
    if (!("active_location" in delta)) return delta;
    const out = { ...delta };
    const old = out.active_location;
    delete out.active_location;
    if (Array.isArray(old) && old.length === 2) {
      out.active_locations = { 0: [old[0] === null ? REMOVED : old[0],
                                   old[1] === null ? REMOVED : old[1]] };
    } else {
      out.active_locations = { 0: old };
    }
    return out;
  }

  replayFromDict(d) {
    this.deltas = [];
    this.replay_step = -1;
    if (!d || typeof d !== "object" || Array.isArray(d)) return;
    const ds = d.deltas;
    if (!Array.isArray(ds) || !ds.every(x => x && typeof x === "object" && !Array.isArray(x))) return;
    this.deltas = ds.map(x => GameState._migrateDelta(x));
    const rs = d.replay_step;
    if (typeof rs !== "number" || !Number.isInteger(rs)) {
      this.replay_step = ds.length - 1;
      return;
    }
    this.replay_step = Math.max(-1, Math.min(rs, ds.length - 1));
  }

  toDict() {
    return {
      players: this.players.map(p => ({
        label: p.label, threat: p.threat, starting_threat: p.starting_threat,
        threat_per_round: p.threat_per_round, eliminated: p.eliminated,
        elimination: p.elimination, commit: p.commit })),
      view: this.view, round: this.round, first_player: this.first_player,
      step: this.step, quest: { ...this.quest },
      scenario: this.scenario,
      // `stages` is NOT saved. It is scenario ASSET data - the full card tree
      // - and a save should reference an asset by id, not embed a copy.
      // Embedding it meant every data correction stopped at the save
      // boundary, and it put a median 2 KB of card data into the state blob.
      // `scenario` carries the slug; main.js re-reads the tree with it on
      // resume. fromDict still ACCEPTS a saved `stages` for older saves.
      stage_idx: this.stage_idx, card_idx: this.card_idx,
      active_locations: this.active_locations.map(l => ({ ...l })),
      side_quests: this.side_quests.map(s => ({ ...s })),
      willpower: this.willpower, willpower_detached: this.willpower_detached,
      staging: this.staging,
      pending_budget: this.pending_budget, pending_elim: this.pending_elim,
      pending_quest_card: this.pending_quest_card,
      pending_side_quest_pick: this.pending_side_quest_pick,
      pending_progress_detail: this.pending_progress_detail,
      pending_location_detail: this.pending_location_detail,
      pending_progress_history: this.pending_progress_history,
      pending_quest_config: this.pending_quest_config,
      pending_side_quest_detail: this.pending_side_quest_detail,
      pending_location_pick: this.pending_location_pick,
      elimination_threat: this.elimination_threat,
      quest_resolved: this.quest_resolved,
      refresh_applied: this.refresh_applied,
      sailed_this_round: this.sailed_this_round,
      quest_outcome: this.quest_outcome, quest_outcome_n: this.quest_outcome_n,
      quest_history: this.quest_history.map(e => ({ ...e })),
      sailing: this.sailing, heading: this.heading,
      game_over: this.game_over ? { ...this.game_over } : null,
      pending_stage: this.pending_stage ? { ...this.pending_stage } : null,
      pending_resolution: this.pending_resolution,
      // `log` is deliberately NOT saved here, for the same reason `stages`
      // is not: it was 96% of a save rewritten on every tap, and it is
      // append-only in practice (snapshot() excludes it, so undo never
      // touches it). It lives in its own append-only store; foldLog rebuilds it.
      seq: this._seq,
    };
  }

  static fromDict(d) {
    const g = new GameState();
    g.elimination_threat = d.elimination_threat ?? DEFAULT_ELIMINATION;
    g.players = d.players.map(pd => {
      const p = new Player(pd.label);
      p.threat = pd.threat;
      p.starting_threat = pd.starting_threat;
      p.threat_per_round = pd.threat_per_round;
      p.eliminated = pd.eliminated;
      p.elimination = pd.elimination ?? DEFAULT_ELIMINATION;
      p.commit = pd.commit ?? 0;
      return p;
    });
    // saves written before Resource and Planning were split carry the merged
    // view id; land them on the Resource half.
    const _v = d.view ?? VIEW_ORDER[0];
    g.view = _v === "resource_planning" ? "resource" : _v;
    g.round = d.round;
    g.first_player = d.first_player;
    g.step = d.step;
    g.quest = { ...d.quest };
    g.scenario = d.scenario ?? null;
    g.stages = d.stages ?? [];
    g.stage_idx = d.stage_idx ?? 0;
    g.card_idx = d.card_idx ?? 0;
    // Saves written before the list existed hold a single "active_location"
    // dict (or null). Migrate rather than drop it: a player mid-campaign
    // should not lose the location they travelled to because the HUD learned
    // to hold two.
    if (d.active_locations !== undefined) {
      g.active_locations = d.active_locations.map(l => ({ ...l }));
    } else {
      g.active_locations = d.active_location ? [{ ...d.active_location }] : [];
    }
    g.side_quests = (d.side_quests ?? []).map(s => ({ ...s }));
    g.willpower = d.willpower ?? 0;
    g.willpower_detached = d.willpower_detached ?? false;
    g.staging = d.staging ?? 0;
    g.pending_budget = d.pending_budget ?? 0;
    g.pending_elim = d.pending_elim ?? null;
    g.pending_quest_card = d.pending_quest_card ?? false;
    g.pending_side_quest_pick = d.pending_side_quest_pick ?? false;
    g.pending_progress_detail = d.pending_progress_detail ?? false;
    g.pending_location_detail = d.pending_location_detail ?? false;
    g.pending_progress_history = d.pending_progress_history ?? false;
    g.pending_quest_config = d.pending_quest_config ?? false;
    g.pending_side_quest_detail = d.pending_side_quest_detail ?? false;
    g.pending_location_pick = d.pending_location_pick ?? null;
    // A save written before this flag existed, resumed AT or AFTER the
    // refresh view, has already had its threat raised.
    g.refresh_applied = d.refresh_applied ??
      ["refresh", "aw_refresh", "round_end"].includes(d.view);
    // Same reasoning one field up: a save written before this flag existed,
    // resumed at or after the sailing test, has already shifted its heading.
    g.sailed_this_round = d.sailed_this_round ??
      (Boolean(d.sailing) &&
       !["resource", "aw_resource", "planning"].includes(d.view));
    g.quest_resolved = d.quest_resolved ?? false;
    g.quest_outcome = d.quest_outcome ?? null;
    g.quest_outcome_n = d.quest_outcome_n ?? 0;
    g.quest_history = (d.quest_history ?? []).map(e => ({ ...e }));
    g.sailing = d.sailing ?? false;
    g.heading = d.heading ?? 0;
    g.game_over = d.game_over ? { ...d.game_over } : null;
    g.pending_stage = d.pending_stage ? { ...d.pending_stage } : null;
    g.pending_resolution = d.pending_resolution ?? false;
    g.log = (d.log ?? []).map(e => ({ ...e }));
    g._seq = d.seq ?? 0;
    return g;
  }
}
