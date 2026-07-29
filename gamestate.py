"""Pure game-state logic for the LOTR LCG HUD.

No hardware imports — runs under CPython for host tests and under MicroPython
on the device. UI and hardware live elsewhere; this module only models state.
"""

import json

import phases
# Play-screen copy lives in one place so the web twin can be generated from
# it rather than hand-mirrored. Re-exported here because callers and tests
# have imported these names from gamestate since before viewcopy existed.
from viewcopy import (VIEW_LABELS, SETUP_TIP, ACTION_WINDOW_TIPS,  # noqa: F401
                      OUTCOME)

MAX_PLAYERS = 4
DEFAULT_ELIMINATION = 50   # rulebook: eliminated when threat REACHES 50
DEFAULT_START_THREAT = 25  # varies by deck; editable per player at setup

# Guided per-round flow. quest_resolution is entered only via a successful
# resolve; advance_view otherwise skips from staging to travel.
# A window view is "aw_" + the view whose step it follows. They are real views
# rather than screen-local state so that undo, save/resume and delta replay all
# work on them for free - snapshot() already carries `view` and `step`.
VIEW_ORDER = ["resource", "aw_resource",
              "planning",
              "quest_commit", "aw_quest_commit",
              "quest_staging", "aw_quest_staging",
              "quest_resolution", "aw_quest_resolution",
              "travel", "aw_travel",
              "enc_optional", "aw_enc_optional",
              "enc_checks", "aw_enc_checks",
              "combat_shadow", "combat_enemy", "combat_player",
              "refresh", "aw_refresh"]

WINDOW_PREFIX = "aw_"


def is_window_view(v):
    """True for the interstitial action-window screens."""
    return v.startswith(WINDOW_PREFIX)


def phase_view_of(v):
    """The phase view a window view follows (identity for phase views)."""
    return v[len(WINDOW_PREFIX):] if is_window_view(v) else v


def window_after(v):
    """The window view that follows `v`, or None.

    Single predicate so the frequency policy is one function. Currently every
    window is always in the flow; a "once per game" or "off" policy would be a
    change here and nowhere else.
    """
    w = WINDOW_PREFIX + v
    return w if w in VIEW_STEP else None

# view -> representative step id (for the phases screen / log tags / LEDs)
VIEW_STEP = {
    "setup_game": "0.0",
    "quest_setup": "0.0",
    "resource": "1.R",
    "planning": "2.P",
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
# Window views share the step they follow: the window IS that step's window.
for _pv in ("resource", "quest_commit", "quest_staging", "quest_resolution",
            "travel", "enc_optional", "enc_checks", "refresh"):
    VIEW_STEP["aw_" + _pv] = VIEW_STEP[_pv]


_PHASE_VIEW = {
    "Beginning": "resource",
    "Resource": "resource",
    "Planning": "planning",
    "Quest": "quest_commit",
    "Travel": "travel",
    "Encounter": "enc_optional",
    "Combat": "combat_shadow",
    "Refresh": "refresh",
    "End": "refresh",
}
# Built from PHASE views only. A blanket inversion is last-wins, so the window
# views would capture their shared step and a phases-screen jump to 3.3 would
# land on the window instead of Staging.
_STEP_VIEW = {}
for _v, _s in VIEW_STEP.items():
    if not is_window_view(_v):
        _STEP_VIEW[_s] = _v
# encounter/combat later steps fall to the closest earlier view
_STEP_VIEW["5.3"] = "enc_checks"
_STEP_VIEW["5.4"] = "enc_checks"
_STEP_VIEW["6.11"] = "combat_player"
# jumping to 0.0 from the phases screen means round start, not game setup
_STEP_VIEW["0.0"] = "resource"


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


def fmt_ms(ms):
    """1m35s-style duration for the log."""
    s = ms // 1000
    return "%dm%02ds" % (s // 60, s % 60)




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


# ---------------------------------------------------------------------------
# Delta replay engine.
#
# Ported at parity from DragnCards (seastan/DragnCards @ a79716f9),
# backend/lib/dragncards_game/ui/game_ui.ex: get_delta/2, delta/2,
# apply_delta/3, apply_delta_list/3. Names and semantics are the reference's;
# see docs/superpowers/plans/2026-07-26-delta-replay-parity.md for the four
# deliberate divergences.
#
# A delta mirrors the shape of the state it describes. Every changed leaf is a
# two-element [old, new] pair, which is what lets ONE apply function serve both
# directions: index 0 undoes, index 1 redoes.
# ---------------------------------------------------------------------------

REMOVED = ":removed"       # sentinel: the key does not exist on this side
MAX_SAVED_DELTAS = 500     # ~47 KB, ~31 rounds. Reference caps at 5 for
                           # non-supporters (game.ex trim_saved_deltas/2);
                           # we have no paywall, just a bound.


def get_delta(old, new):
    """Recursive structural diff. Returns None when nothing changed.

    Parity note: recursion happens only when BOTH sides are dicts. Elixir's
    map_diff has the same guard (`when is_map(vala) and is_map(valb)`), so a
    list is an atomic primitive and changes wholesale. That is why the
    snapshot keys its collections instead of listing them.
    """
    if old == new:
        return None
    if isinstance(old, dict) and isinstance(new, dict):
        out = {}
        for k in old:
            if k not in new:
                out[k] = [old[k], REMOVED]
            else:
                d = get_delta(old[k], new[k])
                if d is not None:
                    out[k] = d
        for k in new:
            if k not in old:
                out[k] = [REMOVED, new[k]]
        return out or None
    return [old, new]


def apply_delta(state, delta, direction):
    """Apply delta to state in place; returns state.

    direction "undo" takes each pair's index 0, "redo" its index 1. A chosen
    value of REMOVED deletes the key. Mirrors the reference's
    `if is_map(map) and is_map(delta)` guard by returning state untouched when
    either side is not a dict.
    """
    if not (isinstance(state, dict) and isinstance(delta, dict)):
        return state
    idx = 0 if direction == "undo" else 1
    for k, v in delta.items():
        if k == "_delta_metadata":
            continue
        if isinstance(v, dict):
            apply_delta(state.get(k), v, direction)
        else:
            val = v[idx]
            if val == REMOVED:
                state.pop(k, None)
            else:
                state[k] = val
    return state


def apply_delta_list(state, delta_list, direction):
    """Fold apply_delta over a list of deltas, in the given order."""
    for d in delta_list:
        apply_delta(state, d, direction)
    return state


class Player:
    def __init__(self, label, starting_threat=0):
        self.label = label
        self.threat = starting_threat
        self.starting_threat = starting_threat
        self.threat_per_round = 1
        self.eliminated = False
        self.elimination = DEFAULT_ELIMINATION
        self.commit = 0  # willpower committed; persists as next round's default
        self.commit_touched = False  # willpower ring state: committed this round?


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
        self.scenario = None         # preloaded quest-picker scenario metadata
        self.stages = []             # preloaded quest stage/card data
        self.stage_idx = 0           # index into self.stages
        self.card_idx = 0            # index into stages[stage_idx]["cards"]
        self.active_location = None  # or {"points": int, "progress": int}
        self.side_quests = []        # list of {"points": int, "progress": int,
                                      #           "name": str|None (optional,
                                      #           absent/None on old saves)}
        self.willpower = 0           # transient questing input
        self.staging = 0             # transient questing input (staging area threat)
        self.pending_budget = 0      # success progress awaiting placement
        self.pending_elim = None     # player index that just crossed elimination
        self.pending_quest_card = False   # Progress-detail quest-row tap wants
                                           # QuestCardModal opened once the
                                           # Progress-detail modal has closed
                                           # (router replaces one modal at a
                                           # time - see main.py's loop)
        self.pending_side_quest_pick = False  # Progress-detail "+ Side quest"
        # Set by SideQuestPickModal on the way out so the router reopens the
        # Progress modal you tapped "+ Side quest" from, instead of dropping
        # you back on the play screen. Same pending-flag pattern - a modal
        # cannot open another modal directly.
        self.pending_progress_detail = False
                                           # tap wants SideQuestPickModal
                                           # opened once the Progress-detail
                                           # modal has closed (same
                                           # pending-flag pattern as
                                           # pending_quest_card above - the
                                           # picker also needs a catalog read
                                           # first, see main.py's loop)
        # Travel / "+ Add location" wants LocationPickModal opened once the
        # current screen or modal has let go. None, or
        # {"mode": "new"|"change", "back": "play"|"progress"} - the picker
        # needs a catalog read (the gather-list union, see
        # quest_catalog.load_locations) that neither a screen's on_button nor
        # a modal's can do mid-tap, and `back` is how it knows whether to
        # return you to the play screen or reopen the Progress modal.
        self.pending_location_pick = None
        self.reminders = {k: False for k, _, _, _, _ in REMINDER_DEFS}
        self.quest_resolved = False  # quest resolved this round
        self.quest_outcome = None    # "success" | "fail" | "tie" - last resolution
        self.quest_outcome_n = 0     # progress gained / threat taken
        self.quest_history = []      # by-round chart data, capped at last 20
        self.sailing = False         # Dream-chaser Sailing test active
        self.heading = 0             # index into HEADINGS (0 = on-course)
        self.game_over = None        # or {"result", "round", "duration"}
        self.pending_stage = None    # or {"cleared", "excess"} awaiting new stage
        self.pending_resolution = False  # False | "auto" | "forced" - catalog
                                          # game wants ResolutionModal opened
                                          # once the current modal has closed
                                          # (same pending-flag pattern as
                                          # pending_quest_card above)
        self.log = []                # oldest-first list of {seq, round, step, text}
        self._seq = 0
        # -- delta replay (parity: DragnCards gameui["deltas"]/["replayStep"])
        self.deltas = []             # oldest-first; each is a get_delta result
                                     # plus a "_delta_metadata" key
        self.replay_step = -1        # cursor INTO deltas. -1 = before the
                                     # first delta. Not a stack pointer:
                                     # deltas are never popped.
        self.messages = []           # log text produced by the current action,
                                     # drained into the next delta's metadata.
                                     # Mirrors game["messages"].
        self._replay_moved = False   # a cursor move happened inside the current
                                     # recording window - see add_delta

    # -- log ---------------------------------------------------------------
    def _now(self):
        return self.clock() if self.clock else None

    def log_event(self, text):
        """Append a log entry tagged with round, step, and session time."""
        self._seq += 1
        self.log.append({"seq": self._seq, "round": self.round,
                         "step": self.step, "text": text, "t": self._now()})
        self.messages.append(text)

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
        self.players[index].commit_touched = True
        self.willpower = sum(p.commit for p in self.players)

    def touch_commit(self, index):
        """Mark a player's commit as touched this round (willpower ring visual)."""
        self.players[index].commit_touched = True

    def confirm_all_commits(self):
        """One-tap 'same as last round' - marks every living player's
        willpower commit as reviewed (ring goes gold) without changing any
        value."""
        for p in self.players:
            if not p.eliminated:
                p.commit_touched = True

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
        if is_window_view(v):
            self.log_event("Action window: %s"
                           % VIEW_LABELS.get(phase_view_of(v), v))
        else:
            self.log_event("Phase: %s" % VIEW_LABELS.get(v, v))

    def next_view(self):
        """Where advance_view() would go from here, without going there.

        Lets the action-window screen label its CTA with the real destination
        instead of a vague "Continue" - it sits between one step's view and
        the next, so the next phase is exactly what it is handing off to.
        """
        if self.view == "quest_sailing":
            return "quest_commit"
        i = VIEW_ORDER.index(self.view)
        nxt = VIEW_ORDER[(i + 1) % len(VIEW_ORDER)]
        # Resolution is entered only by a successful resolve, so the staging
        # window hands straight to travel.
        if self.view == "aw_quest_staging":
            nxt = "travel"
        if self.view == "planning" and self.sailing:
            nxt = "quest_sailing"
        return nxt

    def next_phase_view(self):
        """The next PHASE view, skipping any window in between.

        next_view() drives navigation; this drives the CTA label. They differ
        because a phase view's button must still read "Next: Questing: Staging"
        even when the tap lands on that phase's window first - the window is a
        step on the way, not the destination being announced.
        """
        v = self.next_view()
        seen = 0
        while is_window_view(v) and seen < len(VIEW_ORDER):
            i = VIEW_ORDER.index(v)
            v = VIEW_ORDER[(i + 1) % len(VIEW_ORDER)]
            if v == "quest_resolution":
                v = "travel"
            seen += 1
        return v

    def advance_view(self):
        """Move to the next view; staging skips resolution (that view is only
        entered by a successful resolve). The one-time setup phase leads into
        round 1 and is never revisited."""
        if self.view == "setup_game":
            self.log_event("Setup complete - round 1 begins (quest %s needs %d)"
                           % (self.quest_label(), self.quest["points"]))
            self.enter_view(VIEW_ORDER[0])
            for p in self.players:
                p.commit_touched = False
            self._snapshot_round()
            return
        if self.view == "quest_sailing":
            self.enter_view("quest_commit")
            return
        nxt = self.next_view()
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

    def _seat_location(self, points, name):
        """The new active location. `name` is the catalog card name when the
        player picked one (LocationPickModal's list step); manual entry
        passes None and the dict keeps exactly the two keys it always had, so
        old saves and hand-entered locations stay indistinguishable from
        today's - every label site reads .get("name") with a generic
        fallback."""
        loc = {"points": points, "progress": 0}
        if name:
            loc["name"] = name
        return loc

    def travel_to(self, points, contribution=0, name=None):
        self.active_location = self._seat_location(points, name)
        self.log_event("Traveled to %s (%d quest points)"
                       % (name or "new location", points))
        self._apply_travel_staging(contribution)

    def change_location(self, points, contribution=0, name=None):
        old = self.active_location
        self.active_location = self._seat_location(points, name)
        new_label = name or "new"
        if old:
            self.log_event(
                "Changed active location (%s at %d/%d discarded) -> %s (%d quest points)"
                % (old.get("name") or "old", old["progress"], old["points"],
                   new_label, points))
        else:
            self.log_event("Changed active location -> %s (%d quest points)"
                           % (new_label, points))
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
        for p in self.players:
            p.commit_touched = False
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
    def preload_scenario(self, scn, stages):
        """Load a quest-picker scenario: scn is metadata (slug/name/pack/...),
        stages is the stage/card tree. Resets quest to stage 1 side A.

        The deep copy is a JSON round-trip, not copy.deepcopy: MicroPython has
        no `copy` module, so the deepcopy version raised ImportError on the
        Presto the moment this screen became reachable there and froze the
        panel. A round-trip is also what the twin does
        (docs/js/gamestate.js: JSON.parse(JSON.stringify(stages))), and it is
        honest about the data - `stages` comes straight out of the catalog's
        JSON, so it has no non-serializable members to lose.
        """
        self.scenario = scn
        self.stages = json.loads(json.dumps(stages))
        self.stage_idx = 0
        self.card_idx = 0
        st = self.stages[0]
        self.quest["stage_n"] = st["stage"]
        self.quest["side"] = "A"
        self.quest["points"] = 0
        self.quest["progress"] = 0
        self.sailing = bool(st["cards"][0].get("sailing"))

    def flip_to_b(self):
        """1A -> 1B: load the current card's questPoints as side B's target."""
        card = self.stages[self.stage_idx]["cards"][self.card_idx]
        self.quest["side"] = "B"
        self.quest["points"] = card["questPoints"]
        return self.quest["points"]

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

    def needs_resolution(self):
        """True if the active location, the quest, or any side quest is
        currently at/over its own (positive) quest points - the trigger for
        the guided resolution flow after a manual progress edit."""
        loc = self.active_location
        if loc and loc["points"] > 0 and loc["progress"] >= loc["points"]:
            return True
        if self.quest["points"] > 0 and self.quest["progress"] >= self.quest["points"]:
            return True
        return any(s["points"] > 0 and s["progress"] >= s["points"] for s in self.side_quests)

    def resolve_location_overflow(self):
        """Active location at/over its points: explore it (rulebook p.15),
        crediting any excess progress to the quest card. No-op (returns 0)
        if there's no active location or it hasn't reached its points."""
        loc = self.active_location
        if not loc or loc["points"] <= 0 or loc["progress"] < loc["points"]:
            return 0
        excess = loc["progress"] - loc["points"]
        self.log_event("Active location Explored (%d/%d)%s"
                       % (loc["progress"], loc["points"],
                          " - %d excess to quest" % excess if excess else ""))
        self.active_location = None
        if excess:
            self.quest["progress"] += excess
        return excess

    def clear_and_advance(self, card_idx=0):
        """Clear the current (side-B) stage and reveal the next stage's side
        A. Per the rulebook (p.22), excess quest progress does NOT carry to
        the next stage - it is discarded, so progress always resets to 0.
        `card_idx` selects the branch alternative when the next stage has
        more than one card (default 0). Returns False (no mutation) if
        there is no next stage - the caller should treat that as victory."""
        if self.stage_idx + 1 >= len(self.stages):
            return False
        was = self.quest_label()
        excess = self.quest["progress"] - self.quest["points"]
        if excess > 0:
            self.log_event("Quest %s cleared (%d excess discarded - does not carry over)"
                           % (was, excess))
        else:
            self.log_event("Quest %s cleared" % was)
        self.stage_idx += 1
        self.card_idx = card_idx
        st = self.stages[self.stage_idx]
        self.quest["stage_n"] = st["stage"]
        self.quest["side"] = "A"
        self.quest["points"] = 0
        self.quest["progress"] = 0
        self.sailing = bool(st["cards"][card_idx].get("sailing"))
        return True

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
                if self.stages:
                    # Catalog game: defer ALL advance mechanics (branch
                    # choice, reveal, flip) to ResolutionModal - see
                    # docs/superpowers/plans/2026-07-24-quest-picker-bresolve.md.
                    self.pending_resolution = "auto"
                else:
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
            outcome, n = "success", diff
            result = {"outcome": outcome, "budget": n}
        elif diff < 0:
            shortfall = -diff
            for i, p in enumerate(self.players):
                if not p.eliminated:
                    self.adjust_threat(i, shortfall)
            self.log_event(OUTCOME["toast_fail"] % shortfall)
            outcome, n = "fail", shortfall
            result = {"outcome": outcome, "threat": n}
        else:
            self.log_event("Quest unsuccessful - tie, no change")
            outcome, n = "tie", 0
            result = {"outcome": outcome}
        self.quest_outcome = outcome
        self.quest_outcome_n = n
        self.quest_history.append({
            "round": self.round, "willpower": willpower, "staging": staging,
            "outcome": outcome, "n": n, "heading": self.heading})
        if len(self.quest_history) > 20:
            self.quest_history = self.quest_history[-20:]
        return result

    # -- delta replay ------------------------------------------------------
    # The seam between our object graph and the reference's map model.
    # DragnCards' `game` IS a map, so it diffs itself; snapshot()/
    # load_snapshot() are the one adapter parity requires.
    #
    # Collections become index-keyed maps because get_delta recurses into
    # dicts only - the same reason the reference models everything as
    # groupById/cardById/stackById.

    def snapshot(self):
        """The diffable projection: everything a phase handler can change."""
        return {
            "players": {str(i): {"threat": p.threat,
                                 "eliminated": p.eliminated,
                                 "commit": p.commit,
                                 "commit_touched": p.commit_touched}
                        for i, p in enumerate(self.players)},
            "quest": dict(self.quest),
            "active_location": (dict(self.active_location)
                                if self.active_location else None),
            "side_quests": {str(i): dict(s)
                            for i, s in enumerate(self.side_quests)},
            "quest_history": {str(i): dict(e)
                              for i, e in enumerate(self.quest_history)},
            "willpower": self.willpower,
            "staging": self.staging,
            "sailing": self.sailing,
            "heading": self.heading,
            "pending_budget": self.pending_budget,
            "pending_stage": (dict(self.pending_stage)
                              if self.pending_stage else None),
            "pending_elim": self.pending_elim,
            "round": self.round,
            "first_player": self.first_player,
            "view": self.view,
            "step": self.step,
            "stage_idx": self.stage_idx,
            "card_idx": self.card_idx,
            "quest_resolved": self.quest_resolved,
            "quest_outcome": self.quest_outcome,
            "quest_outcome_n": self.quest_outcome_n,
            "game_over": dict(self.game_over) if self.game_over else None,
        }

    def load_snapshot(self, m):
        """Write a snapshot back onto the live object. Inverse of snapshot()."""
        for i, p in enumerate(self.players):
            pd = m["players"].get(str(i))
            if pd is None:
                continue
            p.threat = pd["threat"]
            p.eliminated = pd["eliminated"]
            p.commit = pd["commit"]
            p.commit_touched = pd["commit_touched"]
        self.quest = dict(m["quest"])
        self.active_location = (dict(m["active_location"])
                                if m["active_location"] else None)
        # keyed maps back to lists, in key order - the keys are positions
        self.side_quests = [dict(m["side_quests"][k])
                            for k in sorted(m["side_quests"], key=int)]
        self.quest_history = [dict(m["quest_history"][k])
                              for k in sorted(m["quest_history"], key=int)]
        self.willpower = m["willpower"]
        self.staging = m["staging"]
        self.sailing = m["sailing"]
        self.heading = m["heading"]
        self.pending_budget = m["pending_budget"]
        self.pending_stage = (dict(m["pending_stage"])
                              if m["pending_stage"] else None)
        self.pending_elim = m["pending_elim"]
        self.round = m["round"]
        self.first_player = m["first_player"]
        self.view = m["view"]
        self.step = m["step"]
        self.stage_idx = m["stage_idx"]
        self.card_idx = m["card_idx"]
        self.quest_resolved = m["quest_resolved"]
        self.quest_outcome = m["quest_outcome"]
        self.quest_outcome_n = m["quest_outcome_n"]
        self.game_over = dict(m["game_over"]) if m["game_over"] else None

    def begin_action(self):
        """Open a recording window: clear the message buffer and return the
        snapshot to hand back to add_delta().

        The clear matters. Without it, anything logged before the window opens
        (game setup, a round summary, a modal that logged and returned) would
        be drained into the next delta's metadata and stamped with its index -
        so the Log screen would offer a jump target that does not undo those
        lines. The reference has the same boundary: game_ui_server.ex zeroes
        game["messages"] before dispatching an action.
        """
        self.messages = []
        self._replay_moved = False
        return self.snapshot()

    def add_delta(self, prev_snapshot):
        """Record the action that turned prev_snapshot into the current state.

        Parity: game_ui.ex add_delta/2. Returns True when a delta was recorded.

        Divergence D2: the reference advances replayStep before it knows
        whether the diff is non-nil, so a no-op action leaves the cursor one
        past the end and silently swallows the next undo. We only advance on a
        real delta.

        Navigating the history is NOT an action. If the window contained a
        cursor move, the "change" this would diff is the undo itself - which
        would append it as a fresh delta, destroy the redo future, and make the
        log claim an action happened that never did. The reference is immune by
        construction: step_through is a separate GenServer call from
        game_action, so its add_delta is never reached. We have one choke
        point, so we need the guard.
        """
        if self._replay_moved:
            self._replay_moved = False
            self.messages = []
            return False
        d = get_delta(prev_snapshot, self.snapshot())
        if d is None:
            self.messages = []
            return False
        d["_delta_metadata"] = {"unix_ms": self._now(),
                                "log_messages": self.messages}
        # A fresh action after an undo discards the redo future. Python's slice
        # handles replay_step == -1 naturally; the reference needs an explicit
        # guard there because Elixir's 0..-1 range means "to the end".
        self.deltas = self.deltas[:self.replay_step + 1]
        self.deltas.append(d)
        self.replay_step = len(self.deltas) - 1
        # Stamp this action's log entries with their delta index, so the Log
        # screen can offer a jump target per row without matching on text.
        # log_event appends to self.log and self.messages together, so the
        # last len(messages) entries are exactly this action's.
        n = len(self.messages)
        if n:
            for e in self.log[-n:]:
                e["delta_i"] = self.replay_step
        self.messages = []
        if len(self.deltas) > MAX_SAVED_DELTAS:
            drop = len(self.deltas) - MAX_SAVED_DELTAS
            self.deltas = self.deltas[drop:]
            self.replay_step -= drop
            for e in self.log:
                if "delta_i" in e:
                    e["delta_i"] -= drop      # may go negative: not a target
        return True

    def can_undo(self):
        return self.replay_step >= 0

    def can_redo(self):
        return self.replay_step < len(self.deltas) - 1

    def undo(self):
        """Parity: game_ui.ex undo/1."""
        if not self.can_undo():
            return False
        m = self.snapshot()
        apply_delta(m, self.deltas[self.replay_step], "undo")
        self.load_snapshot(m)
        self.replay_step -= 1
        self._replay_moved = True
        return True

    def redo(self):
        """Parity: game_ui.ex redo/1."""
        if not self.can_redo():
            return False
        m = self.snapshot()
        apply_delta(m, self.deltas[self.replay_step + 1], "redo")
        self.load_snapshot(m)
        self.replay_step += 1
        self._replay_moved = True
        return True

    def step_replay(self, direction):
        """Parity: game_ui.ex step/2.

        Named step_replay, not step: `self.step` is already the phase step id
        and a method of that name would be shadowed by __init__'s assignment.
        """
        if direction == "undo":
            return self.undo()
        if direction == "redo":
            return self.redo()
        return False

    def apply_deltas_until_index(self, target):
        """Walk the cursor to target. Parity: apply_deltas_until_index/2."""
        moved = False
        while self.replay_step > target and self.undo():
            moved = True
        while self.replay_step < target and self.redo():
            moved = True
        return moved

    def apply_deltas_until_round_change(self, direction):
        """Step until the round changes, or we run out.

        Divergence D1: the reference reads roundNumber off the gameui wrapper
        (game_ui.ex:1017, :1027) where the key does not exist, so its halt
        condition compares nil to nil and never fires. We read the live round.
        """
        round_init = self.round
        moved = False
        while self.step_replay(direction):
            moved = True
            if self.round != round_init:
                break
        return moved

    def step_through(self, options):
        """Parity: game_ui.ex step_through/2."""
        size = options.get("size")
        if size == "single":
            return self.step_replay(options.get("direction"))
        if size == "round":
            return self.apply_deltas_until_round_change(options.get("direction"))
        if size == "index":
            return self.apply_deltas_until_index(options.get("index"))
        return False

    # -- replay persistence ------------------------------------------------
    # Parity: the Replay schema's two columns (backend/lib/dragn/replay.ex) -
    # game_json and deltas. Divergence D4: two stores rather than one row,
    # because the device writes flash, not Postgres, and state.json is
    # rewritten on every tap. to_dict()/from_dict() are untouched.
    #
    # Divergence D3: replay_step is written, not recomputed. The reference
    # derives it as count(deltas)-1 on load while game_json holds whatever the
    # current state was, so saving mid-undo reloads a cursor that claims
    # end-of-history over a state several steps back.

    def replay_to_dict(self):
        return {"deltas": self.deltas, "replay_step": self.replay_step}

    def replay_from_dict(self, d):
        """Load a replay blob. Anything malformed degrades to no history."""
        self.deltas = []
        self.replay_step = -1
        if not isinstance(d, dict):
            return
        ds = d.get("deltas")
        if not isinstance(ds, list) or not all(isinstance(x, dict) for x in ds):
            return
        self.deltas = ds
        rs = d.get("replay_step")
        if not isinstance(rs, int) or isinstance(rs, bool):
            self.replay_step = len(ds) - 1
            return
        self.replay_step = max(-1, min(rs, len(ds) - 1))

    # -- persistence -------------------------------------------------------
    def to_dict(self):
        return {
            "players": [{"label": p.label, "threat": p.threat,
                         "starting_threat": p.starting_threat,
                         "threat_per_round": p.threat_per_round,
                         "eliminated": p.eliminated,
                         "elimination": p.elimination,
                         "commit": p.commit,
                         "commit_touched": p.commit_touched} for p in self.players],
            "view": self.view,
            "round": self.round,
            "first_player": self.first_player,
            "step": self.step,
            "quest": dict(self.quest),
            "scenario": self.scenario,
            "stages": self.stages,
            "stage_idx": self.stage_idx,
            "card_idx": self.card_idx,
            "active_location": dict(self.active_location) if self.active_location else None,
            "side_quests": [dict(s) for s in self.side_quests],
            "willpower": self.willpower,
            "staging": self.staging,
            "pending_budget": self.pending_budget,
            "pending_elim": self.pending_elim,
            "pending_quest_card": self.pending_quest_card,
            "pending_side_quest_pick": self.pending_side_quest_pick,
            "pending_progress_detail": self.pending_progress_detail,
            "pending_location_pick": self.pending_location_pick,
            "reminders": dict(self.reminders),
            "quest_resolved": self.quest_resolved,
            "quest_outcome": self.quest_outcome,
            "quest_outcome_n": self.quest_outcome_n,
            "quest_history": [dict(e) for e in self.quest_history],
            "sailing": self.sailing,
            "heading": self.heading,
            "game_over": dict(self.game_over) if self.game_over else None,
            "pending_stage": dict(self.pending_stage) if self.pending_stage else None,
            "pending_resolution": self.pending_resolution,
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
            p.commit_touched = pd.get("commit_touched", False)
            g.players.append(p)
        v = d.get("view", VIEW_ORDER[0])
        # saves written before Resource and Planning were split carry the
        # merged view id; land them on the Resource half.
        g.view = "resource" if v == "resource_planning" else v
        g.round = d["round"]
        g.first_player = d["first_player"]
        g.step = d["step"]
        g.quest = dict(d["quest"])
        g.scenario = d.get("scenario")
        g.stages = d.get("stages", [])
        g.stage_idx = d.get("stage_idx", 0)
        g.card_idx = d.get("card_idx", 0)
        g.active_location = dict(d["active_location"]) if d["active_location"] else None
        g.side_quests = [dict(s) for s in d["side_quests"]]
        g.willpower = d.get("willpower", 0)
        g.staging = d.get("staging", 0)
        g.pending_budget = d.get("pending_budget", 0)
        g.pending_elim = d.get("pending_elim", None)
        g.pending_quest_card = d.get("pending_quest_card", False)
        g.pending_side_quest_pick = d.get("pending_side_quest_pick", False)
        g.pending_progress_detail = d.get("pending_progress_detail", False)
        g.pending_location_pick = d.get("pending_location_pick", None)
        g.reminders = {k: False for k, _, _, _, _ in REMINDER_DEFS}
        saved_rem = d.get("reminders", {})
        for k in g.reminders:
            if k in saved_rem:
                g.reminders[k] = saved_rem[k]
        g.quest_resolved = d.get("quest_resolved", False)
        g.quest_outcome = d.get("quest_outcome", None)
        g.quest_outcome_n = d.get("quest_outcome_n", 0)
        g.quest_history = [dict(e) for e in d.get("quest_history", [])]
        g.sailing = d.get("sailing", False)
        g.heading = d.get("heading", 0)
        go = d.get("game_over", None)
        g.game_over = dict(go) if go else None
        ps = d.get("pending_stage", None)
        g.pending_stage = dict(ps) if ps else None
        g.pending_resolution = d.get("pending_resolution", False)
        g.log = [dict(e) for e in d["log"]]
        g._seq = d["seq"]
        return g
