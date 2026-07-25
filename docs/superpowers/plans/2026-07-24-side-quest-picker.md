# Side-Quest Picker (M4-B sidequest) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the blind "+ Side quest" numeric entry in the Progress-detail modal with a picker over the 14 real **player side quests** from the catalog — pick by name, and its quest points preload. Manual entry stays as a fallback for anything uncatalogued.

**Architecture:** A small picker modal reading the player-card DB emitted by M4-A (`docs/data/players/<pack>.json` → `cards.sideQuest`), flattened once into a name/points/sphere list. Selecting one appends to the existing `game.side_quests` track (`{points, progress}`) plus a `name` for display. No new game mechanics — this is data-assisted entry.

**Tech Stack:** ES modules (web, Canvas) + MicroPython (firmware); pytest + the scene layout linter.

**Context:** The **B-sidequest** piece of the M4-B family (see `docs/superpowers/specs/2026-07-24-quest-picker-bcore-design.md` → "M4-B family"). B-core and B-modal are complete. Today the Progress-detail modal has a "+ Side quest" button that appends `{points: <default>, progress: 0}` and the user edits the points by hand.

## Global Constraints

- **Two twins in lockstep** (Iron rule #1): web `docs/js/` first, then the firmware mirror; identical layout, ids, behavior.
- **`python3 -m pytest tests/` stays green** (Iron rule #3) including the layout linter; add a scene per new modal state.
- **Touch targets ≥ 24px**; everything within 480×480; no text collisions.
- **Tap-only** — no keyboard, no drag-scroll. Long lists use the established Up/Down pager (see `ui/screen_quest.py`'s `PickCycleScreen` for the exact shape already used in this feature).
- **Catalog data is optional at runtime.** Firmware reads `/data/` from flash, web fetches `data/`; if the player DB is missing or fails to load, the picker must fall back to today's manual "+ Side quest" behavior rather than erroring.
- **Data shape** (verified): each player pack file is `{"pack": str, "cards": {"sideQuest": [card, ...], ...}}`; a side-quest card is the normalized shape `{"id","name","sphere","traits","faces":[{"side","questPoints","text",...}]}`. Quest points live on a face (`questPoints`), and **2 of the 14 have `questPoints: null`** (variable "X" quests — "Protect the Innocent", "Rally the West"): treat null as 0 and let the user edit, never crash.
- **The 14 known cards** (name / points / sphere): Delay the Enemy 8 Tactics; Double Back 4 Spirit; Explore Secret Ways 6 Lore; Fend Off Despair 8 —; Gather Information 4 Neutral; Keep Watch 6 Tactics; Loot the Dungeons 4 —; Mysterious Omens 9 —; Prepare for Battle 6 Leadership; Protect the Innocent null —; Rally the West null Spirit; Scout Ahead 4 Lore; Send for Aid 6 Leadership; The Storm Comes 5 Neutral. (Use these for fixtures; do NOT hardcode them as the runtime source — read the catalog.)

## File structure

- `quest_catalog.py` + `docs/js/quest_catalog.js` — add `side_quests(player_db)` / `sideQuests(playerDb)`: flatten every pack's `cards.sideQuest` into a sorted list of `{id, name, points, sphere, pack}`; plus a `load_player_side_quests()` wrapper per twin (firmware reads flash, web fetches).
- `ui/modals.py` + `docs/js/screens.js` — new `SideQuestPickModal`; and the Progress-detail modal's "+ Side quest" button opens it.
- `gamestate.py` + `docs/js/gamestate.js` — side-quest entries gain an optional `name`.
- `tests/scenes.py`, `tests/test_quest_catalog.py`, `tests/test_modals.py` — scenes + tests.

---

### Task 1: `side_quests` catalog helper (both twins)

**Files:** Modify `quest_catalog.py`, `docs/js/quest_catalog.js`; Test `tests/test_quest_catalog.py`.

**Interfaces (Produces):**
- `side_quests(player_db)` / `sideQuests(playerDb)` — `player_db` is a list of loaded pack dicts (or a dict of them). Returns `[{"id","name","points","sphere","pack"}, ...]` sorted by `name`, where `points` = the first non-null `questPoints` across the card's faces, else `0`.
- `load_player_side_quests()` / `loadPlayerSideQuests()` — the twin-specific loader: read `players/index.json`, then each pack file, and return `side_quests(...)`. Firmware reads `/data/players/...`; web fetches `data/players/...`. On any failure return `[]` (callers fall back to manual entry).

- [ ] **Step 1: Write the failing test** in `tests/test_quest_catalog.py` (module is imported there as `qc`):

```python
SQ_PACKS = [
    {"pack": "The Lost Realm", "cards": {"sideQuest": [
        {"id": "a", "name": "Gather Information", "sphere": "Neutral", "traits": "",
         "faces": [{"side": "", "questPoints": 4, "text": "..."}]}]}},
    {"pack": "Angmar Awakened Campaign Expansion", "cards": {"sideQuest": [
        {"id": "b", "name": "Protect the Innocent", "sphere": None, "traits": "",
         "faces": [{"side": "", "questPoints": None, "text": "..."}]},
        {"id": "c", "name": "Fend Off Despair", "sphere": None, "traits": "",
         "faces": [{"side": "", "questPoints": 8, "text": "..."}]}]}},
    {"pack": "Empty Pack", "cards": {"hero": [{"id": "h", "name": "Aragorn", "faces": []}]}},
]

def test_side_quests_flattens_sorts_and_defaults_null_points():
    out = qc.side_quests(SQ_PACKS)
    assert [s["name"] for s in out] == ["Fend Off Despair", "Gather Information",
                                        "Protect the Innocent"]
    assert [s["points"] for s in out] == [8, 4, 0]      # null -> 0
    assert out[1]["pack"] == "The Lost Realm"
    assert out[1]["sphere"] == "Neutral"

def test_side_quests_handles_packs_without_side_quests():
    assert qc.side_quests([{"pack": "x", "cards": {}}]) == []
```

- [ ] **Step 2: Run → FAIL** (`AttributeError: ... 'side_quests'`).
- [ ] **Step 3: Implement** in `quest_catalog.py`, then mirror in `docs/js/quest_catalog.js`.
- [ ] **Step 4: Run → PASS**; full suite green.
- [ ] **Step 5: Real-data check** — `python3 -c "import quest_catalog,json,glob; packs=[json.load(open(f)) for f in glob.glob('docs/data/players/*.json') if not f.endswith('index.json')]; sq=quest_catalog.side_quests(packs); print(len(sq)); [print(' ',s['name'],s['points'],s['sphere']) for s in sq]"` → expect **14** entries matching the list in Global Constraints.

---

### Task 2: `SideQuestPickModal` + wiring (both twins)

**Files:** Modify `ui/modals.py`, `docs/js/screens.js`, `gamestate.py`, `docs/js/gamestate.js`, `tests/scenes.py`, `tests/test_modals.py`.

**Interfaces:**
- Consumes: `side_quests(...)` / the loader from Task 1.
- Produces: `SideQuestPickModal(game, entries)` — radio-select list of side quests (name + points + sphere), Up/Down pager, **Add** (commits the selection) and **Manual** (appends a blank `{points: 0, progress: 0}` — today's behavior) and DONE/cancel. `on_button` returns `"close"` on commit/cancel and `"redraw"` while paging/selecting.
- Committing appends `{"points": <points>, "progress": 0, "name": <name>}` to `game.side_quests` and logs an event.

**Model note:** `side_quests` entries currently carry `{points, progress}`. Add an optional `name` (default `None`/absent) that serializes through `to_dict`/`from_dict` and is tolerated when absent (old saves). Anywhere a side quest is labelled (Progress zone "S1/S2", Progress-detail rows), prefer `name` when present, else keep today's generic label — check both twins for label sites.

- [ ] **Step 1: Write the failing tests** in `tests/test_modals.py` (follow that file's existing modal-test conventions for constructing `FakeHardware`/`Palette`):

```python
def test_side_quest_pick_adds_selected_with_points():
    g = <a GameState with no side quests>
    entries = [{"id": "a", "name": "Scout Ahead", "points": 4, "sphere": "Lore", "pack": "p"},
               {"id": "b", "name": "Keep Watch", "points": 6, "sphere": "Tactics", "pack": "p"}]
    m = SideQuestPickModal(g, entries)
    <draw>
    m.on_button(<the row button for index 1>)          # select "Keep Watch"
    m.on_button(<the "add" button>)
    assert g.side_quests[-1]["points"] == 6
    assert g.side_quests[-1]["name"] == "Keep Watch"

def test_side_quest_pick_manual_falls_back_to_blank_entry():
    ...
    m.on_button(<the "manual" button>)
    assert g.side_quests[-1]["points"] == 0 and g.side_quests[-1]["progress"] == 0

def test_side_quest_pick_empty_entries_renders_and_offers_manual():
    m = SideQuestPickModal(g, [])
    <draw>   # must not raise
    assert any(b.id[0] == "manual" for b in m.buttons)
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement the web modal** in `docs/js/screens.js`; mirror in `ui/modals.py`. Reuse the radio glyph + pager already used by `ChooseScenarioScreen`/`PickCycleScreen` in `ui/screen_quest.py` so this feels like the same family.
- [ ] **Step 4: Wire the entry point** — the Progress-detail modal's "+ Side quest" button opens this modal instead of appending directly. The router holds one modal at a time; the quest-card modal solved this with a `pending_quest_card` flag consumed by the main loop (see `main.py` / `docs/js/main.js`) — **follow that same established pattern** rather than inventing a new one. If the entries list is empty (no catalog), skip the picker and keep today's direct append.
- [ ] **Step 5: Add scenes** `side_quest_pick` and `side_quest_pick_empty` to `tests/scenes.py`; linter → PASS.
- [ ] **Step 6: Render and inspect** — `python3 tools/preview.py side_quest_pick /tmp/sq.png` (+ empty). Names must not clip; points/sphere legible; pager correct.
- [ ] **Step 7: Browser walkthrough** — build data if needed, serve, start any scenario, reach round 1, open Progress detail → "+ Side quest" → pick "Keep Watch" → Add → confirm a side-quest row appears with 6 target points and the name shown. Report console errors.
- [ ] **Step 8: Full suite → green.**

---

## Self-Review

**Spec coverage:** picker over the 14 player side quests → Tasks 1-2; preloads quest points → Task 2 commit path; manual entry preserved → the Manual button + the empty-catalog fallback; reached from the Progress-detail add-side-quest action → Task 2 Step 4. Encounter-side side quests are deliberately out of scope (they arrive with a scenario, not chosen by a player).

**Placeholder scan:** Task 1 carries complete test code and the verified 14-row expectation. Task 2's tests are given in shape with the exact assertions; the modal-open mechanism points at the existing `pending_quest_card` precedent instead of leaving it open.

**Type consistency:** `side_quests(...)` returns `{id,name,points,sphere,pack}` in Task 1 and is consumed with those exact keys in Task 2; the appended game entry is `{points, progress, name}` in both the test and the model note.
