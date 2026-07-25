# Bottom Toasts + Auto-Change Animation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the action-window / reminder toast from the top of the screen to the bottom, rising over the next view's primary CTA; and make automatically-applied value changes (round-end threat +1, placed progress) *visible* by animating them into place **after** the next view renders, instead of arriving silently pre-applied.

**Architecture:** Both halves reuse machinery that already exists. The toast is an overlay drawn by `ScreenPlay._draw_notif` with a countdown pie animated per tick via `partial_update` — this plan re-anchors that overlay to the bottom band and adds a short rise-in. The change animation borrows the same trick: the model records *pending visual deltas* when it auto-adjusts a value, the screen draws the **old** value on first paint, and the main loop then steps each delta to its new value, repainting only that cell's rectangle.

**Tech Stack:** ES modules (web, Canvas) + MicroPython (firmware); pytest + the scene layout linter.

**Context:** From TODO.md "Ideas": *"Action Window toasts should come up from the bottom, (over the next view's main CTA). Any auto-adjusted value changes (like threat or placed progress) should happen via animation after the next view renders, so its clear what changed."*

## Verified current behavior (do not re-derive)

- **The toast already exists and already animates.** `ScreenPlay._draw_notif` (`ui/screen_play.py:288`) draws a bevel overlay at **`HEADER_H + 2`** (top of the content area), with a left colour edge, optional icon, wrapped lines, a countdown pie at its right, and a `("notif_dismiss",)` button covering it. It stores `self.notif_pie = (cx, cy, r)`.
- **The per-tick animation precedent is `main.py:198-204`:** each tick the loop recomputes `play.notif_frac = notif_t / NOTIF_TICKS`, redraws only the pie via `draw_notif_pie`, and calls `hw.partial_update(cx - r - 2, cy - r - 2, 2*r + 4, 2*r + 4)` — **no full redraw**. This proves cheap animation is viable on device and is the pattern to copy.
- Toast state lives on the screen: `notif`, `notif_frac`, `notif_pie`, `notif_edge` (`ui/screen_play.py:48-51`); the loop owns `notif_t` / `NOTIF_TICKS` and a `screens["play"].toast` override (`main.py:168-186`, mirrored in `docs/js/main.js:115,306-320`).
- Layout constants (`ui/screen_play.py:19-23`, `docs/js/screen_play.js:13-17`): `HEADER_H`, `ZONE_TOP`, `CONTENT_Y = 150`, **`CTA_Y = 410`, `CTA_H = 58`**, `MARGIN = 8`.
- Auto-adjusting call sites: `end_round`/`endRound` (each living player's `threat_per_round`), `place_progress`/`placeProgress` (location/quest/side-quest progress), and `resolve_quest`'s failure branch (threat to all).
- The web loop is event-driven (`setInterval` tick + `pointerdown`); the firmware loop is blocking (`while True`, `time.sleep(0.02)`, explicit `hw.update()` / `hw.partial_update`).
- The layout linter inspects **one drawn frame** per scene and enforces ≥24px targets, on-screen bounds, and no text collisions.

## Global Constraints

- **Two twins in lockstep** (Iron rule #1): web `docs/js/` first, then firmware — identical layout, ids, timing constants.
- **`python3 -m pytest tests/` stays green** (Iron rule #3) including the layout linter.
- **Touch targets ≥ 24px**; everything within 480×480; no text collisions; **ASCII-only** drawn strings.
- **Animation must never block input.** The firmware loop must keep polling touch between animation steps; a tap during an animation **completes it immediately** (snap to final) and is then handled normally.
- **Animation is cosmetic only.** The model is already at its final value; animation only affects what is *drawn*. A reload, a redraw, or a skipped frame must always converge on the true value — never let a pending animation be the source of truth.
- **Bounded cost.** Reuse the `partial_update`-one-region approach; never full-redraw per frame. Cap total animation duration (see Task 2) so it cannot delay play.
- Old saves must load unchanged: any new model field defaults empty and is not required.

## File structure

- `ui/screen_play.py` + `docs/js/screen_play.js` — toast re-anchored to the bottom band with a rise-in; cell-level draw helpers reused for animated repaints.
- `main.py` + `docs/js/main.js` — the rise-in tick, and the pending-change animation driver.
- `gamestate.py` + `docs/js/gamestate.js` — `pending_visual` queue populated by the auto-adjusting call sites.
- `tests/scenes.py` — scenes for the bottom toast (mid-rise and settled) and a mid-animation frame.
- `tests/test_pending_visual.py`, `tests/test_screen_play.py` — model + draw tests.

---

### Task 1: Toast rises from the bottom, over the CTA

**Files:**
- Modify: `docs/js/screen_play.js` (`_drawNotif`), then `ui/screen_play.py` (`_draw_notif`)
- Modify: `main.py`, `docs/js/main.js` (rise-in tick)
- Modify: `tests/scenes.py`
- Test: `tests/test_screen_play.py` (extend)

**Interfaces:**
- Produces: `ScreenPlay.notif_rise` / `notifRise` — 0.0 (fully off-screen below) → 1.0 (fully risen). Default `1.0` so any caller that does not animate still gets a correctly-placed toast.
- The toast's settled top edge is `CTA_Y - 6 - th` where `th` is the measured toast height, i.e. it sits **over the CTA band**, bottom-aligned to just above `CTA_Y + CTA_H`. Concretely: settled rect = `(MARGIN, CTA_Y - 6 - th, 480 - 2*MARGIN, th)`; while rising, the same rect is offset down by `(1 - rise) * (th + 12)`.
- `notif_pie` continues to be published for the existing per-tick pie repaint, recomputed for the new position.
- The dismiss button follows the drawn rect (so it is never off-screen mid-rise) and keeps id `("notif_dismiss",)`.

- [ ] **Step 1: Write the failing test** — add to `tests/test_screen_play.py` (follow that file's existing construction of `FakeHardware`/`Palette`/`GameState`):

```python
def _notif_rect(hw):
    """The toast's bevel rect: the widest full-width rect below CONTENT_Y."""
    from ui.screen_play import MARGIN
    cands = [c for c in hw.display.calls
             if c[0] == "rect" and c[1] == MARGIN and c[3] == 480 - 2 * MARGIN]
    return max(cands, key=lambda c: c[2])          # lowest y wins ties by area


def test_toast_sits_over_the_cta_when_settled():
    from ui.screen_play import CTA_Y
    g = _play_game()
    s = ScreenPlay()
    s.notif = [("THREAT", "Round end: +1 threat to all", "amber")]
    s.notif_rise = 1.0
    hw = _draw(s, g)
    _, x, y, w, h, _pen = _notif_rect(hw)
    assert y + h > CTA_Y            # overlaps the CTA band
    assert y + h <= 480             # stays on screen


def test_toast_is_lower_while_rising():
    g = _play_game()
    s = ScreenPlay()
    s.notif = [("THREAT", "Round end: +1 threat to all", "amber")]
    s.notif_rise = 1.0
    settled = _notif_rect(_draw(s, g))[2]
    s.notif_rise = 0.4
    rising = _notif_rect(_draw(s, g))[2]
    assert rising > settled         # further down the screen mid-rise


def test_dismiss_button_tracks_the_toast_and_stays_on_screen():
    g = _play_game()
    s = ScreenPlay()
    s.notif = [("THREAT", "Round end: +1 threat to all", "amber")]
    s.notif_rise = 0.5
    _draw(s, g)
    b = next(b for b in s.buttons if b.id[0] == "notif_dismiss")
    assert b.y >= 0 and b.y + b.h <= 480
    assert b.w >= 24 and b.h >= 24
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_screen_play.py -q` → the toast is still drawn at `HEADER_H + 2`, so `test_toast_sits_over_the_cta_when_settled` fails.

- [ ] **Step 3: Implement in `docs/js/screen_play.js`** — keep all existing content logic (entries normalisation, icon, wrapping, colour edge, pie, dismiss button); change only the anchor: compute `th` as today, then `const y0 = CTA_Y - 6 - th + (1 - this.notifRise) * (th + 12);` and use `y0` everywhere `HEADER_H + 2` was used (bevel, colour edge, icon, text baseline, pie centre, dismiss button). Clamp so the rect never leaves the screen.

- [ ] **Step 4: Mirror in `ui/screen_play.py`** (`_draw_notif`), including `self.notif_pie = (cx, cy, r)` at the new centre.

- [ ] **Step 5: Drive the rise in both loops.** Where `notif_t = NOTIF_TICKS` is set (`main.py:180,186`; `docs/js/main.js:314,320`), also set `notif_rise = 0.0`. Each tick, while `notif_rise < 1.0`, advance it by `1 / RISE_TICKS` (`RISE_TICKS = 6`, ~120 ms at the 20 ms tick), redraw, and — on firmware — `hw.partial_update` the toast band only (`MARGIN, CTA_Y - 6 - th_max, 480 - 2*MARGIN, th_max + CTA_H + 12`), then continue with the existing pie repaint once risen. Dismissal may simply hide (no fall-out animation) — see *If the user prefers*.

- [ ] **Step 6: Scenes + render** — add `play_toast_settled` and `play_toast_rising` to `tests/scenes.py`; `python3 -m pytest tests/test_layout.py -q` → PASS. Then `python3 tools/preview.py play_toast_settled /tmp/t1.png` and `play_toast_rising` — confirm the toast reads as covering the CTA, the pie is visible, and nothing collides.

- [ ] **Step 7: Full suite + commit.**

---

### Task 2: Animate auto-applied value changes after the next render

**Files:**
- Modify: `gamestate.py`, `docs/js/gamestate.js` (pending queue)
- Modify: `ui/screen_play.py`, `docs/js/screen_play.js` (draw a cell at an overridden value; publish cell rects)
- Modify: `main.py`, `docs/js/main.js` (animation driver)
- Test: `tests/test_pending_visual.py` (new)

**Interfaces:**
- Produces: `GameState.pending_visual` — a list of `{"kind": str, "key": <int|str>, "from": int, "to": int}`. `kind` ∈ `"threat"` (key = player index) and `"progress"` (key ∈ `"quest"`, `"location"`, `"side:<i>"`). Appended by the auto-adjusting paths only (`end_round`, `place_progress`, `resolve_quest`'s failure branch) — **never** by direct user edits, which need no explanation.
- Produces: `GameState.take_pending_visual()` / `takePendingVisual()` — returns the list and clears it (the driver owns it once taken).
- Produces: `ScreenPlay.visual_override` / `visualOverride` — a dict consulted when drawing a value cell: `{("threat", 0): 27, ...}`. Empty by default, so every existing draw path is unchanged.
- Produces: `ScreenPlay.cell_rect(kind, key)` / `cellRect(...)` — the `(x, y, w, h)` of that value cell, so the driver can `partial_update` exactly that region. Returns `None` for an unknown cell.
- **Serialization:** `pending_visual` is **not** serialized — it is ephemeral presentation state; a reload simply shows final values. State this in the code comment.

- [ ] **Step 1: Write the failing test** — `tests/test_pending_visual.py`:

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gamestate


def _g():
    g = gamestate.GameState(2, 25)
    return g


def test_end_round_records_threat_deltas():
    g = _g()
    before = [p.threat for p in g.players]
    g.end_round()
    pend = g.take_pending_visual()
    assert len(pend) == len(g.players)
    for i, e in enumerate(pend):
        assert e["kind"] == "threat" and e["key"] == i
        assert e["from"] == before[i] and e["to"] == g.players[i].threat
        assert e["to"] != e["from"]


def test_take_clears_the_queue():
    g = _g()
    g.end_round()
    assert g.take_pending_visual()
    assert g.take_pending_visual() == []


def test_direct_user_edits_do_not_queue():
    g = _g()
    g.adjust_threat(0, +3)
    assert g.take_pending_visual() == []


def test_pending_visual_is_not_serialized():
    g = _g()
    g.end_round()
    assert "pending_visual" not in g.to_dict()
    g2 = gamestate.GameState.from_dict(g.to_dict())
    assert g2.take_pending_visual() == []


def test_place_progress_records_progress_deltas():
    g = _g()
    g.quest["points"] = 10
    g.take_pending_visual()
    g.place_progress({"quest": 3})
    pend = g.take_pending_visual()
    assert any(e["kind"] == "progress" and e["key"] == "quest"
               and e["to"] - e["from"] == 3 for e in pend)
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_pending_visual.py -q` → `AttributeError: ... 'take_pending_visual'`.

- [ ] **Step 3: Implement the model** in `gamestate.py`: `self.pending_visual = []` in the constructor (with the "ephemeral, not serialized" comment), a private `_queue_visual(kind, key, frm, to)` that appends only when `frm != to`, calls at the three auto-adjust sites, and `take_pending_visual()`. Mirror in `docs/js/gamestate.js`.

- [ ] **Step 4: Implement the draw hook.** In both screens, where a value cell is rendered (the players-zone threat token and the progress-zone tokens), look up `visual_override.get((kind, key), <real value>)` before drawing, and record that cell's rect so `cell_rect` can return it. Default-empty override means **zero behavior change** when nothing is animating — assert that with an existing-scene render.

- [ ] **Step 5: Implement the driver in both loops.** After the next view has been drawn once (this is the "after the next view renders" requirement — take the queue on the *first* tick following a view change, not during it):
  1. `pend = game.take_pending_visual()`; if empty, nothing to do.
  2. Seed `visual_override[(kind, key)] = e["from"]` for each entry and draw once (the user sees the *old* values).
  3. Over `STEP_TICKS = 8` ticks (~160 ms), advance each override toward `to` (linear, integer steps; always land exactly on `to`), and each tick repaint **only** the affected cells via `cell_rect` + `hw.partial_update` (web: redraw those rects on the canvas).
  4. Clear the overrides and mark dirty so the next full draw is authoritative.
  5. **Any touch during the animation** finishes it immediately (set every override to `to`, clear, redraw) and then processes the tap normally.

- [ ] **Step 6: Scenes + render** — add `play_threat_animating` (a scene with `visual_override` seeded mid-way) so the linter covers a mid-animation frame; `python3 -m pytest tests/test_layout.py -q` → PASS. Render it and confirm the token reads correctly at an intermediate value.

- [ ] **Step 7: Verify on both twins.** Browser: play to a round end and watch the threat tokens step up after the new view paints; confirm no console errors and that tapping mid-animation snaps and responds. Firmware: this is main-session-only — note in the report that on-device verification is deferred to the next device deploy, and confirm the tick math against `NOTIF_TICKS`/`RISE_TICKS` timing.

- [ ] **Step 8: Full suite + commit.**

---

## If the user prefers something else

- **Firmware animation fidelity.** The default steps integer values over ~160 ms with per-cell `partial_update`, mirroring the proven `draw_notif_pie` approach. *If it proves too slow on device*, degrade to a **single highlight flash** of the changed cell (draw the final value with `pal.gold` fill for ~150 ms, then normal) — same queue, same `cell_rect`, only the driver's inner loop changes. Both are honest about what the device can do; the flash is the safe fallback.
- **Toast dismissal.** Default: dismiss hides immediately (only the rise-in is animated). *If the user wants symmetry*, animate `notif_rise` back to 0 over `RISE_TICKS` before clearing — same tick code in reverse.
- **What animates.** Default covers round-end threat and placed progress (the two the user named). *If the user also wants quest-failure threat and stage advances*, they queue at the same call sites with no driver change.

## Self-Review

**Spec coverage:** toast rising from the bottom over the next view's main CTA → Task 1 (anchored to `CTA_Y`, with `notif_rise`); auto-adjusted value changes animating *after* the next view renders → Task 2 (queue taken on the first tick following the view change, old values drawn first, then stepped). Both reuse the existing toast/pie/`partial_update` machinery rather than inventing a parallel system.

**Placeholder scan:** both tasks carry complete test files, exact rect math (`CTA_Y - 6 - th`), named timing constants (`RISE_TICKS = 6`, `STEP_TICKS = 8`), and a concrete degraded fallback for the device rather than an unqualified "animate it".

**Type consistency:** `pending_visual` entries `{kind, key, from, to}` are produced in Task 2 Step 3 and consumed by the driver in Step 5 with the same keys; `visual_override` is keyed `(kind, key)` in both the draw hook and the driver; `cell_rect(kind, key)` takes the same pair.
