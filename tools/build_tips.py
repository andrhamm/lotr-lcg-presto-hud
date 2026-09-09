"""Fetch, cache, and summarize per-scenario strategy write-ups from Vision of
the Palantir (https://visionofthepalantir.com/) - the site the project's own
quests/*.md notes already cite as their source - into docs/data/tips.json.
That output is COMMITTED, the one allow-listed exception to the blanket
docs/data/ gitignore: everything in it is text this project wrote itself (see
the Copyright posture below - a source sentence is never trimmed and shipped;
only a fact-pattern rule's own fixed phrasing, or a quests/*.md callout we
authored, survives), which CLAUDE.md's "What may be committed" allows in git,
while the verbatim card DB alongside it stays generated. See docs/superpowers/
plans/2026-07-24-stage-tips.md, Task 1.

Because it is committed, this fetcher is a NO-OP by default: main() bails out
early via build_card_data.needs_refresh() whenever --out already exists, so a
clean checkout or a Pages build never re-scrapes the site. Regenerating is an
explicit, local act: --refresh. Nothing in CI runs this any more (see
.github/workflows/pages.yml).

Verified facts (Task 1 Step 1-2, recorded per the plan's Global Constraints):

  - robots.txt (fetched 2026-07-24): only disallows WordPress admin/login
    machinery (/wp-admin/, /wp-login.php, /wp-signup.php, /cgi-bin/, etc.);
    article paths and /sitemap.xml are not disallowed, so fetching article
    pages for a polite, rate-limited, cached crawl is permitted. Two
    Sitemap: lines are advertised: sitemap.xml (704 URLs, general content)
    and news-sitemap.xml (recent-only, not used here).

  - Slug -> article URL mechanism: the site's WordPress sitemap.xml is a
    single flat <urlset> (no pagination encountered - 704 <url> entries in
    one file) mixing dated blog-post URLs (".../YYYY/MM/DD/<slug>/" - the
    "Quest Spotlight" strategy-article series this tool wants) with a
    smaller number of undated static pages (cycle-guide overviews etc,
    skipped - see parse_sitemap). Matching a catalog scenario slug against
    the dated-post slugs, case-sensitive exact match after normalizing the
    "-s-"/"-s" possessive shape our own slugify() produces (see
    quest_catalog.normalize_icon_key for the same rule on the icon side),
    resolved 111 of 131 official quest scenarios with ZERO ambiguous
    (multi-URL) matches and no false positives spot-checked (celembrimbor-
    s-secret does not match despite a same-topic post existing, because the
    catalog's own name has a "Celembrimbor"/"Celebrimbor" spelling
    mismatch upstream - see the Task 1 report). No "-2"/"-3" WordPress
    slug-collision suffix was ever needed for a real match, so match_article
    intentionally only tries the exact (normalized) slug - see its
    docstring for why guessing a suffixed URL would be worse than no match.
    Reliability: high for exact matches (WordPress enforces globally unique
    post slugs, so a match is never ambiguous); coverage is inherently
    partial (VotP has not written a Quest Spotlight for every scenario ever
    printed) - that's expected and fine, see the plan's Global Constraints.

Copyright posture (stricter than card text - see the plan): extract_blocks()
only locates candidate paragraphs/list items (preferring the article's own
"Tips and Tricks" section); summarize() never simply trims/truncates a
source sentence and calls it a tip - the only sentences that ever survive
are ones a small set of fact-pattern rules can genuinely restate in fixed,
original phrasing (currently just a threat-threshold-with-avoid-target
callout - see _THREAT_AVOID), and every candidate - however it was
produced - is additionally rejected if it shares an implausibly long run of
consecutive words with its source sentence (_too_verbatim). Everything else
is dropped, per the plan's explicit "if a passage cannot be summarized
without effectively copying it, drop it". This trades coverage for safety:
most source sentences (flowing prose with no recognized factual pattern)
are dropped rather than force-fit, so many matched scenarios still end up
with zero tips - a scenario is only written to tips.json's "scenarios" map
if at least one tip survived (see build()).

Quality gate (post-launch correctness fix - real emitted samples turned out
unreadable-to-backwards, e.g. "Avoid: be afraid to scoop." from a source
that says DO scoop): an earlier rule mechanically rewrote a sentence-initial
"Don't X"/"Never X" into "Avoid: X". That transform is gone outright - it
mangled grammar and could silently invert meaning ("Don't forget to..." ->
"Avoid: forget to..." reads as the opposite instruction), and no negation-
rewriting rule may be reintroduced (a tip must never carry different
semantics than its source sentence - if a sentence can't be safely
shortened without that risk, dropping it is always correct, never a
truncate-with-"..").  Every candidate tip, from EITHER source below, must
additionally pass is_useful_tip() - a single, source-agnostic, unit-tested
predicate that rejects dangling fragments, unresolved pronouns, generic
filler with no actual game information, and (still) anything too verbatim.

Sources, in preference order: (1) quests/*.md - this project's own hand-
authored, in-house quest notes (see CLAUDE.md); a small number of them
carry Obsidian "> [!tip]"/"> [!warning]" callouts written in exactly the
terse, correct style wanted, parsed by load_project_notes() and attributed
to the project itself (no external citation needed for our own words).
(2) The Vision of the Palantir scrape below, used only where notes don't
already cover a scenario. Both sources are gated by the same
is_useful_tip() before anything reaches tips.json.
"""
import argparse
import datetime
import html.parser
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from build_card_data import needs_refresh

SOURCE_NAME = "Vision of the Palantir"
BASE_URL = "https://visionofthepalantir.com"
SITEMAP_URL = BASE_URL + "/sitemap.xml"
USER_AGENT = ("lotr-lcg-presto-hud/build_tips "
              "(+https://github.com/andrhamm/lotr-lcg-presto-hud)")
TIMEOUT = 30  # seconds

    # This project's own quests/*.md notes - see load_project_notes(). No
    # URL: "attributed to the project itself" means exactly that, not a
    # link to the external VotP article those notes happen to cite as
    # their own research source (see quests/*.md frontmatter `source:`).
PROJECT_SOURCE_NAME = "Presto HUD notes"
# The long form is the same advice as tips.json, written at the length it
# wants rather than the length a 240x240 screen allows. Same authorship,
# same fact-checking, same never-reproduced rule.
LONG_SOURCE = ("the same tips as tips.json, written in full for a screen "
               "with room for them - authored by this project from the "
               "same sources, summarized, never reproduced, and re-checked "
               "against the compiled card data")

MAX_LEN = 140    # chars per tip - see the plan's Global Constraints
MAX_TIPS = 4     # tips per scenario
# The LONG form's own ceiling. The 140 above is the Presto's constraint: a
# 240x240 screen with a fixed type scale, where a tip has to be one clause.
# The tablet has no such limit, and the terseness that bought us the Presto
# fit reads like a telegram - so the long form gets room for a real sentence
# or two. Still a ceiling, because a tip is advice you act on mid-game, not
# an article: past this it belongs in the source the citation points at.
MAX_LONG_LEN = 320
# A long tip has to earn the name. MIN_TIP_WORDS is the short form's
# floor; anything near it in the long file is the terse line pasted into
# the wrong place, which would silently ship the same sentence twice.
MIN_LONG_TIP_WORDS = 14

DEFAULT_INDEX = os.path.join("docs", "data", "index.json")
DEFAULT_OUT = os.path.join("docs", "data", "tips.json")
DEFAULT_CACHE = os.path.join("tools", "data", "tips_cache")
DEFAULT_NOTES = os.path.join("quests")
DEFAULT_DELAY = 1.0  # seconds after each real network fetch (politeness)
# The distilled strategy tips - COMMITTED derived data, this build's primary
# source. See load_distillation() and the module docstring's Sources.
DEFAULT_DISTILLED = os.path.join("tools", "data", "tips_distilled.json")
# The LONG form of those same tips - committed derived data, authored the
# same way (read the corpus, re-check every claim against the card data),
# and keyed BY THE SHORT TIP'S OWN TEXT rather than by position. Position
# pairing would break the moment anything reorders or reclassifies a list,
# and it would break silently, into wrong pairings; a text key cannot
# mispair, and a key that no longer matches any tip is reported as an
# orphan - which is exactly when its long form needs rewriting anyway.
DEFAULT_LONG = os.path.join("tools", "data", "tips_long.json")
# TABLET ONLY, and deliberately not under docs/data/: the device deploy is
# `mpremote cp -r docs/data/ :/data/`, which copies that directory whole,
# and long prose on Presto flash is pure waste - the same reason the icon
# pack's SVG export is kept out of it.
DEFAULT_LONG_OUT = os.path.join("docs", "tablet", "data", "tips_full.json")


# -- catalog scenario selection ----------------------------------------------

def pickable_scenarios(index):
    """Every catalog scenario a player can actually choose in the quest
    picker: kind=="quest", stageCount>0, and not a "<name> - Nightmare"
    variant. Mirrors quest_catalog.group_by_cycle's filter (reimplemented
    locally - tools/ build scripts are host-only and self-contained, see
    tools/build_hob_enrichment.py's own precedent of not importing
    quest_catalog). This is also the only slug set worth fetching tips for:
    game.scenario["slug"] is always the base scenario's slug, even when
    Nightmare mode is picked via the Scenario Options toggle (see main.py's
    begin_setup handling), so a "- Nightmare" catalog entry's own slug is
    never looked up at runtime."""
    return [s for s in index.get("scenarios", [])
            if s.get("kind") == "quest" and s.get("stageCount", 0) > 0
            and not (s.get("name") or "").endswith(" - Nightmare")]


# -- sitemap -> slug/URL map, and the slug matcher ---------------------------

_DATED_PATH = re.compile(r"^/(\d{4})/(\d{2})/(\d{2})/([^/]+)/?$")


def parse_sitemap(xml_text):
    """{slug: url} for every dated blog-post URL in a WordPress sitemap.xml
    (".../YYYY/MM/DD/<slug>/" - VotP's "Quest Spotlight" strategy series
    convention, see the module docstring's Verified facts). Undated pages
    (static cycle-guide pages etc) are skipped - they're not part of the
    per-scenario matching (see match_article). Pure, host-tested. Tolerates
    a non-well-formed feed by falling back to a plain regex scan for <loc>
    tags rather than raising - a malformed third-party feed shouldn't break
    the whole build."""
    try:
        root = ET.fromstring(xml_text)
        locs = [el.text for el in root.iter()
                if el.tag == "loc" or el.tag.endswith("}loc")]
    except ET.ParseError:
        locs = re.findall(r"<loc>([^<]+)</loc>", xml_text)

    slugs = {}
    for url in locs or []:
        if not url:
            continue
        url = url.strip()
        path = urllib.parse.urlparse(url).path
        m = _DATED_PATH.match(path)
        if m:
            slugs[m.group(4)] = url
    return slugs


def _normalize_possessive(slug):
    """Collapse a "-s-"/trailing "-s" possessive slug shape (our own
    slugify() keeps the hyphen before a possessive s, e.g. "shelob-s-lair";
    WordPress's own slug generator drops the apostrophe outright instead,
    e.g. "shelobs-lair") onto the same form, so the two otherwise-identical
    slugs line up. A small local reimplementation of quest_catalog.
    normalize_icon_key's possessive rule, kept self-contained rather than
    imported (see the module docstring / pickable_scenarios)."""
    s = slug.replace("-s-", "s-")
    if s.endswith("-s"):
        s = s[:-2] + "s"
    return s


def match_article(slug, sitemap_slugs):
    """The VotP article URL for catalog `slug`, or None. Exact match first,
    then both sides possessive-normalized (see _normalize_possessive) -
    covers the small, mostly-cosmetic difference between our slugify()'s
    "-s-" and WordPress's own apostrophe-dropping convention. No fuzzier
    matching is attempted (e.g. a "-2"/"-3" WordPress slug-collision
    suffix): the real sitemap never needed it for a genuine match (see the
    module docstring), and guessing at a suffixed URL risks silently
    attributing tips to the wrong quest, which is worse than the safe
    default of no tips for that scenario - see the plan's Global
    Constraints (tips coverage is optional and partial throughout)."""
    if slug in sitemap_slugs:
        return sitemap_slugs[slug]
    norm = _normalize_possessive(slug)
    if norm != slug:
        for candidate, url in sitemap_slugs.items():
            if _normalize_possessive(candidate) == norm:
                return url
    return None


# -- extract_blocks: HTML -> plain-text candidate blocks ---------------------

_SKIP_TAGS = {"script", "style", "nav", "header", "footer", "aside"}
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_TEXT_TAGS = {"p", "li"}
_TIPS_HEADING = re.compile(r"\btips\b", re.I)
_WS_RUN = re.compile(r"\s+")


class _ArticleParser(html.parser.HTMLParser):
    """Collects plain-text <p>/<li> blocks from inside <article>...</article>,
    preferring the section headed by a "Tips"-matching heading (bounded by
    the next heading at the SAME level - VotP's own "Tips and Tricks" H2 is
    always followed directly by another H2 with no H3s nested inside it, per
    the module docstring's Verified facts) and falling back to every block
    in the article when no such heading is found. Inline markup (<a>,
    <strong>, <em>, ...) inside a captured <p>/<li> contributes its text but
    is not itself a block boundary. This is a scraper tuned to one known
    site's WordPress theme, not a general HTML->text converter - it
    degrades by omission (skips what it doesn't recognize), never raises on
    well-formed-ish input."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_article = 0
        self.skip_depth = 0
        self.heading_level = None
        self.heading_text = []
        self.in_tips = False
        self.tips_level = None
        self.capture_tag = None
        self.buf = []
        self.all_blocks = []
        self.tips_blocks = []

    def handle_starttag(self, tag, attrs):
        if tag == "article":
            self.in_article += 1
        if not self.in_article:
            return
        if tag in _SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in _HEADING_TAGS:
            self.heading_level = tag
            self.heading_text = []
        elif tag in _TEXT_TAGS and self.capture_tag is None:
            self.capture_tag = tag
            self.buf = []

    def handle_endtag(self, tag):
        if tag == "article":
            self.in_article = max(0, self.in_article - 1)
            return
        if not self.in_article:
            return
        if tag in _SKIP_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth:
            return
        if tag in _HEADING_TAGS:
            if tag == self.heading_level:
                text = _clean_ws("".join(self.heading_text))
                if self.in_tips and tag == self.tips_level:
                    self.in_tips = False   # next same-level heading ends it
                elif _TIPS_HEADING.search(text):
                    self.in_tips = True
                    self.tips_level = tag
                self.heading_level = None
            return
        if tag == self.capture_tag:
            text = _clean_ws("".join(self.buf))
            if text:
                self.all_blocks.append(text)
                if self.in_tips:
                    self.tips_blocks.append(text)
            self.capture_tag = None
            self.buf = []

    def handle_data(self, data):
        if not self.in_article or self.skip_depth:
            return
        if self.heading_level is not None:
            self.heading_text.append(data)
        if self.capture_tag is not None:
            self.buf.append(data)


# The device draws with an 8px bitmap font whose glyph table only covers
# printable ASCII (see tests/fake_hardware.py BITMAP8_W - 82 entries). Any
# codepoint above that renders as garbage on hardware, so fold the typographic
# characters our sources use (quests/*.md notes and web articles both contain
# arrows, en/em dashes, curly quotes, the minus sign) down to ASCII.
_ASCII_FOLD = {
    "→": "->", "←": "<-",           # arrows
    "–": "-", "—": "-", "−": "-",  # en dash, em dash, minus
    "‘": "'", "’": "'",             # curly single quotes
    "“": '"', "”": '"',             # curly double quotes
    "…": "...", " ": " ", "×": "x", "•": "-",
}


def _to_ascii(s):
    for src, dst in _ASCII_FOLD.items():
        s = s.replace(src, dst)
    # Anything still non-ASCII would render as garbage on the device; drop it
    # rather than shipping a broken glyph.
    return "".join(c for c in s if 32 <= ord(c) < 127)


def _clean_ws(s):
    return _WS_RUN.sub(" ", _to_ascii(s)).strip()


def extract_blocks(html_text):
    """Plain-text candidate blocks (paragraphs/list items, tags stripped,
    whitespace collapsed) from one article's HTML - see _ArticleParser.
    Prefers the "Tips"-headed section; falls back to the whole article body
    when no such section exists. [] for empty/unparseable input - never
    raises, since a malformed page from a third party is exactly the case
    this must degrade gracefully for."""
    parser = _ArticleParser()
    try:
        parser.feed(html_text or "")
    except Exception:
        return []
    return parser.tips_blocks if parser.tips_blocks else parser.all_blocks


# -- summarize: condense to our own short phrasing, or drop -----------------

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")

    # NOTE: re.I is scoped with (?i:...) to ONLY the "keep threat" clause,
    # not the whole pattern - a bare re.I compile flag would also make
    # [A-Z] match lowercase, which defeats its entire purpose here (finding
    # where a proper-noun target name ends). Verified against the real
    # corpus (Task 1 Step 7): without scoping, "avoid the Hummerhorns or
    # raise their" swallowed the trailing lowercase words into `name`.
_THREAT_AVOID = re.compile(
    r"(?i:\b(?:keep|stay|remain)\w*\s+(?:your\s+)?threat\s+(?:below|under)\s+"
    r"(?P<n>\d+)\b[^.?!]{0,60}?\bavoid(?:ing)?\s+(?:the\s+)?)"
    r"(?P<name>[A-Z][\w']*(?:\s+[A-Z][\w']*){0,3})")

    # REMOVED (correctness fix): this used to also include a
    # "^(?:do not|don't|never) <clause>" rule that reframed a sentence-
    # initial negative imperative as "Avoid: <clause>." - e.g. "Don't
    # bring a Swarm deck." -> "Avoid: bring a Swarm deck.". That looked
    # safe (the negator IS the sentence's own first word, so it's a
    # genuine imperative command, not a relative clause/aside/descriptive
    # negation) but the transform itself was the bug: splicing the raw
    # clause after "Avoid:" doesn't just reword the source, it can invert
    # it - "Don't be afraid to scoop." (DO scoop) became "Avoid: be afraid
    # to scoop." (the opposite advice), and "Don't forget to raise the
    # temperature." became the confusing "Avoid: forget to raise the
    # temperature." A tip must never carry different semantics than its
    # source sentence (see the module docstring's Quality gate) - there is
    # no safe general fix for this shape, so the rule is simply gone. See
    # tests/test_tips.py's test_summarize_never_produces_avoid_colon_tips
    # for the regression coverage.


def _rule_threat_avoid(m):
    name = m.group("name").strip()
    return "Stay under %s threat - avoid %s." % (m.group("n"), name)


_RULES = [(_THREAT_AVOID, _rule_threat_avoid)]

_WORD_RE = re.compile(r"[A-Za-z0-9']+")
MAX_SHARED_RUN = 8  # words - see _too_verbatim


def _too_verbatim(candidate, source, max_shared=MAX_SHARED_RUN):
    """True if `candidate` shares a run of more than `max_shared`
    consecutive whole words (case-insensitive) with `source` - the
    mechanical guard that catches a rule output which still carries too
    much of the source sentence's own wording, whichever rule produced it.
    This is what actually enforces "if it can't be summarized without
    effectively copying it, drop it" as code rather than as a promise."""
    a = _WORD_RE.findall(candidate.lower())
    b = _WORD_RE.findall(source.lower())
    best = 0
    for i in range(len(a)):
        for j in range(len(b)):
            k = 0
            while i + k < len(a) and j + k < len(b) and a[i + k] == b[j + k]:
                k += 1
            if k > best:
                best = k
    return best > max_shared


def _split_sentences(text):
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


# -- is_useful_tip: the quality gate every candidate tip must pass ----------

    # Source-agnostic: summarize() (VotP scrape, below) and
    # load_project_notes() (quests/*.md, further down) both run every
    # candidate through this exact function before it can reach
    # tips.json. Every check is a REJECT rule (default is to accept) -
    # matching this module's "if in doubt, drop it" posture: a false
    # negative (a fine tip dropped) is always acceptable, a false positive
    # (a broken tip shipped) is not. See tests/test_tips.py for the real
    # bad/good samples this is regression-tested against.

_LEADING_GLUE = re.compile(r"^avoid:\s", re.I)
    # The exact shape the old "Don't X" -> "Avoid: X" transform produced
    # (see _THREAT_AVOID's neighboring comment) - "Avoid: be afraid to
    # scoop.", "Avoid: bother with easy mode." - a bare clause glued after
    # "Avoid:" that doesn't parse as English (needs a gerund: "Avoid being
    # afraid...", "Avoid bothering with..."). Kept as its own check so
    # this exact bug can never resurface even from a future rule.

_RISKY_PRONOUNS = re.compile(
    r"\b(?:them|him|her|it|they)\b"                 # always pronouns
    r"|\b(?:this|that|these|those)\b(?!\s+[a-z])",   # pronoun use only -
    re.I)                                            # "this quest" (a
    # determiner + its own noun, self-contained) is allowed; a bare "this"/
    # "that"/... with nothing after it is not. Real bad samples this
    # catches: "rely on them too much", "worry about him for now" - the
    # only possible antecedent was in the source article, which the tip
    # doesn't carry over. A good tip names the actual card/enemy instead
    # (see the accepted "Stay under 40 threat - avoid Hummerhorns.", which
    # repeats "Hummerhorns" rather than saying "them").

_DANGLING_TRAILERS = {
    "though", "too", "also", "however", "but", "and", "or", "so", "then",
    "yet", "instead", "either", "well", "anyway", "besides",
}
    # A tip whose last word is one of these reads as a clause chopped off
    # mid-thought - "rely on them too much though.", "go overboard
    # though." - rather than a complete standalone statement.

_META_REFERENCE = re.compile(
    r"\b(?:HUD|companion|quest picker|the app|app's|screen|modal|UI)\b",
    re.I)
    # quests/*.md mixes genuine player-facing quest facts with the notes
    # author's own asides about the companion app itself ("a quest picker
    # could preload...", "the HUD's progress row could..."). Those are
    # real, grammatical sentences - just not tips about how to PLAY the
    # quest - so they're rejected here rather than shown to a player
    # mid-game.

_GAME_KEYWORDS = {
    "threat", "engage", "engages", "engaged", "engagement", "quest",
    "questing", "damage", "dmg", "boss", "enemy", "enemies", "location",
    "locations", "stage", "stages", "progress", "willpower", "defend",
    "defending", "defended", "attack", "attacks", "attacking", "shadow",
    "treachery", "treacheries", "hp", "atk", "def", "eng", "resource",
    "resources", "hero", "heroes", "ally", "allies", "card", "cards",
    "deck", "encounter", "surge", "surges", "victory", "objective",
    "objectives", "keyword", "exhaust", "exhausted", "ready", "discard",
    "discarded", "sail", "sailing", "heading", "ship", "wound", "wounds",
    "condition", "nightmare", "scenario",
}
    # Coarse allow-list for "carries actual game information" - a tip
    # passes this leg of the gate if it names a number (a threat/
    # engagement value), one of these LOTR-LCG terms, or a proper noun
    # (see _PROPER_NOUN). A sentence with none of the three is generic
    # filler ("there is no single right answer here") with nothing for a
    # player to act on.

_PROPER_NOUN = re.compile(r"(?<=[a-z] )[A-Z][a-zA-Z']{2,}")
    # A capitalized word that follows a lowercase word + space - i.e. NOT
    # the tip's own first word (always capitalized regardless of content)
    # and NOT the first word of a later sentence (which follows ". ", not
    # a lowercase letter) - so a match is a genuine mid-sentence proper
    # noun, almost always a card/enemy/location name in this corpus
    # ("avoid Hummerhorns", "Chieftain Ufthak").

_WORD_TOKEN = re.compile(r"[A-Za-z']+")
MIN_TIP_WORDS = 3   # e.g. "Stay under 40." alone is too thin/ambiguous


def is_useful_tip(text, max_len=MAX_LEN):
    """True if `text` is fit to ship as a standalone tip: a complete,
    grammatical, self-contained statement that carries real LOTR-LCG game
    information, within `max_len` chars. Pure text-in/bool-out - knows
    nothing about where `text` came from (scrape or our own notes) - see
    the module docstring's Quality gate and the constants above for what
    each check catches."""
    if not text:
        return False
    text = text.strip()
    if not text or len(text) > max_len:
        return False
    if _LEADING_GLUE.match(text):
        return False
    if not (text[0].isupper() or text[0].isdigit()):
        return False          # starts mid-clause, not a sentence of its own
    if text[-1] not in ".!?":
        return False          # no terminal punctuation - reads as clipped
    words = _WORD_TOKEN.findall(text)
    if len(words) < MIN_TIP_WORDS:
        return False
    last_token = text.rstrip(".!?").split()[-1].strip("()[]\"'.,;:")
    if last_token.lower() in _DANGLING_TRAILERS:
        return False
    if _RISKY_PRONOUNS.search(text):
        return False
    if _META_REFERENCE.search(text):
        return False
    has_digit = any(ch.isdigit() for ch in text)
    has_keyword = any(w.lower() in _GAME_KEYWORDS for w in words)
    has_proper_noun = bool(_PROPER_NOUN.search(text))
    return has_digit or has_keyword or has_proper_noun


# -- the distilled tips: load + validate -------------------------------------
#
# tools/data/tips_distilled.json is this build's PRIMARY source: per-scenario
# strategy tips written by this project after reading the Vision of the
# Palantir quest spotlights, with every factual claim re-checked against the
# compiled card data in docs/data/. It is committed derived data (our own
# words - see CLAUDE.md's "What may be committed"), so a build never fetches
# anything to produce it.
#
# Why it exists at all: the mechanical summarize() path below can only emit a
# sentence matching a hardcoded fact-pattern, so in practice it emitted almost
# nothing, and what did ship was stat restatement rather than strategy. The
# distillation replaces that, and summarize() is kept only for the notes path.

_PRONOUN = re.compile(r"\b(?:them|him|her|it|they)\b", re.I)
_CAPITALISED = re.compile(r"\b[A-Z][a-zA-Z'\-]{2,}\b")

# Capitalised only because they begin a sentence - not names, so they can
# never be a pronoun's antecedent. Anything capitalised and NOT in here is
# taken to be a card/enemy/location name.
_SENTENCE_STARTERS = {
    "the", "you", "your", "bring", "keep", "under", "over", "send", "stay",
    "take", "defend", "play", "most", "only", "four", "five", "three", "two",
    "one", "end", "at", "on", "in", "don", "do", "never", "always", "use",
    "expect", "push", "clear", "each", "every", "if", "when", "while",
    "after", "before", "this", "that", "go", "leave", "hold", "start",
    "begin", "commit", "quest", "stage", "first", "second", "advance",
    "block", "kill", "damage", "progress", "threat", "travel", "for", "no",
    "make", "failing", "nothing", "capture", "chump", "camp", "off",
}


def _has_antecedent(text):
    """True if `text`'s first risky pronoun has something to refer to WITHIN
    the tip - a card/enemy name, or a game keyword, appearing before it.

    is_useful_tip()'s _RISKY_PRONOUNS bans these pronouns outright, which is
    right for a SCRAPED sentence: it was lifted out of an article, so its
    antecedent stayed behind and "avoid them" means nothing on its own. A
    distilled tip is authored as a standalone sentence, so ordinary anaphora
    ("Caradhras cannot be travelled to, so pre-load it") is both correct and
    shorter than repeating the name - and brevity is the whole point on a
    small screen. What must still be rejected is a genuinely dangling
    reference, i.e. a tip that opens with a bare "It ..." naming nothing.

    Pure, host-tested."""
    m = _PRONOUN.search(text or "")
    if not m:
        return True
    head = text[:m.start()]
    for word in _CAPITALISED.findall(head):
        if word.lower() not in _SENTENCE_STARTERS:
            return True          # a real name precedes the pronoun
    return any(w.lower() in _GAME_KEYWORDS
               for w in _WORD_TOKEN.findall(head))


def is_valid_distilled_tip(text, max_len=MAX_LEN):
    """True if an authored, already-fact-checked tip is fit to ship.

    Deliberately NOT is_useful_tip(): that gate is tuned for text extracted
    from an article and rejects things that are perfectly fine in authored
    prose - a complete sentence ending "... take the extra encounter card
    instead." (its _DANGLING_TRAILERS rule), or one whose only proper noun
    starts the sentence, e.g. "Counter-spell can cancel your event."
    (its _PROPER_NOUN rule needs a lowercase word before the capital). Run
    over the distillation, those two rejected roughly a third of a corpus
    that had already been checked claim-by-claim against the card data.

    So this keeps the checks that still mean something for authored text -
    length, a real sentence, enough words, no talking about the app itself,
    no dangling pronoun - and drops the ones that only made sense for
    scraped fragments. The verbatim guard is applied separately by the
    caller, which has the source article to compare against.

    Pure, host-tested."""
    if not text:
        return False
    text = text.strip()
    if not text or len(text) > max_len:
        return False
    if not (text[0].isupper() or text[0].isdigit()):
        return False
    if text[-1] not in ".!?":
        return False
    if len(_WORD_TOKEN.findall(text)) < MIN_TIP_WORDS:
        return False
    if _META_REFERENCE.search(text):
        return False
    return _has_antecedent(text)


def is_valid_long_tip(text, max_len=MAX_LONG_LEN):
    """True if an authored LONG-form tip is fit to ship.

    The same gate as is_valid_distilled_tip - a real sentence, enough words,
    no talking about the app, no dangling pronoun - with one thing relaxed
    and one added:

    - `max_len` is MAX_LONG_LEN, not MAX_LEN. That is the whole point of the
      long form: 140 chars is the Presto's screen talking, not the advice's
      natural length.
    - it must actually BE longer than a telegram. A "long" tip that is 60
      characters is the short one pasted into the wrong file, and pairing it
      would quietly ship the terse version twice; MIN_TIP_WORDS is the floor
      for the short form, so the long form asks for more.

    Pure, host-tested."""
    if not text:
        return False
    text = text.strip()
    if not text or len(text) > max_len:
        return False
    if not (text[0].isupper() or text[0].isdigit()):
        return False
    if text[-1] not in ".!?":
        return False
    if len(_WORD_TOKEN.findall(text)) < MIN_LONG_TIP_WORDS:
        return False
    if _META_REFERENCE.search(text):
        return False
    return _has_antecedent(text)


def load_long(path=DEFAULT_LONG):
    """{slug: {"general": {short: long}, "stages": {n: {short: long}}}} from
    the committed long-form file, or {} on ANY failure.

    Absent-tolerant like load_distillation(): a build with no long file at
    all still emits tips.json exactly as before, and the tablet falls back
    to the short form tip by tip. That is what lets this land scenario by
    scenario instead of as a flag day.

    An entry that fails is_valid_long_tip() is DROPPED, not fatal - it just
    means that one tip keeps its short form. Dropping is safe here in a way
    it would not be under positional pairing: the key is the short tip's own
    text, so removing one cannot shift any other."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        scenarios = data.get("scenarios")
        if not isinstance(scenarios, dict):
            return {}
    except Exception:
        return {}

    out = {}
    for slug, entry in scenarios.items():
        if not isinstance(entry, dict):
            continue

        def _pairs(m):
            return {str(k): v for k, v in (m or {}).items()
                    if isinstance(v, str) and is_valid_long_tip(v)}

        general = _pairs(entry.get("general"))
        stages = {}
        for key, pairs in (entry.get("stages") or {}).items():
            kept = _pairs(pairs)
            if kept:
                stages[str(key)] = kept
        if not general and not stages:
            continue
        out[slug] = {"general": general, "stages": stages}
    return out


def load_distillation(path=DEFAULT_DISTILLED):
    """{slug: entry} from the committed distillation, or {} on ANY failure.

    Absent-tolerant by design, matching _load_enrichment() in
    build_card_data.py and quest_catalog.load_icons(): a missing or corrupt
    file must degrade to "no distilled tips" (the notes path still runs)
    rather than fail a build. Entries whose tips do not survive
    is_valid_distilled_tip() are dropped tip-by-tip; a scenario left with no
    tips at all is omitted entirely, so tips.json's keys keep meaning
    "this scenario has tips" for the modal's enabled/disabled button."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        scenarios = data.get("scenarios")
        if not isinstance(scenarios, dict):
            return {}
    except Exception:
        return {}

    out = {}
    for slug, entry in scenarios.items():
        if not isinstance(entry, dict):
            continue
        general = [t for t in (entry.get("general") or [])
                   if is_valid_distilled_tip(t)]
        stages = {}
        for key, tips in (entry.get("stages") or {}).items():
            kept = [t for t in (tips or []) if is_valid_distilled_tip(t)]
            if kept:
                stages[str(key)] = kept
        if not general and not stages:
            continue
        out[slug] = {
            "attribution": entry.get("attribution") or {},
            "general": general,
            "stages": stages,
        }
    return out





def summarize(blocks, max_len=MAX_LEN, max_tips=MAX_TIPS):
    """Condense `blocks` (raw paragraph/list-item text, see extract_blocks)
    into at most `max_tips` short (<= max_len char) tips, each in our own
    phrasing rather than a copy of the source sentence.

    Deliberately NOT a generic trim-and-truncate: a source sentence is only
    ever turned into a tip when one of a small set of fact-pattern rules
    (_RULES - currently just a threat-threshold-with-avoid-target callout)
    can restate it in fixed, original phrasing, every candidate is further
    rejected by _too_verbatim if it still shares an implausibly long run
    of the source's own words, and every survivor must then also pass
    is_useful_tip (see the module docstring's Quality gate) - a candidate
    that's too long, a dangling fragment, or otherwise unfit is DROPPED,
    never truncated-with-".." into a shorter fragment (a clipped copy is
    still a copy, and clipping can itself produce an unreadable tip).
    Sentences with no recognized pattern are dropped too. This means
    summarize() commonly returns fewer tips than max_tips, or none at all,
    for prose-heavy input; that's the intended, safe behavior (see the
    plan's "if a passage cannot be summarized without effectively copying
    it, drop it"), not a bug. Order-preserving; de-duplicates
    (case-insensitive) across all blocks."""
    seen = set()
    out = []
    for block in blocks:
        text = _clean_ws(block)
        if not text:
            continue
        for sentence in _split_sentences(text):
            for pattern, template in _RULES:
                m = pattern.search(sentence)
                if not m:
                    continue
                tip = template(m)   # a rule may itself veto its own match (return None)
                if not tip:
                    continue
                tip = _clean_ws(tip)
                if not tip or _too_verbatim(tip, sentence):
                    continue
                if not is_useful_tip(tip, max_len=max_len):
                    continue
                key = tip.lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append(tip)
                break
            if len(out) >= max_tips:
                return out
    return out


# -- build_entry: {attribution, general, stages} shape -----------------------

def build_entry(slug, url, tips, stages=None, attribution=None):
    """One docs/data/tips.json scenarios[slug] entry: attribution (source
    name + article URL, always displayed alongside the tips in the UI - see
    the plan's copyright posture), the scenario-wide `general` tips, and
    optional per-stage `stages` (keyed by stage number as a string) - both
    lists of short summarized strings, never raw article text. `slug` is
    accepted (matching the shape's use as the outer dict key in tips.json)
    but not embedded in the returned entry, which only ever holds the
    per-scenario payload.

    `attribution`, if given, overrides the default `{"name": SOURCE_NAME,
    "url": url}` (a VotP article citation) - build() passes an explicit
    `{"name": PROJECT_SOURCE_NAME, "url": ""}` for quests/*.md-derived
    tips, which need no external citation (see load_project_notes)."""
    return {
        "attribution": dict(attribution) if attribution else
                        {"name": SOURCE_NAME, "url": url},
        "general": list(tips),
        "stages": dict(stages) if stages else {},
    }


# -- load_project_notes: quests/*.md -> {slug: [tip, ...]} ------------------

    # quests/*.md are this project's OWN hand-authored, in-house quest
    # notes (not scraped, not third-party - see CLAUDE.md and the module
    # docstring's Sources). A small number of them (currently ~4) carry
    # Obsidian "> [!tip]"/"> [!warning]" callouts written in exactly the
    # terse, factual style wanted for tips.json - e.g. threat/engagement
    # warnings and boss stat lines. build() prefers a scenario's
    # notes-derived tips over its scraped ones when both exist (see
    # build()) - first-party, human-reviewed text is strictly more
    # trustworthy than a scrape, though it still has to pass the same
    # is_useful_tip gate (preferred, not exempt - a note can also contain
    # the author's own asides about the companion app itself, e.g. "a
    # quest picker could preload...", which are real sentences but not
    # player-facing quest tips; see _META_REFERENCE).

_FRONTMATTER_TAGS_KEY = re.compile(r"^tags:\s*$")
_FRONTMATTER_LIST_ITEM = re.compile(r"^\s*-\s*(.+?)\s*$")
_CALLOUT_START = re.compile(r"^>\s*\[!(\w+)\]")
_CALLOUT_LINE = re.compile(r"^>\s?(.*)$")
_BULLET_ITEM = re.compile(r"^[-*]\s+(.*)$")
_WIKILINK = re.compile(r"\[\[[^\]]*\]\]")
_MD_BOLD = re.compile(r"\*\*(.+?)\*\*")
_MD_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")

CALLOUT_TYPES = ("tip", "warning")
    # Deliberately NOT "note"/"check"/etc - see quests/*.md, e.g.
    # escape-from-dol-guldur.md's "[!note] Advancement isn't
    # progress-only": that's the notes author's own design commentary
    # about the companion app, not player-facing quest advice, and is
    # never a candidate here regardless of what is_useful_tip would make
    # of its wording.


def _frontmatter_tags(md_text):
    """The values of a leading YAML frontmatter block's `tags:` list (e.g.
    {"lotr-lcg/quest", "core-set", ...}), or set() if `md_text` has no
    frontmatter or no `tags:` key. A minimal hand-rolled reader for the
    one fixed shape quests/*.md's frontmatter actually uses (a flat `key:
    value` block with one `tags:` list) - not a YAML parser and not meant
    to be one (tools/ build scripts are self-contained, see the module
    docstring's Verified facts on why match_article works the same way)."""
    if not md_text.startswith("---"):
        return set()
    end = md_text.find("\n---", 3)
    if end == -1:
        return set()
    tags = set()
    in_tags = False
    for line in md_text[3:end].splitlines():
        if _FRONTMATTER_TAGS_KEY.match(line):
            in_tags = True
            continue
        if in_tags:
            m = _FRONTMATTER_LIST_ITEM.match(line)
            if m:
                tags.add(m.group(1))
                continue
            in_tags = False
    return tags


def _parse_callouts(md_text, types=CALLOUT_TYPES):
    """[(callout_type, body_lines)] for every Obsidian "> [!type] Title"
    callout in `md_text` whose type (lowercased) is in `types`. The title
    text on the callout's own first line is a section label, not tip
    content, and is discarded here; `body_lines` are the raw ">"-stripped
    lines that follow, up to the first line that isn't itself a ">"
    continuation (a blank line, or the next heading/callout/paragraph)."""
    lines = md_text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        m = _CALLOUT_START.match(lines[i])
        if not m:
            i += 1
            continue
        ctype = m.group(1).lower()
        i += 1
        body = []
        while i < len(lines):
            lm = _CALLOUT_LINE.match(lines[i])
            if not lm:
                break
            body.append(lm.group(1))
            i += 1
        if ctype in types:
            out.append((ctype, body))
    return out


def _callout_items(body_lines):
    """Split one callout's body lines into candidate text units: each "- "/
    "* " bullet is its own item; consecutive non-bullet lines are
    soft-wrapped markdown prose, so they're joined with a space into a
    single item (mirrors how Obsidian itself renders a hard-wrapped
    paragraph - see e.g. quests/passage-through-mirkwood.md's "Companion
    value" callout, two source lines that are one sentence). Blank lines
    separate items. Order-preserving."""
    items = []
    prose = []

    def _flush():
        if prose:
            items.append(" ".join(prose))
            prose[:] = []

    for raw in body_lines:
        line = raw.strip()
        if not line:
            _flush()
            continue
        bm = _BULLET_ITEM.match(line)
        if bm:
            _flush()
            items.append(bm.group(1).strip())
        else:
            prose.append(line)
    _flush()
    return items


def _md_clean(text):
    """Plain-text rendering of one markdown fragment for tip purposes.
    Wikilinks ("[[target|display]]" or "[[target]]") are dropped
    ENTIRELY, not replaced with their display text: a link into our own
    notes vault is never itself useful, standalone, player-facing content,
    and keeping just the display text risks shipping an orphaned pointer
    like "See quest index." (real case, quests/passage-through-mirkwood.md
    - is_useful_tip's own word-count check happens to catch that specific
    one too, but this is the correct fix at the source). "**bold**"/
    "*italic*" markers are unwrapped to their plain text. Whitespace-
    collapsed via _clean_ws."""
    text = _WIKILINK.sub("", text)
    text = _MD_BOLD.sub(r"\1", text)
    text = _MD_ITALIC.sub(r"\1", text)
    return _clean_ws(text)


def load_project_notes(notes_dir=DEFAULT_NOTES, max_tips=MAX_TIPS):
    """{slug: [tip, ...]} for every quests/*.md note whose frontmatter
    `tags:` includes "lotr-lcg/quest" (the per-scenario notes - a cycle
    index, MOC, or mechanic note like quests/dream-chaser.md or quests/
    sailing-tests.md carries a different tag and is skipped). `slug` is
    the file's own basename (quests/passage-through-mirkwood.md ->
    "passage-through-mirkwood") - these already ARE the catalog's own
    scenario slugs (see pickable_scenarios / game.scenario["slug"]), no
    lookup needed.

    Each file's "[!tip]"/"[!warning]" callouts (see _parse_callouts) are
    split into candidate items (see _callout_items), markdown-cleaned (see
    _md_clean), sentence-split (_split_sentences - the same splitter
    summarize() uses), and every resulting sentence must pass
    is_useful_tip - the SAME gate the scraped pipeline uses (these are
    first-party notes, not exempt from quality control just for being
    ours; see build()'s "prefer notes over scraped material", which is a
    preference, not a bypass). Capped at `max_tips` per scenario,
    order-preserving, de-duplicated (case-insensitive) within a file.

    A slug only appears in the result if at least one sentence survived
    the gate - matches build()'s "only write a scenario with >=1 real
    tip" contract. Never raises: a missing notes_dir, an unreadable file,
    or a file with no matching frontmatter tag/callouts/gate-passing
    sentences all just contribute nothing, same posture as the rest of
    this module toward optional, best-effort input."""
    result = {}
    try:
        names = sorted(os.listdir(notes_dir))
    except OSError:
        return result
    for name in names:
        if not name.endswith(".md"):
            continue
        try:
            with open(os.path.join(notes_dir, name), encoding="utf-8") as f:
                md_text = f.read()
        except OSError:
            continue
        if "lotr-lcg/quest" not in _frontmatter_tags(md_text):
            continue
        slug = name[:-len(".md")]

        seen = set()
        tips = []
        for _ctype, body in _parse_callouts(md_text):
            for item in _callout_items(body):
                cleaned = _md_clean(item)
                if not cleaned:
                    continue
                for sentence in _split_sentences(cleaned):
                    if not is_useful_tip(sentence):
                        continue
                    key = sentence.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    tips.append(sentence)
                    if len(tips) >= max_tips:
                        break
                if len(tips) >= max_tips:
                    break
            if len(tips) >= max_tips:
                break
        if tips:
            result[slug] = tips
    return result


# -- fetch: cached, polite GET -----------------------------------------------

def fetch(url, cache_path, delay=DEFAULT_DELAY):
    """GET `url`, using `cache_path` as a persistent on-disk cache: a cache
    hit reads and returns with no network call and no delay; a miss fetches,
    writes the cache file, sleeps `delay` seconds (politeness), and returns.
    Network only past the cache check, not host-tested (mirrors tools/
    build_hob_enrichment.py's fetch_scenario). A transport failure (DNS/
    timeout/HTTP error) raises and is never cached, so a later run retries
    it - the caller (build()) is responsible for catching, logging, and
    counting a failure as a skip rather than failing the whole build."""
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            return f.read()

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        text = resp.read().decode("utf-8", errors="replace")

    cache_dir = os.path.dirname(cache_path)
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(text)
    if delay:
        time.sleep(delay)
    return text


# -- build: orchestrate the whole pipeline -----------------------------------

def _long_arrays(entry, long_entry, orphans, slug):
    """The long form of one scenario's tips, POSITIONAL against the entry
    tips.json just emitted, with null where there is no long form yet.

    The source file is keyed by short text (see DEFAULT_LONG) because that
    is what a human edits and what survives a reorder. The OUTPUT is
    positional because that is what a client wants: index into the array
    beside the tips array it already has, and take the short one when the
    slot is null. The two shapes cannot drift apart - one build writes both
    from the same source in the same pass.

    Any key that matched no tip is appended to `orphans`: its short tip was
    reworded or removed, so its long form is now describing something that
    is not on screen and needs rewriting.
    """
    used = set()

    def arr(tips, pairs):
        out = []
        for t in tips:
            long_text = (pairs or {}).get(t)
            if long_text:
                used.add(t)
            out.append(long_text or None)
        return out

    general = arr(entry.get("general") or [], (long_entry or {}).get("general"))
    stages = {}
    for key, tips in (entry.get("stages") or {}).items():
        stages[str(key)] = arr(tips, ((long_entry or {}).get("stages") or {}).get(str(key)))

    for scope, pairs in [("general", (long_entry or {}).get("general") or {})] + [
            ("stage " + k, v) for k, v in ((long_entry or {}).get("stages") or {}).items()]:
        for short in pairs:
            if short not in used:
                orphans.append((slug, scope, short))

    if not any(x for x in general) and not any(
            x for arr_ in stages.values() for x in arr_):
        return None
    return {"general": general, "stages": stages}


def build(index_path, out_path, distilled_path=DEFAULT_DISTILLED,
          notes_dir=DEFAULT_NOTES, long_path=DEFAULT_LONG,
          long_out_path=None):
    """Compile docs/data/tips.json from COMMITTED sources only. No network.

    Two sources, in precedence order:

    1. tools/data/tips_distilled.json (load_distillation) - per-scenario
       strategy tips this project wrote after reading the Vision of the
       Palantir spotlights, each claim re-checked against the compiled card
       data. Carries both `general` and per-stage `stages`, and covers most
       of the catalog.
    2. quests/*.md callouts (load_project_notes) - this project's own
       hand-authored notes, used ONLY for scenarios the distillation does
       not cover.

    Note the precedence: it is the reverse of what this build used to do.
    Notes used to win outright, which is why tips.json shipped stat lines
    ("Hummerhorns engage at 40 -> ...") instead of strategy - those notes are
    reference tables, written to be read beside the cards, not advice to act
    on mid-game. The distillation is the advice, so it goes first.

    A scenario appears in the output only if at least one tip survived, so
    the modal's "Tips button enabled only where tips exist" contract holds
    directly off this file's keys (see ui/modals.py's QuestCardModal and
    docs/js/screens.js). Only a missing/unreadable `index_path` is fatal -
    an absent distillation or notes directory just means fewer tips."""
    with open(index_path, encoding="utf-8") as f:
        index = json.load(f)
    scenarios = pickable_scenarios(index)

    distilled = load_distillation(distilled_path)
    notes_tips = load_project_notes(notes_dir)
    # OPT-IN, and deliberately not defaulted to DEFAULT_LONG_OUT: build() is
    # called by tests with a tmp `out_path`, and a real path defaulted here
    # meant every one of those runs overwrote the repo's own committed long
    # file with whatever fixture it happened to be using. main() passes the
    # real path; anyone calling build() directly asks for it explicitly.
    long_tips = load_long(long_path) if long_out_path else {}

    long_scenarios = {}
    orphans = []
    out_scenarios = {}
    from_distilled = from_notes = no_tips = skipped = 0
    for scn in scenarios:
        slug = scn.get("slug")
        if not slug:
            skipped += 1
            continue

        entry = distilled.get(slug)
        if entry:
            out_scenarios[slug] = build_entry(
                slug, (entry["attribution"] or {}).get("url"),
                entry["general"], stages=entry["stages"],
                attribution=entry["attribution"] or None)
            from_distilled += 1
            long_entry = _long_arrays(out_scenarios[slug], long_tips.get(slug),
                                      orphans, slug)
            if long_entry:
                long_scenarios[slug] = long_entry
            continue

        if slug in notes_tips:
            out_scenarios[slug] = build_entry(
                slug, None, notes_tips[slug],
                attribution={"name": PROJECT_SOURCE_NAME, "url": ""})
            from_notes += 1
            continue

        no_tips += 1

    # Provenance: credit each source only when it actually contributed, the
    # same rule build_card_data.build_outputs() uses for the Hall of Beorn
    # enrichment. Each entry's own "attribution" stays authoritative; this
    # string only summarizes them.
    parts = []
    if from_distilled:
        parts.append("strategy tips written by this project from %s (%s) "
                     "quest spotlights - summarized, never reproduced, and "
                     "re-checked against the card data"
                     % (SOURCE_NAME, BASE_URL))
    if from_notes:
        parts.append("this project's own quests/*.md notes")
    source = "; ".join(parts) or "no tips available this build"

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated": datetime.date.today().isoformat(),
            "source": source,
            "scenarios": out_scenarios,
        }, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    # The tablet's long form, written whether or not anything is in it yet:
    # an empty map is a valid answer ("no scenario has a long form"), and a
    # client that has to distinguish "absent file" from "empty file" is a
    # client with two code paths for one state.
    if long_out_path:
        long_out_dir = os.path.dirname(long_out_path)
        if long_out_dir:
            os.makedirs(long_out_dir, exist_ok=True)
        with open(long_out_path, "w", encoding="utf-8") as f:
            json.dump({
                "generated": datetime.date.today().isoformat(),
                "source": LONG_SOURCE,
                "scenarios": long_scenarios,
            }, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    # An orphan is a long tip whose short tip was reworded or removed, so it
    # now describes something no longer on screen. Loud, but never fatal: it
    # costs that one tip its long form, which is exactly the degrade the
    # whole long path is built to survive.
    for slug, scope, short in orphans:
        print("build_tips: WARNING orphaned long tip - %s / %s / %r"
              % (slug, scope, short[:60]))

    long_count = sum(1 for v in long_scenarios.values()
                     for arr_ in [v["general"], *v["stages"].values()]
                     for x in arr_ if x)
    summary = {"resolved": from_distilled + from_notes,
               "from_distilled": from_distilled, "from_notes": from_notes,
               "no_tips": no_tips, "skipped": skipped,
               "total": len(scenarios),
               "long_scenarios": len(long_scenarios), "long_tips": long_count,
               "orphans": len(orphans)}
    print("build_tips: %d scenarios with tips (%d distilled, %d from project "
          "notes), %d without, %d skipped (of %d pickable) -> %s"
          % (summary["resolved"], from_distilled, from_notes, no_tips,
             skipped, len(scenarios), out_path))
    if long_out_path:
        print("build_tips: long form for %d tips across %d scenarios%s -> %s"
              % (long_count, len(long_scenarios),
                 (", %d orphaned" % len(orphans)) if orphans else "",
                 long_out_path))
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Compile docs/data/tips.json from the committed distilled "
                     "strategy tips plus this project's quests/*.md notes. "
                     "Reads only local files - never touches the network.")
    ap.add_argument("--index", default=DEFAULT_INDEX,
                     help="catalog index.json to read scenarios from "
                          "(default: %s - run tools/build_card_data.py first)"
                          % DEFAULT_INDEX)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--distilled", default=DEFAULT_DISTILLED,
                     help="committed distilled strategy tips (default: %s); "
                          "a missing or corrupt file is skipped, leaving only "
                          "the quests/*.md notes - see load_distillation()"
                          % DEFAULT_DISTILLED)
    ap.add_argument("--notes", default=DEFAULT_NOTES,
                     help="directory of hand-authored quest notes "
                          "(default: %s) - used only for scenarios the "
                          "distillation does not cover, see build()"
                          % DEFAULT_NOTES)
    ap.add_argument("--long", default=DEFAULT_LONG,
                     help="committed LONG-form tips, keyed by each short "
                          "tip's own text (default: %s); missing or corrupt "
                          "is skipped and every tip keeps its short form - "
                          "see load_long()" % DEFAULT_LONG)
    ap.add_argument("--long-out", default=DEFAULT_LONG_OUT,
                     help="where to write the tablet's long-form file "
                          "(default: %s). NOT under docs/data/: the device "
                          "deploy copies that directory whole and the Presto "
                          "cannot show this text." % DEFAULT_LONG_OUT)
    ap.add_argument("--refresh", action="store_true",
                     help="rebuild --out even though it already exists. "
                          "Without this an existing --out is left alone - it "
                          "is committed derived data, see needs_refresh().")
    args = ap.parse_args(argv)

    # The long output rides along with --out, so an --out that is present
    # while the long file is not still has work to do (the first build after
    # this landed, and any checkout that predates it).
    if not needs_refresh(args.out, args.refresh) and os.path.exists(args.long_out):
        print("build_tips: %r already present (committed derived data - see "
              "CLAUDE.md's Card data section); nothing rebuilt. Pass "
              "--refresh to regenerate it." % args.out)
        return 0

    if not os.path.exists(args.index):
        raise SystemExit("No catalog index at %r - run tools/build_card_data.py "
                          "first." % args.index)
    build(args.index, args.out, distilled_path=args.distilled,
          notes_dir=args.notes, long_path=args.long,
          long_out_path=args.long_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
