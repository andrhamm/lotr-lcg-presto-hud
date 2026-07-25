# Game Log Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the game log a real timeline — every entry carries a full timestamp, the view reads like a terminal (oldest at top, newest at the bottom, anchored to the latest), and four right-edge buttons where a scrollbar would sit give jump-to-oldest / up / down / jump-to-latest.

**Architecture:** Entries already store a monotonic session time (`t`, ms). Add a one-time wall-clock anchor (`started_at`, epoch seconds) captured when the game begins, so any entry's absolute time is `started_at + t/1000` — with a clean fallback to elapsed-only display when the device has no clock set. The log screen switches from newest-first pages to a bottom-anchored window with an explicit scroll offset.

**Tech Stack:** ES modules (web, Canvas) + MicroPython (firmware); pytest + the scene layout linter.

**Context:** From TODO.md "Ideas": *"Game log data should be logged with full timestamp, log view should at least show the basic date and time with each entry. Logs should be latest at the bottom, like a terminal, need ability to scroll up and down and jump to oldest / latest (4 buttons on right side of screen where a scrollbar would normally be expected)."*

## Verified current behavior (do not re-derive)

- `GameState.log_event(text)` (`gamestate.py:199`) appends `{"seq", "round", "step", "text", "t"}` where `t = self._now()` → `self.clock()` or `None`.
- Injected clocks: web `performance.now()` (`docs/js/main.js:19`), firmware `time.ticks_ms()` (`main.py:132`). **Both are session-relative, not wall-clock**, and reset every boot/reload.
- The firmware already knows the RTC may be unset: `load_saved()` (`main.py:65-67`) formats `saved_at` with `time.localtime(t)` and treats `lt[0] < 2024` as "RTC not set → wall time unknown". Reuse that exact test.
- `ScreenLog` (`docs/js/screens_other.js:72`) and `ui/screen_log.py` today: `PER_PAGE = 13`, `ROW_H = 26`, entries **reversed** (newest first), Older/Newer paging, row = `R<round>.<step>` + optional `m:ss` + truncated text.
- The layout linter (`tests/test_layout.py`) enforces ≥24px touch targets, on-screen bounds, and no text collisions over every scene in `tests/scenes.py`.

## Global Constraints

- **Two twins in lockstep** (Iron rule #1): web `docs/js/` first, then the firmware mirror — identical layout, ids, behavior.
- **`python3 -m pytest tests/` stays green** (Iron rule #3) including the layout linter.
- **Touch targets ≥ 24px** each dimension, everything within 480×480, no text collisions.
- **Backward compatible:** saves written before this change have entries without the new fields and no `started_at`. Loading them must work and display sensibly (elapsed-only), never crash.
- **ASCII only** in any drawn string — the device bitmap font's glyph table covers printable ASCII only (82 entries in `tests/fake_hardware.py`).
- **No new clock dependency on device.** Do not add NTP in this plan; use the RTC when it happens to be set and degrade otherwise.
- `t` may be `None` (no clock injected, e.g. host tests) — every display path must tolerate it.

## File structure

- `gamestate.py` + `docs/js/gamestate.js` — `started_at` field, capture, serialization.
- `ui/screen_log.py` + `docs/js/screens_other.js` (`ScreenLog`) — terminal ordering, scroll offset, the 4 buttons, timestamped rows.
- `tests/scenes.py` — log scenes (bottom-anchored, scrolled-up, empty).
- `tests/test_gamestate_log.py` (new) — timestamp model tests; `tests/test_layout.py` picks the scenes up automatically.

---

### Task 1: Wall-clock anchor in the model

**Files:**
- Modify: `gamestate.py` (constructor near `self.clock`, `to_dict`, `from_dict`), `docs/js/gamestate.js` (mirror)
- Test: `tests/test_gamestate_log.py` (new)

**Interfaces:**
- Produces: `GameState.started_at` — epoch **seconds** (int) or `None`. Set once, when the first log entry is written and the value is still `None`, from an injected `wall_clock` callable (`self.wall_clock() if self.wall_clock else None`), so pure-logic tests stay deterministic.
- Produces: `GameState.wall_clock` — injected like `clock` (default `None`).
- Produces: `entry_time(entry, started_at)` / `entryTime(entry, startedAt)` — module-level helper returning `(epoch_seconds | None, elapsed_ms | None)` for one entry: `epoch = started_at + entry["t"] // 1000` when both are present, else `None`; `elapsed = entry["t"]`.

- [ ] **Step 1: Write the failing test** — `tests/test_gamestate_log.py`:

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gamestate


def _g():
    g = gamestate.GameState(2, 25)
    ticks = [0]
    g.clock = lambda: ticks[0]
    g.wall_clock = lambda: 1_700_000_000
    return g, ticks


def test_started_at_captured_once_on_first_entry():
    g, ticks = _g()
    assert g.started_at is None
    g.log_event("first")
    assert g.started_at == 1_700_000_000
    g.wall_clock = lambda: 9_999_999_999      # must not be re-read
    ticks[0] = 5000
    g.log_event("second")
    assert g.started_at == 1_700_000_000


def test_entry_time_combines_anchor_and_session_ms():
    g, ticks = _g()
    g.log_event("a")
    ticks[0] = 65_000
    g.log_event("b")
    epoch, elapsed = gamestate.entry_time(g.log[-1], g.started_at)
    assert elapsed == 65_000
    assert epoch == 1_700_000_000 + 65


def test_entry_time_without_anchor_is_elapsed_only():
    g = gamestate.GameState(2, 25)
    g.clock = lambda: 3000
    g.log_event("a")                       # no wall_clock injected
    assert g.started_at is None
    epoch, elapsed = gamestate.entry_time(g.log[-1], g.started_at)
    assert epoch is None and elapsed == 3000


def test_entry_time_tolerates_missing_t():
    epoch, elapsed = gamestate.entry_time({"text": "x"}, 1_700_000_000)
    assert epoch is None and elapsed is None


def test_started_at_round_trips_and_old_saves_default_none():
    g, _ = _g()
    g.log_event("a")
    g2 = gamestate.GameState.from_dict(g.to_dict())
    assert g2.started_at == 1_700_000_000
    old = g.to_dict()
    del old["started_at"]                  # a save written before this change
    assert gamestate.GameState.from_dict(old).started_at is None
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_gamestate_log.py -q` → `AttributeError: ... 'started_at'`.

- [ ] **Step 3: Implement in `gamestate.py`.** Constructor, beside `self.clock = None`:
```python
        self.wall_clock = None       # epoch-seconds source injected by main
        self.started_at = None       # epoch seconds of the first logged event
```
In `log_event`, before appending:
```python
        if self.started_at is None and self.wall_clock:
            self.started_at = self.wall_clock()
```
Module level:
```python
def entry_time(entry, started_at):
    """(epoch_seconds, elapsed_ms) for one log entry. epoch is None unless the
    game captured a wall-clock anchor (the device RTC is often unset)."""
    t = entry.get("t")
    if t is None:
        return None, None
    if started_at is None:
        return None, t
    return started_at + t // 1000, t
```
Serialization: add `"started_at": self.started_at` to `to_dict`, and `g.started_at = d.get("started_at")` in `from_dict`.

- [ ] **Step 4: Run tests to verify they pass** — `python3 -m pytest tests/test_gamestate_log.py -q` → 5 passed.

- [ ] **Step 5: Mirror in `docs/js/gamestate.js`** — `this.wall_clock = null; this.started_at = null;`, the same capture inside `logEvent`, an exported `entryTime(entry, startedAt)` returning `[epoch, elapsed]`, `started_at: this.started_at` in `toDict`, `g.started_at = d.started_at ?? null` in `fromDict`.

- [ ] **Step 6: Inject the wall clock in both mains.** Web (`docs/js/main.js`, everywhere `game.clock = clock` appears): `game.wall_clock = () => Math.floor(Date.now() / 1000);`. Firmware (`main.py`, beside `game.clock = clock`):
```python
    def _wall():
        t = time.time()
        lt = time.localtime(t)
        return int(t) if lt[0] >= 2024 else None      # RTC unset -> no anchor
    game.wall_clock = _wall
```
(The `lt[0] >= 2024` test mirrors `load_saved()`'s existing RTC check at `main.py:65-67`.)

- [ ] **Step 7: Full suite + commit.** `python3 -m pytest tests/ -q`; `git add -A && git commit --no-gpg-sign -m "feat(log): wall-clock anchor for log entries"`.

---

### Task 2: Terminal-order log view with a scroll window

**Files:**
- Modify: `docs/js/screens_other.js` (`ScreenLog`), then `ui/screen_log.py`
- Modify: `tests/scenes.py`
- Test: `tests/test_screen_log.py` (new)

**Interfaces:**
- Consumes: `entry_time`/`entryTime` from Task 1.
- Produces: `ScreenLog` with `offset` (0 = pinned to the newest entry; positive = scrolled back that many rows) replacing `page`. Button ids: `["oldest"]`, `["up"]`, `["down"]`, `["latest"]`. `onButton`/`on_button` returns `"redraw"` for all four (they are view state, not game state — do not autosave on a scroll).
- Rows render **oldest→newest top-to-bottom**; when `offset == 0` the newest entry sits on the last visible row.

**Layout** (480×480, header is `HEADER_H`):
- Content column: x 12 → 428 (a 44px right gutter for the button rail).
- Rows: `ROW_H = 26`, first row at `HEADER_H + 8`; `VISIBLE = 13`.
- Button rail at x 432, w 44 — four buttons stacked, each 44×44 with 8px gaps, vertically centred in the content area: **⇱ oldest**, **▲ up**, **▼ down**, **⇲ latest** (draw these as triangle glyphs via `d.triangle`, plus a bar for the jump variants — **no non-ASCII text glyphs**).
- Row content: `R<round>.<step>` (`pal.dim`), then the time, then the message truncated to the remaining width.
  - With an epoch: `HH:MM` (and the date on the **first row of each day**, as a full-width separator line `YYYY-MM-DD` in `pal.dim`, so the date is present without repeating on every row).
  - Without an epoch: `m:ss` elapsed, as today.
- Disabled state: at `offset == 0`, **down** and **latest** draw dim and are inert; at the top, **up** and **oldest** likewise. Buttons remain present (stable layout) and still satisfy ≥24px.

- [ ] **Step 1: Write the failing test** — `tests/test_screen_log.py`:

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gamestate
from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.screen_log import ScreenLog, VISIBLE


def _game(n):
    g = gamestate.GameState(2, 25)
    ticks = [0]
    g.clock = lambda: ticks[0]
    g.wall_clock = lambda: 1_700_000_000
    for i in range(n):
        ticks[0] = i * 1000
        g.log_event("event %d" % i)
    return g


def _draw(s, g):
    hw = FakeHardware()
    s.draw(hw, g, Palette(hw.display))
    return hw


def _texts(hw):
    return [c[1] for c in hw.display.calls if c[0] == "text"]


def test_newest_entry_is_visible_by_default():
    g = _game(40)
    s = ScreenLog()
    hw = _draw(s, g)
    assert any("event 39" in t for t in _texts(hw))
    assert not any("event 0" in t for t in _texts(hw))


def test_rows_are_oldest_to_newest_top_down():
    g = _game(40)
    s = ScreenLog()
    hw = _draw(s, g)
    ys = {}
    for c in hw.display.calls:
        if c[0] == "text" and c[1].startswith("event "):
            ys[c[1]] = c[3]
    assert ys["event 38"] < ys["event 39"]      # older sits above newer


def test_up_scrolls_back_and_latest_returns():
    g = _game(40)
    s = ScreenLog()
    _draw(s, g)
    assert s.on_button(next(b for b in s.buttons if b.id[0] == "up")) == "redraw"
    assert s.offset > 0
    s.on_button(next(b for b in s.buttons if b.id[0] == "latest"))
    assert s.offset == 0


def test_oldest_jumps_to_the_first_entry():
    g = _game(40)
    s = ScreenLog()
    _draw(s, g)
    s.on_button(next(b for b in s.buttons if b.id[0] == "oldest"))
    hw = _draw(s, g)
    assert any("event 0" in t for t in _texts(hw))


def test_offset_clamps_at_both_ends():
    g = _game(40)
    s = ScreenLog()
    _draw(s, g)
    for _ in range(50):
        s.on_button(next(b for b in s.buttons if b.id[0] == "up"))
    _draw(s, g)
    assert s.offset == len(g.log) - VISIBLE
    for _ in range(50):
        s.on_button(next(b for b in s.buttons if b.id[0] == "down"))
    assert s.offset == 0


def test_short_log_renders_without_scrolling():
    g = _game(3)
    s = ScreenLog()
    hw = _draw(s, g)                     # must not raise
    assert any("event 0" in t for t in _texts(hw))
    assert s.offset == 0
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_screen_log.py -q` → `ImportError: cannot import name 'VISIBLE'`.

- [ ] **Step 3: Implement the web `ScreenLog`** in `docs/js/screens_other.js` per the layout above: replace `page` with `offset`, stop reversing the entry list, compute the visible window as `entries.slice(start, start + VISIBLE)` where `start = max(0, len - VISIBLE - offset)`, draw the day separator when the date changes between rows, and draw the four rail buttons with their disabled states.

- [ ] **Step 4: Mirror in `ui/screen_log.py`.** Remember the firmware helpers need the measure callback: `truncate_text(text, 1, width, d.measure_text)`. Format times with `time.localtime(epoch)` guarded by the same `lt[0] >= 2024` check.

- [ ] **Step 5: Run tests to verify they pass** — `python3 -m pytest tests/test_screen_log.py -q` → 6 passed.

- [ ] **Step 6: Update/add scenes** in `tests/scenes.py`: keep `log` (bottom-anchored, ~40 entries, wall clock set), add `log_scrolled` (offset mid-way, so both jump buttons are active) and `log_no_clock` (entries with no wall-clock anchor → elapsed display). Run `python3 -m pytest tests/test_layout.py -q` → PASS.

- [ ] **Step 7: Render and inspect** — `python3 tools/preview.py log /tmp/log.png`, `log_scrolled`, `log_no_clock`. Check: newest row sits at the bottom, the rail reads as four distinct buttons with obvious disabled states, timestamps do not crowd the message, the day separator appears once per day. Fix anything cramped.

- [ ] **Step 8: Full suite + commit.** `python3 -m pytest tests/ -q`; commit.

---

## If the user prefers something else

- **Date placement.** The default puts the date on a separator row when the day changes, keeping per-row noise low. *If the user prefers a date on every row*, drop the separator and render `MM-DD HH:MM` in the time column — this costs roughly 40px of message width, so re-check truncation and the linter.
- **Scroll granularity.** Up/down move by **one row** (precise, matches a terminal). *If the user prefers page-at-a-time*, change the step to `VISIBLE - 1` (keeping one row of overlap for context); the clamping tests stay valid with the step constant swapped.
- **Wall clock on device.** This plan uses the RTC only when it is already set. *If the user wants real timestamps guaranteed on device*, that needs an NTP sync at boot (WiFi-dependent) — a separate task; the model here already stores the anchor, so only the injection in `main.py` would change.

## Self-Review

**Spec coverage:** full timestamp on every entry → Task 1 (`started_at` anchor + `entry_time`); date and time shown per entry → Task 2 (time column + day separator); latest-at-bottom terminal order → Task 2 (unreversed list, bottom-anchored window); scroll up/down and jump to oldest/latest via 4 right-edge buttons where a scrollbar would be → Task 2 (the 44px rail). Backward compatibility with existing saves and with a device whose RTC is unset is handled explicitly in both tasks.

**Placeholder scan:** both tasks carry complete test files and real implementation code for the model; the view task specifies exact coordinates, row/window math, and disabled-state behavior rather than describing them loosely.

**Type consistency:** `entry_time(entry, started_at) -> (epoch|None, elapsed|None)` is defined in Task 1 and consumed by name in Task 2; `offset`/`VISIBLE` and the four button ids (`oldest`/`up`/`down`/`latest`) are used identically in Task 2's tests and layout.
