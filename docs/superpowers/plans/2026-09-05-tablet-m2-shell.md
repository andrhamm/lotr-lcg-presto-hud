# Tablet Client — Milestone 2: The Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docs/tablet/` boots in a browser, starts or resumes a catalog game, and walks a whole round on a 1366×1024 landscape iPad: the transport strip, the three-zone rail with its log block, and every phase pane with Back / Next / the skip, persisting through the shared data client. No editors, sheets, rules, notes or images yet (milestones 3–6).

**Architecture:** A third client over the same model. `docs/tablet/js/` imports `../../js/gamestate.js`, `phases.js`, `viewcopy.js`, `db.js` and never `ui.js`/`screen*.js`/`main.js` (those are the 480×480 canvas). Rendering is plain DOM from tagged-template HTML strings: every render module exports a pure `renderX(game, ui) -> string` (no `document` at import or render time, so pytest can drive them under node exactly as `tests/test_twin_parity.py` drives the model); `app.js` alone touches the DOM, mounts one `layout()` per state change, delegates clicks by `data-act`, and calls `Session.record()`/`tick()` like `main.js` does. All game mutations go through one pure `dispatch(game, ui, act, arg)` in `actions.js`, which is what the tap-budget test walks. At boot the client sets the two module switches milestone 1 added: `setWindowPolicy(WINDOW_POLICY_BANDS)` and `setBoardTracking(true)`.

**Tech Stack:** ES modules, no build step, no framework; CSS custom properties; Google Fonts (Alegreya, Alegreya Sans); pytest driving node for the tablet's pure modules; `tools/devserver.py` (already serves `docs/`, so `/tablet/` needs no new server).

**Spec:** `docs/superpowers/specs/2026-09-05-tablet-client-design.md` — sections "Structure", "Visual system", "Interaction model", "Code layout", "Testing". Milestone 1's model API is in `docs/superpowers/plans/2026-09-05-tablet-m1-model.md` (landed: commits f0c0217..40825fa).

## Global Constraints

- `docs/tablet/js/*.js` import shared code only from `../../js/` (`gamestate.js`, `phases.js`, `viewcopy.js`, `xtargets.js`, `quest_catalog.js`, `db.js`). Never `ui.js`, `screens*.js`, `screen_play.js`, `main.js`.
- Every render module is pure: no `document`/`window` reference at import or in `render*` functions; `app.js` is the only DOM-touching file. `tests/test_tablet.py` imports the render and action modules under node, where `document` does not exist.
- No `localStorage`/`fetch` outside `docs/js/db.js` (`tests/test_no_stray_io.py` already walks `docs/tablet/`). Storage prefix `"lotr-tablet-"`.
- All play copy comes from `../../js/viewcopy.js` (`VIEW_LABELS`, `PHASE_FRAMEWORK`, `PHASE_WINDOW`, `ACTION_WINDOW_TIPS`, `LOOP_FLOW`, `LOOP_LEGEND`, `STAGING`, `STAGING_PENDING`, `TRAVEL`, `TOTALS`, `OUTCOME`, `QUEST_SETUP`, `SETUP_TIP`, `COMBAT_LAST_CHANCE`, `PROGRESS_PLACEMENT`). Tablet-only chrome strings (zone labels, "Next", "Back", "Rounds", "Game log") live in one `docs/tablet/js/copy.js` so they can move into `viewcopy.py` later; nothing is inlined in markup.
- Type and colour tokens are the spec's: palette from `docs/js/ui.js`'s `pal` verbatim as CSS custom properties; `DISPLAY` 34px Alegreya 600, `BODY` 20px Alegreya Sans (18px on secondary lines, never lower for a sentence), `LABEL` 13px caps tracked; numerals tabular. Every `<button>` is at least 44px tall; the CTA row buttons 64px.
- Nothing in `docs/js/` or `ui/` changes in this milestone except `tools/gen_web_data.py` + a new generated `docs/js/icons_svg.js` (iron rule 2: generated, never hand-edited, byte-compared by `tests/test_viewcopy.py`).
- `python3 -m pytest tests/` stays green (2402 at the start). Commit after every task; do not push.
- The Presto and web twin are untouched: `tests/test_skin_identity.py` and `tests/test_tap_budget.py` unchanged.

## File structure

```
docs/tablet/
  index.html            viewport, fonts link, <div id="app">, <script type="module" src="js/app.js">
  style.css             tokens + layout + primitives (strip, column, zone, pane, band, chip, counter, cta)
  js/
    copy.js             tablet-only chrome strings
    dom.js              h`` tagged template (escapes), raw(), classnames helper
    primitives.js       chip(), band(), counter(), zone(), cta() -> strings
    strip.js            renderStrip(game, ui)
    rail.js             renderRail(game, ui) incl. the log block
    loops.js            renderLoop(flow) for LOOP_FLOW entries
    pane.js             renderPane(game, ui): one branch per flow view + quest_setup + game over
    layout.js           layout(game, ui) -> the whole <div class="app"> (or the new-game / game-over screens)
    actions.js          dispatch(game, ui, act, arg) -> bool (changed); newUi()
    app.js              boot, DataClient({prefix}), render loop, click delegation, persistence, async acts
docs/js/icons_svg.js    GENERATED: {NAME: {size, path}} from ui/icons.py masks (tools/gen_web_data.py)
tests/test_tablet.py    node-driven: every view renders; actions mutate; tap budget ≤ 17 (M2 walk)
```

`ui` is a plain object owned by `app.js` and threaded through every render/dispatch: `{ screen: "play"|"newgame"|"gameover", alloc: null | {locations, quest, side_quests}, picker: {index, busy} }`.

---

### Task 1: Foundations — page, tokens, DOM helpers, primitives, generated stat icons

**Files:**
- Create: `docs/tablet/index.html`, `docs/tablet/style.css`, `docs/tablet/js/copy.js`, `docs/tablet/js/dom.js`, `docs/tablet/js/primitives.js`
- Modify: `tools/gen_web_data.py` (emit `docs/js/icons_svg.js`), `tests/test_viewcopy.py` (`GENERATED` += `"icons_svg.js"`)
- Test: `tests/test_tablet.py` (new; the node harness + primitive tests)

**Interfaces:**
- Produces: `dom.js`: `h` (tagged template; interpolations are HTML-escaped unless wrapped with `raw()`; arrays of strings/raws are joined), `raw(html)`, `esc(s)`, `cx(...names)` (joins truthy class names). `primitives.js`: `chip({act, arg, label, tone="gold", h=44})`, `band({kind: "framework"|"window", text, sub})`, `counter({label, icon, value, act, arg})` (a −/+ pair, 64×52 buttons, `data-act="${act}-"`/`"${act}+"`), `zone({name, icon, edge, ground, body})`, `cta({act, arg, label, tone: "ok"|"skip"|"plain", grow=true})` (64px). `icons_svg.js`: `ICONS = { THREAT: {size, path}, WILLPOWER: …, TRAIL: …, PIPE: …, … }` and `icon(name, px, fill, shadow=null) -> string` (an inline `<svg viewBox="0 0 size size" shape-rendering="crispEdges">` with an optional 1px-offset shadow path first).
- `copy.js`: `CHROME = { next: "Next", back: "Back", players: "Players", quest: "Quest", staging: "Staging", log: "Game log", round: "Round", newGame: "New game", resume: "Resume", begin: "Begin", eliminated: "Eliminated", noLocation: "no active location", sideQuest: "+ side quest" }`.

- [ ] **Step 1: Write the node harness and the first failing tests**

`tests/test_tablet.py`:

```python
"""The tablet client's pure modules, driven under node the way
test_twin_parity.py drives the model. Render functions return strings and
never touch `document`, which is what makes this possible."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _stage(tmp):
    """Copy docs/js and docs/tablet/js so ../../js imports resolve."""
    for sub in ("js", os.path.join("tablet", "js")):
        src = os.path.join(ROOT, "docs", sub)
        dst = os.path.join(tmp, sub)
        os.makedirs(dst, exist_ok=True)
        for f in os.listdir(src):
            if f.endswith(".js"):
                shutil.copy(os.path.join(src, f), os.path.join(dst, f))
    with open(os.path.join(tmp, "package.json"), "w") as f:
        f.write('{"type":"module"}')


def node(probe):
    """Run `probe` (an ES module body) from tablet/js/ and return its JSON."""
    exe = shutil.which("node")
    if exe is None:
        pytest.skip("node not installed")
    with tempfile.TemporaryDirectory() as tmp:
        _stage(tmp)
        path = os.path.join(tmp, "tablet", "js", "probe.mjs")
        with open(path, "w") as f:
            f.write(probe)
        r = subprocess.run([exe, path], cwd=tmp, capture_output=True, text=True)
        assert r.returncode == 0, "tablet module failed to load:\n%s" % r.stderr
        return json.loads(r.stdout)


def test_h_escapes_interpolations_but_not_raw():
    js = node("""
import { h, raw } from "./dom.js";
console.log(JSON.stringify({
  esc: h`<b>${"<i>&"}</b>`,
  raw: h`<b>${raw("<i>x</i>")}</b>`,
  list: h`<ul>${["a", raw("<li>b</li>")]}</ul>`,
}));
""")
    assert js["esc"] == "<b>&lt;i&gt;&amp;</b>"
    assert js["raw"] == "<b><i>x</i></b>"
    assert js["list"] == "<ul>a<li>b</li></ul>"


def test_primitives_are_buttons_with_actions():
    js = node("""
import { chip, cta, counter, band } from "./primitives.js";
console.log(JSON.stringify({
  chip: chip({ act: "open_log", label: "Open" }),
  cta: cta({ act: "advance", label: "Next: Travel" }),
  counter: counter({ label: "Staging area", icon: "", value: 4, act: "stg" }),
  band: band({ kind: "window", text: "Responses.", sub: "Last window." }),
}));
""")
    assert 'data-act="open_log"' in js["chip"] and js["chip"].startswith("<button")
    assert 'data-act="advance"' in js["cta"] and "Next: Travel" in js["cta"]
    assert 'data-act="stg-"' in js["counter"] and 'data-act="stg+"' in js["counter"]
    assert ">4<" in js["counter"]
    assert 'class="band band-window"' in js["band"] and "Last window." in js["band"]


def test_stat_icons_are_generated_from_the_masks():
    js = node("""
import { ICONS, icon } from "../../js/icons_svg.js";
console.log(JSON.stringify({ names: Object.keys(ICONS).sort().slice(0, 4),
  threat: icon("THREAT", 28, "#f7653e", "#070503") }));
""")
    assert "THREAT" in js["names"] or "ARCHERY" in js["names"]
    assert js["threat"].startswith("<svg") and 'viewBox="0 0 20 20"' in js["threat"]
    assert js["threat"].count("<path") == 2      # shadow first, then the fill
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m pytest tests/test_tablet.py -q`
Expected: FAIL — node cannot find `./dom.js` (`ERR_MODULE_NOT_FOUND`).

- [ ] **Step 3: Generate the stat icons**

In `tools/gen_web_data.py`, after the `icons.js` block, add a second emitter that writes `docs/js/icons_svg.js`. It converts each mask (a list of `n` ints, bit `n-1-x` set = pixel on) to one SVG path of horizontal runs:

```python
# The same masks as SVG path data, for the tablet client (which draws with
# the DOM, not a framebuffer). One path per icon: each horizontal run of set
# pixels is an "M x y h w v1 h-w z" rectangle. shape-rendering: crispEdges at
# the draw site keeps the pixel look at any size.
def _runs_path(mask):
    n = len(mask)
    d = []
    for y, row in enumerate(mask):
        x = 0
        while x < n:
            if (row >> (n - 1 - x)) & 1:
                x0 = x
                while x < n and (row >> (n - 1 - x)) & 1:
                    x += 1
                d.append("M%d %dh%dv1h-%dz" % (x0, y, x - x0, x - x0))
            else:
                x += 1
    return "".join(d)

out = ["// GENERATED from ui/icons.py - do not edit (tools/gen_web_data.py)",
       "export const ICONS = %s;" % json.dumps(
           {n: {"size": len(getattr(icons, n)), "path": _runs_path(getattr(icons, n))}
            for n in names}, sort_keys=True),
       """
// An inline SVG of one mask. `shadow`, when given, is drawn first offset by
// (1, 1) - the charcoal under the red helm, the brown under the ranger.
export function icon(name, px, fill, shadow = null) {
  const m = ICONS[name];
  if (!m) return "";
  const sh = shadow
    ? `<path d="${m.path}" fill="${shadow}" transform="translate(1 1)"></path>` : "";
  return `<svg viewBox="0 0 ${m.size} ${m.size}" width="${px}" height="${px}" `
    + `shape-rendering="crispEdges" style="display:block;flex:none">${sh}`
    + `<path d="${m.path}" fill="${fill}"></path></svg>`;
}
"""]
open(os.path.join(root, "icons_svg.js"), "w").write("\n".join(out) + "\n")
```

(`names` is the list the existing `icons.js` block already computes.) Run `python3 tools/gen_web_data.py`. Add `"icons_svg.js"` to `GENERATED` in `tests/test_viewcopy.py` and to the generated-file list in its docstring.

- [ ] **Step 4: Write `dom.js`, `copy.js`, `primitives.js`**

`docs/tablet/js/dom.js`:

```js
// HTML from tagged templates. Every interpolation is escaped unless it is a
// raw() fragment; arrays are joined. That is the whole safety story for a
// client that renders card names and log text it did not write.
const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = s => String(s).replace(/[&<>"']/g, c => ESC[c]);
export class Raw { constructor(html) { this.html = html; } }
export const raw = html => new Raw(html);
const one = v => (v instanceof Raw ? v.html : Array.isArray(v) ? v.map(one).join("") : esc(v ?? ""));
export const h = (strings, ...vals) =>
  strings.reduce((out, s, i) => out + s + (i < vals.length ? one(vals[i]) : ""), "");
export const cx = (...names) => names.filter(Boolean).join(" ");
```

`docs/tablet/js/copy.js` holds `CHROME` exactly as listed under Interfaces.

`docs/tablet/js/primitives.js`:

```js
import { h, raw, cx } from "./dom.js";

// Bevelled = tappable: the HUD's one chrome rule, kept. Every button is a
// real <button> with a data-act; app.js delegates on it.
export function chip({ act, arg = "", label, tone = "gold", height = 44 }) {
  return h`<button type="button" class="${cx("chip", "chip-" + tone)}" style="height:${height}px" data-act="${act}" data-arg="${arg}">${raw(label)}</button>`;
}

export function band({ kind, text, sub = null }) {
  return h`<div class="${cx("band", "band-" + kind)}"><div class="band-text"><p class="body">${text}</p>${sub ? raw(h`<p class="body secondary">${sub}</p>`) : ""}</div></div>`;
}

export function counter({ label, icon, value, act, arg = "" }) {
  return h`<div class="counter"><div class="label">${label}</div><div class="counter-row">
<button type="button" class="step" data-act="${act}-" data-arg="${arg}">&minus;</button>
<div class="counter-value"><span class="num num-64">${value}</span>${raw(icon)}</div>
<button type="button" class="step" data-act="${act}+" data-arg="${arg}">+</button></div></div>`;
}

export function zone({ name, icon, edge, ground, body }) {
  return h`<section class="${cx("zone", "zone-" + edge, "ground-" + ground)}"><header class="zone-head">${raw(icon)}<span class="label">${name}</span></header><div class="zone-body">${raw(body)}</div></section>`;
}

export function cta({ act, arg = "", label, tone = "ok", grow = true }) {
  return h`<button type="button" class="${cx("cta", "cta-" + tone, grow && "grow")}" data-act="${act}" data-arg="${arg}">${raw(label)}</button>`;
}
```

- [ ] **Step 5: Write `index.html` and `style.css`**

`docs/tablet/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>LOTR LCG tracker — tablet</title>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Alegreya:wght@500;600;700&family=Alegreya+Sans:wght@400;500;700&display=swap">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div id="app"></div>
  <script type="module" src="js/app.js"></script>
</body>
</html>
```

`docs/tablet/style.css` opens with the tokens (values are `docs/js/ui.js`'s `pal`, verbatim) and the type scale, then the layout and primitives:

```css
:root {
  --bg: rgb(16,12,9); --card: rgb(36,32,21); --card-hi: rgb(48,44,29); --well: rgb(24,20,12);
  --border: rgb(60,54,35); --border-gold: rgb(150,118,48);
  --gold: rgb(214,180,110); --tan: rgb(200,186,144); --muted: rgb(180,162,118); --dim: rgb(162,146,100);
  --green: rgb(136,168,92); --amber: rgb(214,164,70); --red: rgb(247,101,62); --purple: rgb(166,122,196);
  --btn: rgb(52,42,26); --btn-ok: rgb(40,50,26); --ok-fg: rgb(158,196,104); --btn-no: rgb(56,26,18); --no-fg: rgb(224,112,80);
  --bevel-l: rgb(96,86,54); --bevel-d: rgb(7,5,3); --outline: rgb(0,0,0); --brown: rgb(104,70,34);
  --serif: 'Alegreya', Georgia, 'Times New Roman', serif;
  --sans: 'Alegreya Sans', 'Gill Sans', 'Trebuchet MS', system-ui, sans-serif;
}
html, body { margin: 0; height: 100%; background: var(--bg); color: var(--tan); font: 20px/1.35 var(--sans); }
#app, .app { width: 100vw; height: 100vh; overflow: hidden; }
.display { font: 600 34px/1.1 var(--serif); color: var(--gold); }
.body { font: 20px/1.35 var(--sans); color: var(--tan); margin: 0; text-wrap: pretty; }
.body.secondary { font-size: 18px; color: var(--muted); }
.label { font: 700 13px/1 var(--sans); letter-spacing: .09em; text-transform: uppercase; color: var(--dim); }
.num { font-family: var(--sans); font-weight: 600; line-height: 1; font-variant-numeric: tabular-nums; color: var(--gold); }
.num-26 { font-size: 26px } .num-36 { font-size: 36px } .num-40 { font-size: 40px } .num-48 { font-size: 48px } .num-56 { font-size: 56px } .num-64 { font-size: 64px } .num-84 { font-size: 84px }
button { font: inherit; color: inherit; cursor: pointer; touch-action: manipulation; }
.chip { display: inline-flex; align-items: center; gap: 8px; padding: 0 14px; background: var(--btn);
  border: 1px solid var(--bevel-l); border-bottom-color: var(--bevel-d); border-right-color: var(--bevel-d);
  border-radius: 6px; font: 700 13px/1 var(--sans); letter-spacing: .08em; text-transform: uppercase; white-space: nowrap; }
.chip-gold { color: var(--gold) } .chip-tan { color: var(--tan) } .chip-amber { color: var(--amber) }
.cta { display: flex; align-items: center; justify-content: center; height: 64px; padding: 0 24px; border-radius: 8px;
  border: 1px solid; border-bottom: 3px solid var(--bevel-d); font: 600 22px/1 var(--sans); white-space: nowrap; }
.cta.grow { flex: 1 1 0 } .cta-ok { background: var(--btn-ok); color: var(--ok-fg); border-color: var(--green) }
.cta-skip { background: var(--card); color: var(--amber); border-color: var(--amber) }
.cta-plain { background: var(--btn); color: var(--tan); border-color: var(--bevel-l) }
.step { width: 64px; height: 52px; background: var(--btn); border: 1px solid var(--bevel-l); border-bottom-color: var(--bevel-d); border-right-color: var(--bevel-d); border-radius: 6px; font-size: 30px; color: var(--tan); }
.band { display: flex; gap: 16px; align-items: center; padding: 10px 12px 10px 18px; background: var(--card); border: 1px solid var(--border); border-left: 6px solid; border-radius: 6px; }
.band-framework { border-left-color: var(--red) } .band-window { border-left-color: var(--green) }
.band-text { display: flex; flex-direction: column; gap: 6px; min-width: 0; flex: 1 1 0 }
.counter { display: flex; flex-direction: column; gap: 10px; padding: 12px 16px; background: var(--card); border: 1px solid var(--border); border-radius: 8px; flex: 1 1 0; min-width: 0 }
.counter-row { display: flex; align-items: center; justify-content: space-between; gap: 12px }
.counter-value { display: flex; align-items: center; gap: 14px }
.zone { display: flex; flex-direction: column; gap: 8px; padding: 8px 10px 10px; border: 1px solid var(--border); border-top: 3px solid; border-radius: 8px; min-width: 0 }
.zone-head { display: flex; align-items: center; gap: 8px } .zone-head .label { color: var(--gold) }
.zone-gold { border-top-color: var(--gold) } .zone-green { border-top-color: var(--green) } .zone-outline { border-top-color: var(--outline) }
.ground-card { background: var(--card) } .ground-well { background: var(--well) }
```

Layout classes (`.app`, `.strip`, `.body-row`, `.column`, `.pane`, `.cta-row`, `.player-cell`, `.pill`, `.log-block`, `.seg`, `.tick`) are added by the tasks that own them; keep them in this one file.

- [ ] **Step 6: Run the tests, then the whole suite**

Run: `python3 -m pytest tests/test_tablet.py tests/test_viewcopy.py -q` — Expected: passed.
Run: `python3 -m pytest tests/ -q` — Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add docs/tablet tools/gen_web_data.py docs/js/icons_svg.js tests/test_tablet.py tests/test_viewcopy.py
git commit -m "feat(tablet): page, tokens, DOM helpers, primitives, generated stat icons"
```

---

### Task 2: Actions — one pure dispatch over the model

**Files:**
- Create: `docs/tablet/js/actions.js`
- Test: `tests/test_tablet.py`

**Interfaces:**
- Produces: `newUi() -> {screen: "play", alloc: null, picker: null}`; `dispatch(game, ui, act, arg) -> boolean` (true when the game or `ui` changed and a re-render + `Session.record()` are due). Reference for each action's model calls: `docs/js/screen_play.js`'s `onButton` (read it; the calls below are the same ones).

Action table (the `act` string, the `arg`, the model calls):

| act | arg | does |
|---|---|---|
| `advance` | — | `game.advanceView()`; `ui.alloc = null` |
| `back` | — | `return game.backView()` (false when nothing to go back to) |
| `flip_to_b` | — | `const pts = game.flipToB(); game.logEvent(\`Setup complete - round 1 begins (quest ${game.questLabel()} needs ${pts})\`); game.enterView(VIEW_ORDER[0]); game._snapshotRound();` |
| `wp-` / `wp+` | — | `game.setWillpower(game.willpower ∓ 1)` |
| `stg-` / `stg+` | — | `game.setStaging(game.staging ∓ 1)` |
| `resolve` | — | `game.enterView("quest_resolution"); if (!game.quest_resolved) { const r = game.resolveQuest(game.willpower, game.staging); ui.alloc = null; if (r.outcome === "success") game.pending_budget = r.budget; }` |
| `alloc+` / `alloc-` | `"quest"` or `"side:<i>"` | the cascade from `screen_play.js` (`ap`/`am`): `+` fills active locations in order before the quest; `-` pulls back the quest first, then unwinds the last location. `ui.alloc` is created lazily as `game.autoSplit(game.pending_budget)` the first time the resolution pane renders (see Task 5) or any alloc act runs |
| `alloc_reset` | — | zero every placement in `ui.alloc` |
| `apply_alloc` | — | `const used = …; const discard = game.pending_budget - used; const completed = game.placeProgress(ui.alloc); game.logEvent(msg)` (same message as the twin: `Placed N progress[, discarded D (over capacity)][ (completed…)]`); `game.pending_budget = 0; ui.alloc = null; ui.placed = true` (a flag the resolution pane reads to switch from the allocator to the placed summary; cleared by `advance`/`back`). Do NOT enter `aw_quest_resolution`: under bands the resolution view is its own window; `Next` hands to travel. Leave `game.pending_resolution` as the model set it (milestone 3's sheet consumes it) |
| `eng-` / `eng+` | player index | `game.setEngaged(i, game.players[i].engaged ∓ 1)` |
| `stgen-` / `stgen+` | — | `game.setStagingEnemies(game.staging_enemies ∓ 1)` |
| `stgloc-` / `stgloc+` | — | `game.setStagingLocations(game.staging_locations ∓ 1)` |
| `skip` | skip id | `return game.skipTo(arg) !== null` |
| `endround` | — | `game.endRound()` |
| `new_game` / `pick_scenario` / `resume` | — | NOT here: they are async (catalog reads) and owned by `app.js` |

`dispatch` returns `false` for an unknown act and never throws on one.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tablet.py`:

```python
_WALK = """
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS, setBoardTracking } from "../../js/gamestate.js";
import { dispatch, newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS); setBoardTracking(true);
const g = new GameState(4, 25);
g.advanceView();                       // setup -> round 1 (no catalog: a bare game)
[3, 4, 2, 2].forEach((c, i) => g.setCommit(i, c));
g.quest.points = 20;                   // room enough that the walk never clears the stage
const ui = newUi();
const taps = [];
const tap = (act, arg) => { taps.push(act); return dispatch(g, ui, act, arg ?? ""); };
tap("advance");                        // resource -> planning
tap("advance");                        // planning -> quest_commit
tap("wp-");                            // 11 -> 10, detached total
tap("advance");                        // -> quest_staging
tap("stg+"); tap("stg+"); tap("stg+");
tap("resolve");                        // -> quest_resolution, resolved
const budget = g.pending_budget;
tap("apply_alloc");
const placed = g.quest.progress;
tap("advance");                        // -> travel
tap("advance");                        // -> enc_optional
tap("advance");                        // -> enc_checks
tap("advance");                        // -> combat_shadow
tap("advance");                        // -> combat_enemy
tap("advance");                        // -> combat_player
tap("advance");                        // -> refresh
tap("advance");                        // -> round_end
"""
# _WALK prints nothing; each test appends the one console.log it wants.


def test_the_m2_walk_reaches_round_end_in_17_taps():
    """The HUD's tap-budget walk minus the shadow-effect threat edits (those
    need the players sheet, milestone 3). 31 taps on the HUD for the whole
    walk; 17 here for this part of it, and the count is the gate."""
    js = node(_WALK + """
console.log(JSON.stringify({ taps: taps.length, view: g.view, round: g.round,
  willpower: g.willpower, staging: g.staging, budget, placed,
  unknown: dispatch(g, ui, "nope", ""), first: g.first_player }));
""")
    assert js["view"] == "round_end"
    assert js["round"] == 1
    assert js["taps"] <= 17
    assert js["willpower"] == 10 and js["staging"] == 3
    assert js["budget"] == 7 and js["placed"] == 7
    assert js["first"] == 1              # the token passed on arrival at refresh
    assert js["unknown"] is False


def test_endround_starts_the_next_round():
    js = node(_WALK + """
const changed = dispatch(g, ui, "endround", "");
console.log(JSON.stringify({ changed, view: g.view, round: g.round }));
""")
    assert js == {"changed": True, "view": "resource", "round": 2}
```

- [ ] **Step 2: Run to verify failure** — `python3 -m pytest tests/test_tablet.py -q` → `ERR_MODULE_NOT_FOUND ./actions.js`.

- [ ] **Step 3: Write `actions.js`** implementing the table above; keep each case a few lines; the allocation cascade is copied from `screen_play.js` verbatim with `this.alloc` → `ui.alloc` and `btn.id` → `arg`. Add at the top:

```js
// Every tap that changes the game goes through here, and nothing here reads
// the DOM: that is what lets tests/test_tablet.py walk a round under node
// and count the taps.
import { VIEW_ORDER } from "../../js/gamestate.js";
export const newUi = () => ({ screen: "play", alloc: null, placed: false, picker: null });
```

- [ ] **Step 4: Run the tests and the whole suite** — green.

- [ ] **Step 5: Commit** — `git commit -m "feat(tablet): one pure dispatch over the model, with the milestone-2 walk as its test"`

---

### Task 3: The transport strip

**Files:**
- Create: `docs/tablet/js/strip.js`; append `.strip` / `.seg` / `.tick` rules to `docs/tablet/style.css`
- Test: `tests/test_tablet.py`

**Interfaces:**
- Produces: `renderStrip(game, ui) -> string`: a `<header class="strip">` with the round block, one `<div class="seg" data-phase="…">` per phase in `PHASES` order that has a flow view (Resource, Planning, Quest, Travel, Encounter, Combat, Refresh, End — "Beginning" has none and is skipped), and inside each segment one `<span class="tick tick-framework|tick-window is-done|is-current|is-future" data-view="…">` per flow view plus a `tick-window` after any view whose `windowAfter(v)` exists (the window is on the view under bands but the strip still shows it as its own tick). The current view's tick carries `is-current` and a `<i class="playhead">`. A segment whose views are all passed by a promoted skip offer (`game.skipOffer()?.promoted`, views strictly between the offer's origin and its landing) gets `is-skippable` and a `.seg-note` with the landing's step id. Each segment shows a badge with the count of this round's log entries whose `step` equals one of its views' `VIEW_STEP`s, when non-zero. Ticks are not buttons in this milestone (rewind lands in milestone 4).
- Consumes: `flowViews`, `VIEW_STEP`, `windowAfter`, `isActionWindow`, `VIEW_LABELS` (from `gamestate.js`/`viewcopy.js`), `PHASES`, `step` (from `phases.js`).

- [ ] **Step 1: Failing tests**

```python
def test_strip_has_a_segment_per_phase_and_a_playhead_on_the_current_view():
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderStrip } from "./strip.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView(); g.enterView("quest_staging");
const html = renderStrip(g, newUi());
console.log(JSON.stringify({ segs: (html.match(/class="seg/g) || []).length,
  current: (html.match(/is-current/g) || []).length,
  currentView: /data-view="quest_staging"[^>]*is-current|is-current[^>]*data-view="quest_staging"/.test(html),
  windows: (html.match(/tick-window/g) || []).length, aw: html.includes("aw_"),
  round: html.includes(">1<") }));
""")
    assert js["segs"] == 8
    assert js["current"] == 1 and js["currentView"]
    assert js["windows"] >= 8          # every aw_ window plus the two combat windows
    assert js["aw"] is False           # window views are ticks, never named
    assert js["round"]


def test_strip_marks_the_combat_segment_skippable_when_the_offer_is_promoted():
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderStrip } from "./strip.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView(); g.enterView("enc_checks");
const a = renderStrip(g, newUi());
g.setEngaged(0, 1);
const b = renderStrip(g, newUi());
console.log(JSON.stringify({ promoted: /data-phase="Combat"[^>]*is-skippable/.test(a),
  demoted: /data-phase="Combat"[^>]*is-skippable/.test(b), landing: a.includes("6.P") }));
""")
    assert js["promoted"] and js["landing"]
    assert js["demoted"] is False
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement `strip.js`** per Interfaces. Group flow views by `step(VIEW_STEP[v]).phase`. Use `h` and `cx`. Styles: the strip is 96px tall, `display:flex; gap:8px; padding:12px 18px; background: var(--well); border-bottom: 1px solid var(--border)`; a segment is a bordered card with the phase name (`.seg-name`, Alegreya 18px 600; gold when current, tan when done, dim when future, amber when skippable) above a row of ticks; a tick is `22×22` (`tick-framework`: 2px radius, `var(--red)` when done/current, dim when future; `tick-window`: `12×12` round, `var(--green)`); `.playhead` is a gold triangle above the current tick.
- [ ] **Step 4: Tests + suite green.**
- [ ] **Step 5: Commit** — `git commit -m "feat(tablet): the transport strip"`

---

### Task 4: The rail and the log block

**Files:**
- Create: `docs/tablet/js/rail.js`; append `.column` / `.player-cell` / `.pill` / `.log-block` rules to `docs/tablet/style.css`
- Test: `tests/test_tablet.py`

**Interfaces:**
- Produces: `renderRail(game, ui) -> string`: an `<aside class="column">` holding three `zone()`s and the log block.
  - PLAYERS (`edge: "gold"`, `ground: "card"`, icon `icon("THREAT", 22, red, bevel-d)`): a 2×2 grid of `.player-cell`s — `P{n}` label (gold with a flag glyph for `first_player`), threat `num-36` with the red helm, a 3px bar (`--red` when `threat >= elimination - 10`, else `--gold`), a row with willpower commit (`icon("WILLPOWER", 20, gold)` + `num-26`) and engaged (`icon("THREAT", 20, outline, bevel-l)` + `num-26`, dim when 0). An eliminated player's cell adds `is-eliminated` and the label `CHROME.eliminated`.
  - QUEST (`edge: "green"`, icon `icon("TRAIL", 22, green, brown)`): a stage pill (`Stage {questLabel()}`, `progress / points`, the stage name if `game.stages[stage_idx]?.cards[card_idx]?.name`), a location pill for `active_locations[0]` (`name`, `progress / points`) or a dashed `CHROME.noLocation` slot, and a dashed `CHROME.sideQuest` slot (side quests get their pills in milestone 3).
  - STAGING (`edge: "outline"`, `ground: "well"`, icon `icon("THREAT", 22, outline, bevel-l)`): three compact pills — threat (`game.staging`), enemies (`staging_enemies`), locations (`staging_locations`) — each `num-34` with the black helm.
  - The log block (`.log-block`, pinned to the column's bottom with `margin-top:auto`): `CHROME.log` label, the last five `game.log` entries as rows (`fmtMs(e.t)` when `t` is a number, else blank; text with ellipsis), then a prompt row `▶ {VIEW_LABELS[game.view]}`.
- No chips, no buttons in this milestone: rail values are status (spec); the "Edit ›" chips arrive with the sheets in milestone 3, "Open ›" with the log screen in milestone 4.

- [ ] **Step 1: Failing tests**

```python
def test_rail_shows_every_player_and_the_three_zones():
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderRail } from "./rail.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(3, 25); g.advanceView();
g.adjustThreat(2, 16); g.setEngaged(2, 1); g.setStagingEnemies(2); g.setStaging(5);
g.logEvent("P1 threat 25 -> 26");
const html = renderRail(g, newUi());
console.log(JSON.stringify({ zones: (html.match(/class="zone /g) || []).length,
  cells: (html.match(/player-cell/g) || []).length, danger: html.includes("bar-danger"),
  buttons: html.includes("<button"), log: html.includes("P1 threat 25 -&gt; 26"),
  prompt: html.includes("Resource"), staging: />5</.test(html) && />2</.test(html) }));
""")
    assert js["zones"] == 3 and js["cells"] == 3
    assert js["danger"]                # P3 at 41 is within 10 of elimination
    assert js["buttons"] is False      # status, not controls, in this milestone
    assert js["log"] and js["prompt"] and js["staging"]
```

- [ ] **Step 2: Run to verify failure.** — [ ] **Step 3: Implement `rail.js`.** Column: `width: 324px; display:flex; flex-direction:column; gap:10px; padding:12px; background: var(--well); border-right: 1px solid var(--border); overflow:hidden`. — [ ] **Step 4: Tests + suite green.** — [ ] **Step 5: Commit** — `git commit -m "feat(tablet): the three-zone rail and the log block"`

---

### Task 5: The phase panes

**Files:**
- Create: `docs/tablet/js/loops.js`, `docs/tablet/js/pane.js`, `docs/tablet/js/layout.js`; append `.pane` / `.cta-row` / `.loop` / `.alloc` rules to `style.css`
- Test: `tests/test_tablet.py`

**Interfaces:**
- Produces: `renderLoop(flow) -> string` (a `LOOP_FLOW` entry → framing line, numbered rungs with a green dot where `rung[1]` is true, `Repeat until …` exit from `flow.exit`, the note with `flow.note_kind`, the `LOOP_LEGEND` line). `renderPane(game, ui) -> string`: a `<main class="pane">` for the current view. `layout(game, ui) -> string`: `ui.screen === "play"` → `<div class="app">${renderStrip}<div class="body-row">${renderRail}${renderPane}</div></div>`; `"gameover"` → a centred `display` title (`Victory!` / `Defeat`, from `game.game_over.result`), the round and `gameDuration()`, and one `cta({act:"new_game", label: CHROME.newGame})`; `"newgame"` → `renderNewGame(ui)` (Task 6).
- Every pane: a title row (`<h1 class="display">` = `VIEW_LABELS[view]`, plus a `label` line `Round {round} · step {step} · first player P{first_player+1}`), the parts below, then a `.cta-row`: `cta({act:"back", label:"‹ " + CHROME.back, tone:"plain", grow:false})` only when `game.canGoBack()`; the skip CTA when `game.skipOffer()` returns an offer (`tone: promoted ? "skip" : "plain"`, label `offer.skip.label`, `act:"skip"`, `arg: offer.skip.id`); `cta({act:"advance", label: nxt ? \`Next: ${VIEW_LABELS[nxt]}\` : CHROME.next})` with `nxt = game.nextPhaseView()` — except the views in the table that name their own CTA.

Per-view parts (copy keys are `viewcopy.js` exports; read `docs/js/screen_play.js`'s `draw()` for how the twin assembles the same keys):

| view | parts |
|---|---|
| `quest_setup` | title `VIEW_LABELS.quest_setup`; `SETUP_TIP` lines as a framework band; the setup instruction from `QUEST_SETUP.resolve`/`.none` with `%s` → stage number and side-A name (the A face is `game.stages[game.stage_idx].cards[game.card_idx]`; its `text` decides resolve vs none), then `QUEST_SETUP.then_flip`; the A face's printed `text` in a `.well` block when present; CTA `cta({act:"flip_to_b", label: QUEST_SETUP.begin})`, no Back |
| `resource` | framework band `PHASE_FRAMEWORK.resource`; window band `ACTION_WINDOW_TIPS.resource[0]` |
| `planning` | `renderLoop(LOOP_FLOW.planning)` |
| `quest_sailing` | the heading (`game.headingDesc()`) as a `display` value; `SAILING` copy; Next (the sailing test sheet is milestone 3) |
| `quest_commit` | window band `PHASE_WINDOW.quest_commit`, sub `ACTION_WINDOW_TIPS.quest_commit.join(" ")`; `counter({label: TOTALS.willpower, icon: icon("WILLPOWER", 40, gold), value: game.willpower, act:"wp"})` |
| `quest_staging` | framework band `STAGING.framework`; window band `STAGING.window`, sub `ACTION_WINDOW_TIPS.quest_staging.join(" ")`; two counters (`TOTALS.willpower` / `wp`, `TOTALS.staging` / `stg` with the black helm); a "without actions" block from `game.questPreview()` → `[outcome, n, room]`: success → `OUTCOME.toast_success` with `%d` → n; fail → `OUTCOME.toast_fail`; tie → `OUTCOME.toast_tie`; plus `PROGRESS_PLACEMENT`; CTA label `Resolve Quest. ${outcome text}` with `act:"resolve"` |
| `quest_resolution` | if `game.pending_budget > 0 && !ui.placed`: the allocator — `ui.alloc ??= game.autoSplit(game.pending_budget)`; header `OUTCOME.alloc_header` (`%d` → budget), caption `OUTCOME.alloc_caption`; one row per active location (`name`, `progress + alloc / points`, no stepper — locations fill by the cascade), the quest row with `alloc+`/`alloc-` (`arg:"quest"`), each side quest with `arg:"side:i"`, an `OUTCOME.alloc_unplaced` line when the budget exceeds room, `chip({act:"alloc_reset", label:"Reset"})`, CTA `cta({act:"apply_alloc", label:"Place progress"})`. Otherwise (failed/tied, or placed): the outcome line (`OUTCOME.card_fail`/`card_tie`/success summary of `quest_outcome_n`), the window band `ACTION_WINDOW_TIPS.quest_resolution[0]`, Next |
| `travel` | `game.active_locations.length ? band(framework, TRAVEL.blocked) : band(window, TRAVEL.open)`; window band `ACTION_WINDOW_TIPS.travel.join(" ")`; Next (travelling needs the picker, milestone 3) |
| `enc_optional` | window band `PHASE_WINDOW.enc_optional`, sub `ACTION_WINDOW_TIPS.enc_optional.join(" ")` |
| `enc_checks` | `renderLoop(LOOP_FLOW.enc_checks)`; window band `ACTION_WINDOW_TIPS.enc_checks.join(" ")`; a two-column block: "Checks made" (a line naming `game.staging_enemies` enemies in staging and the engaged total) and, when `skipOffer()`, the offer block (`offer.skip.claim`, promoted → amber border; demoted → a line naming the counts: `The tracker shows ${engaged} engaged and ${staging_enemies} in staging.`); the skip CTA per the common rule |
| `combat_shadow` | framework band `PHASE_FRAMEWORK.combat_shadow`; window band `PHASE_WINDOW.combat_shadow` |
| `combat_enemy` | `renderLoop(LOOP_FLOW.combat_enemy)`; the engaged steppers: a 4-up grid of `counter`-like cells per player (`act:"eng"`, `arg: i`, 44px steps, the black helm, `num-34`) |
| `combat_player` | `renderLoop(LOOP_FLOW.combat_player)`; a note band with `COMBAT_LAST_CHANCE` |
| `refresh` | framework band `PHASE_FRAMEWORK.refresh`; window band `PHASE_WINDOW.refresh`, sub `ACTION_WINDOW_TIPS.refresh.join(" ")` |
| `round_end` | title `End of Round ${round}`; framework band `PHASE_FRAMEWORK.round_end`; CTA `cta({act:"endround", label: \`Next: ${VIEW_LABELS.resource} (Round ${round + 1})\`})` |
| any `aw_` view (a resumed cross-client save) | render the pane of `phaseViewOf(view)` — navigation already maps it |

- [ ] **Step 1: Failing tests**

```python
_ALL_VIEWS = """
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS, flowViews } from "../../js/gamestate.js";
import { layout } from "./layout.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const out = {};
for (const v of flowViews()) {
  const g = new GameState(4, 25); g.advanceView(); g.enterView(v);
  if (v === "quest_resolution") { g.setWillpower(9); g.setStaging(2); g.resolveQuest(9, 2); g.pending_budget = 7; }
  const html = layout(g, newUi());
  out[v] = { len: html.length, next: html.includes('data-act="advance"') || html.includes('data-act="endround"'),
             bad: /undefined|NaN|\\[object Object\\]/.test(html), title: html.includes('class="display"') };
}
console.log(JSON.stringify(out));
"""


def test_every_flow_view_renders_a_pane_with_a_way_forward():
    js = node(_ALL_VIEWS)
    for v, r in js.items():
        assert r["len"] > 2000, v
        assert r["title"], v
        assert not r["bad"], v
        assert r["next"] or v == "quest_resolution", v


def test_resolution_pane_offers_the_allocator_then_the_window():
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderPane } from "./pane.js";
import { dispatch, newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView(); g.enterView("quest_staging");
g.setWillpower(9); g.setStaging(2); g.quest.points = 20;
const ui = newUi();
dispatch(g, ui, "resolve", "");
const before = renderPane(g, ui);
dispatch(g, ui, "apply_alloc", "");
const after = renderPane(g, ui);
console.log(JSON.stringify({ allocator: before.includes('data-act="apply_alloc"'),
  placed: after.includes('data-act="advance"') && !after.includes('data-act="apply_alloc"'),
  progress: g.quest.progress }));
""")
    assert js["allocator"] and js["placed"] and js["progress"] == 7


def test_enc_checks_pane_carries_the_skip_cta_promoted_or_demoted():
    js = node("""
import { GameState, setWindowPolicy, WINDOW_POLICY_BANDS } from "../../js/gamestate.js";
import { renderPane } from "./pane.js";
import { newUi } from "./actions.js";
setWindowPolicy(WINDOW_POLICY_BANDS);
const g = new GameState(2, 25); g.advanceView(); g.enterView("enc_checks");
const a = renderPane(g, newUi()); g.setEngaged(1, 2); const b = renderPane(g, newUi());
console.log(JSON.stringify({ a: /data-act="skip"[^>]*/.exec(a)?.[0] ?? "", b: /class="cta cta-(\\w+)[^>]*data-act="skip"/.exec(b)?.[1] ?? "",
  aTone: /class="cta cta-(\\w+)[^>]*data-act="skip"/.exec(a)?.[1] ?? "", counts: b.includes("2 engaged") }));
""")
    assert 'data-arg="combat_empty"' in js["a"]
    assert js["aTone"] == "skip" and js["b"] == "plain" and js["counts"]
```

- [ ] **Step 2: Run to verify failure.** — [ ] **Step 3: Implement `loops.js`, `pane.js`, `layout.js`** per the tables. The pane is `flex:1 1 0; display:flex; flex-direction:column; gap:12px; padding:14px 18px 16px; min-width:0`; `.cta-row { display:flex; gap:12px; margin-top:auto }`. Loop rungs are numbered gold circles with a 2px connector; a window dot is `9px` round green. — [ ] **Step 4: Tests + suite green.** — [ ] **Step 5: Commit** — `git commit -m "feat(tablet): every phase pane, the loop diagram, and the page layout"`

---

### Task 6: Boot, persistence, new game, resume

**Files:**
- Create: `docs/tablet/js/app.js`, `docs/tablet/js/newgame.js`
- Modify: `docs/tablet/js/layout.js` (the `newgame` branch), `.claude/launch.json` (add a `tablet` entry that reuses the web-twin server: same `python3 tools/devserver.py --port 8643 --directory docs` command, `"url": "http://localhost:8643"` is the origin; the page is `/tablet/`)
- Test: `tests/test_tablet.py` (the new-game screen renders; the app module is NOT imported under node)

**Interfaces:**
- `newgame.js`: `renderNewGame(ui) -> string`: player count chips (1–4, `act:"ng_players"`, `arg:n`), a starting-threat counter per player (`act:"ng_threat"`, `arg:i`, default 25, min 0), a scenario list from `ui.picker.index.scenarios` filtered to `kind === "quest"`, grouped by `cycle` in `order` (`quest_catalog.js`'s `groupByCycle(scenarios, "official")` if it fits; else sort by `order` then `name`), each row a `chip({act:"pick_scenario", arg: slug, label: name})` with the pack as a `label`; a `resume` chip when `ui.picker.hasSave`.
- `app.js` (the only DOM file):
  1. `setWindowPolicy(WINDOW_POLICY_BANDS); setBoardTracking(true);`
  2. `const db = new DataClient({ prefix: "lotr-tablet-" });`
  3. Boot: `const saved = db.session.loadState(); if (saved) { game = GameState.fromDict(saved.state); game.clock = () => Math.floor(performance.now()); db.session.loadReplay(game); db.session.loadLog(game); const b = game.scenario?.slug ? await db.bundle(game.scenario.slug) : null; if (b) game.rehydrateStages(b.stages); ui.screen = game.game_over ? "gameover" : "play"; } else { ui.screen = "newgame"; ui.picker = { index: await db.index(), players: 2, threats: [25, 25], hasSave: false }; }`
  4. `render()`: `root.innerHTML = layout(game, ui)`.
  5. Click delegation on `#app`: read `data-act`/`data-arg`; the async acts (`new_game` → clear the session and show the picker; `ng_players`, `ng_threat-`/`ng_threat+`; `pick_scenario` → `const b = await db.bundle(slug); const entry = ui.picker.index.scenarios.find(...)`; build `scenarioMeta` exactly as `main.js`'s `begin_setup` does (`slug, name, pack, cycle, source, kind, nightmare:false, mode:"Standard", maxCardThreat, hasXThreat`); `game = new GameState(players); threats.forEach(...)`; `game.logEvent(\`New game: …\`)`; `game.preloadScenario(scenarioMeta, b.stages); game.view = "quest_setup"; ui.screen = "play"; db.session.saveState(game)`) are handled here; everything else goes to `dispatch`. After a `true` from `dispatch`: `if (!game.game_over && game.players.length && game.allEliminated()) game.setGameOver("defeat"); if (game.game_over) ui.screen = "gameover"; db.session.record(game);`. Then `render()`.
  6. Persistence: `setInterval(() => db.session.tick(game), 250)`; `window.addEventListener("pagehide", () => db.session.flush(game))`.
  7. `game.pending_elim`: milestone 3 (the elimination sheet); until then the rail's `is-eliminated` state is the only signal and the flag is left set.

- [ ] **Step 1: Failing test** — `test_new_game_screen_lists_scenarios_and_players`: render `renderNewGame({picker: {index: {scenarios: [{slug:"a", name:"A", pack:"P", cycle:"C", kind:"quest", order:1, source:"official"}, {slug:"n", name:"N", pack:"P", cycle:"C", kind:"nightmare", order:2, source:"official"}]}, players: 3, threats: [25, 25, 30], hasSave: true}})` and assert three threat counters, the `A` row present and `N` absent, `data-act="resume"` present.
- [ ] **Step 2–3: Implement `newgame.js`, wire `layout.js`, write `app.js`.** — [ ] **Step 4: Tests + suite green.**
- [ ] **Step 5: Browser check (the controller does this, not a subagent):** `preview_start` the `web-twin` server, open `http://localhost:8643/tablet/`, start a game with Passage Through Mirkwood, walk a round, reload to confirm resume, confirm no console errors and no `localStorage` key without the `lotr-tablet-` prefix.
- [ ] **Step 6: Commit** — `git commit -m "feat(tablet): boot, persistence, a new-game screen, and resume"`

---

## Done when

- `python3 -m pytest tests/ -q` is green with the six commits.
- `http://localhost:8643/tablet/` starts a catalog game, walks a round with the strip, rail and panes, survives a reload, and shares no storage key with the web twin.
- `tests/test_tablet.py::test_the_m2_walk_reaches_round_end_in_17_taps` gates the walk at 17; milestone 3 extends it to the spec's 20 with the players sheet.
- Nothing under `ui/`, `docs/js/` (except the generated `icons_svg.js` and its generator) changed; `tests/test_skin_identity.py` and `tests/test_tap_budget.py` untouched.
