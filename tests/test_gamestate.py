import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gamestate import GameState


def test_new_game_has_four_players_named_p1_to_p4():
    g = GameState()
    assert [p.label for p in g.players] == ["P1", "P2", "P3", "P4"]


def test_new_game_defaults():
    g = GameState()
    assert g.round == 1
    assert g.first_player == 0
    assert g.step == "0.0"
    for p in g.players:
        assert p.threat == 0
        assert p.starting_threat == 0
        assert p.threat_per_round == 1
        assert p.eliminated is False


def test_adjust_threat_changes_value():
    g = GameState()
    g.adjust_threat(1, 28)
    assert g.players[1].threat == 28


def test_adjust_threat_clamps_at_zero():
    g = GameState()
    g.adjust_threat(0, 5)
    g.adjust_threat(0, -20)
    assert g.players[0].threat == 0


def test_threat_reaching_fifty_eliminates_player():
    # Rulebook: eliminated when threat level REACHES 50.
    g = GameState()
    g.adjust_threat(2, 50)
    assert g.players[2].eliminated is True


def test_threat_of_fortynine_is_not_eliminated():
    g = GameState()
    g.adjust_threat(2, 49)
    assert g.players[2].eliminated is False


def test_elimination_level_is_configurable():
    g = GameState(elimination_threat=99)  # e.g. Dire quests
    g.adjust_threat(0, 50)
    assert g.players[0].eliminated is False
    g.adjust_threat(0, 49)
    assert g.players[0].eliminated is True


def test_player_count_limits_players_and_rotation():
    g = GameState(player_count=2)
    assert [p.label for p in g.players] == ["P1", "P2"]
    # The token passes at 7.4, which is apply_refresh() now, not end_round().
    g.apply_refresh()
    assert g.first_player == 1
    g.end_round()          # arms the next round's 7.4
    g.apply_refresh()
    assert g.first_player == 0


def test_new_game_starting_threat_applies_to_all():
    g = GameState(player_count=3, starting_threat=28)
    assert [p.threat for p in g.players] == [28, 28, 28]
    assert all(p.starting_threat == 28 for p in g.players)


def test_settings_survive_round_trip():
    g = GameState(player_count=2, starting_threat=30, elimination_threat=99)
    restored = GameState.from_dict(g.to_dict())
    assert len(restored.players) == 2
    assert restored.elimination_threat == 99


def test_apply_refresh_adds_threat_per_round_to_living_players():
    """7.3 lives in apply_refresh(), not end_round().

    RR's chart runs 7.3, 7.4, ACTION WINDOW, 7.5 - the threat raise happens
    on ARRIVAL at the refresh view, before its window opens, so a player can
    see the result while the window is still theirs to act in."""
    g = GameState()
    g.adjust_threat(0, 10)
    g.players[1].threat_per_round = 3
    g.adjust_threat(1, 10)
    g.apply_refresh()
    assert g.players[0].threat == 11
    assert g.players[1].threat == 13


def test_apply_refresh_is_idempotent():
    """Guarded on state, not on "have I drawn": re-entering the view, a
    redraw, or back-and-forward must not raise threat twice."""
    g = GameState()
    assert g.apply_refresh() is True
    before = [p.threat for p in g.players]
    assert g.apply_refresh() is False
    assert [p.threat for p in g.players] == before


def test_end_round_skips_eliminated_players():
    g = GameState()
    g.adjust_threat(2, 51)  # eliminated
    g.end_round()
    assert g.players[2].threat == 51


def test_end_round_increments_round_and_resets_step():
    g = GameState()
    g.step = "3.4"
    g.end_round()
    assert g.round == 2
    assert g.step == "1.R"     # enter_view sets the step from the view now
    assert g.view == "resource"
    assert g.refresh_applied is False   # next round's 7.3 is armed again


def test_apply_refresh_advances_first_player_token():
    """7.4, and it happens BEFORE the refresh window opens - so that window
    is run by the NEW first player, who gets the first opportunity in it."""
    g = GameState()
    assert g.first_player == 0
    g.apply_refresh()
    assert g.first_player == 1
    g.first_player = 3
    g.refresh_applied = False
    g.apply_refresh()
    assert g.first_player == 0


def test_next_step_walks_the_step_order():
    g = GameState()
    assert g.step == "0.0"
    g.next_step()
    assert g.step == "1.1"
    g.prev_step()
    assert g.step == "0.0"


def test_prev_step_at_first_step_stays_put():
    g = GameState()
    g.prev_step()
    assert g.step == "0.0"


def test_next_step_past_last_step_ends_round():
    g = GameState()
    g.step = "0.1"  # End of the round
    g.next_step()
    assert g.round == 2
    assert g.step == "1.R"


def test_current_step_action_window_flag():
    g = GameState()
    g.step = "3.4"  # Quest resolution — action window open
    assert g.action_window_open() is True
    g.step = "6.2"  # Deal shadow cards — no window
    assert g.action_window_open() is False


def test_editing_the_total_detaches_the_player_breakdown():
    """Two ways into the questing total - the player widgets and the Questing
    For stepper - and they must never quietly disagree. Setting the total
    directly makes the per-player numbers no longer add up to it, which the
    pills show as "?" rather than asserting a breakdown that is not true."""
    from gamestate import GameState
    g = GameState(3, 25)
    g.set_commit(0, 4)
    g.set_commit(1, 3)
    assert g.willpower == 7 and g.willpower_detached is False

    g.set_willpower(11)
    assert g.willpower == 11
    assert g.willpower_detached is True
    # the stored per-player values are NOT lost - they are just no longer
    # what the total says
    assert [p.commit for p in g.players] == [4, 3, 0]


def test_typing_a_total_that_matches_the_players_is_not_detached():
    """Nothing is out of sync, so there is nothing to flag."""
    from gamestate import GameState
    g = GameState(3, 25)
    g.set_commit(0, 4)
    g.set_commit(1, 3)
    g.set_willpower(7)
    assert g.willpower_detached is False


def test_resync_refuses_to_overwrite_a_detached_total():
    """INVERTED 2026-07-30. This test used to assert the opposite - that
    resync adopted the sum and cleared the flag - and that assertion was the
    bug, written down.

    resync_willpower() overwrote a committed TOTAL with a stale per-player sum,
    and PlayersDetailModal called it from its constructor, so merely opening the
    players view during the quest phase destroyed the commitment. See
    test_opening_the_players_modal_does_not_destroy_a_committed_total.

    A detached total is the NEWER of the two facts. Reconciliation happens when
    a player edits a breakdown (set_commit), not when a view is opened.
    """
    from gamestate import GameState
    g = GameState(3, 25)
    g.set_commit(0, 4)
    g.set_commit(1, 3)
    g.set_willpower(11)
    assert g.resync_willpower() == 11
    assert g.willpower == 11 and g.willpower_detached is True
    # and the breakdown is still there, untouched, for whoever wants to edit it
    assert [p.commit for p in g.players] == [4, 3, 0]


def test_resync_still_adopts_the_breakdown_when_the_two_already_agree():
    """The guard is on `detached`, not on the method - when nothing is out of
    sync there is nothing to protect and resync stays a plain no-op."""
    from gamestate import GameState
    g = GameState(3, 25)
    g.set_commit(0, 4)
    g.set_commit(1, 3)
    assert g.resync_willpower() == 7
    assert g.willpower == 7 and g.willpower_detached is False


def test_solo_writes_the_total_through_to_the_one_players_commit():
    """With one player the total IS that player's commit, so there is no
    breakdown to lose and nothing to flag. This also makes willpower_detached
    unreachable in solo, which is what retires the meaningless "?" the pill
    used to show for a number the player had just typed."""
    from gamestate import GameState
    g = GameState(1, 29)
    g.set_willpower(11)
    assert g.players[0].commit == 11
    assert g.willpower == 11
    assert g.willpower_detached is False


def test_editing_a_player_reattaches_the_total():
    """The other direction: a per-player edit makes the sum authoritative
    again without needing the view to be reopened."""
    from gamestate import GameState
    g = GameState(3, 25)
    g.set_willpower(11)
    assert g.willpower_detached is True
    g.set_commit(0, 2)
    assert g.willpower == 2 and g.willpower_detached is False


def test_the_log_never_implies_a_breakdown_it_does_not_have():
    """When the total is set directly the per-player split is unknown, so the
    entry says what IS known - a total - and not who committed it."""
    from gamestate import GameState
    g = GameState(3, 25)
    g.set_commit(0, 4)
    g.set_willpower(11)
    assert "Players committed 11 willpower to the quest" == g.log[-1]["text"]


def test_detached_flag_round_trips():
    from gamestate import GameState
    g = GameState()
    g.set_commit(0, 3)
    g.set_willpower(9)
    g2 = GameState.from_dict(g.to_dict())
    assert g2.willpower == 9
    assert g2.willpower_detached is True
    assert g2.players[0].commit == 3


def test_end_round_reattaches_the_total_in_both_twins():
    """end_round re-derives the total from the commits, so the flag has to
    clear with it - otherwise the pills keep showing "?" for a number that is
    once again exactly the sum.

    The web twin did only half of this: it copied the willpower line out of
    gamestate.py and dropped the willpower_detached line under it, so a total
    typed in round 1 left "?" on screen for the whole of round 2. Firmware
    behaviour plus a source check on the twin - endRound is not reachable from
    a DOM-free node probe cheaply, and this is the drift that actually
    happened.
    """
    g = GameState(3, 25)
    g.set_commit(0, 4)
    g.set_willpower(11)
    assert g.willpower_detached is True
    g.end_round()
    assert g.willpower == 4 and g.willpower_detached is False

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(root, "docs", "js", "gamestate.js")).read()
    body = js[js.index("  endRound() {"):]
    body = body[:body.index("\n  }")]
    assert "willpower_detached = false" in body, (
        "docs/js/gamestate.js endRound() must clear willpower_detached, "
        "mirroring gamestate.py end_round")


def test_quest_history_records_each_resolution():
    from gamestate import GameState
    g = GameState()
    g.heading = 1
    g.resolve_quest(10, 4)          # success +6
    g.resolve_quest(3, 7)           # fail +4 threat
    g.resolve_quest(5, 5)           # tie 0
    h = g.quest_history
    assert [e["outcome"] for e in h] == ["success", "fail", "tie"]
    assert h[0]["willpower"] == 10 and h[0]["staging"] == 4 and h[0]["n"] == 6
    assert h[1]["n"] == 4 and h[2]["n"] == 0
    assert h[0]["heading"] == 1


def test_quest_history_records_the_stage_it_happened_on():
    # The History chart rules a gold vertical wherever the stage changes, so
    # the entry has to carry it. Without this the chart can show a sudden jump
    # in the staging line but not the advance that explains it.
    from gamestate import GameState
    g = GameState()
    g.resolve_quest(5, 3)
    g.quest["stage_n"] = 2
    g.resolve_quest(5, 3)
    assert [e["stage"] for e in g.quest_history] == [1, 2]


def test_quest_history_readers_tolerate_an_entry_without_a_stage():
    # Saves written before the key existed still load, so nothing may index it
    # directly.
    from gamestate import GameState
    g = GameState()
    g.resolve_quest(5, 3)
    del g.quest_history[0]["stage"]
    assert g.quest_history[0].get("stage") is None


def test_quest_history_caps_at_20():
    from gamestate import GameState
    g = GameState()
    for _ in range(25):
        g.resolve_quest(5, 3)
    assert len(g.quest_history) == 20


