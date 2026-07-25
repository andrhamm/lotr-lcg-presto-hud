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

def test_advance_icon_shown_only_for_catalog_games():
    g = _catalog_game()
    m = QuestingProgressModal(g)
    hw = _draw(m, g)
    assert any(b.id == ("qAdv",) for b in m.buttons)
    g2 = gamestate.GameState(2, 25)          # custom game: no stages
    m2 = QuestingProgressModal(g2)
    _draw(m2, g2)
    assert not any(b.id == ("qAdv",) for b in m2.buttons)

def test_advance_icon_sets_forced_resolution():
    g = _catalog_game()
    m = QuestingProgressModal(g)
    _draw(m, g)
    adv = next(b for b in m.buttons if b.id == ("qAdv",))
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
    g.active_location = {"points": 3, "progress": 2}
    m = QuestingProgressModal(g)
    _draw(m, g)
    plus = next(b for b in m.buttons if b.id == ("lP+", None))
    assert m.on_button(plus) is None
    assert g.active_location is not None          # NOT auto-explored
    assert g.active_location["progress"] == 3
    assert g.needs_resolution() is True
    close = next(b for b in m.buttons if b.id[0] == "close")
    assert m.on_button(close) == "close"
    assert g.pending_resolution == "auto"
    assert g.active_location is not None           # still deferred to ResolutionModal

def test_location_manual_edit_over_target_still_auto_explores_for_custom_games():
    # Custom (uncatalogued) games are out of scope for the guided flow
    # (Global Constraint) and have no ResolutionModal to defer to, so they
    # keep the pre-existing immediate auto-explore behavior unchanged -
    # same case as tests/test_modals.py's
    # test_questing_progress_modal_location_current_bump_explores_when_done,
    # transcribed here for direct contrast with the catalog case above.
    g = gamestate.GameState(2, 25)
    g.active_location = {"points": 3, "progress": 2}
    m = QuestingProgressModal(g)
    _draw(m, g)
    plus = next(b for b in m.buttons if b.id == ("lP+", None))
    assert m.on_button(plus) is None
    assert g.active_location is None                # auto-explored immediately, as before

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

def test_custom_game_side_quest_only_overflow_close_does_not_set_pending_resolution():
    # The precise flip side of the regression above: StageCompleteModal has
    # no safe "cancel" (only "go", which commits a stage/side/points change,
    # or "win") - so the custom-game trigger must stay scoped to the QUEST
    # itself overflowing, not needs_resolution()'s broader location/
    # side-quest check (which is safe for catalog games only because
    # ResolutionModal's every step has a real close/dismiss escape hatch).
    # A side-quest-only overflow must NOT force a custom-game player into
    # StageCompleteModal's advance-or-victory dilemma.
    g = gamestate.GameState(2, 25)
    g.quest["points"] = 3
    g.quest["progress"] = 0                # quest itself is fine
    g.side_quests = [{"points": 2, "progress": 2, "name": "Gather Information"}]
    m = QuestingProgressModal(g)
    _draw(m, g)
    assert g.needs_resolution() is True    # side quest alone trips the broad check
    close = next(b for b in m.buttons if b.id[0] == "close")
    assert m.on_button(close) == "close"
    assert g.pending_resolution is False   # but custom games must not act on it
