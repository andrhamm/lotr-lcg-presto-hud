# Card-Data Pipeline — Design (M4 sub-project A)

Status: approved 2026-07-24. First of three sub-projects delivering
[[roadmap|M4 · Quest awareness]]. See [[quest-index]] and [[stats-redesign]].

## Purpose

Compile the **entire** DragnCards community card database into bundled,
generated JSON that both twins (web `docs/js/`, firmware `ui/`) read
identically. This is the data backbone for all of M4 and beyond: the immediate
quest features are one *view* over it, and future features (encounter-sets to
gather, enemy-threat warnings, difficulty modes, campaign, card lookup) get
their data for free.

Directive (user): *compile as much data as DragnCards has, even where not
strictly required by the current plan.* So A ingests all 5,074 cards, every type
and field — not just quests.

Consumers, later:
- **B — Picker UI.** Grouped scenario select → preload the first stage + sailing
  into `gamestate`; extend the model with `scenario` + a `stages` sequence so
  *advance* pulls the next stage automatically.
- **C — Contextual tips.** Surface the active stage's verbatim text in the quest
  views.

A is built first because the data shape, source, and edge cases are the biggest
unknowns and everything downstream depends on the contract.

## Scope

**In scope (A):**
- A build tool that fetches `cardDb.tsv` from a pinned DragnCards commit and
  compiles **all** card types into normalized JSON.
- The JSON data contract both twins read: a top **index**, **per-scenario**
  encounter files (with quests shaped into stages), a **player-card DB** split
  by pack, and a **rules** set.
- Delivery of the (untracked) output: gitignore the generated dir; a GitHub
  Actions workflow that builds + deploys Pages; firmware bundles the full DB.
- Host tests over the derive logic (fixture-driven, no network).
- Licensing provenance + disclaimer embedded in the output.

**Out of scope (A) — deferred:**
- Any UI (picker, tips, card lookup). B, C, later.
- `gamestate` changes (the `scenario`/`stages` model, preload, auto-advance). B.
- **Card image files.** The `imageUrl` reference field is preserved, but no
  images are downloaded or bundled — art is external (S3), large, and a heavier
  copyright tier. A later feature may fetch on demand.
- **Campaign progression logic** (a boon/burden pool, saga state-machine). The
  campaign *cards* are compiled as data/text; modelling campaign *state* is a
  future feature — the TSV has no progression schema to drive it anyway.
- A `packName → cycle` map for grouped display. B owns presentation.

## Data source

- **Repo:** `seastan/dragncards-lotrlcg-plugin`, file `tsvs/cardDb.tsv`
  (tab-separated, 5,074 rows, 28 columns). Generated upstream from a community
  Google Sheet. The `jsons/*.json` files are engine automation keyed by UUID and
  hold no card stats/text — ignore them.
- **Fetch, pinned:** the build reads
  `raw.githubusercontent.com/seastan/dragncards-lotrlcg-plugin/<sha>/tsvs/cardDb.tsv`
  where `<sha>` is a **commit SHA**, never `main`. Not vendored — the repo does
  not carry the source TSV.
- **All 28 columns are preserved.** They are: `databaseId, name, imageUrl,
  cardBack, type, packName, deckbuilderQuantity, setUuid, numberInPack,
  encounterSet, unique, sphere, traits, keywords, cost, side, engagementCost,
  threat, willpower, attack, defense, hitPoints, questPoints, victoryPoints,
  cornerText, text, shadow, tags`.

### Card identity and partitioning (verified against the TSV)

- **A card = the rows sharing one `databaseId`.** A double-sided card is two
  rows (`side` A and B) with the **same** `databaseId`; each row carries its own
  full column set (name/text/points can differ per side). 698 cards are
  two-faced, 3,676 single-faced. Faces are grouped by `databaseId`.
- **A branched quest stage = multiple `databaseId`s sharing one `cost`.**
  Verified on Passage stage 3: `…9123` ("Don't Leave the Path!") and `…9125`
  ("Beorn's Path") are distinct ids, so grouping by id keeps them as two cards.
- **Encounter vs player split = `encounterSet` presence.** Encounter-side cards
  (Quest, Enemy, Location, Treachery, Objective\*, Ship\*, Nightmare, Campaign,
  most Rules) carry an `encounterSet`; player cards (Hero, Ally, Attachment,
  Event, player Side Quest, Contract, Treasure) leave it blank (1,165 of 1,245
  player rows blank). Rule: **`encounterSet` non-empty → group into a scenario
  file; empty → player DB, grouped by `packName`.** (The ~80 player-type rows
  with an `encounterSet`, e.g. objective-allies, correctly land in the scenario
  they belong to.)

### Licensing (decided, built in)

There is **no redistribution license** for the card text — © Fantasy Flight
Publishing; "The Lord of the Rings" is a trademark of Middle-earth Enterprises.
The user has chosen to compile and publish the full text. Mitigation baked in:

- Disclaimer embedded in `index.json`: *"Unofficial companion. Not affiliated
  with or endorsed by Fantasy Flight Games. The Lord of the Rings is a trademark
  of Middle-earth Enterprises. Card text © FFG."*
- Provenance (source repo + pinned commit + generated date) in `index.json`,
  mirrored in `tools/data/cardDb.SOURCE.txt`.
- **Footprint, stated plainly:** this publishes a *complete unofficial card
  database* (all card text) — the same kind of resource Hall of Beorn / RingsDB
  host. Nothing tracked carries card text (see *Delivery*); it exists only in
  generated artifacts (Pages site, device flash).

## Data contract

Output root: `docs/data/` (gitignored, generated). Four kinds of file.

### Normalized card

Every non-quest card is normalized to a shared shape (quests get an additional
shaped view, below). All TSV columns are preserved; numeric fields parse to int
or `null`; `tags` parses from its embedded JSON to an object or `null`; sides
collapse into `faces`.

```json
{
  "id": "51223bd0-…-1e01",
  "type": "Enemy",
  "name": "Ungoliant's Spawn",
  "pack": "Core Set",
  "encounterSet": "Passage Through Mirkwood",
  "number": 34,
  "unique": false,
  "sphere": null,
  "traits": "Creature. Spider.",
  "keywords": "",
  "image": "51223bd0-…-1e01.jpg",
  "tags": null,
  "faces": [
    {
      "side": "A",
      "engagementCost": 32, "threat": 3, "attack": 5, "defense": 2,
      "hitPoints": 9, "willpower": null, "cost": null,
      "questPoints": null, "victoryPoints": null,
      "cornerText": null,
      "text": "When Revealed: Each player…",
      "shadow": "Shadow: attacking enemy gets +1 …"
    }
  ]
}
```

Single-faced cards have one `faces` entry (its `side` may be empty). Fields that
are identity-level (id, type, name, pack, encounterSet, number, unique, sphere,
traits, keywords, image) sit on the card; per-printing stats/text sit on
`faces`. Top-level `name` is the A-side (primary) name.

### Index — `docs/data/index.json`

Loaded up front. Drives the picker and any browse UI.

```json
{
  "generated": "2026-07-24",
  "source": "seastan/dragncards-lotrlcg-plugin@<sha> tsvs/cardDb.tsv",
  "disclaimer": "Unofficial companion. Not affiliated with or endorsed by Fantasy Flight Games. …",
  "scenarios": [
    {
      "slug": "passage-through-mirkwood",
      "name": "Passage Through Mirkwood",
      "pack": "Core Set",
      "kind": "quest",
      "stageCount": 3,
      "sailing": false,
      "hasNightmare": true,
      "modes": [],
      "counts": { "enemy": 6, "location": 5, "treachery": 4, "objective": 0 }
    }
  ],
  "packs": [ { "slug": "core-set", "name": "Core Set", "cardCount": 226 } ],
  "rules": true
}
```

`kind` ∈ `quest | nightmare | campaign | encounter` (the set's primary content).
`hasNightmare` soft-links a base scenario to its `"<name> - Nightmare"` set.
`modes` lists any Easy/Standard/Hard/Epic mode-card names present.

### Per-scenario — `docs/data/scenarios/<slug>.json`

The whole encounter set. `quest` is the shaped stage view; everything else is
normalized cards in typed buckets.

```json
{
  "slug": "passage-through-mirkwood", "name": "Passage Through Mirkwood",
  "pack": "Core Set", "kind": "quest", "sailing": false,
  "quest": {
    "stages": [
      { "stage": 1, "cards": [ { "questPoints": 8, "victory": null, "sailing": false,
          "faces": [ {"side":"A","name":"Flies and Spiders","text":"Setup: Search the encounter deck…"},
                     {"side":"B","name":"Flies and Spiders","text":null} ] } ] },
      { "stage": 2, "cards": [ { "questPoints": 2, "victory": null, "sailing": false, "faces": [ … ] } ] },
      { "stage": 3, "branch": "random", "cards": [
          { "questPoints": 0,  "victory": null, "sailing": false, "faces": [ {"side":"A","name":"A Chosen Path","text":"…"}, {"side":"B","name":"Don't Leave the Path!","text":"When Revealed: …"} ] },
          { "questPoints": 10, "victory": null, "sailing": false, "faces": [ {"side":"A","name":"A Chosen Path","text":"…"}, {"side":"B","name":"Beorn's Path","text":"…"} ] }
      ] }
    ]
  },
  "encounter": {
    "enemy":     [ /* normalized cards */ ],
    "location":  [ … ],
    "treachery": [ … ],
    "objective": [ … ]
  },
  "modes":    [ /* Easy/Standard/Hard mode cards, if any */ ],
  "campaign": [ /* Campaign-type cards in this set, if any */ ]
}
```

Quest-view rules (unchanged from the earlier design):
- `stages` ordered by stage number (`int(cost)`) ascending; faces A before B.
- A stage with >1 card carries `branch` (`"random"` or `"choice"`, inferred from
  the B-side text; default `"random"`). `stageCount` counts stages, not cards.
- Each card: `questPoints` (from the B face; `0` when blank), `victory`
  (`victoryPoints` or null), `sailing` (this card's Sailing keyword), `faces`
  `{side, name, text}`.
- Quest cards appear **only** in `quest.stages`, not duplicated in `encounter`.
- Consumers: B reads `questPoints` (picks a card for a branch — default first, or
  random); C reads the active `face.text`.

`quest` is `null` for a set with no Quest rows (e.g. an objective-only set;
`kind` then reflects the primary content).

### Player-card DB — `docs/data/players/`

```
players/index.json          # [ { slug, name (pack), cardCount } ]
players/<pack-slug>.json     # { "pack": "Core Set",
                             #   "cards": { "hero":[…], "ally":[…], "attachment":[…],
                             #              "event":[…], "sideQuest":[…], "contract":[…],
                             #              "treasure":[…] } }  (normalized cards)
```

Split by pack so a browse/lookup feature loads one pack at a time.

### Rules — `docs/data/rules.json`

The 64 `Rules` cards as normalized cards (reference text).

## Pipeline

Single tool: `tools/build_card_data.py`.

**Pin resolution.** `tools/data/cardDb.SOURCE.txt` records the source URL and the
pinned commit SHA. A normal build reads the pinned SHA. `--refresh` re-resolves
the plugin repo's current default-branch HEAD (GitHub API), rewrites
`SOURCE.txt`, and proceeds — the deliberate "update the data" action. Absent
`SOURCE.txt`, the tool errors and instructs the user to run `--refresh` once.

**Build steps (default mode):**
1. Fetch the TSV at the pinned SHA (`urllib`), parse with `csv` (tab delimiter,
   `QUOTE_NONE` — the text column has quotes but no tabs).
2. **Normalize** every row → a face dict; group rows by `databaseId` into cards
   (faces ordered A, B, …); parse numerics to int/null and `tags` to object.
3. **Partition:** `encounterSet` non-empty → the scenario for that set; empty →
   the player DB under `packName`. `Rules` cards → the rules set.
4. **Shape quests:** within a scenario, from its `Quest` rows build
   `quest.stages` (group by `int(cost)`; a stage's multiple ids → a `cards`
   list + `branch`). Non-quest encounter cards go into typed `encounter`
   buckets; `Nightmare` sets are their own scenarios; `Mode`/`Campaign` cards
   nest into their set's `modes`/`campaign`.
5. **Indexes:** per scenario compute `slug`, `kind`, `stageCount`, `sailing`,
   `hasNightmare`, `modes`, `counts`; build the player-pack index and the top
   `index.json`.
6. **Emit** `docs/data/index.json`, `docs/data/scenarios/<slug>.json`,
   `docs/data/players/index.json` + `players/<pack-slug>.json`,
   `docs/data/rules.json`. Sort collections deterministically (scenarios by
   pack then name; cards by `number`) for stable diffs and byte-identical
   re-runs.

**Both twins / Iron rule #2.** The output is *data*, not code, so it does not
flow through `gen_web_data.py` (which emits code-like JS from `phases.py` /
`ui/icons.py`). It honours [[../CLAUDE|Iron rule #2]] in spirit — a single source
(the pinned TSV), a deterministic regenerator, and **hand-edits to the JSON are
forbidden**; change data by re-running the build. Documented in `index.json`
(`source`) and `CLAUDE.md`.

## Delivery

Output is not tracked; each surface builds it.

**Not committed.** `docs/data/` is **gitignored**. The build populates it — in CI
for Pages, and locally on demand (`python3 tools/build_card_data.py`, one network
fetch). The only tracked artifacts are the build script and the pinned SHA
(`tools/data/cardDb.SOURCE.txt` — a URL + commit, no card text).

**Web (GitHub Pages) — Actions-built.** Pages moves from branch-based to a
**GitHub Actions** source. New workflow `.github/workflows/pages.yml`:
1. Trigger on push to `main` (+ manual `workflow_dispatch`).
2. `actions/checkout` → `actions/setup-python` → `python3
   tools/build_card_data.py` (writes `docs/data/`).
3. `actions/upload-pages-artifact` `path: docs` → `actions/deploy-pages`.
   Permissions `pages: write`, `id-token: write`; `github-pages` environment.
   (Action versions pinned at implementation.)

Published site = the existing static `docs/` **plus** the freshly built
`docs/data/`. The one-time Pages-source switch to GitHub Actions has already
been done by the user.

**Firmware — full DB on flash.** The device has no build step, so the
main-session deploy runbook gains: run `python3 tools/build_card_data.py`
locally, then `mpremote cp -r docs/data/ :/data/`. The **full compiled DB**
(~2 MB) lives on flash; MicroPython reads `/data/index.json` once and other
files on demand with the `json` module — only the index + whatever is open sits
in RAM. Device deploys stay main-session only, per `CLAUDE.md`.

**Local development.** Run the build once to populate the gitignored
`docs/data/` so the preview server serves it. Tests never need it.

**No conflict with the pending `main` push.** The scheduled stats-redesign push
deploys under the current setup fine; the pipeline lands only when M4 merges.

## Edge cases

- **Branched stage** → multiple ids at one `cost` → `cards` length >1 + `branch`.
- **Nightmare** sets → own scenario, `kind:"nightmare"`; base scenario gets
  `hasNightmare:true`.
- **Mode cards** (Easy/Standard/Hard/Epic — `Campaign`/`Objective` type, named
  `… Mode`) → the set's `modes` bucket + listed in the index `modes`.
- **Campaign cards** → the set's `campaign` bucket; a set that is *only* campaign
  cards → `kind:"campaign"`, `quest:null`.
- **Player cards** (blank `encounterSet`) → player DB by pack.
- **Sailing:** a face is sailing if its `keywords` contains "sailing"
  (case-insensitive substring; exact token confirmed at build). Scenario
  `sailing` = OR over quest cards. Sanity: Flight of the Stormcaller `true`,
  Passage `false`.
- **Slugs:** `slugify(encounterSet)` / `slugify(packName)` — lowercase, hyphenate
  runs of non-alphanumerics, trim. Encounter sets and packs are **grouped by
  slug**, so names differing only by case/punctuation (upstream typos, e.g.
  "Lost In"/"Lost in") merge into one scenario/pack under the first-seen
  display name; the index always matches the written files (no orphans).
- **Blank fields** → `null`. **Malformed `cost` on a quest row** → the row is
  logged and skipped; total skipped count printed (no silent drops).
- **`tags` parse failure** → keep raw string under `tagsRaw`, `tags:null`, log.
- **Non-quest multi-sided cards** (some locations/objectives) → handled by the
  generic `databaseId`→`faces` grouping; no special case.

## Testing (host, pure Python, no network)

`tests/test_card_data.py` drives the derive logic against a committed fixture
`tests/fixtures/cardDb_sample.tsv` containing at least: Passage's four quest
cards (incl. the branch), an enemy, a location, a treachery, a nightmare row, a
`Mode` card, a campaign card, a player hero + ally, a rules card, a blank-`text`
row, and a malformed-`cost` row.

The parse/derive entry point takes an **open text stream** (not a URL) so tests
feed the fixture with no network. Assertions:
- Faces grouped by `databaseId`; branch → two ids at one `cost` → `cards`
  length 2 + `branch`; non-branch → length 1, no `branch`.
- `questPoints` from the B face; text captured per face; numerics parsed to int;
  `tags` parsed to object.
- Partition: encounter cards into their scenario's typed buckets; player cards
  into the pack DB; rules into `rules.json`; quest cards absent from `encounter`.
- `sailing`, `slug` (+ uniqueness), `kind`, `hasNightmare`, `modes`, `counts`.
- Malformed `cost` row skipped and counted.
- **Golden:** Passage → stages `[1: qp 8, 2: qp 2, 3: branch {0, 10}]`,
  `sailing:false`, `hasNightmare:true`, matching
  [[passage-through-mirkwood|our captured notes]].

`python3 -m pytest tests/` stays green ([[../CLAUDE|Iron rule #3]]).

## File layout

**Tracked (committed):**
```
tools/
  build_card_data.py               # fetch pinned TSV -> full JSON DB; --refresh re-pins
  data/
    cardDb.SOURCE.txt              # source URL + pinned commit SHA (a pointer; no card text)
.github/workflows/
  pages.yml                        # build DB + deploy Pages (Actions source)
tests/
  fixtures/cardDb_sample.tsv       # small committed sample (no network in tests)
  test_card_data.py
.gitignore                         # + docs/data/
```

**Generated, gitignored (built in CI / locally / at device deploy):**
```
docs/data/
  index.json                       # top index (scenarios + packs + rules flag)
  scenarios/<slug>.json            # per encounter set (quest stages + typed buckets)
  players/index.json
  players/<pack-slug>.json         # player cards grouped by type
  rules.json
```

Firmware deploy builds locally then copies `docs/data/` → device `/data/`.

## Success criteria

1. `build_card_data.py --refresh` then a plain build compiles **all 5,074 cards**
   into `index.json` + scenario files + player DB + rules, deterministically
   (re-runs byte-identical).
2. Passage golden: stages `[1:8, 2:2, 3:{0,10} random]`, `sailing:false`,
   `hasNightmare:true`; its encounter buckets hold its 6 enemies / 5 locations /
   4 treacheries.
3. Flight of the Stormcaller resolves `sailing:true`.
4. Player cards land in `players/<pack>.json` (not in any scenario); Rules in
   `rules.json`; Mode cards in their set's `modes`.
5. `python3 -m pytest tests/` green, **no network during tests**.
6. Nothing tracked carries card text or the TSV — only the script + SHA pointer;
   `docs/data/` gitignored. Hand-editing JSON is not a supported path.
7. `.github/workflows/pages.yml` builds the DB and deploys Pages (existing
   `docs/` + generated `docs/data/`).
8. Firmware deploy bundles the full `docs/data/` to device `/data/`.

## To confirm at implementation time

- The exact Sailing keyword token (substring check is robust regardless).
- The initial pinned commit SHA (resolved by the first `--refresh`).
- Total compiled size and per-file sizes (sanity for the ~2 MB device bundle).
- Slug collisions merge by slug (3 upstream typo pairs in current data — Lost In/Lost in, A Shadow of the Past/…past, The Druadan Forest/…Forest.); revisit if a genuinely distinct set ever collides.
