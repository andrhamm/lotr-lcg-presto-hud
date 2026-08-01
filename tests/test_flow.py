import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gamestate import GameState, VIEW_ORDER


# -- views ----------------------------------------------------------------

def test_view_order():
    assert VIEW_ORDER == ["resource", "aw_resource",
                          "planning",
                          "quest_commit", "aw_quest_commit",
                          "quest_staging", "aw_quest_staging",
                          "quest_resolution", "aw_quest_resolution",
                          "travel", "aw_travel",
                          "enc_optional", "aw_enc_optional",
                          "enc_checks", "aw_enc_checks",
                          "combat_shadow", "combat_enemy", "combat_player",
                          "refresh", "aw_refresh",
                          "round_end"]
    # Planning has no window view: upstream words 2.2-2.3 "player actions
    # THROUGHOUT", so its guidance lives in the phase view. Neither combat
    # half has one either - both are "after each combat SUBSTEP", many windows
    # inside the step rather than one following it.
    assert "aw_planning" not in VIEW_ORDER
    assert "aw_combat_enemy" not in VIEW_ORDER


def test_round_flow_first_view_is_resource_planning():
    assert VIEW_ORDER[0] == "resource"


def test_advance_view_walks_forward():
    g = GameState()
    g.advance_view()            # leaves setup
    g.advance_view()
    assert g.view == "aw_resource"  # every phase view hands off to its window
    g.advance_view()
    assert g.view == "planning"     # Resource -> Planning, now separate phases
    g.advance_view()
    assert g.view == "quest_commit"  # Planning has no window of its own


def test_advance_view_skips_resolution_without_success():
    # staging -> its window -> travel, skipping resolution when not pending.
    # The skip moved onto the window view: resolution is entered only by a
    # successful resolve, so it is the window that hands straight to travel.
    g = GameState()
    g.view = "quest_staging"
    g.advance_view()
    assert g.view == "aw_quest_staging"
    g.advance_view()
    assert g.view == "travel"


def test_end_round_resets_view():
    g = GameState()
    g.view = "refresh"
    g.end_round()
    assert g.view == "resource"


# -- per-player commits ---------------------------------------------------

def test_set_commit_updates_total_willpower():
    g = GameState()
    g.set_commit(0, 3)
    g.set_commit(1, 4)
    assert g.willpower == 7


def test_commits_persist_after_end_round_as_defaults():
    g = GameState()
    g.set_commit(0, 3)
    g.end_round()
    assert g.players[0].commit == 3
    assert g.willpower == 3


# -- per-player elimination -----------------------------------------------

def test_default_player_elimination_is_50():
    g = GameState()
    assert g.players[0].elimination == 50


def test_per_player_elimination_governs():
    g = GameState()
    g.players[1].elimination = 40
    g.adjust_threat(0, 45)
    g.adjust_threat(1, 45)
    assert g.players[0].eliminated is False
    assert g.players[1].eliminated is True


# -- travel actions --------------------------------------------------------

def test_travel_to_new_location_sets_and_logs_precisely():
    g = GameState()
    g.travel_to(points=3)
    assert g.active_locations[0] == {"points": 3, "progress": 0}
    assert "Traveled to new location (3 quest points)" in g.log[-1]["text"]


def test_change_location_replaces_and_logs_precisely():
    g = GameState()
    g.active_locations = [{"points": 3, "progress": 2}]
    g.change_location(points=4)
    assert g.active_locations[0] == {"points": 4, "progress": 0}
    assert "Changed active location" in g.log[-1]["text"]
    assert "discarded" in g.log[-1]["text"]


# -- round trip ------------------------------------------------------------

def test_view_for_step_exact_and_phase_fallback():
    from gamestate import view_for_step
    assert view_for_step("3.2") == "quest_commit"      # exact
    assert view_for_step("6.2") == "combat_shadow"     # exact
    assert view_for_step("1.1") == "resource" # phase fallback
    assert view_for_step("2.P") == "planning"          # its own view now
    assert view_for_step("5.4") == "enc_checks"        # encounter fallback
    assert view_for_step("0.0") == "resource"


def test_crossing_elimination_sets_pending_flag():
    g = GameState()
    g.adjust_threat(1, 50)
    assert g.players[1].eliminated is True
    assert g.pending_elim == 1


def test_no_pending_flag_when_already_eliminated():
    g = GameState()
    g.adjust_threat(1, 50)
    g.pending_elim = None
    g.adjust_threat(1, 1)  # still eliminated, no new crossing
    assert g.pending_elim is None


def test_refresh_threat_bump_can_set_pending():
    """The 7.3 raise can eliminate on ARRIVAL at the refresh view, before
    anyone can act. That is correct per RR (50 is immediate) and it is why
    the elimination warning has to be shown back in combat, the last window
    that can still prevent it."""
    g = GameState()
    g.adjust_threat(2, 49)
    g.pending_elim = None
    g.enter_view("refresh")        # apply_refresh runs on entry: +1 -> 50
    assert g.pending_elim == 2


def test_avert_elimination_sets_threat_below_level():
    # Favor of the Valar: threat becomes level - 5, not eliminated
    g = GameState()
    g.adjust_threat(0, 52)
    g.avert_elimination(0)
    assert g.players[0].threat == 45
    assert g.players[0].eliminated is False
    assert g.pending_elim is None


def test_resolve_quest_marks_round_resolved():
    g = GameState()
    assert g.quest_resolved is False
    g.resolve_quest(willpower=3, staging=3)
    assert g.quest_resolved is True
    g.end_round()
    assert g.quest_resolved is False


def test_flow_state_round_trip():
    g = GameState()
    g.set_commit(0, 5)
    g.view = "quest_staging"
    g.players[2].elimination = 99
    restored = GameState.from_dict(g.to_dict())
    assert restored.view == "quest_staging"
    assert restored.players[0].commit == 5
    assert restored.players[2].elimination == 99


def test_staging_reveal_estimate_is_three_per_living_player():
    g = GameState()
    assert g.staging_reveal_estimate() == 12  # 4 players x 3
    g.adjust_threat(1, 50)  # eliminated
    g.pending_elim = None
    assert g.staging_reveal_estimate() == 9


