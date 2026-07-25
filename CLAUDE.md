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

## What may be committed (data policy)

Decided by the user, 2026-07-25. The line is **verbatim vs derived**, not
"third-party vs ours":

- **Never committed — verbatim third-party content.** The compiled card
  database (`docs/data/` card text, names, stats) and raw API/HTML caches
  (`tools/data/hob_cache/`, `tools/data/tips_cache/`). These are regenerated
  from pinned sources and exist only in build artifacts (the Pages site, the
  device flash).
- **Fine to commit — derived insight and aggregated metadata.** Summaries we
  wrote ourselves (stage tips), and facts we aggregated across sources (which
  encounter sets a scenario draws from, release dates, cycle groupings). A set
  list or a one-line tip in our own words is not a copy of anyone's work.

Practical consequence: prefer committing derived data over re-fetching it at
build time. A slow third-party fetch in CI (see the Hall of Beorn enrichment)
is a smell — commit the derived output and let the build merge it.

## Card data (generated — except two committed derived files)

`docs/data/` is a **mixed** directory, and `.gitignore` says so explicitly: a
blanket `docs/data/*` ignore (the verbatim compiled card DB) plus a one-line
allow-list, `!docs/data/tips.json` (our own summaries). `tools/data/` splits the
same way — `enrichment.json` (aggregated set names) is **committed**, the raw
`hob_cache/` and `tips_cache/` responses are not. The rule behind both is the
data policy above: verbatim vs derived, not third-party vs ours.

**Committed, so CI never fetches them:** `tools/data/enrichment.json` and
`docs/data/tips.json`. Both fetchers are a **no-op when their output already
exists** (shared guard: `build_card_data.needs_refresh()`); regenerating is an
explicit local act with `--refresh`, never something a build does. This is
deliberate — the Hall of Beorn fetch used to run in CI and pushed the Pages
deploy from ~30s to 9min+, worst case 40+ minutes cold.

**Generated, never committed:** the compiled card DB (`index.json`,
`scenarios/`, `players/`, `rules.json`) and `icons.json`.

`tools/build_card_data.py` compiles the full DragnCards card DB into
`docs/data/` (index + per-scenario + player DB + rules). The source of truth is
the pinned TSV (`tools/data/cardDb.SOURCE.txt` — a URL + sha, tracked); the
output is **gitignored** and regenerated — never hand-edit `docs/data/`.
Refresh the pin with `python3 tools/build_card_data.py --refresh`. It also
merges the committed `tools/data/enrichment.json` in the same pass (absent or
corrupt enrichment is silently skipped, never a build failure). Web Pages
builds it in CI (`.github/workflows/pages.yml` — one pass, no fetch steps); the
device gets it at deploy:
`python3 tools/build_card_data.py && mpremote cp -r docs/data/ :/data/`.

`tools/build_icons.py` rasterizes the community SVG icon pack (encounter-set
+ expansion-symbol symbols) into `docs/data/icons.json` (24×24 1-bit masks,
same gitignored/regenerated posture as the compiled card DB — never
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
`tools/data/enrichment.json` — **committed**: it holds only a sorted list of
encounter-set *names* per scenario, aggregated metadata with no printed card
text. The raw per-scenario responses it aggregates (`tools/data/hob_cache/
<slug>.json`) are verbatim third-party card data and stay **gitignored**.
`build_card_data.py` merges the committed file automatically (`includedSets`
on each scenario, `gatherCount` on its index entry) — absent or corrupt
enrichment is silently skipped, never a build failure.

**Nothing fetches this in CI, and a plain run fetches nothing.** With
`enrichment.json` present, `python3 tools/build_hob_enrichment.py` prints a
one-line no-op and exits 0. To actually regenerate: `python3
tools/build_card_data.py && python3 tools/build_hob_enrichment.py --refresh &&
python3 tools/build_card_data.py` — two card-data passes because the fetcher
reads scenario names out of `docs/data/index.json` and the merge is the second
pass. Then commit the new `enrichment.json`. The endpoint is slow
(~20s/request) and third-party, so the fetcher is polite — strictly serial
with a small delay, warm cache skips the network entirely — but a cold run
over the full catalog takes 40+ minutes; `--limit N` first for a smoke check.
A device deploy needs none of this: `docs/data/` gets the gather list from the
plain `build_card_data.py` one-liner above, since the enrichment is in the
checkout.

`tools/build_tips.py` writes per-scenario strategy tips to `docs/data/tips.json`
— **committed**, the single `!docs/data/tips.json` allow-list line in
`.gitignore`. Everything in it is text this project wrote itself: tips come
either from our own `quests/*.md` callouts or from a Vision of the Palantir
article (the site `quests/*.md` already cites) run through a **summarize,
never reproduce** pipeline — only sentences a small set of fact-pattern rules
can restate in fixed original phrasing survive (≤140 chars, ≤4/scenario), with
a mechanical `_too_verbatim` guard on top; everything else is dropped. See the
module docstring's "Verified facts" and Copyright posture for the robots.txt
check and the approach. The fetched article HTML (`tools/data/tips_cache/`) is
verbatim third-party content and stays **gitignored**. In practice the gate is
strict enough that *nothing scraped currently survives it*: as committed, every
tip in `tips.json` comes from a `quests/*.md` callout we wrote, and the file's
own `source` string says so (it only credits the scrape when a scraped tip
actually made it in — same rule as `index.json`'s Hall of Beorn credit).

**Nothing fetches this in CI, and a plain run fetches nothing.** With
`tips.json` present, `python3 tools/build_tips.py` prints a one-line no-op and
exits 0; `--refresh` is the way to regenerate (then commit the result).
Politeness on a refresh mirrors `build_hob_enrichment.py`: strictly serial with
a delay, cache-first. `QuestCardModal` loads it via `quest_catalog.load_tips()`
/ `docs/js/quest_catalog.js`'s `loadTips()` and enables its Tips button only
where `tips_for()`/`tipsFor()` finds something — an absent or corrupt
`tips.json` just leaves the button in its disabled state. A device deploy needs
no extra step: the committed file rides along with
`mpremote cp -r docs/data/ :/data/`.

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
