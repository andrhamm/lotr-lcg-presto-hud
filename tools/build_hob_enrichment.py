"""Fetch Hall of Beorn's per-scenario "sets to gather" enrichment (the full
list of encounter sets a scenario draws from, beyond just its own named
set) into tools/data/enrichment.json - which, unlike tools/build_card_data.py's
docs/data/ output, is COMMITTED. The file holds only aggregated metadata (per
scenario, a sorted list of encounter-set NAMES - no printed card text, stats,
or any other verbatim third-party content), which CLAUDE.md's "What may be
committed" allows in git; the raw API responses it is aggregated from stay in
the gitignored cache below. See docs/superpowers/plans/2026-07-24-catalog-
enrichment.md, Task 1.

Because it is committed, this fetcher is a NO-OP by default: main() bails out
early via build_card_data.needs_refresh() whenever --out already exists, so a
clean checkout, a Pages build, or an absent-minded rerun never re-hits the API.
Regenerating is an explicit, local, occasional act: --refresh. Nothing in CI
runs this any more (see .github/workflows/pages.yml) - a cold run costs 40+
minutes, which is exactly why the output is in git instead.

Hall of Beorn's Export/Search endpoint (https://hallofbeorn.com/Export/
Search?EncounterSet=<name>&CardType=Quest) returns every quest-stage card
for one encounter set; each card's "EncounterInfo" carries the set's own
name plus "IncludedEncounterSets" - e.g. Passage Through Mirkwood's stage
cards list ["Dol Guldur Orcs", "Spiders of Mirkwood"], so the union across
all of a scenario's stage cards is the scenario's full gather list (see
included_sets()). Names sometimes carry a qualifier suffix like
" (Campaign)" that our catalog's set names don't - stripped before matching.

This is a second, separate enrichment source layered onto the M4-A catalog
(tools/build_card_data.py); it is best-effort and optional throughout: a
network failure or a name the API has no data for is logged and skipped,
never raised past build() (mirrors build_icons.py's "optional data source"
posture) - only a bad/missing --index catalog (nothing to enrich) raises a
friendly SystemExit from the CLI. Every fetch is cached to
<cache_dir>/<slug>.json (default tools/data/hob_cache/, gitignored - it
holds verbatim third-party card data) so repeat --refresh runs don't re-hit
the API; a cache hit skips the network call and its rate-limit delay entirely.

Politeness: requests are strictly serial (one scenario at a time, driven by
a plain for-loop - never concurrent) with a small delay after each real
network fetch (never after a cache hit). The endpoint is also documented
(see the plan's Verified facts) as paginated at 50 rows for broad/unfiltered
queries; empirically a single EncounterSet's quest-stage count never gets
close to that limit, and no working page-number query parameter was found
during development (an ASP.NET-conventional "&Page=2" was tried and had no
effect on the response - see the Task 1 report), so fetch_scenario() does
not attempt to fetch further pages. It does log a warning if a response
ever comes back at exactly 50 rows (the one signal available that a result
might be truncated), so a silent truncation would at least be visible in
build output rather than invisible.
"""
import argparse
import datetime
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from build_card_data import needs_refresh, slugify

SEARCH_URL = "https://hallofbeorn.com/Export/Search?EncounterSet=%s&CardType=Quest"
USER_AGENT = ("lotr-lcg-presto-hud/build_hob_enrichment "
              "(+https://github.com/andrhamm/lotr-lcg-presto-hud)")
TIMEOUT = 45  # seconds - this endpoint is slow (~20s observed), not flaky
PAGE_SIZE = 50  # see module docstring's Politeness section

DEFAULT_INDEX = os.path.join("docs", "data", "index.json")
DEFAULT_OUT = os.path.join("tools", "data", "enrichment.json")
DEFAULT_CACHE = os.path.join("tools", "data", "hob_cache")

_TRAILING_PAREN = re.compile(r"\s*\([^)]*\)\s*$")


def _normalize_set_name(name):
    """Strip a trailing parenthetical qualifier (" (Campaign)", "
    (Nightmare)", ...) and surrounding whitespace from one encounter-set
    name; "" (falsy in, or empty after stripping) stays "". Only one
    trailing group is stripped - no known set name needs more."""
    name = (name or "").strip()
    if not name:
        return ""
    return _TRAILING_PAREN.sub("", name).strip()


def included_sets(cards):
    """The sorted, de-duplicated, normalized union of every encounter set
    named across `cards` (one scenario's raw Hall of Beorn quest-card
    array, see fetch_scenario): each card's EncounterInfo.EncounterSet plus
    EncounterInfo.IncludedEncounterSets. Pure, host-tested. Cards missing
    "EncounterInfo" (or with an empty one) simply contribute nothing - []
    in, [] out, never raises."""
    names = set()
    for card in cards or []:
        info = card.get("EncounterInfo") or {}
        candidates = [info.get("EncounterSet")]
        candidates.extend(info.get("IncludedEncounterSets") or [])
        for raw in candidates:
            norm = _normalize_set_name(raw)
            if norm:
                names.add(norm)
    return sorted(names)


def fetch_scenario(name, cache_dir, delay=0.5):
    """The raw quest-card array for encounter set `name`: reads
    <cache_dir>/<slug>.json when present (no network call, no delay),
    else GETs Hall of Beorn's Export/Search, caches the parsed result, and
    sleeps `delay` seconds before returning (politeness - see module
    docstring). Network only, not host-tested.

    A valid "no cards match this name" response is Hall of Beorn's own
    literal JSON string "Search returned no results" (verified empirically
    - see the Task 1 report) rather than an empty array or an HTTP error;
    normalized to [] here either way, and still cached (a confirmed miss is
    worth remembering so the next build doesn't re-ask). A real transport
    failure (DNS/timeout/HTTP error/malformed JSON) raises instead - never
    cached, so it's retried on the next run - and is the caller's (build's)
    job to catch, log, and count as a skip."""
    slug = slugify(name)
    cache_path = os.path.join(cache_dir, slug + ".json")
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    url = SEARCH_URL % urllib.parse.quote(name, safe="")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    cards = payload if isinstance(payload, list) else []
    if len(cards) >= PAGE_SIZE:
        print("build_hob_enrichment: %r returned %d cards (>= page size %d) "
              "- result may be truncated, see module docstring"
              % (name, len(cards), PAGE_SIZE))

    os.makedirs(cache_dir, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False)
    if delay:
        time.sleep(delay)
    return cards


def build(index_path, out_path, cache_dir, limit=None, delay=0.5):
    """For every kind=="quest" scenario in the catalog index at
    `index_path`, resolve its included sets (fetch_scenario + included_sets)
    and write {"generated", "source", "scenarios": {slug: {"includedSets":
    [...]}}}} to `out_path`. `limit` caps how many scenarios are processed
    (for a quick --limit smoke run); `delay` is passed through to
    fetch_scenario.

    Never raises for a single scenario's failure - a fetch exception (bad
    name, transport error, timeout, ...) or an empty resolved set (the
    "Search returned no results" case, or a scenario with no EncounterInfo
    at all) is logged and counted as skipped, not fatal; the catalog build
    this feeds must still succeed with whatever enrichment could be
    gathered (see the plan's Global Constraints - enrichment is optional).
    Returns a small summary dict ({"resolved", "skipped", "total"}) for the
    CLI to report."""
    with open(index_path, encoding="utf-8") as f:
        index = json.load(f)
    scenarios = [s for s in index.get("scenarios", []) if s.get("kind") == "quest"]
    if limit is not None:
        scenarios = scenarios[:limit]

    out_scenarios = {}
    resolved = skipped = 0
    for scn in scenarios:
        slug, name = scn.get("slug"), scn.get("name")
        if not slug or not name:
            skipped += 1
            continue
        try:
            cards = fetch_scenario(name, cache_dir, delay=delay)
        except Exception as e:
            print("build_hob_enrichment: fetch failed for %r (%s) - skipping"
                  % (name, e))
            skipped += 1
            continue
        sets = included_sets(cards)
        if not sets:
            print("build_hob_enrichment: no gather-list data for %r - skipping"
                  % name)
            skipped += 1
            continue
        out_scenarios[slug] = {"includedSets": sets}
        resolved += 1

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated": datetime.date.today().isoformat(),
            "source": "hallofbeorn.com/Export/Search",
            "scenarios": out_scenarios,
        }, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    summary = {"resolved": resolved, "skipped": skipped, "total": len(scenarios)}
    print("build_hob_enrichment: resolved %d, skipped %d (of %d quest scenarios) -> %s"
          % (resolved, skipped, len(scenarios), out_path))
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Fetch Hall of Beorn sets-to-gather enrichment for the "
                     "quest catalog.")
    ap.add_argument("--index", default=DEFAULT_INDEX,
                     help="catalog index.json to read scenarios from "
                          "(default: %s - run tools/build_card_data.py first)"
                          % DEFAULT_INDEX)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--refresh", action="store_true",
                     help="re-fetch and overwrite --out even though it already "
                          "exists. Without this, an existing --out is left "
                          "alone and nothing is fetched - see needs_refresh().")
    ap.add_argument("--limit", type=int, default=None,
                     help="only process the first N quest scenarios (quick "
                          "smoke run)")
    ap.add_argument("--delay", type=float, default=0.5,
                     help="seconds to sleep after each real network fetch "
                          "(default 0.5; not applied on cache hits)")
    args = ap.parse_args(argv)

    if not needs_refresh(args.out, args.refresh):
        print("build_hob_enrichment: %r already present (committed derived "
              "data - see CLAUDE.md's Card data section); nothing fetched. "
              "Pass --refresh to rebuild it." % args.out)
        return 0

    if not os.path.exists(args.index):
        raise SystemExit("No catalog index at %r - run tools/build_card_data.py "
                          "first." % args.index)
    build(args.index, args.out, args.cache, limit=args.limit, delay=args.delay)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
