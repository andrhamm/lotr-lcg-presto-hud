# rules/ — verified rules notes, and how to check a claim

Two different things live under this heading, and the split is the same
verbatim-vs-derived line the rest of the repo uses:

- **`rules/*.md` (committed)** — our own summaries, written after reading a
  primary source, with the source cited. `action-windows.md` is one.
- **`research/rules/*.md` (gitignored)** — the official FFG rulebooks parsed to
  markdown, so they can be *searched*. Verbatim third-party text: never
  committed, never shipped, same posture as `research/votp/`.

## Searching the rulebooks

The parsed corpus is indexed by [qmd](https://github.com/) as the collection
**`lotr-lcg-rules`**, so a rules question is a semantic search, not a grep
through a PDF:

```bash
qmd query "does each player resolve all their engaged enemies before the next player" -c lotr-lcg-rules
```

Keyword search when you know the exact term, which is often faster for a
numbered step:

```bash
qmd search "engagement cost" -c lotr-lcg-rules
```

The parse turns every numbered rule step into a markdown heading
(`###### 6.4a Next enemy attack initiates`), so a hit lands on the step rather
than mid-page. Claude reaches the same index through the qmd MCP server.

## Building the corpus

```bash
python3 tools/build_rules_corpus.py ~/path/to/rulebook.pdf --title "Rules Reference" --no-ocr
```

Then re-index:

```bash
qmd update -c lotr-lcg-rules && qmd embed -c lotr-lcg-rules
```

`--no-ocr` is right for text-based PDFs (every FFG rulebook released as a
digital download) and is much faster. Drop it for scans — `01 - Core Set.pdf`
is a photographed scan with no text layer and needs OCR.

Registering the collection, once:

```bash
qmd collection add "$PWD/research/rules" --name lotr-lcg-rules --pattern "**/*.md"
```

**Why liteparse and not `pdftotext`:** the rulebooks are two-column. Plain
`pdftotext` runs the columns together in reading order; `-layout` keeps them
side by side, so each line holds fragments of two unrelated sentences. Both
shred the prose — fine for grep, useless for embeddings. LiteParse
(`--format markdown`) reconstructs the columns from the PDF's geometry and
emits real headings.

## What is indexed

16 documents, ~100k words. All but the Rules Reference came from the official
downloads on FFG's product page:
<https://www.fantasyflightgames.com/en/products/the-lord-of-the-rings-the-card-game/>

| Document | Source PDF |
|---|---|
| **Rules Reference** — glossary + numbered turn steps | `lotr lcg saga rulebook.pdf` |
| **Core Set Learn to Play** | `lotr_lcg_core_set_rules_reference.pdf` |
| The Fellowship of the Ring Saga Expansion | `mec109_rulebook-compressed.pdf` |
| The Two Towers Saga Expansion | `mec112_rulebook_eng.pdf` |
| The Return of the King Saga Expansion | `mec113_rules-web.pdf` |
| Angmar Awakened Campaign Expansion | `mec108_rules.pdf` |
| Angmar Awakened Hero Expansion | `mec107_rules.pdf` |
| Dream-chaser Campaign Expansion | `mec111_dreamchaser_campaign_rulebook_web-compressed.pdf` |
| Dream-chaser Hero Expansion | `mec110_hero_rules_insert_web.pdf` |
| Ered Mithrin Campaign Expansion | `mec115_rules-web.pdf` |
| Ered Mithrin Hero Expansion | `mec114_rules-web.pdf` |
| Dark of Mirkwood | `dark_of_mirkwood_rulebook_v2.pdf` |
| Dwarves / Wood-elves / Gondorians / Rohirrim starter decks | `mec103`–`mec106_rules.pdf` |

**Two traps in that list.** FFG's `lotr_lcg_core_set_rules_reference.pdf` is
*Learn to Play*, not the Rules Reference — it has no glossary and no numbered
steps, and it tells you to "see the Rules Reference" for keywords. The actual
Rules Reference (the one with 6.4a in it) is the separate 36-page book. Both
are ©2021 Revised Core, so they are companion volumes, not two versions of one
document; keep both indexed. And the MEC product codes make useless search
titles, so `--title` is passed per file to name each book properly.

The campaign expansions are what finally cover the scenario-specific modes the
Rules Reference does not: sailing and heading/off-course (Dream-chaser),
Battle/Siege, and the saga campaign rules.

## The point of all this

CLAUDE.md's rule 4 says never ship an unverified rules claim, and orders the
sources to check. This corpus is the primary-source rung of that ladder. Before
it existed, the on-screen line *"deal 1 facedown shadow card to each engaged
enemy, in player order — highest engagement cost first"* sat in the UI marked
**unverified** because nothing local could confirm it. It is now confirmed
verbatim by Rules Reference **6.2** — both clauses, including the tiebreak.
