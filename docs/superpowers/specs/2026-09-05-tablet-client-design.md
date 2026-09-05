---
title: Tablet client — design
type: design-note
tags:
  - lotr-lcg/design
  - tablet
related:
  - "[[2026-07-25-design-system]]"
  - "[[2026-08-11-visual-overhaul-design]]"
  - "[[design-review]]"
---

# Tablet client — design

A third client for the tracker: a standalone web app for a landscape iPad
Pro 12.9" (1366×1024 CSS px), served from the same GitHub Pages site as the
web twin and sharing its core modules. The Presto HUD and its web twin are
untouched and stay in lockstep with each other; the tablet is a separate
surface over the same model.

Decided with the user on 2026-09-05 against rendered options. The design
canvas (fourteen artboards, three rounds of feedback) is at
https://claude.ai/code/artifact/53d193be-6148-4f95-8c12-0b11e4d24470 — page
1 is the chosen direction built out, page 2 the two directions not taken.
This document is the durable record; the canvas is the picture.

## Why a third client

The Presto is a 480×480 bitmap surface with a 24 px minimum target and no
scroll. Three consequences shaped everything the user asked for here:

- **Tap economy.** Every step and every action window is its own view, so a
  common round costs 31 taps in `tests/test_tap_budget.py`'s walk (gate 33).
  Playtest feedback: *"loooots of tapping ... when there are no enemies ...
  we can completely skip over combat."*
- **Nothing is static.** The players' threat, the quest, the staging area
  and the log each take the whole screen in turn. The user wants them always
  visible, with more density.
- **No room for context.** Tips are one line; rules text is a paraphrase;
  card images and set icons do not exist.

A tablet has ~8× the pixels and real typography. The question is what to do
with them, and the answer is *not* "the HUD, bigger".

## Scope

**In:** the play loop end to end (setup → rounds → game over), the
scenario picker and overview, the players/quest/staging editors, the game
log with rewind, contextual notes with sources, official rules text behind a
tap, card images, set icons, phase skipping driven by tracked counts.

**Out (explicitly):** syncing with a Presto at the same table, computer
vision of the board (a later effort that fills the same fields), portrait
layout, campaign tracking, RingsDB decks, any change to the Presto's own UI.

## Decisions

Each of these was a user call made against a rendered option. Do not
re-litigate them without a new render.

1. **Structure: B · Transport.** The rulebook's turn sequence as a horizontal
   strip across the top; a left column holding the state rail and a small
   log block; the phase pane in the remaining ~1000×880. Rejected: A "Ledger"
   (a phase column doubling as the log — the column competed with the pane
   for height) and C "Console" (the event stream as nav — nothing future is
   drawn).
2. **The log is a small block at the foot of the left column**, never a
   full-width drawer. "Open ›" goes to a full Game Log screen.
3. **The state rail is three zones** — PLAYERS (red helm), QUEST (green
   trail), STAGING (black helm, inset well ground) — each with its own icon,
   ground and top-edge colour, so the players' side and the encounter deck's
   side never read as one strip. Rail values are read-only status; each zone
   has one tap target, an "Edit ›" chip in its header.
4. **Enemy tracking:** a per-player engaged-enemy count, plus enemies and
   locations in staging. Simple steppers. These feed skip offers and the
   printed-X targets. Computer vision may fill the same fields later.
5. **Action windows are bands on their step's view, not views.** The strip
   still draws every window as a green tick, so timing stays visible. This is
   the single biggest tap saving (eight views per round become bands).
6. **Skips are offered, never taken automatically.** When the tracked counts
   say combat is empty the offer is promoted; when they say otherwise it is
   still available but demoted, and the confirm names the counts.
7. **The players sheet is one screen for all players, no tabs**, opened at
   any time from the Players zone. Everyone-at-once buttons cover Doomed.
8. **Card images are hotlinked from the card database's image host at
   runtime and cached heavily client-side.** Nothing stored in the repo.
9. **Verbatim Rules Reference excerpts ship as a gitignored build artifact**,
   the same posture as the card DB. `rules/README.md`'s "never shipped" line
   is updated to match.
10. **Set icons appear wherever a set is named**, as the pinned icon pack's
    SVGs. The Presto keeps its 24 px masks.
11. **Tap targets are bevelled chips.** The HUD's rule — if it is bevelled it
    is a button, and vice versa — carries over at 44 px.
12. **Base:** `feat/ui-ux-iteration` was fast-forwarded into `main`
    (1099548) so the tablet builds on the delta-replay undo, the `aw_` views,
    the data client and the copy inventory. Not yet pushed.

## Structure

```
┌ strip ─────────────────────────────────────────────────────────────────┐
│ R4  Resource Planning Questing Travel Encounter Combat Refresh End ⏮◀▶⏭│
├ left column 324 ┬ phase pane ────────────────────────────────────────────┤
│ PLAYERS  Edit › │ Title                                    round · step │
│  P1 P2          │ ┃ framework band                          [Rules 3.3 ›]│
│  P3 P4          │ ┃ window band                          [Rules windows ›]│
│ QUEST    Edit › │ counters / loop diagram / lists                       │
│  stage location │ notes panel (tips + Source ↗)             [More notes ›]│
│ STAGING  Edit › │                                                        │
│  threat en. loc │                                                        │
│ GAME LOG  Open ›│ ‹ Back   [skip, when offered]   Next: <phase>          │
└─────────────────┴────────────────────────────────────────────────────────┘
```

### The strip

One segment per phase (Resource, Planning, Questing, Travel, Encounter,
Combat, Refresh, End), each holding one tick per step: a red square for a
framework step, a green round tick for a window. The current step carries
the playhead. Done ticks are lit, future ticks dim, a skippable phase is
dashed amber with its landing named under it. Tapping a tick moves the
replay head there (see Rewind). ⏮ ◀ ▶ ⏭ do the same at round and step
granularity — the transport the branch's Log screen already has.

The strip is the round's map and its scrubber. It is not a tap-heavy
control: in the common round nobody touches it.

### The left column

Three zones, then the log block pinned to the bottom.

| Zone | Icon | Ground | Edge | Content | Editor |
|---|---|---|---|---|---|
| PLAYERS | red helm | `card`, cells `card_hi` | `gold` | 2×2 cells: threat (36 px), 3 px bar (red at elimination−10), willpower commit, engaged (black helm), first-player flag | Players sheet |
| QUEST | green trail | `card` | `green` | stage `n/points` + name, active location `n/points` + name (or "no active location"), `+ side quest` | Quest editor (progress sheet, from the branch) |
| STAGING | black helm | `well` | `outline` | threat, enemies, locations | Staging editor |

Every value here is status. The one tap target per zone is the header's
"Edit ›" chip. This is the rule recorded in `status-vs-control-surfaces`,
applied with room: the 44 px targets live in the sheets and the pane.

The log block shows the last five lines (time, text, ellipsis on overflow)
and a prompt row naming the current step. "Open ›" is the affordance for
the full text; nothing is truncated silently.

### The phase pane

One view per step, as the branch has them (`VIEW_ORDER` minus the `aw_`
entries — see Model). Every view is built from the same parts:

- **Title** (`DISPLAY`) and a `LABEL` line: round, step, first player.
- **Framework band** (red edge) and/or **window band** (green edge), copy
  verbatim from `viewcopy` (`PHASE_FRAMEWORK`, `PHASE_WINDOW`,
  `ACTION_WINDOW_TIPS`, `STAGING`, `TRAVEL`, ...). Each band ends in a
  "Rules <section> ›" chip.
- **Loop diagram** for the four loop views (Planning, Engagement checks,
  Enemy Attacks, Player Attacks): framing line, numbered rungs with a green
  dot where a window opens after the rung, `Repeat until …` exit, note.
  Copy is `LOOP_FLOW` verbatim.
- **Counters** where the step has one contextual stat: Questing for /
  Staging area on Staging, the allocation on Resolution, the engaged-enemy
  steppers on Enemy Attacks.
- **Notes panel**: the pipe medallion, `Notes · <scope>`, one to three tips
  in our own words, a Source chip. "More notes ›" opens the notes sheet.
- **CTA row**: `‹ Back` (plain), the skip (amber) when offered, `Next:
  <phase>` (green). All 64 px tall.

### Modals and full screens

| Surface | Opened from | Holds |
|---|---|---|
| Players sheet | PLAYERS "Edit ›", any time | one row per player: −5 −1 threat +1 +5, willpower ±, engaged ±, distance to elimination; header: All −1 / +1 / +2 |
| Quest editor | QUEST "Edit ›", the stage row | the branch's Progress screen, re-laid out for the width |
| Staging editor | STAGING "Edit ›" | threat, enemies, locations steppers |
| Location picker | Travel "Travel to location", `+ Add location` | in-staging locations first (image, printed threat and quest points, card text), then the gathered sets' locations, then manual entry |
| Rules modal | any "Rules … ›" chip | official text verbatim with the section cited; our timing summary with its source named; FAQ (only when entries exist); related-section chips; Open PDF |
| Notes sheet | "More notes ›" | every note for the scenario, general then per stage, each with its source |
| Game Log | log block "Open ›" | terminal order, filter chips (All, Threat, Quest, Phases, Skips), transport, tap a line then Rewind; a side panel explaining rewinding and listing round summaries; Export |
| Scenario overview | picker → scenario; the QUEST zone's stage name during play | set icon and title, difficulty, sets to gather (icons), stages with points, this scenario's own set as card images with counts, shared sets as chips, notes general and per stage with source, Begin setup |

The picker flow (source → cycle → scenario) reuses the branch's screens'
content at tablet density; it is a list, not a design problem.

## Visual system

Held fixed across the exploration; only structure varied.

- **Colour:** `docs/js/ui.js`'s `pal`, verbatim. Roles unchanged: `gold`
  emphasis and values, `tan` body, `muted`/`dim` secondary and metadata,
  `red` framework and danger, `green` your window, `amber` caution — and on
  the tablet, a skip, because a skip asserts a claim about the table.
  Grounds `bg → well → card → card_hi`.
- **Type:** Alegreya (titles, phase names — the game's proper nouns) and
  Alegreya Sans (everything else), both from Google Fonts with Georgia and
  system-ui fallbacks. `DISPLAY` 34 px, `BODY` 20 px (18 px on secondary
  lines, never lower for a sentence), `LABEL` 13 px caps tracked. Numerals
  are tabular and owned by the widget: 26 / 36 / 40 / 48 / 56 / 84.
- **Stat icons:** the app's own 1-bit masks (`ui/icons.py`) rendered as SVG
  paths with `shape-rendering: crispEdges` — the HUD's pixel DNA at any
  size. Colour rules from `design/stat-system.md`: player threat red with a
  charcoal shadow; enemy/staging threat black with a light edge; willpower
  gold; progress green with a brown shadow; all values gold; danger is the
  bar, never the value.
- **Set icons:** the pinned pack's SVGs (`fill="currentColor"`, 72 px),
  coloured `gold` at 20–52 px.
- **Chips:** bevelled (light top-left, dark bottom-right), `LABEL` caps,
  ≥ 44 px tall except the 30–36 px chips inside zone headers and list rows,
  which sit in ≥ 44 px rows.
- **Copy:** `viewcopy` rules apply — sentence case, third person, no spaced
  dash, reserved trigger words, `BODY` for anything read as a sentence.
  Shared copy stays ASCII because the linter and the Presto need it; the
  tablet renders `->` as an arrow glyph at draw time and may use real
  punctuation in tablet-only copy.

## Interaction model

### Tap economy

The HUD's `tests/test_tap_budget.py` walk, replayed on the tablet:

| Step | HUD | Tablet | Why |
|---|---|---|---|
| Resource, Planning, Commit views | 3 | 2 | the Resource window is a band |
| Adjust one player's commit | 3 | 1 | the Commit pane carries the total counter |
| Commit → Staging | 2 | 1 | window folded |
| Staging +3, Resolve | 4 | 4 | inline steppers, unchanged |
| Resolution → Travel | 2 | 2 | accept the split, next |
| Travel, Encounter, Combat views | 6 | 3 | three windows folded |
| Shadow: +1 threat to everyone | 6 | 3 | Edit, All +1, Done |
| Combat → Refresh → End | 5 | 4 | the Refresh window folded |
| **Total** | **31** | **20** | HUD gate is 33 |
| Same round, no enemies at engagement | — | 19 | the skip replaces two advances |

Eight of the tablet's 20 are `Next` taps; every other tap changes a number.
A tablet tap-budget test gates this at 20 (see Testing).

### Windows as bands

A step's action window is drawn on the step's own view as the green band,
under the framework band. The Planning view is the one exception the
rules note already records: 2.2–2.3 reads "player actions throughout", so
its band says so rather than "after".

This is a per-client policy on the shared model, not a tablet fork of the
flow (see Model → Window policy).

### Skips

`SKIPS` stays the list of what a player may assert. The tablet adds an
*offer state* computed from tracked counts:

- **Promoted** — engaged total 0 and enemies in staging 0: the amber CTA
  reads "No enemies. Skip combat." and the confirm shows the claim.
- **Demoted** — otherwise: the same button, plain, and the confirm reads
  "The tracker shows 2 engaged. Skip anyway?" with the counts.

Both paths go through `skipTo()` and are logged identically ("Skipped …").
The player is still the authority; the app never skips on its own. This is
`its-a-tracker-not-a-referee` applied to skipping.

The landing is unchanged: `lastWindowBefore("refresh")` is `combat_player`
(6.P), and with windows folded the offer moves from `aw_enc_checks` to
`enc_checks`, whose own window is on the view the player is standing on.

### Rewind

The strip's ticks, the transport, and the Game Log's "Rewind to selected
line" all move the replay head (`replay_step`) the way the branch's Back
arrow does. Later entries stay, greyed, until an edit truncates them. A
skip rewinds like any other transition. Nothing new in the model; the
tablet just exposes the cursor in three places.

### Editing

Every change is logged as it happens (the branch's keyed tallies keep
eight stepper taps to one line). Sheets have no Save; Done closes them.
The rail never carries a control.

## Model changes (both twins)

Iron rule 1: these land in `docs/js/gamestate.js` and `gamestate.py`
together, with parity tests. The Presto UI draws none of them.

- **`Player.engaged`** (int, default 0). In `toDict`/`fromDict`, and in
  `snapshot()`/`loadSnapshot()` — the snapshot keys players by index and
  lists fields explicitly (`threat`, `eliminated`, `commit`), so `engaged`
  is added there or the delta engine will not see it.
- **`staging_enemies`, `staging_locations`** (ints, default 0) on the game:
  `toDict`/`fromDict`/`snapshot`, log lines "Staging enemies 1 -> 2",
  keyed tallies like `staging`.
- **`xtargets`:** `enemies_in_play` gains an auto source (engaged total +
  enemies in staging) and `locations_in_staging` gains one (staging
  locations). `xtargets.py` + regenerated `docs/js/xtargets.js`; the
  hand-mirrored `resolve()` gains the two cases.
- **Window policy:** a module-level `WINDOW_POLICY` (`"views"` | `"bands"`),
  default `"views"`, set once by the client at boot. With `"bands"`,
  `nextView()`/`prevView()` step over `aw_` entries and `SKIPS` `from`
  resolves to the phase view. `lastWindowBefore`, `isActionWindow`,
  `enterView`'s window handling and every test under `"views"` are
  unchanged. `tests/test_phase_skip.py` and `test_twin_parity.py` run the
  skip landing and the offering set under both policies.
- **Skip offer state:** `skipOffer(game)` → `{skip, promoted: bool,
  counts}` in both twins (the Presto may ignore it).

## Data and build

### Rules text

`tools/build_rules_text.py` parses the Rules Reference markdown the
existing `tools/build_rules_corpus.py` produces (every numbered step is a
`######` heading) into `docs/data/rules_text.json`: `{section_id: {title,
text, book}}`, gitignored. A `tools/data/rules.SOURCE.txt` pins the PDF URL
and sha, like the card TSV; the plain run fetches nothing when the corpus
is already present. The Pages workflow gains a step (`continue-on-error`,
like icons): fetch the pinned PDF, parse, build. The URL is pinned when the
step is written — FFG's product page blocks scripted fetches, so it is
verified by hand then. `rules/README.md` records the new posture: the
parsed corpus is still not committed; excerpts ship as a build artifact.

The modal's "Timing" section is our own summary keyed by step, kept in
`viewcopy.py` with its source named. The FAQ section renders only when
`rules_text.json` carries `faq` entries; the FAQ PDF is a later corpus.

### Set icons

`tools/build_icons.py` gains `--svg-out docs/data/icons/svg/`, writing the
tarball's encounter-set and expansion SVGs by slug (gitignored, same pin,
same run). The tablet loads them by set name through `quest_catalog.js`'s
existing slug rule.

### Card images

The compiled data carries `image` per card face; the plugin's
`imageUrlPrefix.json` resolves them (`…/cards/English/<id>.jpg`). Measured
2026-09-05: one image is ~157 KB, served without a CORS header and with an
ETag.

- The tablet registers a service worker scoped to `/tablet/`. It caches the
  app shell and `docs/data/` files it has seen, and it caches image
  responses cache-first in a dedicated cache, evicting oldest past a cap
  (start at 200 MB). No CORS means these are opaque responses: they render
  in `<img>` and cache fine, but browsers account opaque entries
  generously against quota — measure on the actual iPad before trusting
  the cap.
- "Begin setup" prefetches the scenario's own set and its gathered sets
  (~40 cards, ~6 MB). Nothing else is prefetched; the catalog is ~1.5 GB
  of images.
- Offline or evicted: the frame shows the name and printed values in place
  of the picture. Never a broken-image glyph.

### Notes

`docs/data/tips.json` already carries `attribution.url` per scenario; the
Source chip opens it. No new fetch. The notes sheet lists `general` then
`stages`.

### Persistence

`db.js`'s `Session`, `History` and `DataClient` are reused. The tablet and
the web twin share an origin, so the key names must not: the constructors
gain a `prefix` (default `lotr-hud-`, tablet `lotr-tablet-`). `DataClient`
is origin-relative and works from `/tablet/` unchanged. The no-stray-IO
rule extends to `docs/tablet/`.

## Code layout

```
docs/tablet/
  index.html          viewport, fonts, sw registration, one <main>
  style.css           tokens (from ui.js pal), type, chips, zones, bands
  sw.js               shell + data + image caches
  js/
    app.js            boot, prefs, Session(prefix), render loop
    strip.js          the transport strip
    rail.js           the three zones + log block
    pane.js           view → pane builder (framework/window/loop/counters/notes/CTA)
    loops.js          the loop diagram
    sheets/           players, staging, quest, location picker, rules, notes
    log.js            Game Log screen
    overview.js       scenario overview; picker flow
    images.js         url for a card face; prefetch a scenario
    icons.js          GENERATED from ui/icons.py masks (tools/gen_web_data.py)
```

Imports from `../js/`: `gamestate.js`, `phases.js`, `viewcopy.js`,
`xtargets.js`, `quest_catalog.js`, `db.js`. Nothing from `ui.js`,
`screens*.js`, `screen_play.js`, `main.js` — those are the 480×480 canvas.

Rendering is plain DOM from template strings: one `render(game)` builds
the strip, rail and pane; event delegation on `<main>` maps `data-act`
attributes to game methods; `Session.record()` after every mutation and
`Session.tick()` on idle, as `main.js` does. No framework, no build step,
ES modules as today.

`tools/gen_web_data.py` gains the mask→SVG output so the stat icons follow
iron rule 2 (generated, byte-compared by `tests/test_viewcopy.py`).

## Testing

`python3 -m pytest tests/` stays the one gate.

| Rule | Gate |
|---|---|
| New fields round-trip, replay and rebase in both twins | `test_gamestate*.py`, `test_gamestate_replay.py`, `test_twin_parity.py` |
| Skip landing, offering set and offer state under both window policies | `test_phase_skip.py`, `test_twin_parity.py` |
| Window policy `"bands"` walks every view without an `aw_` | new `test_window_policy.py` |
| The tablet's common round costs ≤ 20 taps | new `test_tablet_tap_budget.py`: pytest drives a node script over the tablet's action map, the same way `test_twin_parity.py` drives node |
| No `fetch`/`localStorage` outside `db.js` | `test_no_stray_io.py`, scope += `docs/tablet/` |
| Tablet copy is ASCII, third person, no spaced dash, no reserved words | `test_viewcopy.py` (copy lives in `viewcopy.py`) |
| Generated mirrors fresh (`viewcopy`, `xtargets`, `icons`) | `test_viewcopy.py` |
| Every chip ≥ 44 px, every stat value ≥ 26 px, contrast AA on the tablet tokens | new `test_tablet_tokens.py` reads `style.css` tokens and the shared `pal` |
| Screens render and the round walks in a browser | Playwright smoke, opt-in local (`tools/devserver.py`), CI later — the existing TODO card |

## Milestones

Sequence, not the plan. Each is a PR that leaves both twins green.

1. **Model.** `engaged`, staging counts, xtargets auto sources, window
   policy, skip offer state — both twins, parity tests. No UI.
2. **Shell.** `docs/tablet/` boots, loads a saved game, draws the strip,
   the rail and every phase pane with `Next`/`Back`. Tap budget test.
3. **Editors.** Players sheet, staging editor, quest editor, location
   picker. Everyone-at-once buttons.
4. **Log and rewind.** Log block, Game Log screen, transport, tick taps.
5. **Context.** Rules text artifact and modal, notes panel and sheet, set
   icon SVGs, card images with the service worker.
6. **Overview and picker.** Scenario overview, picker flow at tablet density.
7. **Soak.** A real game on the iPad, the way the Presto had one.

## Risks and open questions

- **Opaque-response quota on iPad Safari** is unmeasured. Measure in
  milestone 5 before setting the cap; the fallback is a smaller cap.
- **The FFG PDF URL** is pinned by hand when the build step is written; if
  no stable URL exists, `rules_text.json` is built locally only and the
  Pages modal shows the summary and the product-page link.
- **Planning's window** reads "throughout", not "after"; the band copy
  must say so (already in `rules/action-windows.md`).
- **The Presto ignores the new fields** by design. If a later Presto
  feature wants engaged counts, the model already has them.
- **Same-origin storage:** without the key prefix, opening the tablet and
  the web twin in the same browser would clobber saves. The prefix lands
  in milestone 1's `db.js` change, before any tablet code persists.
