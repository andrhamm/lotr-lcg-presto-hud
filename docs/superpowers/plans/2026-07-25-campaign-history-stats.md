# Campaign, History & Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give players a persistent record of finished games — scenario, outcome, rounds, per-player result — that survives starting a new game, and a read-only place to browse it. This is the foundation ("H-core") of a larger, deliberately decomposed family covering the TODO board's whole `"long term: campaign mode tracking, long term historical game results, stats, sharing"` item; this plan fully implements H-core (real code, TDD) and sketches the three pieces that build on it (interfaces + dependencies, not full tasks) — see "The History family" below.

**Architecture:** A new pure module (`history.py` / `docs/js/history.js`) turns a just-finished `GameState` into a small, capped record. The existing `end_game` router branch (both twins, already the single place a game is declared over and its save cleared) appends one record on every finish, into a **new persistence slot fully separate from the live save** — `/history.json` (firmware) / `localStorage["lotr-hud-history"]` (web) — so `save_quit`, starting a fresh game, or a corrupted live save can never lose history, and clearing history can never lose an in-progress game. A minimal `HistoryModal` (reusing the existing `modal_header` and the Log screen's paging convention) surfaces the archive read-only from a new Settings tile.

**Tech Stack:** ES modules (web, Canvas) + MicroPython (firmware); pytest + the scene layout linter — same as the rest of the project, no new dependencies.

**Context — grounded in what already exists (verified by reading the actual code, not assumed):**

- **`quest_history`** (`gamestate.py`, `GameState.__init__`) is already exactly "per-round willpower/staging/outcome records": `{"round": int, "willpower": int, "staging": int, "outcome": "success"|"fail"|"tie", "n": int, "heading": int}`, appended in `resolve_quest()` and already self-capping at the last **20** entries (`if len(self.quest_history) > 20: self.quest_history = self.quest_history[-20:]`). The in-game UI never shows more than the last **8** of those (`ui/modals.py`, `QuestingProgressModal._draw_chart`: `cols = self.game.quest_history[-8:]`) — H-core's archived records reuse this exact tail-8 convention rather than inventing a new cap, keeping records small for free.
- **The game log** (`game.log`) is oldest-first, unbounded, and effectively a debug/session transcript (per-phase-transition entries with full text) — far too large and not aggregable, so it is deliberately **not** archived; `quest_history`'s already-structured per-round numbers are what a "finished games" list and later stats actually need.
- **Campaign-type cards, verified via the real generated data:** `tools/build_card_data.py`'s `build_outputs()` buckets each scenario's non-mode `Campaign`-type cards into a `campaign` list (`campaign = [c for c in group if c["type"] == "Campaign" and not _is_mode(c)]`). Checked directly against the generated corpus: **33 of 349** `docs/data/scenarios/*.json` files have a non-empty `campaign` bucket. Inspected one (`the-oath-campaign.json`): a single physical **"The Oath"** Campaign card whose two faces carry the actual resource-token rules text — *"Setup: ... Response: At the end of each round, place 1 resource token here."* / *"Resolution: If there are 6 or more resource tokens here, ..."*. This is the real in-game object a future campaign-tracking piece (H-campaign, sketched below) would need a counter for — not an abstraction invented for this plan.
- **Existing persistence, verified by reading both twins directly:** web uses `localStorage` keys `STATE_KEY = "lotr-hud-state"` / `PREFS_KEY = "lotr-hud-prefs"` (`docs/js/main.js`); firmware uses flash files `STATE_PATH = "/state.json"` / `PREFS_PATH = "/device.json"` (`main.py`). Both follow the identical `{"saved_at": <ts>, "state": game.toDict()}` shape, written/read through small `try`/`except`-wrapped functions. History reuses this exact pattern under new, separate keys/paths.
- **`to_dict`/`from_dict`** (`gamestate.py`) is the serialization contract every persisted field goes through; new fields default sanely on old saves via `d.get(key, default)`, never a raw `d[key]` — the established backward-compatibility rule this plan follows too.
- **Flash budget, verified:** Pimoroni's own product page (`https://shop.pimoroni.com/en-us/products/presto`, fetched live) lists **16MB of QSPI flash**. The compiled card catalog already deployed to that flash measures **~4.9MB** on disk (`du -sh docs/data/`, run directly against this checkout). Any history-archive size budget below is set against these two real numbers, not guesses.
- **Where this sits on the roadmap:** `design/roadmap.md`'s five-milestone "prototype to beta" arc (verified: M1 Visual foundation … **M5 Beta hardening**, the last one) and the public `ROADMAP.md` (verified: `## Shipped` M1 Offline HUD; `## Planned` M2 Connectivity, M3 Spotify) both stop short of anything like this. That matches the TODO board's own framing of this item as **"long term"** — this plan doesn't claim a slot in either numbered roadmap; it names its own family (below) so a maintainer can fold it into a future milestone once the current arcs ship.

## The History family (decomposition)

Matching how `docs/superpowers/specs/2026-07-24-quest-picker-bcore-design.md` decomposed the M4-B family: this plan builds the first row completely; the rest are sketched (interfaces + dependencies only) after Task 3.

| Piece | Scope | Depends on |
|---|---|---|
| **H-core** (this plan, Tasks 1–3) | Completed-game record shape + bounded, separate-from-the-live-save archive; the `end_game` hook; a read-only paged History view reached from Settings | `quest_history`, `game.game_over`, existing persistence conventions |
| **H-stats** (sketched below) | Aggregate stats (win rate, avg rounds, per-scenario breakdown, streaks) computed over the H-core archive; a compact stats view reusing the existing arc/token primitives | H-core's record shape |
| **H-campaign** (sketched below) | A small numeric campaign id linking games; carrying a scenario's Campaign-card resource pool (the verified `campaign` bucket, e.g. "The Oath") forward between a campaign's sessions | H-core's record shape; M4-B's `scenario` field |
| **H-share** (sketched below) | Getting a record or stat summary off the device — web: native copy/download; firmware: a QR-encoded link into the web twin (self-serve) plus the already-available `mpremote cp` file pull (maintainer fallback, zero new code) | H-core; H-stats (for a nicer payload) |

**H-core builds first** because every other piece needs a stable record shape and an archive to read — exactly the same "foundational model piece first" ordering `B-core` used in the M4-B family, even though the TODO text lists "campaign mode" before "historical results." H-stats and H-campaign can then proceed in either order; H-share is last because sharing something is only useful once there's a nice *something* (H-stats) to share.

## Global Constraints

- **Two twins in lockstep** (Iron rule #1): web `docs/js/` first, then firmware.
- **`python3 -m pytest tests/` stays green** (Iron rule #3), including the layout linter.
- **History is a separate store from the live save**, not a field on `GameState`. Starting a new game, `save_quit`, or clearing a corrupted live save must never touch it; nothing in this plan reads or writes `/state.json` / `STATE_KEY`.
- **Read-only surfaces never mutate `game`.** `HistoryModal` follows `QuestCardModal`'s existing precedent exactly — presentational only.
- **Bounded storage**, sized against the verified flash budget above, not left open-ended (see Task 1's `MAX_HISTORY`).
- **Records stay small on purpose:** never store the full `game.log` or the full 20-entry `quest_history` in an archived record — only the already-established last-8 tail (see Context).
- Touch targets ≥ 24px each dimension; everything within 480×480; no text collisions (linter-enforced).

## File structure

- `history.py` (new) + `docs/js/history.js` (new) — pure `summarize_game`/`summarizeGame` + `archive_record`/`archiveRecord`.
- `main.py` + `docs/js/main.js` — `HISTORY_PATH`/`HISTORY_KEY`, `load_history`/`save_history` (mirroring `load_saved`/`save_state`), the `end_game` hook, an `open_history` dispatch branch.
- `ui/modals.py` (new `HistoryModal`) + `docs/js/screens.js` (mirror).
- `ui/screen_settings.py` (new History tile) + `docs/js/screens_other.js` (mirror).
- `tests/test_history.py` (new), `tests/scenes.py`.

---

### Task 1: `history.py` — pure record + archive logic

**Files:**
- Create: `history.py`
- Test: `tests/test_history.py` (new)

**Interfaces (Produces):**
- `summarize_game(game, now=None) -> dict | None` — pure. `None` if `game.game_over` is falsy (defensive; the real caller only calls this once it's set). Otherwise returns:
  ```
  {"ended_at": float|None, "scenario": dict|None, "result": "victory"|"defeat",
   "rounds": int, "duration": str|None,
   "players": [{"label","final_threat","eliminated","starting_threat"}, ...],
   "quest_history": [...]}   # game.quest_history[-8:], each entry copied
  ```
- `archive_record(records, record, max_records=MAX_HISTORY) -> list` — pure. Appends oldest-first (matching `game.log`'s own convention) and caps by dropping the oldest.
- `MAX_HISTORY = 50` — see the sizing comment in the implementation below.

- [ ] **Step 1: Write the failing test** (`tests/test_history.py`):

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gamestate
import history

SCENARIO = {"slug": "p", "name": "Passage Through Mirkwood", "pack": "Core Set",
           "cycle": "Core Set", "source": "official", "kind": "quest",
           "nightmare": False, "mode": "Standard"}

def _finished_game(result="victory", round_=5, scenario=None, hist_rounds=11):
    g = gamestate.GameState(2, 25)
    g.scenario = scenario
    g.round = round_
    g.quest_history = [{"round": i, "willpower": 5, "staging": 3,
                        "outcome": "success", "n": 2, "heading": 0}
                       for i in range(1, hist_rounds + 1)]
    g.set_game_over(result)
    return g

def test_summarize_game_returns_none_before_game_over():
    g = gamestate.GameState(2, 25)
    assert history.summarize_game(g) is None

def test_summarize_game_captures_core_fields():
    g = _finished_game(result="victory", round_=5, scenario=SCENARIO)
    rec = history.summarize_game(g, now=1234567890.0)
    assert rec["result"] == "victory"
    assert rec["rounds"] == 5
    assert rec["scenario"]["slug"] == "p"
    assert rec["ended_at"] == 1234567890.0
    assert len(rec["players"]) == 2
    assert rec["players"][0]["starting_threat"] == 25

def test_summarize_game_caps_quest_history_to_last_8():
    g = _finished_game(hist_rounds=11)
    rec = history.summarize_game(g)
    assert len(rec["quest_history"]) == 8
    assert rec["quest_history"][0]["round"] == 4     # oldest of the kept tail
    assert rec["quest_history"][-1]["round"] == 11    # newest

def test_summarize_game_custom_quest_has_null_scenario():
    g = _finished_game(scenario=None)
    rec = history.summarize_game(g)
    assert rec["scenario"] is None

def test_summarize_game_snapshots_scenario_not_a_live_reference():
    g = _finished_game(scenario=dict(SCENARIO))
    rec = history.summarize_game(g)
    g.scenario["name"] = "mutated after archiving"
    assert rec["scenario"]["name"] == "Passage Through Mirkwood"

def test_archive_record_appends_oldest_first():
    out = history.archive_record([{"rounds": 1}], {"rounds": 2})
    assert [r["rounds"] for r in out] == [1, 2]

def test_archive_record_caps_dropping_oldest():
    records = [{"rounds": i} for i in range(5)]
    out = history.archive_record(records, {"rounds": 99}, max_records=3)
    assert [r["rounds"] for r in out] == [3, 4, 99]
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_history.py -q` → `ModuleNotFoundError: No module named 'history'`.

- [ ] **Step 3: Implement `history.py`:**

```python
"""Completed-game history: turns a finished GameState into a compact,
bounded archive record - a permanent record kept fully separate from the
live save-in-progress (/state.json | localStorage STATE_KEY), so
finishing or starting a new game never erases what came before it. Pure
logic only - no file/localStorage I/O (that lives in main.py's
load_history()/save_history(), mirroring save_state()/load_saved()
exactly). See docs/superpowers/plans/2026-07-25-campaign-history-stats.md
(H-core).

A record captures only what a finished-games list needs to display and
later aggregate (H-stats) - not the full round-by-round game.log
(unbounded, session-only) and not the full 20-entry quest_history (only
the last 8 rounds are kept, matching what the in-game round-by-round
chart already shows - ui/modals.py's QuestingProgressModal._draw_chart,
`cols = self.game.quest_history[-8:]`).
"""

MAX_HISTORY = 50   # ~1.1-1.3KB/record worst case (4 players, a loaded
                    # scenario, an 8-round tail) => ~65KB total at the cap.
                    # Verified against the Presto's real 16MB QSPI flash
                    # (shop.pimoroni.com/en-us/products/presto) and the
                    # ~4.9MB the card catalog already uses on it
                    # (`du -sh docs/data/`) - a rounding error either way.
                    # A single constant to raise later (500 records is
                    # still well under 700KB) if the user wants a longer
                    # memory than "last 50 games".


def summarize_game(game, now=None):
    """A finished GameState -> a compact archive record, or None if the
    game hasn't ended (game.game_over is falsy - defensive; the only real
    caller is the end_game handler, where it's always set by then). `now`
    is an injected unix-seconds float (or None - mirrors save_state's own
    time.time() convention and load_saved's "RTC not set" handling) so
    this stays pure/host-testable rather than calling time.time() itself."""
    go = game.game_over
    if not go:
        return None
    return {
        "ended_at": now,
        "scenario": dict(game.scenario) if game.scenario else None,
        "result": go.get("result"),
        "rounds": go.get("round", game.round),
        "duration": go.get("duration"),
        "players": [{"label": p.label, "final_threat": p.threat,
                     "eliminated": p.eliminated,
                     "starting_threat": p.starting_threat} for p in game.players],
        "quest_history": [dict(e) for e in game.quest_history[-8:]],
    }


def archive_record(records, record, max_records=MAX_HISTORY):
    """Append `record` (oldest-first, matching game.log's own convention)
    and cap at `max_records`, dropping the oldest first - pure, so both
    twins' save_history() can call it identically right after their own
    load_history()."""
    out = list(records) + [record]
    return out[-max_records:]
```

- [ ] **Step 4: Run tests → PASS.** `python3 -m pytest tests/test_history.py -q`.

- [ ] **Step 5: Mirror in `docs/js/history.js`:**

```javascript
// Port of history.py — method-for-method. Pure logic only; load/saveHistory
// live in main.js (localStorage), mirroring saveState()/loadSaved().
export const MAX_HISTORY = 50;

export function summarizeGame(game, now = null) {
  const go = game.game_over;
  if (!go) return null;
  return {
    ended_at: now,
    scenario: game.scenario ? { ...game.scenario } : null,
    result: go.result,
    rounds: go.round ?? game.round,
    duration: go.duration ?? null,
    players: game.players.map(p => ({ label: p.label, final_threat: p.threat,
      eliminated: p.eliminated, starting_threat: p.starting_threat })),
    quest_history: game.quest_history.slice(-8).map(e => ({ ...e })),
  };
}

export function archiveRecord(records, record, maxRecords = MAX_HISTORY) {
  const out = [...records, record];
  return out.slice(-maxRecords);
}
```

- [ ] **Step 6: Full suite + commit.** `python3 -m pytest tests/ -q`; `git add -A && git commit -m "feat(history): pure game-record summary + bounded archive logic"`.

---

### Task 2: Persistence + the `end_game` hook (both twins)

**Files:**
- Modify: `main.py` (new `HISTORY_PATH`, `load_history`/`save_history`, the `end_game` branch)
- Modify: `docs/js/main.js` (mirror: `HISTORY_KEY`, `loadHistory`/`saveHistory`, the `end_game` branch)

**Interfaces:**
- `load_history() -> list` / `loadHistory()` — read `{"records": [...]}` from `/history.json` / `localStorage["lotr-hud-history"]`; on **any** failure (never deployed/written yet, corrupt file) return `[]`, matching `quest_catalog.py`'s established "optional data, degrade silently" convention. Like `save_state`/`load_saved`, these are thin I/O wrappers with no seam to unit-test against (no `/history.json` on the dev host) — not host-tested, verified instead by Task 3's manual walkthrough once there's a UI to see the result in.
- `save_history(records)` / `saveHistory(records)` — write `{"records": records}`.
- The `end_game` router branch (already the single point where a finished game's save is cleared, in both twins) additionally archives a summary **before** clearing.

- [ ] **Step 1: `main.py`.** Add near the other `*_PATH` constants:
```python
HISTORY_PATH = "/history.json"
```
Add near `save_state`/`load_saved`/`clear_state`:
```python
def load_history():
    try:
        with open(HISTORY_PATH) as f:
            return json.load(f).get("records", [])
    except Exception:
        return []


def save_history(records):
    try:
        with open(HISTORY_PATH, "w") as f:
            json.dump({"records": records}, f)
    except Exception:
        pass
```
Add `import history` near the top (alongside `import quest_catalog`). Change the existing `end_game` branch (verified exact current text) from:
```python
                        elif kind == "end_game":
                            clear_state()
                            game = GameState()
                            game.clock = clock
                            screens["boot"] = BootScreen(None)
                            nav_stack = []
                            active = "boot"
```
to:
```python
                        elif kind == "end_game":
                            rec = history.summarize_game(game, now=time.time())
                            if rec is not None:
                                save_history(history.archive_record(load_history(), rec))
                            clear_state()
                            game = GameState()
                            game.clock = clock
                            screens["boot"] = BootScreen(None)
                            nav_stack = []
                            active = "boot"
```

- [ ] **Step 2: Mirror in `docs/js/main.js`.** Add near `STATE_KEY`/`PREFS_KEY`:
```javascript
const HISTORY_KEY = "lotr-hud-history";
function loadHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY))?.records ?? []; }
  catch { return []; }
}
function saveHistory(records) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify({ records }));
}
```
Add `import { summarizeGame, archiveRecord } from "./history.js";` near the top. Change the existing `end_game` branch (verified exact current text) from:
```javascript
      } else if (kind === "end_game") {
        clearState();
        game = new GameState();
        game.clock = clock;
        screens.boot = new BootScreen(null, bootImg);
        navStack = [];
        active = "boot";
      }
```
to:
```javascript
      } else if (kind === "end_game") {
        const rec = summarizeGame(game, Date.now() / 1000);
        if (rec !== null) saveHistory(archiveRecord(loadHistory(), rec));
        clearState();
        game = new GameState();
        game.clock = clock;
        screens.boot = new BootScreen(null, bootImg);
        navStack = [];
        active = "boot";
      }
```

- [ ] **Step 3: `python3 -m pytest tests/ -q` stays green** (nothing new to unit-test here, but this confirms the dispatch edit didn't break existing behavior — `tests/test_modals.py` and friends still exercise `GameOverScreen`/the router indirectly). Manual end-to-end verification (a real finished game producing a real `/history.json` entry) happens in Task 3's walkthrough, once `HistoryModal` exists to see it in.

- [ ] **Step 4: Commit.** `git add -A && git commit -m "feat(history): archive a record on end_game, separate from the live save"`.

---

### Task 3: `HistoryModal` (both twins) + Settings entry point

**Files:**
- Modify: `ui/modals.py` (new `HistoryModal`), `docs/js/screens.js` (mirror)
- Modify: `ui/screen_settings.py` (History tile + `open_history` result), `docs/js/screens_other.js` (mirror)
- Modify: `main.py`, `docs/js/main.js` (`open_history` dispatch branch)
- Modify: `tests/scenes.py`
- Test: extend `tests/test_history.py`

**Interfaces:**
- `HistoryModal(records)` — `records` is whatever `load_history()` returned (oldest-first on disk); the modal reverses it once at construction to show newest-first, matching `ScreenLog`'s own convention. Purely presentational, like `QuestCardModal` — never mutates `game`. `on_button` returns `"close"` (DONE), `"redraw"` (paging), `None` otherwise. Paged with the Log screen's exact convention: `PER_PAGE = 6`, Older/Newer buttons + "N/M" shown only on overflow.
- Settings gains a second **DEVICE** tile, "History" (`icons.TRAIL` — no dedicated history/book icon exists yet; `TRAIL` is already used elsewhere for "progress over time" and needs no new art). Tapping it returns `("open_history",)`, handled centrally (screens don't do file/localStorage I/O directly in this codebase — see `save_quit`/`end_game`'s own precedent) by opening `HistoryModal(load_history())`.
  - **Verified layout note:** firmware `ScreenSettings`'s content already runs from y=56 to y≈476 (computed directly from the real `y +=` chain in `ui/screen_settings.py`) — there is no free vertical space for a new row. The DEVICE tile row is the only slot that costs zero extra height (a tile row is already reserved regardless of how many tiles are in it). Firmware's DEVICE row has one tile today (LED at x=16) → History goes at x=132 (second tile). **Web's `ScreenSettings` has already diverged**: it has a second DEVICE tile firmware doesn't (About, `icons.LORE`, at x=132) — a pre-existing, out-of-scope twin-parity gap, not something this plan fixes — so on web, History becomes the *third* tile, at x=248.

- [ ] **Step 1: Write the failing tests** (extend `tests/test_history.py`):

```python
def test_history_modal_shows_empty_state():
    from ui.modals import HistoryModal
    from tests.fake_hardware import FakeHardware
    from ui.theme import Palette
    hw = FakeHardware()
    pal = Palette(hw.display)
    m = HistoryModal([])
    m.draw(hw, gamestate.GameState(), pal)
    assert any(b.id[0] == "close" for b in m.buttons)

def test_history_modal_shows_newest_first():
    from ui.modals import HistoryModal
    from tests.fake_hardware import FakeHardware
    from ui.theme import Palette
    records = [{"scenario": None, "result": "victory", "rounds": i,
               "duration": None, "ended_at": None} for i in (1, 2, 3)]
    m = HistoryModal(records)
    assert [r["rounds"] for r in m.records] == [3, 2, 1]

def test_history_modal_paginates_and_never_mutates_game():
    from ui.modals import HistoryModal
    from tests.fake_hardware import FakeHardware
    from ui.theme import Palette
    records = [{"scenario": None, "result": "victory", "rounds": i,
               "duration": None, "ended_at": None} for i in range(8)]
    g = gamestate.GameState()
    before = g.to_dict()
    m = HistoryModal(records)
    hw = FakeHardware()
    pal = Palette(hw.display)
    m.draw(hw, g, pal)
    older = next(b for b in m.buttons if b.id[0] == "older")
    assert m.on_button(older) == "redraw" and m.page == 1
    assert g.to_dict() == before

def test_settings_history_tile_returns_open_history():
    from ui.screen_settings import ScreenSettings
    s = ScreenSettings()
    s.draw(FakeHardware(), gamestate.GameState(), Palette(FakeHardware().display))
    tile = next(b for b in s.buttons if b.id[0] == "history")
    assert s.on_button(tile, gamestate.GameState()) == ("open_history",)
```
(This test file already has `gamestate`, `FakeHardware`, `Palette` imported from Task 1 — reuse those imports.)

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement `HistoryModal` in `ui/modals.py`:**

```python
class HistoryModal:
    """Read-only, paged list of finished games (H-core) - reached from
    Settings' History tile. Purely presentational, matching
    QuestCardModal's own precedent: never mutates `game`. `records` is
    whatever load_history() returned (main.py) - already oldest-first on
    disk, shown newest-first here to match ScreenLog's convention."""

    PER_PAGE = 6
    ROW_H = 56

    def __init__(self, records):
        self.records = list(reversed(records))
        self.page = 0
        self.buttons = []

    def _pages(self):
        return max(1, (len(self.records) + self.PER_PAGE - 1) // self.PER_PAGE)

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        from ui.header import modal_header
        modal_header(d, pal, game, "History", self.buttons)

        if not self.records:
            text_center(d, pal, "No games finished yet", 240, 200, 2, pal.dim)
            return

        pages = self._pages()
        self.page = min(self.page, pages - 1)
        chunk = self.records[self.page * self.PER_PAGE:(self.page + 1) * self.PER_PAGE]
        y = 50
        for rec in chunk:
            name = rec["scenario"]["name"] if rec["scenario"] else "Custom game"
            name = truncate_text(name, 2, 300, d.measure_text)
            win = rec["result"] == "victory"
            text_left(d, pal, name, 12, y, 2, pal.tan)
            text_left(d, pal, "VICTORY" if win else "DEFEAT", 330, y, 1,
                      pal.gold if win else pal.red)
            detail = "R%d" % rec["rounds"]
            if rec.get("duration"):
                detail += " - %s" % rec["duration"]
            detail += " - %s" % _fmt_history_date(rec.get("ended_at"))
            text_left(d, pal, detail, 12, y + 22, 1, pal.dim)
            y += self.ROW_H

        if pages > 1:
            up = Button(("older",), 12, 420, 150, 46)
            dn = Button(("newer",), 318, 420, 150, 46)
            bevel(d, pal, up.x, up.y, up.w, up.h, pal.btn)
            text_center(d, pal, "Older", up.x + 75, up.y + 14, 2, pal.tan)
            bevel(d, pal, dn.x, dn.y, dn.w, dn.h, pal.btn)
            text_center(d, pal, "Newer", dn.x + 75, dn.y + 14, 2, pal.tan)
            text_center(d, pal, "%d/%d" % (self.page + 1, pages), 240, 434, 2, pal.muted)
            self.buttons.append(up)
            self.buttons.append(dn)

    def on_button(self, btn):
        k = btn.id[0]
        if k == "close":
            return "close"
        if k == "older":
            self.page += 1
            return "redraw"
        if k == "newer":
            self.page = max(0, self.page - 1)
            return "redraw"
        return None


def _fmt_history_date(ts):
    """"earlier session" on no timestamp (matches main.py's load_saved()
    RTC-unset convention) - else YYYY-MM-DD."""
    if ts is None:
        return "earlier session"
    import time
    lt = time.localtime(ts)
    if lt[0] < 2024:
        return "earlier session"
    return "%04d-%02d-%02d" % (lt[0], lt[1], lt[2])
```

- [ ] **Step 4: Settings tile.** In `ui/screen_settings.py`'s `draw`, right after the existing LED tile block:
```python
        self._app_tile(d, pal, 16, y, icons.LED, "LEDs", enabled=True)
        self.buttons.append(Button(("led",), 16, y, TILE, TILE))
```
add:
```python
        self._app_tile(d, pal, 16 + TILE + TILE_GAP, y, icons.TRAIL, "History", enabled=True)
        self.buttons.append(Button(("history",), 16 + TILE + TILE_GAP, y, TILE, TILE))
```
In `on_button`, add: `if k == "history": return ("open_history",)`.

- [ ] **Step 5: Main-loop dispatch.** In `main.py`, right after the existing:
```python
                        elif kind == "open_repo":
                            pass  # no browser on the device; link lives in the web twin
```
add:
```python
                        elif kind == "open_history":
                            from ui.modals import HistoryModal
                            modal = HistoryModal(load_history())
```

- [ ] **Step 6: Run tests → PASS.**

- [ ] **Step 7: Mirror in `docs/js/screens.js`** (`HistoryModal`, same `PER_PAGE`/`ROW_H`, using `modalHeader`/`truncateText`/`measureText` already imported in that file) and `docs/js/screens_other.js`'s `ScreenSettings` — **note the x-offset difference above**: web's DEVICE row already has LED (x=16) and About (x=132), so History goes at x=248:
```javascript
    const hx = ax + TILE + 16;   // ax is the existing About tile's x (132)
    bevel(ctx, hx, y, TILE, TILE, pal.card);
    icons.drawIcon(ctx, icons.TRAIL, hx + 30, y + 14, pal.gold, 2);
    textCenter(ctx, "History", hx + TILE / 2, y + TILE - 22, 1, pal.tan);
    this.buttons.push(new Button(["history"], hx, y, TILE, TILE));
```
and `onButton`: `if (k === "history") return ["open_history"];`. In `docs/js/main.js`, add `HistoryModal` to the existing `import { EliminationModal, QuestCardModal, SideQuestPickModal } from "./screens.js";` line, and add a branch next to the existing `open_repo` one:
```javascript
      } else if (kind === "open_history") {
        modal = new HistoryModal(loadHistory());
      }
```

- [ ] **Step 8: Add scenes** to `tests/scenes.py`:
```python
def _history_modal():
    from ui.modals import HistoryModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    records = [
        {"scenario": {"name": "Passage Through Mirkwood"}, "result": "victory",
         "rounds": 6, "duration": "42m10s", "ended_at": None},
        {"scenario": None, "result": "defeat", "rounds": 3, "duration": None, "ended_at": None},
    ]
    m = HistoryModal(records)
    m.draw(hw, _game(), pal)
    return hw, m


def _history_modal_empty():
    from ui.modals import HistoryModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    m = HistoryModal([])
    m.draw(hw, _game(), pal)
    return hw, m
```
Add `"history_modal": _history_modal, "history_modal_empty": _history_modal_empty,` to `SCENES`. Render: `python3 tools/preview.py history_modal /tmp/hist.png` and the empty variant — confirm rows don't collide with the VICTORY/DEFEAT badge or each other, and the empty state is centered and legible. `python3 -m pytest tests/test_layout.py -q` → PASS.

- [ ] **Step 9: Verify end-to-end.** Play (or fast-forward via the console/host harness) a game to completion on the web twin, let it hit `end_game`, then Settings → History — confirm the just-finished game appears with the right scenario name, result, and round count, and that starting a brand-new game afterward does **not** clear it. Repeat on-device after deploying.

- [ ] **Step 10: Full suite + commit.** `python3 -m pytest tests/ -q`; `git add -A && git commit -m "feat(history): read-only History view + Settings entry point"`.

---

## Sketched: the rest of the History family

Not implemented here — interfaces and dependencies only, so a follow-up plan can pick each up without re-deriving the shape.

### H-stats — aggregate stats over the archive

**Depends on:** H-core's record shape (stable once Task 1 lands).

- New pure module `stats.py` / `docs/js/stats.js`: `aggregate(records) -> dict`, something like `{"games": int, "wins": int, "win_rate": float, "avg_rounds": float, "longest_game": record|None, "by_scenario": {slug: {"played": int, "won": int}}, "current_streak": {"kind": "win"|"loss", "n": int}}` — every input field already exists on an H-core record, so this is pure aggregation, no new data source.
- A stats view reusing `ui/widgets.py`'s existing circular primitives (`ring`, `token`, `disc`, `arc_runs` — the same ones the TODO board's own "Stats redesign" entry credits for the Players/Progress detail views) for e.g. a win-rate ring and a compact per-scenario list. Default placement: a summary strip folded into the top of `HistoryModal` itself (above the list) rather than a whole new nav destination, since it's a handful of numbers, not a full screen's worth — revisit if the real content ends up needing more room.
- Not yet decided: the exact field set beyond the sketch above, and whether `by_scenario` needs pagination once someone has played dozens of distinct scenarios (H-core's own list already established the pager pattern to reuse if so).

### H-campaign — linking games + carrying Campaign-card state forward

**Depends on:** H-core's record shape (gains a `campaign_number` field); M4-B's `scenario` field (cycle/slug already known per game).

- **Campaign identity, zero typing:** reuse `ui/widgets.py`'s existing `stepper()` for a small "Campaign #" field (default `0` = not part of a campaign) on Player Setup or Scenario Options. This is the RingsDB plan's device-input reasoning applied in the opposite direction: RingsDB IDs are large, so a stepper was rejected there in favor of a keypad; campaign numbers are naturally *small* (a player runs a handful of concurrent campaigns at most), so the plain stepper already in this codebase is the right-sized widget here — no new input mechanism needed.
- `GameState.campaign_number = 0` (int, serialized like any other field).
- **Carrying Campaign-card resource pools forward:** `game.campaign_pool = {}` (dict keyed by the Campaign card's `id`, from the scenario's verified `campaign` bucket — see Context — value = a token count), edited with the existing `CounterState` widget (`ui/counter.py`), the same primitive already backing other in-game counters. A pure `campaign.py` / `docs/js/campaign.js` function, `carry_forward(prior_records, campaign_number) -> pool`, would scan the H-core archive for the most recent record sharing `campaign_number` and seed a freshly-preloaded scenario's pool from it.
- Not yet decided: the in-play UI for showing/editing a scenario's Campaign card + pool (likely a small panel similar to today's Side Quests row); whether "official" FFG campaign boundaries (a specific product's fixed scenario sequence) get their own curated data later, the way `tools/build_card_data.py`'s `PACK_META` curates cycle/source — deferred rather than guessed, matching that precedent.

### H-share — getting a record or summary off the device

**Depends on:** H-core (record format); ideally H-stats (a nicer payload than raw JSON).

- **Web:** a "Copy summary" / "Download JSON" affordance in `HistoryModal` — the browser's native clipboard/download, zero new infrastructure, consistent with this project's already-static, backend-free posture.
- **Firmware, already available today, zero new code:** `/history.json` is a flat file the moment Task 2 lands; sharing already means the maintainer pulling it with `mpremote cp :/history.json ./`, exactly `CLAUDE.md`'s existing "Device access (main session only)" convention. Worth stating explicitly so H-share isn't mistaken for the *only* way to get data off the device — it's the fallback, not the deliverable.
- **Firmware, self-serve (the actual H-share deliverable):** a **QR code shown on-device**, encoding a small payload as a URL fragment into the web twin — e.g. `https://andrhamm.com/lotr-lcg-presto-hud/#share=<base64url(JSON)>` — decoded and rendered **entirely client-side** (no backend, matching the project's static-Pages hosting). This reuses the same "Presto displays a QR, a phone reads it" primitive `ROADMAP.md`'s own M2 already anticipates for WiFi provisioning, so it needs no new *device capability* beyond a QR-rendering routine M2 will need anyway — just not built yet, either place. Payload size must stay small enough to scan reliably across a table (a single-game summary, well under 1KB, fits comfortably; a multi-game export does not — that stays on the `mpremote cp` path).
- Not yet decided: the QR-rendering primitive itself (no encoder exists in this codebase today; would need to be pure-Python/MicroPython-safe, or precomputed the way `tools/build_icons.py` rasterizes ahead of time rather than at runtime) and the exact `#share=` contract + the web twin's decode/render page.

---

## Self-Review

**Spec coverage:** "what a completed game record is and where it's stored, with flash bounded" → Task 1 (`summarize_game`'s exact shape, reusing the already-capped `quest_history` tail) + Task 1's `MAX_HISTORY` sizing comment (real math against the verified 16MB flash and the verified ~4.9MB already in use, not a guess); "campaign linkage across scenarios" → addressed concretely in H-campaign's sketch (a stepper-driven `campaign_number`, grounded in the verified `campaign` card bucket) rather than deferred to a vague "later"; "what stats are worth showing" → H-stats' sketch lists concrete fields, all derivable from H-core's own record with no new data source; "what sharing means with no keyboard" → H-share's sketch gives three concrete, twin-appropriate answers (web native, firmware fallback available today, firmware self-serve via QR) rather than one hand-wave. The FIRST sub-project (H-core) is fully actionable — three tasks, each with complete test files and complete implementation code, matching `docs/superpowers/plans/2026-07-24-quest-card-modal.md`'s own level of detail; the other three are interfaces + dependencies only, per the brief.

**Grounded, not invented:** every fact in Context was checked against the actual repository state this session — `quest_history`'s cap and its existing last-8 display convention (grep + read), the `campaign` bucket's real contents from the generated corpus (33/349 files, one inspected in full), both twins' actual persistence code, and the real vertical-space math in `ui/screen_settings.py` that determined *where* the History tile could go without restructuring anything (and the pre-existing web/firmware DEVICE-row divergence that math surfaced, called out rather than silently papered over).

**Placeholder scan:** Tasks 1–3 each carry a complete, runnable test file and complete implementation code, not sketches — including the one thin-I/O task (Task 2) that has no host-testable seam, which is stated explicitly as such (matching `quest_catalog.py`'s own documented convention) rather than faked with a hollow test.

**Type consistency:** `summarize_game(game, now)`'s return shape is defined once (Task 1) and consumed identically by Task 2's `end_game` hook and Task 3's `HistoryModal` rendering; the sketched H-stats/H-campaign/H-share sections all consume that same shape without proposing a different one.

**Cross-twin:** every task is web-first-then-firmware; Task 3 explicitly documents the one place the twins have already silently diverged (web's Settings has an About tile firmware lacks) so the new History tile lands correctly on each rather than assuming symmetry that doesn't hold.
