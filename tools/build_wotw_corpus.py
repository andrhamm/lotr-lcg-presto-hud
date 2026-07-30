"""Fetch Warriors of the West blog posts into a local, GITIGNORED research
corpus under research/wotw/.

The second source for the tip distillation, alongside Vision of the Palantir
(tools/build_votp_corpus.py). It is complementary rather than redundant:

  - VotP's quest spotlights describe a scenario in STANDARD mode.
  - Warriors of the West is mostly NIGHTMARE - about 15 of its ~48 posts are
    "Nightmare review: <scenario>", plus turn-by-turn reports and a running
    mega-campaign - so it covers the mode the other corpus barely touches, and
    covers it as played rather than as previewed.

Both are WordPress, so the extraction machinery is shared outright with
build_votp_corpus rather than reimplemented: the post body is the single
`div.entry-content`, located with a balanced-depth parser and converted by
pandoc.

DATA POLICY (CLAUDE.md, "What may be committed"). Everything this writes is
VERBATIM third-party article prose, so NOTHING it produces is committed:

  - tools/data/wotw_cache/   raw HTML       gitignored
  - research/wotw/           markdown       gitignored, vault-side so it can
                                            be read in Obsidian beside
                                            research/votp/ and quests/

Only text we write OURSELVES from reading it reaches
tools/data/tips_distilled.json, and from there docs/data/tips.json. This tool
never touches tips.json.

The post list comes from the blog's own sitemap, so no URL here is guessed.
Slugs are matched to catalog scenarios by longest-substring: the blog's slugs
carry a prefix and often two scenarios ("mega-campaign-part-5-angmar-awakened-
across-the-ettenmoors-treachery-of-rhudaur"), so a post can map to more than
one, and posts that map to none (deck tech, spoiler round-ups, "about") are
kept but filed unmatched rather than dropped - they are still readable
context.

Usage:
    python3 tools/build_wotw_corpus.py --refresh   # fetch, then convert
    python3 tools/build_wotw_corpus.py             # convert what is cached
    python3 tools/build_wotw_corpus.py --list      # show the slug -> scenario
                                                   # mapping, fetch nothing
"""
import argparse
import glob
import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import quest_catalog
# The WordPress extraction is identical for both blogs; one implementation.
from build_votp_corpus import convert

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITEMAP = "https://warriorsofthewestblog.wordpress.com/sitemap.xml"
CACHE_DIR = os.path.join(ROOT, "tools", "data", "wotw_cache")
OUT_DIR = os.path.join(ROOT, "research", "wotw")
DELAY = 1.0          # polite: a small personal blog, not an API
TIMEOUT = 60

# Pages that are not posts, so not worth fetching.
SKIP_PATHS = ("/about/", "/links-and-resources/")

# This theme's <h1> is the SITE name ("Warriors of the West"), so the default
# <h1> lookup would file all 45 posts under one title. The post title is the
# .entry-title element.
TITLE_RE = r'<[^>]*class="[^"]*entry-title[^"]*"[^>]*>(.*?)</'


def post_urls(sitemap_xml):
    """Every post URL in the sitemap, in sitemap order. Dated paths only -
    /YYYY/MM/DD/slug/ - which excludes the standalone pages and the site
    root without needing a list of them."""
    urls = re.findall(r"<loc>([^<]+)</loc>", sitemap_xml)
    out = []
    for u in urls:
        if any(p in u for p in SKIP_PATHS):
            continue
        if re.search(r"/\d{4}/\d{2}/\d{2}/[^/]+/?$", u):
            out.append(u)
    return out


def slug_of(url):
    """Last path segment - the WordPress post slug, and the cache filename."""
    return url.rstrip("/").rsplit("/", 1)[-1]


def scenario_slugs(index_path=None):
    """Every pickable scenario's slug, longest first so the substring match
    prefers "the-battle-of-carn-dum" over a shorter slug inside it."""
    index_path = index_path or os.path.join(ROOT, "docs", "data", "index.json")
    if not os.path.exists(index_path):
        return []
    with open(index_path, encoding="utf-8") as f:
        scns = json.load(f)["scenarios"]
    slugs = {s["slug"] for s in scns
             if s.get("stageCount", 0) > 0 and s.get("kind") != "nightmare"}
    return sorted(slugs, key=len, reverse=True)


def _squash(slug):
    """Slug with its separators removed, so two spellings of the same name
    meet: we build "helm-s-deep" from the apostrophe, the blog writes
    "helms-deep"; both squash to "helmsdeep"."""
    return slug.replace("-", "")


def match_scenarios(post_slug, slugs):
    """Catalog slugs named in this post slug, longest-first and
    non-overlapping.

    A post slug carries a prefix and sometimes two scenarios
    ("...across-the-ettenmoors-treachery-of-rhudaur"), so this returns a list.
    Consuming each match keeps a long slug from also reporting the shorter one
    nested inside it.

    Matching is on the SQUASHED form, and also on the slug minus a leading
    "the-", because the blog's own titles differ from the catalog's two ways:
    possessives ("helms-deep" vs our "helm-s-deep") and dropped articles
    ("review-siege-of-annuminas" vs our "the-siege-of-annuminas"). Both are
    spelling, not identity. What it will NOT bridge is the author spelling a
    name differently - "deadmans-dike" for "Deadmen's Dike" - and that is
    correct: guessing there would be guessing.
    """
    hay = _squash(post_slug)
    found = []
    for slug in slugs:
        if not slug:
            continue
        for cand in (_squash(slug),
                     _squash(slug[4:]) if slug.startswith("the-") else None):
            if cand and len(cand) > 4 and cand in hay:
                found.append(slug)
                hay = hay.replace(cand, "|")
                break
    return found


def fetch_all(urls, cache_dir, delay=DELAY, force=False):
    os.makedirs(cache_dir, exist_ok=True)
    got = skipped = failed = 0
    for url in urls:
        path = os.path.join(cache_dir, slug_of(url) + ".html")
        if os.path.exists(path) and not force:
            skipped += 1
            continue
        req = urllib.request.Request(
            url, headers={"User-Agent": "lotr-lcg-presto-hud research corpus"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                html = r.read().decode("utf-8", "replace")
        except Exception as exc:                    # noqa: BLE001
            print("  ! %s (%s)" % (slug_of(url), exc))
            failed += 1
            continue
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        got += 1
        time.sleep(delay)
    return got, skipped, failed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refresh", action="store_true",
                    help="fetch the sitemap and any post not already cached")
    ap.add_argument("--force", action="store_true",
                    help="with --refresh, re-fetch even cached posts")
    ap.add_argument("--list", action="store_true",
                    help="print the post -> scenario mapping and exit")
    ap.add_argument("--cache", default=CACHE_DIR)
    ap.add_argument("--out", default=OUT_DIR)
    args = ap.parse_args(argv)

    slugs = scenario_slugs()
    if not slugs:
        print("build_wotw_corpus: no docs/data/index.json - run "
              "tools/build_card_data.py first")
        return 1

    if args.refresh or args.list:
        print("Fetching %s ..." % SITEMAP)
        req = urllib.request.Request(
            SITEMAP, headers={"User-Agent": "lotr-lcg-presto-hud research corpus"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                xml = r.read().decode("utf-8", "replace")
        except Exception as exc:                    # noqa: BLE001
            print("build_wotw_corpus: sitemap fetch failed (%s)" % exc)
            return 1
        urls = post_urls(xml)
        print("  %d posts in the sitemap" % len(urls))
    else:
        urls = []

    if args.list:
        hit = miss = 0
        for u in urls:
            s = slug_of(u)
            m = match_scenarios(s, slugs)
            if m:
                hit += 1
            else:
                miss += 1
            print("  %-72s %s" % (s, ", ".join(m) or "-"))
        print("\n%d posts name a catalog scenario, %d do not "
              "(deck tech, spoiler round-ups, campaign framing)" % (hit, miss))
        return 0

    if args.refresh:
        got, skipped, failed = fetch_all(urls, args.cache, force=args.force)
        print("  fetched %d, already cached %d, failed %d"
              % (got, skipped, failed))

    cached = sorted(glob.glob(os.path.join(args.cache, "*.html")))
    if not cached:
        print("build_wotw_corpus: nothing cached yet - run with --refresh")
        return 1

    wrote = empty = 0
    for path in cached:
        slug, size, err = convert(path, args.out, tag="wotw",
                                  title_re=TITLE_RE)
        if err or not size:
            empty += 1
            print("  ! %s: %s" % (slug, err or "empty"))
        else:
            wrote += 1
    print("Wrote %d markdown files to %s (%d skipped)"
          % (wrote, os.path.relpath(args.out, ROOT), empty))

    matched = {}
    for path in cached:
        s = os.path.splitext(os.path.basename(path))[0]
        for scn in match_scenarios(s, slugs):
            matched.setdefault(scn, []).append(s)
    print("%d scenarios have at least one Warriors of the West post"
          % len(matched))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
