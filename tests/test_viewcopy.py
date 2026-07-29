"""Gates on play-screen copy and on the generated web-twin mirrors.

Two jobs, and the second one is the reason this file exists at all.

**Freshness.** `docs/js/{phases,icons,metrics,viewcopy}.js` are generated from
Python sources. Nothing used to check they were regenerated after their source
changed, so a stale mirror shipped silently to the Pages build.

**Copy rules.** The house rules on wording were written down in the design
system and then broken repeatedly, because nothing enforced them. Now that all
copy lives in one module they are cheap to check. Each rule below cites the
failure that motivated it.
"""
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import viewcopy  # noqa: E402

GENERATED = ("phases.js", "icons.js", "metrics.js", "viewcopy.js")


# --------------------------------------------------------------------------
# Freshness
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name", GENERATED)
def test_generated_mirrors_are_up_to_date(name):
    """Regenerating must be a no-op. If this fails, run:

        python3 tools/gen_web_data.py
    """
    path = os.path.join(ROOT, "docs", "js", name)
    before = open(path, "rb").read()
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "gen_web_data.py")],
                   cwd=ROOT, check=True, capture_output=True)
    after = open(path, "rb").read()
    assert before == after, (
        "%s is stale - its Python source changed without regenerating. "
        "Run: python3 tools/gen_web_data.py" % name)


def test_every_copy_group_reaches_the_web_twin():
    """A new group in viewcopy.py must appear in the generated module.

    The generator exports every uppercase dict/list, so this holds by
    construction - the test guards against someone narrowing that filter.
    """
    js = open(os.path.join(ROOT, "docs", "js", "viewcopy.js")).read()
    exported = set(re.findall(r"^export const ([A-Z_]+)", js, re.M))
    expected = {n for n in dir(viewcopy)
                if n.isupper()
                and isinstance(getattr(viewcopy, n), (dict, list, str))}
    assert expected - exported == set(), (
        "not reaching the web twin: %s" % sorted(expected - exported))


# --------------------------------------------------------------------------
# Copy rules
# --------------------------------------------------------------------------

def _strings():
    """Every player-facing string in viewcopy, as (group, text) pairs."""
    out = []

    def walk(group, v):
        if isinstance(v, str):
            out.append((group, v))
        elif isinstance(v, (list, tuple)):
            for item in v:
                walk(group, item)
        elif isinstance(v, dict):
            for item in v.values():
                walk(group, item)

    for name in dir(viewcopy):
        if not name.isupper():
            continue
        val = getattr(viewcopy, name)
        if isinstance(val, (dict, list, str)):
            walk(name, val)
    return out


def test_copy_is_ascii_only():
    """BITMAP8_W measures an unknown glyph as 4px, so a curly quote or an
    arrow passes every layout test and renders as garbage on the device."""
    bad = [(g, s) for g, s in _strings() if any(ord(c) > 127 for c in s)]
    assert not bad, "non-ASCII copy: %s" % bad[:5]


@pytest.mark.xfail(strict=True, reason=
    "spaced dashes are removed by T4-T7 (the copy rewrite); strict=True so this flips to a real gate the moment it passes")
def test_copy_uses_no_spaced_dash():
    """Use two sentences. A dash invites a trailing clause, and the trailing
    clause is where vague copy hides - splitting one such sentence is what
    exposed that "resolve each When Revealed" was narrower than the rule."""
    bad = [(g, s) for g, s in _strings()
           if " - " in s or " -- " in s or "—" in s]
    assert not bad, "spaced dash in copy: %s" % [b[1][:70] for b in bad[:8]]


@pytest.mark.xfail(strict=True, reason=
    "the second-person purge lands in T4; strict=True so this flips to a real gate the moment it passes")
def test_copy_is_third_person():
    """The Presto sits between four players, so "your threat" has no referent.

    Name the actor instead: the active player, each player, the first player,
    the players.
    """
    second = re.compile(r"\b(you|your|yours|yourself)\b", re.I)
    bad = [(g, s) for g, s in _strings() if second.search(s)]
    assert not bad, "second person in copy: %s" % [b[1][:70] for b in bad[:8]]


def test_copy_does_not_reuse_bold_trigger_words_as_framework_prose():
    """`Action`, `Forced`, `Response`, `When Revealed`, `Travel`, `Surge` and
    `Doomed` name printed card abilities. A draft opened a framework step with
    "Forced, not optional", but RR defines `Forced` as "a bold trigger word"
    for mandatory triggered abilities and never applies it to engagement.

    Quoted card text is fine - that is the term naming itself - so a trigger
    word inside double quotes is allowed.
    """
    reserved = ("Forced", "Surge", "Doomed", "Response", "When Revealed")
    bad = []
    for g, s in _strings():
        unquoted = re.sub(r'\\?"[^"]*\\?"', "", s)
        for word in reserved:
            # Only a sentence-LEADING use is the descriptor form. Naming the
            # keyword mid-sentence is correct usage: "Keywords on setup
            # reveals (Surge/Doomed) do resolve" is exactly right.
            if re.search(r"(?:^|\. )%s\b(?!:)" % word, unquoted):
                bad.append((g, word, s[:70]))
    assert not bad, "reserved trigger word as prose: %s" % bad[:5]


def test_view_labels_cover_every_view():
    """A view without a label crashes the CTA, which reads VIEW_LABELS[view]."""
    from gamestate import VIEW_ORDER, VIEW_STEP
    missing = [v for v in list(VIEW_ORDER) + list(VIEW_STEP)
               if v not in viewcopy.VIEW_LABELS]
    assert not missing, "views with no label: %s" % missing
