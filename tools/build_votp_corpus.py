"""Convert the cached Vision of the Palantir article HTML into readable
markdown under tools/data/votp_md/ - a local, GITIGNORED research corpus.

Why this exists: tools/build_tips.py's mechanical summarizer reads the raw
HTML and emits almost nothing (see its docstring's Copyright posture - only
sentences matching one hardcoded fact-pattern survive). The articles
themselves are full of exactly the strategy advice the HUD's tips should
carry, so the useful first step is to get them into a form that can actually
be read and distilled, rather than regex-scraped.

Same data-policy posture as tools/data/tips_cache/ (see CLAUDE.md's "What may
be committed"): this output is VERBATIM third-party article prose, so it is
never committed - it is a working corpus, and only text we write ourselves
from reading it ever reaches docs/data/tips.json.

Extraction is narrowed to the article body by CSS selector: WordPress wraps
the post content in exactly one `<div class="entry-content">` per page
(verified: 113 of 113 cached files have exactly one), which excludes the
site header, nav, sidebar, comment thread, and footer. Within that div a few
WordPress/Jetpack furniture blocks are dropped by class (sharing buttons,
"Related" posts, author bio).

The div is located with a balanced-depth HTMLParser rather than a regex -
the body nests many <div>s, so `<div class="entry-content">(.*?)</div>` would
truncate at the first inner close tag. The extracted fragment is then handed
to pandoc (`-f html -t gfm --wrap=none`) for the actual markdown conversion.

Usage:
    python3 tools/build_votp_corpus.py              # convert every cached page
    python3 tools/build_votp_corpus.py --slug the-old-forest
    python3 tools/build_votp_corpus.py --check      # report only, write nothing
"""
import argparse
import glob
import html.parser
import os
import re
import shutil
import subprocess
import sys

DEFAULT_CACHE = os.path.join("tools", "data", "tips_cache")
# Vault-side, not under tools/data/: the repo root is an Obsidian vault (see
# .obsidian/, quests/, design/, TODO.md), and this corpus exists to be READ -
# by a person in Obsidian and by the distillation pass - so it lives where
# the other notes live. Still gitignored: it is verbatim article prose.
DEFAULT_OUT = os.path.join("research", "votp")

# -- EXTRA: articles the plain slug match in build_tips.py never reaches ------
#
# build_tips.match_article only tries a catalog slug and its possessive
# variant (deliberately - see its docstring on why guessing suffixed URLs is
# worse than no match). That leaves three kinds of article unfetched, all
# resolved here BY HAND against the sitemap and the site's own hub pages, so
# every entry is an observed URL rather than a guess.
#
# Key = the filename the corpus stores it under. Where a catalog scenario
# exists, that is the CATALOG slug, so the corpus lines up with docs/data/
# index.json; otherwise it is the article's own slug.

# (1) Second-edition rewrites. VotP redid the early cycles from 2020 on with
#     a much fuller template (per-quest-card sections, "Optimal starting
#     threat", "Tips and Tricks"). The plain slug still points at the thin
#     2018 original, so these override it. Verified: every cached base below
#     carries a 2018 source URL, while Passage through Mirkwood - which took
#     the clean slug for its rewrite - carries 2020.
SECOND_EDITIONS = {
    "a-journey-to-rhosgobel": "a-journey-to-rhosgobel-3",
    "conflict-at-the-carrock": "conflict-at-the-carrock-2",
    "escape-from-dol-guldur": "escape-from-dol-guldur-2",
    "return-to-mirkwood": "return-to-mirkwood-2",
    "the-dead-marshes": "the-dead-marshes-2",
    "the-hills-of-emyn-muil": "the-hills-of-emyn-muil-2",
    "the-hunt-for-gollum": "the-hunt-for-gollum-2",
}

# (2) Catalog scenarios whose VotP article sits at a different slug. Left
#     side is the catalog slug (docs/data/index.json), right side the
#     article slug found in the sitemap.
SLUG_FIXES = {
    # VotP prefixes the definite article; our catalog name does not.
    "temple-of-doom": "the-temple-of-doom",
    "temple-of-the-deceived": "the-temple-of-the-deceived",
    # NOT "-2" here: that slug is a Quest-of-the-Week *results* post
    # (attempts/wins tables), not a spotlight. Verified by its body.
    "crossings-of-poros": "the-crossings-of-poros",
    "fords-of-isen": "the-fords-of-isen",
    # Known upstream misspelling in the card DB's own scenario name
    # ("Celembrimbor" for "Celebrimbor") - see build_tips.py's docstring.
    "celembrimbor-s-secret": "celebrimbors-secret",
    # ALeP (fan-made, see tools/alep.py). VotP drops the leading article
    # that the catalog's own scenario name carries.
    "the-battle-for-the-beacon": "battle-for-the-beacon",
    # The Core Set's scenario 2 is printed "Journey Down the Anduin"; VotP
    # titles its article after the ENCOUNTER SET, "Journey Along the
    # Anduin". Both names exist separately in our catalog (the encounter
    # set is its own entry), which is why no slug match was possible.
    # Second edition, per (1).
    "journey-down-the-anduin": "journey-along-the-anduin-2",
}

# (3) Articles with no catalog scenario of their own, kept as background for
#     the distillation pass. Encounter-set reviews cover cards that recur
#     across many quests; the ALEP posts cover the fan-made A Long Extended
#     Party scenarios, which the DragnCards catalog does not carry at all
#     (so they cannot become in-app tips until it does - they are research).
#     Discovered from the site's own hub pages, not guessed.
BACKGROUND = [
    "encounter-set-review-passage-through-mirkwood",
    "encounter-set-review-dol-guldur-orcs",
    "encounter-set-review-spiders-of-the-mirkwood",
    "encounter-set-review-journey-along-the-anduin",
    "encounter-set-review-saurons-reach",
    "encounter-set-review-wilderlands",
    "encounter-set-review-escape-from-dol-guldur",
    "encounter-set-review-the-hunt-for-gollum",
    "encounter-set-review-conflict-at-the-carrock",
    # A Long Extended Party (fan-made) - from /a-long-extended-party/.
    "ambush-at-erelas",
    "battle-for-the-beacon",
    "into-the-west",
    "at-the-end-of-all-things",
    "the-siege-of-erebor",
]

# The one container that holds the post body, and nothing else.
CONTENT_SELECTOR = ("div", "entry-content")

# WordPress/Jetpack furniture that lives *inside* entry-content but is not
# article prose. Matched against a tag's class attribute (substring).
DROP_CLASSES = (
    "sharedaddy",          # "Share this:" button row
    "jp-relatedposts",     # "Related" post grid
    "sd-block",            # Jetpack sharing/like blocks
    "author-bio",
    "wp-block-buttons",    # "Buy Published Works" style CTAs
    "wp-block-image",      # card-scan figures - pandoc passes these through
    "tiled-gallery",       # as raw HTML, and they carry no readable content
)                          # (Jetpack galleries are card scans too)

DROP_TAGS = ("script", "style", "noscript", "svg", "iframe", "form",
             "figure", "img")

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}


class ContentExtractor(html.parser.HTMLParser):
    """Capture the raw inner HTML of the first `div.entry-content`.

    Tracks nesting depth so the capture ends at the *matching* close tag, not
    the first one. Tags in DROP_TAGS and elements whose class matches
    DROP_CLASSES are skipped along with their subtrees.
    """

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = []
        self._depth = 0          # depth inside the captured div (0 = not in it)
        self._skip_tag = None    # tag name whose subtree we are dropping
        self._skip_depth = 0
        self.found = False
        self.done = False

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _attr(attrs, name):
        for k, v in attrs:
            if k == name:
                return v or ""
        return ""

    def _rebuild(self, tag, attrs, self_closing=False):
        bits = "".join(
            ' %s="%s"' % (k, (v or "").replace('"', "&quot;"))
            for k, v in attrs
        )
        return "<%s%s%s>" % (tag, bits, " /" if self_closing else "")

    def _capturing(self):
        return self._depth > 0 and self._skip_tag is None and not self.done

    # -- parser hooks --------------------------------------------------------

    def handle_starttag(self, tag, attrs):
        if self.done:
            return

        # Already dropping a subtree: just track its depth.
        if self._skip_tag is not None:
            if tag == self._skip_tag and tag not in VOID_TAGS:
                self._skip_depth += 1
            return

        if self._depth == 0:
            sel_tag, sel_class = CONTENT_SELECTOR
            if (not self.found and tag == sel_tag
                    and sel_class in self._attr(attrs, "class").split()):
                self.found = True
                self._depth = 1
            return

        # Inside the content div.
        if tag in DROP_TAGS or any(
                c in self._attr(attrs, "class") for c in DROP_CLASSES):
            if tag in VOID_TAGS:
                return
            self._skip_tag = tag
            self._skip_depth = 1
            return

        if tag == CONTENT_SELECTOR[0]:
            self._depth += 1
        self.parts.append(self._rebuild(tag, attrs))

    def handle_startendtag(self, tag, attrs):
        if self._capturing() and tag not in DROP_TAGS:
            self.parts.append(self._rebuild(tag, attrs, self_closing=True))

    def handle_endtag(self, tag):
        if self.done:
            return

        if self._skip_tag is not None:
            if tag == self._skip_tag:
                self._skip_depth -= 1
                if self._skip_depth <= 0:
                    self._skip_tag = None
            return

        if self._depth == 0:
            return

        if tag == CONTENT_SELECTOR[0]:
            self._depth -= 1
            if self._depth == 0:
                self.done = True
                return

        self.parts.append("</%s>" % tag)

    def handle_data(self, data):
        if self._capturing():
            self.parts.append(data)

    def handle_entityref(self, name):
        if self._capturing():
            self.parts.append("&%s;" % name)

    def handle_charref(self, name):
        if self._capturing():
            self.parts.append("&#%s;" % name)

    def result(self):
        return "".join(self.parts)


def extract_content(page_html):
    """Inner HTML of the page's `div.entry-content`, or "" if absent."""
    p = ContentExtractor()
    p.feed(page_html)
    p.close()
    return p.result() if p.found else ""


def page_title(page_html):
    """The article's <h1>, for a markdown title line. Falls back to "" - the
    slug in the filename is always available to the reader anyway."""
    m = re.search(r"<h1[^>]*>(.*?)</h1>", page_html, re.S | re.I)
    if not m:
        return ""
    import html as _html
    return _html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()


def to_markdown(fragment):
    """Hand the HTML fragment to pandoc. Raises SystemExit with a clear
    message if pandoc is missing - this is a local research tool, so a hard
    failure is friendlier than silently emitting tag soup."""
    if not shutil.which("pandoc"):
        raise SystemExit(
            "pandoc not found - install it (brew install pandoc) to convert "
            "the cached articles to markdown.")
    out = subprocess.run(
        ["pandoc", "-f", "html", "-t", "gfm", "--wrap=none"],
        input=fragment, capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit("pandoc failed: %s" % out.stderr.strip()[:400])
    return out.stdout


def tidy(md, title, slug, url):
    """Trim pandoc's noise: runs of blank lines, empty link shells, and the
    stray non-breaking spaces WordPress sprinkles through post bodies."""
    md = md.replace(" ", " ")
    md = re.sub(r"\[\]\([^)]*\)", "", md)         # image-only anchors
    # Bare layout wrappers pandoc passes through as raw HTML blocks, once the
    # figures inside them are gone. Only whole lines that are nothing but an
    # open/close <div> are removed - a line with prose on it is left alone.
    md = re.sub(r"^[ \t]*</?div\b[^>]*>[ \t]*\n?", "", md, flags=re.M)
    md = re.sub(r"^<!-- -->[ \t]*\n?", "", md, flags=re.M)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    head = ["---",
            "slug: %s" % slug,
            "title: %s" % (title or slug),
            "source: %s" % url,
            "tags:",
            "  - votp",
            "  - research",
            "note: verbatim third-party article text - research corpus only,",
            "  never committed and never reproduced in shipped tips.",
            "---",
            ""]
    return "\n".join(head) + "\n" + md + "\n"


def article_url(page_html, slug):
    """The canonical URL, so each markdown file cites where it came from."""
    m = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"',
                  page_html, re.I)
    if m:
        return m.group(1)
    return "https://visionofthepalantir.com/?p=%s" % slug


def convert(path, out_dir, write=True):
    slug = os.path.splitext(os.path.basename(path))[0]
    page = open(path, encoding="utf-8", errors="replace").read()
    fragment = extract_content(page)
    if not fragment.strip():
        return slug, 0, "no div.entry-content"
    md = tidy(to_markdown(fragment), page_title(page), slug,
              article_url(page, slug))
    if write:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, slug + ".md"), "w",
                  encoding="utf-8") as fh:
            fh.write(md)
    return slug, len(md), ""


def extra_targets():
    """[(corpus_name, article_slug)] for every EXTRA article above - the
    second-edition overrides, the slug fixes, and the background reading.
    Pure, so the manifest can be asserted on without touching the network."""
    targets = []
    for name, article in sorted(SECOND_EDITIONS.items()):
        targets.append((name, article))
    for name, article in sorted(SLUG_FIXES.items()):
        targets.append((name, article))
    for article in BACKGROUND:
        targets.append((article, article))
    return targets


def fetch_extras(cache_dir, delay=1.0):
    """Fetch the EXTRA manifest into the HTML cache, keyed by corpus name.

    Reuses build_tips.fetch for its politeness contract: on-disk cache first
    (a warm entry costs no request and no delay), a real GET otherwise with
    the project User-Agent, then a delay. A single failure is reported and
    skipped, never fatal - partial coverage is the normal state here.

    The article slug is resolved to a URL through the cached sitemap rather
    than assembled by hand, so a manifest entry that no longer exists on the
    site fails loudly at resolution instead of 404ing.
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from build_tips import fetch, parse_sitemap

    sitemap_path = os.path.join(cache_dir, "sitemap.xml")
    if not os.path.exists(sitemap_path):
        raise SystemExit(
            "no cached sitemap at %s - run tools/build_tips.py --refresh "
            "first to populate it." % sitemap_path)
    with open(sitemap_path, encoding="utf-8", errors="replace") as fh:
        sitemap = parse_sitemap(fh.read())

    fetched, cached, missing, failed = 0, 0, [], []
    for name, article in extra_targets():
        url = sitemap.get(article)
        if not url:
            missing.append(article)
            continue
        path = os.path.join(cache_dir, name + ".html")
        if os.path.exists(path):
            # A warm entry is only a hit if it is the SAME article. The
            # second-edition and slug-fix entries deliberately point a
            # corpus name at a different post than the one build_tips.py
            # already cached under that name (the thin 2018 original), so
            # compare the cached page's own canonical URL against the
            # target and re-fetch on a mismatch rather than silently
            # keeping the wrong article.
            with open(path, encoding="utf-8", errors="replace") as fh:
                canonical = article_url(fh.read(), name)
            if canonical.rstrip("/").endswith("/" + article):
                cached += 1
                continue
            os.remove(path)
            print("  replacing %s (was %s)" % (name, canonical))
        try:
            fetch(url, path, delay=delay)
            fetched += 1
            print("  fetched %s <- %s" % (name, url))
        except Exception as exc:                  # network/HTTP - never fatal
            failed.append((name, exc))

    print("extras: %d fetched, %d already cached, %d not in sitemap, "
          "%d failed" % (fetched, cached, len(missing), len(failed)))
    for a in missing:
        print("  MISSING from sitemap: %s" % a, file=sys.stderr)
    for name, exc in failed:
        print("  FAILED %s: %s" % (name, exc), file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--slug", help="convert a single cached page")
    ap.add_argument("--check", action="store_true",
                    help="report sizes, write nothing")
    ap.add_argument("--fetch-extras", action="store_true",
                    help="fetch the EXTRA manifest (second editions, slug "
                         "fixes, background reading) before converting")
    ap.add_argument("--delay", type=float, default=1.0,
                    help="seconds to wait after each real fetch")
    args = ap.parse_args(argv)

    if args.fetch_extras:
        fetch_extras(args.cache, delay=args.delay)

    pattern = args.slug + ".html" if args.slug else "*.html"
    paths = sorted(glob.glob(os.path.join(args.cache, pattern)))
    # `_`-prefixed cache entries are the site's hub/index pages, kept only so
    # the EXTRA manifest above can be re-derived from the site's own link
    # lists. They are navigation, not articles - never part of the corpus.
    paths = [p for p in paths if not os.path.basename(p).startswith("_")]
    if not paths:
        raise SystemExit("no cached HTML at %s/%s" % (args.cache, pattern))

    failures, total = [], 0
    for p in paths:
        slug, size, err = convert(p, args.out, write=not args.check)
        if err:
            failures.append((slug, err))
        else:
            total += size
    print("%d article(s) -> %s (%.1f KB markdown)"
          % (len(paths) - len(failures), args.out, total / 1024.0))
    for slug, err in failures:
        print("  SKIP %s: %s" % (slug, err), file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
