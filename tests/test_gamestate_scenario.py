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

def _flip(card):
    g = _g()
    g.preload_scenario({"slug": "p", "name": "P", "pack": "Core Set",
                        "cycle": "Core Set", "source": "official",
                        "kind": "quest", "nightmare": False,
                        "mode": "Standard"}, [{"stage": 1, "cards": [card]}])
    g.flip_to_b()
    return g.quest


def test_flip_marks_a_condition_stage_and_carries_its_sentence():
    # 177 stage cards print NO quest points: they advance on a condition, not
    # by filling a bar, so drawing 0/0 for them is a lie. `mode` is what lets
    # the Progress row drop the phantom Target stepper and the detail sheet
    # show the card's own sentence instead.
    q = _flip({"questPoints": 0, "questPointsKind": "na",
               "advance": "The players win when Bolg is destroyed.",
               "lose": "Otherwise the players lose the game."})
    assert q["mode"] == "condition"
    assert q["advance"] == "The players win when Bolg is destroyed."
    assert q["lose"] == "Otherwise the players lose the game."
    assert "x" not in q


def test_flip_marks_a_stage_whose_target_is_a_formula():
    q = _flip({"questPoints": 0, "questPointsKind": "x",
               "questPointsX": {"text": "+4 quest points per player",
                                "target": "players", "mul": 4}})
    assert q["mode"] == "formula"
    # The coded X, not a sentence to re-parse: `text` is only ever shown,
    # `target` names what to count. See xtargets.py.
    assert q["x"]["target"] == "players"
    assert q["x"]["mul"] == 4


def test_flip_leaves_a_genuine_zero_alone():
    # The regression this guards: a card that really prints 0 has no marker,
    # and must stay an ordinary points stage rather than being reclassified as
    # condition-advanced and losing its (editable) target.
    q = _flip({"questPoints": 0})
    assert q["mode"] == "points" and "advance" not in q


def test_flip_clears_stale_condition_state_on_the_next_stage():
    # quest is a long-lived dict, so advancing from a condition stage to a
    # pointed one must REMOVE the old sentence, not leave it on screen.
    g = _g()
    g.preload_scenario({"slug": "p", "name": "P", "pack": "Core Set",
                        "cycle": "Core Set", "source": "official",
                        "kind": "quest", "nightmare": False, "mode": "Standard"},
                       [{"stage": 1, "cards": [{"questPoints": 0,
                                                "questPointsKind": "na",
                                                "advance": "Old sentence."}]},
                        {"stage": 2, "cards": [{"questPoints": 8}]}])
    g.flip_to_b()
    assert g.quest["advance"] == "Old sentence."
    g.stage_idx = 1
    g.flip_to_b()
    assert g.quest["mode"] == "points"
    assert "advance" not in g.quest and "x" not in g.quest


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
