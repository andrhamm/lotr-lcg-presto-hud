# Full CI: Playwright Integration Tests + PR Coverage Reports — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A GitHub Actions workflow that runs on every PR: the existing
`pytest` suite (plus code coverage), and a new Playwright suite driving the
**web twin** through real user flows in a real browser — with a PR comment
that summarizes pass/fail, links failure screenshots, and reports coverage,
so a reviewer sees test results without pulling the branch.

**Scope note:** Playwright drives the web twin (`docs/js/`) only. The
firmware (`ui/`, MicroPython on real Presto hardware) has no browser to
automate — it stays covered by the existing `pytest` suite (host-run Python
logic + the layout linter) exactly as today. This is consistent with Iron
rule #1 (web-first): the web twin is the one built to be exercised headless
and in CI; the firmware is verified on-device by the maintainer.

## Architecture

```
package.json                    # new — @playwright/test devDependency
playwright.config.js            # new — webServer, projects (desktop + touch), reporters
tests/e2e/
  helpers/
    hud.js                      #   tap/tapTouch (real dispatched PointerEvents),
                                 #   readState (localStorage introspection),
                                 #   gotoFresh (clears storage, loads app)
  boot-and-round.spec.js        #   new-game -> full guided round -> log/settings
  quest-picker.spec.js          #   scenario picker -> QuestCardModal paging/branch
  sailing.spec.js               #   sailing toggle -> test log -> heading shift;
                                 #   asserts the corrected tip copy (see the M5 plan)
.github/workflows/
  ci.yml                        # new — pytest+coverage job, playwright+coverage job,
                                 #   PR-comment job (needs: [pytest, playwright])
  ci-extended.yml               # new — weekly cron: firefox/webkit + full matrix,
                                 #   non-blocking, no PR comment
```

`pages.yml` (deploy) is untouched — this is a separate, PR-triggered
workflow, not a rename/replacement.

## Tech Stack

`@playwright/test` (Node), driving Chromium (+ Firefox/WebKit in the
extended, non-blocking workflow) against the existing unbundled ES-module web
twin (no bundler needed — `docs/js/*.js` loads directly in a browser today,
confirmed by reading `docs/index.html`). Python side unchanged
(`pytest` + `pytest-cov`, new). GitHub Actions for orchestration
(`actions/github-script` for the PR comment — no new marketplace-action trust
required beyond what's already a first-party GitHub action).

## Context

TODO.md "Ideas": *"full Github actions CI with playwright integration tests
for all UI/UX functionality. Automatic PR coverage report with screenshots
of failing issues... at least one of my private GH projects implement
this."* This plan cannot see or copy that private-repo implementation (no
access) — everything below is designed from scratch against this repo's
actual code and standard, first-party-friendly GitHub Actions capabilities,
not a guess at what the private project does. Where a choice was made
between a simple/robust option and a fancier one, both are given — see
Task 5.

**Why "dispatch real PointerEvents" is a hard requirement, verified against
this app's actual input handling** (`docs/js/main.js`, read in full for this
plan):

```js
canvas.addEventListener("pointerdown", ev => {
  const now = performance.now();
  if (now - lastTapT < 50) return;         // guards duplicate dispatch
  lastTapT = now;
  const r = canvas.getBoundingClientRect();
  const x = (ev.clientX - r.left) * (480 / r.width);
  const y = (ev.clientY - r.top) * (480 / r.height);
  handleTap(x, y);
});
```

Two consequences for the test design:
1. **The whole UI is one `<canvas>`.** There are no per-button DOM nodes to
   locate by role/text/testid — every "button" is a shape drawn at a
   game-state-dependent pixel position. Playwright's element-locator APIs
   (`getByRole`, `getByText`, `locator(...).click()`) have nothing to grab.
   The only viable interaction is **coordinate-based**: compute where a
   button is (from the same layout math the app itself uses — button
   rects are already available in-app as `screens.play.buttons`, etc., but
   the simplest and most decoupled approach for tests is to hardcode/derive
   the same coordinates the screen code draws at, exactly like a real user
   reading the screen would) and click *there*.
2. **The listener is `pointerdown`, not `click`.** A generic
   `element.click()` DOM call fires a `click` event only — this app never
   listens for `click` on the canvas, so that call is a silent no-op. Real
   input is required. Playwright's `page.mouse.click(x, y)` and
   `page.touchscreen.tap(x, y)` both drive input at the browser-engine
   level (via CDP), producing genuinely trusted `pointerdown`/`pointerup`
   events — that's the "real PointerEvent" this plan's helper uses as the
   default, primary technique (Task 1), with a manually-constructed
   `new PointerEvent(...)` + `dispatchEvent()` documented as the fallback if
   engine-level input ever proves insufficient (e.g. a future headless
   quirk) — see Task 1, Step 3.
3. **The 50ms same-tap debounce** means a helper that fires more than one
   pointerdown in quick succession (e.g. `mouse.click` internally doing
   move+down+up, occasionally observed to double-fire pointerdown in some
   Chromium versions) can silently eat the second tap. The helper adds a
   small settle delay between taps for this reason (Task 1).

**Structured assertions on a canvas app.** Playwright cannot read
canvas-rendered text (no DOM to query). Two channels exist without any app
code changes:
- **Visual**: `expect(page).toHaveScreenshot()` (Playwright's built-in
  pixel-diff snapshot testing) against the canvas region.
- **State**: `docs/js/main.js` calls `saveState(game)` — which writes
  `JSON.stringify({saved_at, state: game.toDict()})` to
  `localStorage["lotr-hud-state"]` — after essentially every state-changing
  interaction (verified: 9 call sites, covering every button handler that
  returns a truthy "changed" result, plus every explicit view transition).
  Reading that key after a tap gives structured, exact game state (threat,
  willpower, view, round, step, etc.) for free, with zero app code changes.

  This covers most assertions this plan needs. If implementation surfaces a
  gap `localStorage` truly can't reach (e.g. transient in-modal state before
  it commits), the fallback is a small, explicitly test-only debug bridge —
  `docs/js/main.js` currently exposes nothing on `window` except one
  `window.open(...)` call (verified by grep) — gated behind a query param so
  it never activates for real players:
  ```js
  if (new URLSearchParams(location.search).has("e2e")) {
    window.__hud = { get game() { return game; }, get active() { return active; } };
  }
  ```
  Add this **only if Task 2/3 hits a wall** the `localStorage` channel can't
  cover — don't add it speculatively (see Global Constraints).

**Data dependency.** Several flows (scenario picker, QuestCardModal) need
`docs/data/*.json`, which is generated and gitignored. CI must build it
before serving the twin — reusing `tools/build_card_data.py` exactly as
`pages.yml` already does. Unlike `pages.yml`, this workflow runs on **every
PR** (much more frequently than pushes to `main`), so it deliberately does
**not** run the slow, third-party-heavy optional builders
(`build_hob_enrichment.py`: ~20s/request, 40+min cold per `CLAUDE.md`;
`build_tips.py`: also serial/rate-limited) — every screen this plan tests
already degrades gracefully without that enrichment (confirmed:
`ScenarioOptionsScreen` falls back to a scenario's own set list;
`QuestCardModal`'s Tips button stays disabled without `tips.json`), so
skipping them keeps PR CI fast and avoids hammering Hall of
Beorn/Vision of the Palantir on every push. `build_icons.py` is cheap
(one tarball fetch, no per-item network calls) and worth keeping so
icon-dependent screens render as designed.

## Global Constraints

- **Two twins in lockstep still applies, but asymmetrically here**: this CI
  plan only *tests* the web twin (Architecture's Scope note). It must never
  become a reason to skip porting a feature to firmware — that's still the
  `pytest` suite's + maintainer's job, unchanged by this plan.
- **`python3 -m pytest tests/` stays the source of truth for firmware/shared
  logic.** This plan adds coverage reporting to it (Task 4) but does not
  change what it tests.
- **Don't add app code speculatively.** The `window.__hud` debug bridge in
  Context is written out because it's the documented fallback, not because
  it's assumed necessary — only add it if a task's Step actually hits a wall
  `localStorage` can't cover, and say so in that task's report.
- **PR-gating CI must be fast and third-party-network-light** — Chromium-only
  by default (Task 4); no Hall of Beorn/Vision of the Palantir fetches
  (Context, above); Firefox/WebKit and any slower/broader matrix live in the
  separate, non-blocking, weekly `ci-extended.yml` (Task 6).
- **No secrets required.** Everything here runs against public data with the
  repo's own `GITHUB_TOKEN` (for posting PR comments) — no new secrets to
  configure.
- **Don't touch `pages.yml`.** It deploys `main`; this plan's workflows are
  additive and PR/schedule-triggered.

## File structure

```
package.json                       # new
playwright.config.js               # new
tests/e2e/
  helpers/hud.js                   # new
  boot-and-round.spec.js           # new
  quest-picker.spec.js             # new
  sailing.spec.js                  # new
.github/workflows/ci.yml           # new
.github/workflows/ci-extended.yml  # new
docs/js/main.js                    # modified — ONLY if Task 2/3 needs the debug bridge
```

---

### Task 1: Scaffold Playwright + the tap/state helpers

**Files:**
- Create: `package.json`, `playwright.config.js`
- Create: `tests/e2e/helpers/hud.js`

**Interfaces:**
- Produces: `tapAt(page, x, y)`, `tapAtTouch(page, x, y)` — logical
  480×480-space coordinates in, real dispatched input out.
  `readState(page)` — parses and returns `localStorage["lotr-hud-state"]`'s
  `state` object, or `null` if no save exists yet. `gotoFresh(page, path?)` —
  clears `localStorage` and navigates to the twin.

- [ ] **Step 1: Scaffold the Node project.**
  ```sh
  npm init playwright@latest
  ```
  Accept: TypeScript → **No** (the rest of this repo is plain JS/ES modules,
  no build step anywhere — stay consistent); tests folder → `tests/e2e`;
  add a GitHub Actions workflow → **No** (Task 4 writes a purpose-built one,
  not the generic scaffold). Confirm `package.json` ends up with
  `"type": "module"` (or add it) so spec files can use the same
  `import`/`export` style as `docs/js/`. Pin whatever `@playwright/test`
  version the scaffold installs (check current at implementation time — this
  plan was written without a live npm registry check, so don't hardcode a
  version here that might already be stale).

- [ ] **Step 2: `playwright.config.js`.**
  ```js
  import { defineConfig, devices } from "@playwright/test";

  export default defineConfig({
    testDir: "./tests/e2e",
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 1 : 0,
    reporter: process.env.CI
      ? [["html", { open: "never" }], ["json", { outputFile: "playwright-report/results.json" }], ["github"]]
      : "list",
    use: {
      baseURL: "http://localhost:8000",
      trace: "retain-on-failure",
      screenshot: "only-on-failure",
      video: "retain-on-failure",
    },
    webServer: {
      // docs/data/ must already exist (built as a prior CI step / by hand
      // locally) - the server just serves static files, it doesn't build data.
      command: "python3 -m http.server 8000 --directory docs",
      url: "http://localhost:8000",
      reuseExistingServer: !process.env.CI,
      timeout: 10_000,
    },
    projects: [
      {
        name: "chromium-desktop",
        use: { ...devices["Desktop Chrome"] },
      },
      {
        name: "chromium-mobile-touch",
        use: { ...devices["Pixel 7"] },   // hasTouch:true, real device viewport
      },
    ],
  });
  ```
  Two projects by default (desktop mouse + mobile touch) because this is a
  touchscreen device app — both interaction modes are real usage, not just
  desktop-as-a-proxy. Both are Chromium (cheap); Firefox/WebKit are the
  extended workflow's job (Task 6), not every PR's.

- [ ] **Step 3: `tests/e2e/helpers/hud.js`.**
  ```js
  const SETTLE_MS = 80;   // clears the app's own 50ms same-tap debounce

  /** Map logical 480x480 app-space coordinates to real page coordinates and
   * dispatch a real, engine-level pointer tap there - NOT a bare .click(),
   * which fires only a `click` event this canvas app never listens for
   * (it listens for `pointerdown`; see docs/js/main.js). page.mouse.click
   * drives input via CDP at the browser-engine level, producing genuinely
   * trusted pointerdown/pointerup events. */
  export async function tapAt(page, x, y) {
    const box = await page.locator("#screen").boundingBox();
    if (!box) throw new Error("canvas #screen not found/visible");
    const px = box.x + (x / 480) * box.width;
    const py = box.y + (y / 480) * box.height;
    await page.mouse.click(px, py);
    await page.waitForTimeout(SETTLE_MS);
  }

  /** Touch-input variant (mobile/touch projects) - page.touchscreen.tap
   * produces pointerType:"touch" events, same trusted-input guarantee. */
  export async function tapAtTouch(page, x, y) {
    const box = await page.locator("#screen").boundingBox();
    if (!box) throw new Error("canvas #screen not found/visible");
    const px = box.x + (x / 480) * box.width;
    const py = box.y + (y / 480) * box.height;
    await page.touchscreen.tap(px, py);
    await page.waitForTimeout(SETTLE_MS);
  }

  /** Fallback only - a manually constructed PointerEvent, for the rare case
   * engine-level input isn't viable (documented in the CI plan's Context).
   * Dispatched from page-context JS, so it is NOT isTrusted - but this app's
   * plain addEventListener("pointerdown", ...) fires for untrusted dispatched
   * events too (only certain default browser gestures require isTrusted). */
  export async function dispatchPointerDown(page, x, y) {
    const box = await page.locator("#screen").boundingBox();
    const clientX = box.x + (x / 480) * box.width;
    const clientY = box.y + (y / 480) * box.height;
    await page.evaluate(({ clientX, clientY }) => {
      const el = document.getElementById("screen");
      el.dispatchEvent(new PointerEvent("pointerdown", {
        bubbles: true, cancelable: true, composed: true,
        pointerId: 1, isPrimary: true, pointerType: "mouse",
        button: 0, clientX, clientY,
      }));
    }, { clientX, clientY });
    await page.waitForTimeout(SETTLE_MS);
  }

  /** Reads the app's own persisted state (docs/js/main.js's saveState()) -
   * structured, exact game state with zero app code changes. Returns null
   * before any save has happened yet (e.g. still on the boot screen). */
  export async function readState(page) {
    return page.evaluate(() => {
      const raw = localStorage.getItem("lotr-hud-state");
      if (!raw) return null;
      return JSON.parse(raw).state;
    });
  }

  /** Clean slate: clear persisted state/prefs, load the app fresh. */
  export async function gotoFresh(page) {
    await page.goto("/");
    await page.evaluate(() => localStorage.clear());
    await page.reload();
  }
  ```

- [ ] **Step 4: Smoke-test the helpers** with a throwaway one-off spec (not
  committed) that calls `gotoFresh`, screenshots the boot screen, and
  confirms `#screen` is a 480×480 canvas with non-blank pixels. Delete the
  throwaway once Task 2's real spec covers the same ground.

---

### Task 2: Core happy-path spec — new game through a guided round

**Files:**
- Create: `tests/e2e/boot-and-round.spec.js`

**Interfaces:**
- Consumes: Task 1's `helpers/hud.js`.

Grounded in the actual screen flow (`docs/js/screen_play.js`, `README.md`'s
"The guided round" section): Boot → New Game → add players/threat → Start →
one-time Setup phase → `resource_planning` → `quest_commit` → `quest_staging`
→ `quest_resolution` → `travel` → (encounter/combat notes) → `refresh` → back
to `resource_planning` (round 2) → Game Log → Settings. This is the literal
"a new player completes a full game guided by the HUD alone" beta-acceptance
criterion from `design/roadmap.md` — this spec is that criterion, automated.

- [ ] **Step 1: Boot -> New Game -> Start.** `gotoFresh`; tap "New Game";
  fill in player count/threat via the setup screen's controls (coordinates
  read from `docs/js/screens_other.js`'s `SetupScreen` at implementation
  time — the exact layout, not guessed); tap "Start"; `readState` and assert
  `view` is the one-time setup view and `round === 1`.
- [ ] **Step 2: Walk one full round**, tapping "Next Phase"/the primary CTA
  through `resource_planning` → `quest_commit` → `quest_staging` →
  `quest_resolution` → `travel` → `refresh`, asserting `readState().view`
  transitions in the exact order `docs/js/gamestate.js`'s view-advance logic
  defines after each tap. At `refresh`, assert threat rose by each player's
  configured per-round amount and `round` incremented after "End round."
- [ ] **Step 3: Header nav.** From round 2's `resource_planning`, tap the
  header's `R2 ...` step label to open the Game Log; assert at least one
  logged entry from round 1 (staging/resolution/refresh events); tap back;
  tap the phase-name header element to open Game Phases; assert the current
  step is highlighted; tap back; tap `Set.` to open Settings.
- [ ] **Step 4: Save & Quit round-trips.** From Settings, tap "Save & Quit";
  assert the Boot screen's "Resume Game" button is now present (state
  persisted); tap "Resume Game"; assert `readState().view` matches where the
  session left off.
- [ ] **Step 5: Visual snapshot.** `await expect(page).toHaveScreenshot("round1-quest-commit.png")`
  at one representative, stable point in the flow (post-Step-2's
  `quest_commit` view) — establishes the baseline; subsequent CI runs diff
  against it. Keep to one or two snapshot points in this spec (broader visual
  coverage is Task 3's/a later phase's job, see Self-Review) so this spec
  stays about *flow correctness*, not pixel-diffing.
- [ ] **Step 6: Run it.** `npx playwright test boot-and-round.spec.js` locally
  against a `python3 tools/build_card_data.py`-populated `docs/data/` ->
  green, including on the `chromium-mobile-touch` project
  (`--project=chromium-mobile-touch`, using `tapAtTouch` in a touch-specific
  variant of Step 1 if any interaction proves mouse-only-flaky).

---

### Task 3: Quest-picker + Sailing specs

**Files:**
- Create: `tests/e2e/quest-picker.spec.js`
- Create: `tests/e2e/sailing.spec.js`

**Interfaces:**
- Consumes: Task 1's helpers; the same coordinate-reading-from-source
  discipline as Task 2.

**`quest-picker.spec.js`** — covers the M4 quest-picker family (the most
complex recently-built feature, per `git log`/current branch
`feat/quest-picker`): New Game → "New Quest" (scenario source → pick cycle →
choose scenario, e.g. Passage Through Mirkwood) → Scenario Options (Standard
mode) → Quest Setup screen renders with stages/points preloaded → tap "View
quest card" → `QuestCardModal` opens on the *current* stage → page
Next/Prev through all stages → on the branch stage (stage 3, per the card-data
pipeline's own golden test data), tap the alternative-switch control and
assert the displayed card changes → tap the disabled Tips button and assert
nothing happens (`readState()` unchanged) → DONE closes back to Quest Setup.

- [ ] **Step 1: Write the scenario-picker walk** (source → cycle → scenario →
  options → Quest Setup), asserting `readState().scenario.slug ===
  "passage-through-mirkwood"` and the preloaded stage count/points match the
  card-data pipeline's own documented golden values (stage 1: 8 points,
  stage 2: 2, stage 3: branch {0, 10} — from
  `docs/superpowers/specs/2026-07-24-card-data-pipeline-design.md`'s Testing
  section, so this spec is also an end-to-end cross-check that the built
  `docs/data/` matches what the unit tests assert against a fixture).
- [ ] **Step 2: Write the `QuestCardModal` walk** (open, page every stage,
  branch-switch, disabled-Tips-button no-op, DONE) per the interaction
  contract already established in
  `docs/superpowers/plans/2026-07-24-quest-card-modal.md`'s Task 1 (same
  button ids: `next`/`prev`/`alt`/`tips`/`close` — this spec exercises the
  same contract that plan's `pytest` tests exercise, just end-to-end through
  real taps instead of calling `on_button` directly).
- [ ] **Step 3: Run it green** on `chromium-desktop`.

**`sailing.spec.js`** — covers the sailing/heading mechanic
(`docs/js/screen_play.js`'s `quest_sailing` view, `SailingModal`): pick a
sailing-flagged scenario (e.g. Flight of the Stormcaller — confirmed
`sailing:true` per the card-data pipeline's own sanity check) or toggle
Sailing on manually; advance into `quest_sailing`; assert the heading shifted
one step off-course on entry (per `quests/sailing-tests.md`'s validated
timing); open "Log sailing test," submit a wheel count, assert the heading
shifts back accordingly.

- [ ] **Step 1: Write the flow** as described above.
- [ ] **Step 2: Regression-guard the sailing tip copy.** This is the one
  place in this plan that directly depends on the sibling M5 plan
  (`docs/superpowers/plans/2026-07-24-m5-beta-hardening.md`, Task on the
  Sailing "discarded" copy fix) — once that fix lands, the tip text reads
  "...looks at and discards that many cards." (not "looks at that many
  cards."). Since Playwright can't read canvas text directly, assert this
  visually: `toHaveScreenshot("sailing-tip.png")` on the tip panel region,
  taken *after* the M5 copy fix lands (if this task runs first, take the
  snapshot as-is and add a `// TODO: re-baseline after the M5 Sailing-copy
  fix lands` comment rather than blocking on task ordering across plans).
- [ ] **Step 3: Run it green.**

---

### Task 4: `.github/workflows/ci.yml` — pytest + Playwright, PR-triggered

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:** Two jobs Task 5's PR-comment job depends on by name
(`pytest`, `playwright`) via `needs:`.

```yaml
name: CI
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  pytest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python3 -m pip install pytest pytest-cov
      - name: Run pytest with coverage
        run: |
          python3 -m pytest tests/ -q \
            --cov=. --cov-report=xml --cov-report=term \
            --ignore=tests/e2e
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: pytest-coverage
          path: coverage.xml
          retention-days: 14

  playwright:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Build card data (required, fast - one network fetch)
        run: python3 tools/build_card_data.py
      - name: Install icon rasterizer deps
        # Same continue-on-error posture as pages.yml - icons are optional,
        # a fetch/rasterize hiccup here must not fail the whole CI run.
        continue-on-error: true
        run: |
          sudo apt-get update && sudo apt-get install -y librsvg2-bin
          pip install Pillow
      - name: Build icons
        continue-on-error: true
        run: python3 tools/build_icons.py
      # Deliberately NOT building Hall of Beorn enrichment or strategy tips
      # here (see this plan's Context: "Data dependency") - both are slow,
      # third-party, best-effort, and every tested screen already degrades
      # gracefully without them. Keeps every PR run fast and polite to
      # third parties we don't control.
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci
      - run: npx playwright install --with-deps chromium
      - name: Run Playwright
        run: npx playwright test
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-report
          path: |
            playwright-report/
            test-results/
          retention-days: 14

  pr-comment:
    needs: [pytest, playwright]
    if: always() && github.event_name == 'pull_request'
    uses: ./.github/workflows/ci-pr-comment.yml
    permissions:
      contents: read
      pull-requests: write
      actions: read
```

- [ ] **Step 1: Create the file** with the content above.
- [ ] **Step 2: Confirm `--ignore=tests/e2e`** is actually necessary — pytest
  only collects `test_*.py`/`*_test.py` by default, so `.spec.js` files are
  already invisible to it; keep the flag anyway as an explicit, self-documenting
  guard against a future accidental `test_*.py` landing under `tests/e2e/`.
- [ ] **Step 3: Push a throwaway branch/PR and confirm both jobs run and
  pass** before wiring Task 5's dependent workflow (a `workflow_call` job
  that doesn't exist yet will fail to resolve `uses:` — implement Task 5
  before this reference is live, or stub it first and fill in after).

---

### Task 5: PR comment — pass/fail summary, coverage, failure screenshots

**Files:**
- Create: `.github/workflows/ci-pr-comment.yml` (a reusable `workflow_call`
  workflow, invoked by `ci.yml`'s `pr-comment` job above)

**Interfaces:** Reads the `pytest-coverage` and `playwright-report`
artifacts Task 4's jobs upload.

Two versions, baseline required + inline-screenshots optional — see Context
for why this plan doesn't assume a single "obviously correct" mechanism.

**5a (required): sticky comment with pass/fail + coverage + a link to the
full report.** Robust, no extra permissions beyond `pull-requests: write`,
works today with zero additional infrastructure.

```yaml
name: CI PR comment
on:
  workflow_call:
jobs:
  comment:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
        with: { name: pytest-coverage, path: artifacts/ }
        continue-on-error: true
      - uses: actions/download-artifact@v4
        with: { name: playwright-report, path: artifacts/playwright/ }
        continue-on-error: true
      - name: Build summary + upsert PR comment
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const runUrl = `${context.serverUrl}/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId}`;
            let body = `<!-- ci-pr-comment-marker -->\n## CI results\n\n`;

            // Playwright JSON reporter summary (Task 1's playwright.config.js
            // writes playwright-report/results.json)
            try {
              const r = JSON.parse(fs.readFileSync('artifacts/playwright/playwright-report/results.json', 'utf8'));
              const stats = r.stats ?? {};
              body += `**Playwright:** ${stats.expected ?? '?'} passed, ` +
                      `${stats.unexpected ?? 0} failed, ${stats.skipped ?? 0} skipped\n\n`;
              const failures = (r.suites ?? []).flatMap(s => s.specs ?? [])
                .filter(s => !s.ok).map(s => s.title);
              if (failures.length) {
                body += `Failing:\n` + failures.map(f => `- \`${f}\``).join('\n') + '\n\n';
              }
            } catch { body += `**Playwright:** report not found (job may have failed before producing one)\n\n`; }

            // pytest-cov summary (coverage.xml's line-rate attribute)
            try {
              const xml = fs.readFileSync('artifacts/coverage.xml', 'utf8');
              const m = xml.match(/line-rate="([\d.]+)"/);
              if (m) body += `**Python coverage:** ${(parseFloat(m[1]) * 100).toFixed(1)}%\n\n`;
            } catch { body += `**Python coverage:** report not found\n\n`; }

            body += `[Full report, traces, and failure screenshots](${runUrl})\n`;

            const { data: comments } = await github.rest.issues.listComments({
              ...context.repo, issue_number: context.issue.number,
            });
            const mine = comments.find(c => c.body.includes('ci-pr-comment-marker'));
            if (mine) {
              await github.rest.issues.updateComment({ ...context.repo, comment_id: mine.id, body });
            } else {
              await github.rest.issues.createComment({ ...context.repo, issue_number: context.issue.number, body });
            }
```

- [ ] **Step 1: Create `ci-pr-comment.yml`** with 5a's content.
- [ ] **Step 2: Verify the sticky-comment upsert** — push two commits to a
  throwaway PR, confirm the second run edits the first run's comment rather
  than adding a new one (searches by the HTML comment marker).
- [ ] **Step 3: Verify a deliberately-broken spec** produces a comment
  listing it under "Failing," and that the report link's Artifacts section
  contains a screenshot for it (Playwright's `screenshot: "only-on-failure"`
  config from Task 1 handles the capture; this step just confirms it's
  actually there).

**5b (optional, do only if the linked-artifact experience in 5a is judged
insufficient): inline screenshots in the comment body itself**, not just a
link to them. GitHub renders `raw.githubusercontent.com` image URLs inline in
markdown; artifact-store URLs require auth and don't. The standard way to get
a stable, unauthenticated image URL out of a CI run is to push the failure
screenshots to a dedicated branch and reference them there.

- [ ] **Step 1 (if pursuing 5b): add a scoped push step** to the `playwright`
  job (Task 4), gated `if: failure()`, that commits any files under
  `test-results/**/*.png` to an orphan branch (e.g. `e2e-artifacts`) under
  `pr-<number>/<run-id>/`, using a workflow-scoped `contents: write`
  permission (default `contents: read` everywhere else in this plan stays
  untouched).
- [ ] **Step 2: Reference those paths** as
  `![name](https://raw.githubusercontent.com/andrhamm/lotr-lcg-presto-hud/e2e-artifacts/pr-<number>/<run-id>/<name>.png)`
  markdown image links in 5a's comment body, one per failing spec that
  produced a screenshot.
- [ ] **Step 3: Add cleanup** — a second, simple workflow on
  `pull_request: closed` that deletes that PR's directory from the
  `e2e-artifacts` branch, so it doesn't grow unbounded. (For a personal-scale
  project, "let it grow and prune manually every so often" is also a
  legitimate call — note the tradeoff rather than treating cleanup as
  mandatory.)

---

### Task 6: Extended matrix — Firefox/WebKit, weekly, non-blocking

**Files:**
- Create: `.github/workflows/ci-extended.yml`

**Interfaces:** Reuses Task 1-3's spec files and helpers unchanged — only
the `playwright.config.js` projects invoked differs (via `--project` flags),
no new specs.

- [ ] **Step 1: Add the workflow**, `on: schedule: cron: "0 6 * * 1"` (weekly,
  Monday) `+ workflow_dispatch` (manual trigger), running the same
  data-build + `npx playwright install --with-deps` + `npx playwright test`
  steps as Task 4's `playwright` job, but across all of: `chromium-desktop`,
  `chromium-mobile-touch`, plus two more projects added to
  `playwright.config.js` (`firefox`, `webkit`, using `devices["Desktop
  Firefox"]`/`devices["Desktop Safari"]`).
- [ ] **Step 2: No PR-comment step** — this workflow isn't tied to a PR (it's
  scheduled); on failure, rely on GitHub's default "failed scheduled
  workflow" email/notification to the repo owner rather than building a
  second comment mechanism for a non-PR context.
- [ ] **Step 3: Confirm it's genuinely non-blocking** — it must not appear as
  a required/blocking check on PRs (it isn't triggered by `pull_request` at
  all, so this should already hold; double check no branch-protection rule
  references it by name).

---

## Self-Review

**Spec coverage:** GitHub Actions CI with Playwright integration tests →
Tasks 1-4; "for all UI/UX functionality" → Task 2 (full guided round, the
beta-acceptance-criterion flow) + Task 3 (the most complex recent feature,
quest-picker/QuestCardModal, plus sailing) as the concrete starting set, with
the Self-Review-visible acknowledgment (below) that "all" is aspirational on
day one and this plan establishes the pattern + infra, not exhaustive
coverage of every screen in one pass; "automatic PR coverage report" →
Task 5 (pass/fail + Python coverage %, sticky-updated, not spammed per push);
"with screenshots of failing issues" → Task 5a (screenshot artifacts,
captured automatically via config, linked from the comment) with 5b as the
literal inline-image reading of the ask, explicitly optional rather than
silently downgraded to the link-only version without saying so.

**What this plan deliberately does NOT claim:** it does not claim to
replicate "at least one of my private GH projects" — that repo wasn't
accessible during planning, so nothing here is presented as matching it;
everything is designed from this repo's actual code (`main.js`'s real event
listener, real `saveState` call sites, real screen files) and mainstream
GitHub Actions capabilities. Where a genuine design choice existed (5a vs.
5b for screenshots; localStorage-introspection vs. a new debug bridge for
assertions; Chromium-only-by-default vs. full-matrix-every-PR), the
tradeoff is stated rather than picked silently.

**Honest scope limit:** Task 2+3 cover two flows in depth (the core round,
and the quest-picker family) rather than literally every screen/modal in
this app (settings tiles, LED modal, elimination modal, game-over screen,
side-quest picker, etc. are not each given their own spec here). Extending
coverage to the rest is the same pattern repeated (Task 1's helpers, Task
2/3's style of "read the real screen file for coordinates, assert via
`readState`/screenshot") — left as follow-on work rather than padding this
plan with mechanically repetitive tasks for every remaining screen.

**Verification discipline:** the core technical claim this plan is built
on — that this app's canvas listens for `pointerdown` and needs real,
engine-dispatched input, not a bare DOM `.click()` — was verified by reading
`docs/js/main.js` directly (quoted in Context), not assumed from the user's
brief alone. The `saveState` call-site count (9) and the absence of any
existing `window.*` debug surface were both confirmed by `grep` before this
plan proposed localStorage-first, debug-bridge-only-if-needed, rather than
proposing new app code speculatively.

**Placeholder scan:** `playwright.config.js`, the helper module, and the
`ci.yml`/`ci-pr-comment.yml` workflow YAML are complete, working content, not
sketches — the specs (Tasks 2/3) are more outline-shaped (exact button
coordinates deferred to "read the real screen file at implementation time")
because those coordinates live in files (`screens_other.js`, `screen_play.js`)
that change release to release; hardcoding numbers into this plan that the
next `docs/js/` edit could invalidate would be a worse placeholder than
naming the exact source of truth to read them from.
