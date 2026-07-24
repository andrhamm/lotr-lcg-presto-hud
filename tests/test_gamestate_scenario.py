import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gamestate

STAGES = [
    {"stage": 1, "cards": [{"questPoints": 8, "victory": None, "sailing": False,
        "faces": [{"side":"A","name":"Flies and Spiders","text":"Setup: ..."},
                  {"side":"B","name":"Flies and Spiders","text": None}]}]},
    {"stage": 3, "branch": "random", "cards": [
        {"questPoints": 0, "victory": None, "sailing": False, "faces": [{"side":"A","name":"x","text":""},{"side":"B","name":"Don't","text":""}]},
        {"questPoints": 10, "victory": None, "sailing": False, "faces": [{"side":"A","name":"x","text":""},{"side":"B","name":"Beorn","text":""}]}]},
]

def _g():
    g = gamestate.GameState(2, 25); return g

def test_preload_sets_stage1_side_a_zero_points():
    g = _g(); g.preload_scenario({"slug":"passage","name":"Passage","pack":"Core Set",
        "cycle":"Core Set","source":"official","kind":"quest","nightmare":False,"mode":"Standard"}, STAGES)
    assert g.quest["side"] == "A" and g.quest["points"] == 0
    assert g.stage_idx == 0 and g.card_idx == 0 and g.scenario["slug"] == "passage"
    assert g.stages[0]["cards"][0]["questPoints"] == 8

def test_flip_loads_b_points():
    g = _g(); g.preload_scenario({"slug":"p","name":"P","pack":"Core Set","cycle":"Core Set",
        "source":"official","kind":"quest","nightmare":False,"mode":"Standard"}, STAGES)
    assert g.flip_to_b() == 8 and g.quest["side"] == "B" and g.quest["points"] == 8

def test_serialization_round_trips_scenario():
    g = _g(); g.preload_scenario({"slug":"p","name":"P","pack":"Core Set","cycle":"Core Set",
        "source":"official","kind":"quest","nightmare":False,"mode":"Standard"}, STAGES)
    g.card_idx = 0; g.stage_idx = 0
    d = g.to_dict(); g2 = gamestate.GameState.from_dict(d)
    assert g2.scenario["slug"] == "p" and g2.stages[0]["cards"][0]["questPoints"] == 8
    assert g2.stage_idx == 0 and g2.card_idx == 0

def test_from_dict_defaults_when_absent():
    g = gamestate.GameState.from_dict(gamestate.GameState(1, 25).to_dict())
    assert g.scenario is None and g.stages == []
