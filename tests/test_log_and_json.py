import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gamestate import GameState


# -- log -------------------------------------------------------------------

def test_log_event_tags_round_and_step():
    g = GameState()
    g.step = "3.4"
    g.log_event("Placed 4 progress")
    entry = g.log[-1]
    assert entry["round"] == 1
    assert entry["step"] == "3.4"
    assert entry["text"] == "Placed 4 progress"


def test_log_entries_have_increasing_seq():
    g = GameState()
    g.log_event("a")
    g.log_event("b")
    assert g.log[0]["seq"] < g.log[1]["seq"]


def test_end_round_writes_round_and_phase_entries():
    g = GameState()
    before = len(g.log)
    g.end_round()
    assert len(g.log) > before
    texts = [e["text"] for e in g.log[before:]]
    assert any("New round" in t for t in texts)
    assert any(t.startswith("Phase:") for t in texts)


def test_resolve_quest_fail_logs_threat_increase():
    g = GameState()
    g.resolve_quest(willpower=2, staging=7)
    assert any("threat" in e["text"].lower() for e in g.log)


# -- json ------------------------------------------------------------------

def test_to_dict_from_dict_round_trip():
    g = GameState()
    g.adjust_threat(0, 14)
    g.players[1].threat_per_round = 2
    g.step = "6.P"
    g.quest = {"stage_n": 2, "side": "B", "points": 8, "progress": 5}
    g.active_location = {"points": 3, "progress": 1}
    g.side_quests = [{"points": 5, "progress": 2}]
    g.first_player = 2
    g.round = 4
    g.log_event("hello")

    restored = GameState.from_dict(g.to_dict())
    assert restored.to_dict() == g.to_dict()


def test_new_game_has_zero_questing_inputs():
    g = GameState()
    assert g.willpower == 0
    assert g.staging == 0


def test_questing_inputs_survive_round_trip():
    g = GameState()
    g.willpower = 11
    g.staging = 7
    restored = GameState.from_dict(g.to_dict())
    assert restored.willpower == 11
    assert restored.staging == 7


def test_from_dict_restores_player_and_progress_state():
    g = GameState()
    g.adjust_threat(3, 41)
    g.active_location = {"points": 4, "progress": 2}
    restored = GameState.from_dict(g.to_dict())
    assert restored.players[3].threat == 41
    assert restored.players[3].eliminated is False
    assert restored.active_location == {"points": 4, "progress": 2}
