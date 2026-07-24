# Stats Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the four stacked stat rows on the play screen with two compact
axis-flipped zones (Players + Progress) and rework the Progress detail view, in
lockstep across the web twin and the MicroPython firmware.

**Architecture:** New arc/circle drawing primitives (built from rect/triangle
runs — the device has no arc primitive) power circular "token" widgets. The play
screen draws a 3-row Players matrix and a header+row Progress zone, each a single
tap-target opening a full-screen detail modal. Two new gamestate fields
(`commit_touched`, `quest_history`) back the willpower ring and the by-round
chart.

**Tech Stack:** ES modules + Canvas (`docs/js/`), MicroPython + PicoGraphics
(`ui/`, `gamestate.py`), pytest + a layout linter over shared scenes.

**Spec:** `design/stats-redesign.md`. **Proven mock (lift geometry/code from
here):** `scratchpad/mock_stats.py` in the session scratchpad — every function
below was prototyped and rendered device-faithfully there.

## Global Constraints

- **Device-faithful drawing only:** `rect`, `triangle`, `text` (+ `create_pen`).
  No `circle`/arc primitive exists in the pipeline or the linter. Every ring/disc
  is emitted as per-scanline rect runs / triangle wedges.
- **`MIN_TARGET = 24`** (`tests/test_layout.py`): every `Button` hit-rect must be
  ≥ 24px in each dimension and on-screen. Drawn circles may be smaller than their
  hit-rect — size the `Button` to ≥24, center the visual inside it.
- **Layout linter also asserts:** all rect/text inside 480×480; no two text runs
  overlap **except** identical strings within 2px (the drop-shadow pair); every
  text call with a space passes `wrap` width > its pixel width (pre-wrapped).
- **Web-first, then firmware, in lockstep.** JS is the source of truth per task;
  Python mirrors method-for-method. A task is done only when **both** land.
- **Tests are Python:** `python3 -m pytest tests/` must stay green (includes the
  layout lint over every scene). Web is verified live in the browser
  (`python3 -m http.server` in `docs/`, hard-reload `?v=N`).
- **No `tools/gen_web_data.py` run** — these are code, not generated data. No new
  icon masks (reuse `WHEEL`, `WHEEL_SM`, `THREAT`, `WILLPOWER`, `TRAIL`).
- **Stat colours** (`design/stat-system.md`): threat icon red / staging-enemy
  threat black / progress ranger green / willpower sunburst gold; **all values
  gold** (`pal.value`); **danger = red ring only** at `threat ≥ elimination−10`.
- **DONE header convention:** every full-screen modal + the log/phases/about/
  gameover screens show the round id upper-left, title centred, and a **`DONE`**
  button upper-right (replaces the old `X` / `< back`). `DONE` applies-and-closes
  (edits are live and logged on close — the existing `QuestingProgressModal`
  pattern). `EliminationModal` and `StageCompleteModal` keep their distinct choice
  buttons but adopt the round-id/DONE header.
- **Palette already has** `value` (=gold), `brown`, `well` (uncommitted). This
  plan adds `shadow`.

---

### Task 1: Dark-gray text drop-shadow

**Files:**
- Modify: `docs/js/ui.js` (pal object; `textLeft`)
- Modify: `ui/theme.py` (Palette `__init__`)
- Modify: `ui/widgets.py` (`text_left`, `text_center`)

**Interfaces:**
- Produces: `pal.shadow` (JS) / `Palette.shadow` (Python) = `rgb(34,30,24)`, used
  as the text drop-shadow pen everywhere.

- [ ] **Step 1: Add the pen (web).** In `docs/js/ui.js`, in the `pal` object,
  add after `bevel_d, bevel_l`: `shadow: rgb(34, 30, 24),`.

- [ ] **Step 2: Use it (web).** In `docs/js/ui.js` `textLeft`, change the shadow
  draw from `drawGlyphs(ctx, s, x + off, y + off, scale, pal.bevel_d)` to
  `... pal.shadow)`. (`textCenter` delegates to `textLeft` — no change.)

- [ ] **Step 3: Add the pen (firmware).** In `ui/theme.py` after `self.bevel_d`,
  add `self.shadow = d.create_pen(34, 30, 24)`.

- [ ] **Step 4: Use it (firmware).** In `ui/widgets.py`, in `text_left` and
  `text_center`, change `d.set_pen(pal.bevel_d)` (the shadow pass only) to
  `d.set_pen(pal.shadow)`. Leave `bevel()` using `bevel_d`.

- [ ] **Step 5: Run tests.** Run: `python3 -m pytest tests/ -q`
  Expected: PASS (shadow is a same-string±2px pair — the collision test already
  exempts it; the pen value doesn't affect geometry).

- [ ] **Step 6: Browser check.** Serve `docs/`, open the play screen, confirm text
  still legible; the black staging number no longer blurs into its shadow.

- [ ] **Step 7: Commit.**
```bash
git add docs/js/ui.js ui/theme.py ui/widgets.py
git commit -m "feat(theme): dark-gray text drop-shadow (pal.shadow)"
```

---

### Task 2: Circle/arc drawing primitives

**Files:**
- Modify: `docs/js/ui.js` (export `disc`, `arcRuns`, `ring`, `token`, `wxSmall`)
- Modify: `ui/widgets.py` (`disc`, `arc_runs`, `ring`, `token`, `wx_small`)
- Test: `tests/test_widgets_primitives.py` (new)

**Interfaces:**
- Produces (web): `disc(ctx,cx,cy,r,pen)`, `arcRuns(ctx,cx,cy,R,r,a0,a1,pen)`,
  `ring(ctx,cx,cy,R,w,frac,fill,track)`,
  `token(ctx,cx,cy,R,w,value,vpen,frac,fill,track,vscale=2)`,
  `wxSmall(ctx,idx,cx,cy,r,pen=null)`.
- Produces (firmware): same as `disc`, `arc_runs`, `ring`, `token`, `wx_small`
  in `ui/widgets.py`. Angles: 0° = top, clockwise. `wx_small` idx 0 sun / 1
  cloud / 2 rain / 3 storm; `pen` forces one colour (else natural).

- [ ] **Step 1: Write the failing test (firmware primitives).** Create
  `tests/test_widgets_primitives.py`:
```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.fake_hardware import FakeDisplay
from ui.theme import Palette
from ui import widgets as W


def _d():
    d = FakeDisplay()
    return d, Palette(d)


def test_disc_stays_in_bounds_and_draws():
    d, pal = _d()
    W.disc(d, 40, 40, 15, pal.gold)
    assert d.calls, "disc drew nothing"
    for c in d.calls:
        assert c[0] == "rect"
        _, x, y, w, h, _pen = c
        assert 0 <= x and 0 <= y and x + w <= 480 and y + h <= 480


def test_ring_full_then_partial_uses_both_pens():
    d, pal = _d()
    W.ring(d, 40, 40, 15, 2, 0.5, pal.gold, pal.dim)
    pens = {c[5] for c in d.calls if c[0] == "rect"}
    assert pal.dim in pens and pal.gold in pens


def test_token_draws_value_text_centered():
    d, pal = _d()
    W.token(d, pal, 40, 40, 14, 2, 42, pal.gold, 0.5, pal.gold, pal.dim)
    texts = [c for c in d.calls if c[0] == "text" and str(c[1]) == "42"]
    assert texts, "token value not drawn"


def test_wx_small_sun_and_storm_differ():
    d, pal = _d()
    W.wx_small(d, pal, 0, 40, 40, 6)
    sun = len(d.calls)
    d2, _ = _d()
    W.wx_small(d2, pal, 3, 40, 40, 6)
    assert sun != len(d2.calls)
```

- [ ] **Step 2: Run it — verify it fails.**
  Run: `python3 -m pytest tests/test_widgets_primitives.py -q`
  Expected: FAIL (`AttributeError: module 'ui.widgets' has no attribute 'disc'`).

- [ ] **Step 3: Implement the firmware primitives.** Add to `ui/widgets.py`
  (`import math` at top if absent). Lift verbatim from `scratchpad/mock_stats.py`,
  adjusting `token`/`wx_small` to take `pal` (mock used a global `P`):
```python
import math

def disc(d, cx, cy, rad, pen):
    d.set_pen(pen)
    for py in range(int(cy - rad), int(cy + rad) + 1):
        h2 = rad * rad - (py - cy) ** 2
        if h2 < 0:
            continue
        hx = int(math.sqrt(h2))
        d.rectangle(int(cx - hx), py, 2 * hx + 1, 1)


def arc_runs(d, cx, cy, R, r, a0, a1, pen):
    """Ring/arc band between radii r..R and angles a0..a1 (0deg=top, cw)."""
    d.set_pen(pen)
    for py in range(int(cy - R), int(cy + R) + 1):
        run = False
        x0 = 0
        for px in range(int(cx - R), int(cx + R) + 2):
            dx, dy = px - cx, py - cy
            dd = math.sqrt(dx * dx + dy * dy)
            on = r <= dd <= R
            if on and a1 is not None:
                ang = math.degrees(math.atan2(dx, -dy)) % 360.0
                on = a0 <= ang <= a1
            if on and not run:
                run, x0 = True, px
            elif not on and run:
                d.rectangle(x0, py, px - x0, 1)
                run = False


def ring(d, cx, cy, R, w, frac, fill, track):
    arc_runs(d, cx, cy, R, R - w, 0, 360, track)
    if frac > 0:
        arc_runs(d, cx, cy, R, R - w, 0, frac * 360.0, fill)


def token(d, pal, cx, cy, R, w, value, vpen, frac, fill, track, vscale=2):
    disc(d, cx, cy, R, pal.well)
    ring(d, cx, cy, R, w, frac, fill, track)
    if value is not None:
        text_center(d, pal, str(value), cx, int(cy - 4 * vscale), vscale, vpen)


def wx_small(d, pal, idx, cx, cy, r, pen=None):
    if idx == 0:
        disc(d, cx, cy, r, pen or pal.amber)
        disc(d, cx - 1, cy - 1, max(1, r // 2), pen or pal.gold)
        d.set_pen(pen or pal.amber)
        for dx, dy in ((0, -r - 3), (0, r + 1), (-r - 3, 0), (r + 1, 0)):
            d.rectangle(cx + dx, cy + dy, 2, 2)
        return
    cloud = pen or pal.muted
    disc(d, cx - 3, cy, r - 1, cloud)
    disc(d, cx + 3, cy - 1, r - 2, cloud)
    disc(d, cx, cy - 2, r - 1, cloud)
    d.set_pen(cloud)
    d.rectangle(cx - 6, cy, 12, r - 1)
    if idx == 2:
        d.set_pen(pen or pal.dim)
        for k in (-3, 1, 5):
            d.rectangle(cx + k, cy + r - 1, 1, 3)
    elif idx == 3:
        d.set_pen(pen or pal.gold)
        d.triangle(cx, cy + r - 2, cx - 3, cy + r + 3, cx + 2, cy + r)
```
Note `token`/`wx_small` take `pal` as 2nd arg (Python needs it for `text_center`
+ pens). `text_center` is already defined in this module (used before its
def is fine — module-level functions resolve at call time).

- [ ] **Step 4: Run tests — verify pass.**
  Run: `python3 -m pytest tests/test_widgets_primitives.py -q`  Expected: PASS.

- [ ] **Step 5: Mirror to the web (`docs/js/ui.js`).** Export the same, using
  `ctx.fillStyle`/`ctx.fillRect`. `token` takes no `pal` (uses `textCenter` +
  passed pens). Lift from the mock's canvas forms:
```javascript
export function disc(ctx, cx, cy, rad, pen) {
  ctx.fillStyle = pen;
  for (let py = Math.floor(cy - rad); py <= Math.ceil(cy + rad); py++) {
    const h2 = rad * rad - (py - cy) ** 2;
    if (h2 < 0) continue;
    const hx = Math.floor(Math.sqrt(h2));
    ctx.fillRect(Math.floor(cx - hx), py, 2 * hx + 1, 1);
  }
}
export function arcRuns(ctx, cx, cy, R, r, a0, a1, pen) {
  ctx.fillStyle = pen;
  for (let py = Math.floor(cy - R); py <= Math.ceil(cy + R); py++) {
    let run = false, x0 = 0;
    for (let px = Math.floor(cx - R); px <= Math.ceil(cx + R) + 1; px++) {
      const dx = px - cx, dy = py - cy;
      const dd = Math.hypot(dx, dy);
      let on = r <= dd && dd <= R;
      if (on && a1 !== null) {
        const ang = ((Math.atan2(dx, -dy) * 180 / Math.PI) % 360 + 360) % 360;
        on = a0 <= ang && ang <= a1;
      }
      if (on && !run) { run = true; x0 = px; }
      else if (!on && run) { ctx.fillRect(x0, py, px - x0, 1); run = false; }
    }
  }
}
export function ring(ctx, cx, cy, R, w, frac, fill, track) {
  arcRuns(ctx, cx, cy, R, R - w, 0, 360, track);
  if (frac > 0) arcRuns(ctx, cx, cy, R, R - w, 0, frac * 360, fill);
}
export function token(ctx, cx, cy, R, w, value, vpen, frac, fill, track, vscale = 2) {
  disc(ctx, cx, cy, R, pal.well);
  ring(ctx, cx, cy, R, w, frac, fill, track);
  if (value !== null && value !== undefined)
    textCenter(ctx, String(value), cx, Math.floor(cy - 4 * vscale), vscale, vpen);
}
export function wxSmall(ctx, idx, cx, cy, r, pen = null) { /* mirror wx_small */ }
```

- [ ] **Step 6: Browser smoke.** Temporarily call `token`/`ring` from the console
  or a scratch draw; confirm a clean ring + centered value. (No committed web
  test harness — visual check only.)

- [ ] **Step 7: Commit.**
```bash
git add docs/js/ui.js ui/widgets.py tests/test_widgets_primitives.py
git commit -m "feat(ui): arc/disc/ring/token/wx_small primitives (rect/tri only)"
```

---

### Task 3: `commit_touched` (willpower ring state)

**Files:**
- Modify: `docs/js/gamestate.js` (Player, `setCommit`, `endRound`, `advanceView`,
  `toDict`/`fromDict`; new `touchCommit`)
- Modify: `gamestate.py` (mirror)
- Test: `tests/test_gamestate.py` (add cases)

**Interfaces:**
- Produces: `player.commit_touched` (bool). `game.touchCommit(i)` / `touch_commit(i)`
  sets it true. Reset false for all in `endRound`/`end_round` and on setup→round-1.
  `setCommit`/`set_commit` also sets it true for that player.

- [ ] **Step 1: Failing test (Python).** In `tests/test_gamestate.py` add:
```python
def test_commit_touched_lifecycle():
    from gamestate import GameState
    g = GameState()
    assert g.players[0].commit_touched is False
    g.set_commit(0, 5)
    assert g.players[0].commit_touched is True
    g.touch_commit(1)
    assert g.players[1].commit_touched is True
    g.end_round()
    assert all(p.commit_touched is False for p in g.players)


def test_commit_touched_round_trips():
    from gamestate import GameState
    g = GameState()
    g.set_commit(0, 3)
    g2 = GameState.from_dict(g.to_dict())
    assert g2.players[0].commit_touched is True
```

- [ ] **Step 2: Run — verify fail.**
  Run: `python3 -m pytest tests/test_gamestate.py -k commit_touched -q`
  Expected: FAIL (`AttributeError: ... 'commit_touched'`).

- [ ] **Step 3: Implement (Python `gamestate.py`).**
  - `Player.__init__`: add `self.commit_touched = False`.
  - `set_commit(self, index, value)`: after setting commit, add
    `self.players[index].commit_touched = True`.
  - New method:
    ```python
    def touch_commit(self, index):
        self.players[index].commit_touched = True
    ```
  - `end_round`: after the threat loop, add
    `for p in self.players: p.commit_touched = False`.
  - `advance_view` setup→round-1 branch (where it enters `VIEW_ORDER[0]`): add the
    same reset loop.
  - `to_dict` player dict: add `"commit_touched": p.commit_touched`.
  - `from_dict` player build: add `p.commit_touched = pd.get("commit_touched", False)`.

- [ ] **Step 4: Run — verify pass.**
  Run: `python3 -m pytest tests/test_gamestate.py -k commit_touched -q`  Expected: PASS.

- [ ] **Step 5: Mirror (web `docs/js/gamestate.js`).** `Player`: `this.commit_touched
  = false;`. `setCommit`: set `this.players[index].commit_touched = true;`. Add
  `touchCommit(i){ this.players[i].commit_touched = true; }`. `endRound` +
  `advanceView` setup branch: `this.players.forEach(p => p.commit_touched = false);`.
  `toDict`/`fromDict`: include `commit_touched` (default false).

- [ ] **Step 6: Run full suite.** Run: `python3 -m pytest tests/ -q`  Expected: PASS.

- [ ] **Step 7: Commit.**
```bash
git add docs/js/gamestate.js gamestate.py tests/test_gamestate.py
git commit -m "feat(gamestate): commit_touched flag for the willpower ring"
```

---

### Task 4: `quest_history` (by-round chart data)

**Files:**
- Modify: `docs/js/gamestate.js` (`quest_history`, append in `resolveQuest`,
  `toDict`/`fromDict`)
- Modify: `gamestate.py` (mirror)
- Test: `tests/test_gamestate.py` (add cases)

**Interfaces:**
- Produces: `game.quest_history` — list of
  `{round, willpower, staging, outcome, n, heading}`, appended once per round at
  `resolveQuest`/`resolve_quest` (all three outcomes). `n` = progress (success) /
  threat (fail) / 0 (tie). Capped at the last 20 entries.

- [ ] **Step 1: Failing test (Python).**
```python
def test_quest_history_records_each_resolution():
    from gamestate import GameState
    g = GameState()
    g.heading = 1
    g.resolve_quest(10, 4)          # success +6
    g.resolve_quest(3, 7)           # fail +4 threat
    g.resolve_quest(5, 5)           # tie 0
    h = g.quest_history
    assert [e["outcome"] for e in h] == ["success", "fail", "tie"]
    assert h[0]["willpower"] == 10 and h[0]["staging"] == 4 and h[0]["n"] == 6
    assert h[1]["n"] == 4 and h[2]["n"] == 0
    assert h[0]["heading"] == 1


def test_quest_history_caps_at_20():
    from gamestate import GameState
    g = GameState()
    for _ in range(25):
        g.resolve_quest(5, 3)
    assert len(g.quest_history) == 20
```

- [ ] **Step 2: Run — verify fail.**
  Run: `python3 -m pytest tests/test_gamestate.py -k quest_history -q`  Expected: FAIL.

- [ ] **Step 3: Implement (Python).**
  - `__init__`: `self.quest_history = []`.
  - `resolve_quest`: at the top capture `diff = willpower - staging`; determine
    `outcome`/`n` (success→"success",diff; diff<0→"fail",-diff; else "tie",0), and
    **before returning**, append:
    ```python
    self.quest_history.append({
        "round": self.round, "willpower": willpower, "staging": staging,
        "outcome": outcome, "n": n, "heading": self.heading})
    if len(self.quest_history) > 20:
        self.quest_history = self.quest_history[-20:]
    ```
    (Refactor the existing branches so the append runs on every path.)
  - `to_dict`: `"quest_history": [dict(e) for e in self.quest_history]`.
  - `from_dict`: `g.quest_history = [dict(e) for e in d.get("quest_history", [])]`.

- [ ] **Step 4: Run — verify pass.**
  Run: `python3 -m pytest tests/test_gamestate.py -k quest_history -q`  Expected: PASS.

- [ ] **Step 5: Mirror (web).** Same in `resolveQuest` (append `{round, willpower,
  staging, outcome, n, heading}`, cap 20); `toDict`/`fromDict` include it (default
  `[]`).

- [ ] **Step 6: Full suite.** Run: `python3 -m pytest tests/ -q`  Expected: PASS.

- [ ] **Step 7: Commit.**
```bash
git add docs/js/gamestate.js gamestate.py tests/test_gamestate.py
git commit -m "feat(gamestate): quest_history for the by-round chart"
```

---

### Task 5: Players zone — flipped 3-row matrix

**Files:**
- Modify: `docs/js/screen_play.js` (`_chips` → `_playersZone`; all call sites)
- Modify: `ui/screen_play.py` (`_chips` → `_players_zone`; call sites)
- Modify: `tests/scenes.py` (existing play scenes exercise it)
- Test: `python3 -m pytest tests/ -q` (layout lint over play scenes)

**Interfaces:**
- Consumes: `token` (Task 2), `pal.value`, `commit_touched` (Task 3).
- Produces: `_playersZone(ctx, game)` / `_players_zone(d, pal, game)` drawing the
  zone at x 8..~162 and pushing **one** Button `["players_detail"]` (≥24px) over
  the whole zone. Constant `ZONE_TOP = HEADER_H + 6`.

- [ ] **Step 1: Web implementation.** In `docs/js/screen_play.js` add
  `_playersZone(ctx, game)` (lift geometry from `scratchpad/mock_stats.py`
  `frame()` players block). Header row y = `ZONE_TOP+2`; threat row cy = `ZONE_TOP+40`;
  willpower row cy = `ZONE_TOP+72`; columns `pcx=[50,82,114,146]`; token `R=14 w=2`.
  Row-label icons: helm at `(7, threatCy-10)` (red + `pal.shadow` offset),
  sunburst at `(7, willCy-10)` gold; `P` header at `(18, ZONE_TOP+2)` scale 2 muted.
  Per player: first-player → gold rect `(cx-12, ZONE_TOP-2, 24, 19)` + dark number;
  else number tan. Threat token: `danger = threat >= elimination-10`, ring frac
  `threat/elimination`, fill `danger?pal.red:pal.gold`, value `eliminated?"OUT":threat`
  (`pal.red` if eliminated else `pal.value`). Willpower token: uniform ring
  (`frac=1`), fill `commit_touched?pal.gold:pal.dim` during `quest_commit`, else
  `pal.gold`; value `commit` in `pal.value`. Push `new Button(["players_detail"],
  8, ZONE_TOP-2, 156, 90)`.

- [ ] **Step 2: Replace call sites (web).** Everywhere `draw()` calls
  `this._chips(ctx, game)`, call `this._playersZone(ctx, game)`. Delete `_chips`,
  `_chipW`, `_commitRow` (folded away). Route `["players_detail"]` in `onButton`
  to `["modal", new PlayersDetailModal(game)]` (Task 9 provides the class — stub it
  to `QuestingProgressModal` temporarily so this task runs, then wire in Task 9).

- [ ] **Step 3: Browser check.** Serve `docs/`, walk the phases; confirm the 3-row
  matrix, first-player chip, red danger ring (set a threat ≥40), willpower dim vs
  gold across commit.

- [ ] **Step 4: Firmware mirror.** In `ui/screen_play.py` add
  `_players_zone(self, d, pal, game)` mirroring Step 1 (snake_case; `token(d, pal,
  ...)`; `icons.draw(d, mask, x, y, pen)`). Replace every `self._chips(d, pal, game)`
  with `self._players_zone(d, pal, game)`. Remove `_chips`, `_chip_w`, `_commit_row`.
  Add the `["players_detail"]` Button. Add `ZONE_TOP = HEADER_H + 6`.

- [ ] **Step 5: Run tests.** Run: `python3 -m pytest tests/ -q`
  Expected: PASS. Fix any `test_screen_play.py` assertions that referenced the old
  `_chips` layout (update coordinates/expected button ids to `players_detail`).

- [ ] **Step 6: Commit.**
```bash
git add docs/js/screen_play.js ui/screen_play.py tests/
git commit -m "feat(play): flipped 3-row Players zone (one tap-target)"
```

---

### Task 6: Progress zone — flipped header + one row

**Files:**
- Modify: `docs/js/screen_play.js` (`_progressRow`/`_headingProgressCard` →
  `_progressZone`)
- Modify: `ui/screen_play.py` (mirror)
- Test: `python3 -m pytest tests/ -q`

**Interfaces:**
- Consumes: `token`, `disc`, `arcRuns`, `wxSmall`, `WHEEL_SM`, `HEADINGS`.
- Produces: `_progressZone(ctx, game)` / `_progress_zone(d, pal, game)` at x
  174..472, pushing **one** Button `["progress_detail"]` over the zone. A vertical
  divider rect at x=168.

- [ ] **Step 1: Web implementation.** Lift from `scratchpad/mock_stats.py` progress
  block. Columns start x=190, stride 32 (`gx=[190,222,254,...]`); header labels at
  y=`ZONE_TOP+2`, circle row cy=`ZONE_TOP+40`, token `R=14 w=2`. Build the column
  list: `Q` (quest, label from `questLabel()` short → just `"Q"`), `L` (if
  `active_location`), `S1..Sn` (side quests), then the sailing column last (wheel
  `WHEEL_SM` header at `(scx-8, ZONE_TOP+0)`, `disc` + 4 quadrant `arcRuns`
  `[(272,360),(0,88),(92,178),(182,268)]` lit `4-heading` dimming upper-left first,
  `wxSmall(HEADING, scx, cy, 6)` centre). Value = remaining `max(0, points-progress)`,
  ring `progress/points`. **Column cap:** `maxCols = Math.floor((472-174)/32)`; if
  `Q + L + sides + sailing` exceed it, keep Q, L, the **oldest** side quests, and
  sailing (drop the newest side quests; they remain in Progress detail). Caption
  `"quest points remaining"` at `(174, ZONE_TOP+66)` scale 1 dim. Divider
  `rect(168, ZONE_TOP, 1, 90, pal.border)`. Push `new Button(["progress_detail"],
  174, ZONE_TOP-2, 298, 90)`.

- [ ] **Step 2: Replace call sites (web).** Replace `this._progressRow(...)` calls
  with `this._progressZone(ctx, game)` in every view branch. Delete `_progressRow`,
  `_headingProgressCard`, `_headingPen`. Route `["progress_detail"]` to `["modal",
  new QuestingProgressModal(game)]` (Task 10 reworks it).

- [ ] **Step 3: Browser check.** Confirm Q/L/S labels + remaining values, sailing
  column with small wheel + weather, caption, divider; toggle sailing + add side
  quests to see wrap/cap.

- [ ] **Step 4: Firmware mirror** in `ui/screen_play.py` (`_progress_zone`). Replace
  `self._progress_row(...)` call sites; remove `_progress_row`,
  `_heading_progress_card`, `_heading_pen`, `PROG_Y`/`PROG_H` if now unused.

- [ ] **Step 5: Run tests.** Run: `python3 -m pytest tests/ -q`  Expected: PASS
  (update `test_screen_play.py` button-id/coord expectations to `progress_detail`).

- [ ] **Step 6: Commit.**
```bash
git add docs/js/screen_play.js ui/screen_play.py tests/
git commit -m "feat(play): flipped Progress zone (header + one row, capped cols)"
```

---

### Task 7: Rewired play taps + staging inline ± + reveal copy

**Files:**
- Modify: `docs/js/screen_play.js` (`onButton`, `_totalsRow`)
- Modify: `ui/screen_play.py` (mirror)
- Test: `python3 -m pytest tests/ -q`

**Interfaces:**
- Consumes: `PlayersDetailModal` (Task 9), reworked `QuestingProgressModal` (Task 10).
- Produces: taps — `players_detail` + the "Questing for" card → Players detail;
  `progress_detail` → Progress detail; `stg-`/`stg+` inline steppers on the Staging
  card's left/right thirds; centre → `CounterModal`.

- [ ] **Step 1: Web — Questing-for + zone routing.** In `onButton`: `["wp"]`
  (Questing for card) now returns `["modal", new PlayersDetailModal(game)]` (was
  `QuestingForModal`). Ensure `["players_detail"]` and `["progress_detail"]` route
  to their modals.

- [ ] **Step 2: Web — Staging inline ±.** In `_totalsRow`, for the Staging half
  (`key === "stg"`, non-stepper branch), add a left third Button `["stg-"]` and a
  right third Button `["stg+"]` (each ≥24px: `x, y, half/3, 84`), draw a dim `-`
  and `+` glyph and a 1px divider before each third; keep the centre third as the
  existing `["stg"]` → `CounterModal`. Handlers: `stg-` →
  `game.staging = Math.max(0, game.staging-1)`, `stg+` → `+1`.

- [ ] **Step 3: Web — reveal copy.** In `_totalsRow` staging caption, change
  `` `reveal up to +${game.stagingRevealEstimate()}` `` to
  `` `+${game.stagingRevealEstimate()} reveal estimate` ``.

- [ ] **Step 4: Browser check.** Tap Players/Progress zones + Questing-for →
  correct modals; staging ± thirds adjust; caption reads "+12 reveal estimate".

- [ ] **Step 5: Firmware mirror** in `ui/screen_play.py` (`on_button`,
  `_totals_row`): same routing, `stg-`/`stg+` thirds, caption text.

- [ ] **Step 6: Run tests.** Run: `python3 -m pytest tests/ -q`  Expected: PASS
  (add a `play_quest_staging` scene assertion for the new stg ± buttons if
  `test_screen_play.py` enumerates buttons).

- [ ] **Step 7: Commit.**
```bash
git add docs/js/screen_play.js ui/screen_play.py tests/
git commit -m "feat(play): route zones/questing-for to details, staging inline +/-"
```

---

### Task 8: DONE header convention

**Files:**
- Modify: `docs/js/screens.js` (`drawHeader`; new `modalHeader`)
- Modify: `ui/header.py` (`draw_header`; new `modal_header`)
- Modify: `docs/js/screens.js` + `ui/modals.py` (Reminders/Sailing top rows use it)
- Test: `python3 -m pytest tests/ -q`

**Interfaces:**
- Produces: `modalHeader(ctx, game, title, buttons)` / `modal_header(d, pal, game,
  title, buttons)` — round id `R{round} {step}` upper-left (muted), title centred
  (gold, scale 2), a **DONE** bevel button upper-right pushing `["close"]` (hit-rect
  `408,4,64,32`). `drawHeader`'s `close:true` case renders `DONE` (same button
  `["nav","close"]`) instead of `X`.

- [ ] **Step 1: Web — shared header.** In `docs/js/screens.js` add
  `export function modalHeader(ctx, game, title, buttons)` drawing the round label,
  centred title, `rect(0,HEADER_H,480,1,pal.border)`, and a `bevel` DONE button at
  `(408,4,64,32)` with `textCenter("DONE",440,12,2,pal.ok_fg)`, pushing
  `new Button(["close"],408,4,64,32)`. In `drawHeader`, replace the `close` branch's
  `textLeft(ctx,"X",...)` with a DONE bevel button at `(408,4,64,32)` (keep id
  `["nav","close"]`, hit-rect ≥24).

- [ ] **Step 2: Web — apply.** In `RemindersModal.draw` and `SailingModal.draw`,
  replace their hand-drawn round/title/X rows with `modalHeader(ctx, this.game,
  "<title>", this.buttons)` (Sailing keeps its Apply/Cancel footer; DONE = its
  cancel/dismiss — but Sailing's Apply must persist, so keep Apply at the footer
  and let DONE = cancel). Confirm the `["close"]`/`["cancel"]` handling in
  `onButton` still returns the right value.

- [ ] **Step 3: Firmware mirror.** In `ui/header.py` add `modal_header(d, pal,
  game, title, buttons)` and change `draw_header`'s close branch to a DONE button.
  Apply in `ui/modals.py` (`RemindersModal`, `SailingModal`).

- [ ] **Step 4: Run tests.** Run: `python3 -m pytest tests/ -q`
  Expected: PASS (update `test_modals.py`/`test_screen_log.py` expectations for the
  DONE button id/position; the reminders/sailing scenes now include a `["close"]`
  bevel ≥24px).

- [ ] **Step 5: Browser check.** Log/phases/about screens + reminders/sailing modals
  show `DONE` upper-right; round id upper-left; tapping DONE closes.

- [ ] **Step 6: Commit.**
```bash
git add docs/js/screens.js ui/header.py ui/modals.py tests/
git commit -m "feat(ui): DONE header convention (round id left, DONE right)"
```

---

### Task 9: Players detail modal

**Files:**
- Create class `PlayersDetailModal` in `docs/js/screens.js`
- Create class `PlayersDetailModal` in `ui/modals.py`
- Modify: `docs/js/main.js` import (already imports `* as screens`? confirm) +
  `docs/js/screen_play.js` (open it)
- Modify: `tests/scenes.py` (add `players_detail` scene) + `tests/test_modals.py`

**Interfaces:**
- Consumes: `token`, `circ_btn` helper, `modalHeader`, `CounterState`,
  `commit_touched`, `setCommit`/`touchCommit`.
- Produces: `PlayersDetailModal(game)` — full-screen inline grid editing every
  player's threat + willpower; `onButton` returns `"close"`; edits are live +
  logged. Opens from `["players_detail"]` and the Questing-for card.

- [ ] **Step 1: Web helper `circBtn`.** In `docs/js/screens.js` add
  `function circBtn(ctx, cx, cy, r, glyph, pen=pal.tan)` → `disc(btn)` +
  `arcRuns(bevel_l ring)` + centred glyph (from the mock). Callers push a **≥24px**
  Button separately (the drawn circle is r≈11, the hit-rect is 24×24 centred).

- [ ] **Step 2: Web class.** `PlayersDetailModal`: header via `modalHeader(ctx,
  game, "Players", this.buttons)`. For each player row (label `P{i+1}`, first-player
  marked): a Threat editor and a Willpower editor, each = circular `−` button
  (Button `[key,i,-1]` 24×24), a `token` (Button `[key,i,"edit"]` 24×24 → opens a
  `CounterModal` for ±5), a circular `+` button `[key,i,1]`. Threat edits →
  `game.adjustThreat(i, ±1)` + log; Willpower edits → `game.setCommit(i, commit±1)`
  (auto-sets `commit_touched`) + log; opening the willpower editor calls
  `game.touchCommit(i)`. Layout: rows from y≈`HEADER_H+16`, step 56; threat editor
  centred x≈150, willpower editor x≈330; column captions "Threat"/"Willpower".
  `onButton`: `−/+` mutate + `return null`; `edit` → `["modal", new CounterModal(...)]`
  (nested — return it; main loop stacks? if not, inline a ±5 row instead — see
  note); `close` → `return "close"`.

  > Nested-modal note: the main loop holds a single `modal`. If nested modals
  > aren't supported, implement the ±5 editor **inline** in this modal (tap the
  > token cycles a small `CounterState` shown in place) rather than opening
  > `CounterModal`. Verify against `docs/js/main.js` modal handling before choosing.

- [ ] **Step 3: Wire open.** `screen_play.js` `["players_detail"]` and `["wp"]` →
  `["modal", new PlayersDetailModal(game)]`. Ensure `PlayersDetailModal` is exported
  and imported where modals are constructed.

- [ ] **Step 4: Browser check.** Open from the Players zone + Questing-for; adjust a
  threat and a willpower; confirm the willpower ring on the play screen goes gold
  after editing.

- [ ] **Step 5: Firmware mirror** (`ui/modals.py` `PlayersDetailModal`, `circ_btn`
  helper in `ui/widgets.py`). Snake_case; `token(d, pal, ...)`.

- [ ] **Step 6: Scene + tests.** In `tests/scenes.py` add:
```python
def _players_detail_modal():
    from ui.modals import PlayersDetailModal
    hw = FakeHardware(); pal = Palette(hw.display); g = _game()
    for i, c in enumerate((3, 4, 2, 2)):
        g.set_commit(i, c)
    m = PlayersDetailModal(g); m.draw(hw, g, pal)
    return hw, m
```
  Register `"players_detail_modal": _players_detail_modal` in `SCENES`.
  Run: `python3 -m pytest tests/ -q`  Expected: PASS (lint covers the new scene;
  all −/+/edit hit-rects ≥24).

- [ ] **Step 7: Commit.**
```bash
git add docs/js/screens.js docs/js/screen_play.js ui/modals.py ui/widgets.py tests/
git commit -m "feat(modals): Players detail (inline grid, circular +/-)"
```

---

### Task 10: Progress detail rework

**Files:**
- Modify: `docs/js/screens.js` (`QuestingProgressModal`)
- Modify: `ui/modals.py` (mirror)
- Modify: `tests/scenes.py` (`_questing_progress_modal` add history + side quests)
- Test: `tests/test_modals.py`, `python3 -m pytest tests/ -q`

**Interfaces:**
- Consumes: `modalHeader`, `token`, `circBtn`, `icon`/`flag` glyphs, `wxSmall`,
  `ring`, `disc`, `quest_history`, `HEADINGS`.
- Produces: reworked `QuestingProgressModal` — `Current | Target` circular editors,
  per-row complete/remove, location-remove prompt, weather-radio heading, a
  bottom-anchored by-round chart.

- [ ] **Step 1: Web — header + columns.** Replace the modal's top row with
  `modalHeader(ctx, game, "Progress", this.buttons)`. Column captions
  `"Quest points"` (left), `"Current"` (x≈178), `"Target"` (x≈300).

- [ ] **Step 2: Web — stat rows.** Lift `stat_row2`/`val_editor2`/`icon_btn` from
  `scratchpad/mock_stats.py`. Each row (Quest, Location, side quests): label; a
  **Current** editor (circular −/+, `token` with progress ring); a **Target** editor
  (circular −/+, **dim disc + dim ring only, no progress fill** — draw `disc(well)`
  + `arcRuns(...,dim)` + value, not `token`). Non-main rows add a **complete**
  circular button (`icon_btn "done"` → flag, green) and a **remove** circular button
  (`icon_btn "x"` → red X). All −/+/complete/remove/edit hit-rects **≥24px**.
  Handlers mutate `quest.progress/points`, `active_location.*`,
  `side_quests[i].*`; `exploreLocationIfDone()` after a location progress bump.

- [ ] **Step 3: Web — complete vs remove logging.** Complete on Location →
  `logEvent("Active location Explored")` then clear; on side quest →
  `logEvent("Side quest N completed")` then splice. Remove → `"...removed"`. (Only
  the log wording differs.)

- [ ] **Step 4: Web — Location remove prompt.** Remove on the Location opens a small
  in-modal prompt (3 buttons, each ≥24px): **Replaced** (→ `LocationPickModal`
  "change" style, set new points), **To staging** (→ specify threat contribution via
  a `CounterState`, then `game.staging += contribution` + clear location + log),
  **Discard** (clear + log). Implement as an internal `this.locPrompt` state the
  `draw`/`onButton` branch on (avoid nested modals).

- [ ] **Step 4b: Web — Add location when none exists.** When `!game.active_location`,
  render a **`+ Add location`** button (≥24px, styled like `+ Side quest`) in the
  Location row's place. Tapping it sets `game.active_location = {points: 3,
  progress: 0}` and logs `"Active location added (card effect)"`; the Location row
  (with Current/Target editors + complete/remove) then appears for editing. This is
  for card effects that place a location outside the Travel phase.

- [ ] **Step 5: Web — heading radios.** If `game.sailing`: four circular weather
  radios (`disc(well)` + active `ring(gold)` + `wxSmall(i, cx, cy, 7, active?null:dim)`),
  packed close (stride ≈40), each a ≥24px Button `["hd_set", i]` → `game.heading = i`
  + log. (Replaces the old ± heading stepper.)

- [ ] **Step 6: Web — bottom chart.** Absolutely position the by-round chart near
  the bottom (cy0≈344): a divider, "THIS GAME - BY ROUND", column headers `R{n}`
  for the last N (`quest_history.slice(-8)`), and rows keyed by icon
  (`WILLPOWER` gold, `THREAT` **black** on a lighter stripe rect, `TRAIL` green with
  green `+n` / **red for `n<=0`**, `WHEEL` heading tinted). Numbers only; no buttons.

- [ ] **Step 7: Browser check.** Open Progress detail: current/target rings (target
  dim), complete/remove on location+side, location-remove prompt paths, weather
  radios, and the bottom chart matching the mock.

- [ ] **Step 8: Firmware mirror** in `ui/modals.py` (`QuestingProgressModal`).
  Lift the mock's Python directly (it already uses `d.set_pen`/`d.rectangle`/
  `d.triangle`); swap the mock's `P[...]` for `pal.*` and pass `pal` to `token`/
  `wx_small`.

- [ ] **Step 9: Scene + tests.** Update `_questing_progress_modal` in
  `tests/scenes.py` to seed side quests + `quest_history`:
```python
def _questing_progress_modal():
    from ui.modals import QuestingProgressModal
    hw = FakeHardware(); pal = Palette(hw.display); g = _game()
    g.sailing = True; g.heading = 1
    g.side_quests = [{"points": 5, "progress": 2}]
    for wp, st in [(16, 12), (14, 14), (22, 11)]:
        g.resolve_quest(wp, st)
    m = QuestingProgressModal(g); m.draw(hw, g, pal)
    return hw, m
```
  Run: `python3 -m pytest tests/ -q`  Expected: PASS (lint + updated
  `test_modals.py` expectations; every −/+/complete/remove/radio ≥24px, no text
  collisions in the chart — verify column stride keeps numbers apart).

- [ ] **Step 10: Commit.**
```bash
git add docs/js/screens.js ui/modals.py tests/
git commit -m "feat(modals): Progress detail rework (current/target, chart, radios)"
```

---

### Task 11: Integration verify

**Files:** none (verification only) — plus any fixups the checks surface.

- [ ] **Step 1: Full suite.** Run: `python3 -m pytest tests/ -q`  Expected: PASS
  (all layout scenes lint-clean, all modal/gamestate tests green).

- [ ] **Step 2: Regenerate any previews (optional).**
  Run: `python3 tools/preview.py play_quest_commit /tmp/p.png` and inspect a few
  scenes to confirm the device-faithful render matches the mock.

- [ ] **Step 3: Browser walkthrough.** Serve `docs/`, play a full round with 1 and
  4 players: both zones on every phase, both detail modals, staging ±, sailing on/off,
  a stage clear, a fail round; confirm `quest_history` chart fills and the willpower
  ring tracks commit.

- [ ] **Step 4: Confirm no stray references.** `grep -rn "_chips\|_progressRow\|
  _commitRow\|_headingProgressCard" docs/js ui` returns nothing.

- [ ] **Step 5: Commit any fixups; do NOT deploy.** Device deploy happens only in
  the main session (per `CLAUDE.md`), separately from this plan.

---

## Self-Review

**Spec coverage:** primitives (T2) · shadow (T1) · commit_touched (T3) ·
quest_history (T4) · flipped Players zone (T5) · flipped Progress zone + caps (T6)
· rewired taps + staging ± + reveal copy (T7) · DONE header everywhere (T8) ·
Players detail (T9) · Progress detail: current/target + dim target + complete/
remove + location prompt + weather radios + bottom chart (T10) · firmware lockstep
(each task) · scenes + lint green (T5,T6,T9,T10,T11). All spec sections mapped.

**Placeholder scan:** none — code is inline or lifted from the cited proven mock;
the two judgement calls (nested-modal support in T9; DONE-vs-Cancel scope in T8)
are called out explicitly with a decision rule, not left vague.

**Type/name consistency:** `token(d, pal, ...)` (Python) vs `token(ctx, ...)`
(web) is intentional and stated in T2. Button ids used across tasks:
`players_detail`, `progress_detail`, `wp`, `stg-`, `stg+`, `close`, `hd_set`,
`hd-`/`hd+` removed. `commit_touched`, `quest_history`, `touch_commit`/`touchCommit`
consistent T3/T4/T9.

## Open decisions to confirm at execution

1. **Nested modals (T9):** does `docs/js/main.js` / `main.py` support a modal
   opening another modal? If not, the ±5 editors go inline. Check first.
2. **DONE scope (T8):** this plan applies DONE to the header + dismiss/live-edit
   modals and keeps explicit Apply/Cancel where a cancel is semantically load-
   bearing (Sailing apply, Elimination choices). Confirm that matches "change them
   all to DONE," or widen to every modal.
