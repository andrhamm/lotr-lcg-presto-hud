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
    g.end_round()
    assert g.first_player == 1
    g.end_round()
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


def test_end_round_adds_threat_per_round_to_living_players():
    g = GameState()
    g.adjust_threat(0, 10)
    g.players[1].threat_per_round = 3
    g.adjust_threat(1, 10)
    g.end_round()
    assert g.players[0].threat == 11
    assert g.players[1].threat == 13


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
    assert g.step == "0.0"


def test_end_round_advances_first_player_token():
    g = GameState()
    assert g.first_player == 0
    g.end_round()
    assert g.first_player == 1
    g.first_player = 3
    g.end_round()
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
    g.step = "8.0"  # End of the round
    g.next_step()
    assert g.round == 2
    assert g.step == "0.0"


def test_current_step_action_window_flag():
    g = GameState()
    g.step = "3.4"  # Quest resolution — action window open
    assert g.action_window_open() is True
    g.step = "6.2"  # Deal shadow cards — no window
    assert g.action_window_open() is False


def test_commit_touched_lifecycle():
    from gamestate import GameState
    g = GameState()
    assert g.players[0].commit_touched is False
    g.set_commit(0, 5)
    assert g.players[0].commit_touched is True
    g.touch_commit(1)
    assert g.players[1].commit_touched is True
    g.end_round()
    assert all(p.commit_touched is False for p in g.players)


def test_commit_touched_round_trips():
    from gamestate import GameState
    g = GameState()
    g.set_commit(0, 3)
    g2 = GameState.from_dict(g.to_dict())
    assert g2.players[0].commit_touched is True


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


def test_quest_history_caps_at_20():
    from gamestate import GameState
    g = GameState()
    for _ in range(25):
        g.resolve_quest(5, 3)
    assert len(g.quest_history) == 20


def test_confirm_all_commits_touches_only_living_players():
    g = GameState()
    g.adjust_threat(1, 50)                     # P2 eliminated (default elimination 50)
    g.confirm_all_commits()
    assert g.players[0].commit_touched is True
    assert g.players[1].commit_touched is False
    assert g.players[2].commit_touched is True
    assert g.players[3].commit_touched is True


def test_confirm_all_commits_does_not_change_values():
    g = GameState()
    g.set_commit(0, 3)
    g.confirm_all_commits()
    assert g.players[0].commit == 3
    assert g.players[1].commit == 0
