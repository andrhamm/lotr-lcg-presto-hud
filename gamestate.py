"""Pure game-state logic for the LOTR LCG HUD.

No hardware imports — runs under CPython for host tests and under MicroPython
on the device. UI and hardware live elsewhere; this module only models state.
"""

import json

import phases
import xtargets
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
              "refresh", "aw_refresh",
              "round_end"]

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


# -- window policy ---------------------------------------------------------
# How a step's action window reaches the player.
#   "views": the aw_ screens are in the flow. The Presto: a 480px screen has
#            no room for a band under the framework text.
#   "bands": the window is drawn on its step's own view, and next_view() /
#            prev_view() step over the aw_ entries. The tablet.
# Module state, set once by the client at boot. Everything else - the step
# ids, is_action_window, last_window_before, the skip landing - is identical
# under both, which is what keeps the skip's safety rule one rule.
WINDOW_POLICY_VIEWS = "views"
WINDOW_POLICY_BANDS = "bands"
_window_policy = [WINDOW_POLICY_VIEWS]


def set_window_policy(policy):
    if policy not in (WINDOW_POLICY_VIEWS, WINDOW_POLICY_BANDS):
        raise ValueError("unknown window policy: %r" % (policy,))
    _window_policy[0] = policy


def window_policy():
    return _window_policy[0]


def flow_views():
    """VIEW_ORDER as navigation sees it under the current policy.

    Always a fresh copy - callers must not be able to mutate the shared
    VIEW_ORDER (or a cached filtered list) by mutating a return value.
    """
    if _window_policy[0] == WINDOW_POLICY_BANDS:
        return [v for v in VIEW_ORDER if not is_window_view(v)]
    return list(VIEW_ORDER)


# Whether this client tracks the board (engaged enemies, staging cards) well
# enough to answer printed-X questions itself. The tablet sets this at boot;
# the Presto never does, so its printed-X rows keep asking the player - see
# xtargets.resolve and GameState.x_context.
_board_tracking = [False]


def set_board_tracking(on):
    _board_tracking[0] = bool(on)


def board_tracking():
    return _board_tracking[0]


def is_action_window(v):
    """True if this view's STEP is an action window.

    NOT the same as is_window_view(). The `aw_` screens are the interstitial
    windows, but Combat's two windows ARE its phase views: phases.STEPS marks
    6.E (enemy attacks) and 6.P (player attacks) as action_window, and neither
    has an `aw_` screen. Asking the naming convention instead of the turn
    sequence would miss both - which are exactly the windows a combat skip
    passes over.
    """
    import phases as _phases
    st = VIEW_STEP.get(v)
    return bool(st and _phases.step(st)["action_window"])


def last_window_before(target):
    """The last action-window view strictly before `target`, or None.

    This is the whole safety rule for skipping. An action window is a player's
    opportunity to act, and phase-locked abilities can ONLY be initiated in a
    window of their own phase (RR). Jumping a player past the final window of
    a phase silently removes an opportunity they may have been holding a card
    for - and the compiled catalog says that is not hypothetical: 34 distinct
    cards print "Combat Action:", 35 "Planning Action:", 32 "Quest Action:".

    So a skip never lands on its nominal destination. It lands here.
    """
    if target not in VIEW_ORDER:
        return None
    for v in reversed(VIEW_ORDER[:VIEW_ORDER.index(target)]):
        if is_action_window(v):
            return v
    return None


# Contextual skips. Each is something the PLAYER asserts about the table, not
# something the app infers: nothing here tracks enemies, and a tracker that
# guessed would eventually guess wrong in the direction of skipping a phase
# that mattered.
#
# `to` is the nominal destination; the skip actually lands on
# last_window_before(to), so the last window of the skipped span is preserved.
SKIPS = (
    {
        "id": "combat_empty",
        # Offered ONLY from the encounter window, never from enc_checks
        # itself - true under "views". From the phase view, taking the skip
        # would jump the player over aw_enc_checks - the encounter phase's OWN
        # window, which they have not had yet. A skip may pass windows on the
        # way to its landing, but it must never eat the window of the phase
        # the player is standing in. Under "bands" skips_from() offers it ON
        # enc_checks instead: the window is drawn on its step's own view under
        # that policy, so enc_checks IS the window, and the player is already
        # standing on it.
        "from": ("aw_enc_checks",),
        "to": "refresh",
        "label": "No enemies. Skip combat.",
        # Shown on the confirm, so the player is agreeing to a specific claim
        # about their table rather than to a shortcut.
        "claim": "No enemies are engaged and none are in staging.",
    },
)


def skips_from(view):
    """The contextual skips offered on `view` - usually none. Under "bands" a
    skip declared from a window is offered on that window's phase view: the
    window is on the view, so the player is standing on it."""
    bands = _window_policy[0] == WINDOW_POLICY_BANDS
    out = []
    for s in SKIPS:
        origins = [phase_view_of(f) if bands else f for f in s["from"]]
        if view in origins:
            out.append(s)
    return tuple(out)

# view -> representative step id (for the phases screen / log tags / LEDs)
VIEW_STEP = {
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
    # 0.1 is still the CURRENT round's final step. RR: "This step formalizes
    # the end of a game round. Proceed to step 0.0 of the next game round" -
    # so the round counter turns on this view's CTA, not on arriving at it.
    "round_end": "0.1",
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


def fold_log(records):
    """Rebuild `game.log` from the append-only log store.

    The store records log EVENTS, not final rows, because log_event is not
    purely append: a keyed tally rewrites its own row in place so that a run
    of eight stepper taps stays one line. Replaying therefore has to apply the
    identical rule - a record whose (key, round, step) matches the last
    retained row REPLACES it - or the same run comes back as eight rows.

    Keeping the fold here, beside log_event, is deliberate: the two rules must
    agree, and agreement is easier to hold when they are adjacent.
    """
    out = []
    for r in records:
        prev = out[-1] if out else None
        if (r.get("key") is not None and prev is not None
                and prev.get("key") == r.get("key")
                and prev.get("round") == r.get("round")
                and prev.get("step") == r.get("step")):
            out[-1] = dict(r)
        else:
            out.append(dict(r))
    return out


def fold_replay(ops):
    """Rebuild (deltas, replay_step) from the append-only replay journal.

    The store is append-only, so the two things that are NOT appends are
    recorded as tombstones and replayed here:

        {"op": "d", "d": delta}   a new delta
        {"op": "t", "to": n}      a fresh action after an undo discarded the
                                  redo future - keep only the first n
        {"op": "x", "n": k}       MAX_SAVED_DELTAS compaction dropped k from
                                  the front
        {"op": "s", "i": n}       the cursor moved (written, not recomputed -
                                  Divergence D3)

    Order matters: a truncate is emitted before the delta that caused it, so
    replaying in file order reproduces the sequence exactly.
    """
    deltas = []
    step = -1
    for o in ops:
        op = o.get("op")
        if op == "d":
            deltas.append(o.get("d"))
            step = len(deltas) - 1
        elif op == "t":
            deltas = deltas[:o.get("to", 0)]
            if step > len(deltas) - 1:
                step = len(deltas) - 1
        elif op == "x":
            k = o.get("n", 0)
            deltas = deltas[k:]
            step -= k
        elif op == "s":
            step = o.get("i", -1)
    if step < -1:
        step = -1
    if step > len(deltas) - 1:
        step = len(deltas) - 1
    return deltas, step


# -- phase-relative rebasing -----------------------------------------------
#
# The rule, from the original TODO card: "all stat changes / events are
# recorded for the given phase. if you click the back button and make a
# change, the 'final' values for that page are adjusted, the next page always
# bases stat changes relative to the final values from the previous phase."
#
# So a phase owns the AMOUNT it changed each stat by, not the value it left
# behind. Bump willpower 4 -> 6 on Staging, back up and correct Commit to 2,
# and coming forward lands on 4: Staging still contributed +2, applied to the
# corrected base.
#
# This is a separate mechanism from get_delta/apply_delta, deliberately. Those
# are the DragnCards replay port and they are ABSOLUTE by design - undo means
# "put it back exactly as it was", which is the opposite of rebasing.
#
# view/step/round are excluded: they are the navigation doing the rebasing,
# not state a phase changed.
PHASE_NAV_KEYS = ("view", "step", "round")


def rel_delta(old, new):
    """Structural diff where numbers carry HOW MUCH they moved.

    Returns None when nothing changed. Leaves are ["+", amount] for numbers
    and ["=", value] for everything else - a bool, a string or a None has no
    meaningful "+", so it is simply replayed as itself.
    """
    if old == new:
        return None
    if isinstance(old, dict) and isinstance(new, dict):
        out = {}
        for k in new:
            if k not in old:
                out[k] = ["=", new[k]]
            else:
                d = rel_delta(old[k], new[k])
                if d is not None:
                    out[k] = d
        for k in old:
            if k not in new:
                out[k] = ["x", None]
        return out or None
    # bool is a subclass of int, so it has to be caught FIRST or eliminated
    # would "add" to 1 and a re-applied phase would resurrect a dead player.
    if isinstance(old, bool) or isinstance(new, bool):
        return ["=", new]
    if isinstance(old, (int, float)) and isinstance(new, (int, float)):
        return ["+", new - old]
    return ["=", new]


def apply_rel(state, rel):
    """Replay a rel_delta onto `state` in place; returns state."""
    if not (isinstance(state, dict) and isinstance(rel, dict)):
        return state
    for k, v in rel.items():
        if isinstance(v, dict):
            if isinstance(state.get(k), dict):
                apply_rel(state[k], v)
            continue
        op, val = v
        if op == "x":
            state.pop(k, None)
        elif op == "+":
            base = state.get(k, 0)
            if isinstance(base, bool) or not isinstance(base, (int, float)):
                base = 0
            state[k] = base + val
        else:
            state[k] = val
    return state


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
        self.engaged = 0  # enemies engaged with this player (the tablet's tracker)


class GameState:
    def __init__(self, player_count=4, starting_threat=0,
                 elimination_threat=DEFAULT_ELIMINATION):
        self.elimination_threat = elimination_threat
        self.players = [Player("P%d" % (i + 1), starting_threat)
                        for i in range(player_count)]
        for p in self.players:
            p.elimination = elimination_threat
        # The one-time setup phase precedes round 1. Always the CATALOG one:
        # there is no manual/custom quest mode. The game is out of print, so
        # the card data can be complete, and an escape hatch that let a player
        # hand-enter quest points was a second, worse source of truth.
        self.view = "quest_setup"
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
        # A LIST, and the default is still one. Rules Reference, "Active
        # Location": "There can only be one active location at a time", and
        # "The players cannot travel if another location card is active."
        # FIVE printed cards override that in their own text, which is why the
        # state has to hold two (checked against docs/data/, 2026-07-30):
        #   Fisherman's Dock  (The Battle of Lake-town)   "(There are now 2 active locations)"
        #   The Gates of Moria (The Ring Goes South)      "There can be 2 active locations."
        #   Ruined Tower      (Assault on Osgiliath)      "(There are now 2 active locations.)"
        #   Dark Passages     (Over the Misty Mountains - Nightmare)
        #   Widfast           (ALeP - The Aldburg Plot)
        # Order is load-bearing: progress fills the actives in list order
        # before it reaches the quest card (RR "Active Location": the active
        # location "acts as a buffer for the current quest"), so [0] soaks it
        # up first. Empty is the normal case.
        self.active_locations = []   # of {"points": int, "progress": int, ...}
        self.side_quests = []        # list of {"points": int, "progress": int,
                                      #           "name": str|None (optional,
                                      #           absent/None on old saves)}
        self.willpower = 0           # questing total; normally the sum of the
                                     # per-player commits
        # True once the TOTAL has been set directly to something the per-player
        # commits do not add up to. There are two ways into this number - the
        # player widgets and the Questing For stepper - and they must never
        # quietly disagree: while this is set the pills show "?" instead of a
        # breakdown that is no longer true, and opening the players view
        # adopts the breakdown again (see resync_willpower).
        self.willpower_detached = False
        self.staging = 0             # transient questing input (staging area threat)
        # The staging area's card counts. The Presto tracks only its threat;
        # the tablet steps these too, and skip offers + printed-X targets read
        # them (see set_engaged for why they are keyed tallies).
        self.staging_enemies = 0
        self.staging_locations = 0
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
        # Set by the Progress modal's location row. A modal cannot open another
        # modal, so the router (main.py) opens LocationConfigModal on the next
        # tick, exactly like pending_location_pick.
        self.pending_location_detail = False
        # Progress screen's "History" button: the log is a screen, not a modal,
        # so the router does the nav once the modal has closed.
        self.pending_progress_history = False
        # Progress row ">" on the quest: opens QuestConfigModal (the editor),
        # which links on to the read-only card.
        self.pending_quest_config = False
        # Progress row ">" on a SIDE QUEST: opens SideQuestsModal, where Done
        # and Remove live. Distinct from pending_side_quest_pick, which opens
        # the ADD picker - the row's chevron used to raise that one, so a row
        # could never reach its own done/remove.
        self.pending_side_quest_detail = False
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
        self.quest_resolved = False  # quest resolved this round
        self.refresh_applied = False  # 7.3 / 7.4 done for this round
        self.sailed_this_round = False  # the winds have shifted for this one
        self.quest_outcome = None    # "success" | "fail" | "tie" - last resolution
        self.quest_outcome_n = 0     # progress gained / threat taken
        self.quest_history = []      # by-round chart data, capped at last 20
        # Phase-relative rebasing, round-scoped. _phase_bases[view] is the
        # state as that view was ENTERED; _phase_deltas[view] is how much it
        # moved things by the time it was left. See rel_delta above.
        self._phase_bases = {}
        self._phase_deltas = {}
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
        # The log ENTRIES produced by the current action. Replaces a
        # self.log[-n:] slice that assumed every entry of an action sits
        # at the tail - false the moment log_event coalesces into an
        # earlier row. Holds the dicts themselves, so stamping is by
        # identity rather than by position.
        self._action_entries = []
        # Log rows created OR rewritten by the current action, drained by
        # take_log_appends() at the commit point. The log lives in its own
        # append-only store rather than inside the save: it was 96% of
        # state.json and was rewritten in full on every tap.
        self._log_appends = []
        # Replay-journal ops produced by the current action, drained at the
        # commit point. The replay store used to be a whole-file rewrite of
        # every delta on every tap - 42 KB and 875 ms by round 10 - so it is
        # append-only now, and undo/compaction are recorded as tombstones
        # rather than by rewriting history. See fold_replay.
        self._replay_appends = []
        self._last_phase_logged = None
        self.messages = []           # log text produced by the current action,
                                     # drained into the next delta's metadata.
                                     # Mirrors game["messages"].
        self._replay_moved = False   # a cursor move happened inside the current
                                     # recording window - see add_delta

    # -- log ---------------------------------------------------------------
    def _now(self):
        return self.clock() if self.clock else None

    def log_event(self, text, cat="move", key=None):
        """Append a log entry tagged with round, step, and session time.

        `cat` classifies the entry so the Log screen can filter it:
          "move"  something happened in the game. The DEFAULT, deliberately -
                  anything a caller forgets to tag stays visible.
          "phase" a phase transition. Identical every round, carries no game
                  state, and the R<round>.<step> column already says it.
          "tally" a number being dialled in on a stepper.

        `key` coalesces a tally. A run of taps on one stepper is ONE decision,
        not eight: committing 8 willpower used to write eight rows ("Players
        committed 1 willpower" ... "...8 willpower"), and setting staging to 7
        wrote five more. With a key, a repeat within the same (round, step)
        rewrites its own entry in place instead of appending.

        Coalescing is bounded by (key, round, step) on purpose. Re-opening a
        stepper later in the round starts a NEW entry, so *when* each change
        happened stays visible - which is the point of a log.
        """
        prev = self.log[-1] if self.log else None
        if (key is not None and prev is not None and prev.get("key") == key
                and prev.get("round") == self.round and prev.get("step") == self.step):
            self._seq += 1
            prev.update({"seq": self._seq, "text": text, "t": self._now()})
            # messages feeds the delta's metadata; replace the superseded one
            # so a coalesced run contributes a single line there too.
            if self.messages:
                self.messages[-1] = text
            else:
                self.messages.append(text)
            self._log_appends.append(prev)
            return prev
        self._seq += 1
        entry = {"seq": self._seq, "round": self.round, "step": self.step,
                 "text": text, "t": self._now(), "cat": cat}
        if key is not None:
            entry["key"] = key
        self.log.append(entry)
        self.messages.append(text)
        self._action_entries.append(entry)
        self._log_appends.append(entry)
        return entry

    def take_log_appends(self):
        """Rows this action created or rewrote, then clear. Call AFTER
        add_delta, which stamps `delta_i` onto the new rows."""
        out = self._log_appends
        self._log_appends = []
        return out

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

    # Fallback only, for a game with no catalog scenario loaded (manual setup,
    # or a save from before maxCardThreat was emitted). The real number comes
    # from the scenario itself - see staging_reveal_estimate.
    STAGING_HIGH_PER_PLAYER = 3

    def staging_reveal_estimate(self):
        """Worst printed threat on ONE revealed card, times the living players.

        This was `living * STAGING_HIGH_PER_PLAYER` with the constant pinned at
        3, so it showed the same "+3" for every scenario ever published - a
        constant wearing the costume of a calculation, and wrong for The Oath,
        whose Spider Den prints 4. tools/build_card_data.py now answers the
        question per scenario at build time, across the sets the scenario
        actually gathers, and stamps it on the index entry that preload_scenario
        stores as self.scenario.
        """
        living = sum(1 for p in self.players if not p.eliminated)
        worst = (self.scenario or {}).get("maxCardThreat")
        return living * (worst if worst else self.STAGING_HIGH_PER_PLAYER)

    def staging_estimate_is_floor(self):
        """True when the pool holds a card whose printed threat is a literal X.

        Then the estimate is a floor, not a ceiling, and the caption has to say
        so rather than quote a number it knows can be exceeded.
        """
        return bool((self.scenario or {}).get("hasXThreat"))

    def set_commit(self, index, value):
        """Set a player's committed willpower; total willpower = sum of commits."""
        self.players[index].commit = max(0, value)
        self.willpower = sum(p.commit for p in self.players)
        self.willpower_detached = False

    def set_willpower(self, value):
        """Set the committed-willpower total, logging the change.

        A setter rather than a bare assignment because three entry points
        write this - the quest_commit and quest_staging steppers and the
        willpower counter modal - and all three used to assign straight to
        the attribute, so none of them appeared in the log.
        """
        v = max(0, value)
        # Solo has no breakdown to lose: with one player the total IS that
        # player's commit, so write it through. This is an identity, not a
        # heuristic, and it is deliberately keyed on len(players) rather than
        # on "one player not eliminated" - an eliminated player's stored commit
        # is still real data.
        if len(self.players) == 1:
            self.players[0].commit = v
            detached = False
        else:
            # Setting the total directly is the one way the two sources can
            # disagree - unless the value happens to match the sum, in which
            # case nothing is out of sync and there is nothing to flag.
            detached = v != sum(p.commit for p in self.players)
        if v != self.willpower:
            # Two different facts, so two different sentences. Once the total
            # is set directly the per-player breakdown is unknown, and the log
            # must not imply one it does not have; when the typed total does
            # match the players' own numbers, it is not hiding anything.
            self.log_event(
                ("Players committed %d willpower to the quest" % v) if detached
                else ("Willpower total %d, matching the player breakdown" % v),
                cat="tally", key="wp")
            self.willpower = v
        self.willpower_detached = detached
        return self.willpower

    def set_staging(self, value):
        """Set the staging-threat total, logging the change. Same three entry
        points as set_willpower, same reason."""
        v = max(0, value)
        if v != self.staging:
            # State phrasing, not "%d -> %d". Coalescing rewrites the row in
            # place, and a delta phrasing would then claim the run started
            # wherever the last tap happened to be.
            self.log_event("Staging area threat %d" % v, cat="tally", key="stg")
            self.staging = v
        return self.staging

    def set_engaged(self, index, value):
        """Enemies engaged with player `index`. A keyed tally, like set_staging:
        a run of stepper taps rewrites one row rather than logging eight."""
        v = max(0, value)
        p = self.players[index]
        if v != p.engaged:
            self.log_event("P%d engaged enemies %d" % (index + 1, v),
                           cat="tally", key="eng%d" % index)
            p.engaged = v
        return p.engaged

    def engaged_total(self):
        return sum(p.engaged for p in self.players)

    def set_staging_enemies(self, value):
        v = max(0, value)
        if v != self.staging_enemies:
            self.log_event("Staging enemies %d" % v, cat="tally", key="stgen")
            self.staging_enemies = v
        return self.staging_enemies

    def set_staging_locations(self, value):
        v = max(0, value)
        if v != self.staging_locations:
            self.log_event("Staging locations %d" % v, cat="tally", key="stgloc")
            self.staging_locations = v
        return self.staging_locations

    def enemies_in_play(self):
        """What the printed X "enemies in play" counts: engaged with anyone,
        plus still in staging."""
        return self.engaged_total() + self.staging_enemies

    def x_context(self):
        """Every tracked value a printed X can resolve from, by the keyword
        names xtargets.resolve takes. One place, so a new auto target is a
        change here and in xtargets, never at a call site.

        `enemies` and `staging_locations` are included only when this client
        tracks the board (board_tracking()) - the Presto never does, so those
        two keys are absent and xtargets.resolve falls back to its `count`
        argument exactly as it did before either target existed.
        """
        ctx = {
            "players": len(self.players),
            "stage": self.quest.get("stage_n", 1),
            "highest_threat": max([p.threat for p in self.players] or [0]),
        }
        if board_tracking():
            ctx["enemies"] = self.enemies_in_play()
            ctx["staging_locations"] = self.staging_locations
        return ctx

    def resync_willpower(self):
        """Adopt the per-player breakdown as the total, but ONLY when the two
        already agree.

        This used to overwrite the total unconditionally, and PlayersDetailModal
        called it from its constructor. So opening the players view during the
        quest phase - which is exactly what a Doomed keyword, Caught in a Web or
        a failed quest pushes you to do, to record the threat - silently threw
        away a committed total and replaced it with a stale sum. A solo player
        committed 11 willpower, tapped in +1 threat, and resolved the quest
        against 0. Found in the 2026-07-30 playtest of The Oath.

        A view that shows numbers must not rewrite them. Reconciliation still
        happens, at the moment the player actually edits a breakdown:
        set_commit recomputes the total and clears the flag.
        """
        if self.willpower_detached:
            return self.willpower
        total = sum(p.commit for p in self.players)
        if total != self.willpower:
            self.log_event("Willpower total %d -> %d (re-synced to the players)"
                           % (self.willpower, total))
        self.willpower = total
        self.willpower_detached = False
        return total

    # -- view flow ---------------------------------------------------------
    def _total_progress(self):
        n = self.quest["progress"]
        n += sum(l["progress"] for l in self.active_locations)
        n += sum(s["progress"] for s in self.side_quests)
        return n

    def _snapshot_round(self):
        self._round_snap = {"t": self._now(),
                            "threats": [p.threat for p in self.players],
                            "progress": self._total_progress(),
                            "quest": self.quest["progress"]}

    # -- phase-relative bookkeeping ----------------------------------------
    def _phase_projection(self):
        m = self.snapshot()
        for k in PHASE_NAV_KEYS:
            m.pop(k, None)
        return m

    def _record_phase_delta(self):
        """Close the current view's phase: store how much it moved things."""
        base = self._phase_bases.get(self.view)
        if base is None:
            return
        d = rel_delta(base, self._phase_projection())
        if d:
            self._phase_deltas[self.view] = d
        else:
            self._phase_deltas.pop(self.view, None)

    def _restore_phase_entry(self, view):
        """Put live state back to what it was when `view` was entered - which
        is by definition the previous phase's final values."""
        base = self._phase_bases.get(view)
        if base is None:
            return False
        m = self.snapshot()
        m.update(base)
        self.load_snapshot(m)
        return True

    def enter_view(self, v, rebase=True):
        """Central view transition: sets the step and logs the phase start.

        Closes the outgoing phase's delta, then re-applies the incoming
        view's own delta relative to wherever the numbers now stand. `rebase`
        is False only for back_view, which restores rather than replays.
        """
        self._record_phase_delta()
        self.view = v
        self.step = VIEW_STEP[v]
        if v == "round_end":
            # Names the round being CLOSED, not the one beginning: 0.1 is
            # still this round's final step. It is the one screen where two
            # round numbers are live at once (this one, and the one the CTA
            # offers), so the title carries the digit even though the R-chip
            # already shows it.
            self.log_event("End of Round %d" % self.round)
        elif is_window_view(v):
            # Action windows are no longer logged at all. A window is not a
            # state change, its own screen names it, and the R<round>.<step>
            # column already carries the step - it was 8 of the ~21 rows a
            # round produced, every round, identically.
            pass
        else:
            # And a phase is logged only when the PHASE changes, not on every
            # view transition. VIEW_ORDER has 21 entries but only 12 distinct
            # phases, so this halves what is left.
            phase = VIEW_LABELS.get(v, v)
            if phase != self._last_phase_logged:
                self._last_phase_logged = phase
                self.log_event("Phase: %s" % phase, cat="phase")
        # 7.3 and 7.4 happen on ARRIVAL at refresh, before its window opens.
        # After the log line, so the log reads arrival-then-effect.
        if v == "refresh":
            self.apply_refresh()

        if v == VIEW_ORDER[0]:
            # A round boundary. end_round() has banked the stats, bumped the
            # counter and re-derived the willpower total, so no phase of the
            # closed round has a base worth rebasing onto.
            self._phase_bases = {}
            self._phase_deltas = {}
        # The base is taken AFTER any arrival effect, so apply_refresh's threat
        # raise and the sailing shift stay out of the phase delta - both are
        # once-per-round arrival effects with their own idempotence guards, and
        # replaying them relatively would raise threat a second time.
        self._phase_bases[v] = self._phase_projection()
        if rebase:
            d = self._phase_deltas.get(v)
            if d:
                m = self.snapshot()
                apply_rel(m, d)
                self.load_snapshot(m)

    def next_view(self):
        """Where advance_view() would go from here, without going there.

        Lets the action-window screen label its CTA with the real destination
        instead of a vague "Continue" - it sits between one step's view and
        the next, so the next phase is exactly what it is handing off to.
        """
        if self.view == "quest_sailing":
            return "quest_commit"
        order = flow_views()
        # Under "bands" an off-flow window view can be the current view - the
        # allocation path enters aw_quest_resolution directly (see
        # screen_play's apply_alloc), and that view is filtered out of
        # flow_views() under "bands". Navigate as if standing on its phase
        # view instead of raising. Under "views" every view is already in
        # order, so this is a no-op there.
        v = self.view if self.view in order else phase_view_of(self.view)
        if v not in order:
            # An unrecognised view id (a save from a future build, say) has
            # no forward step. Total, like the JS twin - null there is None
            # here, not a ValueError from order.index().
            return None
        i = order.index(v)
        nxt = order[(i + 1) % len(order)]
        # Resolution is entered only by a successful resolve, so whichever
        # view precedes it in the flow hands straight to travel - the staging
        # window under "views", the staging view itself under "bands".
        if nxt == "quest_resolution":
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

    def skip_to(self, skip_id):
        """Take a contextual skip, landing on the last window before its target.

        Three things this deliberately is NOT:

        - It is not automatic. The app does not track enemies, so it cannot
          know combat is empty; the player asserts it. A tracker that inferred
          this would eventually infer it wrong, in the direction of removing a
          phase that mattered.
        - It is not silent. The skipped span is named in the log, so a player
          reading back can see what was passed over and why.
        - It is not a one-way door. This goes through enter_view like every
          other transition, so it sits inside the same delta bracket and undo
          restores it exactly as it restores an ordinary advance.

        Returns the view landed on, or None if the skip is not offered here.
        """
        skip = next((s for s in skips_from(self.view) if s["id"] == skip_id),
                    None)
        if skip is None:
            return None
        landing = last_window_before(skip["to"])
        if landing is None or landing == self.view:
            return None

        order = flow_views()
        # last_window_before walks the raw VIEW_ORDER, so under "bands" it can
        # hand back an aw_ landing that flow_views() has filtered out (not
        # reachable today - the only landing is combat_player - but stay
        # total). Index its phase view instead; a landing whose phase view IS
        # the current view is still refused, via the j <= i guard below.
        landing = landing if landing in order else phase_view_of(landing)
        # Same off-flow mapping for the origin as for the landing above - an
        # off-flow window entered directly (see next_view/prev_view) must not
        # refuse to index just because it is the one standing off the flow.
        origin = self.view if self.view in order else phase_view_of(self.view)
        i, j = order.index(origin), order.index(landing)
        if j <= i:
            return None
        passed = order[i + 1:j]
        self.log_event("Skipped %s - %s" % (
            ", ".join(passed) if passed else "nothing", skip["claim"]))
        self.enter_view(landing)
        return landing

    def skip_offer(self):
        """The skip this view offers, with the tracker's opinion of it, or None.

        `promoted` means the tracked counts say the claim holds. The player
        decides either way - a tracker, not a referee - so the counts inform
        the button and never remove it: the tablet draws a promoted offer in
        amber and a demoted one plain, and the confirm names the counts.
        """
        offered = skips_from(self.view)
        if not offered:
            return None
        engaged = self.engaged_total()
        return {"skip": offered[0],
                "promoted": engaged == 0 and self.staging_enemies == 0,
                "engaged": engaged,
                "staging_enemies": self.staging_enemies}

    def advance_view(self):
        """Move to the next view; staging skips resolution (that view is only
        entered by a successful resolve). The one-time setup phase leads into
        round 1 and is never revisited."""
        if self.view == "quest_setup":
            # The one-time setup view leads into round 1 and is never
            # revisited. A catalog game normally leaves it through the
            # screen's "flip_to_b" CTA, which flips 1A -> 1B first; this is
            # the generic path, kept so advance_view is total over every view.
            self.log_event("Setup complete - round 1 begins (quest %s needs %d)"
                           % (self.quest_label(), self.quest["points"]))
            self.enter_view(VIEW_ORDER[0])
            self._snapshot_round()
            return
        if self.view == "quest_sailing":
            self.enter_view("quest_commit")
            return
        nxt = self.next_view()
        if nxt is None:
            return  # an unrecognised view has no next step; a no-op, not enter_view(None)
        self.enter_view(nxt)
        # A Sailing test begins by shifting one step off-course (rulebook p.6).
        # That is an ARRIVAL effect, once per round - backing out to Planning
        # and coming forward again is one arrival, not two. Guarded the same
        # way and for the same reason as apply_refresh's refresh_applied, and
        # the flag is in snapshot() so undo restores it with the heading.
        if nxt == "quest_sailing" and not self.sailed_this_round:
            self.sailed_this_round = True
            self.shift_heading(1, "winds shift")

    def prev_view(self):
        """Where back_view() would go from here, without going there.

        The inverse of next_view(), and derived from the PHASE SEQUENCE rather
        than from a history of screens visited. Back means "the previous phase
        view" - what the forward arrow means, read backwards. Two consequences
        worth stating, because an earlier draft of this kept a visited-screens
        stack and got both wrong: nothing has to be recorded for it to work, so
        a resumed game has Back on the first frame; and it can never reopen a
        modal flow, because a modal is not a view.
        """
        v = self.view
        if v == "quest_setup":
            return None          # its Back leaves the game - see setup_back
        if v == "quest_sailing":
            return "planning"
        if v == "quest_commit":
            return "quest_sailing" if self.sailing else "planning"
        if v == "quest_resolution":
            # Entered from quest_staging by resolving, never through the
            # staging window - see the play screen's stage_advance CTA.
            return "quest_staging"
        order = flow_views()
        # Same off-flow mapping as next_view(): under "bands" a window view
        # entered directly (e.g. aw_quest_resolution, via screen_play's
        # apply_alloc) is not in flow_views(). Treat it as its phase view
        # rather than refusing to navigate. Under "views" every view is
        # already in order, so this is a no-op there.
        v = v if v in order else phase_view_of(v)
        if v not in order:
            # An unrecognised view id has no view behind it either - total,
            # like the JS twin - null there is None here.
            return None
        i = order.index(v)
        # A closed round is a hard floor: end_round() has already banked its
        # stats, bumped the counter and re-derived the willpower total.
        if i <= 0:
            return None
        prev = order[i - 1]
        # Under "bands" the resolution view sits between staging and travel in
        # the flow, but it is only entered by a resolve; going back from travel
        # without one lands on staging. Bands only: under "views" Back from
        # travel reaches the resolution window first, exactly as before.
        if (_window_policy[0] == WINDOW_POLICY_BANDS
                and prev == "quest_resolution" and not self.quest_resolved):
            return "quest_staging"
        return prev

    def can_go_back(self):
        """Whether the bottom bar's Back arrow has somewhere to go.

        Not can_undo(): Back is navigation. The two answered the same question
        only by accident - can_undo() is true from the first tap of the game
        onward, so Back was offered at the top of every round, where the only
        thing behind you is a round that has already been closed out.
        """
        return self.prev_view() is not None

    def back_view(self):
        """Step back one phase view. Returns False if there is none.

        Navigation, not undo - but the values it lands on are the PREVIOUS
        phase's final ones, which is the same thing as this phase's entry
        state. What this phase changed is not thrown away: it was just banked
        as a relative delta, and walking forward again re-applies it on top of
        whatever the earlier phase now says. So correcting an upstream count
        moves everything downstream with it instead of overwriting it.
        """
        prev = self.prev_view()
        if prev is None:
            return False
        if self.view == "quest_resolution":
            self.unresolve_quest()
        leaving = self.view
        self._record_phase_delta()
        self._restore_phase_entry(leaving)
        # Straight assignment, not enter_view: going back must not re-log the
        # phase, re-run its arrival effect, or reset the base of the view being
        # returned to - that base is what makes ITS delta come out right.
        self.view = prev
        self.step = VIEW_STEP[prev]
        return True

    def unresolve_quest(self):
        """Reopen a resolved quest so advancing runs the comparison again.

        resolve_quest() latches quest_resolved and the play screen only
        resolves `if not game.quest_resolved`, so without this a staging count
        corrected after backing out would still resolve against the old
        numbers - the stale-reference case exactly.

        This is a TRACKER: a player who miscounted may retcon, including out of
        an elimination. So a fail's threat raise is taken back rather than
        being a reason to refuse to move.
        """
        if not self.quest_resolved:
            return False
        if self.quest_outcome == "fail":
            n = self.quest_outcome_n
            for i, p in enumerate(self.players):
                # Who took the raise, worked back from the state it produced.
                # resolve_quest raised the LIVING only, and `eliminated` is
                # purely threat >= elimination, so a player is still eliminated
                # after the reversal exactly when they were already eliminated
                # before it. Exact, and needs nothing extra persisted.
                if not p.eliminated or p.threat - n < p.elimination:
                    self.adjust_threat(i, -n)
            # adjust_threat raises the prompt but never lowers it, and the
            # player it was raised for may be back under their level now.
            if (self.pending_elim is not None
                    and not self.players[self.pending_elim].eliminated):
                self.pending_elim = None
        if self.quest_history:
            self.quest_history.pop()
        # A resolution is DERIVED from willpower vs staging, so it must be
        # recomputed rather than replayed - drop the phase delta that would
        # otherwise re-apply the old outcome on the way forward.
        self._phase_deltas.pop("quest_resolution", None)
        self.quest_resolved = False
        self.quest_outcome = None
        self.quest_outcome_n = 0
        self.pending_budget = 0
        self.log_event("Quest resolution reopened")
        return True

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

    def history_record(self):
        """A finished game, in the shape the history store keeps.

        ~220 B measured, which is what makes appending one per game free
        forever (~63 ms regardless of how many are stored). Deliberately a flat
        summary rather than the whole save: the stats screens aggregate over
        these, and reading 4000 full saves back took 15.9 s.
        """
        scn = self.scenario or {}
        return {
            "scn": scn.get("slug"),
            "name": scn.get("name"),
            "mode": scn.get("mode"),
            "source": scn.get("source"),
            "players": len(self.players),
            "won": bool(self.game_over and self.game_over.get("result") == "victory"),
            "rounds": self.round,
            "duration": (self.game_over or {}).get("duration"),
            "threats": [p.threat for p in self.players],
            "eliminated": sum(1 for p in self.players if p.eliminated),
        }

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

    # Keys _seat_location copies from the picker's entry when present. Every
    # one is optional and absent for a manual entry, so a hand-typed location
    # and an old save stay byte-identical to what they were.
    #
    # `threat` is the location's staging contribution, and it is stored rather
    # than only passed to _apply_travel_staging because putting the location
    # BACK into staging has to add the same number again - the caller no
    # longer has it by then.
    #
    # `*Kind` / `*Formula` say why a stat has no number: see
    # quest_catalog.locations_for. Carried so the Progress screen can show the
    # card's own definition of X instead of a 0 it made up.
    LOC_META = ("threat", "pointsKind", "pointsX",
                "threatKind", "threatX", "threatCount")

    def _seat_location(self, points, name, meta=None):
        """The new active location. `name` is the catalog card name when the
        player picked one (LocationPickModal's list step); manual entry
        passes None and gains none of the CATALOG keys, so every label site
        reads .get("name") with a generic fallback.

        A manual entry does carry `threat`, though: the player typed that
        number into the contribution stepper and travelling took it straight
        out of the staging area, so the record has to hold it or
        "Back to staging" puts 0 back and the staging total stays short."""
        loc = {"points": points, "progress": 0}
        for k in self.LOC_META:
            v = (meta or {}).get(k)
            if v is not None:
                loc[k] = v
        if name:
            loc["name"] = name
        # An AUTO X resolves the moment the card is placed. The other two
        # shapes wait for a count the player supplies on the row sheet, but
        # "X is the number of players" has no control to wait for - there is
        # nothing to ask - so without this the location would sit at no threat
        # at all and under-report the staging total.
        auto = xtargets.resolve(loc.get("threatX"), **self.x_context())
        if auto is not None and xtargets.auto_for(loc["threatX"].get("target")):
            loc["threat"] = auto
        return loc

    def travel_to(self, points, contribution=0, name=None, meta=None):
        # Appends. Travelling with one already active is how the second one
        # arrives, and the printed cards that allow it never say "replace" -
        # that is what change_location is for.
        self.active_locations.append(self._seat_location(points, name, meta))
        # Only claim a travel when the players actually paid the cost. A card
        # effect can make a location active without one, and the log is the
        # game's record - it should not invent a travel that never happened.
        # The mechanics are identical either way (RR: "the active location acts
        # as a buffer", so its threat leaves the staging total regardless).
        verb = ("Traveled to" if (meta or {}).get("arrival", "travel") == "travel"
                else "Placed as active location:")
        self.log_event("%s %s (%d quest points)"
                       % (verb, name or "new location", points))
        self._apply_travel_staging(contribution)

    def change_location(self, points, contribution=0, name=None, idx=0,
                        meta=None):
        # Replaces ONE seat, not the whole row: with two actives, "a card
        # effect replaces the active location" names one of them, and
        # discarding the other alongside it would silently drop its progress.
        old = self.active_locations[idx] if idx < len(self.active_locations) else None
        seat = self._seat_location(points, name, meta)
        if old is not None:
            self.active_locations[idx] = seat
        else:
            self.active_locations.append(seat)
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
        """Any location at its quest points is Explored - removed from the row.

        Iterates back to front so removing one does not shift the index of a
        later one still being checked."""
        done = False
        for i in range(len(self.active_locations) - 1, -1, -1):
            loc = self.active_locations[i]
            if loc["points"] > 0 and loc["progress"] >= loc["points"]:
                self.log_event("Active location Explored (%d/%d) - removed"
                               % (loc["progress"], loc["points"]))
                del self.active_locations[i]
                done = True
        return done

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
    def apply_refresh(self):
        """Steps 7.3 and 7.4: raise each living player's threat, pass the token.

        Called from enter_view() when the refresh view is entered, because RR
        puts both BEFORE the refresh action window (the chart runs 7.3, 7.4,
        ACTION WINDOW, 7.5). The player never performs them; the tracker does.

        It must run inside a button handler's begin_action/add_delta bracket
        (main.py), which enter_view always is - draw() runs OUTSIDE that
        bracket, so doing this at draw time would leave a mutation no delta
        records: invisible to undo, with its log lines mis-attributed to the
        NEXT action.

        Idempotent via refresh_applied, which is in snapshot(), so back
        restores the threat and the flag together and re-advancing applies
        exactly once.
        """
        if self.refresh_applied:
            return False
        for i, p in enumerate(self.players):
            if not p.eliminated:
                self.adjust_threat(i, p.threat_per_round)
        self.first_player = (self.first_player + 1) % len(self.players)
        self.refresh_applied = True
        self.log_event("Refresh: threat raised, first player -> P%d"
                       % (self.first_player + 1))
        return True

    def end_round(self):
        """Close the round out: bump the counter and return to step 1.

        7.3 and 7.4 are NOT here - they belong to apply_refresh(), which runs
        when the refresh view is entered. This is 0.1 -> 0.0.
        """
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
        self.round += 1
        # commits persist as next round's defaults; refresh the derived total
        self.willpower = sum(p.commit for p in self.players)
        self.willpower_detached = False
        self.quest_resolved = False
        self.quest_outcome = None
        self.refresh_applied = False      # arm the next round's 7.3 / 7.4
        self.sailed_this_round = False    # ...and the next round's winds
        self.log_event("New round %d begins" % self.round)
        # enter_view rather than assigning view/step directly: that is what
        # keeps the step, the log line and any on-entry rules effect in step.
        self.enter_view(VIEW_ORDER[0])    # rounds never revisit setup
        self._snapshot_round()

    # -- quest / progress --------------------------------------------------
    def rehydrate_stages(self, stages):
        """Replace the in-memory stage tree with a freshly-read one.

        The counterpart to dropping `stages` from the save: a resumed game
        gets its assets back from the catalog rather than from its own stale
        copy, so a card-data correction reaches games already in progress.

        Refuses the swap when the new tree cannot host the position the game
        is already at - `stage_idx` and `card_idx` index into it, so a
        scenario that lost a stage upstream would otherwise leave the game
        pointing past the end. Returns True if it took.

        Never touches `quest`: the live stage number, side, points and
        progress live there, so refreshing the tree does not disturb play.
        The corrected numbers are picked up at the next flip.
        """
        if not stages:
            return False
        if self.stage_idx >= len(stages):
            return False
        cards = (stages[self.stage_idx] or {}).get("cards") or []
        if self.card_idx >= len(cards):
            return False
        self.stages = stages
        return True

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
        """1A -> 1B: load the current card's questPoints as side B's target.

        `mode` says whether that target is real. ~177 stage cards print no
        quest points at all: they advance on a condition (an enemy defeated,
        an objective claimed, a pile of resource tokens) rather than by
        filling a bar, and drawing 0/0 for them is a lie. `advance` / `lose`
        carry the card's own sentence about how the stage ends, distilled from
        its printed text - see tools/build_advancement.py.

            "points"     a real printed target; fill the bar
            "condition"  no target exists; show the sentence instead
            "formula"    the card computes one in its own text
        """
        card = self.stages[self.stage_idx]["cards"][self.card_idx]
        self.quest["side"] = "B"
        self.quest["points"] = card["questPoints"]
        kind = card.get("questPointsKind")
        coded = card.get("questPointsX")
        if coded:
            self.quest["mode"] = "formula"
            self.quest["x"] = coded
        elif kind == "na" or (not card["questPoints"] and kind):
            self.quest["mode"] = "condition"
            self.quest.pop("x", None)
        else:
            self.quest["mode"] = "points"
            self.quest.pop("x", None)
        for k in ("advance", "lose"):
            if card.get(k):
                self.quest[k] = card[k]
            else:
                self.quest.pop(k, None)
        return self.quest["points"]

    def quest_label(self):
        return "%d%s" % (self.quest["stage_n"], self.quest["side"])

    def auto_split(self, budget):
        """Fill the active location, then the quest - each capped at its own
        quest points. Side quests are left untouched; any overflow beyond
        location + quest capacity is discarded."""
        alloc = {"locations": [0] * len(self.active_locations), "quest": 0,
                 "side_quests": [0] * len(self.side_quests)}
        remaining = budget
        # In list order: RR p.15 fills the active location(s) before the quest
        # card, and with two the first one seated soaks it up first.
        for i, loc in enumerate(self.active_locations):
            room = max(0, loc["points"] - loc["progress"])
            alloc["locations"][i] = min(remaining, room)
            remaining -= alloc["locations"][i]
        qroom = max(0, self.quest["points"] - self.quest["progress"])
        alloc["quest"] = min(remaining, qroom)
        return alloc

    def needs_resolution(self):
        """True if the active location, the quest, or any side quest is
        currently at/over its own (positive) quest points - the trigger for
        the guided resolution flow after a manual progress edit."""
        if any(l["points"] > 0 and l["progress"] >= l["points"]
               for l in self.active_locations):
            return True
        if self.quest["points"] > 0 and self.quest["progress"] >= self.quest["points"]:
            return True
        return any(s["points"] > 0 and s["progress"] >= s["points"] for s in self.side_quests)

    def resolve_location_overflow(self):
        """Active location(s) at/over their points: explore them (rulebook
        p.15), crediting any excess progress to the quest card. Returns the
        total excess credited, 0 if nothing was ready.

        Back to front, so removing one does not shift the index of a later one
        still being checked."""
        total = 0
        for i in range(len(self.active_locations) - 1, -1, -1):
            loc = self.active_locations[i]
            if loc["points"] <= 0 or loc["progress"] < loc["points"]:
                continue
            excess = loc["progress"] - loc["points"]
            self.log_event("Active location Explored (%d/%d)%s"
                           % (loc["progress"], loc["points"],
                              " - %d excess to quest" % excess if excess else ""))
            del self.active_locations[i]
            total += excess
        if total:
            self.quest["progress"] += total
        return total

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

        # Back to front: an explored location is removed, and going forward
        # would shift the index of every later one still to be credited.
        locs = alloc.get("locations") or []
        for i in range(len(self.active_locations) - 1, -1, -1):
            n = locs[i] if i < len(locs) else 0
            if not n:
                continue
            loc = self.active_locations[i]
            loc["progress"] += n
            if loc["progress"] >= loc["points"]:
                completed.append("Active Location explored")
                del self.active_locations[i]

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

    def quest_preview(self):
        """What resolution WOULD do right now, without doing it.

        The staging window's copy is conditional on the pending result, and
        the view must not re-derive the comparison: resolve_quest() owns that
        rule, and two copies of it drift.

        Returns (outcome, n, room) where outcome is success/fail/tie, n is the
        progress or threat that would follow, and room is how much progress
        the board can still absorb - remaining quest points PLUS any unfilled
        active-location capacity, because progress fills the location first
        and its overflow flows on to the quest (RR 3.4). Testing the quest
        card alone would tell a player their willpower is wasted while a
        location is still soaking it up.
        """
        diff = self.willpower - self.staging
        outcome = "success" if diff > 0 else ("fail" if diff < 0 else "tie")
        room = max(0, self.quest["points"] - self.quest["progress"])
        for loc in self.active_locations:
            room += max(0, loc["points"] - loc["progress"])
        return outcome, abs(diff), room

    def would_be_eliminated_at_refresh(self):
        """Players whose threat would cross the elimination level at 7.3.

        NOT used to gate the combat warning: 67 cards interact with the
        refresh raise and several replace it outright (Nalir raises by one
        per player; Escape From Mount Gram substitutes a different number
        entirely), so this sum can be wrong in the dangerous direction. It
        exists for the preview row, which shows its own arithmetic.
        """
        out = []
        for i, p in enumerate(self.players):
            if not p.eliminated and p.threat + p.threat_per_round >= p.elimination:
                out.append(i)
        return out

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
        # `stage` is what the History chart rules a gold vertical on: without
        # it the chart can show the rounds but not where the quest advanced,
        # which is the one thing that explains a sudden jump in the staging
        # line. Entries written before this exist without the key, so every
        # reader uses .get("stage").
        self.quest_history.append({
            "round": self.round, "willpower": willpower, "staging": staging,
            "outcome": outcome, "n": n, "heading": self.heading,
            "stage": self.quest.get("stage_n", 1)})
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
                                 "engaged": p.engaged}
                        for i, p in enumerate(self.players)},
            "quest": dict(self.quest),
            "active_locations": {str(i): dict(l)
                                 for i, l in enumerate(self.active_locations)},
            "side_quests": {str(i): dict(s)
                            for i, s in enumerate(self.side_quests)},
            "quest_history": {str(i): dict(e)
                              for i, e in enumerate(self.quest_history)},
            "willpower": self.willpower,
            "willpower_detached": self.willpower_detached,
            "staging": self.staging,
            "staging_enemies": self.staging_enemies,
            "staging_locations": self.staging_locations,
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
            "refresh_applied": self.refresh_applied,
            "sailed_this_round": self.sailed_this_round,
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
            # .get: deltas recorded before the tracker existed carry no key
            p.engaged = pd.get("engaged", 0)

        self.willpower_detached = m.get("willpower_detached", False)
        self.quest = dict(m["quest"])
        self.active_locations = [dict(m["active_locations"][k])
                                 for k in sorted(m["active_locations"], key=int)]
        # keyed maps back to lists, in key order - the keys are positions
        self.side_quests = [dict(m["side_quests"][k])
                            for k in sorted(m["side_quests"], key=int)]
        self.quest_history = [dict(m["quest_history"][k])
                              for k in sorted(m["quest_history"], key=int)]
        self.willpower = m["willpower"]
        self.staging = m["staging"]
        self.staging_enemies = m.get("staging_enemies", 0)
        self.staging_locations = m.get("staging_locations", 0)
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
        self.refresh_applied = m["refresh_applied"]
        # .get: deltas recorded before the flag existed carry no such key, and
        # a snapshot is replayed as a whole map.
        self.sailed_this_round = m.get("sailed_this_round", False)
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
        self._action_entries = []
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
        if self.replay_step + 1 < len(self.deltas):
            # A fresh action after an undo discards the redo future. The
            # journal cannot un-append, so record the truncation instead.
            self._replay_appends.append({"op": "t", "to": self.replay_step + 1})
        self.deltas = self.deltas[:self.replay_step + 1]
        self.deltas.append(d)
        self._replay_appends.append({"op": "d", "d": d})
        self.replay_step = len(self.deltas) - 1
        # Stamp this action's log entries with their delta index, so the Log
        # screen can offer a jump target per row without matching on text.
        # log_event appends to self.log and self.messages together, so the
        # last len(messages) entries are exactly this action's.
        for e in self._action_entries:
            e["delta_i"] = self.replay_step
        self._action_entries = []
        self.messages = []
        if len(self.deltas) > MAX_SAVED_DELTAS:
            drop = len(self.deltas) - MAX_SAVED_DELTAS
            self.deltas = self.deltas[drop:]
            self.replay_step -= drop
            for e in self.log:
                if "delta_i" in e:
                    e["delta_i"] -= drop      # may go negative: not a target
            self._replay_appends.append({"op": "x", "n": drop})
        self._replay_appends.append({"op": "s", "i": self.replay_step})
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
            moved = self.step_replay(options.get("direction"))
        elif size == "round":
            moved = self.apply_deltas_until_round_change(options.get("direction"))
        elif size == "index":
            moved = self.apply_deltas_until_index(options.get("index"))
        else:
            return False
        if moved:
            # replay_step is WRITTEN, not recomputed (Divergence D3), so a
            # cursor move has to reach the journal too - otherwise a save made
            # mid-undo reloads a cursor claiming end-of-history over a state
            # several steps back.
            self._replay_appends.append({"op": "s", "i": self.replay_step})
        return moved

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

    def take_replay_appends(self):
        """Journal ops this action produced, then clear."""
        out = self._replay_appends
        self._replay_appends = []
        return out

    def seed_replay_journal(self):
        """The ops that would rebuild the CURRENT history from empty.

        Used when the journal is first created for a game that already has
        deltas (an upgrade from the whole-file store), and after compaction.
        """
        ops = [{"op": "d", "d": d} for d in self.deltas]
        ops.append({"op": "s", "i": self.replay_step})
        return ops

    @staticmethod
    def _migrate_delta(delta):
        """Rewrite a pre-list delta's `active_location` onto `active_locations`.

        A delta mirrors the shape of the state it describes, so renaming the
        field renamed every recorded delta out from under undo: applying one
        would set a stray `active_location` key and leave the real seat list
        untouched - a silent wrong-undo rather than a crash, which is worse.

        The old side was a bare record or None; the new one is the keyed map
        snapshot() emits, so seat 0 carries the whole change:

            [None, rec] -> {"0": [REMOVED, rec]}      a location arrived
            [rec, None] -> {"0": [rec, REMOVED]}      it left
            {"progress": [0, 1]} -> {"0": {"progress": [0, 1]}}   it changed
        """
        if "active_location" not in delta:
            return delta
        out = dict(delta)
        old = out.pop("active_location")
        if isinstance(old, list) and len(old) == 2:
            a, b = old
            out["active_locations"] = {"0": [REMOVED if a is None else a,
                                             REMOVED if b is None else b]}
        else:
            out["active_locations"] = {"0": old}
        return out

    def replay_from_dict(self, d):
        """Load a replay blob. Anything malformed degrades to no history."""
        self.deltas = []
        self.replay_step = -1
        if not isinstance(d, dict):
            return
        ds = d.get("deltas")
        if not isinstance(ds, list) or not all(isinstance(x, dict) for x in ds):
            return
        self.deltas = [self._migrate_delta(x) for x in ds]
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
                         "engaged": p.engaged,
                         } for p in self.players],
            "view": self.view,
            "round": self.round,
            "first_player": self.first_player,
            "step": self.step,
            "quest": dict(self.quest),
            "scenario": self.scenario,
            # `stages` is NOT saved. It is scenario ASSET data - the full
            # card tree - and a save should reference an asset by id, not
            # embed a copy of it. Embedding it meant every data correction
            # stopped at the save boundary: fixing 15 quest cards whose side B
            # repeated side A left every in-progress game still showing the
            # old text, because the game was replaying its own copy. It also
            # put a median 2 KB (worst 7.9 KB) of card data into a ~1.3 KB
            # state file, rewritten on every save.
            #
            # `scenario` carries the slug, which is the id. The resume path in
            # main.py / main.js re-reads the stage tree from the catalog with
            # it. from_dict still ACCEPTS a saved `stages` so games written
            # before this keep working until that re-read lands.
            "stage_idx": self.stage_idx,
            "card_idx": self.card_idx,
            "active_locations": [dict(l) for l in self.active_locations],
            "side_quests": [dict(s) for s in self.side_quests],
            "willpower": self.willpower,
            "willpower_detached": self.willpower_detached,
            "staging": self.staging,
            "staging_enemies": self.staging_enemies,
            "staging_locations": self.staging_locations,
            "pending_budget": self.pending_budget,
            "pending_elim": self.pending_elim,
            "pending_quest_card": self.pending_quest_card,
            "pending_side_quest_pick": self.pending_side_quest_pick,
            "pending_progress_detail": self.pending_progress_detail,
            "pending_location_detail": self.pending_location_detail,
            "pending_progress_history": self.pending_progress_history,
            "pending_quest_config": self.pending_quest_config,
            "pending_side_quest_detail": self.pending_side_quest_detail,
            "pending_location_pick": self.pending_location_pick,
            "refresh_applied": self.refresh_applied,
            "sailed_this_round": self.sailed_this_round,
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
            # `log` is deliberately NOT saved here, for the same reason
            # `stages` is not (see the note above): it was 96% of a save that
            # is rewritten on every tap - 37,887 B of which ~36,000 was log -
            # and it is append-only in practice, since snapshot() excludes it
            # so undo never touches it. It lives in its own append-only store;
            # main.py's save_log/load_log own it, and fold_log rebuilds it.
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
            p.engaged = pd.get("engaged", 0)

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
        # Old saves embedded the stage tree; new ones do not (see to_dict).
        # Accepted either way, and the resume path replaces it from the
        # catalog when a scenario slug is present.
        g.stages = d.get("stages", [])
        g.stage_idx = d.get("stage_idx", 0)
        g.card_idx = d.get("card_idx", 0)
        # Saves written before the list existed hold a single "active_location"
        # dict (or null). Migrate rather than drop it: a player mid-campaign
        # should not lose the location they travelled to because the HUD
        # learned to hold two.
        if "active_locations" in d:
            g.active_locations = [dict(l) for l in d["active_locations"]]
        else:
            old = d.get("active_location")
            g.active_locations = [dict(old)] if old else []
        g.side_quests = [dict(s) for s in d["side_quests"]]
        g.willpower = d.get("willpower", 0)
        g.willpower_detached = d.get("willpower_detached", False)
        g.staging = d.get("staging", 0)
        g.staging_enemies = d.get("staging_enemies", 0)
        g.staging_locations = d.get("staging_locations", 0)
        g.pending_budget = d.get("pending_budget", 0)
        g.pending_elim = d.get("pending_elim", None)
        g.pending_quest_card = d.get("pending_quest_card", False)
        g.pending_side_quest_pick = d.get("pending_side_quest_pick", False)
        g.pending_progress_detail = d.get("pending_progress_detail", False)
        g.pending_location_detail = d.get("pending_location_detail", False)
        g.pending_progress_history = d.get("pending_progress_history", False)
        g.pending_quest_config = d.get("pending_quest_config", False)
        g.pending_side_quest_detail = d.get("pending_side_quest_detail", False)
        g.pending_location_pick = d.get("pending_location_pick", None)
        # A save written before this flag existed, resumed AT or AFTER the
        # refresh view, has already had its threat raised. Defaulting False
        # there would raise it a second time on the next back-and-forward.
        g.refresh_applied = d.get("refresh_applied",
                                  d.get("view") in ("refresh", "aw_refresh",
                                                    "round_end"))
        # Same reasoning one field up: a save written before this flag existed,
        # resumed at or after the sailing test, has already shifted its
        # heading. Defaulting False there would shift it again on the next
        # back-and-forward.
        g.sailed_this_round = d.get(
            "sailed_this_round",
            bool(d.get("sailing")) and d.get("view") not in
            ("resource", "aw_resource", "planning"))
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
        # `log` moved to its own append-only store, so it is absent from new
        # saves - but a save written before that split still carries it, and
        # loading it is free. main.py's load_log() fills it for new saves.
        g.log = [dict(e) for e in d.get("log", [])]
        g._seq = d.get("seq", 0)
        return g
