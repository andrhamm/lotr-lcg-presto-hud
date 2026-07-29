"""Validate the distilled advancement conditions and dynamic X values.

Two artifacts, one problem: **a card whose number is not a number.**

`advancement_distilled.json` -- ~177 of the catalog's stage cards print **0
quest points**. They do not advance by filling a progress bar; they advance on
a condition (an enemy defeated, an objective claimed, a pile of resource
tokens) or they cannot be defeated at all. Drawing a 0/0 bar for those is a
lie, so the UI shows the condition sentence in that space instead.

`location_dynamic_distilled.json` -- 84 location faces print a literal **X**
for their quest points, their threat, or both. `build_card_data.py` flattens
that X to `None`, which the compiled DB cannot tell apart from a missing
value, so the picker has nothing to fill in and the staging total cannot be
computed. 45 of those cards define X in their own text; this file holds those
definitions, and the other 39 (whose X is defined on the quest card or an
objective) are left for the player to set.

**`None` here means X, not absent** -- confirmed against the pinned upstream
TSV, which stores the literal string `"X"` for exactly these faces.

**The artifact is committed and this tool does not regenerate it.** It was
produced once by an LLM extraction (one agent per card, reading only that
card's printed text against `docs/superpowers/specs/advancement-extraction.md`)
and its output is our own words, so it is committed under the same
verbatim-vs-derived line as `tips_distilled.json` -- see CLAUDE.md's "What may
be committed". Nothing fetches anything here; a plain run only checks.

What it checks, and why this needs more than the tip gate:

An advancement condition is **not a tip**. A tip is advice a player can
ignore; this is a rules claim they act on mid-game, so iron rule 4 applies at
full force. Beyond the prose rules `build_tips.py` already has, every field is
**grounded**: each proper noun and each trigger keyword in a distilled line
must actually appear in that card's own printed text. That is what catches the
failure mode this content type has and tips do not -- inventing a card name, a
keyword, or a trigger that reads perfectly plausible.

Grounding is also the drift alarm. The card DB is pinned
(`tools/data/cardDb.SOURCE.txt`) and regenerated; when the pin moves and a
card's text changes under us, a line that used to be true stops grounding and
this exits non-zero rather than shipping stale advice.

Deliberately NOT checked: non-ASCII. The card DB stores `Nazgul` with its
circumflex and a dozen other accented names. Folding to ASCII is a rendering
concern for the device's 82-glyph font, not a storage one.

    python3 tools/build_advancement.py            # validate, exit 1 on failure
    python3 tools/build_advancement.py --report   # + per-card coverage

Requires the compiled card DB, so build it first:

    python3 tools/build_card_data.py
"""
import glob
import html
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENARIOS = os.path.join(ROOT, "docs", "data", "scenarios")
DISTILLED = os.path.join(ROOT, "tools", "data", "advancement_distilled.json")
LOCATIONS = os.path.join(ROOT, "tools", "data",
                         "location_dynamic_distilled.json")

MAX_LEN = 120           # hard ceiling; the spec asks authors to target 90
MIN_WORDS = 4

# Trigger words and game keywords a distilled line must not introduce.
KEYWORDS = ("Forced", "Response", "When Revealed", "Action", "Surge", "Doomed",
            "Travel", "Victory", "Battle", "Siege", "Ranged", "Sentinel",
            "Guarded", "Archery", "Time", "Assault", "Defense", "Fortitude")

_WORD = re.compile(r"[A-Za-z'À-ɏ]+")
# A card name is a run of capitalised words, optionally joined by a lowercase
# connective -- but the connective MUST be followed by another capitalised
# word. Without that requirement "Otherwise the players lose" parses as a card
# named "Otherwise the", and every conditional sentence fails grounding.
_CAP = r"[A-Z][a-zÀ-ɏ']+"
_PROPER = re.compile(r"\b(%s(?:[\s-]+(?:of|the|in|de|and|to)[\s-]+%s"
                     r"|[\s-]+%s)*)" % (_CAP, _CAP, _CAP))


def _sentence_openers(text):
    """Offsets of capitalised words that OPEN a sentence. Those are sentence
    case, not card names. Finding them positionally beats keeping a word list
    that needs a new entry for every "Advances" vs "Advance"."""
    return {m.start(1) for m in re.finditer(r"(?:^|[.!?]\s+)([A-Z][a-z]*)", text)}


def _norm(s):
    """Collapse whitespace and undo HTML entities -- the upstream TSV carries
    a few (`Rob &amp; Bob`), and they must not reach the screen."""
    return re.sub(r"\s+", " ", html.unescape(s or "")).strip()


def _fold(s):
    """Accent-insensitive compare, so a line writing `Nazgul` still grounds
    against a card printing it with the circumflex, and the reverse."""
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if unicodedata.category(c) != "Mn")


def ground(condition, card_text):
    """Proper nouns and keywords in `condition` absent from the card's own
    text. Empty list means grounded."""
    src = _fold(_norm(card_text))
    bad = []
    for kw in KEYWORDS:
        # Case-SENSITIVE in the condition: cards print these capitalised, and
        # matching loosely flags ordinary English -- "each time the location is
        # explored" is not the Time keyword, and "a racing defense test" is not
        # the Defense icon.
        if re.search(r"\b%s\b" % re.escape(kw), condition) \
                and _fold(kw) not in src and kw not in bad:
            bad.append(kw)
    openers = _sentence_openers(condition)
    for m in _PROPER.finditer(condition):
        tok = m.group(1).strip()
        if m.start(1) in openers:
            # Sentence case. Drop the opening word and ground what follows --
            # "Otherwise Lake-town burns" opens with an adverb but still names
            # Lake-town.
            tok = tok.split(None, 1)[1].strip() if " " in tok else ""
            if not tok:
                continue
        # A possessive may be ours (the card prints "Saruman", we write
        # "Saruman's tokens") or the card's own name ("Frodo's Choice").
        # Accept either form; stripping unconditionally rejects the real names.
        probes = (tok, re.sub(r"['’]s\b", "", tok))
        if not any(_fold(p) in src for p in probes) and tok not in bad:
            bad.append(tok)
    return bad


def check(value, card_text):
    """(ok, reason) for one prose field."""
    c = _norm(value)
    if not c:
        return False, "empty"
    if len(c) > MAX_LEN:
        return False, "too long (%d > %d)" % (len(c), MAX_LEN)
    if not c[0].isupper() and not c[0].isdigit():
        return False, "does not start with a capital"
    if c[-1] not in ".!?":
        return False, "not a sentence"
    if len(_WORD.findall(c)) < MIN_WORDS:
        return False, "too few words"
    if re.search(r"\b(you|your|yours)\b", c, re.I):
        return False, "second person (the Presto sits between four players)"
    if re.search(r"\b(tap|screen|button|tracker|app)\b", c, re.I):
        return False, "talks about the app"
    ungrounded = ground(c, card_text)
    if ungrounded:
        return False, "not grounded in card text: %s" % ", ".join(ungrounded)
    return True, "ok"


def zero_point_stages():
    """{key: printed text} for every stage card printing 0 quest points.

    Keyed `slug::stage::name`. Reads the B face where it carries the text and
    falls back to A -- side A is story/setup and side B carries the quest
    points, but plenty of cards print their condition on only one of the two.
    """
    out = {}
    for path in sorted(glob.glob(os.path.join(SCENARIOS, "*.json"))):
        with open(path) as fh:
            data = json.load(fh)
        slug = data.get("slug")
        for stage in ((data.get("quest") or {}).get("stages") or []):
            n = stage.get("stage")
            for card in (stage.get("cards") or []):
                if card.get("questPoints"):
                    continue
                faces = card.get("faces") or []
                b = next((f for f in faces if f.get("side") == "B"), None)
                a = next((f for f in faces if f.get("side") == "A"), None)
                face = b if (b and b.get("text")) else a
                if not face:
                    continue
                out["%s::%s::%s" % (slug, n, face.get("name"))] = \
                    face.get("text") or ""
    return out


def x_printing_locations():
    """{key: face} for every location face that prints a literal X for quest
    points or threat. Keyed `encounterSet::name::side` -- a location name
    recurs across encounter sets with different values, so the name alone is
    not unique.

    Gated on the `*Kind == "x"` markers build_card_data.py now emits, NOT on
    `value is None`. Those are not the same set: a null covers X, "-" (the
    stat does not apply) and blank alike, and testing for null let three
    fabricated formulas into this artifact -- a quest-point formula on The
    Mere of Dead Faces, which prints "-", a threat formula on Great Corsair
    Ship, which prints 0, and both fields of Rider of Mirkwood, which is an
    Enemy the compiled DB happens to file under `encounter.location`.
    """
    out = {}
    for path in sorted(glob.glob(os.path.join(SCENARIOS, "*.json"))):
        with open(path) as fh:
            data = json.load(fh)
        for card in ((data.get("encounter") or {}).get("location") or []):
            es = card.get("encounterSet")
            for face in (card.get("faces") or []):
                if face.get("questPointsKind") != "x" \
                        and face.get("threatKind") != "x":
                    continue
                key = "%s::%s::%s" % (es, face.get("name"),
                                      face.get("side") or "-")
                out.setdefault(key, face)
    return out


def check_formula(field, value, face, text):
    """(ok, reason) for one location X formula. Renders inline after a label,
    so it is a lowercase fragment, not a sentence."""
    v = _norm(value)
    if len(v) > 90:
        return False, "too long (%d > 90)" % len(v)
    if v[0].isupper():
        return False, "should be a lowercase fragment"
    if v.endswith("."):
        return False, "trailing period"
    stat = "questPoints" if field == "quest_points" else "threat"
    if face.get(stat + "Kind") != "x":
        printed = face.get(stat)
        return False, ("card prints %s here, not X"
                       % ("'-' (stat does not apply)"
                          if face.get(stat + "Kind") == "na"
                          else repr(printed)))
    bad = ground(v, text)
    if bad:
        return False, "not grounded in card text: %s" % ", ".join(bad)
    return True, "ok"


def validate_locations():
    """(checked, failures, unknown) over location_dynamic_distilled.json."""
    faces = x_printing_locations()
    with open(LOCATIONS) as fh:
        distilled = json.load(fh)
    failures, unknown = [], []
    for key, entry in sorted(distilled.items()):
        face = faces.get(key)
        if face is None:
            unknown.append(key)
            continue
        text = face.get("text") or ""
        for field in ("quest_points", "threat"):
            if entry.get(field):
                ok, why = check_formula(field, entry[field], face, text)
                if not ok:
                    failures.append((key, field, why))
    return distilled, faces, failures, unknown


def main():
    if not os.path.isdir(SCENARIOS):
        raise SystemExit("no compiled card DB at %s\n"
                         "run: python3 tools/build_card_data.py" % SCENARIOS)
    stages = zero_point_stages()
    with open(DISTILLED) as fh:
        distilled = json.load(fh)

    failures, unknown = [], []
    for key, entry in sorted(distilled.items()):
        text = stages.get(key)
        if text is None:
            unknown.append(key)
            continue
        for field in ("advance", "lose"):
            if entry.get(field):
                ok, why = check(entry[field], text)
                if not ok:
                    failures.append((key, field, why))
        if entry.get("quest_points"):
            # A formula, not prose: ground it, skip the sentence rules.
            bad = ground(_norm(entry["quest_points"]), text)
            if bad:
                failures.append((key, "quest_points",
                                 "not grounded: %s" % ", ".join(bad)))

    covered = len(distilled) - len(unknown)
    print("%d zero-quest-point stage cards in the catalog" % len(stages))
    print("%d carry a distilled condition (%d silent)"
          % (covered, len(stages) - covered))
    for f in ("advance", "lose", "quest_points"):
        print("  %-13s %d" % (f, sum(1 for v in distilled.values() if v.get(f))))

    if "--report" in sys.argv:
        for key, entry in sorted(distilled.items()):
            print("\n%s" % key)
            for f in ("advance", "lose", "quest_points"):
                if entry.get(f):
                    print("  %-13s %s" % (f + ":", entry[f]))

    loc, faces, loc_failures, loc_unknown = validate_locations()
    print("\n%d location faces print X for quest points or threat" % len(faces))
    print("%d carry a distilled formula (%d left for the player to set)"
          % (len(loc) - len(loc_unknown), len(faces) - len(loc) + len(loc_unknown)))
    for f in ("quest_points", "threat"):
        print("  %-13s %d" % (f, sum(1 for v in loc.values() if v.get(f))))

    if "--report" in sys.argv:
        for key, entry in sorted(loc.items()):
            print("\n%s" % key)
            for f in ("quest_points", "threat"):
                if entry.get(f):
                    print("  %-13s X is %s" % (f + ":", entry[f]))

    unknown += loc_unknown
    failures += loc_failures
    if unknown:
        print("\n%d distilled keys are not in the catalog "
              "(card DB pin moved?):" % len(unknown))
        for k in unknown:
            print("  %s" % k)
    if failures:
        print("\n%d field(s) failed validation:" % len(failures))
        for key, field, why in failures:
            print("  %-58s %s: %s" % (key[:58], field, why))
    if unknown or failures:
        raise SystemExit(1)
    print("\nok")


if __name__ == "__main__":
    main()
