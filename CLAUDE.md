# LOTR LCG Presto HUD — working notes for Claude

Touchscreen companion HUD for *LOTR: The Card Game*. Two synchronized
implementations:

- **Firmware** (MicroPython, Pimoroni Presto): `gamestate.py`, `phases.py`,
  `ui/`, `main.py`. Deploy with `mpremote` (device auto-runs `main.py`).
- **Web twin** (`docs/`): ES-module mirror, same screens/protocol/metrics,
  localStorage persistence. Two hosts, same layout — root (`docs/index.html`)
  is the tablet client, `/presto/` (`docs/presto/index.html`) is this web
  twin: **lotrlcg.app** (Cloudflare Pages) and the GitHub Pages mirror at
  https://andrhamm.com/lotr-lcg-presto-hud/.

## Iron rules

1. **Web first, then firmware.** New features are built and verified in
   `docs/js/`, then ported to the Python. The two stay in lockstep —
   a change that lands in one and not the other is unfinished work.
2. `tools/gen_web_data.py` regenerates shared data (turn sequence, icon
   masks, font metrics, play copy, printed-X targets) whenever `phases.py`,
   `ui/icons.py`, `viewcopy.py`, `xtargets.py`, or the metrics change. Never
   hand-edit `docs/js/{phases,icons,metrics,viewcopy,xtargets}.js` — all five
   carry a `GENERATED` header, and `tests/test_viewcopy.py` re-runs the
   generator and byte-compares.
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
   2. **The rulebooks** — 16 official FFG books (Rules Reference, Learn to
      Play, every saga/campaign/hero expansion) are parsed to markdown in
      `research/rules/` and indexed by qmd as **`lotr-lcg-rules`**, so this is
      a search, not a PDF hunt:
      `qmd query "when does archery damage resolve" -c lotr-lcg-rules`.
      Do **not** reach for `pdftotext` — the books are two-column and it
      shreds the prose. See `rules/README.md` for how to add a book. Then
      the FAQ.
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
- **Combat resolves player-major, not enemy-major.** Rules Reference **6.4a /
  6.5**: the active player (first player first) picks *one* eligible enemy they
  are engaged with and resolves its attack, repeating "until no eligible enemies
  remain for the active player", and only *then* does the next player in player
  order become active. So a player clears **all** their engaged enemies before
  play passes. Within a player, they **choose** the order freely — engagement
  cost does not order attacks.
- **Engagement cost orders two things, and only two.** Dealing shadow cards
  (**6.2**: in player order, and within one player's enemies "the enemy with the
  highest engagement cost first… next highest second, and so forth"), and
  engagement *checks* (**5.3**: the highest engagement cost that is ≤ the
  player's threat engages). It explicitly does **not** apply to optional
  engagement (**5.2**: "The enemy's engagement cost has no bearing on this
  procedure") or to attack order (6.4a).
- **Engagement checks are round-robin, not per-player-in-full.** **5.3**: first
  player checks, then each other player in order, then the first player makes a
  *second* check, and so on until no enemy in staging can engage anyone.

## The data client (`db.py` / `docs/js/db.js`)

**All data access goes through the client. Nothing else opens a file or calls
`fetch`/`localStorage`** — `tests/test_no_stray_io.py` enforces it by walking
the AST of every firmware module and grepping `docs/js/`. Before it existed,
I/O was split across `main.py` and `quest_catalog.py` with four ad-hoc closure
caches, and `load_player_side_quests()` was re-read **on every "+ Side quest"
tap** because no single place owned the question.

Three collections, because measurement says they are three different problems:
`catalog` (immutable, keyed random read), `session` (state + log + delta
journal, written every tap), `history` (finished games, appended once).

**The scenario bundle** — `db.bundle(slug)` loads every static datapoint a
scenario needs in one go and pins it for the game (~10 KB: detail record +
locations union + tips). After it returns there is **not a single catalog read
during play**. It replaces four inconsistent paths: the scenario dict held on a
screen *and* deep-copied into `game.stages`, locations read lazily on the first
Travel tap, all 122 scenarios' tips loaded to show one, and a re-read on resume.

**Caching is pinned, and the working set is kept small on purpose** — GC pause
scales with the *live* set (~70 ns/byte: 4 ms at 64 KB, **70 ms at 1 MB**), so
a small resident cache is a latency win, not just a memory one. Parsing
`index.json` alone used to hold ~263 KB.

**`quest_catalog.py` is the one allowed exception** to the no-I/O rule: it is
the catalog reader the client delegates to, and its pure functions are
separately host-tested.

**There is no swappable `Store` interface** — considered and cut. The bake-off
rejected every alternative engine (SQLite corrupts and hangs; TinyDB is ~40x
slower than files; btree's `open()` never returns), so nothing will be swapped;
and a get/put/append/scan lowest common denominator cannot express *truncate*,
*compact* or *delete*, which the session genuinely needs. The two real backends
are also structurally unlike: LittleFS appends natively, localStorage has no
append at all.

## Rendering: fill is linear, so never repaint what did not change

Measured on device: the framebuffer fills at **5.1 Mpx/s**, so cost tracks area
exactly — a full `clear()` is **45 ms**, a 48px token box is **2.4 ms**.
Presenting follows the same rule: `hw.update()` is **23.6 ms**, a
`partial_update` of that token box **1.8 ms**.

**Two per-pixel Python loops were most of the app's draw time.** Both are fixed;
do not reintroduce the pattern:

- `widgets.arc_runs` walked every pixel of the bounding box calling
  `math.sqrt` AND `math.atan2` per pixel — ~4,100 trig calls for one token.
  A full ring now uses integer scanline spans (comparing SQUARED distances, so
  it stays exact); a partial arc still needs the angle but only scans the
  annulus. `tests/test_widgets_arc.py` diffs it pixel-for-pixel against the
  original across 60 configurations — **any rewrite must keep that green**.
- `icons.draw` tested one bit per pixel, and each test shifted a `size`-bit
  integer: 7,056 big-int shifts for the 84px `WILLPOWER_XL`, **147 ms**. Runs
  are now decoded once per mask and cached in `_RUNS` (masks are module
  constants). **2.8 ms.**

**Partial repaint protocol.** A modal that changes one widget sets
`self.dirty_rect = (x, y, w, h)` in `on_button` and implements
`draw_partial(hw, game, pal)` returning that rect; the main loop repaints and
`partial_update`s just that region instead of a full draw plus present.
`PlayersDetailModal` (per-token) and `CommitModal` (value band) do this.

Net: a stat increment went **967 ms -> 37 ms**.

## Persistence: gameplay runs off RAM, storage happens in the background

**A tap must never touch storage.** It mutates RAM, queues what changed, and
returns — measured at **3.35 ms median / 7.56 ms worst** on device. The durable
work is drained by `db.session.tick()`, which `main.py` calls *only on frames
with nothing to draw*, so it never lands on a frame the player is waiting for.
This is a product requirement, not an optimisation.

Two rules make the background actually invisible:

- **Batch the journal.** Draining on every idle frame put a ~55 ms append in
  every gap between taps. `tick()` treats `_idle == 0` as "a tap arrived since
  last tick" and holds records in RAM until either `BATCH` have piled up or the
  run stops. Idle ticks are **0 ms median** as a result.
- **Debounce the checkpoint.** The `state.json` rewrite is the one expensive
  operation (~89 ms), so it waits `IDLE_BEFORE_STATE` quiet ticks — a real
  pause, of which a card game has many. Nothing is at risk meanwhile: the
  journal is already durable and is what reconstructs the state.

`flush()` goes **straight at the queue, not through `tick()`** — `tick()`
declines to write while the player looks active, which is right for a
background frame and wrong for a flush. Routing flush through it meant a
save-and-quit could return with records still in RAM. Flush points: save-quit,
game over, and before every `game` rebind.

**The queue is tagged with its game object.** `main.py` rebinds `game` on
new-game and end-game, and a queued write derived from a different game is
garbage — the same hazard `pending[1] is game` guards for deltas. A rebind
**drops** the queue; otherwise a late write resurrects a save the player just
ended. `tests/test_background_persistence.py` covers this.

There is no real background *thread*: Pimoroni disables `MICROPY_PY_THREAD` for
the Presto (`boards/presto/mpconfigboard.h`), so no second core and no sidecar
process is available from Python. The main loop's idle path is the equivalent.

A durable file write costs **~50 ms and is FLAT** — rewriting 1500 B costs the
same whether the file previously held 0 or 100 KB (measured; it is
per-open/write/close, not block-chain traversal). That is why none of this may
happen on the tap path.

- **`/state.json`** — the resumable game, ~1.5 KB. Written **atomically**
  (temp file + `os.rename`; rename over an existing target is permitted on this
  build, 8.6 ms). `open(path,"w")` truncated before the data landed, so a power
  cut left an unloadable save.
- **`/log.bin`** — the game log, append-only. It was **96% of `state.json`**
  (37,887 B rewritten every tap). `to_dict()` no longer carries it.
- **`/replay.bin`** — the delta history, append-only. Was a whole-file rewrite
  of every delta on every tap: 42 KB and **875 ms** by round 10.

Both append-only stores use the same framing: 2-byte little-endian length, then
the payload. A torn tail is **truncated at, never skipped** — for a delta
stream, applying records past a gap produces a *wrong* state rather than a
missing one.

**Two folds keep the stores honest, and both must mirror their writer:**
- `fold_log` — `log_event` is **not** purely append: a keyed tally rewrites its
  own row in place so eight stepper taps stay one line. The store records
  *events*, and the fold reapplies that same (key, round, step) rule.
- `fold_replay` — the journal cannot un-append, so the two non-append
  operations become tombstones: `{"op":"t"}` an undo discarding the redo
  future, `{"op":"x"}` the `MAX_SAVED_DELTAS` front-trim, `{"op":"s"}` a cursor
  move (`replay_step` is *written*, not recomputed — Divergence D3).

`tests/test_replay_journal.py` asserts the load-bearing invariant —
`fold_replay(journal) == (game.deltas, game.replay_step)` — including after
undo-truncation and after compaction. Legacy `/replay.json` is still read and
seeded into the journal, honouring "losing the history must never cost you the
game".

Measured end-to-end over 10 rounds: a tap went **1735 ms → 3.35 ms**, and
31 ms/tap counting every background write the run triggered.

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

**The card-image prefix is pinned, not fetched.** Card records carry only a
filename (`image: "<id>.jpg"`), so the tablet client needs a URL prefix to
build a picture out of one. That prefix is pinned beside the TSV url and sha
in `tools/data/cardDb.SOURCE.txt` as `image_prefix=`, and `build_card_data.py`
copies it verbatim into `index.json` as `imagePrefix` (read by
`quest_catalog.image_prefix()` / `quest_catalog.js`'s `imagePrefix()`,
`None`/`null` for a legacy index that predates the pin). **A plain build makes
no network call for it** — only `--refresh` does, re-reading the plugin's
`jsons/imageUrlPrefix.json` at the newly-resolved sha and taking its
`English` key (falling back to `Default`); a fetch/parse failure or a payload
with neither key is a loud `SystemExit`, so `--refresh` never pins a stale or
empty prefix. Same posture as every other pin here: deterministic ordinary
builds, one explicit local act to move the pin.

Nothing downloads the art. The tablet hotlinks `prefix + card.image`
(`docs/tablet/js/cardimage.js`'s `cardUrl`) and lets its **service worker**
cache the result (`docs/sw.js`, cache-first in its own image cache,
newest-N trimmed) — so no picture is committed, and none is copied into
`docs/data/` or onto the device. Two details `cardUrl` exists to get right:
the filename comes off the record's own `image`, never rebuilt from the id
(24 of 1016 catalog locations print on the BACK of a two-sided card and carry
`<id>.B.jpg`), and an `image` that is already an absolute URL (2 locations
carry a Hall of Beorn hotlink) is returned untouched. With no prefix, no
`image`, or an offline cold cache, the **figcaption** is what the player
reads — a missing picture is a first-class state, not an error path.

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

`tools/build_catalog_pack.py` packs the quest-picker rows into
`docs/data/catalog.bin` — fixed-width `struct` records plus a deduped string
table, slug-sorted for binary search. Same gitignored/regenerated posture as
the rest of `docs/data/`; runs in CI right after `build_card_data.py` and reads
nothing but the `index.json` it just wrote.

**Why binary, measured on the device — do not "simplify" this back to JSON.**
`type(json.loads)` is `<class 'function'>` on the Presto's MicroPython build:
the JSON decoder is **pure Python**, while `struct.unpack_from` is C. Parsing
`index.json` cost **713 ms and 263 KB resident**; the pack loads in **8 ms and
11 KB**. Two independent savings, both taken: 242 of 396 rows are unpickable
(`group_by_cycle` filters `stageCount > 0`) and `counts` alone is 23 KB with
zero runtime readers — so ship less *and* encode tight.

The pack deliberately carries `releaseDate` so `quest_catalog.pack_as_index()`
can feed the **existing** pure `group_by_cycle`/`cycles_for`/
`resume_picker_state` rather than reimplementing the grouping — a
reimplementation is where the twins drift. `CatalogPack` also exposes lazy
accessors (`cycle_names` 16 ms, `find` 1 ms via binary search) that decode no
text at all; `main.py` does not use them yet, because using them *would* mean
reimplementing the grouping. Absent or corrupt `catalog.bin` falls back to
`load_index()` — it is an optimisation, not a new source of truth.

**Slug namespaces collide and the build asserts on it:** `players/` and
`scenarios/` both key by `slugify()`, and **53 of 107 packs share a slug with a
scenario** (`a-journey-to-rhosgobel` is both a quest and a player pack). A flat
keyspace aliases them as *wrong data*, not a crash, so keys are typed
(`("scenario", slug)` / `("pack", slug)`).

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
fall back to their placeholder glyph. The same run can also write the pack's
SVGs — recoloured from `currentColor` to the palette gold both twins use for
set icons (`rgb(214,180,110)`, `pal.gold` in `docs/js/ui.js`), since a
tablet `<img>` can't inherit `currentColor` from the page the way an inline
SVG can — to `--svg-out/<slug>.svg` (gitignored, same pin) for the tablet
client. **`--svg-out` defaults OFF**, and must stay that way: the export is
~2.0 MB of tablet-only vector art, `docs/data/` is what the device deploy
copies wholesale, and nothing on the Presto reads an SVG. Only the Pages
build asks for it, explicitly — `python3 tools/build_icons.py --svg-out
docs/data/icons/svg` in `.github/workflows/pages.yml`. **The device deploy
one-liner below is unchanged and copies nothing new.** Rasterizing needs
Pillow plus either
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

**`includedSets` is not decoration — it is the join you need to see a
scenario's cards.** `scenarios/<slug>.json` is emitted per encounter *group*,
so it holds only cards whose `encounterSet` **is** that group's set. Passage
Through Mirkwood's own file has 2 of its 6 locations; the other 4 live in
`dol-guldur-orcs.json` and `spiders-of-mirkwood.json`, the sets it gathers.
Anything asking "what cards can this scenario put into play?" must union
across `includedSets` via `quest_catalog.slugify` — see `locations_for()` /
`locationsFor()`, which do exactly that for the location picker. Fall back to
the scenario's own slug when it has no gather list: the enrichment covers 108
scenarios and the rest land on the fallback, which is why the picker keeps a
manual escape hatch. 14 of 309 gather names resolve to no card file at all
and are skipped, never fatal.

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

**The tablet reads a LONG form of the same tips.** The 140-char ceiling above
is the Presto's 240x240 screen talking, not the advice's natural length - so
`tools/data/tips_long.json` (committed) carries a full-length version of each
tip, authored the same way (read the corpus, re-check every claim against the
card data, never reproduce). It is **keyed by each short tip's own text**, not
by position: position pairing breaks silently into WRONG pairings the moment
anything reorders or reclassifies a list, whereas a text key cannot mispair
and a key that matches nothing is reported as an orphan - which is exactly
when its long form needs rewriting. `build_tips.py` compiles it to
**`docs/tablet/data/tips_full.json`** (committed), positional against
tips.json's own arrays with `null` where there is no long form yet.

Two things about that output path, both load-bearing:

- **Not under `docs/data/`.** The device deploy is `mpremote cp -r docs/data/
  :/data/`, which copies that directory whole; long prose on Presto flash is
  pure waste. Same reason `--svg-out` is kept out of it.
- **`build()` writes it only when asked** (`long_out_path`, which `main()`
  passes and nothing else does). It defaulted to the real path for one
  commit, and every test that calls `build()` with a tmp `out_path` promptly
  overwrote the repo's committed long file.

The tablet merges long over short in `db.tipsFull()` (`quest_catalog.js`'s
pure `mergeLongTips`), so every renderer keeps reading one tips map and a tip
with no long form yet keeps the string tips.json wrote - the corpus lands
scenario by scenario, never as a flag day. **The firmware gets nothing**: this
is a deliberate divergence from iron rule 1, because the long form exists
precisely because the Presto cannot show it.

**House voice for the long form — write like the source, not like an essay.**
The distilled tips are terse because of a screen; the long ones are not
licence to write *prose*. Match the register of the blogs they come from
(`research/votp/`, `research/wotw/`), which is a player talking to another
player:

- **Lead with the instruction**, then give the reason in a plain
  `as`/`because`/`so` clause. "Don't put Ungoliant's Spawn in the victory
  display. One of the two stage 3 cards is won by finding and defeating it…"
- **Second person, throughout.** "you", "your threat", "don't".
- **Numbers stated flatly**, in passing, not built up to.
- **Be willing to be blunt.** "Don't bother with easy mode." A tip that
  hedges is a tip nobody acts on.
- **Two or three sentences, roughly 180-220 chars.** The ceiling is
  `MAX_LONG_LEN` (240).
- **CUT IDEAS, NEVER GRAMMAR.** This is the one that took three passes to get
  right. When a tip runs long, drop a whole clause or a whole sentence that
  is not earning its place. Do NOT compress the sentences you keep: the
  moment you strip the subject and verb off the front, you get telegraphese,
  and telegraphese reads as machine-written even when every word is
  defensible. "Keep your threat under 32 and Ungoliant's Spawn won't engage
  you" became "Under 32 threat Ungoliant's Spawn won't engage you" - twelve
  characters saved, and the sentence stopped sounding like a person. Keep the
  imperative openers, the "you", and ordinary connectives ("and", "so",
  "because", "as"); a semicolon joining two elliptical halves is the tell.

And the failure mode this hit on its first attempt — LLM explainer voice, all
of which was rejected and rewritten:

- **Thesis framing.** "Two numbers matter more here than staying low in
  general:" / "Taking an attack undefended is how this encounter deck
  punishes you." The blogs never announce what a paragraph is about; they
  just say the thing.
- **Antithesis and cadence for their own sake.** "…where you can shoot them
  instead of fighting them." "…a long fight to be starting from full."
- **Vague summarising flourishes.** "…and they ask for very different
  things."
- **Em-dashes as rhetorical pivots.** The source uses commas and full stops.

Same rules as ever apply on top of voice: written from the corpus, never
inflated from the terse line (expanding a 70-character clause into a sentence
is how invented claims get in), every claim re-checked against the compiled
card data, and never reproduced — `build_tips._too_verbatim` is the check, at
8 shared words.

The article corpus the distillation is written from lives in **two**
vault-side, **gitignored** directories — `research/votp/` (Vision of the
Palantir, built by `tools/build_votp_corpus.py`) and `research/wotw/`
(Warriors of the West, `tools/build_wotw_corpus.py`) — see below. The fetched
HTML in `tools/data/tips_cache/` and `tools/data/wotw_cache/` is verbatim
third-party content and also stays gitignored. Only our own words are
committed.

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

`tools/build_wotw_corpus.py` does the same for the **Warriors of the West**
blog into `research/wotw/` — the second distillation source, and complementary
rather than redundant: VotP's spotlights describe a scenario in **standard**
mode, while ~15 of Warriors of the West's 45 posts are Nightmare reviews, plus
turn-by-turn reports and a running mega-campaign, so it covers the mode the
other corpus barely touches and covers it as *played* rather than as
previewed. Both blogs are WordPress, so the extraction and pandoc conversion
are shared outright with `build_votp_corpus` (`convert(..., tag=, title_re=)`)
rather than reimplemented — note this theme's `<h1>` is the SITE name, which
is what `title_re` exists to override.

The post list comes from the blog's **own sitemap**, so no URL is guessed.
Slugs are matched to catalog scenarios on a separator-stripped form and also
without a leading "the-", because the blog differs from the catalog two ways —
possessives (`helms-deep` vs our `helm-s-deep`) and dropped articles
(`review-siege-of-annuminas` vs `the-siege-of-annuminas`). 33 of 45 posts name
a scenario, covering 29; the rest are deck tech, spoiler round-ups and
campaign framing, and are kept as readable context rather than dropped. What
the matcher deliberately will **not** bridge is the author simply spelling a
name differently (`deadmans-dike` for *Deadmen's Dike*) — guessing there
would be guessing.

Same data policy as everything else here: `--refresh` fetches, nothing runs in
CI, and **only text we write ourselves** from reading either corpus reaches
`tools/data/tips_distilled.json` and from there `docs/data/tips.json`.

`tools/build_rules_text.py` parses `research/rules/rules-reference.md` (the
gitignored liteparse corpus `build_rules_corpus.py` builds, see
`rules/README.md`) into `docs/data/rules_text.json` — sections keyed by
numbered turn-step id (`"6.4a"`) and glossary entries keyed by term
(`"Player Elimination"`). Unlike `tips.json` this is **not** an allow-listed
exception: it is verbatim FFG excerpts, not our own summary, so it stays
under the blanket `docs/data/*` ignore and is never committed — same
generated-and-gitignored posture as the compiled card DB. The source PDF is
pinned by content hash in `tools/data/rules.SOURCE.txt`; FFG's product page
has no verified direct download link (plan ruling R3), so `url=` is normally
empty and both the tool and the CI step that would fetch it are no-ops until
someone fills it in from a verified source. Same no-op-when-present rule as
the rest of `docs/data/`: the tool skips with a one-line message unless
`--force` or the output is missing.

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
