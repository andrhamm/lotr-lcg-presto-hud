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
| `DISPLAY` | 3 | Screen and modal titles |
| `BODY` | 2 | **Default.** Anything read as a sentence or a name |
| `LABEL` | 1 | ALL-CAPS section labels; dense tabular metadata |

> [!note] The primary CTA is `BODY`, not `DISPLAY`
> An earlier draft of this table claimed the CTA was `DISPLAY`. It cannot be:
> the bottom CTA has 424px of usable width, and `Next Phase: Combat (Player
> Attacks)` measures **495px at `DISPLAY`**. Every phase CTA overflows. The
> CTA earns its emphasis from size *and position* — full width, pinned to the
> bottom, `btn_ok` green — not from the type scale alone.

> [!note] Title bars are `DISPLAY`, always, and never ALL CAPS
> "Screen and modal titles" is one row of that table, not two. `draw_header`
> used to pick its tier from the title's character count (`BODY if len > 12`),
> so the title bar changed size as a round advanced — `Planning` at `DISPLAY`,
> `Questing: Staging` at `BODY` — and `modal_header` separately hardcoded
> `BODY`. Measurement retired the rule: the narrowest span a title has is
> **360px** (a two-digit round stamp beside `Set.`), and every title fits
> there at `DISPLAY` with 12–300px to spare.
>
> Casing follows from `LABEL`'s. ALL CAPS is how this system *demotes* text,
> so a title bar wearing it says the opposite of what a title bar is for. Use
> Title Case: it is what 23 of the 31 titles already used, and phase names
> (`Questing: Staging`, `Combat: Shadow Cards`) are the game's own proper
> nouns. A subtitle under a title stays `LABEL` and grows the bar to 52px.

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

Red and green carry the phase-block convention and the elimination ramp. Using
them decoratively breaks the one piece of colour vocabulary a player has to
learn.

> [!note] The phase block is colour-only
> It used to print `FRAMEWORK` / `YOUR WINDOW` label rows above each section.
> They were dropped: the bar already says it, the terms were rulebook jargon
> the player never sees on a card, and two label rows cost ~20px on every
> phase screen — the same vertical space that was pushing text down to
> `LABEL`. Settings → Help teaches the pairing (red = happens anyway, green =
> your window), which is the one place the words still belong.

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

All play-screen copy lives in `viewcopy.py`, from which `docs/js/viewcopy.js`
is generated. One edit, not two, and drift is structurally impossible rather
than merely discouraged.

- Sentence case for prose, ALL CAPS for `LABEL` chrome.
- **ASCII only.** The device font has 82 glyphs; `→`, `−`, `’` and friends
  render as garbage. Write `->`, `-`, `'`. Worse than ugly: `BITMAP8_W`
  measures an unknown glyph as 4px, so a curly quote passes every layout test
  and only breaks on the device.
- **No spaced dash. Use two sentences.** A dash invites a trailing clause, and
  the trailing clause is where vague copy hides — splitting one such sentence
  is what exposed that "resolve each When Revealed" was narrower than the rule
  it paraphrased.
- **Third person. Never "you".** The Presto sits between four players, so
  "your threat" has no referent and "1 enemy engaged with you" is
  unanswerable. Name the actor, using the Rules Reference's own vocabulary:
  *the active player* (one player acting alone), *each player* (everyone, in
  player order), *the first player* (token holder), *the players* (the table
  as a group).
- **Bold trigger words are reserved.** `Action`, `Forced`, `Response`,
  `When Revealed`, `Travel`, `Surge`, `Doomed` name printed card abilities.
  Never use one to describe a framework step: a draft opened a step with
  "Forced, not optional", but RR defines `Forced` as "a bold trigger word" for
  mandatory triggered abilities and never applies it to engagement.
- **Never name a mechanic the copy cannot afford to define.** "Each check
  engages…" leans on a term the screen never explains, and every later mention
  inherits the debt. Say what the player does instead.
- **Do not restate the obvious.** If a competent player already knows it, it is
  not worth a line. Prefer a fact the app computed, or a consequence of the
  rules they may not have connected. This is *not* a ban on explaining why a
  step exists.
- **"In player order" leads the sentence it governs.** It frames the whole
  instruction, so a reader needs it before they picture the action.
- Never ship an unverified rules claim — see [[../../../CLAUDE|Iron rule 4]].
  A truncated rule is a wrong rule, which is why truncation needs an
  affordance rather than a silent cut.

### Loop views

Four views are genuinely loops (Planning, engagement checks, both combat
halves). Each is drawn with one shape: a **framing line** saying what the whole
loop is, the **diagram**, and an optional **note**. The framing line comes
*before* the diagram — it is what tells a reader whether they are looking at
one pass or a rotation.

Draw a loop when its body has two or more steps, or when something happens
between them; otherwise say it in a sentence. Loop exits always read
`Repeat until <condition>`: a question-shaped rung asks the player to work out
the answer at the moment they want to be told it.

## Enforcement

Rules that are only written down decay. Each of these is a test:

| Rule | Gate |
|---|---|
| Prose is never `LABEL`-sized | `tests/test_typography.py` |
| Only numerals/wordmarks above `DISPLAY` | `tests/test_typography.py` |
| Every title bar is `DISPLAY` | `tests/test_typography.py` |
| No title bar is ALL CAPS | `tests/test_typography.py` |
| Every touch target is reachable by some tap | `tests/test_layout.py` (L7) |
| Every ink/ground pair clears WCAG AA (4.5:1) | `tests/test_contrast.py` |
| `dim < muted < tan` stays separable | `tests/test_contrast.py` |
| Touch targets ≥ 24px, nothing off-screen, no text collisions | `tests/test_layout.py` |
| Content text clears the nav rule | `tests/test_layout.py` (L6) |
| A round costs ≤ 33 taps | `tests/test_tap_budget.py` |
| Copy is ASCII, third person, no spaced dash, no reserved trigger words | `tests/test_viewcopy.py` |
| Generated web-twin mirrors are fresh | `tests/test_viewcopy.py` |
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
