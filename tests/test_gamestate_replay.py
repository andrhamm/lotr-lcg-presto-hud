"""Snapshot projection, the replay_step cursor, and replay persistence.

Parity with DragnCards (seastan/DragnCards @ a79716f9). Two of the four
documented divergences from that reference have tests here that name them:
D1 (the round walk actually halts) and D2 (a no-op action does not desync the
cursor).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gamestate import GameState, MAX_SAVED_DELTAS


def _round1(g):
    """Advance a fresh GameState past setup into round 1."""
    g.advance_view()
    return g


def _act(g, fn):
    """Do something, then record the delta - the record point, in miniature."""
    before = g.begin_action()
    fn()
    return g.add_delta(before)


# -- the projection ---------------------------------------------------------

def test_snapshot_keys_collections_as_maps_not_lists():
    g = _round1(GameState(2, 25))
    s = g.snapshot()
    assert isinstance(s["players"], dict)
    assert set(s["players"]) == {"0", "1"}
    assert isinstance(s["side_quests"], dict)
    assert isinstance(s["quest_history"], dict)


def test_snapshot_excludes_transient_and_setup_only_fields():
    g = _round1(GameState(2, 25))
    s = g.snapshot()
    for k in ("log", "messages", "clock", "_round_snap", "reminders",
              "scenario", "stages", "elimination_threat",
              "pending_quest_card", "pending_location_pick"):
        assert k not in s, k


def test_load_snapshot_round_trips():
    g = _round1(GameState(2, 25))
    g.players[0].threat = 31
    g.willpower = 7
    s = g.snapshot()
    g.players[0].threat = 99
    g.willpower = 0
    g.load_snapshot(s)
    assert g.players[0].threat == 31
    assert g.willpower == 7
    assert g.snapshot() == s


def test_load_snapshot_restores_a_cleared_active_location():
    g = _round1(GameState(2, 25))
    g.active_locations = [{"name": "Old Forest Road", "points": 3, "progress": 1}]
    s = g.snapshot()
    g.active_locations = []
    g.load_snapshot(s)
    assert g.active_locations[0] == {"name": "Old Forest Road", "points": 3, "progress": 1}


def test_load_snapshot_shrinks_and_grows_side_quests():
    g = _round1(GameState(2, 25))
    g.side_quests = [{"name": "A", "points": 4, "progress": 0}]
    s_one = g.snapshot()
    g.side_quests = []
    g.load_snapshot(s_one)
    assert len(g.side_quests) == 1
    g.side_quests = [{"name": "A", "points": 4, "progress": 0},
                     {"name": "B", "points": 8, "progress": 2}]
    g.load_snapshot(s_one)
    assert len(g.side_quests) == 1


# -- cursor mechanics -------------------------------------------------------

def test_fresh_state_cannot_undo_or_redo():
    g = _round1(GameState())
    assert g.replay_step == -1
    assert g.can_undo() is False
    assert g.can_redo() is False
    assert g.undo() is False
    assert g.redo() is False


def test_add_delta_appends_and_advances_the_cursor():
    g = _round1(GameState(2, 25))
    assert _act(g, lambda: g.set_commit(0, 3)) is True
    assert len(g.deltas) == 1
    assert g.replay_step == 0
    assert g.can_undo() is True
    assert g.can_redo() is False


def test_add_delta_is_a_noop_when_nothing_changed():
    """Divergence D2: the reference advances replayStep unconditionally, which
    desyncs the cursor on a no-op action. We leave it alone."""
    g = _round1(GameState(2, 25))
    assert _act(g, lambda: None) is False
    assert g.deltas == []
    assert g.replay_step == -1


def test_undo_restores_and_redo_reapplies():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    assert g.willpower == 3
    assert g.undo() is True
    assert g.willpower == 0
    assert g.replay_step == -1
    assert g.redo() is True
    assert g.willpower == 3
    assert g.replay_step == 0


def test_undo_walks_back_through_several_actions():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    _act(g, lambda: g.enter_view("quest_commit"))
    _act(g, lambda: g.enter_view("quest_staging"))
    assert g.view == "quest_staging"
    assert g.undo() and g.view == "quest_commit"
    assert g.undo() and g.view == "resource"
    assert g.undo() and g.willpower == 0
    assert g.can_undo() is False


def test_a_fresh_action_after_undo_truncates_the_redo_future():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    _act(g, lambda: g.set_commit(1, 4))
    assert len(g.deltas) == 2
    g.undo()
    assert g.can_redo() is True
    _act(g, lambda: g.set_commit(1, 9))
    assert len(g.deltas) == 2          # the undone delta was replaced
    assert g.can_redo() is False
    assert g.players[1].commit == 9


def test_deltas_carry_metadata_with_the_log_messages_of_their_action():
    g = _round1(GameState(2, 25))
    g.clock = lambda: 1234
    _act(g, lambda: g.enter_view("quest_commit"))
    md = g.deltas[-1]["_delta_metadata"]
    assert md["unix_ms"] == 1234
    assert any("Phase" in m for m in md["log_messages"])


def test_messages_drain_so_the_next_delta_does_not_repeat_them():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.enter_view("quest_commit"))
    first = g.deltas[-1]["_delta_metadata"]["log_messages"]
    _act(g, lambda: g.enter_view("quest_staging"))
    second = g.deltas[-1]["_delta_metadata"]["log_messages"]
    assert first and second and first != second


def test_log_entries_are_stamped_with_their_delta_index():
    """The Log screen needs a jump target per row without matching on text."""
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.enter_view("quest_commit"))
    _act(g, lambda: g.enter_view("quest_staging"))
    stamped = [e for e in g.log if "delta_i" in e]
    assert [e["delta_i"] for e in stamped] == [0, 1]


def test_undo_does_not_erase_the_log():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.enter_view("quest_commit"))
    n = len(g.log)
    g.undo()
    assert len(g.log) >= n


def test_deltas_are_trimmed_from_the_front_at_the_cap():
    g = _round1(GameState(2, 25))
    for i in range(MAX_SAVED_DELTAS + 10):
        _act(g, lambda i=i: g.adjust_threat(0, 1 if i % 2 == 0 else -1))
    assert len(g.deltas) == MAX_SAVED_DELTAS
    assert g.replay_step == MAX_SAVED_DELTAS - 1


def test_step_field_is_not_shadowed_by_the_replay_method():
    g = _round1(GameState(2, 25))
    assert isinstance(g.step, str)          # the phase step id, e.g. "1.R"
    _act(g, lambda: g.set_commit(0, 3))
    assert g.step_replay("undo") is True
    assert g.willpower == 0


# -- step_through dispatcher ------------------------------------------------

def test_step_through_single_matches_undo():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    assert g.step_through({"size": "single", "direction": "undo"}) is True
    assert g.willpower == 0


def test_step_through_index_jumps_backward_to_any_point():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 1))
    _act(g, lambda: g.set_commit(0, 2))
    _act(g, lambda: g.set_commit(0, 3))
    assert g.willpower == 3
    assert g.step_through({"size": "index", "index": 0}) is True
    assert g.replay_step == 0
    assert g.willpower == 1


def test_step_through_index_jumps_forward_again():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 1))
    _act(g, lambda: g.set_commit(0, 2))
    _act(g, lambda: g.set_commit(0, 3))
    g.step_through({"size": "index", "index": 0})
    assert g.step_through({"size": "index", "index": 2}) is True
    assert g.willpower == 3


def test_step_through_index_to_minus_one_rewinds_everything():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 1))
    _act(g, lambda: g.set_commit(0, 2))
    assert g.step_through({"size": "index", "index": -1}) is True
    assert g.replay_step == -1
    assert g.willpower == 0


def test_step_through_round_halts_on_a_round_change():
    """Divergence D1: the reference reads roundNumber off the wrong map, so
    its round walk never halts on a change. Ours reads the live round."""
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    g.view = "refresh"
    _act(g, lambda: g.end_round())
    assert g.round == 2
    _act(g, lambda: g.enter_view("quest_commit"))
    _act(g, lambda: g.enter_view("quest_staging"))
    assert g.step_through({"size": "round", "direction": "undo"}) is True
    assert g.round == 1                 # stopped at the boundary, not the start
    assert g.can_undo() is True         # round 1's own deltas are still there


def test_step_through_unknown_size_is_a_noop():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    assert g.step_through({"size": "sideways"}) is False
    assert g.willpower == 3


# -- replay persistence -----------------------------------------------------

def test_replay_to_dict_carries_deltas_and_the_cursor():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    _act(g, lambda: g.set_commit(1, 4))
    g.undo()
    d = g.replay_to_dict()
    assert d["replay_step"] == 0
    assert len(d["deltas"]) == 2


def test_replay_round_trips_through_json():
    import json
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    _act(g, lambda: g.enter_view("quest_commit"))
    blob = json.dumps(g.replay_to_dict())

    g2 = _round1(GameState(2, 25))
    g2.load_snapshot(g.snapshot())
    g2.replay_from_dict(json.loads(blob))
    assert g2.replay_step == g.replay_step
    assert g2.deltas == g.deltas
    assert g2.undo() is True
    assert g2.view == "resource"


def test_replay_from_dict_tolerates_a_missing_or_corrupt_file():
    """A bad replay file must cost you undo, never the game."""
    g = _round1(GameState(2, 25))
    g.replay_from_dict(None)
    assert g.deltas == [] and g.replay_step == -1
    g.replay_from_dict({})
    assert g.deltas == [] and g.replay_step == -1
    g.replay_from_dict({"deltas": "not a list", "replay_step": "x"})
    assert g.deltas == [] and g.replay_step == -1


def test_replay_from_dict_clamps_an_out_of_range_cursor():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    g.replay_from_dict({"deltas": g.deltas, "replay_step": 99})
    assert g.replay_step == len(g.deltas) - 1
    g.replay_from_dict({"deltas": g.deltas, "replay_step": -50})
    assert g.replay_step == -1


def test_to_dict_is_unchanged_by_the_replay_feature():
    """Divergence D4: state.json keeps its exact shape and write path."""
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    d = g.to_dict()
    assert "deltas" not in d
    assert "replay_step" not in d
    assert "messages" not in d


# -- the rebase guarantee, end to end --------------------------------------

def test_resolve_rebases_after_undo_and_edit():
    """The original TODO card: back up from a failed resolve, fix the
    committed willpower, resolve again - the new outcome must be computed
    from the corrected base, not stacked on the old one."""
    g = _round1(GameState(2, 25))
    g.view = "quest_staging"
    g.willpower, g.staging = 0, 5

    before = g.begin_action()
    res = g.resolve_quest(g.willpower, g.staging)
    g.enter_view("quest_resolution")
    g.add_delta(before)
    assert res["outcome"] == "fail"
    assert g.players[0].threat == 30          # 25 + 5 shortfall
    assert len(g.quest_history) == 1

    assert g.undo() is True
    assert g.view == "quest_staging"
    assert g.players[0].threat == 25           # the raise is gone
    assert len(g.quest_history) == 0           # the entry is gone

    g.willpower = 9
    before = g.begin_action()
    res2 = g.resolve_quest(g.willpower, g.staging)
    g.enter_view("quest_resolution")
    g.add_delta(before)
    assert res2["outcome"] == "success"
    assert g.players[0].threat == 25            # NOT 30 - no stacking
    assert len(g.quest_history) == 1            # replaced, not appended


def test_undo_is_not_itself_recorded_as_an_action():
    """Caught in the browser: the record point wraps every tap, including the
    Back button, so without a guard add_delta diffs the pre-undo snapshot
    against the post-undo state and appends the undo as a fresh delta -
    destroying the redo and making the history claim an action that never
    happened. The reference is immune by construction (step_through is a
    separate GenServer call from game_action); our single choke point is not."""
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    _act(g, lambda: g.set_commit(1, 4))
    assert len(g.deltas) == 2 and g.replay_step == 1

    # exactly what main.py does for a Back tap
    snap = g.begin_action()
    assert g.undo() is True
    assert g.add_delta(snap) is False           # not recorded

    assert len(g.deltas) == 2                   # nothing appended
    assert g.replay_step == 0                   # cursor moved back, and stayed
    assert g.can_redo() is True                 # the future survives


def test_a_real_action_after_an_undo_still_records():
    """The guard must not leak past its window."""
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    snap = g.begin_action()
    g.undo()
    g.add_delta(snap)
    assert _act(g, lambda: g.set_commit(0, 9)) is True
    assert g.players[0].commit == 9


def test_redo_is_not_recorded_either():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    snap = g.begin_action(); g.undo(); g.add_delta(snap)
    snap = g.begin_action()
    assert g.redo() is True
    assert g.add_delta(snap) is False
    assert len(g.deltas) == 1
    assert g.replay_step == 0


def test_back_across_the_refresh_boundary_reverts_threat_and_token():
    """The round boundary is now TWO actions, and each must undo cleanly.

    Entering refresh applies 7.3 and 7.4 (threat + token); the round_end CTA
    bumps the counter. Stepping back across the first must revert threat, the
    token AND refresh_applied together - the flag is in snapshot() precisely
    so that re-advancing applies exactly once instead of raising twice."""
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    g.view = "combat_player"
    before = (g.players[0].threat, g.players[1].threat, g.first_player, g.round)
    assert before == (25, 25, 0, 1)

    _act(g, lambda: g.enter_view("refresh"))
    assert (g.players[0].threat, g.players[1].threat) == (26, 26)  # +1 each
    assert g.first_player == 1
    assert g.refresh_applied is True
    assert g.round == 1                       # the round has NOT turned yet

    assert g.undo() is True
    assert (g.players[0].threat, g.players[1].threat, g.first_player, g.round) == before
    assert g.refresh_applied is False, "the flag must revert with the threat"
    assert g.view == "combat_player"

    assert g.redo() is True
    assert g.first_player == 1
    assert (g.players[0].threat, g.players[1].threat) == (26, 26)
    # and re-entering does not raise a second time
    g.enter_view("refresh")
    assert (g.players[0].threat, g.players[1].threat) == (26, 26)


def test_back_across_end_round_reverts_the_counter():
    g = _round1(GameState(2, 25))
    _act(g, lambda: g.set_commit(0, 3))
    _act(g, lambda: g.enter_view("refresh"))
    _act(g, lambda: g.end_round())
    assert g.round == 2
    assert g.view == "resource"
    assert g.refresh_applied is False         # next round's 7.3 re-armed

    assert g.undo() is True
    assert g.round == 1
    assert g.refresh_applied is True


# --------------------------------------------------------------------------
# Action-window views (2026-07-28)
#
# Window screens were made real views rather than screen-local ScreenPlay
# state precisely so that undo, save/resume and replay would work on them.
# These tests are the reason that choice was made, so they guard it.
# --------------------------------------------------------------------------

def _advance(g):
    """One tap's worth of work, bracketed the way main.py brackets a tap."""
    prev = g.begin_action()
    g.advance_view()
    g.add_delta(prev)


def test_back_steps_through_a_window_view_not_over_it():
    g = GameState(4, 25)
    g.enter_view("resource")
    _advance(g)                       # -> aw_resource
    _advance(g)                       # -> planning
    assert g.view == "planning"
    g.undo()
    assert g.view == "aw_resource", "back must land ON the window, not skip it"
    g.undo()
    assert g.view == "resource"
    g.redo()
    assert g.view == "aw_resource"
    g.redo()
    assert g.view == "planning"


def test_window_views_carry_their_step_through_replay():
    """A window shares the step it follows, so the header keeps reading 4.2
    across the boundary rather than jumping ahead."""
    g = GameState(4, 25)
    g.enter_view("travel")
    _advance(g)
    assert (g.view, g.step) == ("aw_travel", "4.2")
    g.undo()
    assert (g.view, g.step) == ("travel", "4.2")


def test_phases_screen_jump_still_lands_on_the_phase_view():
    """_STEP_VIEW is a last-wins inversion of VIEW_STEP. Window views share a
    step with the view they follow, so a blanket inversion would silently
    repoint every jump at the window."""
    from gamestate import view_for_step
    for step, expected in (("1.R", "resource"), ("3.3", "quest_staging"),
                           ("4.2", "travel"), ("5.3", "enc_checks"),
                           ("7.R", "refresh")):
        assert view_for_step(step) == expected, step


def test_window_views_are_not_logged_as_phase_starts():
    g = GameState(4, 25)
    g.enter_view("travel")
    _advance(g)
    starts = [e for e in g.log if e["text"].startswith("Phase:")]
    assert not any("aw_" in e["text"] for e in starts)
    assert g.log[-1]["text"] == "Action window: Travel"


# -- pre-list replay logs ---------------------------------------------------

def test_a_pre_list_delta_still_undoes_the_location_it_recorded():
    # A delta mirrors the shape of the state it describes, so renaming
    # active_location -> active_locations renamed every RECORDED delta out
    # from under undo. Applying one used to set a stray "active_location" key
    # and leave the real seat list untouched - a silent wrong-undo.
    g = GameState()
    g.replay_from_dict({"deltas": [
        {"active_location": [None, {"points": 2, "progress": 0,
                                    "name": "Enchanted Stream"}]}],
        "replay_step": 0})
    g.active_locations = [{"points": 2, "progress": 0,
                           "name": "Enchanted Stream"}]
    assert g.undo() is True
    assert g.active_locations == []
    assert not hasattr(g, "active_location")
    assert g.redo() is True
    assert g.active_locations == [{"points": 2, "progress": 0,
                                   "name": "Enchanted Stream"}]


def test_a_pre_list_delta_that_only_changed_progress_migrates_too():
    g = GameState()
    g.replay_from_dict({"deltas": [{"active_location": {"progress": [0, 1]}}],
                        "replay_step": 0})
    g.active_locations = [{"points": 3, "progress": 1}]
    assert g.undo() is True
    assert g.active_locations == [{"points": 3, "progress": 0}]


def test_a_delta_without_a_location_is_untouched():
    g = GameState()
    before = {"staging": [0, 3]}
    g.replay_from_dict({"deltas": [dict(before)], "replay_step": 0})
    assert g.deltas == [before]

