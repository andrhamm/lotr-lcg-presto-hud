"""Contextual phase skipping, and the rule that keeps it rules-safe.

From the first full two-player playtest: "lots of tapping ... when there are
no enemies in the staging area or engaged following staging, we can completely
skip over combat."

The danger in that is real. An action window is a player's opportunity to act,
and a phase-locked ability can ONLY be initiated during a window of its own
phase. Jumping past the final window of a skipped span silently removes an
opportunity someone may have been holding a card for -- and the compiled
catalog says that is not hypothetical: 34 distinct cards print
"Combat Action:".

So a skip never lands on its nominal destination. It lands on the last action
window before it. These tests pin that rule down.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import phases
from gamestate import (GameState, VIEW_ORDER, VIEW_STEP, is_action_window,
                       last_window_before, skips_from)


def _at(view):
    g = GameState()
    g.enter_view(view)
    return g


# -- the landing rule ------------------------------------------------------

def test_combat_windows_are_phase_views_not_aw_screens():
    """The reason is_action_window exists rather than reusing is_window_view.

    Combat has no `aw_` screens; its windows ARE combat_enemy (6.E) and
    combat_player (6.P). A naming-convention check would miss both, which are
    precisely the windows a combat skip passes over.
    """
    from gamestate import is_window_view

    for v in ("combat_enemy", "combat_player"):
        assert is_action_window(v), "%s should be an action window" % v
        assert not is_window_view(v), "%s is not an aw_ screen" % v


def test_landing_is_the_last_window_before_the_target():
    landing = last_window_before("refresh")
    assert landing == "combat_player"
    assert is_action_window(landing)


def test_nothing_between_the_landing_and_the_target_is_a_window():
    """The defining property: no opportunity is passed over after landing."""
    target = "refresh"
    landing = last_window_before(target)
    between = VIEW_ORDER[VIEW_ORDER.index(landing) + 1:VIEW_ORDER.index(target)]
    assert not [v for v in between if is_action_window(v)]


def test_every_declared_skip_lands_on_a_real_window():
    from gamestate import SKIPS

    for s in SKIPS:
        landing = last_window_before(s["to"])
        assert landing is not None, "%s has no window to land on" % s["id"]
        assert is_action_window(landing)
        assert VIEW_ORDER.index(landing) < VIEW_ORDER.index(s["to"])


# -- offering --------------------------------------------------------------

def test_skips_are_contextual_not_global():
    """Almost every view offers nothing. A skip button that is always there
    is a skip button nobody reads."""
    offering = [v for v in VIEW_ORDER if skips_from(v)]
    assert offering == ["aw_enc_checks"]


def test_a_skip_never_eats_the_window_of_the_phase_it_starts_in():
    """The flaw the generalised guard found.

    Offering the combat skip on enc_checks would jump the player over
    aw_enc_checks - the encounter phase's own action window, which they have
    not had yet. Passing windows on the way to a landing is allowed; eating
    the window you are standing in front of is not.
    """
    from gamestate import SKIPS

    for s in SKIPS:
        for origin in s["from"]:
            own = "aw_" + origin if not origin.startswith("aw_") else None
            assert own is None or own not in VIEW_ORDER[
                VIEW_ORDER.index(origin):], (
                "%s is offered on %s, whose own window %s comes later"
                % (s["id"], origin, own))


def test_skip_is_not_offered_where_it_would_go_backwards():
    g = _at("refresh")
    assert g.skip_to("combat_empty") is None


def test_unknown_skip_is_refused():
    g = _at("aw_enc_checks")
    assert g.skip_to("nope") is None


# -- taking the skip -------------------------------------------------------

def test_taking_the_skip_lands_on_the_last_combat_window():
    g = _at("aw_enc_checks")
    assert g.skip_to("combat_empty") == "combat_player"
    assert g.view == "combat_player"
    assert g.step == VIEW_STEP["combat_player"] == "6.P"


def test_the_skip_is_recorded_in_the_log():
    """Not silent: a player reading back can see what was passed over."""
    g = _at("aw_enc_checks")
    before = len(g.log)
    g.skip_to("combat_empty")
    assert len(g.log) > before
    entry = " ".join(str(e.get("text", "")) for e in g.log[-2:])
    assert "Skipped" in entry
    assert "combat_shadow" in entry and "combat_enemy" in entry
    # and it names what the player asserted, not just what it did
    assert "No enemies" in entry


def test_the_skip_saves_taps_but_keeps_the_last_window():
    """The point of the feature, stated as an assertion.

    Walking normally from the encounter window to the last combat window costs
    one advance per view; the skip costs one. The window itself is still
    visited either way.
    """
    walk = _at("aw_enc_checks")
    steps = 0
    while walk.view != "combat_player" and steps < 10:
        walk.advance_view()
        steps += 1
    assert walk.view == "combat_player"
    assert steps == 3, "expected 3 advances by the long road, got %d" % steps

    fast = _at("aw_enc_checks")
    fast.skip_to("combat_empty")
    assert fast.view == "combat_player"


def test_no_window_survives_between_the_landing_and_the_target():
    """The actual invariant, generalised so a future skip cannot break it.

    A skip MAY pass action windows on its way -- that is the whole point, and
    the spec says so: "if we skip over action windows we at least should stop
    at the last action window before the destination". What it may never do is
    leave a window unvisited BETWEEN where it lands and where it was heading,
    because that would be an opportunity silently dropped with no later
    chance to take it.
    """
    from gamestate import SKIPS

    for s in SKIPS:
        for origin in s["from"]:
            g = _at(origin)
            landed = g.skip_to(s["id"])
            if landed is None:
                continue
            after = VIEW_ORDER[VIEW_ORDER.index(landed) + 1:
                               VIEW_ORDER.index(s["to"])]
            windows = [v for v in after if is_action_window(v)]
            assert not windows, (
                "%s landed on %s but left windows %r before %s"
                % (s["id"], landed, windows, s["to"]))


def test_phase_locked_abilities_exist_for_the_phase_being_skipped():
    """Why the landing rule is not over-engineering.

    Guards the assumption behind the whole design: Combat has phase-locked
    abilities, so its final window is worth preserving. If the turn sequence
    ever stops marking 6.P a window, this fails loudly.
    """
    assert phases.step("6.P")["action_window"] is True
    assert phases.step("6.E")["action_window"] is True
