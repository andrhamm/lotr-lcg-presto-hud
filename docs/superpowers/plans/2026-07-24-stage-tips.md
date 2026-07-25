# Per-Stage Strategy Tips (M4-B tips) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill the **disabled "Tips" button** the quest-card modal already renders: short, per-scenario (and where possible per-stage) strategy notes, sourced from the community write-ups the project's quest notes already cite, delivered through the existing generated-catalog pipeline.

**Architecture:** A build tool fetches and parses the source write-ups into a compact tips file (`docs/data/tips.json`, generated + gitignored like the rest of `docs/data/`). The modal loads it through the same catalog-data path and enables the Tips button only where tips exist. Tips are **summarized in our own words**, not verbatim reproductions.

**Tech Stack:** Python stdlib (`urllib`, `html.parser`, `json`) — no new deps. Web ES modules + MicroPython consumers. pytest.

**Context:** The final **B-tips** piece of the M4-B family (see `docs/superpowers/specs/2026-07-24-quest-picker-bcore-design.md` → "M4-B family"). B-core, B-modal, B-sidequest, B-icons and B-data are complete. `QuestCardModal` (in `ui/modals.py` + `docs/js/screens.js`) already draws a per-stage Tips button in a disabled style whose handler returns null — this plan makes it real. The project's own quest notes in `quests/` cite **Vision of the Palantir** (`https://visionofthepalantir.com/`) as their source and are themselves examples of the summarized house style to match.

## Global Constraints

- **`python3 -m pytest tests/` stays green** (Iron rule #3); tests are **fixture-driven with no network** (commit a small captured HTML fixture).
- **Generated, never tracked:** output goes to `docs/data/tips.json`; `docs/data/` is gitignored, built in CI for Pages, copied to flash at deploy. The HTML cache lives in `tools/data/tips_cache/` and is **gitignored**.
- **Optional at build and runtime:** a fetch/parse failure must not fail the catalog build or a Pages deploy, and a missing `tips.json` must leave the Tips button in its existing disabled state. No crashes, no blank panels.
- **Copyright posture — this one is stricter than the card text.** Blog posts are authored prose with a clear owner. **Do not reproduce article text.** Emit only:
  - short **summarized** points in our own words (aim ≤ 140 chars each, ≤ 4 per scenario), and
  - **attribution**: the author/site name and the source URL, stored alongside every tip and **displayed in the UI**.
  If a passage cannot be summarized without effectively copying it, drop it. Record the source URL + retrieval date in the file's provenance block.
- **Be polite to the source:** serial requests, a delay between them, cache on disk, and honor `robots.txt` — **check it first and obey it**; if it disallows the paths, stop and report that instead of proceeding.
- **Two twins in lockstep** for the UI change; touch targets ≥24px; layout linter green.
- **Device budget:** tips must stay small (target well under ~150 KB total) — they ship to Presto flash with the rest of `docs/data/`.

## Data shape

`docs/data/tips.json`:
```json
{
  "generated": "2026-07-24",
  "source": "Vision of the Palantir (https://visionofthepalantir.com/) - summarized, not reproduced",
  "scenarios": {
    "passage-through-mirkwood": {
      "attribution": {"name": "Vision of the Palantir", "url": "https://visionofthepalantir.com/2020/09/05/passage-through-mirkwood/"},
      "general": ["Stay under 40 threat - Hummerhorns engages at 40 and deals 5 damage to one hero."],
      "stages": {"3": ["Beorn's Path cannot be defeated while Ungoliant's Spawn is in play."]}
    }
  }
}
```
`stages` keys are stage numbers as strings; `general` applies to the whole scenario. Both are optional.

## File structure

- `tools/build_tips.py` — new: fetch/cache/parse → `docs/data/tips.json`.
- `tests/fixtures/votp_passage.html` (small captured page), `tests/test_tips.py`.
- `quest_catalog.py` / `docs/js/quest_catalog.js` — `load_tips()` / `loadTips()` (`{}` on failure), `tips_for(slug, stage, tips)` / `tipsFor(...)`.
- `ui/modals.py` / `docs/js/screens.js` — `QuestCardModal`: enable the Tips button when tips exist; add a tips view/panel with attribution.
- `.github/workflows/pages.yml`, `CLAUDE.md` — delivery + docs.

---

### Task 1: Source check + fetcher/parser

**Files:** Create `tools/build_tips.py`, `tests/fixtures/votp_passage.html`, `tests/test_tips.py`.

- [ ] **Step 1: Check `robots.txt` FIRST** — fetch `https://visionofthepalantir.com/robots.txt` and confirm the article paths are allowed for a polite crawler. **If disallowed, stop the whole task, report it, and propose alternatives** (e.g. tips hand-authored from the project's own `quests/*.md` notes, which are already summarized in-house). Record what it said either way.
- [ ] **Step 2: Map the source.** Identify how scenario articles are addressed (the project's own notes cite e.g. `https://visionofthepalantir.com/2020/09/05/passage-through-mirkwood/`) and how to resolve a catalog slug → article URL (a sitemap, an index page, or a slug-in-URL convention). Report the mechanism you found and its reliability.
- [ ] **Step 3: Capture the fixture** — save one article's HTML to `tests/fixtures/votp_passage.html`, trimmed to the relevant content block(s) but structurally faithful.
- [ ] **Step 4: Write failing tests** — `tests/test_tips.py`:

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import build_tips

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "votp_passage.html")

def test_extract_returns_plain_text_blocks():
    html = open(FIXTURE, encoding="utf-8").read()
    blocks = build_tips.extract_blocks(html)
    assert blocks and all(isinstance(b, str) for b in blocks)
    assert not any("<" in b for b in blocks)          # tags stripped

def test_summarize_respects_limits():
    tips = build_tips.summarize(["x" * 400, "short note"], max_len=140, max_tips=4)
    assert len(tips) <= 4
    assert all(len(t) <= 140 for t in tips)

def test_entry_carries_attribution():
    e = build_tips.build_entry("passage-through-mirkwood", "http://example/x", ["a note"])
    assert e["attribution"]["url"] == "http://example/x"
    assert e["general"] == ["a note"]
```

- [ ] **Step 5: Implement** `tools/build_tips.py`: `extract_blocks(html)` (stdlib `html.parser`, strip tags/scripts, return candidate paragraphs/bullets), `summarize(blocks, max_len, max_tips)` (**condense to our own short phrasing** — trim to the actionable clause, drop prose framing; never emit a long verbatim sentence), `build_entry(slug, url, tips, stages=None)`, `fetch(url, cache_dir, delay)`, `build(index_path, out_path, cache_dir, limit=None)`, plus a CLI mirroring `tools/build_hob_enrichment.py`'s flags and its friendly-failure conventions (read that file first).
- [ ] **Step 6: Run tests → PASS.**
- [ ] **Step 7: Smoke run** `--limit 3`, inspect the emitted tips by eye, and **paste them in your report** — they must read as terse original notes in the house style (compare `quests/passage-through-mirkwood.md`'s warning bullets), not as copied sentences. Then a full run; report how many scenarios got tips and the total file size.

---

### Task 2: Wire tips into the quest-card modal (both twins)

**Files:** Modify `quest_catalog.py`, `docs/js/quest_catalog.js`, `ui/modals.py`, `docs/js/screens.js`, `main.py`, `docs/js/main.js`, `tests/scenes.py`, `tests/test_quest_card_modal.py`.

**Interfaces (Produces):**
- `load_tips()` / `loadTips()` → the `scenarios` map from `/data/tips.json` (firmware) or `data/tips.json` (web); `{}` on any failure.
- `tips_for(slug, stage, tips)` / `tipsFor(slug, stage, tips)` → `{"tips": [...], "attribution": {...}} | None` — merges the scenario's `general` with that stage's entries (stage-specific first), returns `None` when there is nothing.

- [ ] **Step 1: Failing tests** in `tests/test_quest_card_modal.py` (it already builds a modal with a stages fixture — follow its conventions):

```python
TIPS = {"p": {"attribution": {"name": "Src", "url": "http://x"},
              "general": ["watch threat"], "stages": {"3": ["branch note"]}}}

def test_tips_button_enabled_when_tips_exist():
    g = _game(); m = QuestCardModal(g, tips=TIPS)          # slug "p" per the fixture
    _draw(m, g)
    tips = next(b for b in m.buttons if b.id[0] == "tips")
    assert m.on_button(tips) == "redraw"                    # opens the tips view, no longer inert

def test_tips_view_shows_attribution_and_stage_specific_first():
    g = _game(stage_idx=2); m = QuestCardModal(g, tips=TIPS)
    m.on_button(next(b for b in _draw(m, g).display and m.buttons if b.id[0] == "tips"))
    hw = _draw(m, g)
    drawn = " ".join(c[1] for c in hw.display.calls if c[0] == "text")
    assert "branch note" in drawn and "watch threat" in drawn and "Src" in drawn

def test_tips_button_stays_disabled_without_tips():
    g = _game(); m = QuestCardModal(g, tips={})
    _draw(m, g)
    assert m.on_button(next(b for b in m.buttons if b.id[0] == "tips")) is None
```
(Adjust the exact construction to match the modal's real constructor; `tips` must default to `{}`/`None` so existing call sites keep working.)

- [ ] **Step 2: Run → FAIL. Step 3: Implement** — the modal gains an optional `tips` argument; the Tips button renders enabled (normal palette) only when `tips_for(...)` is non-empty, and toggles a tips panel showing the tip lines wrapped, with the attribution name + URL in `pal.dim` beneath. A Back/Tips toggle returns to the card view. Mirror in both twins.
- [ ] **Step 4: Wire the load** — the router already loads catalog data (index, scenario, icons) when entering the picker; load tips there too and pass them where `QuestCardModal` is constructed (both entry points: the Quest Setup button and the Progress-detail quest row). Failure → `{}` → button stays disabled.
- [ ] **Step 5: Scenes** — add `quest_card_modal_tips` (tips view open, with attribution). Linter → PASS.
- [ ] **Step 6: Render and LOOK** — the tips panel must wrap cleanly, show attribution, and not collide with the pager/CTA.
- [ ] **Step 7: Delivery** — add the tips build to `.github/workflows/pages.yml` as an optional (`continue-on-error`) step, and extend the CLAUDE.md "Card data" section.
- [ ] **Step 8: Verify** — full suite green; browser walkthrough: open the card modal for a scenario that has tips, tap Tips, confirm the notes + attribution render and Back returns to the card. Report console errors.

---

## Self-Review

**Spec coverage:** the per-stage Tips button the quest-card modal already stubs → Task 2; sourced from the community write-ups the project already cites → Task 1; delivered through the established generated-data pipeline with optional semantics → Tasks 1 & 2. Explicitly handled: the copyright constraint (summarize + attribute, never reproduce) and the robots.txt gate, which can legitimately halt the task.

**Placeholder scan:** Task 1 carries complete test code and makes the two genuine unknowns (robots.txt permission, slug→URL mechanism) explicit steps with reporting requirements and a defined stop/fallback, rather than assuming access. Task 2's test snippets note that constructor details must be matched to the real modal.

**Type consistency:** `build_entry` emits `{attribution, general, stages}` in Task 1, exactly the shape `tips_for` consumes in Task 2 and the file's Data-shape block documents.
