# Back Button — phase-relative stat rebasing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A "< Back" control on the guided round screen (`ScreenPlay`) that steps back one phase at a time within the current round, restoring each phase's state exactly as it stood when the player left it. Editing after going back and moving forward again must recompute everything downstream from the corrected values (not double-apply the old computation) — e.g. back up from a failed quest resolution, fix the committed willpower, and re-resolving must raise threat by the *new* shortfall only, not stack it on top of the old raise.

**Architecture:** A bounded **checkpoint stack** on `GameState` (`_view_history`), not a delta/event log. Every forward transition away from a guided-round view pushes a snapshot of that view's "final" mutable fields; `go_back()` pops the most recent one and restores it verbatim, re-entering that view. This works for the "rebase" requirement for free: `resolve_quest()`, `place_progress()`, `advance_view()` etc. already compute strictly from *current* live state — never from a remembered delta — so restoring state and letting the player redo their forward action naturally recomputes from the corrected base. The stack is scoped to the current round only (cleared at every round boundary, piggybacking on the existing `_snapshot_round()` hook) and is transient — it is deliberately **not** part of `to_dict()`/`from_dict()`. The UI adds one "< Back" button, drawn by the existing shared `_cta()` CTA helper whenever `game.can_go_back()`, which narrows the primary CTA to share the row.

**Tech Stack:** ES modules (web, Canvas) + MicroPython (firmware); pytest + the scene layout linter.

**Context:** TODO.md "Ideas": *"back button. all stat changes / events are recorded for the given phase. if you click the back button and make a change, the 'final' values for that page are adjusted, the next page always bases stat changes relative to the final values from the previous phase."* The guided round is `VIEW_ORDER` (`resource_planning -> quest_commit -> quest_staging -> [quest_resolution] -> travel -> enc_optional -> enc_checks -> combat_shadow -> combat_enemy -> combat_player -> refresh`, with `quest_sailing` conditionally inserted after `resource_planning`), walked by `advance_view()`/`advanceView()`, which funnels every transition through `enter_view()`/`enterView()`. There is already a **round-scoped** snapshot (`_snapshot_round`/`_snapshotRound`, populating `_round_snap`) used only to compute the round-end delta summary text — this plan adds a sibling mechanism, a **per-view** snapshot *stack*, for undo, and clears it at the same point `_round_snap` is refreshed.

Two things that already exist and are explicitly **out of scope**, so the implementer doesn't confuse them with this feature:
- `GameState.prev_step()`/`next_step()` — a low-level cursor over `phases.STEP_ORDER` (the fine-grained step list, not `VIEW_ORDER`). Nothing in the UI calls either today (`next_step` is dead code, `prev_step` is unreferenced dead code); this plan does not wire them up, remove them, or reuse them.
- The Phases screen (`ui/screen_phases.py` / `ScreenPhases` in `docs/js/screens_other.js`) already lets a player jump `game.view`/`game.step` **directly**, with zero rebasing — a totally different, free-form manual override reached by tapping the header's phase name. It is unaffected by this plan: it doesn't push or consult `_view_history`. Using it mid-round doesn't corrupt the back-stack, but it can make "Back" feel surprising (it always returns to wherever the *guided* flow last was, not wherever a manual jump landed) — an accepted edge case, not something this plan fixes.
- The header's `nav_stack` (`("nav", "log"|"phases"|"settings"|"close")`) is a **third**, unrelated "back" concept: it returns an overlay screen (Log/Phases/Settings/About) to the screen it was opened from. Nothing here touches it.

## Architecture — the data model

This is the load-bearing decision, so it's specified field-by-field.

**1. Capture mechanism: a snapshot stack, not a delta log.** Two designs were considered:
- *Delta/event log* (record every individual stat mutation with enough info to reverse or replay it) — enables arbitrary redo and fine-grained partial reversion, but requires every mutating method (`resolve_quest`, `place_progress`, `adjust_threat`, `_advance_quest_stage`, sailing heading shifts, elimination, stage-completion...) to also produce a reversible/replayable record, and getting that right across this much branching mutation logic is a large, bug-prone undertaking for a hobby-scale MicroPython target.
- *Whole-view snapshot stack* (recommended): each checkpoint is a plain copy of the mutable fields, taken right before a forward transition. Going back is "restore the copy." This is **not new machinery** — `to_dict()` already does this exact style of shallow-copy snapshotting on every autosave (every truthy button result triggers `save_state(game)` → `game.to_dict()` → JSON to flash/localStorage), so a per-view checkpoint is the same proven pattern, just kept in RAM and scoped to a named subset of fields instead of the whole game.

**Recommended default: the snapshot stack.** *If the user prefers the delta-log approach instead*, it would replace `_checkpoint_state`/`_restore_checkpoint` with a per-field-change event append and a reducer to reconstruct any prior point — substantially more code and more edge cases (e.g. reconciling a partially-applied stage-clear or an elimination that fired mid-sequence), for a capability (arbitrary redo, cross-field partial revert) this feature doesn't ask for.

**2. Exactly what is captured.** One checkpoint = `{"view": <outgoing view name>, "state": {...}}`. `state` holds only fields a guided-round view can change:

| Field | Why |
|---|---|
| `players[].threat`, `.eliminated`, `.commit`, `.commit_touched` | threat/commit are the per-round "stat changes" the TODO item names explicitly. `starting_threat`/`threat_per_round`/`.elimination`/`.label` are never mutated after game setup (verified: no assignment to them outside `__init__`/`from_dict`), so they're invariant across a round and omitted. |
| `quest` (`stage_n`, `side`, `points`, `progress`) | quest progress, named explicitly. |
| `active_location` (or `None`) | location progress, named explicitly — including its *existence* (travel/change/explore can create or clear it). |
| `side_quests` (list) | side-quest progress, named explicitly, including add/remove. |
| `willpower`, `staging` | named explicitly. Note `willpower` has two independent write paths — via `set_commit` (derived: `sum(commits)`) and via the direct `wp-`/`wp+` steppers on `quest_staging` (which mutate it directly, decoupled from commits) — so it must be captured as its own field, not re-derived from `players[].commit`. |
| `sailing`, `heading` | sailing/heading, named explicitly. |
| `pending_budget`, `pending_stage`, `pending_elim` | control-flow state a resolve/placement/elimination leaves behind; restoring these is what makes going back through `quest_resolution`'s placement step actually re-editable (see Task 1). |
| `quest_resolved`, `quest_outcome`, `quest_outcome_n` | the resolve's own outcome bookkeeping; must roll back together with `quest_history` or a re-resolve looks like a no-op. |
| `quest_history` (list, already capped at 20) | resolving a second time after a back-edit must replace, not append to, the (now-undone) prior entry. |

Deliberately **excluded**: `view`/`step`/`round`/`first_player` (implied by the checkpoint's own `view` tag, or invariant within a round by construction), `log`/`_seq` (see #3), `scenario`/`stages`/`stage_idx`/`card_idx` (static after `preload_scenario`, never mutated by a per-view handler), `reminders` (a standing preference, not phase-scoped play data), `game_over`, `elimination_threat`, `pending_quest_card`/`pending_side_quest_pick` (one-tick router flags, always false by the time `ScreenPlay`'s Back button is reachable).

**3. The log is append-only — always.** Every mutator in the codebase reaches the log through `log_event()`/`logEvent()` (`.append`/`.push`); nothing anywhere deletes from it. This plan keeps that invariant: going back does **not** truncate or rewrite `self.log`. It logs one new entry, `"Back to %s" % VIEW_LABELS[...]` (distinct text from `"Phase: %s"`, so the log reads as a correction, not a normal advance), and any now-stale entries (e.g. a resolve that's about to be redone) simply stay in the permanent record. This trades a slightly noisier log for never lying about what actually happened at the table — consistent with the log's existing role as a session record (see the TODO board's own "full timestamp"/"scrollable" log item).

**4. Serialization: intentionally does *not* go through `to_dict()`/`from_dict()`.** `_view_history` is a plain Python list of small dicts (also fully JSON-serializable — nothing stops it from being persisted), but this plan keeps it **transient, RAM-only, and out of both twins' `to_dict()`/`from_dict()`**. Consequences: `to_dict()`/`from_dict()` need **zero changes** (no persistence-format migration, no backward-compat risk for existing saves); a reload (device resume, or web's `localStorage` restore) always starts with an empty back-stack, and since `_view_history` is cleared at every round boundary anyway, the only thing a reload can ever lose is "being able to back up within the round you were mid-way through when you quit" — a small, clearly-scoped gap. *If the user prefers Back to survive Save & Quit / a device power cycle instead*, add a capped `view_history` key to both `to_dict()`/`toDict()` (list of `{view, state}`, same shape as in RAM) and restore it in `from_dict()`/`fromDict()`; the cap (`MAX_VIEW_HISTORY`, see below) already bounds how much that would add to `state.json`.

**5. Memory bounds.** One checkpoint is on the order of a few dozen small ints/strings/bools (≤4 players × 4 fields, a handful of quest/location/side-quest fields, ≤20 `quest_history` entries × ~6 fields as the dominant term). The guided flow visits at most ~12 views in a single round (`VIEW_ORDER` plus the optional `quest_sailing` insertion), so a stack sized to one round is naturally small; `MAX_VIEW_HISTORY = 16` is set as a generous, defensive cap on top of that (not a real-world limit — the real limit is the round boundary). **Past the cap**, the oldest checkpoint is silently evicted (FIFO) — the practical effect is identical to hitting the start of the round: the "< Back" button simply stops being available past that depth, no error. This is comfortably inside the Presto's hardware headroom: the board is an RP2350B with 520 KB of on-chip SRAM plus 8 MB of external PSRAM ([Pimoroni Presto product page](https://shop.pimoroni.com/en-us/products/presto); [Little Bird spec listing](https://littlebirdelectronics.com.au/products/presto)), and the *entire* game state (all 16 checkpoints' worth of fields combined) is smaller than the `quest_history`/`log`/`stages` data that already round-trips through JSON on every single button tap without issue.

**The rebasing mechanism itself:** because every forward-transition method (`resolve_quest`, `place_progress`, `advance_view`) reads only *current* fields and never a cached delta, "the next page always bases stat changes relative to the final values from the previous phase" falls out of restore-then-replay automatically — no special "rebase" step is implemented or needed. The one wrinkle: two CTAs (`stage_advance`, `apply_alloc`) both *mutate* state (resolve / place progress) **and** transition the view in the same button press. For these, the checkpoint must be pushed **before** that mutation (not merely before the view change), or going back would restore a view where the "final" values already have that page's own terminal action baked in un-editably. Task 1/2 call out both sites explicitly.

## Global Constraints

- **Two twins in lockstep** (Iron rule #1): web `docs/js/` first, then the firmware mirror. Identical field names, method names (camelCase in JS / snake_case in Python, matching the existing `gamestate.js` convention exactly), and behavior.
- **`python3 -m pytest tests/` stays green** (Iron rule #3), including the layout linter. Add a scene exercising the new "< Back" button's geometry.
- **Touch targets ≥ 24px** each dimension; everything within 480×480; no text collisions (linter-enforced). The Back button (96×58) and the narrowed primary CTA (360×58) both clear this easily.
- **The log is append-only, always** — Back adds a `"Back to ..."` entry; it never deletes or rewrites existing entries.
- **The checkpoint stack is transient (RAM-only)** — no changes to `to_dict()`/`from_dict()`/`toDict()`/`fromDict()` in this plan.
- **Scoped to the current round only** — cleared at every round boundary (same call sites that already reset `_round_snap`), plus the defensive `MAX_VIEW_HISTORY` cap.
- **Scoped to `ScreenPlay`'s guided round only** — not the Phases screen's free jump, not the header's overlay-screen nav stack (see Context above for why these are unrelated).
- No changes to `tools/build_tips.py` or `tests/test_tips.py`.

## File structure

- `gamestate.py` / `docs/js/gamestate.js` — checkpoint stack, `go_back`/`goBack`, `can_go_back`/`canGoBack`, small refactor of `enter_view`/`enterView`, two-line addition to `advance_view`/`advanceView`, one-line addition to `_snapshot_round`/`_snapshotRound`.
- `ui/screen_play.py` / `docs/js/screen_play.js` — `_cta` gains a `game` parameter and draws the Back button; `stage_advance`/`apply_alloc` push a checkpoint before their mutation; new `"back"` button case.
- `tests/test_gamestate_back.py` — new; Task 1's TDD tests (checkpoint mechanics + the rebasing guarantee).
- `tests/test_screen_play.py` — additions; Task 2's UI-wiring tests.
- `tests/scenes.py` — one new scene so the layout linter covers the Back button.

---

### Task 1: Checkpoint stack + `go_back`/`can_go_back` on `GameState` (both twins)

**Files:**
- Modify: `gamestate.py`, `docs/js/gamestate.js`
- Test: `tests/test_gamestate_back.py` (new)

**Interfaces:**
- New module-level constants: `PRE_ROUND_VIEWS` (Python: `("setup_game", "quest_setup")` tuple; JS: `new Set(["setup_game", "quest_setup"])`) and `MAX_VIEW_HISTORY = 16`, placed immediately after `VIEW_ORDER`.
- New `GameState` field: `self._view_history = []` (Python `__init__`) / `this._view_history = []` (JS constructor), next to `_round_snap`.
- New methods: `can_go_back() -> bool` / `canGoBack()`; `go_back() -> bool` / `goBack()`; private `_set_view(v)` / `_setView(v)`, `_push_checkpoint()` / `_pushCheckpoint()`, `_checkpoint_state() -> dict` / `_checkpointState()`, `_restore_checkpoint(state)` / `_restoreCheckpoint(state)`.
- Modified: `enter_view`/`enterView` (refactored to call `_set_view`/`_setView`, behavior unchanged), `advance_view`/`advanceView` (pushes a checkpoint before every forward step that leaves a guided-round view), `_snapshot_round`/`_snapshotRound` (also clears `_view_history`).

- [ ] **Step 1: Write the failing tests** — `tests/test_gamestate_back.py`:

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gamestate import GameState, MAX_VIEW_HISTORY


def _round1(g):
    """Advance a fresh GameState past setup into round 1 (resource_planning)."""
    g.advance_view()
    return g


def test_back_unavailable_at_round_start():
    g = _round1(GameState())
    assert g.can_go_back() is False
    assert g.go_back() is False
    assert g.view == "resource_planning"


def test_advance_pushes_checkpoint_back_restores_edited_value():
    g = _round1(GameState())
    g.set_commit(0, 3)                 # willpower=3, "final" value for quest_commit
    g.advance_view()                   # -> quest_staging; commit's phase is left behind
    assert g.view == "quest_staging"
    assert g.can_go_back() is True
    assert g.go_back() is True
    assert g.view == "quest_commit"
    assert g.willpower == 3            # restored exactly as it stood when left
    assert g.players[0].commit == 3


def test_back_to_back_walks_multiple_views():
    g = _round1(GameState())
    g.advance_view()                   # quest_commit
    g.advance_view()                   # quest_staging
    g.advance_view()                   # travel (no resolution: not resolved)
    assert g.view == "travel"
    assert g.go_back() and g.view == "quest_staging"
    assert g.go_back() and g.view == "quest_commit"
    assert g.go_back() and g.view == "resource_planning"
    assert g.can_go_back() is False    # start of the round


def test_back_cleared_at_round_boundary():
    g = _round1(GameState())
    g.advance_view()
    g.advance_view()
    assert g.can_go_back() is True
    g.view = "refresh"
    g.end_round()
    assert g.can_go_back() is False


def test_back_logs_a_distinct_event_without_erasing_history():
    g = _round1(GameState())
    g.advance_view()
    n = len(g.log)
    g.go_back()
    assert len(g.log) == n + 1                 # appended, nothing removed
    assert "Back to" in g.log[-1]["text"]


def test_back_history_capped():
    g = _round1(GameState())
    for _ in range(MAX_VIEW_HISTORY + 5):
        g._push_checkpoint()
    assert len(g._view_history) == MAX_VIEW_HISTORY


def test_resolve_quest_rebases_after_back_and_edit():
    """The core 'rebase' requirement: back up to quest_staging, change the
    committed values, and re-resolving uses the NEW values - the old
    resolution's effects (threat raise, quest_history entry) are undone,
    not stacked on top of."""
    g = _round1(GameState(2, 25))
    g.view = "quest_staging"
    g.willpower, g.staging = 0, 5
    # -- simulate the quest_staging "Next Phase" (stage_advance) handler --
    g._push_checkpoint()
    res = g.resolve_quest(g.willpower, g.staging)
    assert res["outcome"] == "fail"
    g.enter_view("quest_resolution")
    assert g.players[0].threat == 30            # 25 + 5 shortfall
    assert len(g.quest_history) == 1

    # back up to quest_staging: the fail's threat raise and history entry
    # are undone (restored to pre-resolve state), not left dangling
    assert g.go_back() and g.view == "quest_staging"
    assert g.players[0].threat == 25
    assert g.quest_resolved is False
    assert len(g.quest_history) == 0

    # edit, then redo the "Next Phase" action - now a success
    g.willpower = 8
    g._push_checkpoint()
    res = g.resolve_quest(g.willpower, g.staging)
    assert res["outcome"] == "success"
    g.enter_view("quest_resolution")

    assert g.players[0].threat == 25             # the old +5 fail was NOT reapplied
    assert len(g.quest_history) == 1              # the stale fail entry is gone, not doubled
    assert g.quest_history[0]["outcome"] == "success"


def test_place_progress_rebases_after_back_and_reallocate():
    g = _round1(GameState(2, 25))
    g.active_location = {"points": 10, "progress": 0}
    g.quest = {"stage_n": 1, "side": "A", "points": 10, "progress": 0}
    g.view = "quest_resolution"
    g.quest_resolved = True
    g.quest_outcome = "success"
    g.pending_budget = 3

    # -- simulate apply_alloc with the default auto-split (fills location first) --
    g._push_checkpoint()
    alloc = g.auto_split(g.pending_budget)
    g.place_progress(alloc)
    g.pending_budget = 0
    g.enter_view("travel")
    assert g.active_location["progress"] == 3
    assert g.quest["progress"] == 0

    # back up: the placement is undone, not left applied
    assert g.go_back() and g.view == "quest_resolution"
    assert g.active_location["progress"] == 0
    assert g.pending_budget == 3

    # reallocate differently and redo
    g._push_checkpoint()
    g.place_progress({"location": 1, "quest": 2, "side_quests": []})
    g.pending_budget = 0
    g.enter_view("travel")

    assert g.active_location["progress"] == 1     # not 3 + 1 = 4
    assert g.quest["progress"] == 2                # not stacked either
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_gamestate_back.py -q` → `AttributeError: 'GameState' object has no attribute 'can_go_back'` (or similar).

- [ ] **Step 3: Implement in `gamestate.py`.** Add the constants after `VIEW_ORDER`:

```python
# One-time pre-round screens: the back button never reaches into these -
# there is nothing before round 1 to "go back" to.
PRE_ROUND_VIEWS = ("setup_game", "quest_setup")

# Per-round back-navigation depth. The guided flow visits at most ~12 views
# in one round (VIEW_ORDER plus quest_sailing) so this is a generous safety
# margin, not a real-world limit - the hard boundary is the round itself:
# _snapshot_round() (called at every round start) always clears the stack,
# so "Back" can never cross into a previous round.
MAX_VIEW_HISTORY = 16
```

Add `self._view_history = []` in `__init__`, next to `self._round_snap = None`.

Change `_snapshot_round` to also clear the stack:

```python
def _snapshot_round(self):
    self._round_snap = {"t": self._now(),
                        "threats": [p.threat for p in self.players],
                        "progress": self._total_progress(),
                        "quest": self.quest["progress"]}
    self._view_history = []
```

Refactor `enter_view` to share a raw transition primitive (behavior unchanged):

```python
def _set_view(self, v):
    """Raw view/step transition - no logging, no history bookkeeping.
    Shared by enter_view (forward) and go_back (undo)."""
    self.view = v
    self.step = VIEW_STEP[v]

def enter_view(self, v):
    """Central view transition: sets the step and logs the phase start."""
    self._set_view(v)
    self.log_event("Phase: %s" % VIEW_LABELS.get(v, v))
```

Add checkpoint pushes to `advance_view` (only the two marked lines are new):

```python
def advance_view(self):
    if self.view == "setup_game":
        self.log_event("Setup complete - round 1 begins (quest %s needs %d)"
                       % (self.quest_label(), self.quest["points"]))
        self.enter_view(VIEW_ORDER[0])
        for p in self.players:
            p.commit_touched = False
        self._snapshot_round()
        return
    if self.view == "quest_sailing":
        self._push_checkpoint()                              # NEW
        self.enter_view("quest_commit")
        return
    self._push_checkpoint()                                  # NEW
    i = VIEW_ORDER.index(self.view)
    nxt = VIEW_ORDER[(i + 1) % len(VIEW_ORDER)]
    if self.view == "quest_staging":
        nxt = "travel"
    if self.view == "resource_planning" and self.sailing:
        nxt = "quest_sailing"
    self.enter_view(nxt)
    if nxt == "quest_sailing":
        self.shift_heading(1, "winds shift")
```

Add the checkpoint/restore/back methods (e.g. after `advance_view`):

```python
def _push_checkpoint(self):
    """Snapshot the current (about-to-be-left) view's final state onto the
    back-navigation stack. No-op before round 1 - there is nothing to back
    into yet."""
    if self.view in PRE_ROUND_VIEWS:
        return
    self._view_history.append({"view": self.view, "state": self._checkpoint_state()})
    if len(self._view_history) > MAX_VIEW_HISTORY:
        self._view_history.pop(0)

def _checkpoint_state(self):
    """Copy of every field a guided-round view can change. Excludes the log
    (append-only - go_back() adds a 'Back to ...' entry rather than erasing
    history), navigation fields (view/step/round - implied by the
    checkpoint's own view tag / invariant within a round), and static
    fields (scenario, stages, reminders, elimination settings)."""
    return {
        "players": [{"threat": p.threat, "eliminated": p.eliminated,
                     "commit": p.commit, "commit_touched": p.commit_touched}
                    for p in self.players],
        "quest": dict(self.quest),
        "active_location": dict(self.active_location) if self.active_location else None,
        "side_quests": [dict(s) for s in self.side_quests],
        "willpower": self.willpower,
        "staging": self.staging,
        "sailing": self.sailing,
        "heading": self.heading,
        "pending_budget": self.pending_budget,
        "pending_stage": dict(self.pending_stage) if self.pending_stage else None,
        "pending_elim": self.pending_elim,
        "quest_resolved": self.quest_resolved,
        "quest_outcome": self.quest_outcome,
        "quest_outcome_n": self.quest_outcome_n,
        "quest_history": [dict(e) for e in self.quest_history],
    }

def _restore_checkpoint(self, state):
    """Write a _checkpoint_state() snapshot back onto live state."""
    for p, pd in zip(self.players, state["players"]):
        p.threat = pd["threat"]
        p.eliminated = pd["eliminated"]
        p.commit = pd["commit"]
        p.commit_touched = pd["commit_touched"]
    self.quest = dict(state["quest"])
    self.active_location = dict(state["active_location"]) if state["active_location"] else None
    self.side_quests = [dict(s) for s in state["side_quests"]]
    self.willpower = state["willpower"]
    self.staging = state["staging"]
    self.sailing = state["sailing"]
    self.heading = state["heading"]
    self.pending_budget = state["pending_budget"]
    self.pending_stage = dict(state["pending_stage"]) if state["pending_stage"] else None
    self.pending_elim = state["pending_elim"]
    self.quest_resolved = state["quest_resolved"]
    self.quest_outcome = state["quest_outcome"]
    self.quest_outcome_n = state["quest_outcome_n"]
    self.quest_history = [dict(e) for e in state["quest_history"]]

def can_go_back(self):
    """True if go_back() has a checkpoint to restore (mid-round, at least
    one forward step taken)."""
    return bool(self._view_history)

def go_back(self):
    """Undo the most recent forward transition: restore the previous view's
    final state (as it stood when it was left) and re-enter it. Returns
    False if there is nothing to go back to (start of the round)."""
    if not self._view_history:
        return False
    cp = self._view_history.pop()
    self._restore_checkpoint(cp["state"])
    self._set_view(cp["view"])
    self.log_event("Back to %s" % VIEW_LABELS.get(cp["view"], cp["view"]))
    return True
```

- [ ] **Step 4: Run again → green.** `python3 -m pytest tests/test_gamestate_back.py -q`.

- [ ] **Step 5: Mirror in `docs/js/gamestate.js`** (camelCase methods, snake_case fields, matching the rest of the file's existing convention):

```js
export const PRE_ROUND_VIEWS = new Set(["setup_game", "quest_setup"]);
export const MAX_VIEW_HISTORY = 16;
```
placed right after the `VIEW_ORDER` export. In the constructor, next to `this._round_snap = null;`: `this._view_history = [];`. In `_snapshotRound()`, append `this._view_history = [];`. Replace `enterView`/add `_setView`:

```js
_setView(v) {
  this.view = v;
  this.step = VIEW_STEP[v];
}

enterView(v) {
  this._setView(v);
  this.logEvent(`Phase: ${VIEW_LABELS[v] ?? v}`);
}
```

Add the two `this._pushCheckpoint();` calls to `advanceView` in the same two spots as the Python version (before the `quest_sailing -> quest_commit` early return, and before the general `VIEW_ORDER` walk). Add:

```js
_pushCheckpoint() {
  if (PRE_ROUND_VIEWS.has(this.view)) return;
  this._view_history.push({ view: this.view, state: this._checkpointState() });
  if (this._view_history.length > MAX_VIEW_HISTORY) this._view_history.shift();
}

_checkpointState() {
  return {
    players: this.players.map(p => ({ threat: p.threat, eliminated: p.eliminated,
                                      commit: p.commit, commit_touched: p.commit_touched })),
    quest: { ...this.quest },
    active_location: this.active_location ? { ...this.active_location } : null,
    side_quests: this.side_quests.map(s => ({ ...s })),
    willpower: this.willpower,
    staging: this.staging,
    sailing: this.sailing,
    heading: this.heading,
    pending_budget: this.pending_budget,
    pending_stage: this.pending_stage ? { ...this.pending_stage } : null,
    pending_elim: this.pending_elim,
    quest_resolved: this.quest_resolved,
    quest_outcome: this.quest_outcome,
    quest_outcome_n: this.quest_outcome_n,
    quest_history: this.quest_history.map(e => ({ ...e })),
  };
}

_restoreCheckpoint(state) {
  this.players.forEach((p, i) => {
    const pd = state.players[i];
    p.threat = pd.threat;
    p.eliminated = pd.eliminated;
    p.commit = pd.commit;
    p.commit_touched = pd.commit_touched;
  });
  this.quest = { ...state.quest };
  this.active_location = state.active_location ? { ...state.active_location } : null;
  this.side_quests = state.side_quests.map(s => ({ ...s }));
  this.willpower = state.willpower;
  this.staging = state.staging;
  this.sailing = state.sailing;
  this.heading = state.heading;
  this.pending_budget = state.pending_budget;
  this.pending_stage = state.pending_stage ? { ...state.pending_stage } : null;
  this.pending_elim = state.pending_elim;
  this.quest_resolved = state.quest_resolved;
  this.quest_outcome = state.quest_outcome;
  this.quest_outcome_n = state.quest_outcome_n;
  this.quest_history = state.quest_history.map(e => ({ ...e }));
}

canGoBack() {
  return this._view_history.length > 0;
}

goBack() {
  if (!this._view_history.length) return false;
  const cp = this._view_history.pop();
  this._restoreCheckpoint(cp.state);
  this._setView(cp.view);
  this.logEvent(`Back to ${VIEW_LABELS[cp.view] ?? cp.view}`);
  return true;
}
```

- [ ] **Step 6: Port the test file to a quick manual JS sanity check** (no JS test runner exists in this repo — parity is verified via `tests/test_gamestate_back.py` as the source of truth, plus the browser walkthrough in Task 3). Read back through `docs/js/gamestate.js` and confirm every method above has a 1:1 Python counterpart with matching field names.

- [ ] **Step 7: Full suite → green.** `python3 -m pytest tests/ -q`.

---

### Task 2: "< Back" button on `ScreenPlay` (both twins)

**Files:**
- Modify: `ui/screen_play.py`, `docs/js/screen_play.js`
- Modify: `tests/test_screen_play.py`, `tests/scenes.py`

**Interfaces:**
- `_cta` gains a `game` parameter, inserted in the same position `game` already sits in this file's other zone-drawing helpers (`d, pal, game, ...` in Python; `ctx, game, ...` in JS): Python `_cta(self, d, pal, game, label, id, fill=None, fg=None)`; JS `_cta(ctx, game, label, id, fill = pal.btn_ok, fg = pal.gold)`.
- New module-level layout constant next to `MARGIN`/`CTA_Y`/`CTA_H`: `BACK_W = 96`.
- New button id: `("back",)` / `["back"]`.

- [ ] **Step 1: Write the failing tests** — add to `tests/test_screen_play.py`:

```python
def test_back_button_hidden_at_round_start():
    hw, pal, game, screen = _setup("resource_planning")
    screen.draw(hw, game, pal)
    assert "back" not in _ids(screen)
    advance = _find(screen, ("advance",))
    assert (advance.x, advance.w) == (8, 464)      # full-width CTA, unchanged


def test_back_button_shown_after_a_forward_step_and_restores_view():
    hw, pal, game, screen = _setup("resource_planning")
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("advance",)), game)   # -> quest_commit
    screen.draw(hw, game, pal)
    assert "back" in _ids(screen)
    back = _find(screen, ("back",))
    advance = _find(screen, ("advance",))
    assert (back.x, back.w) == (8, 96)
    assert (advance.x, advance.w) == (112, 360)
    assert screen.on_button(back, game) is True
    assert game.view == "resource_planning"


def test_back_resets_screen_local_allocation_and_banner_scratch():
    hw, pal, game, screen = _setup("quest_staging")
    game.willpower, game.staging = 11, 7
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("stage_advance",)), game)   # -> quest_resolution, success
    screen.draw(hw, game, pal)
    assert screen.alloc is not None
    screen.on_button(_find(screen, ("back",)), game)
    assert screen.alloc is None
    assert screen.banner is None
    assert game.view == "quest_staging"


def test_back_noop_returns_none_when_history_empty():
    from ui.widgets import Button
    hw, pal, game, screen = _setup("resource_planning")
    screen.draw(hw, game, pal)
    assert screen.on_button(Button(("back",), 0, 0, 1, 1), game) is None
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_screen_play.py -q -k back` → failures (no `"back"` button drawn, `_cta` signature mismatch).

- [ ] **Step 3: Implement in `ui/screen_play.py`.** Add `BACK_W = 96` next to the other layout constants. Rewrite `_cta`:

```python
def _cta(self, d, pal, game, label, id, fill=None, fg=None):
    show_back = game.can_go_back()
    x, w = MARGIN, 480 - 2 * MARGIN
    if show_back:
        bb = Button(("back",), MARGIN, CTA_Y, BACK_W, CTA_H)
        bevel(d, pal, bb.x, bb.y, bb.w, bb.h, pal.btn)
        text_center(d, pal, "< Back", bb.x + bb.w / 2, CTA_Y + 20, 2, pal.tan)
        self.buttons.append(bb)
        x = MARGIN + BACK_W + MARGIN
        w = 480 - x - MARGIN
    b = Button(id, x, CTA_Y, w, CTA_H)
    bevel(d, pal, b.x, b.y, b.w, b.h,
          fill if fill is not None else pal.btn_ok, t=3)
    text_center(d, pal, label, b.x + b.w / 2, CTA_Y + 20, 2,
                fg if fg is not None else pal.gold)
    self.buttons.append(b)
```

Update every call site (`grep -n "self\._cta(" ui/screen_play.py` — 12 sites: `setup_game`, `resource_planning`, `quest_commit`, `_draw_sailing` ×2, `_draw_staging`, `refresh`, the default combat/encounter branch, `_draw_quest_setup`, `_draw_travel`, `_draw_resolution` ×2) to pass `game` as the third argument, e.g. `self._cta(d, pal, "Begin Round 1", ("advance",))` → `self._cta(d, pal, game, "Begin Round 1", ("advance",))`. Every call site already has `game` in scope (it's either `draw`'s own parameter or a parameter of the `_draw_*` helper it's called from), so this is a mechanical argument insertion, not a control-flow change. `setup_game` and `quest_setup` never show the Back button regardless (history is always empty there — see `PRE_ROUND_VIEWS`), so no call site needs special-casing.

Add the checkpoint push to the two mutate-then-transition handlers in `on_button` (the two other call sites of `enter_view` besides the plain-`advance` path):

```python
if k == "stage_advance":
    game._push_checkpoint()
    if not game.quest_resolved:
        res = game.resolve_quest(game.willpower, game.staging)
        self.alloc = None
        if res["outcome"] == "success":
            game.pending_budget = res["budget"]
        self.toast = [self._outcome_toast(game)]
    game.enter_view("quest_resolution")
    return True
```

```python
if k == "apply_alloc":
    game._push_checkpoint()
    used = self.alloc["location"] + self.alloc["quest"] + sum(self.alloc["side_quests"])
    discard = game.pending_budget - used
    completed = game.place_progress(self.alloc)
    msg = "Placed %d progress" % used
    if discard > 0:
        msg += ", discarded %d (over capacity)" % discard
    if completed:
        msg += " (" + ", ".join(completed) + ")"
    game.log_event(msg)
    game.pending_budget = 0
    self.alloc = None
    game.enter_view("travel")
    if game.pending_stage:
        from ui.modals import StageCompleteModal
        return ("modal", StageCompleteModal(game))
    return True
```

Add the new case (near the other view-transition cases, e.g. just before `"advance"`):

```python
if k == "back":
    if not game.go_back():
        return None
    self.alloc = None
    self.banner = None
    return True
```

- [ ] **Step 4: Mirror in `docs/js/screen_play.js`.** Add `const BACK_W = 96;` next to the other layout constants.

```js
_cta(ctx, game, label, id, fill = pal.btn_ok, fg = pal.gold) {
  const showBack = game.canGoBack();
  let x = MARGIN, w = 480 - 2 * MARGIN;
  if (showBack) {
    const bb = new Button(["back"], MARGIN, CTA_Y, BACK_W, CTA_H);
    bevel(ctx, bb.x, bb.y, bb.w, bb.h, pal.btn);
    textCenter(ctx, "< Back", bb.x + bb.w / 2, CTA_Y + 20, 2, pal.tan);
    this.buttons.push(bb);
    x = MARGIN + BACK_W + MARGIN;
    w = 480 - x - MARGIN;
  }
  const b = new Button(id, x, CTA_Y, w, CTA_H);
  bevel(ctx, b.x, b.y, b.w, b.h, fill, false, 3);
  textCenter(ctx, label, b.x + b.w / 2, CTA_Y + 20, 2, fg);
  this.buttons.push(b);
}
```

Update every `this._cta(ctx, ...)` call site (same 12 sites as Python, `grep -n "this\._cta(" docs/js/screen_play.js`) to `this._cta(ctx, game, ...)`. Add `game._pushCheckpoint();` as the first line inside the `"stage_advance"` and `"apply_alloc"` cases (mirroring the Python bodies above exactly). Add:

```js
if (k === "back") {
  if (!game.goBack()) return null;
  this.alloc = null;
  this.banner = null;
  return true;
}
```

- [ ] **Step 5: Run tests → green.** `python3 -m pytest tests/test_screen_play.py -q`.

- [ ] **Step 6: Add a layout scene.** In `tests/scenes.py`, add a helper and scene entry so the linter covers the Back button's geometry on a realistic view:

```python
def _seed_back_history(g):
    g._view_history = [{"view": "quest_commit", "state": g._checkpoint_state()}]
```

and in `SCENES`, alongside the existing `"play_quest_staging": _play("quest_staging"),` entry:

```python
"play_quest_staging_can_back": _play("quest_staging", mutate=_seed_back_history),
```

- [ ] **Step 7: Full suite → green.** `python3 -m pytest tests/ -q`.

---

### Task 3: Verification

- [ ] **Step 1: Render and inspect.** `python3 tools/preview.py play_quest_staging_can_back /tmp/back_btn.png` — confirm the "< Back" button and narrowed CTA sit cleanly side by side with no overlap, and both read as clearly touchable.
- [ ] **Step 2: Browser walkthrough** (`docs/` served locally). Start a game, play into round 1, and exercise all three rebasing paths:
  - Plain view: on `quest_commit`, commit some willpower, advance to `quest_staging`, tap **< Back**, confirm the commit values are exactly as left, change them, advance again, confirm `quest_staging`'s totals reflect the new commits.
  - Resolve rebase: commit willpower less than staging (a fail), advance through resolution, note the threat raise in the Players zone and the log; tap **< Back** from `quest_resolution`, confirm threat is back to pre-fail; raise willpower above staging, advance again (now success), confirm threat did **not** retain the old fail's raise and the log shows both the "Phase:"/outcome entries from the first pass and a single fresh resolution, not a doubled one.
  - Placement rebase: get to a success resolution with an active location and quest both open, let it auto-split, advance to `travel`; tap **< Back**, confirm the split reverts to unplaced (budget restored) and the location/quest progress numbers drop back; re-split differently and advance again; confirm the location/quest progress reflects only the second split.
  - Confirm the "< Back" button is absent on `resource_planning` at the start of a fresh round (and after `end_round()`), and absent on `setup_game`/`quest_setup`.
  - Capture console errors (should be none).
- [ ] **Step 3: Full suite → green; report.** `python3 -m pytest tests/ -q`. Do not deploy to the Presto (device deploys are main-session-only per `CLAUDE.md`).

---

## Self-Review

**Spec coverage:** capture mechanism (snapshot stack vs. delta log, with the trade-off) → Architecture; exact fields captured (players/quest/location/side-quests/sailing/heading/staging/willpower plus the control-flow fields needed for the resolve/placement rebase) → Architecture table; serialization/reload behavior (deliberately outside `to_dict`/`from_dict`, why, and the persisted alternative) → Architecture #4; rebasing mechanism (restore + natural recompute, with the two special-cased mutate-then-transition CTAs called out) → Architecture closing paragraph, Task 1 Step 3, Task 2 Step 3; memory bounds (per-checkpoint size, natural per-round count, `MAX_VIEW_HISTORY` cap, FIFO eviction behavior, verified Presto RAM headroom) → Architecture #5. A recommended default (snapshot stack, transient) is stated with a short alternative note for each of the two real forks (snapshot-vs-delta-log; transient-vs-persisted).

**Placeholder scan:** Task 1 carries complete, runnable test code and complete method bodies for both twins (no "implement similarly" hand-waving on the core mechanism). Task 2 gives the exact new `_cta` bodies for both twins and the exact diffs to `stage_advance`/`apply_alloc`; the 12 mechanical call-site updates are described precisely (what changes, why it's safe, a grep to find every site) rather than left vague, consistent with how the sibling quest-card-modal plan treats similarly-mechanical multi-site edits.

**Type consistency:** `_view_history` entries (`{"view": str, "state": {...}}`) are produced by `_push_checkpoint`/`_pushCheckpoint` and consumed only by `go_back`/`goBack` via `_restore_checkpoint`/`_restoreCheckpoint` — the same shape throughout, in both twins, matching field-for-field. `_checkpoint_state`'s keys match `_restore_checkpoint`'s reads exactly (both enumerated together in Task 1 Step 3). The `_cta` signature change is applied identically to all 12 call sites in each twin.
