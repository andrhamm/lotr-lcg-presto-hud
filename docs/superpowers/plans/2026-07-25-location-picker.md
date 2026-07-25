---
title: Data-driven location picker
type: plan
status: done
tags:
  - lotr-lcg/plan
related:
  - "[[2026-07-24-quest-picker-bcore-design]]"
  - "[[2026-07-25-design-system]]"
---

# Data-driven location picker

Replace the blind "travel to a location with N quest points" stepper with a
pick-from-the-scenario list, keeping manual entry as the escape hatch. Same
shape as the side-quest picker that just shipped (`SideQuestPickModal`).

> [!success] Status
> **Shipped.** Numbers below were measured against the compiled catalog, not
> estimated, and the gate test pins them. See [[#What shipped]] for the three
> open questions and how they were answered.

## Why now

Two entry points guess today:

| Site | Today |
|---|---|
| `LocationPickModal` (Travel phase) | Stepper defaulting to **3** quest points, and a separate "contribution" stepper defaulting to **2** |
| `QuestingProgressModal` "+ Add location" | Appends `{points: 3, progress: 0}` with no prompt at all |

Both numbers are invented. The catalog knows the real ones.

## The data — and the join that is missing

A scenario's own JSON only carries cards whose `encounterSet` is the
scenario's own set. **91 of the 108 scenarios that have a gather list are
missing cards from their other sets**, and 81 of 398 scenario files contain
no locations at all.

The cards are not absent from `docs/data/` — `build_card_data.py` emits a
file per encounter *group*, including sets that ship no quest card. So
`Spiders of Mirkwood`'s locations live in `scenarios/spiders-of-mirkwood.json`.
The picker therefore has to **union across the gather list**:

```python
for name in scenario["includedSets"]:          # committed HoB enrichment
    pack = load(f"scenarios/{slugify(name)}.json")
    locations += pack["encounter"]["location"]
```

Measured over the whole catalog:

- **295 of 309** `includedSets` entries resolve to a card file; **14 do not**.
- Locations per scenario after the union: **min 0, median 6, max 14**
  (before the union: median 2).
- Exactly **1** scenario of 108 would still offer zero locations.

*Passage Through Mirkwood* resolves to six, with real values:

| Location | Quest points | Threat |
|---|---|---|
| Necromancer's Pass | 2 | 3 |
| Enchanted Stream | 2 | 2 |
| Old Forest Road | 3 | 1 |
| Forest Gate | 4 | 2 |
| Great Forest Web | 2 | 2 |
| Mountains of Mirkwood | 3 | 2 |

### What the picker gets for free

Locations carry **both** numbers the flow currently asks a human to guess:
`questPoints` **and** `threat`. Travel removes a location's threat from the
staging area, which is exactly the modal's existing "contribution" field — so
picking a card fills in both, instead of two hand-set steppers.

## Scope

**In:**
- `quest_catalog.locations_for(scenario, data)` (+ JS mirror) — union across
  `includedSets`, falling back to the scenario's own set when it has no
  gather list. Sorted by name, deduped by `(name, encounterSet)`.
- A picker replacing `LocationPickModal`'s stepper: list of
  `name · Nqp · threat`, radio + Travel, **Manual** for anything not in the
  list. Grouped by encounter set when the union spans more than one — the
  same sphere-first drill as the side-quest picker, if the flat list runs
  long (median 6 fits one page; max 14 needs the pager either way).
- `QuestingProgressModal`'s "+ Add location" routes through the same picker
  via the existing pending-flag pattern rather than appending blind.
- Both twins, scenes for each step, layout linter.

**Out:**
- Tracking *which copies remain* in the encounter deck. `quantity` is in the
  data (2x Old Forest Road), but the HUD does not model the deck and should
  not pretend to.
- Location card text / When Revealed. That belongs to the card reference, not
  a picker.
- Encounter-side side quests, treacheries, enemies. Locations only.

## Fallbacks, and why Manual stays

Manual is not a courtesy, it is load-bearing:

- **~290 quest scenarios have no gather list at all** (the committed
  enrichment covers 108), so they fall back to their own set — median 2
  locations, and 81 files have none.
- **14 `includedSets` names resolve to no card file.**
- Custom / uncatalogued quests have no catalog entry by construction.
- Card effects put locations into play that the scenario never "gathers".

So the picker must degrade to exactly today's stepper, never to a dead end.

## What shipped

The three open questions, and how they were answered.

### 1. Flat list, not a grouped drill

Re-measured over the whole catalog with the union in place: **154 quest
scenarios, min 0 / median 5 / max 14 locations** (*Mount Gundabad*), and only
**10** scenarios exceed one page. A grouping step would cost a tap on *every*
travel to save paging on those ten. Flat + pager it is — six rows a page, the
same geometry as `SideQuestPickModal`.

The encounter set is not on the row either. It was going to be the thing
grouping bought you, so it is worth saying why it turned out unnecessary:
**no scenario in the catalog gathers two same-named locations from different
sets** (checked, zero collisions), so the name alone is unambiguous — and the
player is holding the card. `locations_for` still carries `set` per entry if
a future view wants it.

### 2. Both numbers come from the card; Manual is the editable path

A location prints `questPoints` **and** `threat`, and travelling removes that
threat from the staging area — precisely the modal's old hand-set
"contribution". So picking a row fills in both, and there is no third
confirm-the-numbers step: that would reintroduce the guess the feature exists
to delete. When the table needs a different number (a card effect, an
uncatalogued location), **Manual** is right there and is exactly the old
stepper.

### 3. Widening the gather list: not needed, and deliberately not done

The fallback turned out to carry it. With `location_set_slugs` falling back
to the scenario's own set, only **3 of 154** quest scenarios come up empty —
and those open straight on the manual stepper, which is today's behaviour.
Re-running `build_hob_enrichment.py --refresh` (~20s/scenario, 40+ min cold)
would improve the *median*, not the *floor*, and stays independent of this
work.

### Shape as built

`LocationPickModal` grew a step in front of its stepper rather than becoming
a second modal class — the stepper already **was** the manual fallback, so a
separate picker would have had to hand off to it. Two steps, `list` and
`manual`, and which one it opens on is decided by whether the catalog
returned anything.

Both entry points now route through `game.pending_location_pick`
(`{mode, back}`) rather than constructing the modal inline, because the union
is a catalog read that neither `ScreenPlay.on_button` nor a modal's
`on_button` can do mid-tap. `back` is how one modal serves both callers:
`"play"` falls through to the play screen, `"progress"` sets
`pending_progress_detail` so the Progress modal you tapped "+ Add location"
from reopens. The web twin brackets its fetch with the existing
`modalPending` guard, so there is no flash of the screen underneath.

One deliberate non-change: the Progress modal's row caps its title column at
118px, so most location names truncate there ("Old Forest .."). That is the
same cap the catalog side-quest names already live with, and widening it
means re-laying out that row — out of scope here.

## Gates

All met:

- `python3 -m pytest tests/` green — **1019 passing**, including the layout
  linter over six new scenes (`location_pick`, `_selected`, `_change`,
  `_paged`, `_manual`, `_no_catalog`).
- `test_locations_for_unions_across_the_gather_list` asserts *Passage Through
  Mirkwood* resolves to its six locations with the quest points and threat in
  the table above. A build regression that drops the join collapses it to the
  two cards in Passage's own file and fails here.
- Both twins verified byte-identical in behaviour: the Python gate cases were
  replayed against `docs/js/quest_catalog.js` under node (union, own-set
  fallback, missing set file, dedupe, null→0, multi-face, empty) and match on
  every one.
- Walked in the browser against the real compiled data: both entry points,
  Travel and change mode, the pager, Manual and back, and every exit path.
  `loadLocations('passage-through-mirkwood')` → 6 with no console error;
  an unknown slug → `[]` with one warning and the manual stepper.
