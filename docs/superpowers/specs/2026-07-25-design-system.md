---
title: Design system
type: design-note
tags:
  - lotr-lcg/design
related:
  - "[[stats-redesign]]"
  - "[[roadmap]]"
---

# Design system

> [!warning] Why this exists
> Text has shipped too small more than once, and each time it was fixed
> locally and the reason evaporated. There was no written rule, so the same
> instinct — *ran out of room, shrink the text* — kept winning. This document
> is the rule; the tests named in [[#Enforcement]] are the part that actually
> holds.

The HUD renders with a fixed **bitmap8** font on a 480×480 screen, using only
rectangles, triangles and text. Everything below follows from that: there are
no fractional sizes, no antialiasing, no scroll views. Space is decided at
design time, not at runtime.

## Type scale

Defined in `ui/theme.py` and mirrored in `docs/js/ui.js`. **Use the names.** A
bare `1` at a draw site is how prose ends up unreadable.

| Name | Multiplier | What it is for |
|---|---|---|
| `DISPLAY` | 3 | Screen and modal titles; the primary CTA |
| `BODY` | 2 | **Default.** Anything read as a sentence or a name |
| `LABEL` | 1 | ALL-CAPS section labels; dense tabular metadata |

Above `DISPLAY` there is no reading tier — sizes 4–9 belong to **numerals and
wordmarks** (the threat counters, the sailing dial, `LOTR LCG`, `VICTORY!`).
Those are chosen by the widget that owns the numeral, never at a call site,
and a sentence may never use them.

### The rule

> **If a player reads it as a sentence, a name, or an option, it is `BODY`.**

Card text, tips, rules captions, empty states, option rows, button labels,
sphere names, settings tiles. All `BODY`.

`LABEL` is for text read as *chrome* rather than content, and it is
**ALL CAPS** so the casing carries the demotion rather than the size alone:

- Section labels above a group — `SETS TO GATHER`, `TIPS`, `SIDE A`, `GAME`.
- Field labels beside a control — `DIFFICULTY`, `THREAT`, `TARGET`.
- Dense tabular metadata where the row count is the point — the log's feed,
  release dates, `2/3` pagers, `+3 more`.

### When BODY does not fit

Running out of room is **not** a reason to shrink text. In priority order:

1. **Say less.** Shorten the copy. Most overflow is a writing problem.
2. **Page it.** A pager is cheaper than unreadable text — the Quest Cards
   reference pages per card side for exactly this reason.
3. **Truncate with an affordance.** Cut the line and mark it `[...] more`,
   with a tap target that opens the full text. Never truncate silently, and
   never let a truncation marker itself get truncated (see below).
4. **Re-lay out.** Give the text the space something less important is using.

Shrinking to `LABEL` is not on the list.

> [!bug] The marker must be measured, not appended
> `line + " [...] more"` then truncate-to-width cuts the marker down to
> `[....` and the affordance silently disappears. Reserve the marker's width
> first, then trim the line to fit. `QuestCardModal._fit` does this; a test
> covers it.

## Colour

Defined once in `ui/theme.py` (`Palette`), mirrored in `docs/js/ui.js`.
Derived from the Revised Core box art — bark, moss, parchment, ember.

### Ink

| Pen | Role |
|---|---|
| `gold` | Emphasis: headings, card names, the value that matters |
| `tan` | Body text — the default ink |
| `muted` | Secondary text still meant to be read |
| `dim` | Metadata, disabled states, attribution |
| `amber` | Section labels, "resolve now" attention |
| `value` | Stat numerals (an alias of `gold`, so stats read as one family) |

`dim < muted < tan` is a deliberate ramp; it is asserted, not assumed.

### Semantic

| Pen | Meaning | Never used for |
|---|---|---|
| `green` | Your window — a thing you may choose to do | Decoration |
| `red` | Framework — happens whether you act or not; danger | Emphasis |
| `amber` | Caution, pending, attention | Body text |

Red and green carry the phase-block convention (`FRAMEWORK` / `YOUR WINDOW`)
and the elimination ramp. Using them decoratively breaks the one piece of
colour vocabulary a player has to learn.

### Ground

`bg` → `card` → `card_hi` → `well` is a depth ramp, darkest first. `border`
and `border_gold` edge them; `border_gold` means "this one matters".

## Elements

| Element | Use it for |
|---|---|
| `panel` | A grouped region of content. Flat, bordered |
| `bevel` | Anything tappable. If it is beveled it is a button, and vice versa |
| `note_panel` | A tip or reminder: gold edge, pipe medallion. Not for data |
| `token` | A stat with a progress ring — the one place a ring means progress |
| `icon_slot` | A 24×24 set/scenario icon, with a placeholder when unmatched |
| `ribbon` | A scroll-style header for the setup tip. Reserved for R0 |

Buttons are **≥ 24px** on both axes — a finger on a 480×480 panel, enforced by
the layout linter. There is no hover state; a control looks tappable or it is
not tappable.

## Copy

- Sentence case for prose, ALL CAPS for `LABEL` chrome.
- **ASCII only.** The device font has 82 glyphs; `→`, `−`, `’` and friends
  render as garbage. Write `->`, `-`, `'`.
- Never ship an unverified rules claim — see [[../../../CLAUDE|Iron rule 4]].
  A truncated rule is a wrong rule, which is why truncation needs an
  affordance rather than a silent cut.

## Enforcement

Rules that are only written down decay. Each of these is a test:

| Rule | Gate |
|---|---|
| Prose is never `LABEL`-sized | `tests/test_typography.py` |
| Only numerals/wordmarks above `DISPLAY` | `tests/test_typography.py` |
| Every ink/ground pair clears WCAG AA (4.5:1) | `tests/test_contrast.py` |
| `dim < muted < tan` stays separable | `tests/test_contrast.py` |
| Touch targets ≥ 24px, nothing off-screen, no text collisions | `tests/test_layout.py` |
| A round costs ≤ 22 taps | `tests/test_tap_budget.py` |
| Both twins render identically | `tests/scenes.py` + `tools/preview.py` |

`tests/test_typography.py` carries a short, reasoned allowlist. Adding to it
should feel like a decision — write down *why*, or fix the draw site instead.

## Adding a screen

1. Sketch it against this scale before writing a draw call. If the content
   only fits at `LABEL`, the layout is wrong, not the type.
2. Build it web-first, then mirror to the firmware ([[../../../CLAUDE|Iron rule 1]]).
3. Add a scene to `tests/scenes.py` — that is what puts it under every gate
   above at once.
4. Render it with `tools/preview.py` and **look at it**. The linter catches
   collisions, not ugliness.
