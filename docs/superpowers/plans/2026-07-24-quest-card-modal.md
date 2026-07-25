# Quest Card Modal (M4-B modal) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A read-only quest-card modal showing everything the catalog knows about a stage — both faces' names and text, quest points, victory points, sailing, branch alternatives — opening on the *current* stage and paging back/forth through every stage of the loaded scenario. Reached from the Quest Setup screen's card button and from the Progress-detail quest row title. Each stage view carries a **disabled "Tips" button** (a later sub-project scrapes strategy tips into it).

**Architecture:** One new modal class per twin, constructed from the `game.stages` snapshot already on the model (no catalog re-read, so it works offline and after a reload). It is purely presentational — no mutation of game state. Paging is internal modal state, seeded from `game.stage_idx`/`card_idx`.

**Tech Stack:** ES modules (web, Canvas) + MicroPython (firmware); pytest + the scene layout linter.

**Context:** This is the **B-modal** piece of the M4-B family (see `docs/superpowers/specs/2026-07-24-quest-picker-bcore-design.md` → "M4-B family"). B-core is complete: the model carries `scenario`, `stages`, `stage_idx`, `card_idx`, and `quest.side`; the Quest Setup view already renders a **stubbed** "View quest card" button (id `["open_card_modal"]`) whose handler currently returns null — this plan makes it open the modal.

## Global Constraints

- **Two twins in lockstep** (Iron rule #1): web `docs/js/` first, then the firmware mirror. Identical layout, ids, and behavior.
- **`python3 -m pytest tests/` stays green** (Iron rule #3), including the layout linter. Add a scene per distinct modal state.
- **Touch targets ≥ 24px** each dimension; everything within 480×480; no text collisions (linter-enforced).
- **Read-only:** the modal must never mutate `game` (no progress/points/side changes). Its only exit is DONE.
- **Data source is `game.stages`** — the snapshot copied at preload. Shape per entry:
  `{"stage": int, "branch": "random"|"choice" (optional), "cards": [{"questPoints": int, "victory": int|None, "sailing": bool, "faces": [{"side": "A"|"B", "name": str, "text": str|None}, ...]}, ...]}`
- **Custom games have no stages** (`game.scenario is None`, `game.stages == []`) — the entry points must not offer the modal, and the modal must render a graceful empty state if opened anyway.
- **Firmware divergences:** modals are uniformly `draw(self, hw, game, pal)` / `on_button(self, btn)`; `wrap_text`/`truncate_text`/`note_panel` take a trailing `measure=d.measure_text`; header helpers live in `ui/header.py` (`modal_header` draws the round id + centred title + a DONE button emitting `("close",)`).
- **Long text must wrap and clip cleanly** — quest text runs to several hundred characters; never let it overflow the panel or the screen.

## File structure

- `docs/js/screens.js` — web `QuestCardModal` (this file holds the other full-screen modals + `modalHeader`).
- `ui/modals.py` — firmware `QuestCardModal` mirror.
- `docs/js/screen_play.js` + `ui/screen_play.py` — open the modal from the Quest Setup card button and from the Progress-detail quest row.
- `docs/js/screens.js` / `ui/modals.py` (Progress detail) — make the quest row title a tap target that opens the modal.
- `tests/scenes.py` — scenes; `tests/test_modals.py` (or a new `tests/test_quest_card_modal.py`) — behavior tests.

---

### Task 1: The QuestCardModal (both twins)

**Files:**
- Modify: `docs/js/screens.js` (add `QuestCardModal`), `ui/modals.py` (mirror)
- Modify: `tests/scenes.py` (scenes)
- Test: `tests/test_quest_card_modal.py` (new)

**Interfaces:**
- Produces: `QuestCardModal(game)` / `QuestCardModal(game)` — reads `game.stages`, `game.stage_idx`, `game.card_idx`, `game.quest.side`. Internal state: `idx` (stage index, seeded from `game.stage_idx`), `card` (branch-card index, seeded from `game.card_idx`). `onButton`/`on_button` returns `"close"` for DONE, `"redraw"` for paging/branch-switching, `null`/`None` for the disabled Tips button.

**Layout** (one stage per view):
- `modal_header`/`modalHeader` with title `QUEST CARD` and its DONE button.
- Stage line: `STAGE <n><side-letters>` — e.g. `STAGE 2` plus a small "A / B" indicator; mark the stage the game is currently on (e.g. a gold "CURRENT" pill) so paging away is obvious.
- Card name (the A-face name; if the B-face name differs — it does on branch cards like "A Chosen Path" / "Beorn's Path" — show both, labelled).
- **Quest points** rendered with the existing token/value styling, plus `victory` and a sailing wheel glyph when set.
- **Side A block:** label "SIDE A - setup / story", wrapped text (or "no text" placeholder).
- **Side B block:** label "SIDE B - quest", wrapped text (or placeholder).
- If the stage has **multiple cards** (a branch): show `BRANCH - random` / `BRANCH - first player chooses`, and a control to switch which alternative is displayed (e.g. `< 1/2 >` or two small labelled buttons). Switching only changes what's displayed.
- **Tips button, disabled:** a bevel button labelled "Tips" drawn in the disabled palette (`pal.dim` fg on `pal.btn`) with a small "soon" hint; its handler returns null. It must still satisfy the ≥24px target rule.
- Pager: `< Prev` / `Next >` buttons + `stage i of n`, disabled/hidden at the ends.

- [ ] **Step 1: Write the failing test** — `tests/test_quest_card_modal.py`:

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gamestate
from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.modals import QuestCardModal

STAGES = [
    {"stage": 1, "cards": [{"questPoints": 8, "victory": None, "sailing": False,
        "faces": [{"side": "A", "name": "Flies and Spiders", "text": "Setup: Search the encounter deck..."},
                  {"side": "B", "name": "Flies and Spiders", "text": None}]}]},
    {"stage": 2, "cards": [{"questPoints": 2, "victory": None, "sailing": False,
        "faces": [{"side": "A", "name": "A Fork in the Road", "text": None},
                  {"side": "B", "name": "A Fork in the Road", "text": "Forced: ... at random."}]}]},
    {"stage": 3, "branch": "random", "cards": [
        {"questPoints": 0, "victory": None, "sailing": False,
         "faces": [{"side": "A", "name": "A Chosen Path", "text": None},
                   {"side": "B", "name": "Don't Leave the Path!", "text": "When Revealed: ..."}]},
        {"questPoints": 10, "victory": None, "sailing": False,
         "faces": [{"side": "A", "name": "A Chosen Path", "text": None},
                   {"side": "B", "name": "Beorn's Path", "text": "Players cannot defeat..."}]}]},
]

def _game(stage_idx=0):
    g = gamestate.GameState(2, 25)
    g.preload_scenario({"slug": "p", "name": "Passage", "pack": "Core Set", "cycle": "Core Set",
                        "source": "official", "kind": "quest", "nightmare": False, "mode": "Standard"}, STAGES)
    g.stage_idx = stage_idx
    return g

def _draw(m, g):
    hw = FakeHardware()
    m.draw(hw, g, Palette(hw.display))
    return hw

def test_opens_on_current_stage():
    g = _game(stage_idx=1)
    m = QuestCardModal(g)
    assert m.idx == 1

def test_paging_moves_and_clamps():
    g = _game(stage_idx=0)
    m = QuestCardModal(g)
    _draw(m, g)
    nxt = next(b for b in m.buttons if b.id[0] == "next")
    assert m.on_button(nxt) == "redraw" and m.idx == 1
    m.idx = len(STAGES) - 1
    _draw(m, g)
    assert not any(b.id[0] == "next" for b in m.buttons)   # no Next at the end

def test_branch_switch_changes_displayed_card():
    g = _game(stage_idx=2)
    m = QuestCardModal(g)
    _draw(m, g)
    assert m.card == 0
    alt = next(b for b in m.buttons if b.id[0] == "alt")
    m.on_button(alt)
    assert m.card == 1

def test_tips_button_disabled_and_inert():
    g = _game()
    m = QuestCardModal(g)
    _draw(m, g)
    tips = next(b for b in m.buttons if b.id[0] == "tips")
    assert m.on_button(tips) is None

def test_modal_never_mutates_game():
    g = _game()
    before = g.to_dict()
    m = QuestCardModal(g)
    _draw(m, g)
    for b in list(m.buttons):
        if b.id[0] != "close":
            m.on_button(b)
    assert g.to_dict() == before

def test_empty_stages_renders_placeholder():
    g = gamestate.GameState(2, 25)      # custom game: no scenario, no stages
    m = QuestCardModal(g)
    _draw(m, g)                          # must not raise
    assert any(b.id[0] == "close" for b in m.buttons)
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_quest_card_modal.py -q` → `ImportError: cannot import name 'QuestCardModal'`.

- [ ] **Step 3: Implement the web modal** in `docs/js/screens.js`, following the conventions of the modals already there (constructor stores `game`, `draw` rebuilds `this.buttons`, `modalHeader` for the header + DONE). Wrap text with `wrapText`. Keep the layout inside 480×480.

- [ ] **Step 4: Mirror in `ui/modals.py`** — `draw(self, hw, game, pal)` / `on_button(self, btn)`, `wrap_text(..., measure=d.measure_text)`, `modal_header` for the header.

- [ ] **Step 5: Add scenes** to `tests/scenes.py`: `quest_card_modal` (a normal stage with A+B text), `quest_card_modal_branch` (the branch stage), `quest_card_modal_empty` (custom game, no stages). Then `python3 -m pytest tests/test_layout.py -q` → PASS.

- [ ] **Step 6: Render and inspect** — `python3 tools/preview.py quest_card_modal /tmp/qcm.png` (and the branch/empty variants). Confirm: long text wraps and does not overflow; the CURRENT marker is visible; the Tips button reads as disabled; pager states are correct. Fix anything cramped.

- [ ] **Step 7: Full suite → green.** `python3 -m pytest tests/ -q`.

---

### Task 2: Entry points (Quest Setup + Progress detail)

**Files:**
- Modify: `docs/js/screen_play.js` + `ui/screen_play.py` (the `quest_setup` view's `open_card_modal` handler)
- Modify: the Progress-detail modal (web `docs/js/screens.js` `QuestingProgressModal`, firmware `ui/modals.py`) — make the quest row title open the card modal
- Modify: `tests/scenes.py` if a new state is worth a scene

**Interfaces:**
- Consumes: `QuestCardModal(game)` from Task 1.
- The play screen's `open_card_modal` handler returns `["modal", new QuestCardModal(game)]` / `("modal", QuestCardModal(game))` — the router already understands the `"modal"` tag.

- [ ] **Step 1: Wire the Quest Setup button.** In the play screen's button handler, replace the stub `return null` for `"open_card_modal"` with the modal transition. Only when `game.stages` is non-empty; otherwise keep returning null (custom games).

- [ ] **Step 2: Wire the Progress-detail quest row.** In the Progress-detail modal, make the **quest row's title** a tap target (id e.g. `["quest_card"]`) that returns the same modal transition. Per the spec this is the second entry point. Because a modal cannot stack on a modal in this codebase's router (single `modal` variable), the handler should **replace** the current modal with the card modal (return the `"modal"` transition — verify how the existing router handles a modal returning a `"modal"` tuple; if it does not support replacement, close first then open, or note the limitation in the report and implement whichever the router supports).

- [ ] **Step 3: Verify in the browser.** Build data if needed (`python3 tools/build_card_data.py`), serve, and walk: New Game → pick Passage → Quest Setup → "View quest card" → page through the 3 stages (stage 3 shows the branch alternatives) → DONE returns to Quest Setup. Then flip into round 1, open Progress detail, tap the quest title → same modal. Capture evidence and console errors.

- [ ] **Step 4: Full suite → green; report.**

---

## Self-Review

**Spec coverage:** read-only stage/card info modal with all text + quest points → Task 1; opens on the current stage and pages every stage → Task 1 (`idx` seeded, pager); per-stage disabled Tips button → Task 1; entry points from Quest Setup + Progress-detail quest row title → Task 2. Branch stages (multiple cards per stage) are handled explicitly. Out of scope, correctly: scraping/serving actual tips (**B-tips**), any state mutation (**B-resolve**).

**Placeholder scan:** Task 1 carries the complete test file; layout is specified element by element with the data shape given. Task 2's router-modal-replacement question is called out with an explicit decision procedure rather than left vague.

**Type consistency:** `QuestCardModal(game)` with `idx`/`card` state and `"close"`/`"redraw"`/null returns is used identically in Task 1's tests and Task 2's wiring. The `game.stages` shape matches the M4-A catalog output and the B-core snapshot.
