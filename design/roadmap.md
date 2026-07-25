---
title: Roadmap — prototype to beta
type: design-note
tags:
  - lotr-lcg/design
  - prototype-to-beta
related:
  - "[[design-review]]"
  - "[[stat-system]]"
  - "[[stats-redesign]]"
---

# Roadmap — prototype to beta

Five shippable milestones. Each runs the full cadence: **web-first → verify in
browser → port to firmware → pytest + layout scenes → deploy to Presto → soak**.
Web and firmware stay in lockstep. See [[design-review]] and [[stat-system]].

## Milestones
1. **M1 · Visual foundation** — the rethemed look across every screen (evolve the
   existing dark theme; consistent [[stat-system]]; icon colours; hierarchy).
   *Done when* the theme is applied everywhere and gold marks a single focal
   element per screen. **Status: DONE** — stat-colour system + the two-zone
   [[stats-redesign]] (flipped Players/Progress zones, circular token/arc
   primitives, Players + Progress detail views, DONE header) shipped on
   `feat/stats-redesign`; 382 host tests green. Pending: merge + device deploy.
2. **M2 · Phase clarity** — framework (red) / action-window (green) / stat model
   on every phase; threat-as-risk on Encounter & Combat; live willpower-vs-staging.
   *Done when* each phase answers: what happens, when can I act, what matters.
   **Status: DONE.** A new `phase_block` primitive splits every phase view into a
   red FRAMEWORK section (what happens automatically) and a green YOUR WINDOW
   section (when you may act). Quest·Staging gained a live willpower-vs-staging
   meter that names the resolution outcome; Encounter & Combat gained
   threat-as-risk framing plus turn-order captions; Refresh projects each living
   player's threat and flags a projection that crosses the danger threshold.
3. **M3 · Speed** — inline threat −/+, direct willpower total, one-tap all-players;
   declutter commit. No tap-and-hold. *Done when* a common round hits a tap budget.
   **Status: DONE.** Threat edits inline in the players zone (48px columns split
   into two 24px halves), willpower gained the same inline ± as staging, and
   `CommitModal` retired in favour of a one-tap "Confirm all commits (N/M)".
   A common round now takes **22 taps, down from 29**, gated by
   `tests/test_tap_budget.py`.
4. **M4 · Quest awareness** — quest picker preloads stages/points + **encounter
   sets to gather** (icon-pack glyphs); conditional advancement; per-quest threat
   warnings; **quest appendix** (tips/FAQ/campaign-cards from blog+forums);
   optional chase track. *Done when* picking Passage Through Mirkwood preloads
   8/2/10, lists its sets, and warnings go live.
   **Status: DONE.** Shipped: the full DragnCards card-data
   pipeline (M4-A, generated-only), the Setup-phase quest picker + R0 Quest
   Setup view with the pre-round-1 A→B flip (B-core), the quest-card modal
   (B-modal), the player side-quest picker (B-sidequest), set/scenario icons
   at 97% coverage (B-icons), Hall-of-Beorn sets-to-gather + release dates
   (B-data), and per-stage tips (B-tips). Picking Passage preloads **8 / 2 /
   {0,10}** and lists its three encounter sets with icons.
   and **B-resolve** — the guided, correctly-ordered progress resolution
   (location→explore→overflow→quest→advance: reveal side A→flip to side B),
   with branch selection and player-confirmed advancement for the ~137
   conditional (0-quest-point) stage cards.
   **Remaining in this theme:** per-quest threat warnings and the optional
   chase track (neither planned yet).
5. **M5 · Beta hardening** — first-run guidance + a legend for HUD conventions;
   copy/tone pass (incl. the Sailing "discarded" fix); accessibility + touch;
   full tests + on-device soak.

## Definition of beta (acceptance)
1. A **new player** completes a full game guided by the HUD alone.
2. A **veteran** plays a round at/near the tap budget.
3. It **looks like a crafted Middle-earth companion**, not a form.
4. **Quest-aware** for the captured quests.
5. Runs a **full multi-round game on the Presto**, zero tracebacks, state
   surviving a power cycle.

## Artifacts (claude.ai, private)
- **Roadmap deck** (prototype→beta presentation): https://claude.ai/code/artifact/77229372-a5be-4555-93eb-c17c4f927bdb
- **Three dark directions** (Wayfarer/Illuminated/Signalfire — A & C rejected,
  all "too modern"; kept for reference of what NOT to do):
  https://claude.ai/code/artifact/1b62c19e-f561-427c-88aa-275f4558a000

## Current state / next step
- **M1 shipped** (see [[stats-redesign]]): two-zone layout, circular primitives,
  both detail views, DONE header, staging inline ±, `commit_touched` +
  `quest_history`. Squash-merged to `main`.
- **M4 substantially shipped** on `feat/quest-picker` (see the M4 entry above):
  card-data pipeline + quest picker + card modal + side-quest picker + icons +
  enrichment + tips. ~594 host tests green; every flow verified end to end in
  the browser. **Not yet deployed to the Presto, and not yet pushed.**
- **Planned, not built:** every remaining TODO/roadmap item now has an
  implementation plan under `docs/superpowers/plans/` (B-resolve, M2, M3, M5,
  back button, action-window interstitials, game log, toasts/animation,
  side-quest clarity, RingsDB, campaign/history, license, contributing,
  Playwright CI) plus two hardware feasibility reports under
  `docs/superpowers/specs/`.
- **Pending ops:** push `feat/quest-picker` (local commits are unsigned — sign
  or re-sign before pushing), deploy `docs/data/` + firmware to the Presto, soak.
- **Next milestone: M5 · Beta hardening** — first-run guidance + conventions
  legend, copy/tone pass (the Sailing "discarded" fix is located and specified),
  accessibility (measured: `pal.dim` fails WCAG AA on every background it is used
  on), and an on-device soak protocol. Planned in
  `docs/superpowers/plans/2026-07-25-m5-beta-hardening.md`.
- **M1-M4 all shipped**; only M5 remains before the beta bar.
- Mockups must be **device-faithful** (render via `tools/preview.py`), not HTML.
