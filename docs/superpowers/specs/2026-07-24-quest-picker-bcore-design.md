# Quest Picker (M4-B core) — Design

Status: approved 2026-07-24. Second sub-project of [[roadmap|M4 · Quest awareness]];
consumes the [[2026-07-24-card-data-pipeline-design|M4-A card catalog]]. Device
mocks (device-faithful, `tools/preview.py`): `scratchpad/mock_quest.py` →
artifact. See [[quest-index]] and [[stats-redesign]].

## Purpose

Turn the compiled card catalog into gameplay: pick a scenario, preload its stage
sequence, and guide the pre-round-1 setup — replacing today's manual "type quest
points" step. What began as "a picker" is really a **quest-mechanics program**;
B-core is the first, foundational slice.

## M4-B family (decomposition)

| Piece | Scope | Depends on |
|---|---|---|
| **B-core** (this spec) | Setup-phase flow (Player Setup → Scenario Setup → cycle/scenario pick → Scenario Options → **Quest Setup R0 phase**); model (`scenario` / `stages` / `side`); catalog load; the **pre-round-1 first flip** (1A→1B) | M4-A catalog |
| **B-resolve** | **Guided resolution flow** on progress edit / quest success: active-location-first → explore → overflow to quest → clear → **advance + flip** → conditional-advancement handling | B-core model |
| **B-modal** | Read-only stage/card info modal (all text + quest points), paging every stage; per-stage **"Tips" button (disabled)**. Reached from Quest Setup + Progress detail | B-core model |
| **B-sidequest** | Picker for the 14 *player* side quests → `side_quests` track | M4-A catalog |
| **B-icons** | Set/scenario icons: `lotr-lcg-assets` SVGs → device bitmap masks + `encounterSet`→icon mapping | — |
| **B-data** | Curated `packName` → **cycle + source(official/ALeP) + release-date** map; Hall-of-Beorn **sets-to-gather** (`IncludedEncounterSets`) enrichment | M4-A |
| **B-tips** | Scrape Vision of the Palantir blog → per-stage strategy tips (feeds B-modal's Tips button) | B-modal |

**B-core builds first; B-resolve builds last** — it's the capstone that ties
resolution together once the picker, modal, side-quests, icons, and data are all
in place. The middle siblings (B-modal / B-sidequest / B-icons / B-data / B-tips)
are ordered flexibly between them. B-core leaves the hooks they need (icon slots,
a disabled Tips button, a resolution entry point).

## Verified mechanics (rulebook + catalog survey, Iron rule #4)

- **The A→B flip is pre-round-1.** Setup step 7 "Follow Scenario Setup
  Instruction": resolve stage 1A's setup text, **flip to 1B, then round 1
  begins**. Round 1 starts on 1B with quest points live.
- **The flip recurs at every advance.** "Players proceed from side A to side B on
  each stage." Each advance reveals the next A-side (story / `When Revealed`),
  then flips to B (points). A-sides are dense with `When Revealed` (207 hits
  across the catalog); the setup/flip moment triggers effects.
- **Resolution order:** progress fills the **active location first**; a location
  with progress ≥ its quest points is **explored and discarded**; overflow goes
  to the **quest card**; quest points cleared → **advance stage** (flip). (B-resolve.)
- **Conditional advancement is common:** ~137 of ~400 stage-cards have **0 quest
  points**, and B-sides carry `Victory` (63) / `cannot [advance until…]` (209) —
  many stages advance by defeating/exploring/objective, not by placing progress.
  (Handled in B-resolve; B-core must not assume points-only.)
- **Branching is broad:** 39 branch stages across 23 scenarios; selection is
  usually "**first player** chooses" (63/73) not "at random" (2/10) → branch
  prompt default = *choose*.
- **Some cards have C–H sides** (epic/multiplayer variants; 50 faces). The
  `faces` list handles them, but standard-play A/B is B-core's scope; epic is out.

## Scope

**In scope (B-core):**
- The Setup-phase flow (six screens below), tap-only, up/down pagination.
- Model extension + catalog load + the pre-round-1 first flip (1A→1B) and preload.
- Difficulty + Mode selection with a conditional/contextual explainer.
- The `packName → cycle + source + releaseDate` fields on the index (the curated
  map itself is **B-data**, but B-core defines/consumes the fields; ships with the
  official cycles mapped, ALeP flagged).
- Both twins; host tests + layout scenes.

**Out of scope (B-core):** in-game advancement/resolution (**B-resolve**);
read-only card modal (**B-modal**); side-quest picker (**B-sidequest**); set
icons (**B-icons**, B-core shows slots + names); full sets-to-gather list &
release dates data (**B-data**, B-core shows the fields + partial); strategy tips
(**B-tips**, disabled button); epic-multiplayer C–H handling.

## Header convention

All these screens use the standard top bar: **round id left (`R0` during setup),
title centre, settings link right (`Set.`)** — not a "SETUP" label.

## Setup-phase flow (six screens)

1. **Player Setup** — player count + starting threat per player (today's
   `SetupScreen`, reframed).
2. **Scenario Setup** — source gate: two buttons, **Official Scenarios**
   ("Fantasy Flight Games content") / **Community Scenarios** ("Community created
   content"). No ALeP text, no tip. (ALeP is already in the catalog — see B-data.)
3. **Pick Cycle** *(modal)* — cycle list (each: name · **release date** ·
   chevron), up/down pager, back → Scenario Setup. Community's list shows
   **ALeP-prefixed** cycles.
4. **Choose Scenario** *(modal)* — header `Choose Scenario` / small `Cycle: <X>`;
   **radio + Submit**, no chevron, no stage-count; each row shows the **release
   date**. Back → Pick Cycle. Submit → Scenario Options.
5. **Scenario Options** — the scenario title (tap → re-open the chooser modal) +
   **scenario icon** (slot); **SETS TO GATHER above the form** (each set name +
   icon slot); **Difficulty** dropdown (default Standard) + **Mode** dropdown
   (Normal | Nightmare); a **conditional/contextual tip** shown only for a
   non-standard choice — Easy → "remove every encounter card whose set icon has a
   gold ring (the difficulty marker)" (verified); Nightmare → "swaps in a
   separate, harder encounter deck — sold as its own product". CTA → Quest Setup.
6. **Quest Setup** — the **R0 pre-round-1 phase screen** (not a modal): the
   standard **Players & Progress zones** (quest shows stage 1A), a **distinct
   scroll-style tip** (double gold border + ribbon, unlike the normal note tips)
   carrying the **1A setup text to resolve**, a button opening the **read-only
   card modal** (B-modal), and the primary CTA **Flip to Side B → N qp**, which
   resolves the first flip and begins **round 1** with 1B live.

## Model extension (gamestate, both twins in lockstep)

- `scenario`: `null` (custom) or `{ slug, name, pack, cycle, source, kind,
  nightmare: bool, mode: str }`. `source ∈ official | alep`.
- `stages`: a **snapshot** of the picked scenario's `quest.stages`
  (`[{ stage, branch?, cards:[{ questPoints, victory, sailing,
  faces:[{side,name,text}] }] }]`), copied into the save (self-contained, stable
  if the catalog changes).
- `stage_idx`, `card_idx` (chosen branch card), and **`side`** (`"A"`/`"B"`; the
  shown face). `quest.points` derives from
  `stages[stage_idx].cards[card_idx].questPoints`.
- **Preload / first flip (R0):** on entering Quest Setup, `stage_idx=0`,
  `card_idx=0`, `side="A"`, points = 0 (A has none); the Flip CTA sets
  `side="B"`, loads the B-side quest points, and enters round 1.
- **Advancement is deferred to B-resolve.** B-core only performs the pre-round-1
  first flip; subsequent advances/flips + conditional handling are B-resolve.
- `scenario == null` → today's manual `setup_game` flow (custom / uncatalogued),
  unchanged (backward compatible).

## Data, cycle, source, dates

- **Index up front:** `docs/data/index.json`, extended by **B-data** with
  `cycle`, `source` (official/ALeP), and `releaseDate` per scenario, from a
  curated `packName`-keyed map (verified against the product list). B-core
  defines/consumes these fields; unmapped packs → `cycle:"Other"`, `source`
  inferred, logged.
- **ALeP split:** the catalog already contains some ALeP (`The Oath` / pack "Dark
  of Mirkwood"; player packs "Dwarves of Durin", "Elves of Lórien"). No upstream
  flag exists, so `source` comes from the curated map.
- **Sets-to-gather:** the *list* of encounter sets per scenario is not in
  DragnCards (only each card's own set). B-core shows the scenario's own set +
  a partial note; the full list is **B-data** (Hall-of-Beorn `IncludedEncounterSets`).
- **On pick:** load `docs/data/scenarios/<slug>.json` — web `fetch` (async, brief
  loading state), firmware `json.load` from flash `/data/` (sync).

## Both twins, pagination

Web-first then firmware ([[../CLAUDE|Iron rule #1]]). Long lists reuse the Log
screen's pager (a `page` field, `PER_PAGE`, Up/Down + "N/M"), shown only on
overflow — no drag-scroll, no new input plumbing (tap-only; `hardware.poll()`
unchanged).

## Testing

**Host (pure logic, no network):**
- `preloadScenario(scn)` seeds stage 1, `side="A"`, points 0; the flip sets
  `side="B"` + B-side points. `toDict`/`fromDict` round-trips `scenario` +
  `stages` + `stage_idx`/`card_idx`/`side`.
- Cycle/source grouping + scenario filtering from a fixture index (Nightmare
  excluded from the scenario list; ALeP under Community; `cycle:"Other"` fallback).
- Pagination math (mirrors the Log tests).

**Layout scenes** (`tests/scenes.py`, linter + `tools/preview.py`):
`scenario_source`, `pick_cycle`, `choose_scenario`, `scenario_options`
(Standard / Easy / Nightmare tip states), `quest_setup` (R0 phase view). Each
asserts hit-targets ≥ 24px, no text collisions.

`python3 -m pytest tests/` stays green ([[../CLAUDE|Iron rule #3]]).

## File touch list

- `docs/js/gamestate.js` + `gamestate.py` — model fields, preload, first flip,
  serialization. (No in-game advance — B-resolve.)
- `docs/js/screens_other.js` / new screen modules + firmware `ui/screen_*` — the
  six screens + pager; Quest Setup reuses the two-zone stats layout.
- `docs/js/main.js` + `main.py` — route the Setup-phase sequence; per-scenario
  load on pick.
- `docs/js/screen_play.js` + `ui/screen_play.py` — `setup_game` becomes the
  Custom-quest manual path only.
- `tools/build_card_data.py` — accept/emit `cycle`/`source`/`releaseDate` fields
  (map data itself lands with B-data); `tests/test_card_data.py` covers presence.
- `tests/scenes.py`, `tests/test_*` — scenes + model/grouping tests.

## Success criteria

1. Official → Core Set → Passage Through Mirkwood → Scenario Options (sets-to-
   gather shown) → Quest Setup shows stage **1A setup text**; **Flip to Side B**
   loads **8 qp** and begins round 1 — no typing.
2. Flight of the Stormcaller preloads **sailing on**; a branched quest (Passage
   st.3) is represented (advance/branch prompt itself is B-resolve).
3. Nightmare/Easy tips show only on non-standard selection with the verified text;
   Standard+Normal shows none.
4. Community lists ALeP-prefixed cycles; Custom quest still reaches today's manual
   flow.
5. Tap-only with Up/Down paging; standard `R0 · title · Set.` header; hit-targets
   ≥ 24px. Web + firmware in lockstep; pytest green with new tests + scenes.

## Cross-cutting decisions (log)

Difficulty + Mode kept as **two dropdowns** (not segmented). Sets-to-gather sits
**above** the form/tip. Tip is **conditional** (non-standard only) + contextual.
Quest Setup is a **phase screen with the zones**, not a modal. Branch default =
*choose*. Icons/dates/sets-lists/tips are **sibling data tasks** so B-core stays
model + flow. Epic-multiplayer (C–H) deferred.

## To confirm at implementation time

- Re-mock Quest Setup as the R0 two-zone phase view (device-faithful) before
  coding it.
- Exact rulebook wording for the flip prompt + When-Revealed handling copy.
- The curated `packName` map values (cycle / source / date) — B-data.
