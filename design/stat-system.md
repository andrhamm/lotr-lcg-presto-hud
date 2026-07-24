---
title: Stat system — colours, icons, layout
type: design-note
tags:
  - lotr-lcg/design
  - stat-system
related:
  - "[[design-review]]"
  - "[[roadmap]]"
  - "[[stats-redesign]]"
---

# Stat system — colours, icons, layout

The consistent way every stat is drawn. Decided with the user; partially
implemented (see status). Sibling: [[design-review]].

## Rules (decided)
**One stat-cell anatomy everywhere:** `[icon] · LABEL · big value · 2px state-bar`.

### Colour by role
| Element | Colour | Notes |
|---|---|---|
| **Threat icon — player** | **red** + charcoal dropshadow | its identity; NOT gold |
| **Threat icon — staging/enemy** | **black/dark** (`pal.outline`) | the enemy-threat distinction |
| **Progress icon (ranger/trail)** | **green** + **brown** dropshadow | progress-token colours (brown + dark green) |
| **Willpower icon (sunburst)** | **gold** | never colour-coded |
| **All stat VALUES** (threat/willpower/progress/totals) | **uniform gold** (`pal.value`) | told apart by icon+label, never by number colour |
| **Danger** | **red BAR only** | value/icon never turn red for danger |

### Danger rule
- The **bottom bar** reddens when **threat ≥ elimination − 10** (i.e. **> 40** at
  the standard 50-elimination). Otherwise the bar is gold.
- Values/icons do **not** change colour by threat level (this was the original
  complaint — no green/amber/red-by-level).

### Value shade
- Warm gold `rgb(214,180,110)` vs lighter parchment `rgb(200,186,144)` are
  **nearly identical** — user didn't care. Using **gold** (`pal.value = gold`).

## Implemented so far (working tree, UNCOMMITTED)
In **both** web (`docs/js/`) and firmware (`ui/`), kept in lockstep:
- New pens: **`pal.value`** (= gold, drives all stat values) and **`pal.brown`**
  (`rgb(104,70,34)`, ranger dropshadow). In `ui.js` and `ui/theme.py`.
- `screen_play` `_chips`: threat value → `pal.value`; helm → **red + `bevel_d`
  charcoal shadow**; bar → red when `threat >= elimination-10` else gold.
- `_commitRow`/`_commit_row`: willpower value green → `pal.value`.
- `_progressRow`/`_progress_row`: ranger → **green + brown shadow**; card values →
  `pal.value`.
- `_totalsRow`/`_totals_row`: "Questing for" value → `pal.value` (staging stays
  dark `pal.outline` per the user's call).
- pytest: 316 green. Verified live in the browser (red helm, green ranger,
  uniform gold values; staging dark).

## TODO (not yet done)
- **Propagate icon colours** to every place the icons appear: the threat/staging
  counter modals, the willpower/commit icons, and the inline trail/helm icons in
  the staging + resolution tips — so nothing contradicts the system.
- Apply the stat-cell system consistently across all phase screens.
- Consider inline threat −/+ (fast input) within the cell.
- Commit the stat-system pass once coherent (web + firmware together).
