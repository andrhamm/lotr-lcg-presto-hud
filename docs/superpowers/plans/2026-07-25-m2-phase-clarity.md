# M2 · Phase Clarity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every phase screen in the guided round (`docs/js/screen_play.js` / `ui/screen_play.py`) visually separates **framework** (red — mandatory, automatic, no interrupts) from **your window** (green — you may act now), per the rulebook's own turn-sequence colour code, and surfaces the one contextual stat that phase is about — live where the data supports it (willpower-vs-staging on Quest·Staging, projected threat on Refresh) and as verified rules copy where it doesn't (engagement risk on Encounter/Combat). *Done when* each phase screen answers: what happens, when can I act, what matters.

**Architecture:** Two new additive drawing primitives shared by both twins (`ui/widgets.py` / `docs/js/ui.js`): `phase_block`/`phaseBlock` (a framework/window panel — red or green left-accent bar per section, reusing the existing `note_panel` visual language rather than modifying it) and `willpower_staging_meter`/`willpowerStagingMeter` (a live proportional bar for Quest·Staging). Eight `ScreenPlay` view branches (7 distinct phase screens — Encounter's 2 sub-steps and Combat's 3 sub-steps share one lookup-table-driven branch already) are rewritten to call these primitives with per-view, rulebook-verified copy in place of today's single gold-accented `note_panel` call. No new interaction model, no new game-state fields — `willpower`/`staging`/`threat`/`threat_per_round`/`elimination` already live on `GameState`/`Player` and update immediately on every existing stepper/modal, so "live" falls out of drawing from those fields directly.

**Tech Stack:** unchanged — Canvas ES modules (web) + MicroPython/PicoGraphics (firmware); pytest + the scene layout linter; `tools/preview.py` for device-faithful rendering. No JS test runner exists in this repo (verified: no `package.json`, no `*.test.js`) — `python3 -m pytest tests/` is the enforced gate, so every TDD step below targets Python; the JS side is verified by close correspondence plus a manual browser walkthrough (final step of Task 7).

**Context:**

This is milestone 2 of 5 in `design/roadmap.md`: *"framework (red) / action-window (green) / stat model on every phase; threat-as-risk on Encounter & Combat; live willpower-vs-staging."* The framework/window split is `design/design-review.md`'s "organizing insight" — the manual's turn-sequence chart colour-codes every step (RED = mandatory/automatic/no interrupts, GREEN = any player may respond), and the design review's per-phase content-spec table is the source of the copy below. `design/stat-system.md` fixes the colour vocabulary this plan must not violate: player threat = red, staging/enemy threat = dark (`pal.outline`, **not** red), willpower = gold always, progress = green+brown, all stat *values* = uniform gold, danger = red bottom-bar only (never icon/value recolouring).

**Current-state gap** (verified by reading `docs/js/screen_play.js` / `ui/screen_play.py` in full): every phase view calls the same single-tone `note_panel`/`notePanel` — dark panel, gold left accent, muted text — for both mandatory and optional content alike. There is no framework/window distinction anywhere on these screens (the red/green concept exists today only on the separate Phases flowchart screen, `ui/screen_phases.py`/`ScreenPhases` in `docs/js/screens_other.js`, which marks action-window steps with a **purple** square, not green, and is a distinct legend screen this plan does not touch). Quest·Staging's "live" willpower-vs-staging comparison already exists as a single sentence recomputed every draw (`diff = game.willpower - game.staging`) buried inside the tip box — correct but not visually prominent. Encounter and Combat show generic one-line reminders with no threat-as-risk framing. Refresh shows static instructional text with no preview of the threat increase it's about to apply.

**Per-view table** (drives every task below; "—" means the phase has no `phase_block` framework section per `design/design-review.md`'s own "—" cells):

| View | Rulebook phase/step | What happens (framework, red) | When can I act (window, green) | What matters (stat) |
|---|---|---|---|---|
| `resource_planning` | Resource 1.R + Planning 2.P (merged screen) | Collect resources. Draw cards. | Play allies/attachments — your only window for permanents this round. | (copy-only; no resource count is modeled) |
| `quest_commit` | Quest 3.2 | — | Commit characters to the quest. | Running willpower total — **already live** via the players matrix + totals row; no new widget, tip recolours to green only |
| `quest_staging` | Quest 3.3 | Reveal 1 encounter card per player. | Responses to the reveal. | **Willpower vs staging, live** — new proportional meter (Task 4) |
| `travel` | Travel 4.2 | Travel to 1 location if none is active (some add a travel cost). / No travel while a location is active. | Responses. | Travel cost + "explore active first" folded into the framework copy (no location-effect-cost field exists to show live) |
| `enc_optional` | Encounter 5.2 | — | You may engage 1 enemy from the staging area, voluntarily. | Your threat decides which enemies can engage you next (no ordering claim — step 1 has none) |
| `enc_checks` | Encounter 5.3 | Enemies engage you if their cost is ≤ your threat — highest cost first. | Responses. | First player checks first, then clockwise, repeating until stable |
| `combat_shadow` | Combat 6.2 | Deal 1 shadow card to each engaged enemy — first player's enemies first, highest cost first. | Responses. | (ordering is the framework text itself; no separate caption) |
| `combat_enemy` | Combat 6.E | Choose an enemy → declare defender → shadow effect → damage, one at a time. (+ship note when sailing) | Responses at each step. | First player resolves first, then clockwise. Undefended damage hits 1 hero |
| `combat_player` | Combat 6.P | Declare target and attackers → total ATK → damage, one enemy at a time. (+ship note when sailing) | Responses at each step. | First player attacks first, then clockwise. 1 attack per engaged enemy |
| `refresh` | Refresh 7.R | Ready all cards. Each player's threat +1. Pass the first-player token. | Responses. | **Threat after +1, elimination proximity** — new live per-player preview (Task 7) |

**Explicitly out of scope** (state the reason, not a TBD):
- `quest_setup` (R0 scroll tip) and `setup_game` (`SETUP_TIP`) — one-time pre-round screens with their own bespoke double-frame chrome, not part of the repeating phase cycle the milestone targets.
- `quest_resolution` — a progress-placement spreadsheet; no framework/action-window concept applies (nothing is "revealed" or "responded to," it's pure bookkeeping of where already-resolved progress goes).
- Vertical centering / "dead space" polish of tip panels — that is the subject of a **separate, ungroomed** `docs/superpowers/plans/2026-07-24-phase-tip-redesign.md` (sourced from a TODO.md **Ideas**-column note, not yet claimed or scheduled). It touches the same `note_panel`/`notePanel` call sites but pursues a different goal (badge+kicker chrome, vertical centering) via a different mechanism (extending `note_panel`'s own signature). Per `CLAUDE.md`'s card protocol, Ideas-column items are never worked directly without the user grooming them into Ready — this plan does not fold that work in. This plan's new `phase_block`/`phaseBlock` is **additive** (a new function, not a `note_panel` signature change), so the two plans do not conflict at the primitive level; they *would* conflict at the `ScreenPlay` call-site level if both land (both rewrite the same branches). **This plan is written against the code as it stands today** (no `_tip` helper, no `kicker`/`badge`/`min_h` params exist yet). If the user grooms and executes phase-tip-redesign.md first, re-diff this plan's per-view tasks against whatever shape lands rather than applying them blind.
- M3-scope interaction speedups (one-tap all-players, further tap-and-hold removal) — a later milestone; the existing inline staging ±/willpower ± steppers are untouched.

**Geometry is verified, not guessed:** every wrap-line count and pixel height below was computed by running the actual `ui.widgets.wrap_text` against the real bitmap8 metric table (`tests/fake_hardware.py`'s `measure_bitmap8`, captured from the device), not estimated. The tightest view, `quest_staging`, was checked precisely: `phase_block` (84px) + `willpower_staging_meter` (64px) + the existing `_totals_row` (84px) fit in the `CONTENT_Y=150` → `CTA_Y=410` band (260px) with exactly 12px to spare before the CTA. Every other view has comfortably more headroom (confirmed including the worst case: `combat_enemy` with Sailing on, the flavor icon, and its caption line — 206px used of 260px available).

## Global Constraints

- **Two twins in lockstep** (Iron rule #1): implement each task's JS first (`docs/js/`), then mirror line-for-line into Python (`ui/`) — same constants, branching, and pixel math.
- **`python3 -m pytest tests/` stays green** (Iron rule #3), including the layout linter (`tests/test_layout.py`: L1 nothing drawn outside 480×480, L2 no two text runs overlap, L3/L4 touch targets ≥24px and on-screen).
- **No JS test runner in this repo** (verified). The Python/pytest side is the only automated correctness gate; the web twin is verified by exact correspondence to the Python plus one consolidated browser walkthrough (Task 7's final step). Local web-twin server: `python3 -m http.server 8642 --directory docs` (per `.claude/launch.json`, `web-twin` config) — or drive it via the Browser tool's `preview_start` with `name: "web-twin"`.
- **Colour semantics are fixed by `design/stat-system.md`** and must not be violated by new code: player threat = red (`pal.red`), staging/enemy threat = dark (`pal.outline`, never red), willpower = gold always (`pal.gold`), progress = green+brown, all stat *values* = uniform gold (`pal.value`), danger = red bottom-bar only. This plan's new colours — `pal.red` for framework, `pal.green` for window — are additive to that system (framework/window are panel-level semantics, not stat-value semantics) and match the rulebook's own chart coding exactly (`design/design-review.md`).
- **Preserve existing tap targets.** Only `quest_commit`'s tip carries a tap target today (`commit_tip`, opens `CommitModal`) — Task 3 must keep it working at the new geometry. No other touched tip panel has an attached button today; none gains one.
- **Rules claims are pre-verified against the rulebook** (Iron rule #4) — every framework/window/caption string in the per-view table above was checked against `/private/tmp/claude-501/-Users-andrewhammond-dev-lotr-lcg-presto-hud/6b01a428-ccff-4eea-a175-399cf1d555b1/scratchpad/lotr_rules.txt` (a `pdftotext` dump of the rulebook) before being written into this plan: engagement-check ordering and highest-cost-first resolution (p.16), shadow-card dealing order (p.18), the 4-step enemy-attack loop and the undefended-damage-to-1-hero rule (p.18-19), the 3-step player-attack loop and 1-attack-per-engaged-enemy rule (p.19-20), the Refresh phase's ready/+1-threat/pass-token sequence and that an eliminated player's threat does **not** keep increasing (p.21-22), and the travel-cost/no-travel-while-active rule (p.15). No new rules claims are introduced beyond what's in the per-view table.
- **480×480 canvas.** No draw call may land outside it (linter-enforced).
- **Every visual task gets a scene** (new or an existing one re-exercised) **and a `python3 tools/preview.py <scene>` render check** before being called done.

## File structure

- `ui/widgets.py` / `docs/js/ui.js` — add `phase_block`/`phaseBlock` and `willpower_staging_meter`/`willpowerStagingMeter`. `note_panel`/`notePanel` is untouched (see the phase-tip-redesign note above).
- `ui/screen_play.py` / `docs/js/screen_play.js` — every phase-view branch in `draw()` (`resource_planning`, `quest_commit`, `quest_staging`, `_draw_travel`/`_drawTravel`, the Encounter/Combat catch-all `else` branch, `refresh`) switches from `note_panel`/`notePanel` to the new primitives; a new `_refresh_threat_preview`/`_refreshThreatPreview` method is added.
- `tests/test_widgets_primitives.py` — new host unit tests for the two primitives (Task 1).
- `tests/test_screen_play.py` — new behavior tests per touched view (Tasks 2-7).
- `tests/scenes.py` — 5 new scene entries (`play_quest_staging_behind`, `play_quest_staging_tied`, `play_combat_enemy_sailing`, `play_combat_player_sailing`, `play_refresh_danger`) plus their mutate helpers; every other touched view reuses an existing scene.

---

### Task 1: Shared phase-guidance primitives

**Files:**
- Modify: `ui/widgets.py`, `docs/js/ui.js`
- Test: `tests/test_widgets_primitives.py`

**Interfaces:**
- Produces: `phase_block(d, pal, x, y, w, sections, reserve_right=0) -> int` (Python) / `phaseBlock(ctx, x, y, w, sections, reserveRight = 0) -> number` (JS), where `sections` is an ordered list of `(kind, text)` tuples / `{kind, text}` objects, `kind` is `"framework"` or `"window"`, `text` is a string or list of paragraph strings. Returns the drawn height. A phase with no mandatory content (design table's "—") simply omits the `"framework"` entry — nothing is drawn for it.
- Produces: `willpower_staging_meter(d, pal, x, y, w, willpower, staging) -> int` (Python) / `willpowerStagingMeter(ctx, x, y, w, willpower, staging) -> number` (JS). Fixed height 64. Draws a gold(willpower)-vs-dark(staging) proportional bar plus the existing outcome sentence (reused verbatim from today's staging tip: "You will gain N [trail icon]"/"Each player will gain N [threat icon]"/"Tied - no change").
- Consumes: `pal.red`, `pal.green`, `pal.gold`, `pal.outline`, `pal.well`, `pal.dim`, `pal.muted`, `pal.value` (existing); `wrap_text`/`wrapText`, `text_left`/`textLeft`; `icons.WILLPOWER`, `icons.THREAT`, `icons.TRAIL`, `icons.THREAT_SM` (existing, unchanged).

- [ ] **Step 1: Write the failing tests.** Add to `tests/test_widgets_primitives.py`:

```python
def test_phase_block_framework_and_window_use_correct_accents():
    d, pal = _d()
    h = W.phase_block(d, pal, 8, 100, 300,
                       [("framework", "Reveal 1 card per player."),
                        ("window", "Responses.")])
    accents = [c[5] for c in d.calls if c[0] == "rect" and c[1] == 8 and c[3] == 4]
    assert accents == [pal.red, pal.green]
    assert h > 0


def test_phase_block_omits_framework_section_when_absent():
    d, pal = _d()
    W.phase_block(d, pal, 8, 100, 300, [("window", "Commit characters.")])
    accents = [c[5] for c in d.calls if c[0] == "rect" and c[1] == 8 and c[3] == 4]
    assert accents == [pal.green]
    texts = [c[1] for c in d.calls if c[0] == "text"]
    assert "FRAMEWORK" not in texts and "YOUR WINDOW" in texts


def test_phase_block_reserve_right_produces_more_wrapped_lines():
    d, pal = _d()
    h_wide = W.phase_block(d, pal, 8, 100, 300, [("window", "x" * 80)])
    d2, pal2 = _d()
    h_narrow = W.phase_block(d2, pal2, 8, 100, 300, [("window", "x" * 80)], 34)
    assert h_narrow > h_wide   # less usable width, same unbroken text -> more lines


def test_phase_block_multi_paragraph_section_wraps_each_paragraph():
    d, pal = _d()
    W.phase_block(d, pal, 8, 100, 300,
                   [("framework", ["First sentence.", "Second sentence."])])
    texts = [str(c[1]) for c in d.calls if c[0] == "text"]
    assert any("First" in t for t in texts) and any("Second" in t for t in texts)


def test_willpower_staging_meter_fills_proportionally_and_has_fixed_height():
    d, pal = _d()
    h = W.willpower_staging_meter(d, pal, 8, 100, 300, 11, 7)
    assert h == 64
    fills = [c for c in d.calls if c[0] == "rect" and c[4] == 10
             and c[5] in (pal.gold, pal.outline)]
    assert len(fills) == 2
    gold_w = next(c[3] for c in fills if c[5] == pal.gold)
    outline_w = next(c[3] for c in fills if c[5] == pal.outline)
    assert gold_w > outline_w        # willpower (11) ahead of staging (7)


def test_willpower_staging_meter_tied_shows_dim_message():
    d, pal = _d()
    W.willpower_staging_meter(d, pal, 8, 100, 300, 5, 5)
    texts = [str(c[1]) for c in d.calls if c[0] == "text"]
    assert any("Tied" in t for t in texts)


def test_willpower_staging_meter_losing_shows_threat_gain_sentence():
    d, pal = _d()
    W.willpower_staging_meter(d, pal, 8, 100, 300, 4, 9)
    texts = [str(c[1]) for c in d.calls if c[0] == "text"]
    assert any("Each player will gain 5" in t for t in texts)
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_widgets_primitives.py -q` → `AttributeError: module 'ui.widgets' has no attribute 'phase_block'`.

- [ ] **Step 3: Implement in `ui/widgets.py`.** Add below the existing `note_panel` (do not modify `note_panel` itself):

```python
_PHASE_CAPTIONS = {"framework": "FRAMEWORK", "window": "YOUR WINDOW"}


def phase_block(d, pal, x, y, w, sections, reserve_right=0):
    """Framework(red)/window(green) phase-guidance panel - the semantic
    sibling of note_panel(). `sections` is an ordered list of
    (kind, text) tuples (kind is "framework" or "window"; text is a
    string or list of paragraphs). A phase with no mandatory framework
    step just omits that entry - nothing is drawn for it. Distinguishes
    "this happens automatically, no interrupts" from "you may act now"
    per the rulebook's own turn-sequence colour code
    (design/design-review.md). Returns the panel height."""
    usable = w - 16 - 12 - reserve_right
    laid = []
    for kind, text in sections:
        body = " ".join(text) if isinstance(text, (list, tuple)) else text
        lines = wrap_text(body, 2, usable, d.measure_text)
        laid.append((kind, lines, 14 + len(lines) * 24))
    h = 8 + sum(sec_h for _, _, sec_h in laid)
    d.set_pen(pal.card_hi)
    d.rectangle(x, y, w, h)
    ty = y + 4
    for kind, lines, sec_h in laid:
        accent = pal.red if kind == "framework" else pal.green
        d.set_pen(accent)
        d.rectangle(x, ty, 4, sec_h)
        text_left(d, pal, _PHASE_CAPTIONS[kind], x + 12, ty + 2, 1, accent)
        ly = ty + 16
        for s in lines:
            text_left(d, pal, s, x + 12, ly, 2, pal.muted)
            ly += 24
        ty += sec_h
    return h


def willpower_staging_meter(d, pal, x, y, w, willpower, staging):
    """Live head-to-head bar: willpower (gold, left) vs staging threat
    (dark pal.outline, right - staging threat is never red, per
    design/stat-system.md's staging/enemy-threat rule) - the "willpower
    vs staging, live" stat from design/design-review.md's Quest-Staging
    row. Draws straight from the passed-in numbers, so it reflects every
    -/+ stepper tap immediately, no separate commit step. Reuses the
    existing outcome-sentence wording verbatim. Fixed height: 64."""
    from ui import icons as _icons
    icons_draw = _icons.draw
    icons_draw(d, _icons.WILLPOWER, x, y, pal.gold)
    icons_draw(d, _icons.THREAT, x + w - len(_icons.THREAT), y, pal.outline)
    bx, bw, bar_y, bar_h = x + 26, w - 52, y + 5, 10
    d.set_pen(pal.well)
    d.rectangle(bx, bar_y, bw, bar_h)
    total = willpower + staging
    left_w = round(bw * willpower / total) if total > 0 else round(bw / 2)
    if left_w > 0:
        d.set_pen(pal.gold)
        d.rectangle(bx, bar_y, left_w, bar_h)
    if bw - left_w > 0:
        d.set_pen(pal.outline)
        d.rectangle(bx + left_w, bar_y, bw - left_w, bar_h)
    d.set_pen(pal.dim)
    d.rectangle(x + round(w / 2) - 1, bar_y - 3, 2, bar_h + 6)   # tie marker
    ly = bar_y + bar_h + 14
    diff = willpower - staging
    if diff != 0:
        pre = "%s will gain %d " % ("You" if diff > 0 else "Each player", abs(diff))
        pre_w = d.measure_text(pre, 2)
        ic = _icons.TRAIL if diff > 0 else _icons.THREAT_SM
        tail = "at resolution."
        total_w = pre_w + len(ic) + 6 + d.measure_text(tail, 2)
        lx = x + round((w - total_w) / 2)
        text_left(d, pal, pre, lx, ly, 2, pal.muted)
        icons_draw(d, ic, lx + pre_w, ly - 1, pal.gold if diff > 0 else pal.red)
        text_left(d, pal, tail, lx + pre_w + len(ic) + 6, ly, 2, pal.muted)
    else:
        text_center(d, pal, "Tied - no change at resolution.", x + w / 2, ly, 2, pal.dim)
    return 64
```

- [ ] **Step 4: Run → PASS.** `python3 -m pytest tests/test_widgets_primitives.py -q`.

- [ ] **Step 5: Mirror in `docs/js/ui.js`.** Add below the existing `notePanel` export:

```js
const PHASE_CAPTIONS = { framework: "FRAMEWORK", window: "YOUR WINDOW" };

// Framework(red)/window(green) phase-guidance panel - the semantic
// sibling of notePanel(). `sections` is an ordered list of
// {kind, text} ("framework"|"window"; text is a string or paragraph
// array). A phase with no mandatory framework step just omits that
// entry - nothing is drawn for it. Returns the panel height.
export function phaseBlock(ctx, x, y, w, sections, reserveRight = 0) {
  const usable = w - 16 - 12 - reserveRight;
  const laid = sections.map(({ kind, text }) => {
    const body = Array.isArray(text) ? text.join(" ") : text;
    const lines = wrapText(body, 2, usable);
    return { kind, lines, h: 14 + lines.length * 24 };
  });
  const h = 8 + laid.reduce((s, sec) => s + sec.h, 0);
  rect(ctx, x, y, w, h, pal.card_hi);
  let ty = y + 4;
  for (const sec of laid) {
    const accent = sec.kind === "framework" ? pal.red : pal.green;
    rect(ctx, x, ty, 4, sec.h, accent);
    textLeft(ctx, PHASE_CAPTIONS[sec.kind], x + 12, ty + 2, 1, accent);
    let ly = ty + 16;
    for (const s of sec.lines) { textLeft(ctx, s, x + 12, ly, 2, pal.muted); ly += 24; }
    ty += sec.h;
  }
  return h;
}

// Live head-to-head bar: willpower (gold, left) vs staging threat (dark
// pal.outline, right - never red, per design/stat-system.md). The
// "willpower vs staging, live" stat from design/design-review.md's
// Quest-Staging row. Reuses the existing outcome-sentence wording
// verbatim. Fixed height: 64.
export function willpowerStagingMeter(ctx, x, y, w, willpower, staging) {
  icons.drawIcon(ctx, icons.WILLPOWER, x, y, pal.gold);
  icons.drawIcon(ctx, icons.THREAT, x + w - icons.THREAT[0], y, pal.outline);
  const bx = x + 26, bw = w - 52, barY = y + 5, barH = 10;
  rect(ctx, bx, barY, bw, barH, pal.well);
  const total = willpower + staging;
  const leftW = total > 0 ? Math.round(bw * willpower / total) : Math.round(bw / 2);
  if (leftW > 0) rect(ctx, bx, barY, leftW, barH, pal.gold);
  if (bw - leftW > 0) rect(ctx, bx + leftW, barY, bw - leftW, barH, pal.outline);
  rect(ctx, x + Math.round(w / 2) - 1, barY - 3, 2, barH + 6, pal.dim);
  const ly = barY + barH + 14;
  const diff = willpower - staging;
  if (diff !== 0) {
    const pre = `${diff > 0 ? "You" : "Each player"} will gain ${Math.abs(diff)} `;
    const preW = measureText(pre, 2);
    const ic = diff > 0 ? icons.TRAIL : icons.THREAT_SM;
    const tail = "at resolution.";
    const totalW = preW + ic[0] + 6 + measureText(tail, 2);
    const lx = x + Math.round((w - totalW) / 2);
    textLeft(ctx, pre, lx, ly, 2, pal.muted);
    icons.drawIcon(ctx, ic, lx + preW, ly - 1, diff > 0 ? pal.gold : pal.red);
    textLeft(ctx, tail, lx + preW + ic[0] + 6, ly, 2, pal.muted);
  } else {
    textCenter(ctx, "Tied - no change at resolution.", x + w / 2, ly, 2, pal.dim);
  }
  return 64;
}
```

  `icons.THREAT[0]` is the icon's pixel size in the generated JS format (`[size, rows]`) — the Python mirror uses `len(icons.THREAT)` instead, since `ui/icons.py`'s format is a flat row list (verified against both `ui/icons.py` and the generated `docs/js/icons.js`; do not swap these idioms between the two languages).

- [ ] **Step 6: Full suite → green.** `python3 -m pytest tests/ -q`.

- [ ] **Step 7: Commit.**

```bash
git add ui/widgets.py docs/js/ui.js tests/test_widgets_primitives.py
git commit -m "feat(phase-clarity): add phase_block + willpower_staging_meter primitives"
```

---

### Task 2: Resource & Planning (`resource_planning`)

**Files:**
- Modify: `docs/js/screen_play.js`, `ui/screen_play.py`
- Modify: `tests/test_screen_play.py`

**Interfaces:**
- Consumes: `phase_block`/`phaseBlock` from Task 1.

Current code (both twins, to be replaced): a single `note_panel`/`notePanel` call with three plain lines ("Collect resources.", "Draw cards.", "Play allies and attachments."), no colour distinction.

- [ ] **Step 1: Write the failing test.** Add to `tests/test_screen_play.py`:

```python
def test_resource_planning_shows_framework_and_window_blocks():
    hw, pal, game, screen = _setup("resource_planning")
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "FRAMEWORK" in texts
    assert "YOUR WINDOW" in texts
    accents = [c[5] for c in hw.display.calls if c[0] == "rect" and c[1] == 8 and c[3] == 4]
    assert pal.red in accents and pal.green in accents
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_screen_play.py -k resource_planning_shows -q` → FAIL (no "FRAMEWORK"/"YOUR WINDOW" text drawn today).

- [ ] **Step 3: Implement in `docs/js/screen_play.js` first.** Add `phaseBlock` to the existing `ui.js` import line:

```js
import { pal, Button, rect, panel, bevel, textLeft, textCenter, wrapText,
         truncateText, ribbon, notePanel, phaseBlock, drawHeart, drawFlag,
         disc, arcRuns, wxSmall, token } from "./ui.js";
```

  Replace the `resource_planning` branch in `draw()`:

```js
} else if (view === "resource_planning") {
  this._playersZone(ctx, game);
  this._progressZone(ctx, game);
  phaseBlock(ctx, MARGIN, CONTENT_Y, 480 - 2 * MARGIN, [
    { kind: "framework", text: "Collect resources. Draw cards." },
    { kind: "window", text: "Play allies and attachments - your only window for permanents this round." },
  ]);
  this._cta(ctx, `Next Phase: ${VIEW_LABELS[game.sailing ? "quest_sailing" : "quest_commit"]}`, ["advance"]);
}
```

- [ ] **Step 4: Mirror in `ui/screen_play.py`.** Add `phase_block` to the `ui.widgets` import:

```python
from ui.widgets import (Button, panel, bevel, text_center, text_left, ribbon,
                        note_panel, phase_block, wrap_text, truncate_text, draw_heart,
                        draw_flag, disc, arc_runs, token, wx_small)
```

  Replace the `resource_planning` branch in `draw()`:

```python
elif view == "resource_planning":
    self._players_zone(d, pal, game)
    self._progress_zone(d, pal, game)
    phase_block(d, pal, MARGIN, CONTENT_Y, 480 - 2 * MARGIN, [
        ("framework", "Collect resources. Draw cards."),
        ("window", "Play allies and attachments - your only window for permanents this round."),
    ])
    nxt = "quest_sailing" if game.sailing else "quest_commit"
    self._cta(d, pal, "Next Phase: %s" % VIEW_LABELS[nxt], ("advance",))
```

- [ ] **Step 5: Run → PASS.** `python3 -m pytest tests/test_screen_play.py tests/test_layout.py -q`.

- [ ] **Step 6: Render and inspect** — `python3 tools/preview.py play_resource_planning /tmp/m2_resource.png`. Confirm the red framework strip and green window strip both read clearly, text doesn't crowd the zones above or the CTA below.

- [ ] **Step 7: Commit.**

```bash
git add docs/js/screen_play.js ui/screen_play.py tests/test_screen_play.py
git commit -m "feat(phase-clarity): red/green split on Resource & Planning"
```

---

### Task 3: Quest · Commit (`quest_commit`)

**Files:**
- Modify: `docs/js/screen_play.js`, `ui/screen_play.py`
- Modify: `tests/test_screen_play.py`

**Interfaces:**
- Consumes: `phase_block`/`phaseBlock` from Task 1.
- Per the per-view table, Quest·Commit has **no framework section** ("—") — this is a window-only phase. Its contextual stat (running willpower total) is already live via the players matrix + `_totalsRow`/`_totals_row`; this task only recolours the tip and preserves its existing `commit_tip` tap target at the new geometry.

Current code (to be replaced): `th = notePanel(...)` at `ty = CONTENT_Y` with a `commit_tip` button covering it, then `_totalsRow(ctx, game, ty + 48, ...)` (Python: `ty + 48`).

- [ ] **Step 1: Write the failing tests.** Add to `tests/test_screen_play.py`:

```python
def test_commit_view_window_only_no_framework_block():
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "YOUR WINDOW" in texts
    assert "FRAMEWORK" not in texts


def test_commit_tip_button_still_opens_commit_modal_at_new_geometry():
    from ui.modals import CommitModal
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    tip = _find(screen, ("commit_tip",))
    assert tip.w >= 24 and tip.h >= 24
    result = screen.on_button(tip, game)
    assert isinstance(result[1], CommitModal)


def test_commit_totals_row_moves_with_tip_height():
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    tip = _find(screen, ("commit_tip",))
    ids = _ids(screen)
    assert "wp" in ids and "stg" in ids
    wp_button = _find(screen, ("wp",))
    assert wp_button.y >= tip.y + tip.h   # totals row starts at/after the tip's bottom
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_screen_play.py -k commit_view_window_only -q` → FAIL.

- [ ] **Step 3: Implement in `docs/js/screen_play.js`.** Replace the `quest_commit` branch:

```js
} else if (view === "quest_commit") {
  this._playersZone(ctx, game);
  this._progressZone(ctx, game);
  const bh = phaseBlock(ctx, MARGIN, CONTENT_Y, 480 - 2 * MARGIN,
    [{ kind: "window", text: "Commit characters to the quest - exhaust them to add their willpower." }]);
  this.buttons.push(new Button(["commit_tip"], MARGIN, CONTENT_Y, 480 - 2 * MARGIN, bh));
  this._totalsRow(ctx, game, CONTENT_Y + bh + 8, false, ["wp", "stg"]);
  this._cta(ctx, `Next Phase: ${VIEW_LABELS.quest_staging}`, ["advance"]);
}
```

- [ ] **Step 4: Mirror in `ui/screen_play.py`.** Replace the `quest_commit` branch:

```python
elif view == "quest_commit":
    self._players_zone(d, pal, game)
    self._progress_zone(d, pal, game)
    bh = phase_block(d, pal, MARGIN, CONTENT_Y, 480 - 2 * MARGIN,
                     [("window", "Commit characters to the quest - exhaust them to add their willpower.")])
    self.buttons.append(Button(("commit_tip",), MARGIN, CONTENT_Y, 480 - 2 * MARGIN, bh))
    self._totals_row(d, pal, game, CONTENT_Y + bh + 8, tappable=("wp", "stg"))
    self._cta(d, pal, "Next Phase: %s" % VIEW_LABELS["quest_staging"], ("advance",))
```

- [ ] **Step 5: Run → PASS.** `python3 -m pytest tests/test_screen_play.py tests/test_layout.py -q`.

- [ ] **Step 6: Render and inspect** — `python3 tools/preview.py play_quest_commit /tmp/m2_commit.png` and `python3 tools/preview.py play_quest_commit_manyside /tmp/m2_commit_many.png` (the many-side-quests variant exercises the progress zone at its widest, a good collision check). Confirm the green-only tip, the totals row sitting cleanly below it, and the willpower tokens in the players matrix still update on commit.

- [ ] **Step 7: Commit.**

```bash
git add docs/js/screen_play.js ui/screen_play.py tests/test_screen_play.py
git commit -m "feat(phase-clarity): green window-only tip on Quest.Commit"
```

---

### Task 4: Quest · Staging (`quest_staging`) — the live willpower-vs-staging meter

**Files:**
- Modify: `docs/js/screen_play.js`, `ui/screen_play.py`
- Modify: `tests/scenes.py` (2 new scenes)
- Modify: `tests/test_screen_play.py`

**Interfaces:**
- Consumes: `phase_block`/`phaseBlock`, `willpower_staging_meter`/`willpowerStagingMeter` from Task 1.
- **Verified geometry** (Global Constraints): `phase_block` (1-line framework + 1-line window) = 84px at `y=150`; meter = 64px at `y=242`; `_totals_row`/`_totalsRow` (unchanged, `with_steppers=True`) = 84px at `y=314`, bottom `398` — 12px clear of `CTA_Y=410`. The framework copy is deliberately short ("Reveal 1 encounter card per player.") — a longer phrasing that also mentions "adding its threat to staging" was measured to wrap to 2 lines and overflow the CTA by 6px; the meter itself now shows that consequence, so the shorter copy loses nothing.

Current code (to be replaced entirely — both the hand-rolled double-bordered pipe box and the inline diff-sentence that follows it):

```js
} else if (view === "quest_staging") {
  this._playersZone(ctx, game);
  this._progressZone(ctx, game);
  // tip: reveal reminder, then a live preview of the resolution outcome
  const tw = 480 - 2 * MARGIN, gutt = 28 + 14, lh = 26;
  const tx = MARGIN + 12 + gutt, usable = tw - 12 - gutt;
  const lines = wrapText(
    "Reveal 1 encounter card per player and adjust staging area threat accordingly.",
    2, usable);
  const ty0 = CONTENT_Y + 2, th = (lines.length + 1) * lh + 16;
  rect(ctx, MARGIN, ty0, tw, th, pal.card_hi);
  rect(ctx, MARGIN, ty0, 4, th, pal.border_gold);
  icons.drawIcon(ctx, icons.PIPE, MARGIN + 10, ty0 + 8, pal.gold);
  let ly = ty0 + 8;
  for (const ln of lines) { textLeft(ctx, ln, tx, ly, 2, pal.muted); ly += lh; }
  const diff = game.willpower - game.staging;
  if (diff !== 0) { /* pre/icon/tail */ } else { /* tie text */ }
  this._totalsRow(ctx, game, ty0 + th + 8, true);
  this._cta(ctx, `Next Phase: ${VIEW_LABELS.quest_resolution}`, ["stage_advance"]);
}
```

- [ ] **Step 1: Write the failing tests.** Add to `tests/test_screen_play.py`:

```python
def test_staging_shows_framework_window_and_meter():
    hw, pal, game, screen = _setup("quest_staging")
    game.willpower, game.staging = 11, 7
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "FRAMEWORK" in texts and "YOUR WINDOW" in texts
    fills = [c for c in hw.display.calls if c[0] == "rect" and c[4] == 10
             and c[5] in (pal.gold, pal.outline)]
    assert len(fills) == 2


def test_staging_meter_and_totals_row_both_clear_of_cta():
    from ui.screen_play import CTA_Y
    hw, pal, game, screen = _setup("quest_staging")
    screen.draw(hw, game, pal)
    ids = _ids(screen)
    assert "stg-" in ids and "wp-" in ids     # totals_row steppers still present
    stepper = _find(screen, ("stg-",))
    assert stepper.y + stepper.h <= CTA_Y


def test_staging_tied_shows_dim_tie_message():
    hw, pal, game, screen = _setup("quest_staging")
    game.willpower = game.staging = 7
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert any("Tied" in t for t in texts)
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_screen_play.py -k staging_shows_framework -q` → FAIL.

- [ ] **Step 3: Implement in `docs/js/screen_play.js`.** Add `willpowerStagingMeter` to the `ui.js` import (alongside `phaseBlock` from Task 2). Replace the entire `quest_staging` branch body:

```js
} else if (view === "quest_staging") {
  this._playersZone(ctx, game);
  this._progressZone(ctx, game);
  const bh = phaseBlock(ctx, MARGIN, CONTENT_Y, 480 - 2 * MARGIN, [
    { kind: "framework", text: "Reveal 1 encounter card per player." },
    { kind: "window", text: "Responses to the reveal." },
  ]);
  const my = CONTENT_Y + bh + 8;
  const mh = willpowerStagingMeter(ctx, MARGIN, my, 480 - 2 * MARGIN, game.willpower, game.staging);
  this._totalsRow(ctx, game, my + mh + 8, true);
  this._cta(ctx, `Next Phase: ${VIEW_LABELS.quest_resolution}`, ["stage_advance"]);
}
```

- [ ] **Step 4: Mirror in `ui/screen_play.py`.** Replace the body of `_draw_staging`:

```python
def _draw_staging(self, d, pal, game):
    self._players_zone(d, pal, game)
    self._progress_zone(d, pal, game)
    bh = phase_block(d, pal, MARGIN, CONTENT_Y, 480 - 2 * MARGIN, [
        ("framework", "Reveal 1 encounter card per player."),
        ("window", "Responses to the reveal."),
    ])
    my = CONTENT_Y + bh + 8
    mh = willpower_staging_meter(d, pal, MARGIN, my, 480 - 2 * MARGIN, game.willpower, game.staging)
    self._totals_row(d, pal, game, my + mh + 8, with_steppers=True)
    self._cta(d, pal, "Next Phase: %s" % VIEW_LABELS["quest_resolution"], ("stage_advance",))
```

  Add `willpower_staging_meter` to the `ui.widgets` import line.

- [ ] **Step 5: Add scenes** to `tests/scenes.py` — two new mutate helpers near `_sailing_on`:

```python
def _staging_behind(g):
    g.willpower, g.staging = 5, 9


def _staging_tied(g):
    g.willpower, g.staging = 7, 7
```

  Register in `SCENES`:

```python
"play_quest_staging_behind": _play("quest_staging", mutate=_staging_behind),
"play_quest_staging_tied": _play("quest_staging", mutate=_staging_tied),
```

- [ ] **Step 6: Run → PASS.** `python3 -m pytest tests/test_screen_play.py tests/test_layout.py -q`.

- [ ] **Step 7: Render and inspect all 3 outcome branches:**

```
python3 tools/preview.py play_quest_staging /tmp/m2_staging_ahead.png
python3 tools/preview.py play_quest_staging_behind /tmp/m2_staging_behind.png
python3 tools/preview.py play_quest_staging_tied /tmp/m2_staging_tied.png
```

  Confirm: the bar fills gold-heavy in the "ahead" case and outline-heavy in "behind", the tie marker sits at the bar's midpoint, the outcome sentence matches the bar, and the totals row + steppers are fully visible above the CTA in all three (no overlap — verified geometrically above, but eyeball it).

- [ ] **Step 8: Commit.**

```bash
git add docs/js/screen_play.js ui/screen_play.py tests/scenes.py tests/test_screen_play.py
git commit -m "feat(phase-clarity): live willpower-vs-staging meter on Quest.Staging"
```

---

### Task 5: Travel (`travel`)

**Files:**
- Modify: `docs/js/screen_play.js`, `ui/screen_play.py`
- Modify: `tests/test_screen_play.py`

**Interfaces:**
- Consumes: `phase_block`/`phaseBlock` from Task 1.
- Both sub-states (`active_location` present or not) get a framework line reflecting that specific state; the travel-cost and "explore active first" facts (design table's contextual stat — no live numeric field exists for either) are folded directly into the framework copy rather than a separate stat widget.

Current code (`_drawTravel`/`_draw_travel`, to be replaced):

```js
_drawTravel(ctx, game) {
  const loc = game.active_location;
  let y = CONTENT_Y + 4;
  if (!loc) {
    y += notePanel(ctx, MARGIN, y, 480 - 2 * MARGIN,
      "Players may travel to 1 location. It becomes the active location.") + 10;
    const tb = new Button(["travel_new"], MARGIN, y, 480 - 2 * MARGIN, 56);
    /* ... */
  } else {
    y += notePanel(ctx, MARGIN, y, 480 - 2 * MARGIN,
      "Travel is only possible while there is no active location (rulebook).") + 10;
    const cb = new Button(["travel_change"], MARGIN, y, 480 - 2 * MARGIN, 48);
    /* ... */
  }
  this._cta(ctx, `Next Phase: ${VIEW_LABELS.enc_optional}`, ["advance"]);
}
```

- [ ] **Step 1: Write the failing tests.** Add to `tests/test_screen_play.py`:

```python
def test_travel_no_location_shows_framework_and_travel_button():
    hw, pal, game, screen = _setup("travel")
    game.active_location = None
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "FRAMEWORK" in texts
    assert "travel_new" in _ids(screen)


def test_travel_with_location_shows_explore_first_framework():
    hw, pal, game, screen = _setup("travel")
    game.active_location = {"points": 3, "progress": 1}
    screen.draw(hw, game, pal)
    assert "travel_change" in _ids(screen)
    texts = " ".join(str(c[1]) for c in hw.display.calls if c[0] == "text")
    assert "explore" in texts.lower()
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_screen_play.py -k travel_no_location_shows -q` → FAIL.

- [ ] **Step 3: Implement in `docs/js/screen_play.js`.** Replace `_drawTravel`:

```js
_drawTravel(ctx, game) {
  const loc = game.active_location;
  const fw = loc
    ? "No travel while a location is active - explore it first."
    : "Travel to 1 location if none is active (some add a travel cost).";
  const bh = phaseBlock(ctx, MARGIN, CONTENT_Y, 480 - 2 * MARGIN,
    [{ kind: "framework", text: fw }, { kind: "window", text: "Responses." }]);
  const y = CONTENT_Y + bh + 10;
  if (!loc) {
    const tb = new Button(["travel_new"], MARGIN, y, 480 - 2 * MARGIN, 56);
    bevel(ctx, tb.x, tb.y, tb.w, tb.h, pal.btn);
    textCenter(ctx, "Travel to location", 240, y + 18, 2, pal.tan);
    this.buttons.push(tb);
  } else {
    const cb = new Button(["travel_change"], MARGIN, y, 480 - 2 * MARGIN, 48);
    panel(ctx, cb.x, cb.y, cb.w, cb.h);
    textCenter(ctx, "Replace location (card effect)", 240, y + 14, 2, pal.muted);
    this.buttons.push(cb);
  }
  this._cta(ctx, `Next Phase: ${VIEW_LABELS.enc_optional}`, ["advance"]);
}
```

- [ ] **Step 4: Mirror in `ui/screen_play.py`.** Replace `_draw_travel`:

```python
def _draw_travel(self, d, pal, game):
    loc = game.active_location
    fw = ("No travel while a location is active - explore it first." if loc else
          "Travel to 1 location if none is active (some add a travel cost).")
    bh = phase_block(d, pal, MARGIN, CONTENT_Y, 480 - 2 * MARGIN,
                     [("framework", fw), ("window", "Responses.")])
    y = CONTENT_Y + bh + 10
    if loc is None:
        tb = Button(("travel_new",), MARGIN, y, 480 - 2 * MARGIN, 56)
        bevel(d, pal, tb.x, tb.y, tb.w, tb.h, pal.btn)
        text_center(d, pal, "Travel to location", 240, y + 18, 2, pal.tan)
        self.buttons.append(tb)
    else:
        cb = Button(("travel_change",), MARGIN, y, 480 - 2 * MARGIN, 48)
        panel(d, pal, cb.x, cb.y, cb.w, cb.h, fill=pal.card)
        text_center(d, pal, "Replace location (card effect)", 240, y + 14, 2, pal.muted)
        self.buttons.append(cb)
    self._cta(d, pal, "Next Phase: %s" % VIEW_LABELS["enc_optional"], ("advance",))
```

- [ ] **Step 5: Run → PASS.** `python3 -m pytest tests/test_screen_play.py tests/test_layout.py -q`.

- [ ] **Step 6: Render and inspect** — `python3 tools/preview.py play_travel /tmp/m2_travel.png` and `python3 tools/preview.py play_travel_none /tmp/m2_travel_none.png`. Confirm both sub-states read clearly and the travel button/panel sits comfortably below the block.

- [ ] **Step 7: Commit.**

```bash
git add docs/js/screen_play.js ui/screen_play.py tests/test_screen_play.py
git commit -m "feat(phase-clarity): red/green split on Travel"
```

---

### Task 6: Encounter & Combat — threat-as-risk (`enc_optional`, `enc_checks`, `combat_shadow`, `combat_enemy`, `combat_player`)

**Files:**
- Modify: `docs/js/screen_play.js`, `ui/screen_play.py`
- Modify: `tests/scenes.py` (2 new scenes)
- Modify: `tests/test_screen_play.py`

**Interfaces:**
- Consumes: `phase_block`/`phaseBlock` from Task 1.
- These 5 views share one lookup-table-driven `else` branch in `draw()` today (keyed by `view`) — this task replaces the `notes`/`shipNotes`/`flavor` dict-driven body with 3 new lookup tables (`framework`, `window`, `caption` text per view) plus the existing `shipNotes`/`flavor` logic, re-hung off `phaseBlock`. This is "threat-as-risk on Encounter & Combat" from the roadmap: since this app tracks each player's live threat number but not individual enemy cards or their engagement costs, the risk framing is rules-accurate **explanatory copy** tied to the numbers already on screen (the players-zone threat tokens), not a fabricated cost comparison against data the app doesn't have.
- **Verified geometry:** worst case is `combat_enemy`/`combat_player` with Sailing on (ship note appended as a 2nd framework paragraph) + the flavor icon's 34px `reserveRight` + a caption line — 206px/182px of the 260px budget. Every other combination in this task uses less.

Current code (both twins, the `else` branch, to be replaced):

```js
} else {
  this._playersZone(ctx, game);
  const notes = {
    enc_optional: "Each player may engage one enemy in the staging area (optional).",
    enc_checks: "Engagement checks: enemies engage players whose threat >= their cost.",
    combat_shadow: "Deal 1 shadow card to each engaged enemy.",
    combat_enemy: "Enemies attack. Declare defenders, resolve shadow effects, apply damage.",
    combat_player: "Players attack engaged enemies.",
  };
  const flavor = { combat_enemy: [icons.DEFENSE, pal.green],
                   combat_player: [icons.ATTACK, pal.tan] }[view];
  this._progressZone(ctx, game);
  const shipNotes = {
    combat_enemy: "Ships: only a ship can defend a ship-enemy. Undefended ship attacks must damage a ship you control.",
    combat_player: "Ships: your ships attack only ship-enemies - but any character may attack a ship-enemy.",
  };
  let noteText = notes[view] ?? "";
  if (game.sailing && shipNotes[view]) noteText = [noteText, shipNotes[view]];
  const reserve = flavor ? 34 : 0;
  const h = notePanel(ctx, MARGIN, CONTENT_Y + 6, 480 - 2 * MARGIN, noteText, 2, reserve);
  if (flavor) { icons.drawIcon(ctx, flavor[0], 480 - MARGIN - 34, CONTENT_Y + 6 + Math.floor((h - 20) / 2), flavor[1]); }
  const i = VIEW_ORDER.indexOf(view);
  const nxt = VIEW_ORDER[(i + 1) % VIEW_ORDER.length];
  this._cta(ctx, `Next Phase: ${VIEW_LABELS[nxt] ?? nxt}`, ["advance"]);
}
```

- [ ] **Step 1: Write the failing tests.** Add to `tests/test_screen_play.py`:

```python
def test_enc_optional_has_no_framework_block_but_has_risk_caption():
    hw, pal, game, screen = _setup("enc_optional")
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "FRAMEWORK" not in texts
    assert "YOUR WINDOW" in texts
    joined = " ".join(texts)
    assert "engage you" in joined


def test_enc_checks_shows_framework_and_first_player_caption():
    hw, pal, game, screen = _setup("enc_checks")
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "FRAMEWORK" in texts
    assert any("clockwise" in t for t in texts)


def test_combat_shadow_shows_framework_only_ordering_text():
    hw, pal, game, screen = _setup("combat_shadow")
    screen.draw(hw, game, pal)
    texts = " ".join(str(c[1]) for c in hw.display.calls if c[0] == "text")
    assert "FRAMEWORK" in texts
    assert "highest cost first" in texts


def test_combat_enemy_sailing_appends_ship_note_to_framework():
    hw, pal, game, screen = _setup("combat_enemy")
    game.sailing = True
    screen.draw(hw, game, pal)
    texts = " ".join(str(c[1]) for c in hw.display.calls if c[0] == "text")
    assert "ship-enemy" in texts.lower()


def test_combat_enemy_flavor_icon_still_drawn():
    hw, pal, game, screen = _setup("combat_enemy")
    screen.draw(hw, game, pal)
    icon_rows = [c for c in hw.display.calls if c[0] == "rect" and c[4] == 1
                 and c[1] >= 480 - 8 - 34]
    assert icon_rows


def test_combat_player_caption_mentions_one_attack_per_enemy():
    hw, pal, game, screen = _setup("combat_player")
    screen.draw(hw, game, pal)
    texts = " ".join(str(c[1]) for c in hw.display.calls if c[0] == "text")
    assert "1 attack per engaged enemy" in texts
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_screen_play.py -k "enc_optional_has_no_framework or enc_checks_shows or combat_shadow_shows or combat_player_caption" -q` → FAIL.

- [ ] **Step 3: Implement in `docs/js/screen_play.js`.** Add these lookup tables near the top of the module (after the existing constants):

```js
const PHASE_FRAMEWORK = {
  enc_checks: "Enemies engage you if their cost is <= your threat - highest cost first.",
  combat_shadow: "Deal 1 shadow card to each engaged enemy - first player's enemies first, highest cost first.",
  combat_enemy: "Choose an enemy -> declare defender -> shadow effect -> damage, one at a time.",
  combat_player: "Declare target and attackers -> total ATK -> damage, one enemy at a time.",
};
const PHASE_WINDOW = {
  enc_optional: "You may engage 1 enemy from the staging area, voluntarily.",
  enc_checks: "Responses.",
  combat_shadow: "Responses.",
  combat_enemy: "Responses at each step.",
  combat_player: "Responses at each step.",
};
const PHASE_CAPTION = {
  enc_optional: "Your threat decides which enemies can engage you next.",
  enc_checks: "First player checks first, then clockwise, repeating until stable.",
  combat_enemy: "First player resolves first, then clockwise. Undefended damage hits 1 hero.",
  combat_player: "First player attacks first, then clockwise. 1 attack per engaged enemy.",
};
```

  Replace the `else` branch body:

```js
} else {
  this._playersZone(ctx, game);
  const flavor = { combat_enemy: [icons.DEFENSE, pal.green],
                   combat_player: [icons.ATTACK, pal.tan] }[view];
  this._progressZone(ctx, game);
  const shipNotes = {
    combat_enemy: "Ships: only a ship can defend a ship-enemy. Undefended ship attacks must damage a ship you control.",
    combat_player: "Ships: your ships attack only ship-enemies - but any character may attack a ship-enemy.",
  };
  const sections = [];
  if (PHASE_FRAMEWORK[view]) {
    const fw = game.sailing && shipNotes[view]
      ? [PHASE_FRAMEWORK[view], shipNotes[view]] : PHASE_FRAMEWORK[view];
    sections.push({ kind: "framework", text: fw });
  }
  if (PHASE_WINDOW[view]) sections.push({ kind: "window", text: PHASE_WINDOW[view] });
  const reserve = flavor ? 34 : 0;
  const bh = phaseBlock(ctx, MARGIN, CONTENT_Y, 480 - 2 * MARGIN, sections, reserve);
  if (flavor) {
    icons.drawIcon(ctx, flavor[0], 480 - MARGIN - 34,
                   CONTENT_Y + Math.floor((bh - 20) / 2), flavor[1]);
  }
  if (PHASE_CAPTION[view]) {
    textLeft(ctx, PHASE_CAPTION[view], MARGIN + 4, CONTENT_Y + bh + 10, 1, pal.dim);
  }
  const i = VIEW_ORDER.indexOf(view);
  const nxt = VIEW_ORDER[(i + 1) % VIEW_ORDER.length];
  this._cta(ctx, `Next Phase: ${VIEW_LABELS[nxt] ?? nxt}`, ["advance"]);
}
```

- [ ] **Step 4: Mirror in `ui/screen_play.py`.** Add the same 3 dicts at module level (near `MARGIN`/`CONTENT_Y`):

```python
_PHASE_FRAMEWORK = {
    "enc_checks": "Enemies engage you if their cost is <= your threat - highest cost first.",
    "combat_shadow": "Deal 1 shadow card to each engaged enemy - first player's enemies first, highest cost first.",
    "combat_enemy": "Choose an enemy -> declare defender -> shadow effect -> damage, one at a time.",
    "combat_player": "Declare target and attackers -> total ATK -> damage, one enemy at a time.",
}
_PHASE_WINDOW = {
    "enc_optional": "You may engage 1 enemy from the staging area, voluntarily.",
    "enc_checks": "Responses.",
    "combat_shadow": "Responses.",
    "combat_enemy": "Responses at each step.",
    "combat_player": "Responses at each step.",
}
_PHASE_CAPTION = {
    "enc_optional": "Your threat decides which enemies can engage you next.",
    "enc_checks": "First player checks first, then clockwise, repeating until stable.",
    "combat_enemy": "First player resolves first, then clockwise. Undefended damage hits 1 hero.",
    "combat_player": "First player attacks first, then clockwise. 1 attack per engaged enemy.",
}
_SHIP_NOTES = {
    "combat_enemy": "Ships: only a ship can defend a ship-enemy. Undefended ship attacks must damage a ship you control.",
    "combat_player": "Ships: your ships attack only ship-enemies - but any character may attack a ship-enemy.",
}
```

  Replace the `else` branch body in `draw()`:

```python
else:
    self._players_zone(d, pal, game)
    flavor = {"combat_enemy": (icons.DEFENSE, pal.green),
              "combat_player": (icons.ATTACK, pal.tan)}.get(view)
    self._progress_zone(d, pal, game)
    sections = []
    if view in _PHASE_FRAMEWORK:
        fw = _PHASE_FRAMEWORK[view]
        if game.sailing and view in _SHIP_NOTES:
            fw = [fw, _SHIP_NOTES[view]]
        sections.append(("framework", fw))
    if view in _PHASE_WINDOW:
        sections.append(("window", _PHASE_WINDOW[view]))
    reserve = 34 if flavor else 0
    bh = phase_block(d, pal, MARGIN, CONTENT_Y, 480 - 2 * MARGIN, sections, reserve)
    if flavor:
        icons.draw(d, flavor[0], 480 - MARGIN - 34,
                   CONTENT_Y + (bh - 20) // 2, flavor[1])
    if view in _PHASE_CAPTION:
        text_left(d, pal, _PHASE_CAPTION[view], MARGIN + 4, CONTENT_Y + bh + 10, 1, pal.dim)
    i = VIEW_ORDER.index(view)
    nxt = VIEW_ORDER[(i + 1) % len(VIEW_ORDER)]
    self._cta(d, pal, "Next Phase: %s" % VIEW_LABELS.get(nxt, nxt), ("advance",))
```

  The old `notes`/`ship_notes`/`flavor` local variables inside this branch are fully replaced by the module-level dicts — remove them.

- [ ] **Step 5: Add scenes** to `tests/scenes.py` (reuses the existing `_sailing_on` mutate helper):

```python
"play_combat_enemy_sailing": _play("combat_enemy", mutate=_sailing_on),
"play_combat_player_sailing": _play("combat_player", mutate=_sailing_on),
```

- [ ] **Step 6: Run → PASS.** `python3 -m pytest tests/test_screen_play.py tests/test_layout.py -q`.

- [ ] **Step 7: Render and inspect all 7 combinations:**

```
python3 tools/preview.py play_enc_optional /tmp/m2_enc_opt.png
python3 tools/preview.py play_enc_checks /tmp/m2_enc_checks.png
python3 tools/preview.py play_combat_shadow /tmp/m2_combat_shadow.png
python3 tools/preview.py play_combat_enemy /tmp/m2_combat_enemy.png
python3 tools/preview.py play_combat_enemy_sailing /tmp/m2_combat_enemy_sail.png
python3 tools/preview.py play_combat_player /tmp/m2_combat_player.png
python3 tools/preview.py play_combat_player_sailing /tmp/m2_combat_player_sail.png
```

  Confirm: `enc_optional` shows no red strip (window-only, as the table specifies), the DEFENSE/ATTACK flavor icons on `combat_enemy`/`combat_player` still sit clear of the (now taller, 2-section) text, the ship-note paragraph doesn't collide with the caption line beneath it in the sailing variants, and every caption line is legible and doesn't crowd the CTA.

- [ ] **Step 8: Commit.**

```bash
git add docs/js/screen_play.js ui/screen_play.py tests/scenes.py tests/test_screen_play.py
git commit -m "feat(phase-clarity): threat-as-risk framing on Encounter & Combat"
```

---

### Task 7: Refresh (`refresh`) — live elimination-proximity preview

**Files:**
- Modify: `docs/js/screen_play.js`, `ui/screen_play.py`
- Modify: `tests/scenes.py` (1 new scene)
- Modify: `tests/test_screen_play.py`

**Interfaces:**
- Consumes: `phase_block`/`phaseBlock` from Task 1; `Player.threat`, `Player.threat_per_round`, `Player.elimination`, `Player.eliminated` (existing fields, unchanged).
- Produces: `_refreshThreatPreview(ctx, game, y) -> number` (JS) / `_refresh_threat_preview(self, d, pal, game, y) -> int` (Python) — a new `ScreenPlay` method. For each **living** player, shows `P{n} {threat}->{threat+threat_per_round}`, flagged red (`pal.red`) with a trailing `!` when the *projected* value crosses the existing danger threshold (`proj >= elimination - 10`, the same rule `_playersZone`/`_players_zone` already uses for the bottom-bar danger colour) — otherwise `pal.value` (uniform gold, per `design/stat-system.md`). Eliminated players are skipped: verified against the rulebook, an eliminated player's threat is fixed at their elimination level and does not increase further, so projecting `+1` for them would be incorrect. Fixed height 40.

Current code (to be replaced):

```js
} else if (view === "refresh") {
  this._playersZone(ctx, game);
  this._progressZone(ctx, game);
  notePanel(ctx, MARGIN, CONTENT_Y + 6, 480 - 2 * MARGIN,
            ["Ready all exhausted cards.", "Threat increases (automatic).",
             "Pass the first player token."]);
  this._cta(ctx, "End round (raise threat, pass token)", ["endround"]);
}
```

- [ ] **Step 1: Write the failing tests.** Add to `tests/test_screen_play.py`:

```python
def test_refresh_shows_framework_window_and_threat_preview():
    hw, pal, game, screen = _setup("refresh")
    for i, p in enumerate(game.players):
        p.threat = 20 + i
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "FRAMEWORK" in texts and "YOUR WINDOW" in texts
    assert any(t.startswith("P1 20->21") for t in texts)


def test_refresh_flags_projected_danger_even_if_not_yet_flagged():
    hw, pal, game, screen = _setup("refresh")
    game.players[1].threat = 39   # not yet danger (39 < 50-10=40); +1 crosses it
    screen.draw(hw, game, pal)
    danger_texts = [c for c in hw.display.calls
                    if c[0] == "text" and str(c[1]).startswith("P2") and c[5] == pal.red]
    assert danger_texts
    assert danger_texts[0][1].endswith("!")


def test_refresh_skips_eliminated_players_in_preview():
    hw, pal, game, screen = _setup("refresh")
    game.players[2].eliminated = True
    game.players[2].threat = 50
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert not any(t.startswith("P3 ") for t in texts)
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_screen_play.py -k refresh_shows_framework -q` → FAIL.

- [ ] **Step 3: Implement in `docs/js/screen_play.js`.** Add the new method (near `_totalsRow`):

```js
// Live "current -> projected" threat per living player, flagged red when the
// projected value crosses the same danger threshold _playersZone uses
// (proj >= elimination - 10). Eliminated players are skipped: their threat
// is capped at their elimination level and does not keep rising (verified
// rulebook rule). Fixed height: 40.
_refreshThreatPreview(ctx, game, y) {
  textLeft(ctx, "After +1 threat:", MARGIN + 4, y, 1, pal.dim);
  let x = MARGIN + 4;
  const ly = y + 14;
  game.players.forEach((p, i) => {
    if (p.eliminated) return;
    const proj = p.threat + p.threat_per_round;
    const danger = proj >= p.elimination - 10;
    const seg = `P${i + 1} ${p.threat}->${proj}${danger ? "!" : ""}`;
    textLeft(ctx, seg, x, ly, 2, danger ? pal.red : pal.value);
    x += measureText(seg, 2) + 16;
  });
  return 40;
}
```

  Replace the `refresh` branch in `draw()`:

```js
} else if (view === "refresh") {
  this._playersZone(ctx, game);
  this._progressZone(ctx, game);
  const bh = phaseBlock(ctx, MARGIN, CONTENT_Y, 480 - 2 * MARGIN, [
    { kind: "framework", text: "Ready all cards. Each player's threat +1. Pass the first-player token." },
    { kind: "window", text: "Responses." },
  ]);
  this._refreshThreatPreview(ctx, game, CONTENT_Y + bh + 8);
  this._cta(ctx, "End round (raise threat, pass token)", ["endround"]);
}
```

- [ ] **Step 4: Mirror in `ui/screen_play.py`.** Add the method:

```python
def _refresh_threat_preview(self, d, pal, game, y):
    """Live "current -> projected" threat per living player, flagged red
    when the projected value crosses the same danger threshold
    _players_zone uses (proj >= elimination - 10). Eliminated players are
    skipped - their threat is capped at their elimination level and does
    not keep rising (verified rulebook rule). Fixed height: 40."""
    text_left(d, pal, "After +1 threat:", MARGIN + 4, y, 1, pal.dim)
    x = MARGIN + 4
    ly = y + 14
    for i, p in enumerate(game.players):
        if p.eliminated:
            continue
        proj = p.threat + p.threat_per_round
        danger = proj >= p.elimination - 10
        seg = "P%d %d->%d%s" % (i + 1, p.threat, proj, "!" if danger else "")
        text_left(d, pal, seg, x, ly, 2, pal.red if danger else pal.value)
        x += d.measure_text(seg, 2) + 16
    return 40
```

  Replace the `refresh` branch in `draw()`:

```python
elif view == "refresh":
    self._players_zone(d, pal, game)
    self._progress_zone(d, pal, game)
    bh = phase_block(d, pal, MARGIN, CONTENT_Y, 480 - 2 * MARGIN, [
        ("framework", "Ready all cards. Each player's threat +1. Pass the first-player token."),
        ("window", "Responses."),
    ])
    self._refresh_threat_preview(d, pal, game, CONTENT_Y + bh + 8)
    self._cta(d, pal, "End round (raise threat, pass token)", ("endround",))
```

- [ ] **Step 5: Add scene** to `tests/scenes.py`:

```python
def _refresh_danger(g):
    # current threat (39) is NOT yet flagged danger by _players_zone's own
    # rule (39 < 50-10); the refresh preview's projection (+1 = 40) crosses
    # it - proving the preview surfaces upcoming risk before anything else does.
    g.players[1].threat = 39
```

  Register: `"play_refresh_danger": _play("refresh", mutate=_refresh_danger),`

- [ ] **Step 6: Run → PASS.** `python3 -m pytest tests/test_screen_play.py tests/test_layout.py -q`.

- [ ] **Step 7: Render and inspect** — `python3 tools/preview.py play_refresh /tmp/m2_refresh.png` and `python3 tools/preview.py play_refresh_danger /tmp/m2_refresh_danger.png`. Confirm all 4 players' projections fit on one line without crowding, and the danger-flagged player reads clearly red with its `!`.

- [ ] **Step 8: Full suite → green.** `python3 -m pytest tests/ -q`.

- [ ] **Step 9: Consolidated browser walkthrough.** Serve the web twin (`python3 -m http.server 8642 --directory docs`, or the Browser tool's `preview_start` with `name: "web-twin"`) and click through a full round: Resource&Planning → Commit → Staging (adjust the ± staging steppers and confirm the meter's bar and outcome sentence move live) → Resolution → Travel → Encounter (Optional, then Checks) → Combat (Shadow, Enemy, Player — toggle Sailing on first to see the ship-note variant) → Refresh (confirm the "After +1 threat" line matches what End Round then actually applies). Check the browser console for errors. Report any spot where red/green reads ambiguously or text feels cramped on real (non-monospace-approximated) rendering — the PNG previews use a host font substitute (`tools/preview.py`'s `_font`), so the live canvas render is the final word on legibility.

- [ ] **Step 10: Commit.**

```bash
git add docs/js/screen_play.js ui/screen_play.py tests/scenes.py tests/test_screen_play.py
git commit -m "feat(phase-clarity): live elimination-proximity preview on Refresh"
```

---

## Self-Review

**Spec coverage:** the per-view table in Context maps every row of `design/design-review.md`'s per-phase content spec to a task — framework(red)/window(green) visual treatment: Task 1 (primitive) + Tasks 2-7 (every consuming view). "Threat-as-risk on Encounter & Combat": Task 6, implemented honestly as rules-verified explanatory copy tied to the live threat numbers already on screen (the app has no per-enemy engagement-cost data to compare against, so no such comparison is fabricated). "Live willpower-vs-staging": Task 4's meter, driven directly by `game.willpower`/`game.staging` so every existing stepper tap updates it with no new state. Quest·Commit's already-live willpower total is explicitly called out as needing no new widget, not silently skipped. `quest_setup`, `setup_game`, and `quest_resolution` are explicitly excluded with reasons, not left as gaps. The overlapping-but-distinct `phase-tip-redesign.md` Idea is flagged, not silently absorbed or silently ignored. Every task that changes pixels carries a scene + `tools/preview.py` render-check step.

**Placeholder scan:** every task carries complete, real code for both twins (no "mirror similarly" hand-waving — each Python block is written out in full alongside its JS counterpart), complete test code, and exact copy strings. The one place this plan explicitly defers a decision (how phase-tip-redesign.md's eventual `_tip`/badge-kicker chrome should reconcile with this plan's call-site changes, if the user later grooms that Idea) is called out as a real, named risk with a concrete instruction ("re-diff against whatever shape lands"), not a TBD.

**Type consistency:** `phase_block(d, pal, x, y, w, sections, reserve_right=0)` / `phaseBlock(ctx, x, y, w, sections, reserveRight=0)` — the `sections: [(kind, text)]` / `[{kind, text}]` shape and `reserve_right`/`reserveRight` parameter are used identically across Tasks 2-6. `willpower_staging_meter(d, pal, x, y, w, willpower, staging)` / `willpowerStagingMeter(ctx, x, y, w, willpower, staging)` — same positional order in Task 4's only call site. `_refresh_threat_preview`/`_refreshThreatPreview`'s `(d/ctx, [pal,] game, y)` signature matches its Task 7 call site. All new module-level lookup tables (`_PHASE_FRAMEWORK`/`PHASE_FRAMEWORK`, etc.) use the same view-name keys as `VIEW_ORDER`/`VIEW_STEP` already do elsewhere in both files.

**Geometry is the one place this plan goes further than "trust the render-check step":** every line-wrap count and block height quoted in the per-task descriptions was computed by actually running `ui.widgets.wrap_text` against the real bitmap8 metrics (not estimated) — see the Context section's methodology note. The single case that would have overflowed the CTA (`quest_staging`'s framework text, initially drafted longer) was caught this way and shortened before being written into Task 4, rather than being discovered later at the render-check step.

**If the user prefers a different default:**
- *Caption wording:* `"FRAMEWORK"`/`"YOUR WINDOW"` are plain text captions in the accent colour, matching the manual's own colour-only coding rather than adding new iconography. If the user would rather have a small lock/hand glyph instead of (or beside) the text caption, that requires a new icon mask in `ui/icons.py` (regenerated to `docs/js/icons.js` via `tools/gen_web_data.py`, per Iron rule #2) — a bigger, separate change deliberately not bundled here.
- *`willpower_staging_meter`'s bar-only design:* the meter shows the comparison and the outcome sentence but not the raw willpower/staging numbers (those are already big and visible in `_totalsRow` directly above it, in Quest·Staging's actual on-screen order the meter sits between the tip and the totals row — avoiding a third redundant readout was a deliberate space-saving choice, verified necessary by the geometry check). If the user wants the numbers on the meter itself too (e.g., for players glancing only at this one widget), they can be added at each bar end without changing the primitive's height, since the icon slots already reserve 20px of vertical room the numbers could sit inside.
- *Refresh preview granularity:* the live preview is a compact one-line-per-player text row rather than reusing the big circular token widgets `_playersZone` already draws — a full token-based redesign was measured to cost far more vertical space than this view's budget allows without pushing into the CTA. The compact form was chosen as the default; a token-based variant is a strictly bigger follow-up if the compact form reads as too subtle once seen on-device.
