# Tablet milestone 5 — Context — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The tablet shows the official rules text behind every band's "Rules §n ›" chip, our own notes with their sources beside each phase, the set icons wherever a set is named, and card images in the location picker — served from build artifacts and cached on the device.

**Architecture:** Three new build artifacts, all gitignored and produced by pinned tools like the card data: `docs/data/rules_text.json` (verbatim Rules Reference sections, parsed from the liteparse corpus), `docs/data/icons/svg/<slug>.svg` (the icon pack's SVGs, same pin as `icons.json`), and the image URL prefix pinned beside the card TSV. The tablet reads them through `DataClient` (the only file that fetches), renders them with pure string builders, and a classic service worker scoped to `/tablet/` caches the shell, the data files and card images. Nothing here changes game state; the only both-twins change is one `DataClient` method kept in parity.

**Tech Stack:** Python 3 build tools (no new deps; `lit`/liteparse for the corpus in CI, `continue-on-error`), ES modules, a classic (non-module) service worker for old-iPad Safari, pytest driving node.

**Spec:** `docs/superpowers/specs/2026-09-05-tablet-client-design.md` — "Data and build" (Rules text, Set icons, Card images, Notes), "The phase pane" (bands end in a Rules chip; Notes panel), "Modals and full screens" (Rules modal, Notes sheet), "Risks" (PDF URL, opaque-response quota).

## Global Constraints

- **Data policy:** verbatim third-party text is never committed — `docs/data/rules_text.json`, `docs/data/icons/svg/`, and any fetched PDF/corpus stay gitignored; only tools, pins, tests and our own words are committed. `rules/README.md` records the new posture (the parsed corpus still never ships as a corpus; *excerpts* ship as a build artifact).
- **Pinned sources, no-op builds:** every fetcher is a no-op when its output exists; `--refresh` is the only way to re-pin; CI never fetches third-party content except the pinned icon tarball it already fetches and the pinned rules PDF (both `continue-on-error`).
- **Never ship an unverified rules claim:** the modal shows the Rules Reference verbatim with its section cited; the "Timing" section is the band copy `viewcopy` already ships, labelled as this tracker's summary; the FAQ section renders only when `rules_text.json` carries `faq` entries (it will not, this milestone). Notes are `tips.json`'s own text (already our words) with `attribution.url` as the source.
- **I/O boundary:** `fetch`/`localStorage` only in `docs/js/db.js` (`test_no_stray_io.py`); the service worker `docs/tablet/sw.js` is the one other file allowed to call `fetch` (it *is* the network layer) — add it to that test's allow-list explicitly. `app.js` alone touches the DOM/browser APIs (SW registration, `postMessage`, image error handling).
- **Parity:** `DataClient` gains one method in both twins (`rulesText()` / `rules_text()`); `test_the_twins_expose_the_same_client_surface` must stay green.
- Pure renderers via `h`` `/`raw()`; nested `h` through `raw`; Unicode glyphs not entities through interpolations; sizes on 34/20/18/13; BODY for anything read as a sentence/name/option; ≥44px targets; the tokens gate covers new button classes by name.
- The common round stays at 20 taps.
- Generated `docs/js/*.js` mirrors never hand-edited.

## Rulings made while planning

- **R1 — The Rules Reference corpus lives in the main checkout** (`research/rules/rules-reference.md`, gitignored) and is absent from worktrees. `tools/build_rules_text.py` takes `--corpus <dir>` (default `research/rules/`) and its tests use a small fixture markdown, never the real corpus.
- **R2 — Merged headings.** liteparse merges consecutive steps onto one heading (`###### 1.3 Draw cards 1.4 Resource phase ends`). The parser splits the *ids and titles* out of the heading with a regex but keeps the *text* as one block; every id in the heading maps to the same section record (`ids: ["1.3","1.4"]`). The modal cites all ids.
- **R3 — The PDF URL.** FFG's product page blocks scripted fetches and no stable direct URL is verified. `tools/data/rules.SOURCE.txt` pins the PDF by **sha256 of the file** plus the page URL it came from; a CI run tries the pinned direct URL if the pin carries one (`url=`), and otherwise the step is a documented no-op — the Pages site then ships without `rules_text.json` and the modal shows the Timing summary plus the product-page link (spec Risks). Local builds and device/Pages builds from the main checkout produce the file.
- **R4 — Glossary terms ship too** (`##### Term` entries): the elimination sheet's "Rules ›" opens "Player Elimination"; the map from view to step ids is a small module, `rules_map.js`.
- **R5 — Image prefix is pinned, not fetched:** `tools/data/cardDb.SOURCE.txt` gains `image_prefix=https://dragncards-lotrlcg.s3.amazonaws.com/cards/English/` (read from the plugin's `imageUrlPrefix.json` at the pinned sha on 2026-09-05); `build_card_data.py` copies it into `index.json` as `imagePrefix`. `--refresh` re-reads the plugin file.
- **R6 — Cache cap is a count, not bytes.** Opaque responses report size 0, so the image cache keeps the newest N entries (`IMAGE_CACHE_MAX = 400`, ~60 MB at 157 KB each) and evicts the oldest. Measuring quota on the real iPad is milestone 7's soak.
- **R7 — Classic service worker** (`importScripts`, no ES modules) for the old iPad's Safari; its policy helpers are written as plain functions on `self` so a node test can load the file with a stub `self`/`caches`/`Request`/`Response` and drive the handlers.
- **R8 — Where images and icons appear this milestone:** location picker rows (image + printed values), picker set headers (set icon), the QUEST zone's stage pill and the quest sheet (set icon beside the scenario's own set). The scenario overview is milestone 6.
- **R9 — Notes scope:** the pane's notes panel shows the current stage's tips (`stages[String(stage_n)]`) and falls back to `general`; at most three, "More notes ›" opens the sheet with everything. A scenario with no tips renders no panel.

---

### Task 1: The rules text artifact

**Files:**
- Create: `tools/build_rules_text.py`, `tools/data/rules.SOURCE.txt`, `tests/test_build_rules_text.py`, `tests/fixtures/rules_fixture.md`
- Modify: `.gitignore` (comment only — `docs/data/*` already ignores it), `rules/README.md` (posture), `.github/workflows/pages.yml` (step), `CLAUDE.md` ("Card data" section: one paragraph)

**Interfaces:**
- Produces `docs/data/rules_text.json`: `{"generated": iso, "book": "Rules Reference", "source": {"sha256": …, "page": …}, "sections": {"1.1": {"ids": ["1.1"], "title": "Resource phase begins", "text": "…"}, "1.3": {"ids": ["1.3","1.4"], "title": "Draw cards · Resource phase ends", "text": "…"}, …}, "glossary": {"Player Elimination": {"title": "Player Elimination", "text": "…"}}, "faq": []}`. Text is the markdown body under the heading with markdown stripped to plain paragraphs (`\n\n` between paragraphs), "See also:" lines dropped into `see_also: [...]`.
- CLI: `python3 tools/build_rules_text.py [--corpus DIR] [--out docs/data/rules_text.json] [--force]`; no-op with a one-line message when the output exists and `--force` is absent; friendly `SystemExit` (not a traceback) when the corpus file is missing.

- [ ] **Step 1: Fixture and failing tests**

`tests/fixtures/rules_fixture.md` (our own placeholder prose, not FFG text):

```markdown
# Rules Reference

#### Glossary

##### Player Elimination

Fixture: a player leaves the game when the fixture says so.

###### See also: Threat, Threat Elimination Level

##### Threat

Fixture threat entry.

#### Turn Sequence

###### 1.1 Resource phase begins

Fixture text for one one.

###### 1.3 Draw cards 1.4 Resource phase ends

Fixture text for one three and one four.

###### 6.4a Next enemy attack initiates

Fixture text for six four a.
```

```python
# tests/test_build_rules_text.py
import json, os, subprocess, sys
import pytest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import build_rules_text as brt
FIX = os.path.join(ROOT, "tests", "fixtures")

def test_parse_splits_merged_headings_and_keeps_one_text():
    doc = brt.parse(open(os.path.join(FIX, "rules_fixture.md")).read())
    s = doc["sections"]
    assert s["1.1"] == {"ids": ["1.1"], "title": "Resource phase begins", "text": "Fixture text for one one.", "see_also": []}
    assert s["1.3"]["ids"] == ["1.3", "1.4"] and s["1.4"] is s["1.3"]
    assert s["1.3"]["title"] == "Draw cards · Resource phase ends"
    assert s["6.4a"]["text"] == "Fixture text for six four a."

def test_parse_collects_glossary_and_see_also():
    doc = brt.parse(open(os.path.join(FIX, "rules_fixture.md")).read())
    g = doc["glossary"]["Player Elimination"]
    assert g["text"] == "Fixture: a player leaves the game when the fixture says so."
    assert g["see_also"] == ["Threat", "Threat Elimination Level"]
    assert doc["glossary"]["Threat"]["text"] == "Fixture threat entry."
    assert doc["faq"] == []

def test_build_writes_json_and_is_a_noop_when_present(tmp_path):
    out = tmp_path / "rules_text.json"
    brt.build(FIX, str(out), corpus_name="rules_fixture.md")
    d = json.loads(out.read_text())
    assert d["book"] == "Rules Reference" and "1.1" in d["sections"] and d["source"]["sha256"]
    mtime = out.stat().st_mtime
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_rules_text.py"), "--corpus", FIX, "--corpus-name", "rules_fixture.md", "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0 and "already" in r.stdout.lower() and out.stat().st_mtime == mtime

def test_missing_corpus_is_a_friendly_exit(tmp_path):
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_rules_text.py"), "--corpus", str(tmp_path), "--out", str(tmp_path / "x.json")], capture_output=True, text=True)
    assert r.returncode != 0 and "Traceback" not in r.stderr and "research/rules" in (r.stderr + r.stdout)
```

- [ ] **Step 2: Run, expect ImportError.**

- [ ] **Step 3: `tools/build_rules_text.py`**

```python
"""Parse the liteparse markdown of the Rules Reference into docs/data/rules_text.json.

The corpus (research/rules/, gitignored, built by build_rules_corpus.py) is
verbatim FFG text and never ships as a corpus; this tool ships EXCERPTS as a
build artifact under docs/data/ - the same gitignored, regenerated posture as
the compiled card DB (CLAUDE.md, "What may be committed"). Every numbered
turn step ("###### 6.4a Next enemy attack initiates") becomes a section keyed
by its id; glossary entries ("##### Player Elimination") become glossary
records. liteparse sometimes merges two consecutive steps onto one heading
("###### 1.3 Draw cards 1.4 Resource phase ends"); both ids then share one
record (plan ruling R2). No third-party fetch happens here: the PDF pin in
tools/data/rules.SOURCE.txt is checked, never downloaded, by this tool.
"""
import argparse, datetime, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
DEFAULT_CORPUS = os.path.join(ROOT, "research", "rules")
DEFAULT_NAME = "rules-reference.md"
DEFAULT_OUT = os.path.join(ROOT, "docs", "data", "rules_text.json")
SOURCE = os.path.join(HERE, "data", "rules.SOURCE.txt")

STEP_RE = re.compile(r"(\d+\.\d+(?:[ab]|\.\d+)?)\s+(.+?)(?=\s+\d+\.\d+(?:[ab]|\.\d+)?\s+|$)")
SEE_ALSO_RE = re.compile(r"^#{2,6}\s*See also:\s*(.+?)\s*$", re.I)

def _clean(lines):
    text = "\n".join(lines).strip()
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text

def parse(md):
    sections, glossary, cur, body = {}, {}, None, []
    def flush():
        if cur is None: return
        rec = cur["rec"]; rec["text"] = _clean(body); body.clear()
    for line in md.splitlines():
        m = SEE_ALSO_RE.match(line)
        if m and cur is not None:
            cur["rec"]["see_also"] = [t.strip() for t in m.group(1).split(",") if t.strip()]
            continue
        if line.startswith("###### "):
            flush(); head = line[7:].strip()
            steps = STEP_RE.findall(head)
            if not steps: cur = None; continue
            rec = {"ids": [i for i, _ in steps], "title": " · ".join(t.strip() for _, t in steps), "text": "", "see_also": []}
            for i, _ in steps: sections[i] = rec
            cur = {"rec": rec}; continue
        if line.startswith("##### "):
            flush(); term = line[6:].strip()
            rec = {"title": term, "text": "", "see_also": []}; glossary[term] = rec; cur = {"rec": rec}; continue
        if line.startswith("#"):
            flush(); cur = None; continue
        if cur is not None: body.append(line)
    flush()
    return {"sections": sections, "glossary": glossary, "faq": []}

def _pin():
    if not os.path.exists(SOURCE): return {}
    return dict(l.strip().split("=", 1) for l in open(SOURCE) if "=" in l)

def build(corpus_dir, out_path=DEFAULT_OUT, corpus_name=DEFAULT_NAME):
    path = os.path.join(corpus_dir, corpus_name)
    if not os.path.exists(path):
        raise SystemExit("rules corpus not found at %s - build it with tools/build_rules_corpus.py (see rules/README.md; research/rules is gitignored and lives in the main checkout)" % path)
    md = open(path, encoding="utf-8").read()
    doc = parse(md)
    doc.update({"generated": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z", "book": "Rules Reference",
                "source": {"sha256": hashlib.sha256(md.encode("utf-8")).hexdigest(), "page": _pin().get("page", ""), "pin": _pin().get("sha256", "")}})
    # ids that alias one record must serialise once each - JSON has no shared refs, so emit per id.
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    print("wrote %s: %d sections, %d glossary entries" % (out_path, len(set(map(id, doc["sections"].values()))), len(doc["glossary"])))

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=DEFAULT_CORPUS); ap.add_argument("--corpus-name", default=DEFAULT_NAME)
    ap.add_argument("--out", default=DEFAULT_OUT); ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    if os.path.exists(a.out) and not a.force:
        print("%s already exists - nothing to do (--force to rebuild)" % a.out); return 0
    build(a.corpus, a.out, a.corpus_name); return 0

if __name__ == "__main__":
    sys.exit(main())
```

`tools/data/rules.SOURCE.txt`:

```
# The Rules Reference PDF this corpus was parsed from. Pinned by content hash
# (sha256 of the PDF) - FFG's product page serves the download behind a
# script-blocking page, so there is no verified direct URL; `page=` is where
# a human fetches it. Fill `url=` only with a verified direct link; the Pages
# step downloads it when present and skips the artifact when absent (plan R3).
page=https://www.fantasyflightgames.com/en/products/the-lord-of-the-rings-the-card-game/
sha256=<fill from `shasum -a 256` of the local PDF>
url=
```

The implementer fills `sha256` from the local PDF named in `rules/README.md` if it is on this machine (`find ~ -iname "lotr lcg saga rulebook.pdf" -maxdepth 4`); otherwise leaves the placeholder and reports it.

- [ ] **Step 4: CI + docs.** `pages.yml` gains, after "Build icons", a step `Build rules text` (`continue-on-error: true`): reads `url=` from the pin; if empty → `echo "no pinned rules URL - skipping rules_text.json"`; else `curl -fsSL -o /tmp/rr.pdf "$url"`, verify `sha256sum`, `npm i -g @llamaindex/liteparse`, `python3 tools/build_rules_corpus.py /tmp/rr.pdf --title "Rules Reference" --no-ocr`, `python3 tools/build_rules_text.py`. `rules/README.md`: a "What ships" paragraph — the corpus never ships; `docs/data/rules_text.json` ships excerpts keyed by section as a gitignored build artifact; device deploy is `python3 tools/build_rules_text.py && mpremote cp -r docs/data/ :/data/` only if a future firmware feature reads it (today only the tablet does). `CLAUDE.md` "Card data" section: one paragraph naming the tool, the pin, the no-op rule and the artifact.

- [ ] **Step 5: Run** `python3 -m pytest tests/test_build_rules_text.py -q`, then the full suite; run the real build once locally from the main checkout's corpus (`python3 tools/build_rules_text.py --corpus /Users/andrewhammond/dev/lotr-lcg-presto-hud/research/rules`) and report the section/glossary counts. Commit — `feat(data): rules_text.json - Rules Reference excerpts as a pinned build artifact`.

---

### Task 2: The client reads it (both twins)

**Files:** modify `docs/js/db.js` (`DataClient.rulesText()`), `db.py` (`rules_text()`), `tests/test_db_client.py` or the existing client tests (find where `tips()` is tested), `tests/test_twin_parity.py` (surface test already compares method names — confirm it passes with the addition).

**Interfaces:** `await db.rulesText()` → the parsed JSON object, or `null` when the file is absent/corrupt (never throws); cached after the first call like `tips()`. Python `rules_text()` → dict or `None`. Tablet `app.js` loads it at boot into `ui.rules` (null when absent) alongside the bundle.

- [ ] **Step 1: Tests** — JS: a node probe that stubs `fetch` to 404 asserts `null`; to a JSON body asserts the object and a second call does not refetch (count calls). Python: `rules_text()` returns `None` for a missing file and the dict for a present one (tmp dir).
- [ ] **Step 2: Implement** mirroring `tips()`/`load_tips()`'s shape exactly (same cache field convention, same degrade-to-null).
- [ ] **Step 3: Run; commit** — `feat(db): rulesText()/rules_text() in both clients`.

---

### Task 3: The Rules modal and the "Rules §n ›" chips

**Files:**
- Create: `docs/tablet/js/rules_map.js`, `docs/tablet/js/sheet_rules.js`, `docs/tablet/js/acts_rules.js`
- Modify: `docs/tablet/js/primitives.js` (`band` gains `section`), `docs/tablet/js/pane.js` (every band names its section), `docs/tablet/js/sheet_elim.js` (glossary chip), `docs/tablet/js/sheets.js`, `docs/tablet/js/actions.js` (register), `docs/tablet/js/copy.js`, `docs/tablet/style.css`
- Test: `tests/test_tablet.py`

**Interfaces:**
- `rules_map.js`: `export const VIEW_SECTIONS = { resource: ["1.1","1.2","1.3","1.4"], planning: ["2.1","2.2","2.3","2.4"], quest_commit: ["3.1","3.2"], quest_staging: ["3.3"], quest_resolution: ["3.4","3.5"], travel: ["4.1","4.2","4.3"], enc_optional: ["5.1","5.2"], enc_checks: ["5.3","5.4"], combat_shadow: ["6.1","6.2"], combat_enemy: ["6.3","6.4a","6.4b","6.4.1","6.4.2","6.4.3","6.4.4","6.5","6.6"], combat_player: ["6.7","6.8a","6.8b","6.8.1","6.8.2","6.8.3","6.8.4","6.9","6.10","6.11"], refresh: ["7.1","7.2","7.3","7.4","7.5"], round_end: ["7.5"] }` (quest_setup and quest_sailing have no chip); `export function sectionsFor(view) → string[]`; `export const STEP_ORDER` (all ids in book order, for related-section chips prev/next).
- `band({kind, text, sub, section})`: when `section` is given, the band's last row is `chip({act:"open_rules", arg: section, label: h\`${CHROME.rules} §${section} ›\`, tone:"tan"})` (44px). `pane.js` passes the first id of `sectionsFor(view)` to each band (framework band → the phase-begins step; window band → the window step; when a view has one band, the first id).
- `ui.sheet = {kind:"rules", section: "6.2"}` or `{kind:"rules", term: "Player Elimination"}`. `sheet_rules.js` `renderRulesSheet(game, ui)`: header `Rules Reference · §6.2` (LABEL) + title (DISPLAY); **Official text** (BODY paragraphs, verbatim from `ui.rules.sections[id].text`); when `ui.rules` is null → a BODY line `CHROME.rulesUnavailable` ("The official text is not in this build.") and the Open PDF link; **Timing** (LABEL "THIS TRACKER'S SUMMARY") → the band copy for the view that owns the section (`PHASE_FRAMEWORK`/`PHASE_WINDOW`/`ACTION_WINDOW_TIPS` — reuse `viewcopy` verbatim; the sub-line `CHROME.rulesSummarySource` = "Summarised by this tracker from Rules Reference §%s"); **FAQ** only if `ui.rules.faq.length`; **Related** chips: prev/next in `STEP_ORDER` plus `see_also` glossary terms (each `open_rules` with `arg: "term:<name>"`); footer: `<a class="cta cta-plain" href="<page url from index.json rules.source or the pinned page>" target="_blank" rel="noopener">Open the rulebook page ›</a>` and `cta sheet_close Done`.
- Acts: `open_rules` (arg `"6.2"` or `"term:Player Elimination"`) → sets `ui.sheet`; returns true. Opening from inside another sheet (elim) replaces it — acceptable (the elim flag persists; `afterTap` reopens elim after the rules sheet closes; add a test).
- The elimination sheet's rule line gets `chip open_rules "term:Player Elimination"`.

- [ ] **Step 1: Tests** — (a) `sectionsFor` covers every flow view except `quest_setup`/`quest_sailing` (iterate `flowViews()`); (b) render the resource pane and assert both bands carry `data-act="open_rules"` with `1.1` and `1.2`… (exact args per the map); (c) with `ui.rules` = a fixture object, `open_rules 6.2` renders the fixture text verbatim inside `.body` and the header `§6.2`; prev/next chips are `6.1`/`6.3`; (d) with `ui.rules = null`, the sheet renders `rulesUnavailable` and still has the Open link; (e) elim sheet → `open_rules term:Player Elimination` → glossary text; `sheet_close` → elim sheet returns (flag persisted).
- [ ] **Step 2–4:** implement; CSS `.rules-body p.body { margin: 0 0 12px }`, `.rules-related { display:flex; flex-wrap:wrap; gap:8px }`, anchor styled as `.cta` (add `a.cta` to the height gate's class regex? the gate matches `.cta` already — ensure the anchor inherits `display:inline-flex; min-height:44px`). Run tests, tokens, full suite. Commit — `feat(tablet): the Rules modal - official text by section, this tracker's summary, related entries`.

---

### Task 4: Notes panel and Notes sheet

**Files:** create `docs/tablet/js/notes.js` (pure: `notesFor(tips, scenarioSlug, stage_n) → {scope, items:[…], source:{name,url}} | null`, `allNotes(tips, slug) → [{scope, items, source}]`), `docs/tablet/js/sheet_notes.js`, `docs/tablet/js/acts_notes.js`; modify `pane.js` (`renderPane` appends the panel between `parts` and the CTA row), `app.js` (bundle's tips → `ui.tips`; `ui.scenarioSlug`), `sheets.js`, `actions.js`, `copy.js`, `style.css`; test `tests/test_tablet.py`.

**Interfaces:** the bundle already carries tips (`db.bundle(slug).tips` — confirm the field name in `db.js`; if the bundle carries the whole `tips.json` map, `notes.js` indexes by slug). Panel markup: `<aside class="notes"><div class="notes-head">${icon("PIPE", 22, …)}<span class="label">${CHROME.notes} · ${scope}</span></div><ul>…≤3 <li class="body">…</li></ul><div class="notes-foot"><a class="chip chip-tan" href="${url}" target="_blank" rel="noopener">${CHROME.source} · ${name} ›</a>${chip open_notes "More notes ›"}</div></aside>`. Scope labels: `Stage ${n}` or `General` (from copy). Sheet: `{kind:"notes"}` lists General then each stage in order, every group with its source link; `Done` closes.

- [ ] **Step 1: Tests** — with a tips fixture `{scenarios: {"passage-through-mirkwood": {attribution:{name:"Vision of the Palantir", url:"https://…"}, general:["g1","g2","g3","g4"], stages:{"2":["s2a"]}}}}`: at stage 1 the panel shows the first three general tips and the source link; at stage 2 it shows `s2a` with scope "Stage 2"; `open_notes` renders all groups; a scenario absent from tips renders no `.notes` at all. Assert the link `href` is the fixture URL and the anchor has `rel="noopener"`.
- [ ] **Step 2–4:** implement; CSS for `.notes` (card ground, gold edge, 12px gap, `li.body` 18px). Run; commit — `feat(tablet): notes panel with sources, and the Notes sheet`.

---

### Task 5: Set icons as SVG

**Files:** modify `tools/build_icons.py` (`--svg-out`, default `docs/data/icons/svg/`, written in the same run from the same source — tarball or `--assets`), `.github/workflows/pages.yml` (no change if the default writes it in the same command — verify), `CLAUDE.md` (one sentence in the icons paragraph); create `docs/tablet/js/seticon.js` (pure: `setIcon(name, px)` → `<span class="seticon" style="width:px;height:px"><img src="${dataUrl('icons/svg/' + slugify(name) + '.svg')}" alt="" loading="lazy"><i class="seticon-fallback">◆</i></span>`); modify `sheet_locpick.js` (group headers: icon + name), `rail.js` (stage pill: the scenario's own set icon before the stage label when `game.scenario?.name`), `sheet_quest.js` (same), `app.js` (one delegated capture-phase `error` listener on `img` inside `.seticon`/`.card-frame` → add `is-missing` to the wrapper), `style.css`; tests `tests/test_build_icons.py` (find the existing one; add an svg-out test with the `--assets` local-dir path and a tiny SVG), `tests/test_tablet.py`.

**Interfaces:** `slugify` from `docs/js/quest_catalog.js` is the slug rule (mirrors `build_icons._slug` — assert in a test that both produce the same slug for `"Passage Through Mirkwood"` and `"Dol Guldur Orcs"`; if they differ, `seticon.js` uses a local copy of `_slug`'s rule and the test pins the pair). `.seticon.is-missing img { display:none }`, `.seticon:not(.is-missing) .seticon-fallback { display:none }`.

- [ ] **Step 1: Tests** — build_icons: with `--assets tmpdir` holding `encounter-sets/passage_through_mirkwood.svg`, `--svg-out tmp/svg` writes `passage-through-mirkwood.svg` byte-identical to the input; tablet: the picker header for a set contains `<img src="…icons/svg/passage-through-mirkwood.svg"`; slug parity test.
- [ ] **Step 2–4:** implement; run; commit — `feat(icons): export the set SVGs; set icons wherever the tablet names a set`.

---

### Task 6: Card images and the service worker

**Files:** create `docs/tablet/sw.js`, `docs/tablet/js/cardimage.js` (pure: `cardImage({id, name, caption})` → `<figure class="card-frame"><img src="${prefix}${id}.jpg" alt="" loading="lazy"><figcaption class="body">${name}${caption ? " · " + caption : ""}</figcaption></figure>`; `prefix` from `ui.imagePrefix`), `tests/test_tablet_sw.py`; modify `tools/data/cardDb.SOURCE.txt` (`image_prefix=…`, R5), `tools/build_card_data.py` (copy into `index.json` as `imagePrefix`; `--refresh` fetches `jsons/imageUrlPrefix.json` at the pinned sha and rewrites the pin line), `docs/js/quest_catalog.js` + `quest_catalog.py` (`imagePrefix()` / `image_prefix()` reading the index — parity), `docs/tablet/index.html` (nothing — registration lives in app.js), `docs/tablet/js/app.js` (register `sw.js` with `{scope: "/tablet/"}` relative to `import.meta.url`'s directory; on `pick_scenario` post `{type:"prefetch", urls:[…]}` for the scenario's own set and gathered sets' card images — build the list from the bundle's cards via a pure helper `imageUrls(bundle, prefix)` in `cardimage.js`), `sheet_locpick.js` (rows get `cardImage` thumbnails, `caption` = printed threat/points as today), `style.css`, `tests/test_no_stray_io.py` (allow-list `docs/tablet/sw.js` for `fetch`, with the reason), `tests/test_tablet.py`.

**Service worker contract (classic):**
```js
// docs/tablet/sw.js - the tablet's network layer: shell + data cache-first with
// network refresh; card images cache-first in their own cache, newest-N kept.
// Classic worker (importScripts-style globals, no modules) - plan ruling R7:
// the old iPad's Safari predates module workers. Helpers hang off `self` so
// tests/test_tablet_sw.py can load this file with a stub self/caches.
self.SHELL_CACHE = "lotr-tablet-shell-v1";
self.IMAGE_CACHE = "lotr-tablet-images-v1";
self.IMAGE_CACHE_MAX = 400;
self.isImage = url => /\/cards\/[A-Za-z]+\/[0-9a-f-]+\.jpg$/.test(url);
self.isShellOrData = url => { const u = new URL(url); return u.origin === self.location.origin && (/\/tablet\//.test(u.pathname) || /\/js\/|\/data\//.test(u.pathname)); };
self.trimCache = async (cache, max) => { const keys = await cache.keys(); for (const k of keys.slice(0, Math.max(0, keys.length - max))) await cache.delete(k); };
self.addEventListener("install", e => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", e => {
  const url = e.request.url;
  if (self.isImage(url)) e.respondWith(self.cacheFirst(self.IMAGE_CACHE, e.request, self.IMAGE_CACHE_MAX));
  else if (self.isShellOrData(url) && e.request.method === "GET") e.respondWith(self.staleWhileRevalidate(self.SHELL_CACHE, e.request));
});
self.cacheFirst = async (name, req, max) => { const c = await caches.open(name); const hit = await c.match(req); if (hit) return hit; const res = await fetch(req, { mode: "no-cors" }); if (res && (res.ok || res.type === "opaque")) { await c.put(req, res.clone()); await self.trimCache(c, max); } return res; };
self.staleWhileRevalidate = async (name, req) => { const c = await caches.open(name); const hit = await c.match(req); const net = fetch(req).then(res => { if (res && res.ok) c.put(req, res.clone()); return res; }).catch(() => hit); return hit || net; };
self.addEventListener("message", e => { if (e.data?.type === "prefetch") e.waitUntil((async () => { const c = await caches.open(self.IMAGE_CACHE); for (const u of e.data.urls) { if (!(await c.match(u))) { try { const r = await fetch(u, { mode: "no-cors" }); if (r) await c.put(u, r); } catch {} } } await self.trimCache(c, self.IMAGE_CACHE_MAX); })()); });
```

**Test harness (`tests/test_tablet_sw.py`):** a node probe that builds a stub `self` (`addEventListener` collecting handlers, `location`, `clients`, `skipWaiting`), stub `caches` (in-memory Map of Maps with `open/match/put/delete/keys`), stub `fetch` (scripted responses; counts calls), minimal `Request`/`Response`/`URL` (node has `URL`), then `vm.runInNewContext(fs.readFileSync("sw.js"), sandbox)` and drives: (a) an image request twice → one network call, one cache entry; (b) 401 image inserts then `trimCache` leaves 400; (c) a `/tablet/js/app.js` request → served from network the first time, from cache the second with a background refresh; (d) `message` prefetch adds N urls and skips those cached; (e) a non-matching origin URL is untouched (`respondWith` never called).

- [ ] **Step 1: Tests** (the SW harness above + tablet tests: picker rows contain `<figure class="card-frame">` with the pinned prefix + `<id>.jpg`; `imageUrls(bundle, prefix)` lists own-set + gathered-set cards once each; `quest_catalog` parity for `imagePrefix`).
- [ ] **Step 2–4:** implement; `app.js` registration guarded (`if ("serviceWorker" in navigator)`), errors swallowed; CSS `.card-frame { width: 96px } .card-frame img { width:100%; aspect-ratio: 5/7; object-fit: cover; background: var(--well) } .card-frame.is-missing img { display:none }`; the picker row layout gains the thumbnail column. Run; commit — `feat(tablet): card images in the picker, cached by a service worker; image prefix pinned with the card data`.

---

## Done when

- `python3 -m pytest tests/` green; `test_no_stray_io.py` passes with `sw.js` allow-listed by name and reason.
- Local build from the main checkout: `python3 tools/build_rules_text.py --corpus …/research/rules` writes ~50 sections + ~137 glossary entries; `python3 tools/build_icons.py` writes `docs/data/icons/svg/`; `index.json` carries `imagePrefix`.
- In the browser at 1366×1024 (worktree dev server, with `rules_text.json` copied into `docs/data/` for the check): every band shows a "Rules §n ›" chip; tapping one opens the modal with the verbatim section, the Timing summary, prev/next; the elimination sheet's chip opens "Player Elimination"; the notes panel shows Mirkwood's tips with a working Source link; picker headers show set icons; picker rows show card thumbnails; DevTools → Application shows `lotr-tablet-shell-v1` and `lotr-tablet-images-v1` with entries after "Begin setup"; reload offline (DevTools) still renders the shell and cached thumbnails, and an uncached image shows its caption only.
- `rules/README.md` and `CLAUDE.md` describe the three artifacts; the on-iPad quota measurement is recorded as milestone 7's first soak item.
