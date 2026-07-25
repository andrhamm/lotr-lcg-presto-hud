"""A Long Extended Party (ALeP) card data: fetch, errata merge, pack metadata.

ALeP is the fan-made continuation of the card game. DragnCards carries it, but
NOT on the branch tools/build_card_data.py pins: `seastan/dragncards-lotrlcg-
plugin@main` ships one `tsvs/cardDb.tsv` with official cards only. ALeP lives
on the repo's separate **`alep` branch**, as ~31 UUID-named TSVs alongside an
identical copy of cardDb.tsv. The upstream site merges the two branches at
deploy time with the repo's own `merge_alep.sh` (copy main's tsvs/, then
overlay the alep branch's). This module is that merge, done at build time.

Every TSV uses the same columns as cardDb.tsv, so ALeP rows flow through
build_card_data.py's existing parse_tsv/group_cards path unchanged. What ALeP
adds that needs handling here is an ERRATA PACK, plus some non-content packs.

Errata (apply_errata)
---------------------
`ALeP - Errata Pack` holds corrected reprints of cards that already exist in
their real packs. These are errata to apply to our data, not a pack of their
own: surfacing it as a pack would invent three phantom scenarios (Sundown on
the Shire, The Gap of Rohan, The Scouring of the Shire all already exist).

Join key is (name, encounterSet, side, traits) - established by inspecting the
data, not assumed:

  - databaseId does NOT work: every errata row carries a fresh id, so there
    is zero overlap with the base rows (verified: 0 of 23 id+side keys match).
  - `traits` is load-bearing, not incidental. `Eastern Assault` (The Siege of
    Erebor) is a multi_sided card whose two faces are the scenario's Normal.
    and Easy. difficulty variants, and BOTH carry an empty `side` column - so
    without traits in the key the Easy face silently overwrites the Normal
    one. Every ALeP scenario ships easy/normal modes (see the plugin's own
    zz-*.menu.json), so this shape recurs.
  - Excluding type=="Rules", all 25 remaining errata rows resolve to exactly
    one base row, except `Roused Hobbits`, which matches 7 base rows that are
    byte-identical - so replacing all of them is well-defined.
  - type=="Rules" errata rows are DROPPED: multi-page rules inserts repeat a
    name across pages (distinguished only by cornerText), so the key is
    ambiguous by construction, and build_card_data.py routes Rules cards to
    rules.json rather than to any scenario. Nothing playable is lost.

As of the pinned sha only 2 of 29 errata rows change anything a player can
act on - `Gálmód's Escort` gaining `unique`, and a wording fix on `Ambushed at
the Campsite`. The other 27 differ only in databaseId/imageUrl/numberInPack:
corrected card IMAGES. The merge is written to be right regardless, because
the ratio is a fact about today's pin, not about the mechanism.

Excluded packs (EXCLUDED_PACKS)
-------------------------------
`Seastan Scratch Set` (584 rows, no quests) is upstream developer scratch
space, and `ALeP - Shire Cycle 6 Placeholder` is exactly what it says. Neither
is content; both would otherwise leak into the player-card DB or the picker.

Cycles (PACK_CYCLE)
-------------------
Taken from the plugin's own menu files on the alep branch
(jsons/zz-ALeP---*.menu.json), which is upstream's own grouping rather than
our guess. Four scenarios in the TSVs appear in no menu - `Flight to Michel
Delving`, `The Mathom House` (both real, evidently newer than the menus),
`The Withered Heath Nightmare`, and the placeholder - so they land in
"ALeP - Other" rather than being assigned a cycle we made up.
"""
import csv
import io
import os
import urllib.error
import urllib.request

SOURCE_FILE = os.path.join(os.path.dirname(__file__), "data", "alep.SOURCE.txt")
RAW = ("https://raw.githubusercontent.com/seastan/dragncards-lotrlcg-plugin/"
       "{sha}/tsvs/{name}")
API_BRANCH = ("https://api.github.com/repos/seastan/dragncards-lotrlcg-plugin/"
              "commits/alep")
API_TREE = ("https://api.github.com/repos/seastan/dragncards-lotrlcg-plugin/"
            "contents/tsvs?ref={sha}")

ERRATA_PACK = "ALeP - Errata Pack"

# Not content - see the module docstring.
EXCLUDED_PACKS = frozenset({
    "Seastan Scratch Set",
    "ALeP - Shire Cycle 6 Placeholder",
})

# Cycle label per pack, from the alep branch's own zz-ALeP---*.menu.json.
CYCLE_EORL = "ALeP - Children of Eorl & Oaths of the Rohirrim"
CYCLE_SHIRE = "ALeP - The Shire's Reckoning & Fell Summer"
CYCLE_POD = "ALeP - Print on Demand"
CYCLE_OTHER = "ALeP - Other"

PACK_CYCLE = {
    # Children of Eorl & Oaths of the Rohirrim (9 scenarios; the deluxe pack
    # itself carries three of them).
    "ALeP - Children of Eorl": CYCLE_EORL,
    "ALeP - The Aldburg Plot": CYCLE_EORL,
    "ALeP - Fire on the Eastemnet": CYCLE_EORL,
    "ALeP - The Gap of Rohan": CYCLE_EORL,
    "ALeP - The Glittering Caves": CYCLE_EORL,
    "ALeP - Mustering of the Rohirrim": CYCLE_EORL,
    "ALeP - Blood in the Isen": CYCLE_EORL,
    # The Shire's Reckoning & Fell Summer (6 scenarios; the deluxe carries
    # Pies for the Party, Sundown on the Shire, Secrets of the Old Forest).
    "ALeP - The Shire’s Reckoning": CYCLE_SHIRE,
    "ALeP - Strange News in Bree": CYCLE_SHIRE,
    "ALeP - Fangs in the Dark": CYCLE_SHIRE,
    "ALeP - The Brandywine Pursuit": CYCLE_SHIRE,
    # Print on Demand (5 scenarios).
    "ALeP - The Scouring of the Shire": CYCLE_POD,
    "ALeP - The Nine are Abroad": CYCLE_POD,
    "ALeP - The Siege of Erebor": CYCLE_POD,
    "ALeP - The Hobbit": CYCLE_POD,
    "ALeP - The Mirror of Galadriel": CYCLE_POD,
}

# The key that identifies "the same card" between the errata pack and the
# pack it corrects. See the module docstring for why each part is needed.
_ERRATA_KEY = ("name", "encounterSet", "side", "traits")


def _key(row):
    return tuple((row.get(k) or "").strip() for k in _ERRATA_KEY)


def apply_errata(rows):
    """Fold `ALeP - Errata Pack` rows into the rows they correct.

    Returns a new list: every base row replaced by its erratum where one
    exists, and no row from the errata pack surviving as its own card. Rows
    from other packs pass through untouched and in order.

    An errata row that matches nothing is DROPPED rather than added as a new
    card, and the count is returned for the caller to report - a row that
    matches nothing means the join key stopped holding upstream, and silently
    inventing a card from it would be worse than leaving it out. Pure.
    """
    errata, base = [], []
    for r in rows:
        (errata if (r.get("packName") or "").strip() == ERRATA_PACK
         else base).append(r)

    # Rules inserts repeat names across pages: ambiguous by construction, and
    # never part of a scenario. Drop them outright.
    errata = [e for e in errata if (e.get("type") or "").strip() != "Rules"]

    by_key = {}
    for e in errata:
        by_key.setdefault(_key(e), e)

    out, applied = [], set()
    for r in base:
        k = _key(r)
        e = by_key.get(k)
        if e is None:
            out.append(r)
            continue
        # Keep the base row's identity (databaseId/imageUrl/numberInPack are
        # the errata reprint's own) but take the corrected content. Grouping
        # downstream keys on databaseId, so preserving it keeps a corrected
        # face attached to the card it belongs to instead of splitting it off
        # as a second card.
        merged = dict(e)
        for col in ("databaseId", "setUuid", "numberInPack", "packName"):
            if col in r:
                merged[col] = r[col]
        out.append(merged)
        applied.add(k)

    return out, len(by_key) - len(applied)


def read_pin():
    """(sha, [tsv filename, ...]) from the pin file. The file list is pinned
    alongside the sha so an ordinary build is fully deterministic and needs
    no GitHub API call - only --refresh re-resolves either."""
    sha, names = None, []
    with open(SOURCE_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("sha="):
                sha = line.split("=", 1)[1]
            elif line.startswith("tsv="):
                names.append(line.split("=", 1)[1])
    if not sha:
        raise SystemExit("No sha in %s - run build_card_data.py --refresh once."
                         % SOURCE_FILE)
    return sha, names


def refresh_pin():
    """Re-resolve the alep branch HEAD and its TSV file list, and rewrite the
    pin file. Network; called only from build_card_data.py --refresh."""
    import json
    try:
        with urllib.request.urlopen(API_BRANCH) as resp:
            sha = json.loads(resp.read().decode())["sha"]
        with urllib.request.urlopen(API_TREE.format(sha=sha)) as resp:
            entries = json.loads(resp.read().decode())
    except (urllib.error.URLError, ValueError, KeyError) as e:
        raise SystemExit("Failed to resolve the alep branch: %s" % e)

    names = sorted(f["name"] for f in entries
                   if f["name"].endswith(".tsv") and f["name"] != "cardDb.tsv")
    os.makedirs(os.path.dirname(SOURCE_FILE), exist_ok=True)
    with open(SOURCE_FILE, "w", encoding="utf-8") as f:
        f.write("# A Long Extended Party card data - see tools/alep.py.\n")
        f.write("# The alep branch's per-pack TSVs; cardDb.tsv on that branch\n")
        f.write("# duplicates main's and is deliberately not listed.\n")
        f.write("url=%s\n" % RAW)
        f.write("sha=%s\n" % sha)
        for n in names:
            f.write("tsv=%s\n" % n)
    return sha, names


def fetch_rows(sha, names):
    """Every row from the pinned ALeP TSVs, excluding EXCLUDED_PACKS.

    A per-file fetch failure is fatal: unlike the optional Hall of Beorn
    enrichment, a half-fetched ALeP set would silently produce a catalog
    missing scenarios the picker offers, which is worse than not building.
    """
    rows = []
    for name in names:
        url = RAW.format(sha=sha, name=name)
        try:
            with urllib.request.urlopen(url) as resp:
                text = resp.read().decode("utf-8")
        except urllib.error.URLError as e:
            raise SystemExit("Failed to fetch ALeP TSV %s: %s" % (name, e))
        for row in csv.DictReader(io.StringIO(text), delimiter="\t",
                                  quoting=csv.QUOTE_NONE):
            if (row.get("packName") or "").strip() in EXCLUDED_PACKS:
                continue
            rows.append(row)
    return rows


def is_nightmare_pack(pack):
    """Whether an ALeP pack is a Nightmare deck. ALeP names these
    "ALeP - <Scenario> Nightmare" - no " - " before "Nightmare", unlike the
    official "<Scenario> - Nightmare" convention the picker's name rule
    keys on - so the kind has to be recognised from the pack instead. Pure."""
    return (pack or "").strip().endswith("Nightmare")


def pack_meta(pack):
    """{"cycle", "source", "date"} for an ALeP pack, for PACK_META. `source`
    is "alep", which is what quest_catalog.group_by_cycle already filters the
    Scenario Source screen on (the UI path exists; it has simply had no data
    until now). No release dates: ALeP publishes per-scenario rather than on
    FFG's pack schedule, and inventing them would sort the picker wrongly."""
    return {"cycle": PACK_CYCLE.get(pack, CYCLE_OTHER),
            "source": "alep",
            "date": None}
