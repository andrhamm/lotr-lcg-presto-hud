"""Row-level corrections applied to the pinned card DB before it is compiled.

Two jobs, both operating on raw TSV rows so they reach `name` and
`encounterSet` as well as `text` - which `normalize_face` cannot, since it only
sees one face at a time and runs after grouping.

**Transcription fixes.** The upstream DragnCards TSV carries typos that the HUD
renders as authoritative card text: "Gret Spider", "vitory display", "discrad".
`docs/data/` is generated and gitignored, so it cannot be hand-edited; the
sanctioned mechanism is a committed derived table in `tools/data/`, merged at
build time. Same posture as `enrichment.json`. Each entry carries a `why`.

**Encounter-set unification.** Upstream attached a scenario's Quest cards to a
misspelled encounter set and left the correctly-spelled set holding a couple of
stray treacheries, splitting one scenario into a pickable half and an invisible
0-stage stub. Rewriting `encounterSet` at row level makes the pair slug-collide
and merge through `enc_groups.setdefault` in build_card_data - the behaviour
`tests/test_card_data.py::test_slug_collision_merges_and_index_matches_files`
already pins.

Shaped after `tools/alep.py`'s `apply_errata`: a pure `(rows, table) -> (rows,
unmatched)`, run before `group_cards`, reporting entries that matched nothing
rather than raising. An entry that stops matching means upstream fixed it, and
that should show up as a printed line, not as silent divergence.
"""

import re
import unicodedata

# Columns whose contents a player can end up reading on the device. `traits`
# and `keywords` are drawn on card modals; `encounterSet` and `packName` are
# drawn on the scenario picker AND feed slugify, which is why folding them is
# what keeps slugs ASCII.
TEXT_COLUMNS = ("name", "text", "shadow", "traits", "keywords", "cornerText",
                "encounterSet", "packName", "type", "sphere")

# Curly punctuation the bitmap8 font has no glyph for. NFKD alone leaves these
# untouched (they are not decomposable), so they need naming. Measured over the
# whole catalog, the only residue after NFKD is these plus the bullet.
_PUNCT = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"',
    "–": "-", "—": "-", "―": "-", "−": "-", "‐": "-", "‑": "-",
    "…": "...", " ": " ", "•": "-", "©": "(c)",
    "«": '"', "»": '"', "′": "'", "″": '"',
}

# A backtick standing in for an apostrophe INSIDE a word: "card`s", "Durin`s".
# Deliberately not a blanket ` -> ' replace: of ~165 backticks in the catalog
# roughly half are quote DELIMITERS wrapping nested card text ("it gains:
# `Response: ...`"), and rewriting those as apostrophes would be a new error,
# not a fix. Those are left alone; see the todo block in corrections.json.
_POSSESSIVE_BACKTICK = re.compile(r"(?<=\w)`(?=\w)")

# The same, but where the word ends at the backtick: "his heroes` resource
# pool". The lookahead above misses these because the next character is a
# space, and they are unambiguously possessive plurals.
_PLURAL_POSSESSIVE_BACKTICK = re.compile(r"(?<=s)`(?=\s)")


def fold_ascii(s):
    """Fold a string to characters the device font can actually draw.

    The bitmap8 glyph table has 82 entries and no accented characters, and
    `BITMAP8_W.get(c, 4)` returns 4 for anything absent - so a curly quote or a
    circumflex passes every host layout test and only breaks on the device.
    75 of 145 pickable scenarios carry non-ASCII somewhere the HUD renders.

    Folding happens at BUILD time, not at runtime: both twins then consume one
    artifact and cannot drift, and it lands before slugify so a name and its
    slug stay consistent.
    """
    if not s:
        return s
    out = "".join(_PUNCT.get(ch, ch) for ch in s)
    out = unicodedata.normalize("NFKD", out)
    return "".join(ch for ch in out if not unicodedata.combining(ch))


def _fix_backticks(s):
    if not s or "`" not in s:
        return s
    s = _POSSESSIVE_BACKTICK.sub("'", s)
    return _PLURAL_POSSESSIVE_BACKTICK.sub("'", s)


def apply_corrections(rows, table):
    """Rewrite rows per `table`. Returns (rows, unmatched_descriptions).

    Order matters: set renames first (so a text rule can name the corrected
    set), then per-card text fixes, then the mechanical global passes. Folding
    last means a correction can be written with the proper spelling and still
    end up ASCII.
    """
    table = table or {}
    unmatched = []

    renames = {r["from"]: r["to"] for r in table.get("sets") or []}
    hit_renames = set()
    if renames:
        for row in rows:
            enc = (row.get("encounterSet") or "").strip()
            if enc in renames:
                row["encounterSet"] = renames[enc]
                hit_renames.add(enc)
    for src in renames:
        if src not in hit_renames:
            unmatched.append("set rename %r (no row carries it)" % src)

    for rule in table.get("text") or []:
        find, repl = rule["find"], rule["replace"]
        hits = 0
        for row in rows:
            if rule.get("set") and (row.get("encounterSet") or "").strip() != rule["set"]:
                continue
            if rule.get("name") and (row.get("name") or "").strip() != rule["name"]:
                continue
            for col in ("text", "shadow", "name"):
                v = row.get(col)
                if v and find in v:
                    row[col] = v.replace(find, repl)
                    hits += 1
        if not hits:
            unmatched.append("text fix %r (matched no card - upstream may have "
                             "fixed it)" % find)

    glob = set(table.get("global") or [])
    for row in rows:
        for col in TEXT_COLUMNS:
            v = row.get(col)
            if not v:
                continue
            if "possessive_backtick" in glob:
                v = _fix_backticks(v)
            if "fold_ascii" in glob:
                v = fold_ascii(v)
            row[col] = v

    return rows, unmatched


def fold_payload(obj):
    """Fold every string in an emitted payload to device-renderable ASCII.

    The row-level pass in apply_corrections cannot be the only one: it runs
    before grouping, so it never sees the strings that arrive LATER from the
    committed distillations - `includedSets` (enrichment.json), the per-stage
    `advance` conditions (advancement_distilled.json) - or the index's own
    hardcoded disclaimer. Those accounted for 15 of the 16 non-ASCII characters
    left in docs/data after the row pass.

    Both passes are needed and neither is redundant: the row pass has to happen
    before slugify so a name and its slug agree, and this one has to happen at
    emit so nothing merged in afterwards slips through.
    """
    if isinstance(obj, str):
        return fold_ascii(obj)
    if isinstance(obj, list):
        return [fold_payload(v) for v in obj]
    if isinstance(obj, dict):
        return {k: fold_payload(v) for k, v in obj.items()}
    return obj
