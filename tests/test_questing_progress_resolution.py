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
