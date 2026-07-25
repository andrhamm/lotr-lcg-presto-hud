# Phase Tip Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the per-phase instructional panels on the play screen (the `note_panel`/`notePanel`-driven guidance text shown on `resource_planning`, `quest_commit`, `refresh`, and the encounter/combat views) so they read as a deliberate, well-proportioned focal element that uses the vertical space the stats redesign freed up, instead of a thin strip glued under the zones with a large dead gap above the CTA.

**Architecture:** Two additive changes to the shared `note_panel`/`notePanel` primitive (`ui/widgets.py` / `docs/js/ui.js`) — a richer optional chrome (circular icon badge + small kicker label) and a pure height-measurement function — plus a new `center_band_y`/`centerBandY` placement helper that vertically centers a tip block within the space between the zones and the CTA. `screen_play.py`/`.js`'s plain-instruction call sites (resource_planning, quest_commit, refresh, the encounter/combat catch-all) adopt both the new chrome and the new placement. The three hand-rolled "pipe box" tip variants (sailing-enabled, staging, resolution fail/tie) get **only** the placement fix — their bespoke inline-icon content is untouched. The `quest_setup` ornate scroll box is explicitly out of scope.

**Tech Stack:** unchanged — Canvas ES modules (web) + MicroPython/PicoGraphics (firmware); pytest + the scene layout linter; `tools/preview.py` for device-faithful rendering.

**Context:** TODO board (Ideas): *"not in love with the placement or design of the tips... the stats redesign is much more compact than the initial design so the tips can be revamped to use the recovered space more effectively."* This is about the everyday phase-guidance panels in the main play flow (`docs/js/screen_play.js` / `ui/screen_play.py`), **not** the unrelated, already-planned per-stage strategy "Tips" button inside the Quest Card modal (`docs/superpowers/plans/2026-07-24-stage-tips.md`) — that is community strategy notes surfaced through a completely different modal and pipeline. Read `docs/js/screen_play.js` + `ui/screen_play.py` in full before starting; every view branch is touched by at least one task below.

**Verified current geometry** (both twins, `screen_play.js`/`.py`): `HEADER_H = 40`, `ZONE_TOP = HEADER_H + 6 = 46`, the players/progress zones occupy `y=44..136` (90px tall buttons), `CONTENT_Y = 150`, `CTA_Y = 410`, `CTA_H = 58`. That leaves a `150..396` band (246px) between the zones and the CTA for tip content — most existing tip panels only fill 40-90px of it, hugging the top and leaving 150px+ of dead space, which is the "recovered space" the TODO note refers to.

## Global Constraints

- **Two twins in lockstep** (Iron rule #1): implement the JS first (per CLAUDE.md), then mirror line-for-line in Python — same constants, same branching, same pixel math. There is no JS test runner in this repo; `python3 -m pytest tests/` (Python + the layout linter) is the enforced correctness gate, so every TDD step below targets Python. The web side is verified by close correspondence to the Python plus a manual browser look (Task 2's last step).
- **`python3 -m pytest tests/` stays green** (Iron rule #3), including the layout linter (`tests/test_layout.py`: no out-of-bounds draws, no text collisions, ≥24px touch targets).
- **Backward compatible:** `note_panel`/`notePanel` is also called from `ui/screen_quest.py` (`ScenarioOptionsScreen`) and its JS mirror in `docs/js/screens_other.js`. Those call sites pass only the existing positional args — the new `kicker`/`badge`/`min_h` keyword args must default to today's exact behavior (verified by a dedicated regression test in Task 1) so those screens render byte-identical to before.
- **480×480 canvas, ≥24px touch targets, no text collisions** — linter-enforced.
- **Device-faithful:** every touched view gets a preview render check (`python3 tools/preview.py play_<scene> /tmp/<name>.png`) before the task is considered done — this is a visual redesign; eyeballing the PNG is not optional.
- **Out of scope, explicitly:** the `quest_setup` view's double-gold-frame scroll tip (different semantic — printed card text the player must resolve, not phase guidance) and the `setup_game` view's top-anchored `SETUP_TIP` panel (a distinct pre-round screen with its own fully-used layout: stepper + sailing toggle below it, no dead gap to reclaim). Neither is touched by this plan.

## File structure

- `ui/widgets.py` / `docs/js/ui.js` — extend `note_panel`/`notePanel` with `kicker`, `badge`, `min_h`; add `note_panel_height`/`notePanelHeight` (pure measurement) and `center_band_y`/`centerBandY` (placement helper).
- `ui/screen_play.py` / `docs/js/screen_play.js` — new `_tip`/`_tip` helper method; every plain-instruction call site (`resource_planning`, `quest_commit`, `refresh`, the encounter/combat catch-all) switches to it; the 3 hand-rolled pipe-box views (`quest_sailing` on, `quest_staging`, `quest_resolution` fail/tie) get their `ty0` centered via `center_band_y` only.
- `tests/test_note_panel.py` — new: unit tests for the widget-level changes.
- `tests/test_screen_play.py` — extended: placement assertions for the redesigned call sites.
- No new `tests/scenes.py` entries are required — every touched view already has a scene (`play_resource_planning`, `play_quest_commit[*]`, `play_quest_staging`, `play_quest_sailing`, `play_quest_resolution_fail`, `play_refresh`, `play_enc_optional`, `play_enc_checks`, `play_combat_shadow/enemy/player`); this plan re-renders those.

---

### Task 1: `note_panel`/`notePanel` chrome + measurement + centering helpers

**Files:**
- Modify: `ui/widgets.py`, `docs/js/ui.js`
- Test: `tests/test_note_panel.py` (new)

**Interfaces:**
- `note_panel_height(measure, w, text, scale=2, reserve_right=0, icon=None, kicker=None, badge=False, min_h=0) -> int` / `notePanelHeight(w, text, scale=2, reserveRight=0, icon, kicker=null, badge=false, minH=0) -> number` — pure layout pass, no drawing; mirrors `note_panel`'s own math so callers can know a panel's height *before* choosing its `y`.
- `note_panel(d, pal, x, y, w, text, scale=2, reserve_right=0, icon=None, kicker=None, badge=False, min_h=0) -> int` / `notePanel(ctx, x, y, w, text, scale=2, reserveRight=0, icon, kicker=null, badge=false, minH=0) -> number` — extends the existing signature (all new params are keyword/trailing with defaults matching today's behavior). `badge=True` swaps the plain top-left icon for a circular inset badge (disc + thin ring, the same language as the stat tokens); `kicker` prints a small caption (e.g. `"TIP"`) above the body; `min_h` stretches the panel to at least that height.
- `center_band_y(content_h, top, bottom) -> int` / `centerBandY(contentH, top, bottom) -> number` — vertically centers a `content_h`-tall block in `[top, bottom]`, clamped to `top` if the content is taller than the band.

- [ ] **Step 1: Write the failing tests** — `tests/test_note_panel.py`:

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_hardware import FakeDisplay
from ui.theme import Palette
from ui.widgets import note_panel, note_panel_height, center_band_y


def test_note_panel_height_matches_drawn_height():
    d = FakeDisplay()
    pal = Palette(d)
    h1 = note_panel_height(d.measure_text, 300, "Collect resources.", 2)
    h2 = note_panel(d, pal, 8, 100, 300, "Collect resources.", 2)
    assert h1 == h2


def test_note_panel_legacy_call_sites_unchanged():
    # ScenarioOptionsScreen (ui/screen_quest.py) calls note_panel with only
    # positional args through `scale` - this must keep rendering exactly
    # like before (plain top-left icon, no badge ring, no kicker line).
    d = FakeDisplay()
    pal = Palette(d)
    h_before = note_panel(d, pal, 16, 40, 448, ["line one", "line two"], 2)
    d2 = FakeDisplay()
    h_after = note_panel(d2, pal, 16, 40, 448, ["line one", "line two"], 2,
                          reserve_right=0, icon=None, kicker=None, badge=False, min_h=0)
    assert h_before == h_after
    assert d.calls == d2.calls


def test_note_panel_badge_and_kicker_add_height_and_draw_kicker_text():
    d = FakeDisplay()
    pal = Palette(d)
    h_plain = note_panel_height(d.measure_text, 300, "hi", 2)
    h_badge = note_panel_height(d.measure_text, 300, "hi", 2, icon=None,
                                 kicker="TIP", badge=True)
    assert h_badge > h_plain
    note_panel(d, pal, 8, 100, 300, "hi", 2, icon=None, kicker="TIP", badge=True)
    texts = [c[1] for c in d.calls if c[0] == "text"]
    assert "TIP" in texts


def test_note_panel_min_h_stretches_panel():
    d = FakeDisplay()
    h = note_panel_height(d.measure_text, 300, "hi", 2, min_h=200)
    assert h == 200


def test_note_panel_badge_icon_still_drawn_inside_badge():
    from ui import icons
    d = FakeDisplay()
    pal = Palette(d)
    note_panel(d, pal, 8, 100, 300, "hi", 2, icon=icons.PIPE, kicker="TIP", badge=True)
    # a badge draws a ring (arc_runs -> many thin 1px-tall rects) in addition
    # to the icon's own mask rows - strictly more rect calls than the legacy
    # (non-badge) path for the same icon/text.
    d2 = FakeDisplay()
    note_panel(d2, pal, 8, 100, 300, "hi", 2, icon=icons.PIPE)
    assert len(d.calls) > len(d2.calls)


def test_center_band_y_centers_and_clamps():
    assert center_band_y(50, 100, 300) == 100 + (200 - 50) // 2
    assert center_band_y(500, 100, 300) == 100   # taller than band -> clamp to top
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_note_panel.py -q` → `ImportError: cannot import name 'note_panel_height'`.

- [ ] **Step 3: Implement in `ui/widgets.py`.** Replace the existing `note_panel` with a shared-layout version plus the two new functions:

```python
def _note_panel_layout(measure, w, text, scale, reserve_right, icon, kicker, badge, min_h):
    """Shared layout math for note_panel/note_panel_height. Returns
    (h, lines, gutter, badge_r, icon) - icon is the resolved mask (PIPE if
    the caller passed None)."""
    from ui import icons as _icons
    if icon is None:
        icon = _icons.PIPE
    isz = len(icon) if icon else 0
    badge_r = isz // 2 + 9
    gutter = (badge_r * 2 + 14) if (badge and icon is not False) else \
             ((isz + 14) if icon is not False else 0)
    paras = [text] if isinstance(text, str) else list(text)
    usable = w - 16 - 12 - gutter - reserve_right
    lines = []
    for p in paras:
        lines.extend(wrap_text(p, scale, usable, measure))
    lh = 10 * scale + 6
    kicker_h = 14 if kicker else 0
    min_icon_h = (badge_r * 2 + 16) if (badge and gutter) else (isz + 14 if gutter else 0)
    h = max(kicker_h + len(lines) * lh + 16, min_icon_h, min_h)
    return h, lines, gutter, badge_r, icon


def note_panel_height(measure, w, text, scale=2, reserve_right=0, icon=None,
                       kicker=None, badge=False, min_h=0):
    """Pure measurement pass mirroring note_panel's layout math (same shape,
    minus d/pal/x/y, plus an explicit `measure` callback - typically
    `d.measure_text`), so callers can know a panel's height before picking
    where to draw it (e.g. to vertically centre it via center_band_y)."""
    h, _lines, _gutter, _badge_r, _icon = _note_panel_layout(
        measure, w, text, scale, reserve_right, icon, kicker, badge, min_h)
    return h


def note_panel(d, pal, x, y, w, text, scale=2, reserve_right=0, icon=None,
                kicker=None, badge=False, min_h=0):
    """Distinct style for phase reminder messages: dark panel, gold edge,
    muted text, and (by default) the hobbit-pipe hint medallion on the left.
    Accepts a string or list of paragraphs; each is word-wrapped to the usable
    width (minus icon gutter and reserve_right). Returns the panel height.

    badge=True swaps the plain top-left icon for a circular inset badge (the
    same disc+ring language as the stat tokens) and, with `kicker`, prints a
    small caption above the body (e.g. "TIP") - the redesigned chrome used by
    the play-screen phase tips (see screen_play.py's _tip helper). Existing
    callers that pass neither (ui/screen_quest.py's ScenarioOptionsScreen)
    render pixel-identical to before - verified in tests/test_note_panel.py."""
    h, lines, gutter, badge_r, icon = _note_panel_layout(
        d.measure_text, w, text, scale, reserve_right, icon, kicker, badge, min_h)
    d.set_pen(pal.card_hi)
    d.rectangle(x, y, w, h)
    d.set_pen(pal.border_gold)
    d.rectangle(x, y, 4, h)
    if gutter:
        from ui import icons as _icons
        if badge:
            bcx, bcy = x + 14 + badge_r, y + 14 + badge_r
            disc(d, bcx, bcy, badge_r, pal.well)
            arc_runs(d, bcx, bcy, badge_r, badge_r - 2, 0, 360, pal.border_gold)
            _icons.draw(d, icon, bcx - len(icon) // 2, bcy - len(icon) // 2, pal.gold)
        else:
            _icons.draw(d, icon, x + 10, y + 8, pal.gold)   # top-left, not centered
    ty = y + 8
    if kicker:
        text_left(d, pal, kicker, x + 12 + gutter, ty, 1, pal.gold)
        ty += 14
    lh = 10 * scale + 6
    for s in lines:
        text_left(d, pal, s, x + 12 + gutter, ty, scale, pal.muted)
        ty += lh
    return h


def center_band_y(content_h, top, bottom):
    """Vertically centre a content_h-tall block within [top, bottom];
    clamped to `top` if the content is taller than the band."""
    return top + max(0, (bottom - top - content_h) // 2)
```

  `disc` and `arc_runs` are already defined lower in this file (used by `token`/`ring`) — since `note_panel` is defined above them today, move `note_panel`/`_note_panel_layout`/`note_panel_height`/`center_band_y` to **after** `disc`/`arc_runs`/`ring` in the file (or forward-declare by keeping Python's normal call-time resolution — Python functions can reference names defined later in the module as long as they're defined by the time `note_panel` is *called*, so no reordering is strictly required; MicroPython behaves the same way). Leave the functions where `note_panel` already lives; only add the new ones directly below it.

- [ ] **Step 4: Run → PASS.** `python3 -m pytest tests/test_note_panel.py -q`.

- [ ] **Step 5: Mirror in `docs/js/ui.js`.** Replace the existing `notePanel` export with:

```js
function notePanelLayout(w, text, scale, reserveRight, icon, kicker, badge, minH) {
  const mask = icon === undefined ? icons.PIPE : icon;
  const isz = mask ? mask[0] : 0;
  const badgeR = Math.floor(isz / 2) + 9;
  const gutter = (badge && mask) ? badgeR * 2 + 14 : (mask !== false && mask ? isz + 14 : 0);
  const paras = Array.isArray(text) ? text : [text];
  const usable = w - 16 - 12 - gutter - reserveRight;
  const lines = [];
  for (const p of paras) lines.push(...wrapText(p, scale, usable));
  const lh = 10 * scale + 6;
  const kickerH = kicker ? 14 : 0;
  const minIconH = (badge && gutter) ? badgeR * 2 + 16 : (gutter ? isz + 14 : 0);
  const h = Math.max(kickerH + lines.length * lh + 16, minIconH, minH);
  return { h, lines, gutter, badgeR, mask };
}

export function notePanelHeight(w, text, scale = 2, reserveRight = 0, icon, kicker = null, badge = false, minH = 0) {
  return notePanelLayout(w, text, scale, reserveRight, icon, kicker, badge, minH).h;
}

export function notePanel(ctx, x, y, w, text, scale = 2, reserveRight = 0, icon, kicker = null, badge = false, minH = 0) {
  const { h, lines, gutter, badgeR, mask } = notePanelLayout(w, text, scale, reserveRight, icon, kicker, badge, minH);
  rect(ctx, x, y, w, h, pal.card_hi);
  rect(ctx, x, y, 4, h, pal.border_gold);
  if (gutter) {
    if (badge) {
      const bcx = x + 14 + badgeR, bcy = y + 14 + badgeR;
      disc(ctx, bcx, bcy, badgeR, pal.well);
      arcRuns(ctx, bcx, bcy, badgeR, badgeR - 2, 0, 360, pal.border_gold);
      icons.drawIcon(ctx, mask, bcx - mask[0] / 2, bcy - mask[0] / 2, pal.gold);
    } else {
      icons.drawIcon(ctx, mask, x + 10, y + 8, pal.gold);
    }
  }
  let ty = y + 8;
  if (kicker) {
    textLeft(ctx, kicker, x + 12 + gutter, ty, 1, pal.gold);
    ty += 14;
  }
  const lh = 10 * scale + 6;
  for (const s of lines) {
    textLeft(ctx, s, x + 12 + gutter, ty, scale, pal.muted);
    ty += lh;
  }
  return h;
}

export function centerBandY(contentH, top, bottom) {
  return top + Math.max(0, Math.floor((bottom - top - contentH) / 2));
}
```

  `disc`/`arcRuns` are already defined later in `ui.js`; JS function declarations/module exports are all hoisted-resolvable at call time within the same module, so no reordering is needed there either.

- [ ] **Step 6: Full suite → green.** `python3 -m pytest tests/ -q`.

---

### Task 2: Redesign the plain-instruction tip call sites (both twins)

**Files:**
- Modify: `docs/js/screen_play.js`, `ui/screen_play.py`
- Modify: `tests/test_screen_play.py`

**Interfaces:**
- Consumes: `note_panel_height`/`notePanelHeight`, `note_panel`/`notePanel`, `center_band_y`/`centerBandY` from Task 1.
- New `ScreenPlay._tip(d, pal, lines, reserve_right=0, icon=None, min_h=150) -> int` (Python) / `_tip(ctx, lines, {reserveRight, icon, minH} = {}) -> {y, h}` (JS) — measures the panel via `note_panel_height`, centers it in `[CONTENT_Y, CTA_Y - 14]` via `center_band_y`, draws it with `badge=True, kicker="TIP"`, and returns where it landed (JS returns `{y, h}`; Python stores `self._tip_rect = (y, h)` since Python call sites need both values too — see quest_commit below).

Touched views (plain `note_panel`/`notePanel` today → `_tip`):

| View | Band | `min_h` | Notes |
|---|---|---|---|
| `resource_planning` | `[150, 396]` | 150 | drop-in replacement |
| `refresh` | `[150, 396]` | 150 | drop-in replacement |
| `quest_commit` | `[150, 310]` | 90 | totals row moves to a **fixed** bottom-anchored `y=318` (was glued to the tip's bottom edge) so a taller/centered tip can't collide with it |
| encounter/combat catch-all (`enc_optional`, `enc_checks`, `combat_shadow`, `combat_enemy`, `combat_player`) | `[150, 396]` | 150 | keep `reserve_right`/flavor-icon behavior, recomputed from the returned rect |

- [ ] **Step 1: Write the failing tests** — add to `tests/test_screen_play.py`:

```python
def test_resource_planning_tip_is_centered_not_top_hugging():
    from ui.screen_play import CONTENT_Y, CTA_Y
    hw, pal, game, screen = _setup("resource_planning")
    screen.draw(hw, game, pal)
    rects = [c for c in hw.display.calls if c[0] == "rect" and c[5] == pal.card_hi]
    tip_rects = [r for r in rects if r[3] == 480 - 16]   # w = 480-2*MARGIN
    assert tip_rects, "no tip panel drawn"
    ty, th = tip_rects[0][2], tip_rects[0][4]
    assert ty > CONTENT_Y + 20          # no longer hugging the top of the band
    assert ty + th < CTA_Y - 4          # still clear of the CTA


def test_resource_planning_tip_shows_tip_kicker():
    hw, pal, game, screen = _setup("resource_planning")
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "TIP" in texts


def test_commit_totals_row_stays_fixed_and_clear_of_tip():
    from ui.screen_play import COMMIT_TOTALS_Y
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    commit_tip = _find(screen, ("commit_tip",))
    assert commit_tip.y + commit_tip.h <= COMMIT_TOTALS_Y
    # totals row's own "Questing for" panel sits at the fixed Y regardless
    # of tip height (was previously `tip_y + 48`)
    panel_rects = [c for c in hw.display.calls if c[0] == "rect" and c[3] == 84]
    assert any(r[2] == COMMIT_TOTALS_Y for r in panel_rects)


def test_catch_all_view_tip_centered_and_flavor_icon_follows_it():
    from ui.screen_play import CONTENT_Y, CTA_Y
    hw, pal, game, screen = _setup("combat_enemy")
    screen.draw(hw, game, pal)
    rects = [c for c in hw.display.calls if c[0] == "rect" and c[5] == pal.card_hi]
    tip_rects = [r for r in rects if r[3] == 480 - 16]
    assert tip_rects
    ty = tip_rects[0][2]
    assert CONTENT_Y < ty < CTA_Y - 30   # centered, not pinned to CONTENT_Y + 6
```

  Check the exact `hw.display.calls` tuple shape used elsewhere in this file (`("rect", x, y, w, h, pen)` per `tests/fake_hardware.py`) before finalizing index positions — the assertions above use `c[2]`=x, `c[3]`=w... **verify indices against `FakeDisplay.rectangle`'s actual append order** (`("rect", x, y, w, h, pen)` → index 1=x, 2=y, 3=w, 4=h, 5=pen) and fix the test snippets' indices to match exactly (the snippets above use `r[2]`/`r[4]` for y/h assuming that order — double check against `tests/fake_hardware.py` line ~54 before running).

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_screen_play.py -k "tip or commit_totals" -q`.

- [ ] **Step 3: Implement in `docs/js/screen_play.js` first** (iron rule: web first). Add imports and the helper:

```js
import { pal, Button, rect, panel, bevel, textLeft, textCenter, wrapText,
         truncateText, ribbon, notePanel, notePanelHeight, centerBandY, drawHeart, drawFlag,
         disc, arcRuns, wxSmall, token } from "./ui.js";
```

  Add the helper and `COMMIT_TOTALS_Y` constant near the top of the class:

```js
const COMMIT_TOTALS_Y = CTA_Y - 8 - 84;   // 318: bottom-anchored, independent of tip height
```

```js
  // Vertically centred phase-tip card: the band between the zones and the
  // CTA is fixed; this measures the panel first so it sits centred in that
  // recovered space instead of hugging the top (the pre-redesign layout).
  _tip(ctx, lines, { reserveRight = 0, icon, minH = 150, bandBottom = CTA_Y - 14 } = {}) {
    const w = 480 - 2 * MARGIN;
    const h = notePanelHeight(w, lines, 2, reserveRight, icon, "TIP", true, minH);
    const ty = centerBandY(h, CONTENT_Y, bandBottom);
    notePanel(ctx, MARGIN, ty, w, lines, 2, reserveRight, icon, "TIP", true, minH);
    return { y: ty, h };
  }
```

  Update the four call sites:

```js
    } else if (view === "resource_planning") {
      this._playersZone(ctx, game);
      this._progressZone(ctx, game);
      this._tip(ctx, ["Collect resources.", "Draw cards.", "Play allies and attachments."]);
      this._cta(ctx, `Next Phase: ${VIEW_LABELS[game.sailing ? "quest_sailing" : "quest_commit"]}`, ["advance"]);
    } else if (view === "quest_commit") {
      this._playersZone(ctx, game);
      this._progressZone(ctx, game);
      const { y: ty, h: th } = this._tip(ctx, "Commit characters to the quest.",
        { minH: 90, bandBottom: COMMIT_TOTALS_Y - 8 });
      this.buttons.push(new Button(["commit_tip"], MARGIN, ty, 480 - 2 * MARGIN, th));
      this._totalsRow(ctx, game, COMMIT_TOTALS_Y, false, ["wp", "stg"]);
      this._cta(ctx, `Next Phase: ${VIEW_LABELS.quest_staging}`, ["advance"]);
```

```js
    } else if (view === "refresh") {
      this._playersZone(ctx, game);
      this._progressZone(ctx, game);
      this._tip(ctx, ["Ready all exhausted cards.", "Threat increases (automatic).",
                       "Pass the first player token."]);
      this._cta(ctx, "End round (raise threat, pass token)", ["endround"]);
    } else {
      this._playersZone(ctx, game);
      const notes = { /* unchanged */ };
      const flavor = { combat_enemy: [icons.DEFENSE, pal.green],
                       combat_player: [icons.ATTACK, pal.tan] }[view];
      this._progressZone(ctx, game);
      const shipNotes = { /* unchanged */ };
      let noteText = notes[view] ?? "";
      if (game.sailing && shipNotes[view]) noteText = [noteText, shipNotes[view]];
      const reserve = flavor ? 34 : 0;
      const { y: ty, h } = this._tip(ctx, noteText, { reserveRight: reserve });
      if (flavor) {
        icons.drawIcon(ctx, flavor[0], 480 - MARGIN - 34,
                       ty + Math.floor((h - 20) / 2), flavor[1]);
      }
      const i = VIEW_ORDER.indexOf(view);
      const nxt = VIEW_ORDER[(i + 1) % VIEW_ORDER.length];
      this._cta(ctx, `Next Phase: ${VIEW_LABELS[nxt] ?? nxt}`, ["advance"]);
    }
```

  Note `_totalsRow`'s `y` parameter is now always `COMMIT_TOTALS_Y` for the `quest_commit` call (previously `ty + 48`); the sailing/staging call sites of `_totalsRow` (`quest_staging`, via `_draw_staging`/`_drawStaging`) are untouched — only the `quest_commit` branch's call changes.

- [ ] **Step 4: Mirror in `ui/screen_play.py`.** Same four changes: import `note_panel_height, center_band_y` from `ui.widgets`; add `COMMIT_TOTALS_Y = CTA_Y - 8 - 84` and a `_tip` method with the same signature/logic (Python: `min_h`, `band_bottom` kwargs); update `resource_planning`, `quest_commit`, `refresh`, and the catch-all `else` branch identically.

```python
COMMIT_TOTALS_Y = CTA_Y - 8 - 84   # 318: bottom-anchored, independent of tip height

def _tip(self, d, pal, lines, reserve_right=0, icon=None, min_h=150, band_bottom=None):
    if band_bottom is None:
        band_bottom = CTA_Y - 14
    w = 480 - 2 * MARGIN
    h = note_panel_height(d.measure_text, w, lines, 2, reserve_right, icon, "TIP", True, min_h)
    ty = center_band_y(h, CONTENT_Y, band_bottom)
    note_panel(d, pal, MARGIN, ty, w, lines, 2, reserve_right, icon, "TIP", True, min_h)
    return ty, h
```

  Update the `resource_planning`, `quest_commit`, `refresh` branches in `draw()` and the catch-all `else` branch to call `self._tip(...)` exactly as the JS does (positional `d, pal` first, per this module's convention).

- [ ] **Step 5: Run → PASS.** `python3 -m pytest tests/test_screen_play.py -q`.

- [ ] **Step 6: Render and inspect every touched scene.**

```
python3 tools/preview.py play_resource_planning /tmp/tip_resource.png
python3 tools/preview.py play_quest_commit /tmp/tip_commit.png
python3 tools/preview.py play_quest_commit_sailing /tmp/tip_commit_sail.png
python3 tools/preview.py play_quest_commit_manyside /tmp/tip_commit_many.png
python3 tools/preview.py play_refresh /tmp/tip_refresh.png
python3 tools/preview.py play_enc_optional /tmp/tip_enc.png
python3 tools/preview.py play_combat_enemy /tmp/tip_combat.png
```

  Confirm: the tip card sits roughly centered in the recovered band (not glued to the top), the circular badge + "TIP" kicker read clearly, the quest_commit totals row is fully clear of the tip and not pushed off/overlapping, and the combat flavor icon (DEFENSE/ATTACK) still sits centered beside the (now relocated) tip. Read each PNG with the Read tool and fix anything cramped or off-center before continuing.

- [ ] **Step 7: Full suite → green.** `python3 -m pytest tests/ -q`.

---

### Task 3: Center-only placement fix for the 3 hand-rolled pipe boxes

**Files:**
- Modify: `docs/js/screen_play.js` (`_draw_sailing`'s enabled branch — inline in `draw()`, `_drawStaging`, `_drawResolution`'s fail/tie branch), `ui/screen_play.py` (`_draw_sailing`, `_draw_staging`, `_draw_resolution`)
- Modify: `tests/test_screen_play.py`

**Interfaces:** none new — reuses `center_band_y`/`centerBandY` from Task 1. These three views keep their existing bespoke box-drawing code (double-frame pipe box with inline icons/dynamic text) untouched; only the `ty0` they compute from is replaced.

- [ ] **Step 1: Write the failing tests** — add to `tests/test_screen_play.py`:

```python
def test_sailing_enabled_tip_box_is_centered():
    from ui.screen_play import CONTENT_Y, CTA_Y
    hw, pal, game, screen = _setup("quest_sailing")
    game.sailing = True
    screen.draw(hw, game, pal)
    rects = [c for c in hw.display.calls if c[0] == "rect" and c[5] == pal.card_hi]
    ty = min(r[2] for r in rects)   # top-most card_hi rect = the pipe box
    assert ty > CONTENT_Y + 4       # no longer glued to CONTENT_Y+6


def test_staging_tip_box_is_centered():
    from ui.screen_play import CONTENT_Y
    hw, pal, game, screen = _setup("quest_staging")
    screen.draw(hw, game, pal)
    rects = [c for c in hw.display.calls if c[0] == "rect" and c[5] == pal.card_hi]
    ty = min(r[2] for r in rects)
    assert ty > CONTENT_Y


def test_resolution_fail_tip_box_is_centered():
    from ui.screen_play import CONTENT_Y
    hw, pal, game, screen = _setup("quest_resolution")
    game.quest_outcome = "fail"
    game.quest_outcome_n = 3
    screen.draw(hw, game, pal)
    rects = [c for c in hw.display.calls if c[0] == "rect" and c[5] == pal.card_hi]
    ty = min(r[2] for r in rects)
    assert ty > CONTENT_Y
```

  As in Task 2, confirm the `(kind, x, y, w, h, pen)` index order against `tests/fake_hardware.py` before finalizing `r[2]`/`r[5]`.

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement in `docs/js/screen_play.js`.** In the `quest_sailing`-enabled branch (inside `draw()`), `_drawStaging`, and `_drawResolution`'s fail/tie branch, replace the hardcoded `ty0 = CONTENT_Y + 6` / `CONTENT_Y + 2` with a centered value computed from the box's own (already-known-ahead-of-drawing) height:

```js
// quest_sailing enabled branch: th = 3*lh+16 computed above, unchanged
const ty0 = centerBandY(th, CONTENT_Y, CTA_Y - 14);
```

```js
// _drawStaging: th = (lines.length+1)*lh+16 computed above, unchanged
const ty0 = centerBandY(th, CONTENT_Y, CTA_Y - 14);
```

```js
// _drawResolution fail/tie branch: th = 2*lh+16, unchanged
const ty0 = centerBandY(th, CONTENT_Y, CTA_Y - 14);
```

  Import `centerBandY` alongside `notePanelHeight` (already added in Task 2's import line). No other line in these three blocks changes — the box chrome, inline icons, and dynamic text stay exactly as they are today, just repositioned.

- [ ] **Step 4: Mirror in `ui/screen_play.py`** — same three `ty0`/`ty_0` replacements in `_draw_sailing`, `_draw_staging`, `_draw_resolution`, using `center_band_y`.

- [ ] **Step 5: Run → PASS.** `python3 -m pytest tests/test_screen_play.py -q`.

- [ ] **Step 6: Render and inspect.**

```
python3 tools/preview.py play_quest_sailing /tmp/tip_sailing.png
python3 tools/preview.py play_quest_staging /tmp/tip_staging.png
python3 tools/preview.py play_quest_resolution_fail /tmp/tip_resfail.png
```

  Confirm each pipe box is now vertically centered in its band, its inline icons/text are unaffected, and it doesn't collide with the totals row (`quest_staging`, which the box sits above — verify with steppers still visible below it) or the CTA.

- [ ] **Step 7: Full suite → green; open the web twin in a browser and click through Resource → Commit → Staging (enable Sailing to see that variant too) → Refresh, confirming the redesign feels right live, not just in the static PNGs.** Report any spot where the centered placement looks worse than the old top-anchored one (e.g. if a very short reminder now floats awkwardly high in a tall band) so it can be tuned (lower `min_h` or a smaller band) before merging.

---

## Self-Review

**Spec coverage:** "not in love with the placement" → Tasks 2-3's `center_band_y`/`centerBandY` repositioning of every phase-tip call site into the recovered band. "not in love with the design" → Task 1's badge+kicker chrome redesign, applied to the plain-instruction sites in Task 2 (the highest-value target, since those are the ones that look thinnest against the new dead space). The 3 hand-rolled pipe boxes get placement parity without a risky content rewrite (Task 3), and the two explicitly-different screens (`quest_setup` scroll, `setup_game`) are left alone with reasoning given in Global Constraints.

**Placeholder scan:** every task carries complete, real code (full `note_panel`/`notePanel` bodies, full `_tip` helper, exact call-site diffs, exact test assertions). The one explicit "verify before running" flag (fake-hardware tuple index order) is a intentional pointer to a single source of truth (`tests/fake_hardware.py`) rather than a guess, so the fresh engineer checks it once instead of the plan silently being wrong in six places.

**Type consistency:** `note_panel_height(...)`/`notePanelHeight(...)` and `note_panel(...)`/`notePanel(...)` share one `_note_panel_layout`/`notePanelLayout` computation in Task 1, so a caller's measured height is *guaranteed* identical to what gets drawn — no drift between the centering pass and the draw pass. `_tip`'s return shape (`(ty, th)` in Python / `{y, h}` in JS) is consumed identically by the `quest_commit` and catch-all call sites in Task 2.

**If the user prefers a different default:**
- *Kicker wording:* this plan uses a flat `"TIP"` label everywhere for simplicity/consistency. If per-phase kicker text is preferred (e.g. "RESOURCE PHASE", "COMBAT"), swap the literal `"TIP"` argument at each `_tip(...)` call site in Task 2 — the component already accepts an arbitrary string, no widget change needed.
- *Unifying the hand-rolled pipe boxes into the same badge/kicker chrome:* Task 3 deliberately keeps their bespoke inline-icon content (e.g. the sailing tip's inline ribbon/wheel glyphs mid-sentence, the staging tip's dynamic outcome line) untouched, changing only placement. A full visual unification is possible by extracting a `tip_frame(d, pal, x, y, w, h, icon) -> content_x` chrome-only primitive from `note_panel` and having these three call it directly for their box, but that is a larger, higher-risk change (each has different inline-composition logic) better scoped as a follow-up once this plan's simpler win has shipped and been seen on-device.
