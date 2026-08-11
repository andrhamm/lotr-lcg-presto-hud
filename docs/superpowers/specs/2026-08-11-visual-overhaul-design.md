---
title: Visual overhaul — skins, honest type, and a design pane
type: design-note
tags:
  - lotr-lcg/design
related:
  - "[[2026-07-25-design-system]]"
  - "[[design-review]]"
  - "[[roadmap]]"
---

# Visual overhaul — skins, honest type, and a design pane

A major overhaul of the HUD's **visual language**. Structure, flow and game
terminology are out of scope and do not change. Everything else — palette,
chrome, element vocabulary, composition, and type — is in scope.

The overhaul is run as an **exploration**, not as a single proposed look:
candidate directions are built, rendered device-faithfully, and compared, and
the decision is made against real renders. This document specifies the
apparatus that makes that comparison honest and the sequence it runs in.

## Why this needs apparatus at all

Three prior attempts were rejected (`design/design-review.md:72`) and one of the
stated reasons — *"the bitmap font read as a toy"* — was a judgment about
letterforms that **no mockup has ever displayed**. `tools/preview.py:19` renders
text in Menlo; `docs/js/ui.js:100` renders it in Courier New. Both are
metric-faithful (per-character advance comes from `BITMAP8_W`) and both are
glyph-substituted.

So the app has been rethemed more than once by looking at pictures of a font it
does not use. Fixing that is a precondition, not a nicety.

## Constraints (fixed, not design choices)

The device offers exactly four calls: `set_pen`, `rectangle`, `triangle`,
`text` (`tests/fake_hardware.py:47`). No lines, no circles, no gradients, no
alpha, no antialiasing. Rings are scanline spans of rectangles
(`ui/widgets.py:474`); icons are 1-bit masks decoded to runs
(`ui/icons.py:652`).

A visual language therefore has five levers and no others:

1. Palette (arbitrary RGB pens)
2. Shape composition (rectangles and triangles)
3. 1-bit iconography
4. Bevel / depth treatment
5. Type — a font choice plus integer scales

Hardware: `Presto(full_res=True)` → 480×480 PicoGraphics, `bitmap8`
(`hardware.py:19`). Touch, no drag gestures. Fill costs 5.1 Mpx/s; a full
`clear()` is 45 ms; a tap must stay off the storage path.

## Scope decisions

| Question | Decision |
|---|---|
| What changes | Visual language only |
| What is frozen | Game terminology; all copy in `viewcopy.py` |
| Envelope | Palette, chrome, element vocabulary, composition, type — all fair game |
| How the look is chosen | Explore candidates, then decide against renders |
| Review surface | A Claude Design project, via the `DesignSync` tool |
| Screens covered | All 118 scenes |

## Component 1 — the skin

A **skin** is plain data holding every visual literal in the app. After this
lands, no module contains a hardcoded colour, bevel thickness, border weight or
type binding.

**Colour.** `ui/theme.py` already funnels colour through an `RGB` map plus a
`Palette` that builds pens from it (`theme.py:35`), and `Palette.shaded()`
already proves pens must be derivable from numbers rather than dimmed. A skin
supplies that `RGB` map wholesale; `Palette(d, skin)` builds every pen from it.
`threat_pen()`'s thresholds move into the skin — where a stat turns amber is a
visual decision.

**Chrome.** The parameters are currently literals spread through
`ui/widgets.py`: `bevel(..., t=2)` (`widgets.py:37`), `PILL_CAP`,
`_pill_slash(t=3)`, ring widths, border weights, notch sizes, `BAND_PAD`. These
become named skin fields.

That field list is the vocabulary a direction gets to speak with, so it is a
first-class deliverable rather than a mechanical extraction. A direction that
wants flat-no-bevel, or heavier gold rules, or square rather than notched
pills, must be expressible **without editing a widget**. Anything not
expressible is either a hero cut (below) or a missing skin field.

**Type.** Which font, and what `DISPLAY` / `BODY` / `LABEL` resolve to within
it. The current 3 / 2 / 1 is specific to `bitmap8`; `bitmap14_outline` is
larger at scale 1 and needs different numbers.

**Web twin.** Skins are generated into `docs/js/skins.js` by
`tools/gen_web_data.py`, carrying the `GENERATED` header and byte-compared by
`tests/test_viewcopy.py` — the same treatment the existing five generated files
get.

> This is iron rule **2**, not a violation of iron rule 1. Rule 1 governs new
> *features* (built in `docs/js/` first, then ported). Shared data has always
> flowed Python → generated JS, and a skin is shared data. Hand-mirroring a
> palette across two languages is precisely the drift rule 2 exists to prevent.

**The default skin is the current look, extracted verbatim.** With one skin
defined, every render must be pixel-identical to the baseline captured on
2026-08-11 and every existing test must pass unchanged. If either fails, the
extraction is wrong.

## Component 2 — glyph-faithful host rendering

`tools/build_fonts.py`, following the pinned-upstream pattern of
`tools/build_icons.py`: `tools/data/fonts.SOURCE.txt` holds the
`pimoroni/pimoroni-pico` repo plus a commit sha, and **a plain run fetches
nothing**. `--refresh` re-resolves the pin.

It parses `libraries/bitmap_fonts/font6_data.hpp`, `font8_data.hpp` and
`font14_outline_data.hpp` into the **run-encoded mask format `ui/icons.py`
already uses**, so both host renderers draw glyphs as rectangles and are
pixel-exact against the device by construction.

Three payoffs:

- `preview.py` and the web twin stop lying about letterforms.
- Exact upstream widths **verify `BITMAP8_W`**, the hand-built table every
  layout test depends on. A disagreement means the layout linter has been
  passing on wrong numbers.
- A custom mask face is authored in the same format and needs no second
  mechanism.

**Licensing.** `pimoroni/pimoroni-pico` is MIT, Copyright (c) 2021 Pimoroni
Ltd. The derived mask tables are **committed** (user decision, 2026-08-11),
with attribution in a `NOTICE` file, and the data-policy section of `CLAUDE.md`
gains a line recording the carve-out and its reason: the data is small, its
licence explicitly permits redistribution, and the alternative is a network
fetch in CI, which that same section calls a smell.

**Hershey is deferred.** `libraries/hershey_fonts/` ships under Pimoroni's MIT
licence, but the Hershey glyph set carries its own upstream provenance. It is
researched before any derived data is committed. Until it clears, the Hershey
option is judged on device photographs only; if it does not clear, that option
drops rather than shipping on an unverified licence.

## Component 3 — the design pane

`tools/build_design_pane.py` renders scene × skin PNGs through
`tools/preview.py`, then emits **one HTML card per screen** holding that
screen's variants side by side, each labelled. Every card opens with a
`<!-- @dsCard group="…" -->` marker so the Design System pane indexes it.

Groups follow the app's own areas: Play, Phases, Progress, Quest, Setup,
Modals, System.

Publication is `DesignSync`: `create_project` → `finalize_plan` →
batched `write_files` (256 files per call). Output lands in a gitignored build
directory, the same posture as `docs/data/`.

Cards wrap **real pipeline renders**. No card contains a CSS impression of a
device widget; the pane's only job is arrangement and labelling.

## Component 4 — sequencing

**Font is not a peer axis.** Changing it changes character widths, which
changes wrapping, which changes every layout the linter checks. Choosing a
palette on top of a font that is later dropped throws the palette work away.

### Round 1 — type probe

Four options, current colours held fixed, six representative screens:

| Option | What it is |
|---|---|
| A | `bitmap8` — the status quo |
| B | `bitmap14_outline` — outlined bitmap, larger at scale 1 |
| C | Hershey vector (`gothic` / `serif`), `set_thickness()` above the 1px default |
| D | A custom 1-bit mask face, drawn through the `icons.py` run machinery |

Probe screens: `play_quest_staging` (dense chrome), `play_planning` (loop
diagram), `players_detail_modal` (tokens and rings), `choose_scenario` (list
rows), `quest_card_modal_long_text` (long prose), `log` (tabular metadata).

**Cost bound on D.** `bitmap8` is drawn by C inside PicoGraphics; a mask face
is a Python loop. Extrapolating from the measured icon figure (~200 rects →
2.8 ms), a 40-character `BODY` line is roughly 400 rects ≈ 4–5 ms, so a
text-heavy screen would pay ~40–50 ms against a 45 ms full-clear budget. If D
wins it is expected to win as a **hybrid** — mask face for titles, numerals and
wordmarks, `bitmap8` for prose — and the hybrid must be measured on device
before it is adopted.

### Round 2 — look directions

Directions are proposed **after** round 1, against real renders, and are
deliberately not named here: naming four aesthetics before the type result is
guessing. A direction may vary these axes:

- Palette family and semantic assignments
- Chrome weight and depth treatment
- Ring and token style
- Icon density and iconographic register
- Composition, via a hero cut

Round 2 runs across all 118 scenes. Where a direction wants to move regions
within a screen, it gets a **hero cut**: a hand-built variant of 3–4 screens
only, since the skin vocabulary deliberately cannot express composition.

## Testing

**Extraction is provably invisible.** `tests/test_skin_identity.py` renders all
118 scenes under the default skin and compares against committed per-scene
draw-call hashes taken from the 2026-08-11 baseline. Lifting a literal into a
skin field is correct only if not one pixel moves.

**Every existing gate runs per skin.** This is what makes exploration safe
rather than a regression source:

| Gate | Under skins |
|---|---|
| `test_contrast.py` | Every ink/ground pair in every skin clears WCAG AA (4.5:1). A direction that fails is rejected mechanically, not by eye |
| `test_typography.py` | The `dim < muted < tan` ramp survives a repalette; prose is never `LABEL`-sized |
| `test_layout.py` | Re-run per skin — a font change moves text, so collisions and off-screen text are re-proved |
| `test_viewcopy.py` | `docs/js/skins.js` is fresh |
| `test_tap_budget.py` | Unchanged; skins do not touch flow |

**Performance stays flat.** Skin values resolve into `Palette` attributes at
construction, exactly as pens do today (`theme.py:52`), so draw sites read an
attribute just as they do now. Nothing new lands on the 3.35 ms tap path or the
5.1 Mpx/s fill budget.

**New font, new metrics.** Adopting any font other than `bitmap8` requires its
width table to be generated from upstream data, not hand-built, and the layout
suite to be re-run against it.

## Risks

| Risk | Handling |
|---|---|
| Hershey licence unresolved | Option C is device-photo-only until checked; drops if it does not clear |
| `BITMAP8_W` disagrees with upstream | Treated as a found bug, fixed before round 2 rather than worked around |
| Mask-face draw cost | Hybrid scope, measured on device before adoption |
| Skin vocabulary too narrow | Missing expressiveness surfaces as a hero cut; recurring cases become new skin fields |
| Extraction changes a pixel | `test_skin_identity.py` fails the change |

## Out of scope

Information architecture, round flow, tap economy, phase skipping, and the
play-test feedback recorded in `TODO.md` under Ideas. All are real, none are
this project.
