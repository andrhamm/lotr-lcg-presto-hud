---
kanban-plugin: board
tags:
  - kanban
---

# Board

Drop ideas into **Ideas**. Anything in **Ready** is fair game for background
workers. Card protocol lives in [[CLAUDE]] — workers claim cards, move them
across columns, and surface blockers here.

> **Most Ideas below now have a written implementation plan** under
> `docs/superpowers/plans/` (and two have feasibility reports under
> `docs/superpowers/specs/`). They are still Ideas — grooming them into Ready
> is yours to do; the plans just mean the research is already done.

## Ideas

* game setup no longer needs the manual "Sailing quest" On/Off toggle, nor the manual Stage 1B quest-points stepper — when a quest is picked from the catalog we already know both (`stages[0].cards[0].sailing` and `.questPoints`). Keep the manual path only for the custom/no-catalog game, which is what `setup_game` is really for.
* Choose an appropriate license, fully open source but with care regarding the copyrighted IP
* Contributing.md and section on the README
* Game log data should be logged with full timestamp, log view should at least show the basic date and time with each entry. Logs should be latest at the bottom, like a terminal, need ability to scroll up and down and jump to oldest / latest (4 buttons on right side of screen where a scrollbar would normally be expected)
* Feasibility report: could we add audio by taking advantage of the Qwiic port and something like this (with a small speaker(s)) https://www.adafruit.com/product/6258
	* daisy chain qwiic to add haptic feedback driver?
	* i've purchased a qwiic haptic driver as well as a  as well as a qwiic DAC+speaker component for audio (same makers as the Presto)
* action windows. interstitial screens for action windows. when you advance to the next phase, if there is an action window, you land on the action window view, which has a 3 second timer. when timer reaches 0, automatic movement to the next phase. "perform actions" button dismisses the timer. tip explains action window rules. allows adjusting players/progress zones, which get recorded as having been done in the action window. Next phase primary call to action button. this is a setting that can be disabled, which reverts to the action window toast reminder instead of the interstitial view.
* long term: campaign mode tracking, long term historical game results, stats, sharing
* feasibility report: how could a basic wireless camera be incorporated? low FPS / just occasional snapshots of the board state at the table. something easy to build with raspberry pi / xioa camera, battery just adequate for a single game session. 3d printed enclosure with 1/4-20 mount for gorillapod or similar. communicates with the presto / web app over wifi, images saved.
* RingsDB integration - specify which deck each player is using
* full Github actions CI with playwright integration tests for all UI/UX functionality. Automatic PR coverage report with screenshots of failing issues... at least one of my private GH projects implement this
* **Quest Setup copy is wrong on any B side** (follow-up, after the Progress overhaul). Reported as *"Stage 2B has no Setup instructions. Then flip the card to its Stage 2B side."* Diagnosed in `ui/screen_play.py::_draw_quest_setup` (and its JS twin) — three separate defects:
	* **The flip line is only correct on an A side.** `QUEST_SETUP["then_flip"] % game.quest["stage_n"]` always appends `B`, so on a B side it tells you to flip to the side you are already on.
	* **It reads the A face while labelling the current side.** `a_face` is always side A, but `stage_n` is `"%d%s" % (stage_n, side)`. On stage 2B it reports the *A* face's text under a "Stage 2B" heading.
	* **"No Setup instructions" is inferred from the presence of any text at all**, on the A face only — so a card whose A face is blank and whose B face carries the real rules reads as "nothing to do". **75 stage cards in the catalog have no A-side text but real B-side text** (The Hunt for Gollum 2 and 3, Battle of Lake-town 2 and 3, Escape from Dol Guldur 2, ...), which is exactly the reported case.
	* Also worth checking **why this view is reachable at stage 2 at all** — it is documented as the R0 pre-round-1 screen.
	* Rewrite the framework instruction to say what the RR actually requires when a quest card is revealed (When Revealed effects, Surge/Doomed keywords, Forced abilities), not just whether the word "Setup" appears. Verify against the RR before writing, per iron rule 4.

## Ready

- [ ] Reconcile the 18 location faces whose X is defined nowhere we can read
  - notes: cross-referencing the quest cards does NOT work — only 6 of 16 official ones have any `X is` on a stage, and most are a different X (*The Argonath*'s is an enemy's threat, *Wall of Trees*'s is the stage's quest points, *Battering Ram*'s is the damage it deals). One defensible: *Plains of Rohan* = the pursuit value.
  - so: needs an outside source. Hall of Beorn carries printed per-card stats and `tools/build_hob_enrichment.py` already exists, but its cache holds Quest cards only — this is a fresh ~18-card fetch. Until then the sheet correctly shows an empty slot and the player sets it.
  - do NOT guess these. Iron rule 4; a plausible-looking formula is exactly the failure mode.

- [ ] ALeP X states are still unverified
  - notes: 8 of the distilled location formulas are on ALeP cards, absent from the official TSV, so their X-vs-`-`-vs-blank state was never checked against a source. `build_card_data.py` now merges ALeP with markers, so the check is possible — re-run the marker gate against the ALeP branch TSVs specifically.

## In Progress
* Notes for in progress overhaul of location/quest "progress":
	* [these four are UNADDRESSED — the plan below shipped first. They are
	  feedback on exactly that screen, so they are the obvious next round.]
	* the "chevron" on the Progress screen items:
		* "2 QP >" is not useful on a row that already has the quest points displayed... the value's denominator should be labeled as "qp" (or "quest points" below the numbers, between the controls
		* location icon is dumb, find something better
	* when a location is sent back to staging with progress on it, we should track the list of known locations in the staging area and when choosing a location (during travel or replacement, etc) we can offer those known locations with their previous progress values
	* Still need to possibly refine the "Flip to side B" part of the quest flow... not sure if that is really needed... because you resolve the setup and part of that is flipping to side B... so it feels awkward as-is

## Blocked

## Done

- [x] Progress view — realize the proposed flow (T0–T9)
  - notes: plan at `~/.claude/plans/silly-swimming-map.md`. Both twins:
    `active_location` becomes a LIST of seats (RR allows one; five printed
    cards override it), shared row widgets, the redesigned Progress screen
    (sections, chain-aware pagination, compact rows, RESOLVE header, History
    with stage rules), row detail sheets with named actions and live edits,
    and the stage row driven by points / condition / formula.
  - also fixed on the way: a manual location never stored the threat it took
    out of staging, the web location picker threw on every draw, "Replaced"
    always replaced seat 0, and pre-list replay deltas silently no-op'd undo.
  - done: 8cd2727..2d4e401 (12 commits). 1986 tests green, both twins verified
    byte-identical, and a pre-migration save resumed in the real app.

- [x] The count control for a dynamic X
  - notes: the original plan was a 5-rule regex grammar over the distilled sentence, parsed at build time. User called it: put an **enum** in the card data and code one formula per distinct target instead. The 43 distinct sentences collapse to **26 targets** — most of the difference is phrasing ("characters controlled by the first player" vs "characters the first player controls"; "1 more than" vs "1 plus"). Arithmetic is two integers, `value = mul * count + add`, which covers every observed shape.
  - notes(cont): `xtargets.py` holds the table (label + whether a tracked value answers it), host- and device-safe like phases.py; the table is generated into `docs/js/xtargets.js`, the arithmetic hand-mirrored. Three targets are `auto` — players, main-quest stage, highest threat — and `resolve()` ignores any stored count for those so "X is 4 per player" can't be overridden by a stale one.
  - shipped: the threat row takes four shapes (auto / count / bare / plain). The count stepper is labelled by **what it counts**, and the app does the arithmetic — the player answers "how many enemies are in play?" and never adds the +1 themselves. Saving stores the COUNT, so it doesn't go stale when the board changes.
  - done: bccdb4b, 4817ccc. 1891 tests green. The layout linter caught a real collision in the new tallest-case scene (DISPLAY value's descender vs the formula's first line) — iron rule 3 earning its keep.

- [x] Tell printed X, "-" and 0 apart, and stop drawing targets that don't exist
  - notes: `parse_int` flattened four different printed values into one `None` — a number, a literal `X`, a `-` meaning the stat does not apply, and absent. So a stage printing X read as worth 0, and a location printing X read the same as one with no such stat. Sibling `threatKind` / `questPointsKind` markers ("x" | "na") now carry the difference. Verified against the pinned TSV: 131 quest stages print `-`, 7 print X; 52 location faces print X for threat, 10 for quest points.
  - notes(cont): two committed distillations, both our own words, generated once by a one-agent-per-card LLM extraction reading only each card's printed text — `advancement_distilled.json` (153 of 177 zero-point stages carry a condition; 148 `advance`, 14 `lose`, 11 state both) and `location_dynamic_distilled.json` (40 of 58 X-printing faces define X on the card). `tools/build_advancement.py` validates rather than generates: every field must be GROUNDED, i.e. each proper noun and trigger keyword must appear in that card's own printed text. It doubles as the drift alarm when the card-DB pin moves.
  - notes(cont): gating on the marker instead of `value is None` caught three fabricated formulas already in the artifact — a quest-point formula on The Mere of Dead Faces (prints `-`), a threat formula on Great Corsair Ship (prints 0), and both fields of Rider of Mirkwood (`type=Enemy`, filed under `encounter.location`).
  - shipped: the Progress row drops the phantom Target stepper for a condition stage; the quest sheet shows the card's own sentence instead; the location sheet — previously **dead code nothing constructed** — is reachable from the Location row and now carries Progress, Quest points and Threat, saving onto the record rather than over it (it used to drop the name, threat and markers).
  - done: a48a0b0, fa6d658, 80b1861, 646c1db, 91dd314 (unsigned, unpushed). 1815 host tests green, six new layout-linter scenes, both twins verified byte-identical under node and the full tap-to-save round trip walked in the browser.

- [x] Back button — delta replay at DragnCards parity
  - notes: `docs/superpowers/plans/2026-07-26-delta-replay-parity.md`. Bidirectional structural diff, `replay_step` cursor, jump-to-any-point retcon, round-granularity stepping. Bottom nav bar replaces the full-width CTA; Log screen gains the transport. Both twins, 1136 tests green.
  - notes: found and fixed two bugs — history navigation was being recorded as an action (browser-only, no test caught it), and a pre-existing `setup_game` overflow (y=412 vs CTA at 410) that the nav rule exposed; layout linter gained rule L5 to guard the class.
  - done: aa34862 (flashed to the Presto 2026-07-26 — full firmware, since the device predated M4 and a partial copy would not boot)

- [x] Data-driven location picker
  - notes: plan `docs/superpowers/plans/2026-07-25-location-picker.md` (status: done, records how the three open questions were answered). Travel and "+ Add location" used to guess 3 quest points / 2 threat; both now pick from the scenario's own cards, with the printed quest points AND threat filled in from the card. Needs a union across `includedSets` — a scenario's own file only holds its own encounter set, so Passage's own file has 2 of its 6 locations.
  - notes(cont): flat list + pager (median 5, max 14, only 10 scenarios exceed one page); Manual is the old stepper and stays load-bearing (3 of 154 quest scenarios gather no locations). 1019 host tests green, six new scenes through the layout linter, both twins verified in lockstep, full browser walkthrough.
  - done: 3b23a2a

- [x] Commit derived enrichment instead of fetching it in CI
  - done: merged to main 2026-07-25 (enrichment.json + tips.json now tracked; HoB/tips fetch steps dropped from CI)
  - notes: the Pages deploy went from ~30s to 9min+ once `main` gained the Hall of Beorn sets-to-gather step, because a cold run fetches ~123 scenarios at ~20s each (40+ min worst case). It's `continue-on-error` so it can't fail the deploy, and `actions/cache` covers warm runs, but a cold cache is painful.
  - policy (user, 2026-07-25): **derived insights, summaries and aggregated metadata from HoB / Vision of the Palantir CAN be committed** — they are not verbatim copies. Verbatim card text stays generated-only.
  - so: un-gitignore `tools/data/enrichment.json` (aggregated set lists) and `docs/data/tips.json` (our own summaries), commit them, and drop the fetch step from CI — the build just merges what's already in the repo. Keep `tools/data/hob_cache/` (raw third-party responses) ignored.
  - also revisit: `docs/data/` is currently ignored wholesale, which sweeps up tips.json; that needs splitting so the verbatim card DB stays generated but derived files can live in git.

- [x] **M4 · Quest awareness** — full DragnCards card-data pipeline (generated-only, gitignored) + the Setup-phase quest picker (Scenario Source → Pick Cycle → Choose Scenario → Scenario Options → Quest Setup R0 view → flip to side B → round 1), quest-card modal, player side-quest picker, set/scenario icons, Hall-of-Beorn sets-to-gather + release dates, and per-stage tips
  - notes: spec `docs/superpowers/specs/2026-07-24-card-data-pipeline-design.md` + `...-quest-picker-bcore-design.md`; plans for each piece under `docs/superpowers/plans/`. Picking Passage preloads 8 / 2 / {0,10} and lists its three sets with icons. ~594 host tests green; every flow verified in the browser.
  - notes(cont): **B-resolve** also shipped — guided resolution walks location→explore→overflow→quest→advance (reveal side A, flip to side B), incl. branch choice and player-confirmed advance for conditional stages. 660 host tests green.
  - done: on `feat/quest-picker` (local, **unsigned** commits — sign before pushing)
  - follow-ups: ~~deploy `docs/data/` + firmware to the Presto and soak~~ done 2026-07-26 (full firmware + 6.4 MB / 508-file card data; 398 scenarios, 251 icons, 122 tip sets on device; 120s soak clean). Still open: push + Pages deploy; per-quest threat warnings + chase track unplanned
- [x] **Stats redesign** — two flipped compact zones (Players matrix + Progress zone), circular arc/token primitives, Players + Progress detail views, DONE header convention, staging inline ±, `commit_touched` + `quest_history`
  - notes: spec [[stats-redesign]], plan `design/stats-redesign-plan.md`; web-first + firmware lockstep; 378 host tests green; verified device-faithful via `tools/preview.py`
  - done: squash-merged to `main` locally (one commit)
  - follow-ups: push to remote → GitHub Pages deploy. ~~deploy to Presto~~ done 2026-07-26
- [x] Dream-chaser Sailing support + stage-completion flow + game-end transition
  - notes: heading on/off-course, wheel + weather glyphs, stage-complete + game-over screens; `SailingModal` is the sailing-test flow (reached from the quest_sailing view)
  - done: web 2e97817; firmware ported (parity work)
- [x] Trim encounter reminders to Archery + Battle/Siege
  - notes: dropped "Discard shadow cards" + "Time counters" (Lost Realm+ mechanic, not in pool)
  - done: web 5cb1608; firmware ported (parity work)
- [x] About page: settings tile + boot disclaimers link + "made with love @andrhamm" credits
  - done: web 5cb1608; firmware `ui/screen_about.py` (parity work)
- [x] Crop boxart source to 480x480; purge unused assets; gitignore icon packs (keep local)
  - done: d83b997
- [x] M1 firmware: guided round, threat/quest tracking, log, LEDs
  - done: shipped to device, 266 host tests
- [x] Web digital twin + GitHub Pages + README
  - done: https://andrhamm.com/lotr-lcg-presto-hud/

%%
Card format (one card = one deliverable):

- [ ] Short imperative title
  - notes: optional context, links, files
  - claim: <worker-id> <date>          (added when work starts)
  - blocked: <concrete reason>         (only while in Blocked)
  - done: <commit sha / URL>           (added when moved to Done)
%%
