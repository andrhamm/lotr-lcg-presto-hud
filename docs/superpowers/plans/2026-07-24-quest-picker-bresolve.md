# Guided Progress Resolution (M4-B resolve) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Whenever progress placement (manual edit *or* a normal successful quest resolution) pushes the active location, the main quest, or a side quest to/over its own quest points, walk the player through resolving it in the correct order instead of leaving the state silently inconsistent: explore the location and carry its excess onto the quest card, then — if the quest itself clears — reveal the next stage's side A (story/setup text), flip it to side B, handling branch-stage selection and catalog-driven quest points along the way, then offer each completed side quest. Conditional stages (no printed quest points — common: ~137/400 catalogued stage-cards) get an explicit, player-confirmed "Advance" instead of a numeric trigger. This is the capstone of the M4-B family — B-core, B-modal, B-sidequest, B-icons, B-data, and B-tips are already shipped; this plan is the last remaining piece.

**Architecture:** A new modal, `ResolutionModal`, opened via the codebase's established "pending flag, consumed on the next main-loop tick" pattern (same shape as `pending_quest_card`/`pending_side_quest_pick`) — because the router holds one modal at a time and `QuestingProgressModal` (a modal) cannot stack another modal on itself. `ResolutionModal` carries **no constructor payload** beyond `game`: like `QuestCardModal`, it re-derives what to show from live game state (`active_location`, `quest`, `side_quests`, `stages`/`stage_idx`/`card_idx`) every time, via a pure `_derive()` step function called after every mutation. This makes it naturally correct for *any* combination of edits (location-only, quest-only, several side quests, all three at once) without precomputing a plan, and it turns out to **never need to loop more than one stage-advance per pass**: the rulebook (verified below) discards excess quest progress on advance rather than carrying it forward, so the derivation provably terminates after at most one location step + one quest-advance (itself at most a branch-choice + a reveal + a flip) + one step per over-full side quest.

Catalog games (`game.stages` non-empty) get the full guided flow. Custom/uncatalogued games (`game.scenario is None`, B-core's existing fallback) keep today's behavior for stage advancement (the manual-entry `StageCompleteModal`, now reachable from the manual-edit path too, which it wasn't before) — there is no catalog text/branch data to guide them with. Active-location overflow is fixed for **both** game kinds, since it's a catalog-independent numeric rule.

**Tech Stack:** ES modules (web, Canvas) + MicroPython (firmware); pytest + the scene layout linter.

**Context:** Read `docs/superpowers/specs/2026-07-24-quest-picker-bcore-design.md` ("M4-B family" table + "Verified mechanics") before starting. B-core built the model (`scenario`/`stages`/`stage_idx`/`card_idx`/`quest.side`) and the pre-round-1 first flip only; B-modal built the read-only `QuestCardModal` (never mutates `game`); B-sidequest built `SideQuestPickModal`. This plan is the only one that mutates `stage_idx`/`card_idx`/`quest.side` after round 1 begins.

**Verified mechanics** (re-verified against the rulebook in this repo's scratchpad, `lotr_rules.pdf`, `pdftotext -layout`; page numbers refer to the printed rulebook):

- **Quest Points, p.8:** "The number of progress tokens that must be placed on this card in order to proceed to the next stage of the scenario." Same page, location quest points: "...to fully explore the location and discard it from play."
- **Side A → B, p.8:** "Side A is the back of the card, and provides story and setup information. After reading and following any instructions on Side A, players flip the card to Side B. Side B contains the information necessary to move to the next stage of the quest."
- **Location overflow → quest card, p.15 (worked example):** "Any progress tokens that would be placed on a quest card are instead placed on the active location... If a location ever has as many progress tokens as it has quest points, that location is considered explored and is discarded from play." Worked example: a location with 2 quest points receives 2 of 3 placed tokens (explored, discarded); "the other progress token is then placed on the current quest card." **This is the location→quest overflow behavior** — confirmed, and already correctly implemented for the *auto-split* success path (`auto_split`/`place_progress`); this plan adds it for the **manual-edit** path, which has none of this today.
- **Quest overflow does NOT carry to the next stage, p.22 — a correction to a natural-but-wrong assumption:** "Players immediately advance to the next stage of a quest as soon as they place a number of progress tokens equal to or greater than the number of quest points the current quest card has. **Additional progress tokens earned against the quest do not carry over to the next stage. All progress tokens on the quest are returned to the token bank when players advance to the next stage.**" So excess quest progress is **discarded**, never carried forward — unlike the location→quest case. This is what makes the step machine's termination bound provable (see Architecture).
- **New stage's instructions resolve on reveal, p.22 (same paragraph):** "Players follow any instructions on the newly revealed quest card as it is revealed... The game state of other cards does not change... and the round sequence is not interrupted." Confirms the reveal→flip pattern applies uniformly at every advance, not just pre-round-1 (matching B-core's own "Verified mechanics": "the flip recurs at every advance").
- **Winning the game, p.21:** "If at least one player survives through the completion of the final stage of the scenario, the game ends in a victory for the players." — the base victory condition is completing the catalogued final stage; this plan triggers it when advancing would run past the end of `game.stages`, plus keeps the existing explicit "Declare Victory" override for scenarios whose real ending isn't just "run out of stages" (the catalog can't always model that).
- **"Victory X" is a scoring keyword, not an alternate win condition — a second correction, p.24:** "Some enemy and location cards award victory points when they are defeated... victory points are applied to the score of the entire group" at end-of-game **Scoring** (p.22, a separate, already-won-the-game bookkeeping step). The compiled catalog's per-card `"victory"` field (sourced from the DragnCards `victoryPoints` column, `tools/build_card_data.py:335`) is this same keyword applied to some later-cycle quest/stage cards; **this rulebook only documents it for enemy/location cards** (Core Set doesn't use it on a quest card), so treating a non-null `victory` as an auto-win trigger would be unverified and is explicitly **not** done here. `victory` is left untouched by this plan — it's a candidate data point for the future Stats sub-project (`docs/superpowers/plans/2026-07-24-game-history.md`), not a resolution trigger.
- **Side-quest excess is UNVERIFIED against this rulebook** — Side Quest is not a Core Set mechanic (no "side quest" hits anywhere in the rulebook text), so there's no citable rule for what happens to excess progress on one. This plan's side-quest step therefore treats reaching target as informational-only (offer to mark it complete; excess is neither computed nor displayed) rather than asserting a discard/carry rule that can't be backed by a citation. If a future FAQ citation surfaces, revisit.
- **Branch selection wording ("first player chooses")** is inherited from B-core's own catalog survey (`docs/superpowers/plans/2026-07-24-quest-picker-bcore.md` Task-2 findings), not this rulebook (branching isn't a named rulebook mechanic; it's per-card printed text, e.g. Passage Through Mirkwood's "A Fork in the Road"). Not re-verified here; B-core's citation stands.

## Global Constraints

- **Two twins in lockstep** (Iron rule #1): web `docs/js/` first (verified in-browser), then the firmware mirror. A task is done only when both twins + tests are green.
- **`python3 -m pytest tests/` stays green** (Iron rule #3), including the scene layout linter. Add a scene per new modal step.
- **`ResolutionModal(game)` takes no other constructor argument except an optional `force_advance` flag** — like `QuestCardModal`, everything else is re-derived from `game` on construction and after every mutation via `self.step = self._derive()`. Never precompute a queue of steps.
- **At most one stage advance per resolution pass** — provable from the "excess is discarded, not carried" rule above. Do not build cascade/loop protection for multi-stage advancement; it cannot happen. (Do keep the *location→quest* single hand-off, and the *N independent side quests*, each its own step.)
- **Priority order within one pass** (this **is** "the proper order to resolving things" from the brief): unfinished reveal (side A already showing, i.e. a previous pass was interrupted) → active location overflow → quest advance (branch-choice → reveal → flip, as needed) → each over-full side quest, one at a time → done.
- **Modal-can't-stack-on-modal:** `QuestingProgressModal` and the quest-success path's `AllocationModal`/`ScreenPlay.apply_alloc` are the only two entry points. `apply_alloc` lives on a **screen** (`ScreenPlay`), so it may return a `("modal", ResolutionModal(game))` transition directly. `QuestingProgressModal` is itself a **modal**, so it must close and set `game.pending_resolution`, consumed on the next main-loop tick — exactly the existing `pending_quest_card`/`pending_side_quest_pick` pattern in `main.py`/`main.js`.
- **`pending_resolution` is a tri-state** (`False | "auto" | "forced"`), not a bool: `"forced"` (set by the new quest-row "Advance" affordance) skips the numeric gate on the quest step *only*; the location step and side-quest steps are never force-skipped. Serialized in `to_dict`/`from_dict` like its siblings.
- **Custom games (`game.scenario is None`, `game.stages == []`) are out of scope for the rich flow** — `ResolutionModal` is never opened for them. Location overflow gets the same fix either way (`resolve_location_overflow()` is catalog-independent). Quest overflow keeps routing to the existing, unchanged `StageCompleteModal` — the only change is that the *manual-edit* path can now reach it too (today only the auto-split success path can).
- **`gamestate.py` stays pure logic** (no hardware/file I/O) — all new methods are plain state transforms + `log_event` calls, mirroring the existing style of `place_progress`/`resolve_quest`.
- Touch targets ≥ 24px each dimension; everything within 480×480; no text collisions (linter-enforced).

## File structure

- `gamestate.py` + `docs/js/gamestate.js` — new `pending_resolution` field; new methods `needs_resolution`, `resolve_location_overflow`, `clear_and_advance`; `place_progress`/`placeProgress` gains a catalog-aware branch; serialization.
- `ui/modals.py` (new `ResolutionModal`) + `docs/js/screens.js` (mirror).
- `ui/modals.py` (`QuestingProgressModal`) + `docs/js/screens.js` (mirror) — close-time resolution check; new "Advance" icon on the quest row.
- `ui/screen_play.py` (`apply_alloc`) + `docs/js/screen_play.js` (mirror) — route the quest-success path's `pending_resolution` to `ResolutionModal` alongside the existing `pending_stage` → `StageCompleteModal` check.
- `main.py` + `docs/js/main.js` — new top-level `pending_resolution` dispatch block (mirrors the existing `pending_quest_card` block).
- `tests/test_gamestate_resolution.py` (new), `tests/test_resolution_modal.py` (new), `tests/scenes.py`, `tests/test_gamestate.py` (regression check on `place_progress`'s custom-game branch).

---

### Task 1: GameState primitives — `needs_resolution`, `resolve_location_overflow`, `clear_and_advance`, catalog-aware `place_progress`

**Files:**
- Modify: `gamestate.py` (constructor ~`:157-193`, `place_progress` ~`:474-506`, `to_dict`/`from_dict` ~`:550-639`), `docs/js/gamestate.js` (mirror)
- Test: `tests/test_gamestate_resolution.py` (new)

**Interfaces (Produces):**
- Field: `self.pending_resolution = False` (`False | "auto" | "forced"`), next to `self.pending_stage`.
- `needs_resolution(self) -> bool` — true iff the active location, the quest, or any side quest is currently at/over its own (positive) quest points.
- `resolve_location_overflow(self) -> int` — no-op (`return 0`) unless the active location is at/over its points; otherwise explores it (logs, discards, `active_location = None`), credits any excess to `quest["progress"]`, and returns the excess (0 on an exact match).
- `clear_and_advance(self, card_idx=0) -> bool` — clears the current (side-B) stage: logs "cleared" (noting any discarded excess — it is **not** carried forward, see Verified mechanics), advances `stage_idx`, sets `card_idx`, resets `quest["side"]="A"`, `quest["points"]=0`, `quest["progress"]=0`, refreshes `self.sailing` from the new stage's chosen card. Returns `False` and mutates nothing if there is no next stage (`stage_idx + 1 >= len(stages)`) — the caller treats that as the victory condition. Callers should follow a `True` return with `flip_to_b()` (existing method, unchanged, reused verbatim for every advance and not just the pre-round-1 one) once the side-A text has been shown.
- `place_progress(self, alloc)` — **behavior change, same signature**: when the quest clears (`points>0 and progress>=points`) and `self.stages` is non-empty (catalog game), it now sets `self.pending_resolution = "auto"` and does **not** touch `quest["side"]`/`stage_n`/`stages`-related fields — all of that moves to `ResolutionModal` (Task 2), called on the next tick. When `self.stages` is empty (custom game), behavior is **unchanged**: it still calls the legacy `_advance_quest_stage()` synchronously and sets `pending_stage`.
- Serialization: `pending_resolution` added to `to_dict`/`from_dict` (default `False`), same shape as `pending_quest_card`.

- [ ] **Step 1: Write the failing test** (`tests/test_gamestate_resolution.py`):

```python
import gamestate

STAGES = [
    {"stage": 1, "cards": [{"questPoints": 2, "victory": None, "sailing": False,
        "faces": [{"side": "A", "name": "Flies and Spiders", "text": "Setup text."},
                  {"side": "B", "name": "Flies and Spiders", "text": None}]}]},
    {"stage": 2, "branch": "random", "cards": [
        {"questPoints": 0, "victory": None, "sailing": False,
         "faces": [{"side": "A", "name": "A Chosen Path", "text": None},
                   {"side": "B", "name": "Don't Leave the Path!", "text": "Cannot advance until..."}]},
        {"questPoints": 4, "victory": None, "sailing": True,
         "faces": [{"side": "A", "name": "A Chosen Path", "text": None},
                   {"side": "B", "name": "Beorn's Path", "text": None}]}]},
    {"stage": 3, "cards": [{"questPoints": 3, "victory": None, "sailing": False,
        "faces": [{"side": "A", "name": "End", "text": None},
                  {"side": "B", "name": "End", "text": None}]}]},
]

def _catalog_game():
    g = gamestate.GameState(2, 25)
    g.preload_scenario({"slug": "p", "name": "P", "pack": "Core Set", "cycle": "Core Set",
                        "source": "official", "kind": "quest", "nightmare": False, "mode": "Standard"},
                       STAGES)
    g.flip_to_b()          # round 1 begins on 1B, 2 quest points
    return g

def test_needs_resolution_false_initially():
    g = _catalog_game()
    assert g.needs_resolution() is False

def test_needs_resolution_true_on_location_overflow():
    g = _catalog_game()
    g.active_location = {"points": 3, "progress": 3}
    assert g.needs_resolution() is True

def test_needs_resolution_true_on_quest_overflow():
    g = _catalog_game()
    g.quest["progress"] = 2
    assert g.needs_resolution() is True

def test_needs_resolution_true_on_side_quest_overflow():
    g = _catalog_game()
    g.side_quests.append({"points": 3, "progress": 3})
    assert g.needs_resolution() is True

def test_resolve_location_overflow_noop_when_under_target():
    g = _catalog_game()
    g.active_location = {"points": 3, "progress": 2}
    assert g.resolve_location_overflow() == 0
    assert g.active_location is not None

def test_resolve_location_overflow_explores_and_credits_excess():
    g = _catalog_game()
    g.active_location = {"points": 2, "progress": 3}
    excess = g.resolve_location_overflow()
    assert excess == 1
    assert g.active_location is None
    assert g.quest["progress"] == 1     # was 0, +1 excess

def test_resolve_location_overflow_exact_match_no_excess():
    g = _catalog_game()
    g.active_location = {"points": 2, "progress": 2}
    assert g.resolve_location_overflow() == 0
    assert g.active_location is None
    assert g.quest["progress"] == 0

def test_clear_and_advance_moves_to_next_stage_side_a_progress_discarded():
    g = _catalog_game()
    g.quest["progress"] = 5             # 3 over the 2 needed
    ok = g.clear_and_advance(card_idx=1)   # choose "Beorn's Path" branch
    assert ok is True
    assert g.stage_idx == 1 and g.card_idx == 1
    assert g.quest["side"] == "A" and g.quest["points"] == 0
    assert g.quest["progress"] == 0     # excess NOT carried (rulebook p.22)
    assert g.sailing is True            # picked card's sailing flag

def test_clear_and_advance_false_at_last_stage():
    g = _catalog_game()
    g.stage_idx = 2                      # already on the final stage (index 2)
    g.card_idx = 0
    before = g.to_dict()
    assert g.clear_and_advance() is False
    assert g.to_dict() == before         # no mutation

def test_place_progress_catalog_game_defers_to_resolution_flag():
    g = _catalog_game()
    completed = g.place_progress({"quest": 2, "location": 0, "side_quests": []})
    assert g.pending_resolution == "auto"
    assert g.quest["side"] == "B" and g.quest["stage_n"] == 1   # unchanged - deferred
    assert "Quest 1B cleared" in completed[0]

def test_place_progress_custom_game_unchanged_legacy_behavior():
    g = gamestate.GameState(2, 25)       # no scenario/stages: custom game
    g.quest["points"] = 4
    completed = g.place_progress({"quest": 4, "location": 0, "side_quests": []})
    assert g.pending_resolution is False
    assert g.pending_stage == {"cleared": "1A", "excess": 0}
    assert g.quest["side"] == "B" and g.quest["stage_n"] == 1    # legacy toggle already ran

def test_pending_resolution_round_trips():
    g = _catalog_game()
    g.pending_resolution = "forced"
    g2 = gamestate.GameState.from_dict(g.to_dict())
    assert g2.pending_resolution == "forced"

def test_pending_resolution_defaults_false_when_absent():
    g = gamestate.GameState.from_dict(gamestate.GameState(1, 25).to_dict())
    assert g.pending_resolution is False
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_gamestate_resolution.py -q` → `AttributeError: 'GameState' object has no attribute 'needs_resolution'` (and friends).

- [ ] **Step 3: Implement in `gamestate.py`.** Constructor: add `self.pending_resolution = False` next to `self.pending_stage = None`. New methods, placed near `place_progress`:

```python
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
```

Modify `place_progress`'s quest block (the `n = alloc.get("quest", 0)` block):

```python
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
```

Serialization: add `"pending_resolution": self.pending_resolution` to `to_dict`; `g.pending_resolution = d.get("pending_resolution", False)` to `from_dict`.

- [ ] **Step 4: Run tests → PASS.** `python3 -m pytest tests/test_gamestate_resolution.py -q`.

- [ ] **Step 5: Regression check.** `python3 -m pytest tests/test_gamestate.py tests/test_gamestate_scenario.py -q` — confirm no existing test (especially any `place_progress`/`_advance_quest_stage` custom-game test) broke.

- [ ] **Step 6: Mirror in `docs/js/gamestate.js`** — same fields/methods, `needsResolution`, `resolveLocationOverflow`, `clearAndAdvance(cardIdx = 0)`; dict keys stay snake_case (`pending_resolution`) in `toDict`/`fromDict` per existing convention. Mirror the `placeProgress` quest block exactly (check `this.stages.length` instead of truthiness of a Python list).

- [ ] **Step 7: Verify web parity** —
```
node --input-type=module -e "
import('./docs/js/gamestate.js').then(m => {
  const g = new m.GameState(2, 25);
  g.preloadScenario({slug:'p'}, [
    {stage:1, cards:[{questPoints:2, sailing:false, faces:[]}]},
    {stage:2, cards:[{questPoints:3, sailing:true, faces:[]}]}]);
  g.flipToB();
  g.quest.progress = 5;
  console.log(g.placeProgress({quest:0, location:0, side_quests:[]}));
  console.log(g.pending_resolution, g.quest.side);   // -> 'auto' B  (deferred, not yet advanced)
  const excess = g.quest.progress - g.quest.points;
  console.log(g.clearAndAdvance(0), g.quest.side, g.quest.progress, g.sailing);  // -> true A 0 true
});
"
```

- [ ] **Step 8: Full suite + commit.** `python3 -m pytest tests/ -q`; `git add -A && git commit -m "feat(quest): resolution primitives - needs_resolution/resolve_location_overflow/clear_and_advance"`.

---

### Task 2: `ResolutionModal` — the guided step machine (both twins)

**Files:**
- Modify: `ui/modals.py` (add `ResolutionModal`), `docs/js/screens.js` (mirror)
- Modify: `tests/scenes.py`
- Test: `tests/test_resolution_modal.py` (new)

**Interfaces (Produces):**
- `ResolutionModal(game, force_advance=False)` / `ResolutionModal(game, forceAdvance = false)` — no other state is threaded in; everything is re-derived from `game`. Public attribute `self.step` (a `dict | None`, `"kind"` discriminated — see below), recomputed by `self._derive()` after every mutating action. `on_button`/`onButton` returns `"redraw"` after any in-place step change, `"close"` when the flow is fully resolved or the player dismisses it, `None` for inert/disabled controls.
- **Step kinds** (`self.step["kind"]`), in the priority order `_derive()` checks them:
  1. `"reveal"` — `{"kind": "reveal", "stage_n": int, "face_a": {"name": str, "text": str|None}, "next_points": int}`. Shown when `quest["side"] == "A"` (an advance already moved the card, the text hasn't been flipped past yet — this is checked *first*, ahead of a fresh location check, so an interrupted pass always finishes its flip before anything else). Action: `("do_flip",)` → `flip_to_b()`.
  2. `"location"` — `{"kind": "location", "progress": int, "points": int}`. Action: `("resolve_location",)` → `resolve_location_overflow()`.
  3. `"branch"` — `{"kind": "branch", "cards": [stage-card, ...], "mode": "random"|"choice"}`. Shown when the *next* stage has more than one card and no pick has been made yet this pass. Actions: `("pick_branch", i)` for each alternative; `("randomize_branch",)` only when `mode == "random"` (still lands on the same `"advance"` confirm step next — never skips confirmation).
  4. `"advance"` — `{"kind": "advance", "cleared": "2B", "card_idx": int, "next_stage": int, "underfilled": bool}`. `underfilled` is true when this step was reached via `force_advance` without the numeric target actually being met (shows a caution note). Action: `("do_advance",)` → `clear_and_advance(card_idx)`.
  5. `"victory"` — `{"kind": "victory", "cleared": "3B"}`. Shown when there is no next stage. Action: `("declare_victory",)` → `set_game_over("victory")`, returns `"close"`. A `("continue_without_victory",)` escape hatch is also offered (closes without ending the game, for scenarios whose real ending isn't just running off the end of the catalogued stages).
  6. `"side_quest"` — `{"kind": "side_quest", "idx": int, "name": str, "progress": int, "points": int}`. Actions: `("resolve_side_quest",)` (pop it, log, re-derive) and `("skip_side_quest",)` (leave it, remembered as skipped *for this modal instance only* via object-identity so it isn't re-offered later in the same pass).
  7. `None` — fully resolved; the modal shows a plain "All resolved" confirmation with a single `("close",)`.
- Every step's screen also carries the standard `modal_header`/`modalHeader` DONE button (`("close",)`), which exits the flow wherever it is left — resolving what's been resolved so far and leaving the rest for next time (state is always self-consistent between steps, never half-applied).

**Layout** (each step re-clears and redraws the full 480×480; `modal_header(d, pal, game, "Resolve", buttons)` for all of them):
- `"reveal"`: mirrors the Quest Setup scroll-tip exactly (`ui/screen_play.py:_draw_quest_setup`, `pal.scroll`/`pal.border_gold` double-frame + ribbon "STAGE ADVANCE - resolve now"), stage label + name at y≈70-100, tip box below, CTA `"Flip to Side B  ->  %d qp" % next_points` at y≈404.
- `"location"`: centered "Location Explored" headline (y=64), `%d/%d` recap, CTA "Continue" (y=404).
- `"branch"`: headline "Choose a path" + `mode` subtitle ("First player chooses" / "Random"), one row per alternative (B-face name + first ~80 chars of its text, truncated via `truncate_text`), radio-style selection; "Randomize" secondary button only when `mode=="random"`; CTA disabled until a pick exists.
- `"advance"`: recap "Quest %s cleared" (+ "excess discarded" note when nonzero), branch choice recap if applicable, `underfilled` caution banner in `pal.red`/`pal.amber` when set, CTA "Reveal Stage %d" (y=404).
- `"victory"`: reuses `StageCompleteModal`'s victory framing (gold headline "That was the final stage") with two buttons: "Declare Victory" (`pal.btn_ok`) and "Not yet - keep playing" (`pal.btn_no`).
- `"side_quest"`: headline with the side quest's name + `%d/%d`, two buttons "Mark Complete" (`pal.btn_ok`) / "Leave as-is" (`pal.card`).
- `None`: "All resolved" + single centered DONE-style button.

- [ ] **Step 1: Write the failing test** (`tests/test_resolution_modal.py`):

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gamestate
from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.modals import ResolutionModal

STAGES = [
    {"stage": 1, "cards": [{"questPoints": 2, "victory": None, "sailing": False,
        "faces": [{"side": "A", "name": "S1", "text": None}, {"side": "B", "name": "S1", "text": None}]}]},
    {"stage": 2, "branch": "choice", "cards": [
        {"questPoints": 0, "victory": None, "sailing": False,
         "faces": [{"side": "A", "name": "S2", "text": None},
                   {"side": "B", "name": "Don't Leave the Path!", "text": "Cannot advance until X."}]},
        {"questPoints": 4, "victory": None, "sailing": False,
         "faces": [{"side": "A", "name": "S2", "text": None},
                   {"side": "B", "name": "Beorn's Path", "text": None}]}]},
    {"stage": 3, "cards": [{"questPoints": 3, "victory": None, "sailing": False,
        "faces": [{"side": "A", "name": "S3", "text": "Final setup."}, {"side": "B", "name": "S3", "text": None}]}]},
]

def _game(**over):
    g = gamestate.GameState(2, 25)
    g.preload_scenario({"slug": "p", "name": "P", "pack": "Core Set", "cycle": "Core Set",
                        "source": "official", "kind": "quest", "nightmare": False, "mode": "Standard"}, STAGES)
    g.flip_to_b()
    for k, v in over.items():
        setattr(g, k, v) if not isinstance(v, dict) else g.quest.update(v)
    return g

def _draw(m, g):
    hw = FakeHardware()
    m.draw(hw, g, Palette(hw.display))
    return hw

def test_no_overflow_step_is_none():
    g = _game()
    m = ResolutionModal(g)
    assert m.step is None

def test_location_overflow_step_first():
    g = _game()
    g.active_location = {"points": 2, "progress": 3}
    g.quest["progress"] = 2   # ALSO over - location must still come first
    m = ResolutionModal(g)
    assert m.step["kind"] == "location"

def test_resolving_location_feeds_quest_and_advances_to_branch_step():
    g = _game()
    g.active_location = {"points": 2, "progress": 3}   # 1 excess -> quest
    g.quest["progress"] = 1                             # +1 excess = 2 = clears stage 1
    m = ResolutionModal(g)
    _draw(m, g)
    loc_btn = next(b for b in m.buttons if b.id[0] == "resolve_location")
    assert m.on_button(loc_btn) == "redraw"
    assert g.active_location is None and g.quest["progress"] == 2
    assert m.step["kind"] == "branch"        # stage 2 has 2 cards

def test_branch_pick_then_advance_then_reveal_then_flip():
    g = _game()
    g.quest["progress"] = 2       # clears stage 1 outright
    m = ResolutionModal(g)
    _draw(m, g)
    assert m.step["kind"] == "branch"
    pick = next(b for b in m.buttons if b.id == ("pick_branch", 1))   # choose Beorn's Path
    assert m.on_button(pick) == "redraw"
    assert m.step["kind"] == "advance" and m.step["card_idx"] == 1
    _draw(m, g)
    adv = next(b for b in m.buttons if b.id[0] == "do_advance")
    assert m.on_button(adv) == "redraw"
    assert g.stage_idx == 1 and g.card_idx == 1 and g.quest["side"] == "A"
    assert m.step["kind"] == "reveal"
    _draw(m, g)
    flip = next(b for b in m.buttons if b.id[0] == "do_flip")
    assert m.on_button(flip) == "redraw"
    assert g.quest["side"] == "B" and g.quest["points"] == 4
    assert m.step is None        # 4qp target, 0 progress: nothing left to resolve

def test_conditional_stage_halts_without_looping():
    g = _game()
    g.quest["progress"] = 2
    m = ResolutionModal(g)
    pick0 = {"kind": "branch"}
    _draw(m, g)
    pick = next(b for b in m.buttons if b.id == ("pick_branch", 0))   # "Don't Leave the Path!", 0 qp
    m.on_button(pick)
    _draw(m, g)
    adv = next(b for b in m.buttons if b.id[0] == "do_advance")
    m.on_button(adv)
    _draw(m, g)
    flip = next(b for b in m.buttons if b.id[0] == "do_flip")
    m.on_button(flip)
    assert g.quest["points"] == 0 and g.quest["side"] == "B"
    assert m.step is None                 # halts - no auto-loop on a 0-point stage

def test_force_advance_shows_underfilled_caution():
    g = _game()
    g.quest["progress"] = 0        # nowhere near the 2 needed
    m = ResolutionModal(g, force_advance=True)
    assert m.step["kind"] in ("branch", "advance")
    if m.step["kind"] == "branch":
        _draw(m, g)
        m.on_button(next(b for b in m.buttons if b.id == ("pick_branch", 1)))
    assert m.step["kind"] == "advance" and m.step["underfilled"] is True

def test_victory_step_at_last_stage():
    g = _game(stage_idx=2, card_idx=0)
    g.quest.update({"points": 3, "progress": 3, "side": "B", "stage_n": 3})
    m = ResolutionModal(g)
    assert m.step["kind"] == "victory"
    _draw(m, g)
    b = next(x for x in m.buttons if x.id[0] == "declare_victory")
    assert m.on_button(b) == "close"
    assert g.game_over["result"] == "victory"

def test_side_quest_step_resolve_and_skip():
    g = _game()
    g.side_quests = [{"points": 2, "progress": 2, "name": "Gather Information"},
                      {"points": 3, "progress": 3, "name": "Scout Ahead"}]
    m = ResolutionModal(g)
    assert m.step["kind"] == "side_quest" and m.step["idx"] == 0
    _draw(m, g)
    skip = next(b for b in m.buttons if b.id[0] == "skip_side_quest")
    m.on_button(skip)
    assert m.step["kind"] == "side_quest" and m.step["idx"] == 1   # moved past the skipped one
    _draw(m, g)
    done = next(b for b in m.buttons if b.id[0] == "resolve_side_quest")
    m.on_button(done)
    assert len(g.side_quests) == 1                                 # only the resolved one popped
    assert m.step is None

def test_interrupted_reveal_resumes_first():
    g = _game()
    g.stage_idx = 1
    g.quest.update({"side": "A", "points": 0, "progress": 0, "stage_n": 2})
    g.active_location = {"points": 2, "progress": 2}   # a fresh overflow too
    m = ResolutionModal(g)
    assert m.step["kind"] == "reveal"     # finishes the interrupted flip before the location
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_resolution_modal.py -q` → `ImportError: cannot import name 'ResolutionModal'`.

- [ ] **Step 3: Implement `ResolutionModal` in `ui/modals.py`**, next to `StageCompleteModal`:

```python
import random


class ResolutionModal:
    """Guided post-edit/post-success resolution: location -> quest advance
    (branch/reveal/flip) -> side quests, one explicit step at a time,
    re-deriving what's next from live game state after every action. Opened
    only for catalog games (game.stages non-empty) - custom games keep the
    legacy StageCompleteModal. See docs/superpowers/plans/
    2026-07-24-quest-picker-bresolve.md for the full rationale, including
    why at most one stage advance can ever happen per pass."""

    def __init__(self, game, force_advance=False):
        self.game = game
        self.buttons = []
        self.branch_pick = None
        self.force_advance = force_advance
        self._skipped_side_quests = []   # dict refs (identity, not value) - see _derive
        self.step = self._derive()

    def _quest_step(self):
        g = self.game
        if g.quest["side"] == "A":
            card = g.stages[g.stage_idx]["cards"][g.card_idx]
            face_a = next((f for f in card["faces"] if f["side"] == "A"), {})
            return {"kind": "reveal", "stage_n": g.quest["stage_n"], "face_a": face_a,
                    "next_points": card["questPoints"]}
        nxt_idx = g.stage_idx + 1
        if nxt_idx >= len(g.stages):
            return {"kind": "victory", "cleared": g.quest_label()}
        nxt = g.stages[nxt_idx]
        if len(nxt["cards"]) > 1 and self.branch_pick is None:
            return {"kind": "branch", "cards": nxt["cards"], "mode": nxt.get("branch", "choice")}
        card_idx = self.branch_pick or 0
        return {"kind": "advance", "cleared": g.quest_label(), "card_idx": card_idx,
                "next_stage": nxt["stage"],
                "underfilled": g.quest["points"] > 0 and g.quest["progress"] < g.quest["points"]}

    def _derive(self):
        g = self.game
        if g.stages and g.quest["side"] == "A":
            return self._quest_step()      # finish an interrupted reveal/flip first
        loc = g.active_location
        if loc and loc["points"] > 0 and loc["progress"] >= loc["points"]:
            return {"kind": "location", "progress": loc["progress"], "points": loc["points"]}
        if (g.quest["points"] > 0 and g.quest["progress"] >= g.quest["points"]) or self.force_advance:
            return self._quest_step()
        for i, s in enumerate(g.side_quests):
            if any(s is skipped for skipped in self._skipped_side_quests):
                continue
            if s["points"] > 0 and s["progress"] >= s["points"]:
                return {"kind": "side_quest", "idx": i,
                        "name": s.get("name") or "Side Quest %d" % (i + 1),
                        "progress": s["progress"], "points": s["points"]}
        return None

    def draw(self, hw, game, pal):
        from ui.header import modal_header
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        modal_header(d, pal, game, "Resolve", self.buttons)
        st = self.step
        if st is None:
            self._draw_done(d, pal)
        elif st["kind"] == "reveal":
            self._draw_reveal(d, pal, st)
        elif st["kind"] == "location":
            self._draw_location(d, pal, st)
        elif st["kind"] == "branch":
            self._draw_branch(d, pal, st)
        elif st["kind"] == "advance":
            self._draw_advance(d, pal, st)
        elif st["kind"] == "victory":
            self._draw_victory(d, pal, st)
        elif st["kind"] == "side_quest":
            self._draw_side_quest(d, pal, st)

    # -- per-step draw helpers (layout bands per the plan's Layout section) --
    def _cta(self, d, pal, label, id_, y=404, h=56, ok=True):
        b = Button(id_, 24, y, 432, h)
        bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn_ok if ok else pal.btn_no, t=3)
        text_center(d, pal, label, 240, y + h // 2 - 10, 2, pal.ok_fg if ok else pal.no_fg)
        self.buttons.append(b)

    def _draw_done(self, d, pal):
        text_center(d, pal, "All resolved", 240, 200, 3, pal.gold)
        self._cta(d, pal, "Continue", ("close",))

    def _draw_reveal(self, d, pal, st):
        text_center(d, pal, "STAGE %d REVEALED" % st["stage_n"], 240, 64, 2, pal.amber)
        name = truncate_text(st["face_a"].get("name") or "", 3, 432, d.measure_text)
        text_center(d, pal, name, 240, 92, 3, pal.gold)
        tip_x, tip_w, tip_y = 24, 432, 130
        ribbon_h, pad_top, line_h, pad_bottom, max_lines = 22, 10, 24, 10, 5
        raw = st["face_a"].get("text")
        body = raw if raw else "No setup instructions for this stage."
        lines = wrap_text(body, 2, tip_w - 28, measure=d.measure_text)[:max_lines]
        tip_h = ribbon_h + pad_top + len(lines) * line_h + pad_bottom
        d.set_pen(pal.border_gold); d.rectangle(tip_x, tip_y, tip_w, tip_h)
        d.set_pen(pal.bg); d.rectangle(tip_x + 2, tip_y + 2, tip_w - 4, tip_h - 4)
        d.set_pen(pal.border_gold); d.rectangle(tip_x + 4, tip_y + 4, tip_w - 8, tip_h - 8)
        d.set_pen(pal.scroll); d.rectangle(tip_x + 6, tip_y + 6, tip_w - 12, tip_h - 12)
        d.set_pen(pal.border_gold); d.rectangle(tip_x, tip_y, tip_w, ribbon_h)
        text_left(d, pal, "STAGE ADVANCE - resolve now", tip_x + 10, tip_y + 6, 1, pal.bg, shadow=False)
        ly = tip_y + ribbon_h + pad_top
        for ln in lines:
            text_left(d, pal, ln, tip_x + 14, ly, 2, pal.tan)
            ly += line_h
        self._cta(d, pal, "Flip to Side B  ->  %d qp" % st["next_points"], ("do_flip",))

    def _draw_location(self, d, pal, st):
        text_center(d, pal, "Location Explored", 240, 90, 3, pal.gold)
        text_center(d, pal, "%d/%d progress" % (st["progress"], st["points"]), 240, 130, 2, pal.tan)
        excess = st["progress"] - st["points"]
        if excess:
            text_center(d, pal, "%d excess -> quest card" % excess, 240, 160, 2, pal.amber)
        self._cta(d, pal, "Continue", ("resolve_location",))

    def _draw_branch(self, d, pal, st):
        text_center(d, pal, "Choose a path", 240, 56, 3, pal.gold)
        text_center(d, pal, "First player chooses" if st["mode"] != "random" else "Random",
                   240, 86, 1, pal.dim)
        y = 116
        for i, card in enumerate(st["cards"]):
            b_face = next((f for f in card["faces"] if f["side"] == "B"), {})
            b = Button(("pick_branch", i), 24, y, 432, 64)
            sel = self.branch_pick == i
            bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn_ok if sel else pal.btn, t=3)
            text_left(d, pal, b_face.get("name") or "?", b.x + 14, y + 10, 2,
                      pal.ok_fg if sel else pal.tan)
            preview = truncate_text(b_face.get("text") or "", 1, 400, d.measure_text)
            text_left(d, pal, preview, b.x + 14, y + 38, 1, pal.dim)
            self.buttons.append(b)
            y += 74
        if st["mode"] == "random":
            r = Button(("randomize_branch",), 24, y, 432, 40)
            bevel(d, pal, r.x, r.y, r.w, r.h, pal.card, t=2)
            text_center(d, pal, "Randomize for me", 240, y + 10, 2, pal.tan)
            self.buttons.append(r)

    def _draw_advance(self, d, pal, st):
        text_center(d, pal, "Quest %s cleared" % st["cleared"], 240, 90, 3, pal.gold)
        if st["underfilled"]:
            text_center(d, pal, "Progress hasn't reached target - confirm", 240, 130, 1, pal.red)
        self._cta(d, pal, "Reveal Stage %d" % st["next_stage"], ("do_advance",))

    def _draw_victory(self, d, pal, st):
        text_center(d, pal, "Quest %s cleared" % st["cleared"], 240, 70, 2, pal.tan)
        text_center(d, pal, "That was the final stage!", 240, 110, 3, pal.gold)
        self._cta(d, pal, "Declare Victory", ("declare_victory",), y=340)
        self._cta(d, pal, "Not yet - keep playing", ("continue_without_victory",), y=404, ok=False)

    def _draw_side_quest(self, d, pal, st):
        text_center(d, pal, st["name"], 240, 90, 3, pal.gold)
        text_center(d, pal, "%d/%d" % (st["progress"], st["points"]), 240, 130, 2, pal.tan)
        self._cta(d, pal, "Mark Complete", ("resolve_side_quest",), y=340)
        self._cta(d, pal, "Leave as-is", ("skip_side_quest",), y=404, ok=False)

    def on_button(self, btn):
        g = self.game
        k = btn.id[0]
        if k == "do_flip":
            g.flip_to_b(); self.step = self._derive(); return "redraw"
        if k == "resolve_location":
            g.resolve_location_overflow(); self.step = self._derive(); return "redraw"
        if k == "pick_branch":
            self.branch_pick = btn.id[1]; self.step = self._derive(); return "redraw"
        if k == "randomize_branch":
            self.branch_pick = random.randrange(len(self.step["cards"]))
            self.step = self._derive(); return "redraw"
        if k == "do_advance":
            g.clear_and_advance(card_idx=self.step["card_idx"])
            self.force_advance = False
            self.branch_pick = None
            self.step = self._derive()
            return "redraw"
        if k == "declare_victory":
            g.set_game_over("victory")
            return "close"
        if k == "continue_without_victory":
            self.step = self._derive(); return "redraw"
        if k == "resolve_side_quest":
            i = self.step["idx"]
            g.log_event("Side quest %d completed (resolution)" % (i + 1))
            g.side_quests.pop(i)
            self.step = self._derive()
            return "redraw"
        if k == "skip_side_quest":
            self._skipped_side_quests.append(g.side_quests[self.step["idx"]])
            self.step = self._derive()
            return "redraw"
        if k == "close":
            return "close"
        return None
```

(Add `from ui.widgets import ...` names already imported at the top of `ui/modals.py` cover `Button`/`bevel`/`text_center`/`text_left`/`wrap_text`/`truncate_text` — no new imports besides the stdlib `random`.)

- [ ] **Step 4: Run tests → PASS.** `python3 -m pytest tests/test_resolution_modal.py -q`.

- [ ] **Step 5: Mirror in `docs/js/screens.js`** (`export class ResolutionModal`), same step-kind dict shapes (camelCase local vars, but step dict keys can stay as written — this is transient UI state, not persisted, so no snake_case requirement applies). Reuse `wrapText`/`truncateText`/`bevel`/`textCenter`/`textLeft`/`circBtn` per existing file conventions; `Math.random()` in place of `random.randrange`.

- [ ] **Step 6: Add scenes** to `tests/scenes.py`: `resolution_reveal`, `resolution_location`, `resolution_branch`, `resolution_advance`, `resolution_advance_underfilled`, `resolution_victory`, `resolution_side_quest`, `resolution_done` — one per step kind, built the same way `_stage_complete_modal()` is (construct a `GameState` via `preload_scenario`, force it into the right raw state, construct `ResolutionModal`, `.draw()`).

- [ ] **Step 7: Render and inspect** — `python3 tools/preview.py resolution_branch /tmp/rb.png` (and the other 7 scenes). Confirm: branch row text doesn't collide with the radio bevel; the reveal step's scroll-tip matches Quest Setup's look; the underfilled caution is legible in `pal.red`. Fix anything cramped. `python3 -m pytest tests/test_layout.py -q` → PASS (touch targets ≥24px, no collisions).

- [ ] **Step 8: Full suite → green; commit.** `python3 -m pytest tests/ -q`; `git add -A && git commit -m "feat(quest): ResolutionModal - guided location/quest/side-quest resolution"`.

---

### Task 3: Entry points — `QuestingProgressModal`, the quest-success path, and the main-loop dispatch

**Files:**
- Modify: `ui/modals.py` (`QuestingProgressModal._items`/`_row`/`_icon_btn`/`on_button`), `docs/js/screens.js` (mirror)
- Modify: `ui/screen_play.py` (`apply_alloc`), `docs/js/screen_play.js` (mirror)
- Modify: `main.py`, `docs/js/main.js` (new top-level dispatch block)
- Test: extend `tests/test_modals.py` (or wherever `QuestingProgressModal` is currently tested) + one new integration-style assertion in `tests/test_gamestate_resolution.py`

**Interfaces:**
- `QuestingProgressModal`'s quest row gains a third icon kind, `"adv"` (a right-pointing chevron in `pal.gold`, reusing `_icon_btn`'s disc+arc_runs base), shown only when `bool(g.stages)` (catalog game) at `x=400` (the same slot `"done"` uses on removable rows — the quest row is never removable, so there's no collision). Button id `("qAdv",)`. Tapping it sets `game.pending_resolution = "forced"`, logs pending edits, and closes — same shape as the existing `"quest_card"`/`"add"` handlers.
- `QuestingProgressModal.on_button`'s `"close"` case now also sets `game.pending_resolution = "auto"` when `game.needs_resolution()` is true (checked **after** flushing the raw field edits it already logs).
- `ScreenPlay.apply_alloc`'s existing `if game.pending_stage: return ("modal", StageCompleteModal(game))` check gains a sibling: `elif game.pending_resolution: ... return ("modal", ResolutionModal(game, force_advance=...))`.
- `main.py`/`main.js`'s main loop gains a new block, directly modeled on the existing `pending_quest_card` block (`main.py:237-244`): when `modal is None and active == "play" and game.pending_resolution`, open `ResolutionModal(game, force_advance=(game.pending_resolution == "forced"))` for catalog games, or seed `game.pending_stage` + open the legacy `StageCompleteModal` for custom games — mirroring `place_progress`'s own custom-game branch from Task 1.

- [ ] **Step 1: Write the failing tests.** Add to the existing `QuestingProgressModal` test module (find it via `grep -rn "class TestQuestingProgressModal\|def test.*questing_progress" tests/` — likely `tests/test_modals.py`; if the modal is currently only covered via scenes, add a new `tests/test_questing_progress_resolution.py`):

```python
import gamestate
from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.modals import QuestingProgressModal

STAGES = [{"stage": 1, "cards": [{"questPoints": 2, "victory": None, "sailing": False,
    "faces": [{"side": "A", "name": "S1", "text": None}, {"side": "B", "name": "S1", "text": None}]}]},
    {"stage": 2, "cards": [{"questPoints": 3, "victory": None, "sailing": False,
    "faces": [{"side": "A", "name": "S2", "text": None}, {"side": "B", "name": "S2", "text": None}]}]}]

def _catalog_game():
    g = gamestate.GameState(2, 25)
    g.preload_scenario({"slug": "p", "name": "P", "pack": "Core Set", "cycle": "Core Set",
                        "source": "official", "kind": "quest", "nightmare": False, "mode": "Standard"}, STAGES)
    g.flip_to_b()
    return g

def _draw(m, g):
    hw = FakeHardware()
    m.draw(hw, g, Palette(hw.display))
    return hw

def test_manual_edit_over_target_then_close_sets_pending_resolution():
    g = _catalog_game()
    m = QuestingProgressModal(g)
    _draw(m, g)
    plus = next(b for b in m.buttons if b.id == ("qP+", None))
    for _ in range(3):
        m.on_button(plus)     # 0 -> 3, target is 2
    close = next(b for b in m.buttons if b.id[0] == "close")
    assert m.on_button(close) == "close"
    assert g.pending_resolution == "auto"

def test_no_overflow_close_does_not_set_pending_resolution():
    g = _catalog_game()
    m = QuestingProgressModal(g)
    _draw(m, g)
    close = next(b for b in m.buttons if b.id[0] == "close")
    m.on_button(close)
    assert g.pending_resolution is False

def test_advance_icon_shown_only_for_catalog_games():
    g = _catalog_game()
    m = QuestingProgressModal(g)
    hw = _draw(m, g)
    assert any(b.id == ("qAdv",) for b in m.buttons)
    g2 = gamestate.GameState(2, 25)          # custom game: no stages
    m2 = QuestingProgressModal(g2)
    _draw(m2, g2)
    assert not any(b.id == ("qAdv",) for b in m2.buttons)

def test_advance_icon_sets_forced_resolution():
    g = _catalog_game()
    m = QuestingProgressModal(g)
    _draw(m, g)
    adv = next(b for b in m.buttons if b.id == ("qAdv",))
    assert m.on_button(adv) == "close"
    assert g.pending_resolution == "forced"
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_questing_progress_resolution.py -q` (new file) → fails (no `"qAdv"` button, `pending_resolution` never set).

- [ ] **Step 3: Implement in `ui/modals.py`.** `_items()`: add `"advanceable": bool(g.stages)` to the quest item's dict. `_icon_btn`: add an `"adv"` kind:
```python
    def _icon_btn(self, d, pal, cx, cy, r, kind, id):
        if kind == "x":
            circ_btn(d, pal, cx, cy, r, "X", pal.red)
        elif kind == "adv":
            disc(d, cx, cy, r, pal.btn)
            arc_runs(d, cx, cy, r, r - 2, 0, 360, pal.bevel_l)
            d.set_pen(pal.gold)
            d.triangle(cx - 3, cy - 5, cx - 3, cy + 5, cx + 5, cy)
        else:
            ...  # existing "done" branch unchanged
```
`_row()`: after the existing `if it.get("removable"):` block, add:
```python
        if it.get("advanceable"):
            self._icon_btn(d, pal, 400, cy, 11, "adv", ("qAdv",))
```
`on_button()`: add, alongside the existing `k == "quest_card"` handler:
```python
        if k == "qAdv":
            g.pending_resolution = "forced"
            self._log_changes()
            return "close"
```
and change the `k == "close"` handler:
```python
        if k == "close":
            self._log_changes()
            if g.stages and g.needs_resolution():
                g.pending_resolution = "auto"
            return "close"
```

- [ ] **Step 4: Run tests → PASS.**

- [ ] **Step 5: Mirror in `docs/js/screens.js`** (`_iconBtn`, `_items`/`_row`, `onButton`'s `"qAdv"`/`"close"` cases) — identical logic, camelCase.

- [ ] **Step 6: Wire `ScreenPlay.apply_alloc`** (`ui/screen_play.py`, right after the existing `if game.pending_stage:` check):
```python
            if game.pending_stage:
                from ui.modals import StageCompleteModal
                return ("modal", StageCompleteModal(game))
            if game.pending_resolution:
                forced = game.pending_resolution == "forced"
                game.pending_resolution = False
                from ui.modals import ResolutionModal
                return ("modal", ResolutionModal(game, force_advance=forced))
            return True
```
Mirror in `docs/js/screen_play.js`'s `apply_alloc` handler (same ordering).

- [ ] **Step 7: Wire the main-loop dispatch** in `main.py`, modeled directly on the `pending_quest_card` block (`main.py:237-244`) — add right after it:
```python
        # Manual progress-edit overflow (QuestingProgressModal close, or the
        # quest row's "Advance" icon): same pending-flag pattern as
        # pending_quest_card above - the modal that detected it had to
        # close first (router holds one modal at a time).
        if modal is None and active == "play" and game.pending_resolution:
            forced = game.pending_resolution == "forced"
            game.pending_resolution = False
            if game.stages:
                from ui.modals import ResolutionModal
                modal = ResolutionModal(game, force_advance=forced)
            else:
                excess = max(0, game.quest["progress"] - game.quest["points"]) \
                    if game.quest["points"] > 0 else 0
                game.pending_stage = {"cleared": game.quest_label(), "excess": excess}
                from ui.modals import StageCompleteModal
                modal = StageCompleteModal(game)
            dirty = True
            continue
```
Mirror in `docs/js/main.js` (no `Promise`/fetch needed here, unlike `pending_quest_card` — this path never reads the catalog, since `game.stages` is already loaded on the model).

- [ ] **Step 8: Full suite → green; commit.** `python3 -m pytest tests/ -q`; `git add -A && git commit -m "feat(quest): wire ResolutionModal into QuestingProgressModal, quest-success, and the main loop"`.

---

### Task 4: Integration — browser walkthrough + full gate

**Files:** none new (verification + any fixes surfaced).

- [ ] **Step 1: Regenerate catalog locally** — `python3 tools/build_card_data.py` (so `docs/data/scenarios/*.json` exists for the browser walkthrough; this directory is gitignored and was absent in the working tree at plan-writing time).
- [ ] **Step 2: Walkthrough A — manual edit overflow (the literal ask).** New Game → Official → Core Set → Passage Through Mirkwood → play through Quest Setup into round 1. Open Progress detail, use the quest row's Current `+` to push progress at/over the stage's printed points, tap DONE. Confirm `ResolutionModal` opens showing the `"advance"` step (or `"branch"` first, since Passage's stage 3 branches — pick either alternative to confirm the branch UI), then `"reveal"` with the real stage text, then flip. Confirm round/log reflect the new stage and the modal returns to Progress detail (or Play) cleanly.
- [ ] **Step 3: Walkthrough B — location overflow feeding the quest.** Add an active location, push its Current progress at/over its points via the same editor while the quest is close to its own target such that the credited excess also clears the quest. Confirm the `"location"` step fires *before* the `"advance"` step in the same pass.
- [ ] **Step 4: Walkthrough C — conditional stage.** Manually navigate (via a fresh custom `preload_scenario` in the browser console, or by advancing through a real scenario known to have a 0-point stage) to a stage with 0 printed quest points. Confirm the quest row's new chevron ("Advance") icon appears, tapping it opens `ResolutionModal` directly (`force_advance`), and the flow halts cleanly on the conditional stage afterward (no re-trigger loop).
- [ ] **Step 5: Walkthrough D — normal success path still routes correctly.** Play a full round to a successful quest resolution (commit willpower > staging) with a catalog scenario loaded; confirm `AllocationModal` → `apply_alloc` now opens `ResolutionModal` (not the old blind `StageCompleteModal`) when the quest clears.
- [ ] **Step 6: Walkthrough E — custom-game fallback unchanged.** Start a Custom quest (no catalog). Manually push quest progress over a manually-typed target in Progress detail, tap DONE. Confirm the legacy `StageCompleteModal` (steppers) opens — this path must still work exactly as before.
- [ ] **Step 7: Full suite + every scene.** `python3 -m pytest tests/ -q` green; `python3 tools/preview.py --list` shows all 8 new `resolution_*` scenes; spot-render each once more after any fixes from the walkthroughs.
- [ ] **Step 8: Report** the five walkthroughs with screenshots/console-error checks. Commit any fixes found along the way.

---

## Self-Review

**Spec coverage:** location-first / explore+discard / overflow-to-quest / clear+advance+flip → Task 1 (`resolve_location_overflow`, `clear_and_advance`) + Task 2 (`ResolutionModal`'s `"location"`→`"branch"`→`"advance"`→`"reveal"` chain). The A→B flip recurring at every advance (not just setup) → `clear_and_advance` + `"reveal"` step reuse the exact same `flip_to_b()`/scroll-tip pattern B-core used for the pre-round-1 flip. Conditional advancement (0-point stages) → handled by construction: the numeric gate (`points > 0`) simply never fires for them, and the quest row's new "Advance" icon (Task 3) is the only way in, landing on the `"advance"` step with `underfilled` set when appropriate. Branch stages → Task 2's `"branch"` step, default "choose" (radio picker), with a `"random"` convenience that still requires confirmation. The manual-edit-then-submit trigger from the brief → Task 3's `QuestingProgressModal` close-hook is the primary entry point; the quest-success path (`place_progress`/`apply_alloc`) is upgraded too so both routes into stage-advancement are now catalog-aware and consistent with each other.

**Corrections made during verification (flagged, not silently assumed):** excess quest progress does **not** carry to the next stage (rulebook p.22) — this simplified the architecture from "must guard against cascades" to "cannot cascade, provably." The catalog's `"victory"` field is a scoring keyword (p.24), not an alternate win trigger — left untouched by this plan. Side-quest excess has no citable rulebook text (Side Quest isn't a Core Set mechanic) — handled as informational-only, not a discard/carry claim.

**Placeholder scan:** Task 1 and Task 2 both carry complete, runnable test files and complete Python implementations (not sketches); the JS mirror steps name the exact methods/casing to produce without re-deriving logic already fully specified in Python. Task 3's exact diff locations are named (`ui/screen_play.py`'s `apply_alloc`, `main.py`'s `pending_quest_card` block as the model to copy).

**Type consistency:** `ResolutionModal(game, force_advance=False)` and its `step` dict shapes are defined once in Task 2 and used identically in Task 2's own tests, Task 3's wiring (`apply_alloc`, main-loop dispatch), and Task 4's walkthroughs. `pending_resolution`'s tri-state (`False|"auto"|"forced"`) is threaded consistently from Task 1 (field + serialization) through Task 3 (both setters, both consumers).

**Cross-twin:** every task is web-first-then-firmware per Global Constraints; Task 2 explicitly notes the JS mirror can use non-snake_case step-dict keys (transient UI state, unlike persisted model fields) while `pending_resolution` itself (persisted) stays snake_case in both `toDict`s.
