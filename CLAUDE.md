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
3b. **Follow the design system**
   (`docs/superpowers/specs/2026-07-25-design-system.md`) — the type scale,
   colour roles, element vocabulary and copy rules, each with the test that
   enforces it. The one that keeps getting broken: **if a player reads it as
   a sentence, a name, or an option, it is `BODY` (scale 2)**. Running out of
   room is never a reason to shrink text — say less, page it, truncate it
   with a `[...] more` affordance, or re-lay out. `LABEL` (scale 1) is
   ALL-CAPS chrome and dense tabular metadata only. Use the names from
   `ui/theme.py` / `docs/js/ui.js`, never a bare integer.
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
- **Easy mode is general, and it is TWO steps.** *Learn to Play* p.28 "Modes of
  Play" (and the 2013 *Easy Mode Rules* p.1): **1.** add one resource to each
  hero's resource pool; **2.** remove any card from the encounter deck that has
  **a gold border surrounding its encounter set icon**. It applies to any
  scenario. Two things to get right: FFG calls that marker the **"difficulty"
  indicator** (not a "gold ring" — use their wording), and it marks **individual
  copies, not card titles** (FFG's own list removes 2 of the 3 *Gladden Fields*),
  so never treat "marked" as a property of a name. Scenarios before 2013 have no
  printed marker and need the Guide's lookup list, which was never extended past
  2013.
- **Nightmare is a swap, not a substitution.** Per the printed Nightmare Setup
  card: begin with the standard encounter deck, **remove the listed cards in the
  listed quantities**, "then, shuffle the encounter cards in this Nightmare Deck
  into the remainder". Do not describe it as replacing the deck.
- **Easy + Nightmare is unaddressed by the rules** — the Rules Reference v1.0
  contains no occurrence of "mode" at all, and the FAQ says nothing. Neither
  permits nor forbids it. For at least one scenario the two setups are literally
  incompatible: *Passage Through Mirkwood* has exactly 2 *Caught in a Web*, and
  Easy mode and the Nightmare setup card each instruct removing 2. The UI folds
  Nightmare into the single Difficulty ladder, so the pair can't be selected.
- **DragnCards' Nightmare setup text is often a platform artifact.** 39 of 72
  Nightmare setup cards carry an identical placeholder ("The Quest Deck has been
  modified for Nightmare Mode. Flip this card over…") that is **not** printed on
  the card — DragnCards pre-builds the deck, so it skips the instructions. Never
  surface that string as card text.
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

`tools/alep.py` adds the fan-made **A Long Extended Party** packs to that same
build (~23 pickable scenarios, `source: "alep"` — the Scenario Source screen's
Community option, which the UI has always had and which had no data until
now). ALeP is **not** on the branch the card DB pins: upstream keeps official
cards on `main`'s single `tsvs/cardDb.tsv` and ALeP on the repo's separate
**`alep` branch** as ~31 UUID-named per-pack TSVs, merged at deploy by the
repo's own `merge_alep.sh`. Same pinned-upstream pattern as everything else —
`tools/data/alep.SOURCE.txt` holds the branch sha **plus the TSV file list**,
so an ordinary build is deterministic and makes no GitHub API call;
`--refresh` re-resolves both. `--no-alep` builds official cards only.

Three things that pass are load-bearing, all verified against the data (see
the module docstring, which cites each):

- **Errata are applied, not shipped as a pack.** `ALeP - Errata Pack` holds
  corrected reprints of cards that already exist elsewhere; surfacing it would
  invent three phantom scenarios. The join key is
  `(name, encounterSet, side, traits)` — `databaseId` does NOT work (every
  erratum gets a fresh id), and **`traits` is required**: `Eastern Assault` is
  a `multi_sided` card whose two faces are the Normal./Easy. difficulty
  variants with an *empty* `side`, so without it the Easy face overwrites the
  Normal one. `type=="Rules"` errata are dropped (multi-page inserts repeat a
  name, so the key is ambiguous by construction).
- **ALeP Nightmare decks are named `"<Scenario> Nightmare"`**, without the
  `" - "` the official ones use, so the picker's name rule misses them and
  they'd otherwise appear as pickable quests. `alep.is_nightmare_pack()`
  marks them from the pack name instead.
- **`hasNightmare` is same-source only.** `slugify` maps ALeP's
  "The Withered Heath Nightmare" onto the identical slug the official
  "The Withered Heath - Nightmare" would have, so without the source check an
  official scenario advertises a Nightmare mode that silently loads community
  cards.

ALeP is **all-or-nothing and never fatal**: any failure (bad pin, network,
partial fetch) drops it entirely with a printed warning and the build emits
the official catalog, rather than failing CI or — worse — emitting a half
catalog whose picker offers scenarios whose cards never arrived. Cycle names
and order come from the plugin's own `jsons/zz-ALeP---*.menu.json`, mirrored
into `CYCLE_ORDER` in **both** `quest_catalog.py` and
`docs/js/quest_catalog.js`.

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

`tools/build_tips.py` writes per-scenario **strategy** tips to
`docs/data/tips.json` — **committed**, the single `!docs/data/tips.json`
allow-list line in `.gitignore`. It compiles two committed local inputs and
**never touches the network**:

1. **`tools/data/tips_distilled.json`** (committed, primary) — 122 scenarios,
   ~970 tips written by this project after *reading* the Vision of the
   Palantir quest spotlights, with every factual claim re-checked against the
   compiled card data. Carries `general` plus per-stage `stages`.
2. **`quests/*.md` callouts** — used **only** where the distillation is
   silent.

That precedence is deliberate and is the reverse of the original design.
Notes used to win outright, which is why tips.json once shipped stat lines
("Hummerhorns engage at 40 → …") instead of advice: those notes are reference
tables meant to be read beside the cards, not things to act on mid-game.

**Two gates, and they are not interchangeable.** `is_useful_tip()` still
guards the `quests/*.md` path — it is tuned for text *extracted* from prose
and rejects dangling fragments, unresolved pronouns and filler.
`is_valid_distilled_tip()` guards the distillation, because running the old
gate over authored tips rejected ~1/3 of an already-fact-checked corpus for
reasons that only make sense for scraped fragments: `_DANGLING_TRAILERS`
rejects a complete sentence ending "…take the extra encounter card instead.",
and `_PROPER_NOUN` cannot see a card name that *starts* the tip
("Counter-spell can cancel your event."). The distilled gate keeps length, a
real sentence, min-words and the no-talking-about-the-app rule, and swaps the
blanket pronoun ban for `_has_antecedent()` — anaphora is fine when a name
precedes it in the same tip ("Caradhras cannot be travelled to, so pre-load
**it**"), dangling when nothing does ("**It** goes Underwater every quest
phase").

The article corpus the distillation was written from lives in
`research/votp/` (vault-side, **gitignored**, built by
`tools/build_votp_corpus.py` — see below); the fetched HTML in
`tools/data/tips_cache/` is verbatim third-party content and also stays
gitignored. Only our own words are committed.

**Nothing fetches this in CI, and a plain run fetches nothing.** With
`tips.json` present, `python3 tools/build_tips.py` prints a one-line no-op and
exits 0; `--refresh` regenerates it from the two local inputs (then commit the
result). `QuestCardModal` loads it via `quest_catalog.load_tips()`
/ `docs/js/quest_catalog.js`'s `loadTips()` and enables its Tips button only
where `tips_for()`/`tipsFor()` finds something — an absent or corrupt
`tips.json` just leaves the button in its disabled state. A device deploy needs
no extra step: the committed file rides along with
`mpremote cp -r docs/data/ :/data/`.

`tools/build_votp_corpus.py` turns the cached Vision of the Palantir article
HTML into readable markdown in `research/votp/` — the research corpus the
distillation is written from. **Gitignored**: it is verbatim article prose, so
it never ships and is never committed; it lives vault-side (the repo root is
an Obsidian vault) so it can be read in Obsidian next to `quests/` and
`design/`. Extraction is narrowed by CSS selector to WordPress's single
`div.entry-content` per page — which excludes header, nav, sidebar, comments
and footer — located with a balanced-depth `HTMLParser` (a regex would
truncate at the first nested `</div>`), then converted with `pandoc -f html -t
gfm`. No new Python dependencies. `--fetch-extras` fetches an audited manifest
of articles the plain slug match can't reach: **second-edition rewrites**
(VotP redid the early cycles from 2020 on with a much fuller template, and the
plain slug still points at the thin 2018 original), **slug fixes** (VotP
prefixes a definite article the catalog omits; the Core Set's scenario 2 is
titled after its *encounter set*), and background reading. Every entry is an
observed URL, not a guess — and check what you match: `the-crossings-of-poros-2`
is a Quest-of-the-Week *results* post, not a spotlight.

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
