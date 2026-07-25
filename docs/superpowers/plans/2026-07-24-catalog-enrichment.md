# Catalog Enrichment — sets-to-gather & release dates (M4-B data) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the quest picker the two facts the DragnCards card DB cannot supply: the **full list of encounter sets a scenario is built from** ("sets to gather"), and each product's **release date** (shown on the cycle/scenario rows). Both land as fields on the generated catalog, consumed by screens that already have slots for them.

**Architecture:** A second, separate enrichment source — Hall of Beorn's export API — is fetched by a build tool and merged into the M4-A catalog output. Enrichment is **best-effort and optional**: when it is unavailable the catalog still builds and the UI falls back to today's behavior (the scenario's own set + a "partial" note; no date on rows).

**Tech Stack:** Python stdlib (`urllib`, `json`) — no new deps. Web ES modules + MicroPython consumers. pytest.

**Context:** The **B-data** piece of the M4-B family (see `docs/superpowers/specs/2026-07-24-quest-picker-bcore-design.md` → "M4-B family"). B-core, B-modal, B-sidequest and B-icons are complete. `ScenarioOptionsScreen` already renders a SETS TO GATHER list (currently just the scenario's own set, with a note that the list is partial) and `PickCycleScreen`/`ChooseScenarioScreen` already render a release-date slot that is currently always empty (all `releaseDate` values are `null`).

## Verified facts (do not re-derive)

- **Hall of Beorn exposes the gather list.** `https://hallofbeorn.com/Export/Search?EncounterSet=<name>&CardType=Quest` returns an array of cards; each quest card carries:
  ```json
  "EncounterInfo": { "EncounterSet": "Passage Through Mirkwood (Campaign)",
                     "EasyModeQuantity": 0,
                     "IncludedEncounterSets": ["Dol Guldur Orcs (Campaign)", "Spiders of Mirkwood"],
                     "StageNumber": 1, "StageLetter": "A" }
  ```
  For Passage that yields Passage Through Mirkwood + Spiders of Mirkwood + Dol Guldur Orcs — exactly the three sets the rulebook lists (rulebook p.26), so the field is trustworthy.
- **Names carry qualifiers** like `" (Campaign)"` that our catalog's set names do not. Normalize before matching/display.
- The API is **paginated at 50 rows** and is a third-party service — be polite (serial requests, small delay), tolerate failures, and cache.
- **Licensing/posture:** same as the card DB — enrichment output is written into the gitignored `docs/data/`, never tracked, and covered by the existing disclaimer + provenance in `index.json`. Add Hall of Beorn to that provenance string.

## Global Constraints

- **`python3 -m pytest tests/` stays green** (Iron rule #3). Tests must be **fixture-driven with no network** — commit a small captured JSON fixture, never call the API from a test.
- **Enrichment is optional at build time:** if the fetch fails or the cache is absent, `build_card_data.py` must still emit a complete catalog (today's fields), and the UI must still work. Never let enrichment failure fail a Pages deploy.
- **Two twins in lockstep** for any consumer change; touch targets ≥24px; layout linter green.
- **Cache to disk** so repeat builds and CI don't re-hammer the API: `tools/data/hob_cache/<slug>.json` — **gitignored** (it contains third-party card data).
- Release dates are `"YYYY-MM"` strings or `null`; never guess a date you cannot source.

## File structure

- `tools/build_hob_enrichment.py` — new: fetch/cache Hall of Beorn per scenario, emit `tools/data/enrichment.json` (**gitignored**) mapping scenario slug → `{"includedSets": [...]}`.
- `tools/build_card_data.py` — merge enrichment (if present) into each scenario file + index entry; extend `PACK_META` with release dates.
- `quest_catalog.py` / `docs/js/quest_catalog.js` — nothing new expected; verify consumers.
- `ui/screen_quest.py` / `docs/js/screens_other.js` — SETS TO GATHER uses the real list; drop the "partial" note when the list is real.
- `tests/fixtures/hob_passage.json` (new, small), `tests/test_hob_enrichment.py`, `tests/test_card_data.py`.

---

### Task 1: Hall of Beorn enrichment fetcher

**Files:** Create `tools/build_hob_enrichment.py`, `tests/fixtures/hob_passage.json`, `tests/test_hob_enrichment.py`.

**Interfaces (Produces):**
- `included_sets(cards)` → sorted, de-duplicated, **normalized** list of encounter-set names for one scenario's card array: take each card's `EncounterInfo`, union `EncounterSet` + `IncludedEncounterSets`, strip qualifiers (`" (Campaign)"`, `" (Nightmare)"`, and any trailing parenthetical), drop empties. Pure — host-tested.
- `fetch_scenario(name, cache_dir, delay=0.5)` → the raw card array for one encounter-set name, reading `<cache_dir>/<slug>.json` when present, else GET + cache. Network only; not host-tested.
- `build(index_path, out_path, cache_dir)` → for every `kind=="quest"` scenario in the catalog index, resolve its included sets and write `{"generated","source","scenarios":{slug:{"includedSets":[...]}}}`. Skips (with a logged count) any scenario the API doesn't answer for.
- CLI: `python3 tools/build_hob_enrichment.py [--index docs/data/index.json] [--out tools/data/enrichment.json] [--cache tools/data/hob_cache] [--limit N]`. `--limit` is for a quick smoke run.

- [ ] **Step 1: Capture the fixture** — `curl -s 'https://hallofbeorn.com/Export/Search?EncounterSet=Passage%20Through%20Mirkwood&CardType=Quest' > tests/fixtures/hob_passage.json`. Trim it to the first 4 quest cards to keep it small (keep the full `EncounterInfo` blocks intact). Confirm it contains `IncludedEncounterSets`.
- [ ] **Step 2: Write the failing test** — `tests/test_hob_enrichment.py`:

```python
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import build_hob_enrichment as hob

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "hob_passage.json")

def test_included_sets_unions_and_normalizes():
    cards = json.load(open(FIXTURE, encoding="utf-8"))
    sets = hob.included_sets(cards)
    assert sets == ["Dol Guldur Orcs", "Passage Through Mirkwood", "Spiders of Mirkwood"]
    assert not any("(" in s for s in sets)          # qualifiers stripped

def test_included_sets_handles_missing_encounter_info():
    assert hob.included_sets([{"Title": "x"}, {"EncounterInfo": {}}]) == []
```

- [ ] **Step 3: Run → FAIL. Step 4: Implement. Step 5: Run → PASS.**
- [ ] **Step 6: Real run** — `python3 tools/build_hob_enrichment.py --limit 5` first (sanity + politeness), inspect the output, then a full run. Report: how many of the ~123 pickable quests resolved a gather list, how many the API had no answer for, and 3 spot-checked scenarios with their lists. Confirm Passage = the three rulebook sets.

---

### Task 2: Release dates

**Files:** Modify `tools/build_card_data.py` (`PACK_META`); Test `tests/test_card_data.py`.

Every pack currently has `"date": None`. Fill them in with verified release dates (`YYYY-MM`).

- [ ] **Step 1: Source the dates.** Use a reliable reference for LOTR LCG product release dates and **cite what you used** — candidates: the Hall of Beorn product pages, the FFG product archive, or Wikipedia's product table. Cross-check at least a few against a second source. **Where you cannot verify a date, leave it `None`** — a null date is acceptable and the UI already handles it. Do not guess.
- [ ] **Step 2: Fill `PACK_META`** dates for every pack you verified. Report coverage (how many of the 106 packs got a date, and which cycles are fully covered).
- [ ] **Step 3: Test** — extend `tests/test_card_data.py` to assert a couple of known dates flow through to index entries (e.g. Core Set = `"2011-04"`, verify before asserting) and that unknown packs still yield `None` without error.
- [ ] **Step 4: Rebuild + verify** — `python3 tools/build_card_data.py`, then confirm the cycle rows would show dates: `python3 -c "import quest_catalog,json; idx=json.load(open('docs/data/index.json')); [print(g['cycle'], g['date']) for g in quest_catalog.cycles_for(idx,'official')]"`.

---

### Task 3: Merge enrichment into the catalog + use it in the UI

**Files:** Modify `tools/build_card_data.py`, `ui/screen_quest.py`, `docs/js/screens_other.js`, `.github/workflows/pages.yml`, `CLAUDE.md`, `tests/*`.

- [ ] **Step 1: Merge at build time.** `build_card_data.py` loads `tools/data/enrichment.json` if present and adds `"includedSets": [...]` to each scenario file (and a `"gatherCount"` to the index entry if useful for the picker). Absent enrichment → the field is simply omitted; everything else is unchanged. Add a test asserting both paths (with and without an enrichment file) using the existing fixture-driven `build()` helper.
- [ ] **Step 2: Provenance.** Extend `index.json`'s `source` string (or add a `sources` list) to name Hall of Beorn alongside DragnCards, and mention it in the disclaimer wording if appropriate.
- [ ] **Step 3: UI.** `ScenarioOptionsScreen`'s SETS TO GATHER list renders the real `includedSets` when present (still capping the visible rows with a "+N more" row as it does today) and **drops the "(full gather-list needs card data - partial)" note** in that case; keeps today's behavior otherwise. Both twins. Update/extend the existing `scenario_options_*` scenes so one covers a real multi-set list, and re-render to confirm the rows + icons still fit.
- [ ] **Step 4: Delivery.** Add the enrichment build to `.github/workflows/pages.yml` **as an optional step** (`continue-on-error`, like the icons step) — CI will use the committed cache if present, otherwise fetch. Extend the CLAUDE.md "Card data" section with the enrichment tool + its cache.
- [ ] **Step 5: Verify** — full suite green; layout linter green; render `scenario_options_*`; browser walkthrough to Scenario Options for Passage Through Mirkwood showing three real sets with icons. Report console errors.

---

## Self-Review

**Spec coverage:** sets-to-gather (the gap B-core explicitly deferred) → Tasks 1 & 3; release dates on cycle/scenario rows → Task 2; both delivered through the existing generated-data pipeline with optional-enrichment semantics → Tasks 1 & 3. Easy-mode per-card quantities are visible in the same API (`EasyModeQuantity`) but stay **out of scope** — the Easy-mode tip already tells the player the physical rule (gold-ring icon), which needs no data.

**Placeholder scan:** Task 1 carries complete test code and a captured-fixture step. Task 2 deliberately does not enumerate 106 dates inline — it specifies sourcing, citation, cross-checking, and an explicit "leave null if unverified" rule, because inventing dates would be worse than omitting them.

**Type consistency:** `included_sets(cards) -> [str]` in Task 1 is the same shape merged as `"includedSets"` in Task 3 and consumed by the UI there; `PACK_META[pack]["date"]` in Task 2 is the existing key already read by `build_outputs`.
