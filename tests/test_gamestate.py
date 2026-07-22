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
