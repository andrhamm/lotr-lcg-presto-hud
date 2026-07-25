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

MAX_LEN = 140    # chars per tip - see the plan's Global Constraints
MAX_TIPS = 4     # tips per scenario

DEFAULT_INDEX = os.path.join("docs", "data", "index.json")
DEFAULT_OUT = os.path.join("docs", "data", "tips.json")
DEFAULT_CACHE = os.path.join("tools", "data", "tips_cache")
DEFAULT_NOTES = os.path.join("quests")
DEFAULT_DELAY = 1.0  # seconds after each real network fetch (politeness)


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

def build(index_path, out_path, cache_dir, limit=None, delay=DEFAULT_DELAY,
          notes_dir=DEFAULT_NOTES):
    """For every pickable quest scenario in the catalog index at
    `index_path` (see pickable_scenarios): if load_project_notes(notes_dir)
    has tips for it, use those (first-party, preferred - see the module
    docstring's Sources); otherwise resolve its VotP article URL
    (match_article against the cached sitemap), fetch+cache the article,
    and summarize it into at most MAX_TIPS short original-phrasing tips
    (see summarize). Writes {"generated", "source", "scenarios": {slug:
    build_entry(...)}} to `out_path` - a scenario is only included if at
    least one tip survived (from either source), so the modal's "Tips
    button enabled only where tips exist" contract (see docs/js/screens.js
    / ui/modals.py's QuestCardModal) holds directly off this file's keys.

    Never raises for a single scenario's failure, nor for the sitemap fetch
    itself failing (both are optional/best-effort, matching tools/
    build_hob_enrichment.py's posture) - only a missing/unreadable --index
    catalog (nothing to build tips for) is the CLI's job to reject early
    with a friendly SystemExit (see main()). `limit` caps how many pickable
    scenarios are processed (for a quick --limit smoke run); `delay` is
    passed through to fetch(); `notes_dir` is passed through to
    load_project_notes() (a test may point it at an empty/fixture
    directory to exercise the scraped pathway in isolation)."""
    with open(index_path, encoding="utf-8") as f:
        index = json.load(f)
    scenarios = pickable_scenarios(index)
    if limit is not None:
        scenarios = scenarios[:limit]

    notes_tips = load_project_notes(notes_dir)

    try:
        sitemap_xml = fetch(SITEMAP_URL, os.path.join(cache_dir, "sitemap.xml"), delay=delay)
        sitemap_slugs = parse_sitemap(sitemap_xml)
    except Exception as e:
        print("build_tips: sitemap fetch failed (%r) - no scenarios can be "
              "matched this run" % (e,))
        sitemap_slugs = {}

    out_scenarios = {}
    resolved = no_url = no_tips = skipped = from_notes = 0
    for scn in scenarios:
        slug, name = scn.get("slug"), scn.get("name")
        if not slug:
            skipped += 1
            continue

        if slug in notes_tips:
            out_scenarios[slug] = build_entry(
                slug, None, notes_tips[slug],
                attribution={"name": PROJECT_SOURCE_NAME, "url": ""})
            resolved += 1
            from_notes += 1
            continue

        url = match_article(slug, sitemap_slugs)
        if not url:
            no_url += 1
            continue
        try:
            article_html = fetch(url, os.path.join(cache_dir, "%s.html" % slug), delay=delay)
        except Exception as e:
            print("build_tips: fetch failed for %r (%s) - skipping" % (name, e))
            skipped += 1
            continue
        tips = summarize(extract_blocks(article_html))
        if not tips:
            no_tips += 1
            continue
        out_scenarios[slug] = build_entry(slug, url, tips)
        resolved += 1

    # Provenance: only credit the scrape when a scraped tip actually survived
    # the gate. Mirrors build_card_data.build_outputs()'s "only claim Hall of
    # Beorn as a source when enrichment was really merged" rule, and it
    # matters more here now that this file is COMMITTED: the gate is strict
    # enough that a run can (and currently does) end up with every entry
    # sourced from quests/*.md, in which case a hardcoded Vision of the
    # Palantir credit would attribute our own words to a third party. Each
    # entry's own "attribution" is authoritative either way; this string just
    # summarizes them.
    if resolved - from_notes > 0:
        source = ("%s (%s) - summarized, not reproduced; some scenarios use "
                   "this project's own quests/*.md notes instead"
                   % (SOURCE_NAME, BASE_URL))
    else:
        source = ("this project's own quests/*.md notes - no %s material "
                   "survived summarization this build; see each scenario's "
                   "attribution" % SOURCE_NAME)

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated": datetime.date.today().isoformat(),
            "source": source,
            "scenarios": out_scenarios,
        }, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    summary = {"resolved": resolved, "from_notes": from_notes, "no_url": no_url,
               "no_tips": no_tips, "skipped": skipped, "total": len(scenarios)}
    print("build_tips: resolved %d (%d from project notes), no_url %d, "
          "no_tips %d, skipped %d (of %d pickable scenarios) -> %s"
          % (resolved, from_notes, no_url, no_tips, skipped, len(scenarios), out_path))
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Fetch/summarize Vision of the Palantir strategy tips "
                     "for the quest catalog.")
    ap.add_argument("--index", default=DEFAULT_INDEX,
                     help="catalog index.json to read scenarios from "
                          "(default: %s - run tools/build_card_data.py first)"
                          % DEFAULT_INDEX)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--notes", default=DEFAULT_NOTES,
                     help="directory of hand-authored quest notes "
                          "(default: %s) - preferred over the scrape when "
                          "a scenario has both, see load_project_notes()"
                          % DEFAULT_NOTES)
    ap.add_argument("--refresh", action="store_true",
                     help="re-fetch and overwrite --out even though it already "
                          "exists. Without this, an existing --out is left "
                          "alone and nothing is fetched - see needs_refresh().")
    ap.add_argument("--limit", type=int, default=None,
                     help="only process the first N pickable scenarios "
                          "(quick smoke run)")
    ap.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                     help="seconds to sleep after each real network fetch "
                          "(default %.1f; not applied on cache hits)" % DEFAULT_DELAY)
    args = ap.parse_args(argv)

    if not needs_refresh(args.out, args.refresh):
        print("build_tips: %r already present (committed derived data - see "
              "CLAUDE.md's Card data section); nothing fetched. Pass "
              "--refresh to rebuild it." % args.out)
        return 0

    if not os.path.exists(args.index):
        raise SystemExit("No catalog index at %r - run tools/build_card_data.py "
                          "first." % args.index)
    build(args.index, args.out, args.cache, limit=args.limit, delay=args.delay,
          notes_dir=args.notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
