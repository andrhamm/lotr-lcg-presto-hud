"""Aggregate scenario PLAY ORDER from Hall of Beorn into
tools/data/scenario_order.json.

WHY THIS EXISTS: nothing in the card data encodes play order.

  - `releaseDate` cannot do it. A deluxe box ships three quests in one month,
    so EVERY cycle has date ties - 13 of 13 at the time of writing.
  - The TSV's `numberInPack` is card-SHEET order, not play order. For the Core
    Set it gives Passage (119), Escape (123), Journey (126), which puts Escape
    before Journey. Checked, not assumed.

So the order comes from Hall of Beorn's Scenarios listing, which presents each
product's quests in play order. The output is a product -> ordered-names table:
derived metadata, no printed card text, so it is COMMITTED under the same rule
as tools/data/enrichment.json (CLAUDE.md, "What may be committed").

Like the other derived-data fetchers this is a **no-op when its output already
exists** - a clean checkout and a Pages build must never re-scrape a
third-party site. Regenerating is an explicit local act:

    python3 tools/build_scenario_order.py --refresh

VALIDATION. `--refresh` re-asserts the cross-check that made this table
trustworthy in the first place: with the order applied, every sequenced cycle
comes out monotonically non-decreasing by `releaseDate` - a field this table
never looks at. A regression there means Hall of Beorn's page changed shape and
the scrape silently mis-parsed, which is exactly the failure a fetcher like
this should not ship quietly.
"""
import argparse
import json
import os
import sys
import unicodedata
import urllib.request
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import quest_catalog

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(ROOT, "tools", "data", "scenario_order.json")
SOURCE = "https://hallofbeorn.com/LotR/Scenarios/"

# Cycles that are NOT a play sequence, so the date cross-check does not apply.
# "Standalone/PoD" is a grab-bag of unrelated products - Gen Con decks,
# fellowship decks, custom scenario kits - which Hall of Beorn groups by
# product rather than by date. Its numbering is a row index, not an order to
# play them in.
UNSEQUENCED_CYCLES = ("Standalone/PoD",)

# Our catalog's name -> Hall of Beorn's, for the two that no normalization
# rule can bridge. Everything else matches on the shared key below.
ALIASES = {
    # We carry the ORIGINAL Core Set name; FFG renamed the quest for the
    # Revised Core Set. Hall of Beorn's own difficulty-rating link on its
    # "Journey Along the Anduin" row points at
    # "...#core-set-quest-journey-down-the-anduin" - the identity is stated by
    # the source itself, not inferred by us.
    "journey-down-the-anduin": "journey-along-the-anduin",
    # A typo in the upstream DragnCards TSV: "Celembrimbor" for "Celebrimbor".
    "celembrimbor-s-secret": "celebrimbor-s-secret",
}


def match_key(name):
    """Shared key for one scenario across the two sources.

    Folds diacritics (we carry "Amon Din", Hall of Beorn "Amon Dîn") and drops
    a leading "The" (we carry "Fords of Isen", they "The Fords of Isen"). Both
    differences are pure spelling; nine scenarios need the first and three the
    second. Dropping "the-" collides only between a quest and its own
    "(Campaign)" variant, which resolve to the same position anyway.
    """
    n = unicodedata.normalize("NFKD", name or "")
    n = "".join(c for c in n if not unicodedata.combining(c))
    slug = quest_catalog.slugify(n)
    if slug in ALIASES:
        return ALIASES[slug]
    if slug.startswith("the-"):
        slug = slug[4:]
    return ALIASES.get(slug, slug)


class _Scrape(HTMLParser):
    """Hall of Beorn's Scenarios page: an <h3> per product, then one
    /LotR/Scenarios/<name> link per quest IN PLAY ORDER. Other links on the
    row (the difficulty rating points off-site) are ignored by prefix."""

    def __init__(self):
        HTMLParser.__init__(self)
        self.products = []
        self._heading = False
        self._link = None
        self._buf = ""

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._heading, self._buf = True, ""
        elif tag == "a":
            href = dict(attrs).get("href", "")
            if href.startswith("/LotR/Scenarios/"):
                self._link, self._buf = href, ""

    def handle_data(self, data):
        if self._heading or self._link is not None:
            self._buf += data

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self._heading:
            title = " ".join(self._buf.split())
            self._heading = False
            if title and title.lower() != "scenarios":
                self.products.append({"product": title, "scenarios": []})
        elif tag == "a" and self._link is not None:
            name = " ".join(self._buf.split())
            self._link = None
            if name and self.products:
                self.products[-1]["scenarios"].append(name)


def fetch(url=SOURCE):
    req = urllib.request.Request(url, headers={"User-Agent": "lotr-lcg-presto-hud"})
    with urllib.request.urlopen(req, timeout=60) as r:
        html = r.read().decode("utf-8", "replace")
    p = _Scrape()
    p.feed(html)
    return [x for x in p.products if x["scenarios"]]


def ranks(products):
    """match_key -> global position. Hall of Beorn lists products in
    chronological order, so one flat sequence orders scenarios correctly even
    where our cycles span several of its products (The Ring-maker holds both
    "The Voice of Isengard" and "The Ring-maker")."""
    out, i = {}, 0
    for prod in products:
        for name in prod["scenarios"]:
            k = match_key(name.replace(" (Campaign)", ""))
            out.setdefault(k, i)
            i += 1
    return out


def check_monotonic(products, index_scenarios):
    """Every sequenced cycle must come out non-decreasing by releaseDate once
    the order is applied. Returns a list of complaint strings (empty is good).

    Cross-checks the table against a field it never reads. A cycle that goes
    backwards means the scrape mis-parsed, or Hall of Beorn regrouped a
    product - either way the table should not ship unexamined.

    Skips cycles with any unordered or undated member, and the grab-bag
    cycles named in UNSEQUENCED_CYCLES.
    """
    rank = ranks(products)
    bad = []
    for group in quest_catalog.group_by_cycle(index_scenarios, "official"):
        if group["cycle"] in UNSEQUENCED_CYCLES:
            continue
        rows = sorted(group["scenarios"],
                      key=lambda s: (rank.get(match_key(s["name"]), 10 ** 6),
                                     s.get("name") or ""))
        dates = [s.get("releaseDate") for s in rows]
        if any(d is None for d in dates):
            continue
        if any(match_key(s["name"]) not in rank for s in rows):
            continue
        if dates != sorted(dates):
            bad.append("%s: %s" % (group["cycle"], " ".join(dates)))
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refresh", action="store_true",
                    help="re-scrape Hall of Beorn and rewrite the table")
    args = ap.parse_args(argv)

    # Imported here, not at module scope: build_card_data imports THIS module
    # for match_key(), so a top-level import back would be a cycle.
    from build_card_data import needs_refresh

    if not needs_refresh(OUT_PATH, args.refresh):
        print("build_scenario_order: %s already exists, nothing to do "
              "(--refresh to re-scrape)" % os.path.relpath(OUT_PATH, ROOT))
        return 0

    print("Fetching %s ..." % SOURCE)
    try:
        products = fetch()
    except Exception as exc:                       # noqa: BLE001 - any failure
        print("build_scenario_order: fetch failed (%s); leaving the committed "
              "table alone" % exc)
        return 1
    if len(products) < 20:
        print("build_scenario_order: only %d products parsed - the page shape "
              "probably changed; refusing to overwrite" % len(products))
        return 1

    index_path = os.path.join(ROOT, "docs", "data", "index.json")
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            scns = json.load(f)["scenarios"]
        bad = check_monotonic(products, scns)
        for line in bad:
            print("build_scenario_order: WARNING cycle not date-monotonic: %s" % line)
        if not bad:
            print("build_scenario_order: every sequenced cycle is "
                  "date-monotonic under this order")
    else:
        print("build_scenario_order: no docs/data/index.json yet, skipping "
              "the date cross-check")

    prev = {}
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, encoding="utf-8") as f:
            prev = json.load(f)
    payload = dict(prev)
    payload["source"] = SOURCE
    payload["products"] = products
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print("Wrote %d scenarios in %d products to %s"
          % (sum(len(p["scenarios"]) for p in products), len(products),
             os.path.relpath(OUT_PATH, ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
