"""How a step's action window reaches the player.

"views": the aw_ screens are in the flow - the Presto, where a 480px screen has
no room for a band under the framework text. "bands": the window is drawn on
its step's own view and navigation steps over the aw_ entries - the tablet,
where it is the single biggest tap saving (eight views a round become bands).
Module state, set once by the client at boot; the model is otherwise the same.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gamestate
from gamestate import (GameState, VIEW_ORDER, WINDOW_POLICY_BANDS,
                       WINDOW_POLICY_VIEWS, flow_views, is_window_view,
                       phase_view_of, set_window_policy, skips_from,
                       window_policy)


def _round1():
    g = GameState(2, 25)
    g.advance_view()
    return g


def test_default_policy_is_views():
    assert window_policy() == WINDOW_POLICY_VIEWS
    assert flow_views() == VIEW_ORDER


def test_unknown_policy_is_refused():
    with pytest.raises(ValueError):
        set_window_policy("sometimes")


def test_bands_drop_every_window_view_from_the_flow():
    set_window_policy(WINDOW_POLICY_BANDS)
    assert not [v for v in flow_views() if is_window_view(v)]
    assert flow_views() == [v for v in VIEW_ORDER if not is_window_view(v)]


def test_bands_walk_the_round_without_landing_on_a_window():
    set_window_policy(WINDOW_POLICY_BANDS)
    g = _round1()
    seen = [g.view]
    for _ in range(20):
        if g.view == "round_end":
            break
        g.advance_view()
        seen.append(g.view)
    assert seen == ["resource", "planning", "quest_commit", "quest_staging",
                    "travel", "enc_optional", "enc_checks", "combat_shadow",
                    "combat_enemy", "combat_player", "refresh", "round_end"]


def test_bands_step_back_over_windows_too():
    set_window_policy(WINDOW_POLICY_BANDS)
    g = _round1()
    g.enter_view("travel")
    assert g.prev_view() == "quest_staging"   # not the resolution window
    g.enter_view("combat_shadow")
    assert g.prev_view() == "enc_checks"
    g.enter_view("resource")
    assert g.prev_view() is None              # a closed round is a floor


def test_bands_keep_the_resolution_view_reachable_after_a_resolve():
    set_window_policy(WINDOW_POLICY_BANDS)
    g = _round1()
    g.enter_view("quest_resolution")
    assert g.prev_view() == "quest_staging"
    assert g.next_view() == "travel"


def test_the_skip_moves_to_the_phase_view_under_bands():
    set_window_policy(WINDOW_POLICY_BANDS)
    offering = [v for v in flow_views() if skips_from(v)]
    assert offering == ["enc_checks"]
    # Under bands the origin's own window is the origin itself: enc_checks IS
    # aw_enc_checks's phase view, and aw_enc_checks itself has been dropped
    # from the flow - so the player stands on the window the skip would
    # otherwise have eaten, rather than merely on some action-window view
    # (almost every phase view is one, since a window view shares its phase
    # view's step id - is_action_window("enc_checks") alone would not prove
    # this).
    assert phase_view_of("aw_enc_checks") == "enc_checks"
    assert "aw_enc_checks" not in flow_views()


def test_the_skip_lands_and_logs_the_same_under_bands():
    set_window_policy(WINDOW_POLICY_BANDS)
    g = _round1()
    g.enter_view("enc_checks")
    assert g.skip_to("combat_empty") == "combat_player"
    assert g.view == "combat_player"
    entry = " ".join(str(e.get("text", "")) for e in g.log[-2:])
    assert "Skipped combat_shadow, combat_enemy" in entry
    assert "aw_" not in entry


def test_views_policy_is_untouched():
    g = _round1()
    assert g.next_view() == "aw_resource"
    assert skips_from("aw_enc_checks")
    assert not skips_from("enc_checks")


def test_bands_navigation_is_total_from_a_window_entered_directly():
    """The allocation path enters aw_quest_resolution by name (see
    screen_play's apply_alloc). Under bands that view is not in the flow, so
    navigation treats it as its phase view rather than raising or teleporting."""
    set_window_policy(WINDOW_POLICY_BANDS)
    g = _round1()
    g.enter_view("aw_quest_resolution")
    assert g.next_view() == "travel"
    assert g.prev_view() == "quest_staging"
    g.advance_view()
    assert g.view == "travel"


@pytest.mark.parametrize("policy", [WINDOW_POLICY_VIEWS, WINDOW_POLICY_BANDS])
def test_navigation_is_total_over_an_unknown_view(policy):
    """A save written by a future build (or one that has otherwise drifted)
    can carry a view id neither twin recognises - from_dict accepts
    d["view"] verbatim, and can_go_back() runs on the Presto's play-screen
    draw path every frame. Navigation must resolve to nothing there, never
    raise."""
    set_window_policy(policy)
    g = _round1()
    g.view = "some_legacy_view"
    assert g.next_view() is None
    assert g.prev_view() is None
    assert g.can_go_back() is False


def test_flow_views_is_a_copy_under_both_policies():
    fv = flow_views()
    fv.append("nope")
    assert "nope" not in flow_views()
    assert "nope" not in VIEW_ORDER
    set_window_policy(WINDOW_POLICY_BANDS)
    fv = flow_views()
    fv.append("nope")
    assert "nope" not in flow_views()


def test_no_offer_where_no_skip_is_declared():
    g = _round1()
    assert g.skip_offer() is None


def test_offer_is_promoted_when_the_tracker_agrees_with_the_claim():
    set_window_policy(WINDOW_POLICY_BANDS)
    g = _round1()
    g.enter_view("enc_checks")
    o = g.skip_offer()
    assert o["skip"]["id"] == "combat_empty"
    assert o["promoted"] is True
    assert (o["engaged"], o["staging_enemies"]) == (0, 0)


def test_offer_is_demoted_but_still_there_when_enemies_are_tracked():
    """A tracker, not a referee: the counts inform the button, they never
    remove it. The player may know something the tracker does not."""
    set_window_policy(WINDOW_POLICY_BANDS)
    g = _round1()
    g.enter_view("enc_checks")
    g.set_engaged(1, 2)
    g.set_staging_enemies(1)
    o = g.skip_offer()
    assert o["promoted"] is False
    assert (o["engaged"], o["staging_enemies"]) == (2, 1)
    assert g.skip_to("combat_empty") == "combat_player"


def test_offer_works_under_the_views_policy_too():
    g = _round1()
    g.enter_view("aw_enc_checks")
    assert g.skip_offer()["promoted"] is True
