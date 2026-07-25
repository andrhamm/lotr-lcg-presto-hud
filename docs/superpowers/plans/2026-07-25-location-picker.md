---
title: Data-driven location picker
type: plan
status: draft
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

> [!note] Status
> Draft plan, not groomed. Numbers below are measured against the current
> compiled catalog, not estimated.

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

## Open questions

1. **Group by encounter set, or one flat list?** Median 6 fits a page; max 14
   does not. Flat + pager is simpler; grouped matches the side-quest picker's
   drill and tells you which set a card came from.
2. **Should Travel prefill the threat contribution from the card, or keep it
   editable?** Prefill-and-editable is the obvious answer, but it changes a
   number the player may already have adjusted.
3. **Worth widening the gather list first?** Running
   `build_hob_enrichment.py --refresh` over the remaining scenarios would
   lift coverage well past 108, at ~20s/scenario (see CLAUDE.md's warning
   about the cold run). Independent of this work, but it is what decides how
   often the picker has anything to show.

## Gates

- `python3 -m pytest tests/` green, including the layout linter over the new
  scenes.
- A test asserting the union resolves *Passage Through Mirkwood* to its six
  locations with the quest points and threat above — the numbers come from
  the compiled catalog, so a build regression that drops the join fails here.
- Both twins byte-identical in strings and sizes.
