"""Pack the quest-picker index into a binary blob the device can read lazily.

WHY, measured on the device (Presto, RP2350, MicroPython 1.26):

    json.loads(index.json)          429 ms   131,036 B
    json.loads(slim JSON rows)       73 ms    30,705 B
    struct decode, all 154 rows      33 ms    10,131 B
    struct scan, cycle ids only       6 ms    (same file)

MicroPython's JSON decoder is pure Python on this build (`type(json.loads)` is
`<class 'function'>`), while `struct.unpack_from` is C - which is why binary
wins outright here rather than marginally. ~87% of the 429 ms is decode and
object allocation, not I/O, so the win comes from not decoding what a screen
does not read: the Pick Cycle list never materialises a single string.

Two independent savings, both taken:
  * ship less  - 396 index rows, only ~154 pickable (group_by_cycle filters
    stageCount > 0). `counts` alone is 23 KB with zero runtime readers, and
    `packs[]`, `gatherCount`, `sailing` and `modes` have none either.
  * encode tight - fixed-width records plus one deduped string table.

FORMAT (all little-endian):

    magic   4s   b"LCG1"
    nrec    H    number of scenario records
    nstr    H    number of strings in the table
    stroff  I    byte offset of the string table
    records nrec * RECORD_FMT, sorted by slug for binary search
    strings nstr * (H length, then that many UTF-8 bytes)

A record holds string IDs, not strings, so a scan that only needs cycle ids
touches no text at all.

Output is generated and gitignored, exactly like the rest of docs/data/ - the
.gitignore ignores `docs/data/*` with a single `!docs/data/tips.json`
allow-list. Never hand-edit it.
"""
import argparse
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "docs", "data")

MAGIC = b"LCG1"
HEADER_FMT = "<4sHHI"
# slug, name, pack, cycle, date : string ids ("date" is the "YYYY-MM"
#                            releaseDate; carrying it lets the pack feed the
#                            existing, already host-tested group_by_cycle
#                            instead of reimplementing the grouping)
# source, kind            : small enums
# stage_count, order      : ints (order 0xFFFF == unranked, sorts last)
# max_threat              : the worst printed threat in the gather pool
# flags                   : bit 0 hasNightmare, bit 1 hasXThreat, bit 2 sailing
RECORD_FMT = "<HHHHHBBHHHB"
RECORD_SIZE = struct.calcsize(RECORD_FMT)

SOURCES = ["official", "alep"]
KINDS = ["quest", "encounter", "nightmare", "campaign"]


def pickable(entry):
    """The rows the picker can actually offer.

    Mirrors quest_catalog.group_by_cycle's own filter: a scenario with no
    stages has nothing to play. 242 of 396 rows are parsed and discarded on
    the device today purely to be filtered back out here.
    """
    return (entry.get("stageCount") or 0) > 0


def build(index):
    strings = []
    ids = {}

    def sid(v):
        v = v or ""
        i = ids.get(v)
        if i is None:
            i = len(strings)
            ids[v] = i
            strings.append(v)
        return i

    rows = [e for e in index.get("scenarios", []) if pickable(e)]
    # Sorted by slug so the device can binary-search without an index.
    rows.sort(key=lambda e: e.get("slug") or "")

    recs = bytearray()
    for e in rows:
        flags = ((1 if e.get("hasNightmare") else 0)
                 | (2 if e.get("hasXThreat") else 0)
                 | (4 if e.get("sailing") else 0))
        order = e.get("order")
        recs += struct.pack(
            RECORD_FMT,
            sid(e.get("slug")), sid(e.get("name")),
            sid(e.get("pack")), sid(e.get("cycle")),
            sid(e.get("releaseDate")),
            SOURCES.index(e["source"]) if e.get("source") in SOURCES else 0,
            KINDS.index(e["kind"]) if e.get("kind") in KINDS else 0,
            min(0xFFFF, e.get("stageCount") or 0),
            0xFFFF if order is None else min(0xFFFF, order),
            min(0xFFFF, e.get("maxCardThreat") or 0),
            flags)

    tbl = bytearray()
    for s in strings:
        b = s.encode("utf-8")
        tbl += struct.pack("<H", len(b)) + b

    header = struct.pack(HEADER_FMT, MAGIC, len(rows), len(strings),
                         struct.calcsize(HEADER_FMT) + len(recs))
    return bytes(header + recs + tbl), len(rows), len(strings)


def assert_no_slug_collisions(index):
    """`players/` and `scenarios/` both key by slugify() and DO collide.

    53 of 107 packs share a slug with a scenario - half of them, and
    content-plausibly (`a-journey-to-rhosgobel` is both a quest and a player
    pack). A flat keyspace would alias them as *wrong data*, not a crash, so
    the client keys by a typed tuple. This records the count so a future data
    change cannot quietly make it worse without anyone noticing.
    """
    scen = {e.get("slug") for e in index.get("scenarios", [])}
    packs = {p.get("slug") for p in index.get("packs", [])}
    both = sorted(scen & packs)
    print("slug collisions between scenarios/ and players/: %d" % len(both))
    if both:
        print("  e.g. %s" % ", ".join(both[:4]))
    return both


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default=DATA, help="docs/data directory")
    ap.add_argument("--out", default=None, help="output .bin path")
    args = ap.parse_args(argv)

    src = os.path.join(args.data, "index.json")
    if not os.path.exists(src):
        raise SystemExit("no index.json at %s - run build_card_data.py first" % src)
    with open(src) as f:
        index = json.load(f)

    blob, nrec, nstr = build(index)
    out = args.out or os.path.join(args.data, "catalog.bin")
    with open(out, "wb") as f:
        f.write(blob)

    total = len(index.get("scenarios", []))
    raw = os.path.getsize(src)
    print("catalog.bin: %d of %d scenarios (%d dropped as unpickable)"
          % (nrec, total, total - nrec))
    print("  %d strings, %d B  (index.json is %d B -> %.1fx smaller)"
          % (nstr, len(blob), raw, raw / float(len(blob))))
    assert_no_slug_collisions(index)
    return 0


if __name__ == "__main__":
    sys.exit(main())
