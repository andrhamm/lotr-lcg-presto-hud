// Port of gamestate.py — method-for-method. Keep the two in lockstep:
// web-first changes land here, then mirror into gamestate.py.
import { STEP_ORDER, step as phaseStep } from "./phases.js";

export const MAX_PLAYERS = 4;
export const DEFAULT_ELIMINATION = 50;
export const DEFAULT_START_THREAT = 25;

export const VIEW_ORDER = ["resource_planning", "quest_commit", "quest_staging",
  "quest_resolution", "travel", "enc_optional", "enc_checks",
  "combat_shadow", "combat_enemy", "combat_player", "refresh"];

export const VIEW_STEP = {
  setup_game: "0.0", quest_setup: "0.0", resource_planning: "1.R", quest_sailing: "3.1",
  quest_commit: "3.2",
  quest_staging: "3.3", quest_resolution: "3.4", travel: "4.2",
  enc_optional: "5.2", enc_checks: "5.3", combat_shadow: "6.2",
  combat_enemy: "6.E", combat_player: "6.P", refresh: "7.R",
};

export const VIEW_LABELS = {
  setup_game: "Setup", quest_setup: "Quest Setup", resource_planning: "Resource & Planning",
  quest_sailing: "Questing (Sailing)", quest_commit: "Questing (Commit)", quest_staging: "Questing (Staging)",
  quest_resolution: "Questing (Resolution)", travel: "Travel",
  enc_optional: "Encounter (Opt. Engage)", enc_checks: "Encounter (Checks)",
  combat_shadow: "Combat (Shadow Cards)", combat_enemy: "Combat (Enemy Attacks)",
  combat_player: "Combat (Player Attacks)", refresh: "Refresh",
};

const PHASE_VIEW = {
  Beginning: "resource_planning", Resource: "resource_planning",
  Planning: "resource_planning", Quest: "quest_commit", Travel: "travel",
  Encounter: "enc_optional", Combat: "combat_shadow", Refresh: "refresh",
  End: "refresh",
};
const STEP_VIEW = {};
for (const [v, s] of Object.entries(VIEW_STEP)) STEP_VIEW[s] = v;
STEP_VIEW["5.3"] = "enc_checks";
STEP_VIEW["5.4"] = "enc_checks";
STEP_VIEW["6.11"] = "combat_player";
STEP_VIEW["0.0"] = "resource_planning";

export function viewForStep(stepId) {
  if (stepId in STEP_VIEW) return STEP_VIEW[stepId];
  return PHASE_VIEW[phaseStep(stepId).phase];
}

export function fmtMs(ms) {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}m${String(s % 60).padStart(2, "0")}s`;
}

export const SETUP_TIP = [
  "Draw 6 cards - one mulligan, you keep the 2nd hand.",
  "Resolve stage 1A Setup text in printed order.",
  "Keywords on setup reveals (Surge/Doomed) do resolve.",
  "Shuffle the encounter deck AFTER setup searches,",
  "then flip 1A -> 1B and begin.",
];

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

// [key, label, view, notification text, icon name or null]
// (trimmed 2026-07-22: shadow-discard + Time counters dropped per user)
export const REMINDER_DEFS = [
  ["archery", "Archery damage", "combat_shadow",
    "Archery: deal damage now (defense does not block)", "ARCHERY"],
  ["battle", "Battle / Siege questing", "quest_commit",
    "Battle/Siege: commit ATK/DEF instead of willpower", null],
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
    this.commit_touched = false;
  }
}

export class GameState {
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
    this.view = "setup_game";
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
    this.active_location = null;
    this.side_quests = [];       // {points, progress, name?} - name is optional
                                  // (absent/null on old saves)
    this.willpower = 0;
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
    this.reminders = Object.fromEntries(REMINDER_DEFS.map(d => [d[0], false]));
    this.quest_resolved = false;
    this.quest_outcome = null;      // "success" | "fail" | "tie" - last resolution
    this.quest_outcome_n = 0;       // progress gained / threat taken
    this.quest_history = [];        // by-round chart data, capped at last 20
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
    this.messages = [];      // this action's log text, drained into the delta.
                             // Mirrors game["messages"].
    this._replay_moved = false;  // a cursor move happened inside the current
                                 // recording window - see addDelta
  }

  _now() { return this.clock ? this.clock() : null; }

  logEvent(text) {
    this._seq += 1;
    this.log.push({ seq: this._seq, round: this.round, step: this.step,
                    text, t: this._now() });
    this.messages.push(text);
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

  stagingRevealEstimate() {
    const living = this.players.filter(p => !p.eliminated).length;
    return living * GameState.STAGING_HIGH_PER_PLAYER;
  }

  dueNotifications() {
    const out = [];
    for (const [key, _label, view, text, icon] of REMINDER_DEFS) {
      if (view !== this.view || !this.reminders[key]) continue;
      if (key === "archery" && this.staging <= 0) continue;
      out.push([icon, text]);
    }
    return out;
  }

  setCommit(index, value) {
    this.players[index].commit = Math.max(0, value);
    this.players[index].commit_touched = true;
    this.willpower = this.players.reduce((a, p) => a + p.commit, 0);
  }

  touchCommit(i) {
    this.players[i].commit_touched = true;
  }

  confirmAllCommits() {
    // One-tap "same as last round": marks every living player's willpower
    // commit as reviewed (ring goes gold) without changing any value.
    this.players.forEach(p => { if (!p.eliminated) p.commit_touched = true; });
  }

  _totalProgress() {
    let n = this.quest.progress;
    if (this.active_location) n += this.active_location.progress;
    for (const s of this.side_quests) n += s.progress;
    return n;
  }

  _snapshotRound() {
    this._round_snap = { t: this._now(),
                         threats: this.players.map(p => p.threat),
                         progress: this._totalProgress(),
                         quest: this.quest.progress };
  }

  enterView(v) {
    this.view = v;
    this.step = VIEW_STEP[v];
    this.logEvent(`Phase: ${VIEW_LABELS[v] ?? v}`);
  }

  advanceView() {
    if (this.view === "setup_game") {
      this.logEvent(`Setup complete - round 1 begins (quest ${this.questLabel()} needs ${this.quest.points})`);
      this.enterView(VIEW_ORDER[0]);
      this.players.forEach(p => p.commit_touched = false);
      this._snapshotRound();
      return;
    }
    if (this.view === "quest_sailing") { this.enterView("quest_commit"); return; }
    const i = VIEW_ORDER.indexOf(this.view);
    let nxt = VIEW_ORDER[(i + 1) % VIEW_ORDER.length];
    if (this.view === "quest_staging") nxt = "travel";
    if (this.view === "resource_planning" && this.sailing) nxt = "quest_sailing";
    this.enterView(nxt);
    // a Sailing test begins by shifting one step off-course (rulebook p.6)
    if (nxt === "quest_sailing") this.shiftHeading(1, "winds shift");
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
  _seatLocation(points, name) {
    const loc = { points, progress: 0 };
    if (name) loc.name = name;
    return loc;
  }

  travelTo(points, contribution = 0, name = null) {
    this.active_location = this._seatLocation(points, name);
    this.logEvent(`Traveled to ${name || "new location"} (${points} quest points)`);
    this._applyTravelStaging(contribution);
  }

  changeLocation(points, contribution = 0, name = null) {
    const old = this.active_location;
    this.active_location = this._seatLocation(points, name);
    const newLabel = name || "new";
    if (old) {
      this.logEvent(`Changed active location (${old.name || "old"} at ${old.progress}/${old.points} discarded) -> ${newLabel} (${points} quest points)`);
    } else {
      this.logEvent(`Changed active location -> ${newLabel} (${points} quest points)`);
    }
    this._applyTravelStaging(contribution);
  }

  // A location at its quest points is Explored - remove it from the row.
  exploreLocationIfDone() {
    const loc = this.active_location;
    if (loc && loc.points > 0 && loc.progress >= loc.points) {
      this.logEvent(`Active location Explored (${loc.progress}/${loc.points}) - removed`);
      this.active_location = null;
      return true;
    }
    return false;
  }

  actionWindowOpen() { return phaseStep(this.step).action_window; }

  endRound() {
    for (let i = 0; i < this.players.length; i++) {
      if (!this.players[i].eliminated) {
        this.adjustThreat(i, this.players[i].threat_per_round);
      }
    }
    this.players.forEach(p => p.commit_touched = false);
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
    this.first_player = (this.first_player + 1) % this.players.length;
    this.round += 1;
    this.step = STEP_ORDER[0];
    this.view = VIEW_ORDER[0];
    this.willpower = this.players.reduce((a, p) => a + p.commit, 0);
    this.quest_resolved = false;
    this.quest_outcome = null;
    this.logEvent(`New round ${this.round} - threat raised, first player -> P${this.first_player + 1}`);
    this.logEvent(`Phase: ${VIEW_LABELS[VIEW_ORDER[0]]}`);
    this._snapshotRound();
  }

  // Load a quest-picker scenario: scn is metadata (slug/name/pack/...),
  // stages is the stage/card tree. Resets quest to stage 1 side A.
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
  flipToB() {
    const card = this.stages[this.stage_idx].cards[this.card_idx];
    this.quest.side = "B";
    this.quest.points = card.questPoints;
    return this.quest.points;
  }

  questLabel() { return `${this.quest.stage_n}${this.quest.side}`; }

  autoSplit(budget) {
    // Fill the active location, then the quest - each capped at its own
    // quest points. Side quests are left untouched; any overflow beyond
    // location + quest capacity is discarded.
    const alloc = { location: 0, quest: 0,
                    side_quests: this.side_quests.map(() => 0) };
    let remaining = budget;
    if (this.active_location) {
      const room = Math.max(0, this.active_location.points - this.active_location.progress);
      alloc.location = Math.min(remaining, room);
      remaining -= alloc.location;
    }
    const qroom = Math.max(0, this.quest.points - this.quest.progress);
    alloc.quest = Math.min(remaining, qroom);
    return alloc;
  }

  needsResolution() {
    // True if the active location, the quest, or any side quest is
    // currently at/over its own (positive) quest points - the trigger for
    // the guided resolution flow after a manual progress edit.
    const loc = this.active_location;
    if (loc && loc.points > 0 && loc.progress >= loc.points) return true;
    if (this.quest.points > 0 && this.quest.progress >= this.quest.points) return true;
    return this.side_quests.some(s => s.points > 0 && s.progress >= s.points);
  }

  resolveLocationOverflow() {
    // Active location at/over its points: explore it (rulebook p.15),
    // crediting any excess progress to the quest card. No-op (returns 0)
    // if there's no active location or it hasn't reached its points.
    const loc = this.active_location;
    if (!loc || loc.points <= 0 || loc.progress < loc.points) return 0;
    const excess = loc.progress - loc.points;
    this.logEvent(`Active location Explored (${loc.progress}/${loc.points})` +
                  (excess ? ` - ${excess} excess to quest` : ""));
    this.active_location = null;
    if (excess) this.quest.progress += excess;
    return excess;
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
    let n = alloc.location ?? 0;
    if (n && this.active_location) {
      this.active_location.progress += n;
      if (this.active_location.progress >= this.active_location.points) {
        completed.push("Active Location explored");
        this.active_location = null;
      }
    }
    n = alloc.quest ?? 0;
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
      this.logEvent(`Quest failed. +${shortfall} threat to all`);
      outcome = "fail"; n = shortfall;
      result = { outcome, threat: n };
    } else {
      this.logEvent("Quest unsuccessful - tie, no change");
      outcome = "tie"; n = 0;
      result = { outcome };
    }
    this.quest_outcome = outcome;
    this.quest_outcome_n = n;
    this.quest_history.push({
      round: this.round, willpower, staging, outcome, n, heading: this.heading });
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
        commit: p.commit, commit_touched: p.commit_touched }])),
      quest: { ...this.quest },
      active_location: this.active_location ? { ...this.active_location } : null,
      side_quests: keyed(this.side_quests),
      quest_history: keyed(this.quest_history),
      willpower: this.willpower,
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
      p.commit_touched = pd.commit_touched;
    });
    this.quest = { ...m.quest };
    this.active_location = m.active_location ? { ...m.active_location } : null;
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
    // A fresh action after an undo discards the redo future.
    this.deltas = this.deltas.slice(0, this.replay_step + 1);
    this.deltas.push(d);
    this.replay_step = this.deltas.length - 1;
    // Stamp this action's log entries with their delta index so the Log screen
    // can offer a jump target per row without matching on text. logEvent
    // appends to log and messages together, so the last N entries are ours.
    const n = this.messages.length;
    if (n) for (const e of this.log.slice(-n)) e.delta_i = this.replay_step;
    this.messages = [];
    if (this.deltas.length > MAX_SAVED_DELTAS) {
      const drop = this.deltas.length - MAX_SAVED_DELTAS;
      this.deltas = this.deltas.slice(drop);
      this.replay_step -= drop;
      for (const e of this.log) {
        if ("delta_i" in e) e.delta_i -= drop;   // may go negative: not a target
      }
    }
    return true;
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
    if (size === "single") return this.stepReplay(options.direction);
    if (size === "round") return this.applyDeltasUntilRoundChange(options.direction);
    if (size === "index") return this.applyDeltasUntilIndex(options.index);
    return false;
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

  replayFromDict(d) {
    this.deltas = [];
    this.replay_step = -1;
    if (!d || typeof d !== "object" || Array.isArray(d)) return;
    const ds = d.deltas;
    if (!Array.isArray(ds) || !ds.every(x => x && typeof x === "object" && !Array.isArray(x))) return;
    this.deltas = ds;
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
        elimination: p.elimination, commit: p.commit, commit_touched: p.commit_touched })),
      view: this.view, round: this.round, first_player: this.first_player,
      step: this.step, quest: { ...this.quest },
      scenario: this.scenario, stages: this.stages,
      stage_idx: this.stage_idx, card_idx: this.card_idx,
      active_location: this.active_location ? { ...this.active_location } : null,
      side_quests: this.side_quests.map(s => ({ ...s })),
      willpower: this.willpower, staging: this.staging,
      pending_budget: this.pending_budget, pending_elim: this.pending_elim,
      pending_quest_card: this.pending_quest_card,
      pending_side_quest_pick: this.pending_side_quest_pick,
      pending_progress_detail: this.pending_progress_detail,
      pending_location_pick: this.pending_location_pick,
      reminders: { ...this.reminders },
      elimination_threat: this.elimination_threat,
      quest_resolved: this.quest_resolved,
      quest_outcome: this.quest_outcome, quest_outcome_n: this.quest_outcome_n,
      quest_history: this.quest_history.map(e => ({ ...e })),
      sailing: this.sailing, heading: this.heading,
      game_over: this.game_over ? { ...this.game_over } : null,
      pending_stage: this.pending_stage ? { ...this.pending_stage } : null,
      pending_resolution: this.pending_resolution,
      log: this.log.map(e => ({ ...e })), seq: this._seq,
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
      p.commit_touched = pd.commit_touched ?? false;
      return p;
    });
    g.view = d.view ?? VIEW_ORDER[0];
    g.round = d.round;
    g.first_player = d.first_player;
    g.step = d.step;
    g.quest = { ...d.quest };
    g.scenario = d.scenario ?? null;
    g.stages = d.stages ?? [];
    g.stage_idx = d.stage_idx ?? 0;
    g.card_idx = d.card_idx ?? 0;
    g.active_location = d.active_location ? { ...d.active_location } : null;
    g.side_quests = (d.side_quests ?? []).map(s => ({ ...s }));
    g.willpower = d.willpower ?? 0;
    g.staging = d.staging ?? 0;
    g.pending_budget = d.pending_budget ?? 0;
    g.pending_elim = d.pending_elim ?? null;
    g.pending_quest_card = d.pending_quest_card ?? false;
    g.pending_side_quest_pick = d.pending_side_quest_pick ?? false;
    g.pending_progress_detail = d.pending_progress_detail ?? false;
    g.pending_location_pick = d.pending_location_pick ?? null;
    g.reminders = Object.fromEntries(REMINDER_DEFS.map(dd => [dd[0], false]));
    for (const k of Object.keys(g.reminders)) {
      if (d.reminders && k in d.reminders) g.reminders[k] = d.reminders[k];
    }
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
