# M5 · Beta Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the HUD from "works" to "beta": a new player can start cold and be guided through a full game, every piece of on-screen copy is rules-accurate, secondary text is actually readable at arm's length on a 4" panel, and a real multi-round game runs on the Presto without tracebacks or state loss.

**Architecture:** Four independent, separately-shippable tasks — first-run guidance + a conventions legend (new screens), a copy/tone pass (text-only edits driven by a change table), an accessibility pass (palette + touch-target changes measured against WCAG), and a test/soak protocol (a documented on-device procedure plus the automated gate). Nothing here changes game logic.

**Tech Stack:** ES modules (web, Canvas) + MicroPython (firmware); pytest + the scene layout linter; `mpremote` for the device.

**Context:** From `design/roadmap.md` → **M5 · Beta hardening**: *"first-run guidance + a legend for HUD conventions; copy/tone pass (incl. the Sailing 'discarded' fix); accessibility + touch; full tests + on-device soak."* The roadmap's **Definition of beta** is the acceptance bar this plan must satisfy: (1) a new player completes a full game guided by the HUD alone, (2) a veteran plays a round at/near the tap budget (that's **M3**, not this plan), (3) it looks like a crafted Middle-earth companion, (4) it is quest-aware for the captured quests (**M4**, shipped), (5) it runs a full multi-round game on the Presto with zero tracebacks and state surviving a power cycle.

## Measured findings (already verified — do not re-derive)

**Contrast (WCAG 2.1 AA: 4.5:1 body text, 3.0:1 large text ≥18.66px bold / 24px regular).** Computed from `ui/theme.py`'s actual RGB values with the standard relative-luminance formula:

| Foreground | Background | Ratio | Verdict |
|---|---|---|---|
| `dim` | `card_hi` | **2.04** | fails both thresholds |
| `dim` | `btn` | **2.06** | fails both |
| `dim` | `card` | **2.38** | fails both |
| `dim` | `well` | **2.69** | fails both |
| `dim` | `bg` | **2.85** | fails both |
| `red` | `card_hi` | 3.29 | fails body |
| `red` | `btn` | 3.31 | fails body |
| `muted` | `card_hi` | 3.79 | fails body |
| `muted` | `btn` | 3.81 | fails body |
| `red` | `card` | 3.82 | fails body |

`dim` is the worst offender **and** the most-used secondary colour (captions, hints, disabled states, log metadata) — it fails at every background in the palette.

**The Sailing copy bug** named in the roadmap is real and already diagnosed in this repo's own rules notes (`quests/sailing-tests.md`, "Copy fix for the HUD"): the tip says characters *"look at that many cards"*, but the cards are **discarded**.
- `ui/screen_play.py:357` — `"count), looks at that many cards."`
- `docs/js/screen_play.js:237` — same string.
Correct wording per that note: **"…looks at and discards that many cards."**

**Touch targets:** `tests/test_layout.py` enforces `MIN_TARGET = 24`. Apple's HIG and WCAG 2.5.5 (AAA) both point at ~44px for primary controls; WCAG 2.5.8 (AA, 2.2) sets a 24px floor — so the current bar is the AA minimum, not a comfortable one.

## Global Constraints

- **Two twins in lockstep** (Iron rule #1): web `docs/js/` first, then the firmware mirror — identical copy, palette, and layout.
- **`python3 -m pytest tests/` stays green** (Iron rule #3) including the layout linter; add scenes for new screens.
- **Rules claims verified** (Iron rule #4): every copy change that asserts a game rule must cite the rulebook (`pdftotext` on the PDF in the session scratchpad) or this repo's `quests/*.md` notes, in the change table.
- **ASCII only** in drawn strings — the device bitmap font's glyph table covers printable ASCII only (82 entries in `tests/fake_hardware.py`).
- **No game-logic changes.** If a copy fix reveals a behavior bug, log it as a separate finding rather than fixing it here.
- Touch targets ≥ 24px today; Task 3 may raise the constant but must then keep every scene passing.

## File structure

- `ui/screen_firstrun.py` + `docs/js/screens_other.js` — new first-run/legend screens.
- `ui/screen_play.py`, `ui/modals.py`, `ui/screen_quest.py` + web mirrors — copy edits.
- `ui/theme.py` + `docs/js/ui.js` — palette adjustments.
- `tests/test_layout.py` — the target constant (Task 3).
- `tests/scenes.py` — scenes for the new screens.
- `docs/superpowers/specs/2026-07-25-soak-protocol.md` — the on-device procedure (Task 4).

---

### Task 1: First-run guidance + conventions legend

**Files:**
- Create: `ui/screen_firstrun.py`; add the mirror class to `docs/js/screens_other.js`
- Modify: `main.py`, `docs/js/main.js` (route on first run; entry from Settings/About)
- Modify: `tests/scenes.py`
- Test: `tests/test_firstrun.py` (new)

**Interfaces:**
- Produces: `FirstRunScreen` — a short paged intro (3 pages, Back/Next/Done, a page indicator). Page 1: what the HUD is (a companion tracker, not a rules engine — it never touches your cards). Page 2: the round loop (pick a quest → each phase has a primary CTA at the bottom → tap a zone to edit). Page 3: **the conventions legend** (see below). Buttons: `["fr_next"]`, `["fr_back"]`, `["fr_done"]`.
- Produces: `LegendScreen` — page 3's content, reachable on its own from Settings so it is re-openable. Button `["close"]`.
- Produces: `prefs["seen_intro"]` (bool, default `False`) — persisted with the other prefs; set `True` on Done. **Store it in prefs, not game state**, so starting a new game does not re-show it.

**Legend content** (drawn as icon/swatch + label rows — derive the exact colours from `pal`, do not hardcode hex):
- threat helm (red) = player threat · threat helm (dark) = staging/enemy threat
- willpower sunburst (gold) = committed willpower
- ranger/trail (green) = quest progress
- gold value = every stat number (told apart by icon, never by number colour)
- red bar under a stat = danger (threat within 10 of elimination)
- purple dot = an action window is open at this step
- a ring around a token = progress toward that item's quest points

- [ ] **Step 1: Write the failing test** — `tests/test_firstrun.py`: constructing `FirstRunScreen`, drawing each of the 3 pages without raising, `fr_next`/`fr_back` clamping at the ends, `fr_done` returning a transition, and every button being ≥24px. Follow `tests/test_screen_play.py`'s construction idiom (`FakeHardware` + `Palette`).
- [ ] **Step 2: Run → FAIL** (module missing).
- [ ] **Step 3: Implement the web screens** in `docs/js/screens_other.js`, then **Step 4: mirror** in `ui/screen_firstrun.py`.
- [ ] **Step 5: Route it.** Both mains: if `not prefs.get("seen_intro")` at boot, show `FirstRunScreen` before the boot/setup screen; `fr_done` sets the pref, saves, and continues to the normal boot flow. Add a Settings row ("How to read this HUD") opening `LegendScreen`.
- [ ] **Step 6: Scenes + render** — `firstrun_1`, `firstrun_2`, `legend`; linter PASS; `python3 tools/preview.py legend /tmp/legend.png` and check every row reads clearly.
- [ ] **Step 7:** Full suite green; commit.

---

### Task 2: Copy / tone pass

**Files:** Modify the copy sites found below in both twins; Test: `tests/test_copy.py` (new, guards the specific fixes).

- [ ] **Step 1: Fix the known Sailing bug** (the one the roadmap names).
  - `ui/screen_play.py:357`: `"count), looks at that many cards."` → `"count), looks at and discards that many cards."`
  - `docs/js/screen_play.js:237`: the same replacement.
  - Check the surrounding wrapped lines still fit their panel width after the change (the string got longer — re-render the scene, don't assume).
  - Source: `quests/sailing-tests.md` "Copy fix for the HUD"; cross-check the sailing procedure in that note against the rulebook before committing.
- [ ] **Step 2: Build the change table.** Walk every user-visible string in `ui/screen_play.py`, `ui/modals.py`, `ui/screen_quest.py`, `ui/screen_setup.py`, `ui/screen_about.py` (and web mirrors) and record a row per change: `file:line | current | replacement | why`. Apply these rules:
  - **Rules accuracy first** — anything asserting a game rule must match the rulebook; cite it. Flag (don't silently fix) anything where the code's behavior, not just its wording, looks wrong.
  - **Voice:** terse, second person, active. "Commit characters to the quest." not "Characters may now be committed."
  - **Buttons say what happens** ("Flip to Side B", "Begin Round 1"), and the confirmation that follows uses the same verb.
  - **No jargon the box doesn't use**; match the game's own terms (staging area, quest points, engagement cost).
  - **ASCII only.**
- [ ] **Step 3: Write `tests/test_copy.py`** — assert the Sailing string is correct in both twins (read the source files and check the exact text), and add a guard that no drawn string in the firmware source contains a non-ASCII codepoint (a regex over the `text_left`/`text_center` literals is enough; it catches the class of bug that already bit the tips work).
- [ ] **Step 4:** Apply the table; re-render every affected scene; linter green; full suite green; commit with the change table in the commit body.

---

### Task 3: Accessibility + touch

**Files:** Modify `ui/theme.py`, `docs/js/ui.js`; possibly `tests/test_layout.py`; re-render all scenes.

- [ ] **Step 1: Write the failing test** — `tests/test_contrast.py`: implement the WCAG relative-luminance ratio, then assert every **foreground/background pair actually used by the app** clears its threshold (4.5 for body-size text, 3.0 for large). Seed it with the measured table above so it starts RED on `dim`.
- [ ] **Step 2: Run → FAIL** on the `dim` pairs (2.04–2.85).
- [ ] **Step 3: Lighten the secondary colours.** Raise `dim` until it clears **4.5:1 on `card_hi`** (the tightest background it is used on) while staying visibly subordinate to `muted` and `tan`; do the same for `muted` and `red` against their body-text uses. Keep the hue — this is a brightness change, not a re-theme, and the [[stat-system]] colour meanings (threat red, willpower gold, progress green, uniform gold values) must be preserved. Recompute the whole table and put the new numbers in the commit body.
- [ ] **Step 4: Re-render every scene** (`python3 tools/preview.py --list`, then render each) and eyeball them: the palette shift must not flatten the hierarchy or make disabled controls look enabled. Adjust and re-measure if it does.
- [ ] **Step 5: Touch targets.** Audit primary controls (CTAs, modal Done, pager buttons, radio rows) against a **44px** comfort bar. Raise `MIN_TARGET` in `tests/test_layout.py` only if every scene can pass; otherwise keep 24 as the enforced floor, add a separate assertion that *primary* controls (a named list) are ≥44, and record which controls could not be enlarged and why.
- [ ] **Step 6:** Full suite green; commit.

---

### Task 4: Full tests + on-device soak

**Files:** Create `docs/superpowers/specs/2026-07-25-soak-protocol.md`; update `CLAUDE.md`'s device section if the procedure changes.

- [ ] **Step 1: Automated gate.** Document and verify the pre-deploy gate: `python3 -m pytest tests/` green (including the layout linter over every scene), `python3 tools/gen_web_data.py` produces no diff (generated files in sync), and `python3 tools/build_card_data.py` + `build_icons.py` succeed.
- [ ] **Step 2: Write the soak protocol** — concrete and checkable, not "play for a while":
  - **Deploy:** `python3 tools/build_card_data.py && python3 tools/build_icons.py && mpremote cp -r docs/data/ :/data/`, then the firmware files; relaunch `main.py` in a background task and check its output for tracebacks before declaring success (per `CLAUDE.md`).
  - **Scripted walkthrough (≥3 rounds, 2 players):** first-run intro → new game → pick Passage Through Mirkwood → Scenario Options (confirm sets + icons) → Quest Setup → flip → play rounds 1-3 exercising: threat ±, commit, quest resolution (success **and** failure), travel to a location, add a side quest via the picker, open the quest-card modal and page all stages, open the log and use all four scroll buttons.
  - **Power-cycle test:** mid-round, pull power; on reboot the saved game resumes with identical values (compare a screenshot before/after).
  - **Duration:** ≥45 minutes of continuous running (a realistic session) with the display active.
  - **Pass criteria:** zero tracebacks in the device output; no memory error; state identical across the power cycle; every screen renders without visual corruption; touch stays responsive at the end (no degradation).
  - **What to record:** the device output file, a photo of each key screen, and free RAM at start vs end (`gc.mem_free()`), to catch a slow leak.
- [ ] **Step 3: Run the soak** (main session only, device attached) and file the results in the protocol doc. Any traceback or leak becomes its own fix task before beta.

---

## If the user prefers something else

- **First-run intro length.** Default is 3 pages shown once, re-openable from Settings. *If the user prefers less friction*, cut to a single legend page and drop the intro pages — Task 1's legend content is the part that carries the beta acceptance ("a new player completes a full game guided by the HUD alone").
- **Contrast strategy.** Default lightens `dim`/`muted`/`red` in place. *If the user prefers to keep the current palette exactly*, the alternative is to stop using `dim` for anything a player must read (promote those strings to `muted`+) and reserve `dim` purely for decorative/disabled states — which the contrast test would then exempt. Say which, because it changes many call sites rather than three constants.
- **Touch bar.** Default keeps the enforced floor at 24 and adds a 44px assertion for a named primary-control list. *If the user wants 44 everywhere*, expect real layout rework in the dense zones (the 32px-stride players columns especially) — that would become its own task.

## Self-Review

**Spec coverage:** first-run guidance + conventions legend → Task 1; copy/tone pass including the named Sailing "discarded" fix → Task 2 (with the exact file:line and replacement already identified); accessibility + touch → Task 3 (driven by measured WCAG failures, not guesses); full tests + on-device soak → Task 4 (with concrete pass criteria). Beta-acceptance items 2 and 4 are explicitly out of scope here (M3 and M4 own them) and are called out in Context so the gap is deliberate.

**Placeholder scan:** the contrast numbers, the Sailing bug's location and replacement text, and the soak pass criteria are all concrete. Task 2's change table is intentionally produced *during* the task (it requires reading every string) but its rules, format, and required citation are fixed here.

**Type consistency:** `prefs["seen_intro"]` is the single new persisted value; `FirstRunScreen`/`LegendScreen` button ids (`fr_next`/`fr_back`/`fr_done`/`close`) are used identically in Task 1's tests, implementation, and routing.
