import gamestate

STAGES = [
    {"stage": 1, "cards": [{"questPoints": 2, "victory": None, "sailing": False,
        "faces": [{"side": "A", "name": "Flies and Spiders", "text": "Setup text."},
                  {"side": "B", "name": "Flies and Spiders", "text": None}]}]},
    {"stage": 2, "branch": "random", "cards": [
        {"questPoints": 0, "victory": None, "sailing": False,
         "faces": [{"side": "A", "name": "A Chosen Path", "text": None},
                   {"side": "B", "name": "Don't Leave the Path!", "text": "Cannot advance until..."}]},
        {"questPoints": 4, "victory": None, "sailing": True,
         "faces": [{"side": "A", "name": "A Chosen Path", "text": None},
                   {"side": "B", "name": "Beorn's Path", "text": None}]}]},
    {"stage": 3, "cards": [{"questPoints": 3, "victory": None, "sailing": False,
        "faces": [{"side": "A", "name": "End", "text": None},
                  {"side": "B", "name": "End", "text": None}]}]},
]

def _catalog_game():
    g = gamestate.GameState(2, 25)
    g.preload_scenario({"slug": "p", "name": "P", "pack": "Core Set", "cycle": "Core Set",
                        "source": "official", "kind": "quest", "nightmare": False, "mode": "Standard"},
                       STAGES)
    g.flip_to_b()          # round 1 begins on 1B, 2 quest points
    return g

def test_needs_resolution_false_initially():
    g = _catalog_game()
    assert g.needs_resolution() is False

def test_needs_resolution_true_on_location_overflow():
    g = _catalog_game()
    g.active_location = {"points": 3, "progress": 3}
    assert g.needs_resolution() is True

def test_needs_resolution_true_on_quest_overflow():
    g = _catalog_game()
    g.quest["progress"] = 2
    assert g.needs_resolution() is True

def test_needs_resolution_true_on_side_quest_overflow():
    g = _catalog_game()
    g.side_quests.append({"points": 3, "progress": 3})
    assert g.needs_resolution() is True

def test_resolve_location_overflow_noop_when_under_target():
    g = _catalog_game()
    g.active_location = {"points": 3, "progress": 2}
    assert g.resolve_location_overflow() == 0
    assert g.active_location is not None

def test_resolve_location_overflow_explores_and_credits_excess():
    g = _catalog_game()
    g.active_location = {"points": 2, "progress": 3}
    excess = g.resolve_location_overflow()
    assert excess == 1
    assert g.active_location is None
    assert g.quest["progress"] == 1     # was 0, +1 excess

def test_resolve_location_overflow_exact_match_no_excess():
    g = _catalog_game()
    g.active_location = {"points": 2, "progress": 2}
    assert g.resolve_location_overflow() == 0
    assert g.active_location is None
    assert g.quest["progress"] == 0

def test_clear_and_advance_moves_to_next_stage_side_a_progress_discarded():
    g = _catalog_game()
    g.quest["progress"] = 5             # 3 over the 2 needed
    ok = g.clear_and_advance(card_idx=1)   # choose "Beorn's Path" branch
    assert ok is True
    assert g.stage_idx == 1 and g.card_idx == 1
    assert g.quest["side"] == "A" and g.quest["points"] == 0
    assert g.quest["progress"] == 0     # excess NOT carried (rulebook p.22)
    assert g.sailing is True            # picked card's sailing flag

def test_clear_and_advance_false_at_last_stage():
    g = _catalog_game()
    g.stage_idx = 2                      # already on the final stage (index 2)
    g.card_idx = 0
    before = g.to_dict()
    assert g.clear_and_advance() is False
    assert g.to_dict() == before         # no mutation

def test_place_progress_catalog_game_defers_to_resolution_flag():
    g = _catalog_game()
    completed = g.place_progress({"quest": 2, "location": 0, "side_quests": []})
    assert g.pending_resolution == "auto"
    assert g.quest["side"] == "B" and g.quest["stage_n"] == 1   # unchanged - deferred
    assert "Quest 1B cleared" in completed[0]

def test_place_progress_custom_game_unchanged_legacy_behavior():
    g = gamestate.GameState(2, 25)       # no scenario/stages: custom game
    g.quest["points"] = 4
    completed = g.place_progress({"quest": 4, "location": 0, "side_quests": []})
    assert g.pending_resolution is False
    assert g.pending_stage == {"cleared": "1A", "excess": 0}
    assert g.quest["side"] == "B" and g.quest["stage_n"] == 1    # legacy toggle already ran

def test_pending_resolution_round_trips():
    g = _catalog_game()
    g.pending_resolution = "forced"
    g2 = gamestate.GameState.from_dict(g.to_dict())
    assert g2.pending_resolution == "forced"

def test_pending_resolution_defaults_false_when_absent():
    g = gamestate.GameState.from_dict(gamestate.GameState(1, 25).to_dict())
    assert g.pending_resolution is False
