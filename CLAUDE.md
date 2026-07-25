# LOTR LCG Presto HUD — working notes for Claude

Touchscreen companion HUD for *LOTR: The Card Game*. Two synchronized
implementations:

- **Firmware** (MicroPython, Pimoroni Presto): `gamestate.py`, `phases.py`,
  `ui/`, `main.py`. Deploy with `mpremote` (device auto-runs `main.py`).
- **Web twin** (`docs/`, GitHub Pages: https://andrhamm.com/lotr-lcg-presto-hud/):
  ES-module mirror, same screens/protocol/metrics, localStorage persistence.

## Iron rules

1. **Web first, then firmware.** New features are built and verified in
   `docs/js/`, then ported to the Python. The two stay in lockstep —
   a change that lands in one and not the other is unfinished work.
2. `tools/gen_web_data.py` regenerates shared data (turn sequence, icon
   masks, font metrics) whenever `phases.py`, `ui/icons.py`, or the metrics
   change. Never hand-edit `docs/js/{phases,icons,metrics}.js`.
3. `python3 -m pytest tests/` must stay green (includes the layout linter
   over every screen scene). Add scenes for new screens/modals.
4. **Never ship an unverified rules claim.** Every statement the UI makes
   about how the game works — tip copy, button labels, captions, anything a
   player could act on — must be checked before it ships. This rule has been
   broken before and it shipped wrong advice to the screen, so treat it as
   hard:

   **Check in this order, and stop at the first source that answers it:**
   1. **The compiled card data** (`docs/data/`) — it already knows which
      scenarios print which cards, every stage's quest points, every card's
      printed text. Query it before generalizing about "some quests" or
      "a few scenarios"; the answer is usually one `python3 -c` away.
   2. **The rulebook** (`pdftotext` the PDF) and the FAQ.
   3. **This repo's own notes** (`quests/*.md`) — already summarized, already
      checked, and the house voice to match.

   **Then:**
   - **Prefer the card's own printed text over a paraphrase.** If a mode or
     stage has real text in the catalog, show that. A paraphrase is a chance
     to be subtly wrong.
   - **Never generalize what the data can tell you exactly.** "Only a few
     quests ship a Hard Mode card" was wrong-by-vagueness: exactly one of 349
     does, and the catalog says so. If a feature applies to some scenarios,
     gate it on the data, don't hedge in the copy.
   - **Placeholder rules text is not allowed to ship.** If you cannot verify a
     claim, do not write it and flag it later — either leave the element out,
     or surface the uncertainty to the user *before* it lands. "Author-supplied,
     flagged for review" is how wrong copy reaches the screen.
   - **Cite the source** in the commit body or a code comment, so the next
     person can re-check it without redoing the research.

## Verified game mechanics (checked — don't re-derive or contradict)

Facts already confirmed against the rulebook or the compiled catalog. Cite
these rather than re-researching; correct them only with a better citation.

- **Quest cards are two-sided.** Side A is story/setup; you resolve it, then
  **flip to side B**, which carries the quest points. This flip happens at
  **every** stage advance, and stage 1A→1B happens **before round 1**
  (rulebook setup step 7).
- **Quest overflow does NOT carry forward.** Excess progress beyond a stage's
  quest points is discarded on advance, not applied to the next stage
  (p.22). Location overflow *does* flow on to the quest card (p.15).
- **Progress order:** active location first → explored/discarded at its quest
  points → remainder to the quest card.
- **"Victory X" is a scoring keyword**, not an alternate win condition (p.24).
  Never treat a card's `victory` field as an auto-win trigger.
- **Easy mode is general:** remove every encounter card whose set icon carries
  the gold difficulty ring. It applies to any scenario.
- **Hard / Epic Multiplayer are NOT general difficulties** — they are printed
  Mode cards that only a few scenarios ship (exactly 1 of 349 prints Hard;
  3 print Epic Multiplayer). Gate them on the catalog's per-scenario `modes`.
- **Nightmare** is a separately sold encounter deck per scenario, not a
  difficulty toggle.
- **~137 of ~400 stage cards have 0 quest points** — they advance by a
  condition (defeat/explore/objective), not by placing progress.
- **Side quests are not a Core Set mechanic**; the rulebook says nothing about
  excess progress on one. Don't assert a rule there.

## Card data (generated, never committed)

`tools/build_card_data.py` compiles the full DragnCards card DB into
`docs/data/` (index + per-scenario + player DB + rules). The source of truth is
the pinned TSV (`tools/data/cardDb.SOURCE.txt`); the output is **gitignored** and
regenerated — never hand-edit `docs/data/`. Refresh the pin with
`python3 tools/build_card_data.py --refresh`. Web Pages builds it in CI
(`.github/workflows/pages.yml`); the device gets it at deploy:
`python3 tools/build_card_data.py && mpremote cp -r docs/data/ :/data/`.

`tools/build_icons.py` rasterizes the community SVG icon pack (encounter-set
+ expansion-symbol symbols) into `docs/data/icons.json` (24×24 1-bit masks,
same gitignored/regenerated posture as the rest of `docs/data/` — never
hand-edit). Same pinned-upstream pattern as the card data: the source of
truth is `tools/data/icons.SOURCE.txt` (pack repo `KevBelisle/lotr-lcg-assets`
+ commit sha); a normal run downloads that commit's tarball and reads the
SVGs straight out of it in memory (never extracted to disk — the pack also
ships fonts/product images we don't want). Refresh the pin with
`python3 tools/build_icons.py --refresh`. `--assets <path>` overrides with a
local directory instead of fetching (useful offline); either source degrades
gracefully to an empty `icons.json` (missing local dir) or a friendly
`SystemExit` (fetch/rasterize failure) rather than a crash — icon slots just
fall back to their placeholder glyph. Rasterizing needs Pillow plus either
`cairosvg` or the `rsvg-convert` CLI. Runs alongside `build_card_data.py` in
both delivery paths: CI builds it in `.github/workflows/pages.yml` (marked
`continue-on-error` — icons are optional, card data is the critical
artifact); the device gets it at deploy via
`python3 tools/build_icons.py && mpremote cp -r docs/data/ :/data/`.

`tools/build_hob_enrichment.py` fetches Hall of Beorn's per-scenario "sets to
gather" data (every encounter set a quest draws from, not just its own —
`Export/Search?EncounterSet=<name>&CardType=Quest`) into
`tools/data/enrichment.json`, cached per-scenario under
`tools/data/hob_cache/<slug>.json` — both **gitignored**, same posture as
`docs/data/`. `build_card_data.py` merges it automatically when present
(`includedSets` on each scenario, `gatherCount` on its index entry) — absent
or corrupt enrichment is silently skipped, never a build failure. The
endpoint is slow (~20s/request) and third-party, so the fetcher is polite —
strictly serial with a small delay, and a warm cache skips the network call
entirely — but a *cold* run over the full catalog takes 40+ minutes; run
`--limit N` first for a quick smoke check. Order matters: the enrichment
fetcher reads scenario names out of `docs/data/index.json`, so
`build_card_data.py` must run once *before* it and once *after* (to merge)
— `python3 tools/build_card_data.py && python3 tools/build_hob_enrichment.py
&& python3 tools/build_card_data.py`. CI does exactly this in
`.github/workflows/pages.yml`, with the cache step persisted via
`actions/cache` across runs (marked `continue-on-error`, same reasoning as
icons); for a device deploy, run that same three-command sequence before
`mpremote cp -r docs/data/ :/data/` if you want the gather list on-device —
the plain `build_card_data.py`-only one-liner above still works fine without
it, just without a merged gather list.

`tools/build_tips.py` fetches per-scenario strategy tips from Vision of the
Palantir (the site `quests/*.md` already cites) into `docs/data/tips.json` —
gitignored, same posture as the rest of `docs/data/`. It resolves a catalog
slug to a VotP article via the site's `sitemap.xml` (cached under
`tools/data/tips_cache/`, also **gitignored**), then **summarizes, never
reproduces**: only sentences a small set of fact-pattern rules can restate in
fixed original phrasing become tips (≤140 chars, ≤4/scenario), everything
else is dropped — see the module docstring's "Verified facts" and Copyright
posture for the robots.txt check and the summarization approach. Politeness
mirrors `build_hob_enrichment.py`: strictly serial with a delay, cache-first.
`QuestCardModal` loads it via `quest_catalog.load_tips()` /
`docs/js/quest_catalog.js`'s `loadTips()` and enables its Tips button only
where `tips_for()`/`tipsFor()` finds something — absent/corrupt/not-yet-built
`tips.json` just leaves the button in its disabled state. CI builds it in
`.github/workflows/pages.yml` (`continue-on-error` — tips are optional, card
data is the critical artifact); for a device deploy, run
`python3 tools/build_tips.py && mpremote cp -r docs/data/ :/data/` if you want
tips on-device, or skip it — everything else still works without a
`tips.json`.

## The TODO board (TODO.md)

`TODO.md` is an Obsidian Kanban board (also plain markdown). Columns:
**Ideas** (user inbox — never work these directly), **Ready** (groomed,
workable), **In Progress**, **Blocked**, **Done**.

Card protocol — a card is one deliverable, moved between columns by editing
the file:

```
- [ ] Short imperative title
  - notes: context, links
  - claim: <worker-id> <date>      when work starts (move to In Progress)
  - blocked: <concrete reason>     when stuck (move to Blocked)
  - done: <commit sha>             when finished (move to Done, tick box)
```

- Grooming Ideas → Ready needs the user (scope/priority is theirs); only
  suggest, don't promote silently.
- One card per worker at a time. Claim before working; unclaim (remove
  claim line) if abandoning.
- A card leaving In Progress goes to exactly one of Done or Blocked —
  never silently back to Ready.

## Background workers

When the main session is idle — waiting on user input, or waiting on
long-running background agents/builds — pick up **Ready** cards with
background workers as time allows:

- Spawn via the Agent tool with `isolation: "worktree"` so workers never
  collide with the main session's tree. One card per agent, the card text
  is the task brief.
- Workers follow the iron rules (web first, tests green, regenerate shared
  data) and commit in their worktree; the main session merges/pushes and
  moves the card to Done with the commit sha.
- Do not deploy to the Presto from workers — device deploys happen only in
  the main session (serial port is single-user, and the user may be mid-game).
- On any worker failure or open question, move the card to Blocked with a
  concrete `blocked:` reason. Never leave a card claimed-but-idle.

**Surface blockers:** whenever ending a turn to the user, if Blocked is
non-empty, list those cards and their reasons in one short line each.

## Device access (main session only)

- Port: `/dev/cu.usbmodem*` via `mpremote`. Stop any running tethered
  session before copying files. The port drops occasionally — if it
  vanishes, the device still runs standalone from flash; ask the user to
  replug rather than retrying blind.
- After deploying, relaunch `main.py` in a background Bash task and check
  its output file for tracebacks before declaring success.
