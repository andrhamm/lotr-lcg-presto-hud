"""Pure game-state logic for the LOTR LCG HUD.

No hardware imports — runs under CPython for host tests and under MicroPython
on the device. UI and hardware live elsewhere; this module only models state.
"""

import phases

MAX_PLAYERS = 4
DEFAULT_ELIMINATION = 50   # rulebook: eliminated when threat REACHES 50
DEFAULT_START_THREAT = 25  # varies by deck; editable per player at setup

# Guided per-round flow. quest_resolution is entered only via a successful
# resolve; advance_view otherwise skips from staging to travel.
VIEW_ORDER = ["resource_planning", "quest_commit", "quest_staging",
              "quest_resolution", "travel",
              "enc_optional", "enc_checks",
              "combat_shadow", "combat_enemy", "combat_player",
              "refresh"]

# view -> representative step id (for the phases screen / log tags / LEDs)
VIEW_STEP = {
    "setup_game": "0.0",
    "resource_planning": "1.R",
    "quest_sailing": "3.1",
    "quest_commit": "3.2",
    "quest_staging": "3.3",
    "quest_resolution": "3.4",
    "travel": "4.2",
    "enc_optional": "5.2",
    "enc_checks": "5.3",
    "combat_shadow": "6.2",
    "combat_enemy": "6.E",
    "combat_player": "6.P",
    "refresh": "7.R",
}


_PHASE_VIEW = {
    "Beginning": "resource_planning",
    "Resource": "resource_planning",
    "Planning": "resource_planning",
    "Quest": "quest_commit",
    "Travel": "travel",
    "Encounter": "enc_optional",
    "Combat": "combat_shadow",
    "Refresh": "refresh",
    "End": "refresh",
}
_STEP_VIEW = {}
for _v, _s in VIEW_STEP.items():
    _STEP_VIEW[_s] = _v
# encounter/combat later steps fall to the closest earlier view
_STEP_VIEW["5.3"] = "enc_checks"
_STEP_VIEW["5.4"] = "enc_checks"
_STEP_VIEW["6.11"] = "combat_player"
# jumping to 0.0 from the phases screen means round start, not game setup
_STEP_VIEW["0.0"] = "resource_planning"


def view_for_step(step_id):
    """Best view for a raw step id (exact match, else phase default)."""
    if step_id in _STEP_VIEW:
        return _STEP_VIEW[step_id]
    return _PHASE_VIEW[phases.step(step_id)["phase"]]


# Encounter reminders: (key, checkbox label, view that triggers the toast,
# toast text). Grounded in the rules/FAQ: archery resolves at combat start and
# is not blocked by defense; Surge/Doomed resolve on every reveal; Battle/Siege
# quests commit ATK/DEF; shadow cards are discarded at the end of combat; one
# Time counter is removed each refresh.
VIEW_LABELS = {
    "setup_game": "Setup",
    "resource_planning": "Resource & Planning",
    "quest_sailing": "Questing (Sailing)",
    "quest_commit": "Questing (Commit)",
    "quest_staging": "Questing (Staging)",
    "quest_resolution": "Questing (Resolution)",
    "travel": "Travel",
    "enc_optional": "Encounter (Opt. Engage)",
    "enc_checks": "Encounter (Checks)",
    "combat_shadow": "Combat (Shadow Cards)",
    "combat_enemy": "Combat (Enemy Attacks)",
    "combat_player": "Combat (Player Attacks)",
    "refresh": "Refresh",
}


def fmt_ms(ms):
    """1m35s-style duration for the log."""
    s = ms // 1000
    return "%dm%02ds" % (s // 60, s % 60)


# Setup guidance — the real confusion is the ORDER of effects during quest
# setup (rulebook p.10 + FAQ): resolve 1A's Setup text in printed order first;
# keywords on setup reveals (Surge / Doomed / Guarded) DO resolve; the
# encounter deck is shuffled AFTER any setup searches; only then flip 1A -> 1B.
SETUP_TIP = [
    "Draw 6 cards - one mulligan, you keep the 2nd hand.",
    "Resolve stage 1A Setup text in printed order.",
    "Keywords on setup reveals (Surge/Doomed) do resolve.",
    "Shuffle the encounter deck AFTER setup searches,",
    "then flip 1A -> 1B and begin.",
]

# Heading card facings, best -> worst (Grey Havens rulebook p.5). Only the sun
# facing is "on-course"; the rest are "off-course". Facing names are the
# official ones card text uses: "off-course (Cloudy, Rainy, or Stormy)".
# [term, icon, facing name, degree phrase]
HEADINGS = [
    ("On-course", "SUN", "Sunny", "best possible setting"),
    ("Off-course", "CLOUD", "Cloudy", "1 step off-course"),
    ("Off-course", "RAIN", "Rainy", "2 steps off-course"),
    ("Off-course", "STORM", "Stormy", "worst possible setting"),
]

# (key, label, view, notification text, icon name or None)
# (trimmed 2026-07-22: shadow-discard + Time counters dropped per user)
REMINDER_DEFS = [
    ("archery", "Archery damage", "combat_shadow",
     "Archery: deal damage now (defense does not block)", "ARCHERY"),
    ("battle", "Battle / Siege questing", "quest_commit",
     "Battle/Siege: commit ATK/DEF instead of willpower", None),
]


class Player:
    def __init__(self, label, starting_threat=0):
        self.label = label
        self.threat = starting_threat
        self.starting_threat = starting_threat
        self.threat_per_round = 1
        self.eliminated = False
        self.elimination = DEFAULT_ELIMINATION
        self.commit = 0  # willpower committed; persists as next round's default


class GameState:
    def __init__(self, player_count=4, starting_threat=0,
                 elimination_threat=DEFAULT_ELIMINATION):
        self.elimination_threat = elimination_threat
        self.players = [Player("P%d" % (i + 1), starting_threat)
                        for i in range(player_count)]
        for p in self.players:
            p.elimination = elimination_threat
        self.view = "setup_game"     # one-time setup phase precedes round 1
        self.clock = None            # ms time source injected by main (host: fake)
        self._round_snap = None      # {t, threats, progress} at round start
        self.round = 1
        self.first_player = 0
        self.step = phases.STEP_ORDER[0]
        self.quest = {"stage_n": 1, "side": "A", "points": 0, "progress": 0}
        self.active_location = None  # or {"points": int, "progress": int}
        self.side_quests = []        # list of {"points": int, "progress": int}
        self.willpower = 0           # transient questing input
        self.staging = 0             # transient questing input (staging area threat)
        self.pending_budget = 0      # success progress awaiting placement
        self.pending_elim = None     # player index that just crossed elimination
        self.reminders = {k: False for k, _, _, _, _ in REMINDER_DEFS}
        self.quest_resolved = False  # quest resolved this round
        self.quest_outcome = None    # "success" | "fail" | "tie" - last resolution
        self.quest_outcome_n = 0     # progress gained / threat taken
        self.sailing = False         # Dream-chaser Sailing test active
        self.heading = 0             # index into HEADINGS (0 = on-course)
        self.game_over = None        # or {"result", "round", "duration"}
        self.pending_stage = None    # or {"cleared", "excess"} awaiting new stage
        self.log = []                # oldest-first list of {seq, round, step, text}
        self._seq = 0

    # -- log ---------------------------------------------------------------
    def _now(self):
        return self.clock() if self.clock else None

    def log_event(self, text):
        """Append a log entry tagged with round, step, and session time."""
        self._seq += 1
        self.log.append({"seq": self._seq, "round": self.round,
                         "step": self.step, "text": text, "t": self._now()})

    def adjust_threat(self, index, delta):
        """Change a player's threat by delta, clamping at 0. Updates elimination."""
        p = self.players[index]
        was = p.eliminated
        p.threat = max(0, p.threat + delta)
        p.eliminated = p.threat >= p.elimination
        if p.eliminated and not was:
            self.pending_elim = index
        return p.threat

    def avert_elimination(self, index):
        """Card effect (e.g. Favor of the Valar): threat -> level - 5,
        the player is not eliminated."""
        p = self.players[index]
        p.threat = max(0, p.elimination - 5)
        p.eliminated = False
        if self.pending_elim == index:
            self.pending_elim = None
        self.log_event("P%d avoided elimination (card effect) - threat set to %d"
                       % (index + 1, p.threat))

    # High-end estimate of threat added by the staging reveal (1 card per
    # living player). Community quest analyses put the average revealed card
    # at ~1.4-1.6 threat with singles topping out near 3-4 and Surge chains
    # offset by 0-threat treacheries — so ~3x living players is a fair
    # worst-typical ceiling. (Deck distribution is fixed: round number and
    # current threat do not change the reveal odds.)
    STAGING_HIGH_PER_PLAYER = 3

    def staging_reveal_estimate(self):
        living = sum(1 for p in self.players if not p.eliminated)
        return living * self.STAGING_HIGH_PER_PLAYER

    def due_notifications(self):
        """Enabled reminder notifications for the current view. Archery only
        matters while there is threat (cards) in the staging area."""
        out = []
        for key, _label, view, text, icon in REMINDER_DEFS:
            if view != self.view or not self.reminders.get(key):
                continue
            if key == "archery" and self.staging <= 0:
                continue
            out.append((icon, text))
        return out

    def set_commit(self, index, value):
        """Set a player's committed willpower; total willpower = sum of commits."""
        self.players[index].commit = max(0, value)
        self.willpower = sum(p.commit for p in self.players)

    # -- view flow ---------------------------------------------------------
    def _total_progress(self):
        n = self.quest["progress"]
        if self.active_location:
            n += self.active_location["progress"]
        n += sum(s["progress"] for s in self.side_quests)
        return n

    def _snapshot_round(self):
        self._round_snap = {"t": self._now(),
                            "threats": [p.threat for p in self.players],
                            "progress": self._total_progress(),
                            "quest": self.quest["progress"]}

    def enter_view(self, v):
        """Central view transition: sets the step and logs the phase start."""
        self.view = v
        self.step = VIEW_STEP[v]
        self.log_event("Phase: %s" % VIEW_LABELS.get(v, v))

    def advance_view(self):
        """Move to the next view; staging skips resolution (that view is only
        entered by a successful resolve). The one-time setup phase leads into
        round 1 and is never revisited."""
        if self.view == "setup_game":
            self.log_event("Setup complete - round 1 begins (quest %s needs %d)"
                           % (self.quest_label(), self.quest["points"]))
            self.enter_view(VIEW_ORDER[0])
            self._snapshot_round()
            return
        if self.view == "quest_sailing":
            self.enter_view("quest_commit")
            return
        i = VIEW_ORDER.index(self.view)
        nxt = VIEW_ORDER[(i + 1) % len(VIEW_ORDER)]
        if self.view == "quest_staging":
            nxt = "travel"
        if self.view == "resource_planning" and self.sailing:
            nxt = "quest_sailing"
        self.enter_view(nxt)
        # a Sailing test begins by shifting one step off-course (rulebook p.6)
        if nxt == "quest_sailing":
            self.shift_heading(1, "winds shift")

    # -- sailing / game end ------------------------------------------------
    def heading_label(self):
        return HEADINGS[self.heading][0]

    def heading_desc(self):
        term, _icon, facing, _deg = HEADINGS[self.heading]
        return "%s (%s)" % (term, facing)

    def shift_heading(self, delta, why=""):
        to = max(0, min(len(HEADINGS) - 1, self.heading + delta))
        if to == self.heading:
            return False
        was = self.heading_desc()
        self.heading = to
        direction = "off-course" if delta > 0 else "on-course"
        self.log_event("Sailing: heading %s -> %s (shifted %s%s)"
                       % (was, self.heading_desc(), direction,
                          ", " + why if why else ""))
        return True

    def all_eliminated(self):
        return all(p.eliminated for p in self.players)

    def game_duration(self):
        t0 = self.log[0]["t"] if self.log else None
        now = self._now()
        return fmt_ms(now - t0) if (t0 is not None and now is not None) else None

    def set_game_over(self, result):
        if self.game_over:
            return
        self.game_over = {"result": result, "round": self.round,
                          "duration": self.game_duration()}
        self.log_event(
            "GAME OVER - Victory! The final quest stage is complete"
            if result == "victory"
            else "GAME OVER - Defeat. All players are eliminated")

    # -- travel ------------------------------------------------------------
    def _apply_travel_staging(self, contribution):
        """A traveled location leaves the staging area, taking its threat
        contribution with it."""
        if contribution > 0 and self.staging > 0:
            before = self.staging
            self.staging = max(0, self.staging - contribution)
            self.log_event("Staging area threat %d -> %d (traveled location)"
                           % (before, self.staging))

    def travel_to(self, points, contribution=0):
        self.active_location = {"points": points, "progress": 0}
        self.log_event("Traveled to new location (%d quest points)" % points)
        self._apply_travel_staging(contribution)

    def change_location(self, points, contribution=0):
        old = self.active_location
        self.active_location = {"points": points, "progress": 0}
        if old:
            self.log_event(
                "Changed active location (old at %d/%d discarded) -> new (%d quest points)"
                % (old["progress"], old["points"], points))
        else:
            self.log_event("Changed active location -> new (%d quest points)" % points)
        self._apply_travel_staging(contribution)

    def explore_location_if_done(self):
        """A location at its quest points is Explored - remove it from the row."""
        loc = self.active_location
        if loc and loc["points"] > 0 and loc["progress"] >= loc["points"]:
            self.log_event("Active location Explored (%d/%d) - removed"
                           % (loc["progress"], loc["points"]))
            self.active_location = None
            return True
        return False

    # -- step navigation ---------------------------------------------------
    def action_window_open(self):
        """True if the current step opens a player-action window."""
        return phases.step(self.step)["action_window"]

    def next_step(self):
        """Advance to the next step; past the last step ends the round."""
        i = phases.step_index(self.step)
        if i >= len(phases.STEP_ORDER) - 1:
            self.end_round()
        else:
            self.step = phases.STEP_ORDER[i + 1]

    def prev_step(self):
        """Move to the previous step; stays put at the first step."""
        i = phases.step_index(self.step)
        if i > 0:
            self.step = phases.STEP_ORDER[i - 1]

    # -- round flow --------------------------------------------------------
    def end_round(self):
        """Raise threat, rotate first player, bump round, reset to first step."""
        for p in self.players:
            if not p.eliminated:
                self.adjust_threat(self.players.index(p), p.threat_per_round)
        # round stats: duration + per-player threat deltas + progress gained
        snap = self._round_snap
        if snap:
            parts = []
            if snap["t"] is not None and self._now() is not None:
                parts.append(fmt_ms(self._now() - snap["t"]))
            for i, p in enumerate(self.players):
                d = p.threat - snap["threats"][i]
                if d:
                    parts.append("P%d %+d" % (i + 1, d))
            pd = self._total_progress() - snap["progress"]
            if pd:
                parts.append("quest %+d" % pd)
            self.log_event("Round %d ended: %s" % (self.round, ", ".join(parts) if parts else "no changes"))
        self.first_player = (self.first_player + 1) % len(self.players)
        self.round += 1
        self.step = phases.STEP_ORDER[0]
        self.view = VIEW_ORDER[0]    # rounds never revisit the setup phase
        # commits persist as next round's defaults; refresh the derived total
        self.willpower = sum(p.commit for p in self.players)
        self.quest_resolved = False
        self.quest_outcome = None
        self.log_event("New round %d - threat raised, first player -> P%d"
                       % (self.round, self.first_player + 1))
        self.log_event("Phase: %s" % VIEW_LABELS[VIEW_ORDER[0]])
        self._snapshot_round()

    # -- quest / progress --------------------------------------------------
    def quest_label(self):
        return "%d%s" % (self.quest["stage_n"], self.quest["side"])

    def auto_split(self, budget):
        """Fill the active location, then the quest - each capped at its own
        quest points. Side quests are left untouched; any overflow beyond
        location + quest capacity is discarded."""
        alloc = {"location": 0, "quest": 0, "side_quests": [0] * len(self.side_quests)}
        remaining = budget
        if self.active_location is not None:
            room = max(0, self.active_location["points"] - self.active_location["progress"])
            alloc["location"] = min(remaining, room)
            remaining -= alloc["location"]
        qroom = max(0, self.quest["points"] - self.quest["progress"])
        alloc["quest"] = min(remaining, qroom)
        return alloc

    def place_progress(self, alloc):
        """Apply an allocation. Returns a list of completion messages."""
        completed = []

        n = alloc.get("location", 0)
        if n and self.active_location is not None:
            self.active_location["progress"] += n
            if self.active_location["progress"] >= self.active_location["points"]:
                completed.append("Active Location explored")
                self.active_location = None

        n = alloc.get("quest", 0)
        if n:
            self.quest["progress"] += n
            if self.quest["points"] > 0 and self.quest["progress"] >= self.quest["points"]:
                was = self.quest_label()
                excess = self.quest["progress"] - self.quest["points"]
                self._advance_quest_stage()
                self.quest["points"] = 0
                self.pending_stage = {"cleared": was, "excess": excess}
                completed.append("Quest %s cleared" % was)

        for i in range(len(self.side_quests) - 1, -1, -1):
            add = alloc.get("side_quests", [])
            n = add[i] if i < len(add) else 0
            if not n:
                continue
            self.side_quests[i]["progress"] += n
            if self.side_quests[i]["progress"] >= self.side_quests[i]["points"]:
                completed.append("Side quest %d completed" % (i + 1))
                self.side_quests.pop(i)

        return completed

    def _advance_quest_stage(self):
        if self.quest["side"] == "A":
            self.quest["side"] = "B"
        else:
            self.quest["side"] = "A"
            self.quest["stage_n"] += 1
        self.quest["progress"] = 0

    def resolve_quest(self, willpower, staging):
        """Compare willpower vs staging threat. Returns an outcome dict.

        success (willpower > staging): returns budget for the allocation modal;
        does NOT place progress. fail (willpower < staging): raises each living
        player's threat by the shortfall. tie: no change.
        """
        diff = willpower - staging
        self.quest_resolved = True
        if diff > 0:
            self.quest_outcome = "success"
            self.quest_outcome_n = diff
            return {"outcome": "success", "budget": diff}
        if diff < 0:
            shortfall = -diff
            for i, p in enumerate(self.players):
                if not p.eliminated:
                    self.adjust_threat(i, shortfall)
            self.log_event("Quest failed. +%d threat to all" % shortfall)
            self.quest_outcome = "fail"
            self.quest_outcome_n = shortfall
            return {"outcome": "fail", "threat": shortfall}
        self.log_event("Quest unsuccessful - tie, no change")
        self.quest_outcome = "tie"
        self.quest_outcome_n = 0
        return {"outcome": "tie"}

    # -- persistence -------------------------------------------------------
    def to_dict(self):
        return {
            "players": [{"label": p.label, "threat": p.threat,
                         "starting_threat": p.starting_threat,
                         "threat_per_round": p.threat_per_round,
                         "eliminated": p.eliminated,
                         "elimination": p.elimination,
                         "commit": p.commit} for p in self.players],
            "view": self.view,
            "round": self.round,
            "first_player": self.first_player,
            "step": self.step,
            "quest": dict(self.quest),
            "active_location": dict(self.active_location) if self.active_location else None,
            "side_quests": [dict(s) for s in self.side_quests],
            "willpower": self.willpower,
            "staging": self.staging,
            "pending_budget": self.pending_budget,
            "pending_elim": self.pending_elim,
            "reminders": dict(self.reminders),
            "quest_resolved": self.quest_resolved,
            "quest_outcome": self.quest_outcome,
            "quest_outcome_n": self.quest_outcome_n,
            "sailing": self.sailing,
            "heading": self.heading,
            "game_over": dict(self.game_over) if self.game_over else None,
            "pending_stage": dict(self.pending_stage) if self.pending_stage else None,
            "elimination_threat": self.elimination_threat,
            "log": [dict(e) for e in self.log],
            "seq": self._seq,
        }

    @classmethod
    def from_dict(cls, d):
        g = cls()
        g.elimination_threat = d.get("elimination_threat", DEFAULT_ELIMINATION)
        g.players = []
        for pd in d["players"]:
            p = Player(pd["label"])
            p.threat = pd["threat"]
            p.starting_threat = pd["starting_threat"]
            p.threat_per_round = pd["threat_per_round"]
            p.eliminated = pd["eliminated"]
            p.elimination = pd.get("elimination", DEFAULT_ELIMINATION)
            p.commit = pd.get("commit", 0)
            g.players.append(p)
        g.view = d.get("view", VIEW_ORDER[0])
        g.round = d["round"]
        g.first_player = d["first_player"]
        g.step = d["step"]
        g.quest = dict(d["quest"])
        g.active_location = dict(d["active_location"]) if d["active_location"] else None
        g.side_quests = [dict(s) for s in d["side_quests"]]
        g.willpower = d.get("willpower", 0)
        g.staging = d.get("staging", 0)
        g.pending_budget = d.get("pending_budget", 0)
        g.pending_elim = d.get("pending_elim", None)
        g.reminders = {k: False for k, _, _, _, _ in REMINDER_DEFS}
        saved_rem = d.get("reminders", {})
        for k in g.reminders:
            if k in saved_rem:
                g.reminders[k] = saved_rem[k]
        g.quest_resolved = d.get("quest_resolved", False)
        g.quest_outcome = d.get("quest_outcome", None)
        g.quest_outcome_n = d.get("quest_outcome_n", 0)
        g.sailing = d.get("sailing", False)
        g.heading = d.get("heading", 0)
        go = d.get("game_over", None)
        g.game_over = dict(go) if go else None
        ps = d.get("pending_stage", None)
        g.pending_stage = dict(ps) if ps else None
        g.log = [dict(e) for e in d["log"]]
        g._seq = d["seq"]
        return g
