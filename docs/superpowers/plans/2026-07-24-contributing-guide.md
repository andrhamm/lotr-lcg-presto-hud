# CONTRIBUTING.md + README Section — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `CONTRIBUTING.md` that lets an external contributor go from "I
found this repo" to "I opened a working PR" without needing to ask the
maintainer anything — covering the one thing that's genuinely unusual about
this codebase (two synchronized implementations that must move together),
the concrete dev-setup and test commands, and how proposals/PRs are expected
to flow given there's no CI gate yet (see the sibling Playwright-CI plan) and
a solo maintainer. A short README pointer sends readers there.

## Architecture

One new top-level file (`CONTRIBUTING.md`, the GitHub-recognized location —
GitHub surfaces it automatically as a link on the Issues/PR creation forms
when it lives at the repo root) plus a short README section. No code.

## Tech Stack

Markdown only. No code, no build step, no tests to add.

## Context

TODO.md "Ideas": *"Contributing.md and section on the README."* `ROADMAP.md`
wishlist echoes it: *"...and a Contributing guide."* Neither exists today
(confirmed: no `CONTRIBUTING.md`/`CONTRIBUTING` at repo root).

What already exists and this doc must correctly point at rather than
duplicate:
- `.github/ISSUE_TEMPLATE/{bug,suggestion,appreciation}.yml` +
  `config.yml` — issue templates are already live. `ROADMAP.md` already
  tells readers to "Open a Suggestion" issue for ideas/votes.
- `CLAUDE.md`'s "Iron rules" — this is the project's actual working
  constitution (web-first-then-firmware, `gen_web_data.py` regeneration,
  `pytest` green, rules claims verified against source). `CONTRIBUTING.md`
  should restate these for a human audience (CLAUDE.md is written for an AI
  agent and references things — the TODO.md Kanban card protocol, background
  workers, device access — that don't apply to a human drive-by contributor),
  not fork a second, divergent copy of the rules.
- `CLAUDE.md`'s TODO.md/Kanban-board section is explicitly an **internal**
  workflow for the maintainer and their AI workers (`CLAUDE.md`: *"Ideas
  (user inbox — never work these directly)"*). `CONTRIBUTING.md` must not
  invite external contributors to edit `TODO.md` — that's a good way to get
  merge conflicts with an Obsidian board the maintainer treats as a personal
  inbox. External contributors' entry point is GitHub Issues, which already
  exists and already has templates.
- No lint/format config exists anywhere in the repo (checked for
  `.eslintrc*`, `.prettierrc*`, `pyproject.toml`, `.flake8`, `setup.cfg`,
  `.editorconfig` — none found) and no `requirements.txt`/`pyproject.toml`
  pins dependencies — the only documented setup today is README's "Running
  the firmware" section (`pip install mpremote`, `python -m pytest tests/`).
  `CONTRIBUTING.md` needs to give the actual minimal `pip install` commands
  since nothing else in the repo does.
- Recent commit history (`git log --oneline`) is loosely
  `type(scope): description` or `Area: description`, imperative mood, not a
  strictly enforced convention (some commits have no scope, one has none of
  the above — "Design review pass: copy, touch targets, consistency"). Guidance
  should describe the observed pattern, not invent a stricter rule the
  project's own history doesn't follow.
- 571 tests currently collect under `python3 -m pytest tests/` (confirmed by
  running `--collect-only`); Python 3.12 is what CI (`pages.yml`) pins and
  what's installed locally (`python3 --version` → 3.12.3) — use "3.12+" as the
  stated requirement, not a hard pin, since nothing in the repo's own tooling
  enforces an exact version.
- This plan assumes the sibling license plan's recommendation
  (`docs/superpowers/plans/2026-07-24-license.md`, Apache License 2.0) for the
  standard "your contributions are licensed under the project's license"
  line — phrased so it doesn't silently go stale if the user picks a
  different license instead (see Task 1, Step 1's exact wording).

## Global Constraints

- **Don't duplicate `CLAUDE.md`; adapt it.** Where `CONTRIBUTING.md` restates
  an Iron rule, keep the substance identical to `CLAUDE.md` — if the two
  drift, a contributor following one will break the other.
- **Don't invite contributors into `TODO.md`.** Point external contributors at
  GitHub Issues; mention `TODO.md`/`ROADMAP.md` only as "here's where the
  maintainer's own plan lives, for context," not as something to edit.
  `ROADMAP.md` (the public-facing one, not `design/roadmap.md`) is already the
  intended public planning surface.
- **Don't invent tooling that doesn't exist** (no linter to run, no
  `npm install` step for the web twin — it's plain ES modules loaded
  directly by the browser, no bundler).
- **No code changes** — this is a documentation-only plan.

## File structure

```
CONTRIBUTING.md    # new
README.md          # modified — new short "Contributing" section
```

---

### Task 1: `CONTRIBUTING.md`

**Files:**
- Create: `CONTRIBUTING.md`

**Interfaces:** None.

**Exact proposed content:**

```markdown
# Contributing to LOTR LCG Presto HUD

Thanks for the interest — this is a small hobby project (a solo maintainer,
no CI gate yet), so the fastest path to a merged PR is understanding the two
things below before you start.

## The one rule that matters most: two twins, one behavior

This app ships as **two synchronized implementations** of the same screens:

- **Web twin** (`docs/js/`) — plain ES modules, runs in any browser, no
  build step. This is the primary development target.
- **Firmware** (`gamestate.py`, `phases.py`, `ui/`, `main.py`) — MicroPython,
  runs on the actual [Pimoroni Presto](https://shop.pimoroni.com/en-us/products/presto)
  hardware.

They share the same screens, the same button-id protocol, the same layout
math, and the same game logic — deliberately kept in lockstep so a feature
built once behaves identically on both. **New features are built and
verified in `docs/js/` first, then ported to the Python.** A PR that changes
one twin and not the other is unfinished, even if it "works" — the maintainer
will ask for the port before merging.

You do **not** need the physical hardware to contribute. Web-only PRs are
welcome and are how most of this project has been built; porting to firmware
can happen as a separate follow-up (by you, if you have a Presto, or by the
maintainer otherwise) rather than blocking your PR.

One more generated-file rule that trips people up: `tools/gen_web_data.py`
regenerates `docs/js/{phases,icons,metrics}.js` from `phases.py`/`ui/icons.py`.
**Never hand-edit those three files** — if your change touches turn-sequence
data, icon masks, or font metrics, change the Python source and re-run the
generator.

## Setup

No build step, no package manager, no lockfile. You need:

```sh
python3 -m pip install pytest      # test runner
python3 -m pip install Pillow cairosvg   # optional — only for tools/build_icons.py
```

Python 3.12+ is what this project develops and tests against (no hard pin
enforced anywhere in the repo, but that's the known-good version).

To see the web twin in a browser, the card database it reads needs to exist
once locally (it's generated, gitignored, and not required for most UI work
that doesn't touch quest/card data):

```sh
python3 tools/build_card_data.py     # writes docs/data/ (one network fetch)
python3 -m http.server -d docs 8000  # serve the twin
```

Then open `http://localhost:8000/`.

## Making a change

1. **Check the issue tracker first.** Open
   [Issues](https://github.com/andrhamm/lotr-lcg-presto-hud/issues) — bug
   reports and suggestions use templates already set up there. If nothing
   covers what you want to do, open a Suggestion issue before writing code;
   for anything beyond a small fix, it saves both of us from a PR built on a
   misunderstanding of scope or direction.
   - `TODO.md` and `design/roadmap.md` are the maintainer's own working
     notes/backlog (an Obsidian board and design journal) — useful to skim
     for context on where the project is headed, but not the place to file
     things; that's what GitHub Issues is for.
2. **Build it web-first** (`docs/js/`). Verify by hand in a browser.
3. **Port to firmware** (`ui/`, `gamestate.py`, etc.) if you're able to —
   same screen structure, same button ids, MicroPython instead of ES modules.
   If you can't test on real hardware, say so in the PR; the maintainer can
   verify with `tools/preview.py` (renders any test scene to a PNG through
   the actual device graphics pipeline) or on the device itself.
4. **Add or update tests.** `tests/scenes.py` holds named wireframe "scenes"
   (a game state + a screen/modal to render); `tests/test_layout.py` runs a
   pixel-level linter over every scene in that list (every draw call stays
   on-screen, no two text runs overlap, every touch target is at least 24×24
   px and on-screen). If you add a screen or modal, add a scene for it —
   that's how it gets linted.
5. **Run the full suite:**
   ```sh
   python3 -m pytest tests/ -q
   ```
   It must be green (571 tests as of this writing) before a PR is ready for
   review. There's no CI running this automatically yet (see the open
   Playwright-CI proposal on the roadmap) — until there is, please paste the
   passing output into the PR description.
6. **If your change touches game rules or UI copy describing them**, check it
   against the rulebook/FAQ, not memory or assumption — this project has
   shipped copy bugs before from trusting a mechanic's description without
   re-checking the source.

## Commit style

Loosely `type(scope): description` or `Area: description`, imperative mood
(e.g. `feat(quest): add branch-stage paging`, `Web: fix sailing tip copy`) —
look at `git log` for the current pattern rather than following a rigid
template; it isn't strictly enforced.

## Design/visual changes

This app targets a fixed 480×480 touchscreen — there's no responsive layout
to fall back on, so spacing and touch-target sizing are load-bearing, not
cosmetic. `tests/test_layout.py` catches overlap/off-screen/target-size bugs
automatically; for anything visual, a before/after screenshot in the PR
(browser devtools for the web twin, or `tools/preview.py` for a device-exact
render) makes review much faster.

## License

By submitting a PR, you agree your contribution is licensed under this
project's license (see [`LICENSE`](LICENSE) — Apache License 2.0 as of this
writing; check the file itself if this has changed since). No CLA, no
copyright assignment — just the same license the rest of the code ships
under.

## Code of conduct

None of the formal-document kind exists yet — the short version is: be kind,
assume good faith, and remember this is a hobby project made for fun. If that
ever stops being enough, open an issue and it'll get written properly.
```

- [ ] **Step 1: Create `CONTRIBUTING.md`** with the exact content above,
  adjusting the "Apache License 2.0 as of this writing" line to match
  whichever license actually landed if the sibling license plan's
  recommendation was changed before this task runs (check `LICENSE`'s first
  substantive line for the SPDX name in force).
- [ ] **Step 2: Verify every command in the "Setup" section actually works**
  as written, from a clean checkout: `pip install pytest`, then
  `python3 -m pytest tests/ -q` (should collect ~571 tests and pass);
  `python3 tools/build_card_data.py` (one network fetch, writes `docs/data/`);
  `python3 -m http.server -d docs 8000` then load `http://localhost:8000/` in
  a browser and confirm the boot screen renders. Fix the doc, not the
  commands, if anything's off (this file must describe what actually works).
- [ ] **Step 3: Verify the referenced paths are real** — `tests/scenes.py`,
  `tests/test_layout.py`, `tools/preview.py`, `tools/gen_web_data.py`,
  `.github/ISSUE_TEMPLATE/` all exist as named (confirmed during planning;
  re-confirm at implementation time in case they've moved).

---

### Task 2: README "Contributing" section

**Files:**
- Modify: `README.md`

**Interfaces:** None.

**Exact proposed text** — add near the top, after the opening description
paragraph and before "The app, screen by screen" (contributors and users are
different audiences; put this where a potential contributor skimming the top
of the README will actually see it, not buried after the screenshot tour):

```markdown
## Contributing

Bug reports, suggestions, and PRs are welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md) for setup, the web-first-then-firmware
workflow this project relies on, and how to open an issue.
```

- [ ] **Step 1: Add the section** at the chosen location with the exact text
  above.
- [ ] **Step 2: Confirm it doesn't collide** with the existing "Web twin ↔
  firmware" section further down (that one's an architecture explainer for
  readers in general; this one's a contributor call-to-action near the top —
  keep both, they serve different readers at different points in the scroll).
- [ ] **Step 3:** `python3 -m pytest tests/` → confirm still green.

---

## Self-Review

**Spec coverage:** `CONTRIBUTING.md` created with concrete, runnable setup
instructions (not a placeholder) → Task 1; README section added → Task 2;
both grounded in what's actually in the repo (existing issue templates,
existing `TODO.md`/board semantics, existing test count, existing — or
rather nonexistent — lint tooling) rather than generic open-source
boilerplate.

**The one thing most likely to go wrong for a first-time contributor** — not
realizing this is a two-twin project and sending a web-only or
firmware-only PR — gets the most prominent placement in the doc (first
section after the title), with a concrete generated-file trap
(`gen_web_data.py`'s three output files) called out immediately after it,
since that's the other way a well-intentioned PR silently breaks the
lockstep rule.

**Consistency with the sibling plans:** the License section's wording
tracks `docs/superpowers/plans/2026-07-24-license.md`'s Apache-2.0
recommendation without hard-coupling to it (Step 1 explicitly says to check
`LICENSE` if that recommendation changed); the "no CI yet" framing in
Task 1's step 5 is accurate as of this plan and points at
`docs/superpowers/plans/2026-07-24-playwright-ci.md` implicitly (via "the
open Playwright-CI proposal on the roadmap") without assuming it's already
landed — if it lands first, drop that sentence and the "paste passing output"
ask, since a CI badge/check will do the job instead.

**Placeholder scan:** every command in the Setup and Making-a-change
sections is a real, verified command against this actual repo, not a
generic "npm install && npm test" template — checked against `tests/`,
`tools/`, and `.github/ISSUE_TEMPLATE/`'s actual contents during planning.
