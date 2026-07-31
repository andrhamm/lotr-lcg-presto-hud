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


def test_xtargets_labels_are_ascii_only():
    """xtargets ships device-rendered stepper labels but had no ASCII gate.

    _strings() walks viewcopy only, so "Nazgul enemies in play" sat in
    xtargets.TARGETS with a circumflex for as long as the entry existed - drawn
    on the counter modal, measured at 4px per unknown glyph, invisible to every
    layout test. Same rule as test_copy_is_ascii_only, separate collector
    because these are field labels rather than prose and the third-person and
    spaced-dash rules do not govern them.
    """
    import xtargets
    bad = [(k, v["label"]) for k, v in xtargets.TARGETS.items()
           if any(ord(c) > 127 for c in v["label"])]
    assert not bad, "non-ASCII xtargets label: %s" % bad


def test_copy_uses_no_spaced_dash():
    """Use two sentences. A dash invites a trailing clause, and the trailing
    clause is where vague copy hides - splitting one such sentence is what
    exposed that "resolve each When Revealed" was narrower than the rule."""
    bad = [(g, s) for g, s in _strings()
           if " - " in s or " -- " in s or "—" in s]
    assert not bad, "spaced dash in copy: %s" % [b[1][:70] for b in bad[:8]]


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


# --------------------------------------------------------------------------
# Computed copy
# --------------------------------------------------------------------------

def _staging_window(**state):
    """Draw the staging action window and return its text."""
    from tests.fake_hardware import FakeHardware
    from ui.theme import Palette
    from ui.screen_play import ScreenPlay
    from gamestate import GameState, VIEW_STEP
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = GameState(4, 25)
    g.quest = {"stage_n": 2, "side": "B", "points": 8, "progress": 0}
    g.active_locations = []
    for k, v in state.items():
        setattr(g, k, v)
    g.view = "aw_quest_staging"
    g.step = VIEW_STEP[g.view]
    s = ScreenPlay()
    s.draw(hw, g, pal)
    return " ".join(str(c[1]) for c in hw.display.calls if c[0] == "text")


def test_staging_window_warns_on_a_pending_failure():
    t = _staging_window(willpower=2, staging=7)
    assert "Without actions" in t
    assert "raises threat by 5" in t


def test_staging_window_names_the_player_a_failure_would_eliminate():
    from gamestate import GameState
    g = GameState(4, 25)
    g.players[2].threat = 46
    t = _staging_window(willpower=2, staging=7, players=g.players)
    assert "eliminated at 50" in t
    assert "P3" in t


def test_staging_window_says_a_tie_is_neither_outcome():
    t = _staging_window(willpower=7, staging=7)
    assert "no progress and no" in t
    # +1 willpower turns a tie into a 1-progress success: the cheapest win on
    # the board, and easy to miss because a tie reads as a failure.
    assert "places 1" in t


def test_staging_window_offers_the_exchange_rate_only_while_there_is_room():
    """Past the stage's quest points the extra is DISCARDED (p.22), so the
    same line would be advising a play that wastes cards."""
    room = _staging_window(willpower=11, staging=7)
    assert "places 1 more" in room

    full = _staging_window(willpower=11, staging=7,
                           quest={"stage_n": 2, "side": "B",
                                  "points": 8, "progress": 8})
    assert "is discarded" in full
    assert "places 1 more" not in full


def test_room_counts_the_active_location_not_just_the_quest():
    """Progress fills the active location first and its overflow flows on to
    the quest (RR 3.4). Testing the quest card alone would tell a player their
    willpower is wasted while a location is still soaking it up."""
    from gamestate import GameState
    g = GameState(4, 25)
    g.quest = {"stage_n": 2, "side": "B", "points": 8, "progress": 8}
    g.active_locations = [{"points": 3, "progress": 0}]
    g.willpower, g.staging = 11, 7
    _, _, room = g.quest_preview()
    assert room == 3, "the unfilled location is still room"


def test_combat_player_always_warns_about_refresh_elimination():
    """Unconditional by design.

    67 cards interact with the refresh threat raise and several replace it
    outright, so a threshold built on threat_per_round fails silently and in
    the dangerous direction - a player at 44 facing Nalir in a four-player
    game (+1 per player) would get no warning at all.
    """
    from tests.scenes import SCENES
    hw, _ = SCENES["play_combat_player"]()
    t = " ".join(str(c[1]) for c in hw.display.calls if c[0] == "text")
    assert "refresh may eliminate" in t
