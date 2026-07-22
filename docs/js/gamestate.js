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
  setup_game: "0.0", resource_planning: "1.R", quest_sailing: "3.1",
  quest_commit: "3.2",
  quest_staging: "3.3", quest_resolution: "3.4", travel: "4.2",
  enc_optional: "5.2", enc_checks: "5.3", combat_shadow: "6.2",
  combat_enemy: "6.E", combat_player: "6.P", refresh: "7.R",
};

export const VIEW_LABELS = {
  setup_game: "Setup", resource_planning: "Resource & Planning",
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
    this.active_location = null;
    this.side_quests = [];
    this.willpower = 0;
    this.staging = 0;
    this.pending_budget = 0;
    this.pending_elim = null;
    this.reminders = Object.fromEntries(REMINDER_DEFS.map(d => [d[0], false]));
    this.quest_resolved = false;
    this.quest_outcome = null;      // "success" | "fail" | "tie" - last resolution
    this.quest_outcome_n = 0;       // progress gained / threat taken
    this.sailing = false;
    this.heading = 0;
    this.game_over = null;
    this.pending_stage = null;
    this.log = [];
    this._seq = 0;
  }

  _now() { return this.clock ? this.clock() : null; }

  logEvent(text) {
    this._seq += 1;
    this.log.push({ seq: this._seq, round: this.round, step: this.step,
                    text, t: this._now() });
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
    this.willpower = this.players.reduce((a, p) => a + p.commit, 0);
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

  travelTo(points, contribution = 0) {
    this.active_location = { points, progress: 0 };
    this.logEvent(`Traveled to new location (${points} quest points)`);
    this._applyTravelStaging(contribution);
  }

  changeLocation(points, contribution = 0) {
    const old = this.active_location;
    this.active_location = { points, progress: 0 };
    if (old) {
      this.logEvent(`Changed active location (old at ${old.progress}/${old.points} discarded) -> new (${points} quest points)`);
    } else {
      this.logEvent(`Changed active location -> new (${points} quest points)`);
    }
    this._applyTravelStaging(contribution);
  }

  actionWindowOpen() { return phaseStep(this.step).action_window; }

  endRound() {
    for (let i = 0; i < this.players.length; i++) {
      if (!this.players[i].eliminated) {
        this.adjustThreat(i, this.players[i].threat_per_round);
      }
    }
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

  questLabel() { return `${this.quest.stage_n}${this.quest.side}`; }

  autoSplit(budget) {
    const alloc = { location: 0, quest: 0,
                    side_quests: this.side_quests.map(() => 0) };
    let remaining = budget;
    if (this.active_location) {
      const room = Math.max(0, this.active_location.points - this.active_location.progress);
      const toLoc = Math.min(remaining, room);
      alloc.location = toLoc;
      remaining -= toLoc;
    }
    alloc.quest = remaining;
    return alloc;
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
        const excess = this.quest.progress - this.quest.points;
        this._advanceQuestStage();
        this.quest.points = 0;
        this.pending_stage = { cleared: was, excess };
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
    if (diff > 0) {
      this.quest_outcome = "success"; this.quest_outcome_n = diff;
      return { outcome: "success", budget: diff };
    }
    if (diff < 0) {
      const shortfall = -diff;
      this.players.forEach((p, i) => { if (!p.eliminated) this.adjustThreat(i, shortfall); });
      this.logEvent(`Quest failed. +${shortfall} threat to all`);
      this.quest_outcome = "fail"; this.quest_outcome_n = shortfall;
      return { outcome: "fail", threat: shortfall };
    }
    this.logEvent("Quest unsuccessful - tie, no change");
    this.quest_outcome = "tie"; this.quest_outcome_n = 0;
    return { outcome: "tie" };
  }

  toDict() {
    return {
      players: this.players.map(p => ({
        label: p.label, threat: p.threat, starting_threat: p.starting_threat,
        threat_per_round: p.threat_per_round, eliminated: p.eliminated,
        elimination: p.elimination, commit: p.commit })),
      view: this.view, round: this.round, first_player: this.first_player,
      step: this.step, quest: { ...this.quest },
      active_location: this.active_location ? { ...this.active_location } : null,
      side_quests: this.side_quests.map(s => ({ ...s })),
      willpower: this.willpower, staging: this.staging,
      pending_budget: this.pending_budget, pending_elim: this.pending_elim,
      reminders: { ...this.reminders },
      elimination_threat: this.elimination_threat,
      quest_resolved: this.quest_resolved,
      quest_outcome: this.quest_outcome, quest_outcome_n: this.quest_outcome_n,
      sailing: this.sailing, heading: this.heading,
      game_over: this.game_over ? { ...this.game_over } : null,
      pending_stage: this.pending_stage ? { ...this.pending_stage } : null,
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
      return p;
    });
    g.view = d.view ?? VIEW_ORDER[0];
    g.round = d.round;
    g.first_player = d.first_player;
    g.step = d.step;
    g.quest = { ...d.quest };
    g.active_location = d.active_location ? { ...d.active_location } : null;
    g.side_quests = (d.side_quests ?? []).map(s => ({ ...s }));
    g.willpower = d.willpower ?? 0;
    g.staging = d.staging ?? 0;
    g.pending_budget = d.pending_budget ?? 0;
    g.pending_elim = d.pending_elim ?? null;
    g.reminders = Object.fromEntries(REMINDER_DEFS.map(dd => [dd[0], false]));
    for (const k of Object.keys(g.reminders)) {
      if (d.reminders && k in d.reminders) g.reminders[k] = d.reminders[k];
    }
    g.quest_resolved = d.quest_resolved ?? false;
    g.quest_outcome = d.quest_outcome ?? null;
    g.quest_outcome_n = d.quest_outcome_n ?? 0;
    g.sailing = d.sailing ?? false;
    g.heading = d.heading ?? 0;
    g.game_over = d.game_over ? { ...d.game_over } : null;
    g.pending_stage = d.pending_stage ? { ...d.pending_stage } : null;
    g.log = (d.log ?? []).map(e => ({ ...e }));
    g._seq = d.seq ?? 0;
    return g;
  }
}
