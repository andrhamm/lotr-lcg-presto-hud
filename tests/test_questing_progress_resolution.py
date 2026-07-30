import gamestate
from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.modals import QuestingProgressModal

STAGES = [{"stage": 1, "cards": [{"questPoints": 2, "victory": None, "sailing": False,
    "faces": [{"side": "A", "name": "S1", "text": None}, {"side": "B", "name": "S1", "text": None}]}]},
    {"stage": 2, "cards": [{"questPoints": 3, "victory": None, "sailing": False,
    "faces": [{"side": "A", "name": "S2", "text": None}, {"side": "B", "name": "S2", "text": None}]}]}]

def _catalog_game():
    g = gamestate.GameState(2, 25)
    g.preload_scenario({"slug": "p", "name": "P", "pack": "Core Set", "cycle": "Core Set",
                        "source": "official", "kind": "quest", "nightmare": False, "mode": "Standard"}, STAGES)
    g.flip_to_b()
    return g

def _draw(m, g):
    hw = FakeHardware()
    m.draw(hw, g, Palette(hw.display))
    return hw

def test_manual_edit_over_target_then_close_sets_pending_resolution():
    g = _catalog_game()
    m = QuestingProgressModal(g)
    _draw(m, g)
    plus = next(b for b in m.buttons if b.id == ("qP+", None))
    for _ in range(3):
        m.on_button(plus)     # 0 -> 3, target is 2
    close = next(b for b in m.buttons if b.id[0] == "close")
    assert m.on_button(close) == "close"
    assert g.pending_resolution == "auto"

def test_no_overflow_close_does_not_set_pending_resolution():
    g = _catalog_game()
    m = QuestingProgressModal(g)
    _draw(m, g)
    close = next(b for b in m.buttons if b.id[0] == "close")
    m.on_button(close)
    assert g.pending_resolution is False

def test_advance_anyway_is_labelled_on_the_quest_sheet():
    # Was a bare icon on the Progress row with no label. It lives on the quest
    # row's own sheet now, spelled out. It used to be gated on game.stages
    # because a custom quest had no ResolutionModal to open; there are no
    # custom quests any more, so every game gets it.
    from ui.modals import QuestConfigModal
    g = _catalog_game()
    m = QuestConfigModal(g)
    hw = _draw(m, g)
    assert any(b.id == ("force_adv",) for b in m.buttons)
    assert "Advance anyway" in " ".join(
        c[1] for c in hw.display.calls if c[0] == "text")
    assert not any(b.id == ("adv",) for b in m.buttons)   # manual edit is gone


def test_advance_anyway_sets_forced_resolution():
    # The only way into the guided flow for a stage with no quest points:
    # ~137 of ~400 stage cards advance on a condition, so nothing crosses a
    # target to trigger it.
    from ui.modals import QuestConfigModal
    g = _catalog_game()
    m = QuestConfigModal(g)
    _draw(m, g)
    adv = next(b for b in m.buttons if b.id == ("force_adv",))
    assert m.on_button(adv) == "close"
    assert g.pending_resolution == "forced"

def test_location_manual_edit_over_target_defers_to_resolution_flow_for_catalog_games():
    # Regression (found in the Task 4 browser walkthrough): the pre-existing
    # "lP+"/"lP-" handler calls explore_location_if_done() unconditionally,
    # which used to silently explore-and-discard the instant progress hit
    # points - racing ahead of needs_resolution() and defeating the guided
    # flow's location->quest credit (resolve_location_overflow(), Task 1)
    # before it ever got a chance to run. For catalog games the location
    # must stay put (still overflowing) until close, so the ResolutionModal
    # location step is the one that actually explores it.
    g = _catalog_game()
    g.active_locations = [{"points": 3, "progress": 2}]
    m = QuestingProgressModal(g)
    _draw(m, g)
    plus = next(b for b in m.buttons if b.id == ("lP+", 0))
    assert m.on_button(plus) is None
    assert g.active_locations          # NOT auto-explored
    assert g.active_locations[0]["progress"] == 3
    assert g.needs_resolution() is True
    close = next(b for b in m.buttons if b.id[0] == "close")
    assert m.on_button(close) == "close"
    assert g.pending_resolution == "auto"
    assert g.active_locations           # still deferred to ResolutionModal

def test_custom_game_quest_overflow_close_sets_pending_resolution():
    # Regression (found in the Task 4 browser walkthrough): the brief's
    # given "close" handler code gates the pending_resolution trigger on
    # `g.stages`, so custom games could never reach ANY resolution flow -
    # not even the legacy StageCompleteModal - contradicting both the
    # plan's own Global Constraint ("Quest overflow keeps routing to the
    # existing, unchanged StageCompleteModal - the only change is that the
    # manual-edit path can now reach it too") and this task's own walkthrough
    # (e), which explicitly expects StageCompleteModal to open for a custom
    # game's manually-edited quest overflow.
    g = gamestate.GameState(2, 25)         # custom game: no stages
    g.quest["points"] = 3
    g.quest["progress"] = 4                # over target
    m = QuestingProgressModal(g)
    _draw(m, g)
    close = next(b for b in m.buttons if b.id[0] == "close")
    assert m.on_button(close) == "close"
    assert g.pending_resolution == "auto"

