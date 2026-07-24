---
title: Stats redesign — two compact zones
type: design-note
tags:
  - lotr-lcg/design
  - stat-system
related:
  - "[[stat-system]]"
  - "[[design-review]]"
  - "[[roadmap]]"
---

# Stats redesign — two compact zones

Replace the four stacked stat rows on the play screen (`_chips`, `_commitRow`,
`_progressRow`, `_totalsRow`) with **two half-width zones** — **Players** (left)
and **Progress** (right) — freeing the lower screen for tips. Builds on
[[stat-system]] (colours) and [[design-review]] (the "companion, not dashboard"
goal). Milestone M1 in [[roadmap]].

> [!info] Decided with the user (2026-07-23)
> Smooth **arc** rings (not faceted). **Thin** borders, **small** values —
> compact is the point. Each zone is **one big tap-target** → a detail view.
> Device-faithful mock: `scratchpad/mock_stats.py` →
> [artifact](https://claude.ai/code/artifact/5bf204c3-0aca-446a-80a7-adaae057a3cf).

## Goal
- **Compact**: both zones **flip their axis** so they occupy only ~80px tall (vs
  ~270px stacked today) — players in **3 rows**, progress in **2**. Everything
  below is tip space, and it no longer grows with player count.
- Present on **every main play view** (resource_planning, quest_*, travel,
  enc_*, combat_*, refresh). Not on setup / resolution / game-over.

## Layout

```
 Players zone ───────────────┬ Progress zone ─────────────
 P    [1]  2   3   4         │  Q     L    S1        (wheel)
 helm (32)(44)(18)(27)       │ (10)  (3)  (3)        (heading)
 sun  ( 9)( 5)( 7)( 6)       │           quest points remaining
 ────────────────────────────┴────────────────────────────
   … freed tip area (Questing for / Staging during quest; note; CTA) …
```

### Players zone — flipped matrix (3 rows)
- **Players are columns; stats are rows.** Row 1 = player-number headers
  (`1..4`), row 2 = threat, row 3 = willpower. The far-left column holds the row
  labels — a bold **`P`** over the **helm** (threat) over the **sunburst**
  (willpower). Data / icons / colours are exactly as before, just transposed.
- Each value sits in a **circle** (`token`): a dark well disc + a thin arc ring +
  the small value centred.
- **First-player marker** on that player's number header — dark number on a gold
  chip (the ribbon adapts from a left-edge band to a column-header mark).
- **Threat ring** — proportional `threat / elimination`; **red** when
  `threat ≥ elimination − 10`, else **gold**; track dim. Value gold, `OUT` red
  when eliminated (per [[stat-system]]: danger = the ring, never the number).
- **Willpower ring** — **uniform** (full ring, one colour), a *committed-this-
  round* state light: **gold = touched this round**, **dim = carried from last
  round**. See data model. Value gold.
- **3 rows regardless of player count** — the vertical saving. Columns are packed
  tight (spacing ≈ the old row spacing).

### Progress zone — flipped (header + one stat row)
- **A header row of terse labels + exactly one circle row below (never more).**
  Labels: **`Q`** (quest), **`L`** (location), **`S1…S3`** (side quests), and the
  **wheel** icon for sailing (**always the last column**).
- Token value = **remaining** (`points − progress`); ring = `progress / points`.
  The **sailing token** = 4 arc quadrants (lit `4 − heading`, dimming from the
  upper-left) + centred weather glyph, no text.
- A single small **"quest points remaining"** caption under the row.
- **Column cap**: only as many columns as fit the zone width. If side quests
  overflow, **keep the oldest on screen** (the rest live in Progress detail).
  Order: Q, L, oldest→ side quests, sailing last.
- Zones are **not equal halves** — the divider falls wherever the players zone
  ends; the progress zone takes the remainder. Columns packed tight (spacing ≈
  the players' row spacing).

## Primitives (device-faithful, web + firmware in lockstep)
Add to `ui.js` and `ui/widgets.py`:
- `disc(cx, cy, r, pen)` — filled circle as per-scanline rect runs.
- `arc_runs(cx, cy, R, r, a0, a1, pen)` — a ring/arc band between radii `r..R`
  and angles `a0..a1` (0° = top, clockwise), emitted as per-scanline rect runs.
  **This is the whole "device can't draw arcs" answer** — the arc *is* a stack of
  1px rects, so it renders through the existing rect pipeline and the layout
  linter unchanged.
- `ring(cx, cy, R, w, frac, fill, track)` — full track then a `frac` sweep.
- `token(cx, cy, R, w, value, vpen, frac, fill, track, vscale=2)` — well + ring +
  centred value; the shared building block for every matrix/progress cell.
- `wx_small(idx, cx, cy, r, pen=None)` — a **tiny** sun / cloud / rain / storm
  built from `disc`/rect/tri, for the small sailing token + heading radios (the
  24px `SUN/CLOUD/RAIN/STORM` masks are too large there); `pen` forces one colour
  for an inactive radio. The small **wheel** header uses the existing `WHEEL_SM`.
- Header labels sit one clear line above their token row (no touching).

No new icons and no `gen_web_data.py` run (these are code, not generated data).

## Data model
Add `commit_touched` (bool) per `Player`, in `gamestate.js` first then
`gamestate.py`:
- **Reset to false** at round start (`endRound`, and setup→round-1) for all.
- **Set true** when a player's willpower is opened *or* adjusted during the
  commit phase (opening the editor is enough — not only a value change).
- Drives the willpower ring: during `quest_commit` → `touched ? gold : dim`;
  once past commit → **locked gold**. Value itself is the persisted `commit`
  (carried from last round = the "dim" reading until re-touched).
- Serialize in `toDict`/`fromDict` (default false).

### Round history (feeds the Progress-detail chart)
Add `quest_history` (list) to `GameState`, appended **once per round at quest
resolution** (`resolveQuest`):
`{ round, willpower, staging, outcome ("success"|"fail"|"tie"), n, heading }` —
`n` = progress gained (success) or threat gained (fail), `0` on a tie; `heading`
recorded only meaningful when `sailing`. Serialize in `toDict`/`fromDict`
(default `[]`); may be **capped** (e.g. last 20) to bound state size. The chart
shows the newest entries.

## Detail views (full-screen modals — existing pattern)
**Header convention (all modals):** the round id (e.g. `R3`) is pinned
**upper-left**, the title centred, and a **`DONE`** button sits **upper-right** —
replacing the old `X` / `< back` close controls everywhere (a global change to
the existing modals too).

- **Players detail** (new): full-screen **inline grid** — every player row shows
  Threat and Willpower as **`token` values flanked by circular −/+** (same
  language as Progress detail); tapping a **number** opens the ±5 stepper.
  First-player marked. Willpower edits update `commit`, the willpower
  total, and set `commit_touched`. Reached from the **Players zone** tap and the
  **"Questing for"** card. Replaces per-chip `CounterModal` + per-player
  `CommitModal` as the primary edit path (those widgets may be retired or reused
  internally).
- **Progress detail** (extend `QuestingProgressModal`) — all controls in the
  **circular design language**:
  - **Per-target editors reuse the `token` widget**, two columns headed
    **`Quest points: Current | Target`**. Each of Quest, Location, and every
    **side quest** has a **Current** (progress) token drawn as the **progress
    ring**, and a **Target** (points) token drawn in the **dim style only — no
    progress bar** — each flanked by **circular −/+**.
  - **Every non-main row** (Location, side quests) carries two circular buttons:
    **mark complete** (flag) and **remove** (`X`). *Complete* vs *remove* only
    changes how the event is **logged** ("Location explored / Side quest
    completed" vs "…removed").
  - **Removing the active Location prompts** for what happened: **replaced** by a
    new location (set its points), **moved back to staging** (specify its threat
    contribution → auto-increment staging threat), or **discard / other**. The
    **main quest cannot be removed**.
  - **When there is no active location, a `+ Add location`** control creates one
    (default points, then edit via its row) — for card effects that place a
    location outside the Travel phase.
  - **Heading = circular weather radios** (Sun / Cloud / Rain / Storm), packed
    **close together**; the **active facing is marked by its ring**. A setter for
    card-effect / retcon changes — *not* the sailing-test flow (`SailingModal`).
  - **A per-round questing chart** (`quest_history`) is **absolutely positioned
    near the bottom** of the view, so the editor rows above can grow with side
    quests. Compact grid, **icon row-labels** — willpower / staging / result /
    heading (heading row only when `sailing`) — with a **fixed column count** =
    the most recent rounds (older fall off). **Staging renders black** (enemy-
    threat convention) on a **lighter row stripe**; the **result** cell is
    **green for `+progress`**, **red for `0` (tie) or `−threat`**; heading tinted
    by facing.
  - Reached from the **Progress zone** tap.
- **Sailing test** (`SailingModal`) is **unchanged** and still used for the
  `quest_sailing` phase (the actual test). The Progress-detail heading selector is
  only a setter, not the test flow.

## Rewired interactions
| Tap | Opens |
|---|---|
| Players zone (anywhere) | Players detail |
| Progress zone (anywhere) | Progress detail |
| "Questing for" card | Players detail (willpower) |
| "Staging area" card — centre | big-edit `CounterModal` (as today) |
| "Staging area" card — left / right third | inline **−/+** staging |

## Per-view application
- The two zones render at the top of every main play view (a shared `_zones()`).
- **"Questing for" / "Staging area"** totals stay **only** on `quest_commit` /
  `quest_staging`, in the freed tip band (unchanged from today, minus the copy fix
  below). Staging keeps its `CounterModal` plus the new inline −/+ thirds.
- Per-view **tips / CTA** logic is unchanged.
- `setup_game`, `quest_resolution` (spreadsheet), and game-over screens keep their
  current layouts.

## Copy & theme
- Staging reveal caption: `reveal up to +N` → **`+N reveal estimate`**.
- **Text drop-shadow pen → dark gray** (new `pal.shadow`, was near-black
  `bevel_d`) so dark values (the black staging number) stop blurring into their
  own shadow. Global tweak in `ui.js` + `ui/theme.py`; `bevel()` chrome keeps
  `bevel_d`.

## Port plan (iron rules)
1. **Web first**: `ui.js` primitives → `gamestate.js` (`commit_touched`) →
   `screen_play.js` zones + rewired taps → `screens.js` (Players detail,
   Progress-detail extension). Verify live in the browser.
2. **Firmware**: mirror into `ui/widgets.py`, `gamestate.py`, `ui/screen_play.py`,
   `ui/modals.py` — method-for-method.
3. `python3 -m pytest tests/` green; **update/add layout scenes** for the new
   zones + both detail views (the linter runs over every scene).
4. Deploy to the Presto (main session only) and soak.

## Later / out of scope
- **Stage-contextual reveal estimate** (per-quest reveal count instead of the
  living-player heuristic) — flagged by the user as a later improvement.
- Inline threat −/+ directly on the matrix (fast input, M3) — for now edits go
  through the detail view.
