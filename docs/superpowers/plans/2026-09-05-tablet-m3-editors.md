# Tablet Client — Milestone 3: Editors and Sheets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every way a player changes a number or a card on the tablet: the players sheet (all players, ±1/±5 threat, everyone-at-once buttons, willpower and engaged steppers), the staging editor, the elimination prompt, the quest sheet (progress, points, locations with printed-X counts, side quests), the location picker, the side-quest picker, the resolution sheet (explore, reveal, branch, advance, victory), and the sailing test — plus the tablet's own type/target/contrast test gate and the full 20-tap common-round walk.

**Architecture:** Sheets are modal overlays rendered by pure string builders, exactly like the panes: `ui.sheet` (`null` or `{kind, …}`) is UI state owned by `app.js`, `layout()` draws the scrim and sheet when it is set, and every sheet button is a `data-act` handled by `dispatch()`. The model calls are the web twin's modal calls (`docs/js/screens.js`): `PlayersDetailModal`, `EliminationModal`, `QuestingProgressModal` + `LocationConfigModal` + `QuestConfigModal`, `LocationPickModal`, `SideQuestPickModal`, `ResolutionModal`, `SailingModal`. Three model flags drive auto-opened sheets after a tap: `pending_elim` (elimination), `pending_resolution` (resolution), and the tablet's own `ui.sheet` for everything else. Every tap still goes through `perform()` so undo covers sheet edits.

**Tech Stack:** as milestone 2 (ES modules, no framework, pytest driving node). Reference reading for every task: the twin's modal class named in the task, in `docs/js/screens.js`.

**Spec:** `docs/superpowers/specs/2026-09-05-tablet-client-design.md` — "Modals and full screens" table, "Interaction model › Editing", "Tap economy", "Testing". Milestone 2 landed at 2b5e70a.

## Global Constraints

- All milestone-2 constraints hold: render modules pure (no `document`/`window` outside `docs/tablet/js/app.js`); every dynamic string through `h`` `; chip/CTA labels composed with `h`` ` before `raw`; no `localStorage`/`fetch` outside `docs/js/db.js`; tablet-only chrome strings in `docs/tablet/js/copy.js` (`CHROME`); play copy from `../../js/viewcopy.js`.
- Type scale 34 / 20 / 18 / 13, nothing below 13px; every button ≥ 44px on both axes (the `.step` 64×52 and `.chip` 44px classes exist; add a `.step-sm` only if it is still ≥ 44×44); CTA 64px.
- Log lines are byte-identical to the twin's for the same action (they are quoted in each task).
- Every sheet edit goes through `perform()` (delta-bracketed), never `dispatch()` directly; sheets have no Save — Done closes.
- Nothing under `ui/` or `docs/js/` changes except `docs/js/gamestate.js` and `gamestate.py` TOGETHER for the one model addition in Task 2 (`adjustAllThreat`), with a parity probe.
- `python3 -m pytest tests/` stays green (2426 at the start). Commit after every task; do not push.

## File structure

```
docs/tablet/js/
  sheets.js        renderSheet(game, ui) -> string | ""  (scrim + the sheet for ui.sheet.kind)
  sheet_players.js renderPlayersSheet(game, ui)
  sheet_staging.js renderStagingSheet(game, ui)
  sheet_elim.js    renderElimSheet(game, ui)
  sheet_quest.js   renderQuestSheet(game, ui)   (progress editor: quest, locations, side quests)
  sheet_locpick.js renderLocPickSheet(game, ui)
  sheet_sqpick.js  renderSideQuestPickSheet(game, ui)
  sheet_resolve.js renderResolveSheet(game, ui) + deriveResolveStep(game, ui)
  sheet_sailing.js renderSailingSheet(game, ui)
  sheet_menu.js    renderMenuSheet(game, ui)     (New game while a game is in progress)
  actions.js       + the sheet acts (open_*, sheet_close, and each sheet's acts)
  layout.js        + renderSheet() appended inside .app
  rail.js          + the "Edit ›" chip in each zone header
  app.js           + ui.locations / ui.sideQuests loading; auto-open of elim/resolution sheets after perform()
tests/test_tablet_tokens.py   the type/target/contrast gate over style.css and the shared pal
tests/test_tablet.py          + a test per sheet; the 20-tap walk
```

`ui.sheet` shapes: `{kind:"players"}`, `{kind:"staging"}`, `{kind:"elim", i, level}`, `{kind:"quest"}`, `{kind:"locpick", mode:"new"|"change", idx, back:"play"|"quest", selected, manual:{points, contrib}, page}`, `{kind:"sqpick", sphere, selected, page}`, `{kind:"resolve", forced, branchPick, skippedSide:[]}`, `{kind:"sailing", v}`, `{kind:"menu"}`.

---

### Task 1: The tablet's own gate, and two leftovers

**Files:**
- Create: `tests/test_tablet_tokens.py`
- Modify: `docs/tablet/js/copy.js` (delete the dead duplicate `back` key on line 6, keep the live `"‹ Back"` one), `docs/tablet/style.css` (only if the gate finds a violation)

**Interfaces:** none new. The gate reads `docs/tablet/style.css` textually and `docs/js/ui.js`'s `pal` via node.

- [ ] **Step 1: Write the gate**

```python
"""The tablet's type, target and contrast gate - the spec's Testing table row
"Every chip >= 44 px, every stat value >= 26 px, contrast AA on the tablet
tokens". The HUD's equivalents (test_typography.py, test_contrast.py) read
Python draw sites; the tablet's live in one stylesheet, so this reads that."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = os.path.join(ROOT, "docs", "tablet", "style.css")
SCALE = {34, 26, 20, 18, 13}            # DISPLAY, small numerals, BODY, secondary, LABEL
NUMERAL_ALLOW = {84, 64, 56, 48, 40, 36, 30, 26, 24, 22}   # widget-owned numerals and glyph sizes


def _css():
    with open(CSS) as f:
        return f.read()


def _font_sizes():
    css = _css()
    out = []
    for m in re.finditer(r"font(?:-size)?\s*:\s*([^;]+);", css):
        for px in re.findall(r"(\d+(?:\.\d+)?)px", m.group(1)):
            out.append(float(px))
    return out


def test_no_text_smaller_than_label():
    small = sorted({s for s in _font_sizes() if s < 13})
    assert not small, "font sizes below LABEL (13px): %s" % small


def test_every_font_size_is_on_the_scale_or_a_numeral():
    off = sorted({s for s in _font_sizes() if s not in SCALE | NUMERAL_ALLOW})
    assert not off, "font sizes off the scale: %s (add to the scale or justify in NUMERAL_ALLOW)" % off


def test_buttons_are_at_least_44px():
    css = _css()
    # every rule that sets a height on a button-ish class must be >= 44
    for m in re.finditer(r"\.(chip|cta|step|scenario-row|step-sm)[^{]*\{([^}]*)\}", css):
        body = m.group(2)
        hm = re.search(r"(?:min-)?height\s*:\s*(\d+)px", body)
        if hm:
            assert int(hm.group(1)) >= 44, "%s is %spx tall" % (m.group(1), hm.group(1))


def _contrast(fg, bg):
    def lum(rgb):
        r, g, b = [c / 255 for c in rgb]
        f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
    l1, l2 = sorted([lum(fg), lum(bg)], reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def _pal():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(ROOT, "docs", "js")
        for f in os.listdir(src):
            if f.endswith(".js"):
                shutil.copy(os.path.join(src, f), os.path.join(tmp, f))
        with open(os.path.join(tmp, "package.json"), "w") as f:
            f.write('{"type":"module"}')
        probe = os.path.join(tmp, "probe.mjs")
        with open(probe, "w") as f:
            f.write('import { pal } from "./ui.js"; console.log(JSON.stringify(pal));')
        r = subprocess.run([node, probe], cwd=tmp, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        raw = json.loads(r.stdout)
    rgb = lambda s: tuple(int(x) for x in re.findall(r"\d+", s))
    return {k: rgb(v) for k, v in raw.items() if isinstance(v, str) and v.startswith("rgb")}


@pytest.mark.parametrize("ink,ground", [
    ("tan", "bg"), ("tan", "card"), ("tan", "card_hi"), ("tan", "well"),
    ("gold", "bg"), ("gold", "card"), ("gold", "card_hi"), ("gold", "well"),
    ("muted", "card"), ("dim", "card"), ("dim", "well"),
    ("ok_fg", "btn_ok"), ("amber", "card"), ("red", "card"), ("green", "card"),
])
def test_tablet_ink_on_ground_clears_aa(ink, ground):
    pal = _pal()
    ratio = _contrast(pal[ink], pal[ground])
    assert ratio >= 4.5, "%s on %s is %.2f:1" % (ink, ground, ratio)
```

- [ ] **Step 2: Run it** — `python3 -m pytest tests/test_tablet_tokens.py -q`. Any red is a real finding: fix `style.css` (never the gate) unless a size is a widget-owned numeral, in which case add it to `NUMERAL_ALLOW` with a comment naming the widget.
- [ ] **Step 3: Delete the dead `back` key** in `copy.js`; `python3 -m pytest tests/test_tablet.py -q` green.
- [ ] **Step 4: Full suite green; commit** — `git commit -m "test(tablet): the type, target and contrast gate; drop a dead copy key"`

---

### Task 2: The sheet framework, the rail's Edit chips, the players sheet, the staging editor, the menu

**Files:**
- Create: `docs/tablet/js/sheets.js`, `sheet_players.js`, `sheet_staging.js`, `sheet_menu.js`
- Modify: `docs/tablet/js/actions.js`, `layout.js`, `rail.js`, `strip.js` (a `Menu ›` chip in the round block), `copy.js`, `style.css`, `docs/js/gamestate.js` + `gamestate.py` (one method, see below), `tests/test_twin_parity.py` (parity of that method)
- Test: `tests/test_tablet.py`

**Interfaces:**
- `sheets.js`: `renderSheet(game, ui) -> string` — `""` when `ui.sheet` is null; else `<div class="scrim" data-act="sheet_close"><section class="sheet sheet-{kind}" data-stop>…</section></div>`. `app.js`'s delegation ignores clicks whose target is inside `[data-stop]` unless they hit a `[data-act]` (so the scrim closes, the sheet body does not).
- `newUi()` gains `sheet: null, locations: [], sideQuests: []`.
- Acts: `open_players`, `open_staging`, `open_menu`, `sheet_close` (sets `ui.sheet = null`, returns true). Players: `thr` (arg `"i:±n"`, n ∈ {1, 5}): `const before = p.threat; game.adjustThreat(i, n); if (after !== before) game.logEvent(\`P${i+1} threat ${before} -> ${after}\`)` (the twin's `PlayersDetailModal` text, verbatim); `commit` (arg `"i:±1"`): `game.setCommit(i, next); game.logEvent(\`P${i+1} committed ${next} willpower\`)`; `eng` reuses milestone 2's `eng±`. `all_thr` (arg `±n`): the new model method below. Staging: `stg±` (exists), `stg5` (arg ±5 → `setStaging(staging ± 5)`), `stgen±`, `stgloc±` (exist). Menu: `new_game_confirm` (handled by `app.js` like `new_game`), `sheet_close`.
- **Model addition (both twins, parity-tested):** `adjust_all_threat(delta)` / `adjustAllThreat(delta)`: for every living player `adjust_threat(i, delta)`; one log line `All players threat ${delta > 0 ? "+" : ""}${delta} (P1 26, P2 27, …)` listing the resulting values; returns the list of new threats. Keyed tally is NOT used (each press is an event). Elimination follows from `adjust_threat` as usual (`pending_elim` set for the first newly-eliminated player).
- Rail: each zone header gains `chip({act:"open_players"|"open_quest"|"open_staging", label: CHROME.edit + " ›", tone:"tan", height:30})` (`open_quest` is Task 4's; render its chip now, it opens nothing until then — acceptable because Task 4 lands in this same milestone; note it in the report).
- Players sheet layout (from the canvas): header `Players · elimination at N` + the everyone row (`All −1`, `All +1`, `All +2` chips, 44px) + one row per player: label + `${elimination - threat} to ${elimination}` (red when ≤ 10), `−5 −1 [helm 48] +1 +5`, willpower `− [sun 36] +`, engaged `− [black helm 36] +`; footer `Every change is logged as it happens. Done just closes the sheet.` + `Done` CTA (`sheet_close`). Eliminated players show `CHROME.eliminated` and no steppers.
- Staging sheet: three rows (threat with ±5/±1, enemies ±1, locations ±1) + Done.
- Menu sheet: `New game` (`new_game_confirm`, tone `no`) with a line `The current game is saved until you start a new one.` and `Cancel`.

- [ ] **Step 1: Failing tests** (append to `tests/test_tablet.py`; use the `node(probe)` harness):

```python
def test_players_sheet_edits_every_player_and_logs_like_the_twin():
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(3, 25); g.advanceView(); const ui = newUi();
perform(g, ui, "open_players", "");
const html = layout(g, ui);
perform(g, ui, "thr", "2:5"); perform(g, ui, "thr", "2:-1");
perform(g, ui, "commit", "0:1"); perform(g, ui, "commit", "0:1");
perform(g, ui, "eng+", "1");
perform(g, ui, "all_thr", "1");
const texts = g.log.slice(-6).map(e => e.text);
perform(g, ui, "sheet_close", "");
console.log(JSON.stringify({ sheet: html.includes('class="sheet sheet-players"'), rows: (html.match(/class="psheet-row/g) || []).length,
  threats: g.players.map(p => p.threat), commits: g.players.map(p => p.commit), eng: g.players[1].engaged,
  texts, closed: ui.sheet === null, deltas: g.deltas.length }));
""")
    assert js["sheet"] and js["rows"] == 3
    assert js["threats"] == [26, 26, 30]
    assert js["commits"] == [2, 0, 0] and js["eng"] == 1
    assert js["texts"][0] == "P3 threat 25 -> 30"
    assert js["texts"][1] == "P3 threat 30 -> 29"
    assert "P1 committed 2 willpower" in js["texts"]
    assert js["texts"][-1].startswith("All players threat +1 (P1 26, P2 26, P3 30)")
    assert js["closed"] and js["deltas"] == 6   # sheet open/close change ui only: no delta


def test_scrim_closes_and_the_sheet_body_does_not():
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { perform, newUi } from "./actions.js";
import { layout } from "./layout.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView(); const ui = newUi();
perform(g, ui, "open_staging", "");
const html = layout(g, ui);
console.log(JSON.stringify({ scrim: /class="scrim"[^>]*data-act="sheet_close"/.test(html), stop: html.includes("data-stop"),
  rows: html.includes('data-act="stg5"') && html.includes('data-act="stgen+"') && html.includes('data-act="stgloc+"') }));
""")
    assert js["scrim"] and js["stop"] and js["rows"]
```

And in `tests/test_twin_parity.py`, an `adjustAllThreat` probe compared with `adjust_all_threat` (threats after, the log line, `pending_elim` when one player crosses the level).

- [ ] **Step 2: Run to verify failure.** — [ ] **Step 3: Implement** (model method in both twins first, then the sheets, acts, chips, CSS: `.scrim { position:absolute; inset:0; background: rgba(0,0,0,.66); display:flex; align-items:center; justify-content:center }`, `.sheet { width: 1160px; max-height: 920px; overflow:auto; padding: 20px 24px 22px; background: var(--bg); border:1px solid var(--border-gold); border-radius:12px; box-shadow: 0 24px 60px rgba(0,0,0,.6) }`). `app.js`: after any `perform`, if `game.pending_elim !== null && !ui.sheet` → `ui.sheet = {kind:"elim", i: game.pending_elim, level: game.players[i].elimination}` (Task 3 renders it; until then `renderSheet` returns "" for unknown kinds — write it that way). — [ ] **Step 4: Tests + suite green.** — [ ] **Step 5: Commit** — `feat(tablet): sheets; the players sheet, the staging editor, the menu; adjustAllThreat in both twins`

---

### Task 3: The elimination sheet

**Files:** create `docs/tablet/js/sheet_elim.js`; modify `actions.js`, `sheets.js`, `copy.js`, `style.css`; test `tests/test_tablet.py`.

**Interfaces:** `ui.sheet = {kind:"elim", i, level}` auto-opened by `app.js` (Task 2). Acts, mirroring `EliminationModal.onButton` exactly: `elim_confirm` → `game.pending_elim = null; game.logEvent(\`P${i+1} eliminated (threat ${p.threat} >= level ${p.elimination})\`)`, close; `elim_avert` → `game.avertElimination(i)`, close; `elim_lvl` (arg ±1/±5) → `ui.sheet.level = clamp(20, 99)`; `elim_setlvl` → `p.elimination = level; p.eliminated = p.threat >= p.elimination; logEvent(\`P${i+1} elimination level set to ${level}\`)`, then if still eliminated the `eliminated` line too, `pending_elim = null`, close. Copy: title `P{n} reaches {level}`, the three choices with one-line explanations from `viewcopy`/`CHROME` (write them in `CHROME`; no rules claim beyond "threat at or above the elimination level eliminates the player", which is Rules Reference 7.4/elimination — cite in a comment).

- [ ] **Step 1: Failing test** — raise P2 to 50 via `perform(g, ui, "thr", "1:5")` ×5 from 25; assert `ui.sheet.kind === "elim"` after the tap that crosses (the app-level auto-open lives in `app.js`; for the test, replicate it in a helper exported from `actions.js`: `afterTap(game, ui)` that `app.js` also calls — put the auto-open there so it is testable), then `perform(g, ui, "elim_avert")` → threat 45, `pending_elim === null`, sheet closed, log line `P2 avoided elimination (card effect) - threat set to 45`.
- [ ] **Steps 2–5** as before. Commit — `feat(tablet): the elimination sheet`

---

### Task 4: The quest sheet (progress editor) with printed-X counts

**Files:** create `docs/tablet/js/sheet_quest.js`; modify `actions.js`, `sheets.js`, `rail.js` (the `open_quest` chip now opens it), `copy.js`, `style.css`; test.

**Interfaces:** `ui.sheet = {kind:"quest"}`. Reference: `QuestingProgressModal`, `LocationConfigModal`, `QuestConfigModal` in `docs/js/screens.js` — read their `onButton`s; the tablet folds the three into one sheet with sections:
- **Quest** row: `Stage {questLabel()}` + face name; progress `qP±` (`game.quest.progress = max(0, …)`, keyed tally log `Quest progress N` key `qp`); points `qPts±` only when `game.quest.mode` is manual/`points` (mirror `QuestConfigModal`'s `pts`; keyed tally `Quest points N` key `qpts`); a `Quest card ›` chip is milestone 5.
- **Locations**: one row per `active_locations[i]`: name, `progress` `lP±` (keyed `Location N progress M`), `points` `lPts±`, `threat` `lThr±`, and when the location prints an X (`loc.threatKind === "x"` with a `threatX` spec): the count stepper `lX±` labelled `labelFor(threatX.target)` from `../../js/xtargets.js`, resolving via `xtargets.resolve(threatX, { count: loc.threatCount, ...game.xContext() })` — auto targets show the resolved number and no stepper (the tracker supplies it: `enemies_in_play`, `locations_in_staging`, `players`, `stage_number`, `highest_threat`). Row actions: `lExplored` (mirror `LocationConfigModal`'s `explored` branch: log + splice + `exploreLocationIfDone` semantics), `lToStaging` (`tostaging`: put its threat back into `staging` and remove), `lReplace` (opens the picker in `change` mode for that seat, back `quest`). Read those branches for the exact log strings.
- **Side quests**: one row per `side_quests[i]`: name or `Side Quest {i+1}`, progress `sP±`, points `sPts±`, `sRemove` (log `Side quest N removed`).
- `+ Add location` (`open_locpick` with `back:"quest"`, Task 5) and `+ Side quest` (`open_sqpick`, Task 6) chips.
- `Done` (`quest_done`): `ui.sheet = null`; `if (game.needsResolution()) game.pending_resolution = "auto"` (the twin's `close` branch) — Task 7's sheet then opens via `afterTap`.

- [ ] **Step 1: Failing tests** — (a) open the sheet on a bare game with an active location `{points: 4, progress: 1, name: "Forest Gate", threat: 2}`; `lP+` ×3 → progress 4; `quest_done` → `pending_resolution === "auto"`; (b) a location with `threatKind:"x", threatX:{target:"damaged_characters", add:1}, threatCount: null` renders a stepper labelled `Damaged characters` and `lX+` ×2 resolves the threat to 3 (via the row's displayed value); (c) a location with `threatX:{target:"enemies_in_play"}` under `setBoardTracking(true)` shows the tracked value and no `lX+` button.
- [ ] **Steps 2–5.** Commit — `feat(tablet): the quest sheet; progress, points, locations with printed-X counts, side quests`

---

### Task 5: The location picker

**Files:** create `docs/tablet/js/sheet_locpick.js`; modify `actions.js`, `sheets.js`, `pane.js` (Travel's `Travel to location` CTA → `open_locpick` `{mode:"new", back:"play"}`; `Replace location` when a location is active → `{mode:"change", idx:0}`), `app.js` (load `ui.locations = (await db.bundle(slug)).locations` at boot and on `pick_scenario`), `copy.js`, `style.css`; test.

**Interfaces:** reference `LocationPickModal`. `ui.sheet = {kind:"locpick", mode, idx, back, selected:null, page:0, manual:null|{points:3, contrib:2}}`. Entries are `ui.locations` (`loadLocations()`'s shape: `{id, name, points, threat, set, text, image, threatKind, threatX, …}` — read `locationsFor` in `quest_catalog.js` for the exact keys). Sections: `In staging` is not tracked by name yet (milestone 4+), so one list "Locations in the gathered sets" grouped by `set`, rows `chip`-like buttons (`locpick_row`, arg id) showing name + `threat N · M quest points` (BODY, not caps), selected row highlighted; `Manual entry` (`locpick_manual`) reveals two steppers (`points` 1–30, `contribution` 0–9, per the twin's `pts`/`ctr` clamps); CTAs: `locpick_travel` (needs a selection: `arrival = back === "play" ? "travel" : "effect"`; commit exactly as `_commit(e.points ?? 0, e.threat ?? 0, e.name, e)` → `travelTo`/`changeLocation` by mode), `locpick_save` (manual: `_commit(points, contrib)` with the `entry.threat = contribution` rule), `locpick_cancel`. Leaving with `back === "quest"` reopens the quest sheet (`ui.sheet = {kind:"quest"}`).

- [ ] **Step 1: Failing tests** — with `ui.locations = [{id:"a", name:"Old Forest Road", points:3, threat:1, set:"Passage Through Mirkwood"}]`: from `travel`, `open_locpick` → render lists the row; `locpick_row a`; `locpick_travel` → `active_locations[0].name === "Old Forest Road"`, `points 3`, staging reduced by 1 (`setStaging(4)` first), log contains `Traveled to Old Forest Road (3 quest points)`; sheet closed; manual path: `locpick_manual`, `locpick_pts +1` (3→4), `locpick_save` → a second seat? No — `mode:"new"` appends; assert two seats and the manual one has `threat === contribution`.
- [ ] **Steps 2–5.** Commit — `feat(tablet): the location picker`

---

### Task 6: The side-quest picker

**Files:** create `docs/tablet/js/sheet_sqpick.js`; modify `actions.js`, `sheets.js`, `app.js` (`ui.sideQuests = await db.sideQuests()` lazily on first open), `copy.js`; test.

**Interfaces:** reference `SideQuestPickModal`. Entries `{id, name, points, sphere, text}` (read `loadPlayerSideQuests`). Sphere chips (`sqpick_sphere`), rows (`sqpick_row`), `sqpick_add` (push `{points, progress:0, name}` + log `Side quest added: ${name} (${pts} pts, progress view)`), `sqpick_manual` (push `{points:0, progress:0}` + log `Side quest added manually (progress view)`), cancel; leaving reopens the quest sheet.

- [ ] **Step 1: Failing test** — with two entries in two spheres, open, pick sphere, row, add → `side_quests.length === 1`, name and points right, log text exact, `ui.sheet.kind === "quest"`.
- [ ] **Steps 2–5.** Commit — `feat(tablet): the side-quest picker`

---

### Task 7: The resolution sheet

**Files:** create `docs/tablet/js/sheet_resolve.js`; modify `actions.js` (`afterTap` opens it when `game.pending_resolution` is truthy: `ui.sheet = {kind:"resolve", forced: game.pending_resolution === "forced", branchPick:null, skippedSide:[]}; game.pending_resolution = false`), `sheets.js`, `copy.js`, `style.css`; test.

**Interfaces:** port `ResolutionModal._derive()` (quoted in full in the twin; read it) as `deriveResolveStep(game, ui)` → `null | {kind:"reveal"|"location"|"branch"|"advance"|"victory"|"side_quest", …}` with the same fields, using `frontFace`/`faceOf` from `cards.js` for both faces. Acts mirror `onButton`: `res_flip` (`flipToB()`), `res_location` (`resolveLocationOverflow()`), `res_branch` (arg idx), `res_random`, `res_advance` (`clearAndAdvance(card_idx)`; clears `forced`/`branchPick`), `res_victory` (`setGameOver("victory")`, close → `app.js` moves to the gameover screen), `res_not_yet` (log `Victory declined - the stage is not defeated yet`, close), `res_side_done` (log `Side quest ${i+1} completed (resolution)`, splice), `res_side_skip`, `res_close` (only when the step is null: "All resolved"). The reveal step shows BOTH faces' text (the twin's comment: 75 of 514 stage cards print their rules on the back) with `NO_CARD_TEXT` when a face is blank; the branch step lists the next stage's cards (front face name + `questPoints`) with `mode` (`choice`/`random`); the advance step warns `underfilled` when progress < points; the victory step shows the final back face and offers `Declare victory` / `Not yet`.

- [ ] **Step 1: Failing tests** — with a two-stage scenario preloaded (stage 1: one card A/B points 2; stage 2: two cards = a branch): flip to B; `setWillpower(4); setStaging(0); resolve; apply_alloc` → `pending_resolution` set → `afterTap` opens the sheet; step `advance`? No: progress 2 ≥ points 2 → `_derive` → `_questStep`: side B, next stage has 2 cards → `branch`; `res_branch 1` → `advance`; `res_advance` → stage 2, side A → `reveal` step (both faces rendered); `res_flip` → side B; step null → `res_close`. Second test: a one-stage scenario reaching points → `victory` step → `res_victory` → `game_over.result === "victory"`.
- [ ] **Steps 2–5.** Commit — `feat(tablet): the resolution sheet`

---

### Task 8: The sailing test

**Files:** create `docs/tablet/js/sheet_sailing.js`; modify `pane.js` (`quest_sailing` gets a `Sailing test` CTA → `open_sailing`), `actions.js`, `sheets.js`, `copy.js`; test.

**Interfaces:** reference `SailingModal`: `ui.sheet = {kind:"sailing", v:0}`; `sail_d` (arg ±1, clamp −3..8), `sail_apply` (`if (v !== 0) shiftHeading(-v, why)` with the twin's `why` strings verbatim), `sail_cancel`. The sheet shows the heading (`headingDesc()`), the resulting heading preview (`HEADINGS[clamp(heading - v)]`), and the sub-line the twin composes.

- [ ] **Step 1: Failing test** — `g.sailing = true; enterView("quest_sailing")` (heading is 1 after the arrival shift); open; `sail_d +1` ×2; `sail_apply` → heading 0, log contains `2 wheels found (sailing test)`.
- [ ] **Steps 2–5.** Commit — `feat(tablet): the sailing test sheet`

---

### Task 9: The 20-tap common round

**Files:** modify `tests/test_tablet.py`.

- [ ] **Step 1:** Extend `_WALK` into the spec's full walk: after `combat_shadow` (in place of the twin's six-tap players-modal round trip) insert `tap("open_players"); tap("all_thr", "1"); tap("sheet_close")`, and rename/retarget the gate test: `test_the_common_round_costs_at_most_20_taps` asserts `taps <= 20`, every player's threat rose by 1, and `view === "round_end"`. Keep the 17-tap assertion as the same test (one gate, the spec's number).
- [ ] **Step 2:** Run; commit — `test(tablet): the common round at 20 taps`

---

## Done when

- `python3 -m pytest tests/` green with `tests/test_tablet_tokens.py` in it.
- In the browser: every zone's Edit chip opens its sheet; a player can be edited, eliminated and averted; a location can be travelled to from the picker and edited in the quest sheet; a stage clears through the resolution sheet to the next stage and to victory; the sailing test shifts the heading; a new game can be started mid-game from the menu.
- The common-round walk is 20 taps.
