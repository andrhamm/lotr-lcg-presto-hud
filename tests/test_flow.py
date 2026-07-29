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
    assert g.active_location == {"points": 3, "progress": 0}
    assert "Traveled to new location (3 quest points)" in g.log[-1]["text"]


def test_change_location_replaces_and_logs_precisely():
    g = GameState()
    g.active_location = {"points": 3, "progress": 2}
    g.change_location(points=4)
    assert g.active_location == {"points": 4, "progress": 0}
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


def test_due_notifications_archery_requires_staging_threat():
    g = GameState()
    g.reminders["archery"] = True
    g.view = "combat_shadow"
    g.staging = 0
    assert g.due_notifications() == []
    g.staging = 3
    due = g.due_notifications()
    assert any("Archery" in t for _ic, t in due)
    assert due[0][0] == "ARCHERY"          # bow icon attached


def test_due_notifications_only_for_matching_view():
    g = GameState()
    g.reminders["battle"] = True
    g.view = "quest_commit"
    assert any("battle" in t.lower() for _ic, t in g.due_notifications())
    g.view = "travel"
    assert g.due_notifications() == []


def test_travel_contribution_reduces_staging_and_logs():
    g = GameState()
    g.staging = 5
    g.travel_to(points=3, contribution=2)
    assert g.staging == 3
    assert any("Staging area threat 5 -> 3" in e["text"] for e in g.log)


def test_travel_contribution_clamps_at_zero():
    g = GameState()
    g.staging = 1
    g.travel_to(points=3, contribution=4)
    assert g.staging == 0


def test_new_game_starts_at_setup_phase():
    g = GameState()
    assert g.view == "setup_game"
    assert g.step == "0.0"


def test_setup_advances_to_resource_planning_and_never_returns():
    g = GameState()
    g.advance_view()
    assert g.view == "resource"
    g.view = "refresh"
    g.end_round()
    assert g.view == "resource"   # rounds skip setup forever





def _clocked(g, start=0):
    t = {"v": start}
    g.clock = lambda: t["v"]
    return t


def test_entering_views_logs_phase_starts_with_time():
    g = GameState()
    t = _clocked(g)
    t["v"] = 5000
    g.advance_view()   # setup -> resource
    e = g.log[-1]
    assert "Phase: Resource" in e["text"] or "round 1 begins" in e["text"].lower()
    starts = [e for e in g.log if e["text"].startswith("Phase:")]
    assert starts and starts[-1]["t"] == 5000
    t["v"] = 9000
    g.advance_view()   # -> the Resource action window
    # A window is not a new phase, so it does not claim to be one in the log.
    # That matters: the log's "Phase:" lines are how a reader reconstructs the
    # round, and eight extra false phase starts per round would drown it.
    assert g.log[-1]["text"] == "Action window: Resource"
    assert g.log[-1]["t"] == 9000
    g.advance_view()   # -> planning
    assert g.log[-1]["text"] == "Phase: Planning"
    g.advance_view()   # -> quest_commit
    assert g.log[-1]["text"] == "Phase: Questing: Commit"


def test_end_round_logs_duration_and_deltas():
    g = GameState()
    t = _clocked(g)
    g.advance_view()               # round 1 begins at t=0
    g.adjust_threat(0, 10)
    g.quest["points"] = 8
    g.quest["progress"] = 3
    t["v"] = 95000                 # 1m35s later
    # Walk the boundary rather than calling end_round directly: the +1 comes
    # from apply_refresh on entering the refresh view, and the round-stats
    # line diffs against the round snapshot, so the order matters.
    g.enter_view("refresh")
    g.end_round()
    stats = [e["text"] for e in g.log if "Round 1 ended" in e["text"]]
    assert stats, [e["text"] for e in g.log[-5:]]
    line = stats[0]
    assert "1m35s" in line
    assert "P1 +11" in line        # +10 manual +1 refresh
    assert "quest +3" in line


def test_setup_has_tip_and_no_checklist():
    from gamestate import SETUP_TIP
    import gamestate
    assert not hasattr(gamestate, "SETUP_STEPS")
    g = GameState()
    assert not hasattr(g, "setup_checks")
    assert any("mulligan" in s.lower() for s in SETUP_TIP)
    assert any("before" in s.lower() or "then" in s.lower() for s in SETUP_TIP)


# --- pending-modal handoffs must resolve before anything is drawn ----------
# A modal that hands off to another closes itself first and raises a flag
# (the router holds one modal at a time). If the flag were consumed AFTER the
# frame is drawn, the play screen would paint in the gap - the visible flash
# when tapping "+ Side quest" from the Progress modal. Both twins are checked
# by source order, since the loop itself needs hardware to run.

def _src(rel):
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, rel)) as f:
        return f.read()


def test_firmware_resolves_pending_modals_before_the_draw():
    s = _src("main.py")
    draw_at = s.index("        if dirty:\n            if modal is not None:")
    for flag in ("pending_elim", "pending_quest_card", "pending_side_quest_pick",
                 "pending_location_pick", "pending_progress_detail"):
        at = s.index("game.%s" % flag)
        assert at < draw_at, (
            "%s is consumed after the draw - the screen underneath will flash"
            % flag)


def test_web_twin_holds_the_frame_while_a_modal_handoff_is_in_flight():
    s = _src("docs/js/main.js")
    # The three async handoffs (quest card, side-quest picker, location
    # picker - each needs a catalog fetch) must bracket themselves with
    # modalPending, and the draw must honour it.
    assert s.count("modalPending += 1") == 3
    assert s.count("modalPending -= 1") == 3
    assert "if (dirty && !(modalPending && !modal))" in s
