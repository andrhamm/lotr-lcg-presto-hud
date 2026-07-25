import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gamestate
from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.modals import ResolutionModal

STAGES = [
    {"stage": 1, "cards": [{"questPoints": 2, "victory": None, "sailing": False,
        "faces": [{"side": "A", "name": "S1", "text": None}, {"side": "B", "name": "S1", "text": None}]}]},
    {"stage": 2, "branch": "choice", "cards": [
        {"questPoints": 0, "victory": None, "sailing": False,
         "faces": [{"side": "A", "name": "S2", "text": None},
                   {"side": "B", "name": "Don't Leave the Path!", "text": "Cannot advance until X."}]},
        {"questPoints": 4, "victory": None, "sailing": False,
         "faces": [{"side": "A", "name": "S2", "text": None},
                   {"side": "B", "name": "Beorn's Path", "text": None}]}]},
    {"stage": 3, "cards": [{"questPoints": 3, "victory": None, "sailing": False,
        "faces": [{"side": "A", "name": "S3", "text": "Final setup."}, {"side": "B", "name": "S3", "text": None}]}]},
]

def _game(**over):
    g = gamestate.GameState(2, 25)
    g.preload_scenario({"slug": "p", "name": "P", "pack": "Core Set", "cycle": "Core Set",
                        "source": "official", "kind": "quest", "nightmare": False, "mode": "Standard"}, STAGES)
    g.flip_to_b()
    for k, v in over.items():
        setattr(g, k, v) if not isinstance(v, dict) else g.quest.update(v)
    return g

def _draw(m, g):
    hw = FakeHardware()
    m.draw(hw, g, Palette(hw.display))
    return hw

def test_no_overflow_step_is_none():
    g = _game()
    m = ResolutionModal(g)
    assert m.step is None

def test_location_overflow_step_first():
    g = _game()
    g.active_location = {"points": 2, "progress": 3}
    g.quest["progress"] = 2   # ALSO over - location must still come first
    m = ResolutionModal(g)
    assert m.step["kind"] == "location"

def test_resolving_location_feeds_quest_and_advances_to_branch_step():
    g = _game()
    g.active_location = {"points": 2, "progress": 3}   # 1 excess -> quest
    g.quest["progress"] = 1                             # +1 excess = 2 = clears stage 1
    m = ResolutionModal(g)
    _draw(m, g)
    loc_btn = next(b for b in m.buttons if b.id[0] == "resolve_location")
    assert m.on_button(loc_btn) == "redraw"
    assert g.active_location is None and g.quest["progress"] == 2
    assert m.step["kind"] == "branch"        # stage 2 has 2 cards

def test_branch_pick_then_advance_then_reveal_then_flip():
    g = _game()
    g.quest["progress"] = 2       # clears stage 1 outright
    m = ResolutionModal(g)
    _draw(m, g)
    assert m.step["kind"] == "branch"
    pick = next(b for b in m.buttons if b.id == ("pick_branch", 1))   # choose Beorn's Path
    assert m.on_button(pick) == "redraw"
    assert m.step["kind"] == "advance" and m.step["card_idx"] == 1
    _draw(m, g)
    adv = next(b for b in m.buttons if b.id[0] == "do_advance")
    assert m.on_button(adv) == "redraw"
    assert g.stage_idx == 1 and g.card_idx == 1 and g.quest["side"] == "A"
    assert m.step["kind"] == "reveal"
    _draw(m, g)
    flip = next(b for b in m.buttons if b.id[0] == "do_flip")
    assert m.on_button(flip) == "redraw"
    assert g.quest["side"] == "B" and g.quest["points"] == 4
    assert m.step is None        # 4qp target, 0 progress: nothing left to resolve

def test_conditional_stage_halts_without_looping():
    g = _game()
    g.quest["progress"] = 2
    m = ResolutionModal(g)
    pick0 = {"kind": "branch"}
    _draw(m, g)
    pick = next(b for b in m.buttons if b.id == ("pick_branch", 0))   # "Don't Leave the Path!", 0 qp
    m.on_button(pick)
    _draw(m, g)
    adv = next(b for b in m.buttons if b.id[0] == "do_advance")
    m.on_button(adv)
    _draw(m, g)
    flip = next(b for b in m.buttons if b.id[0] == "do_flip")
    m.on_button(flip)
    assert g.quest["points"] == 0 and g.quest["side"] == "B"
    assert m.step is None                 # halts - no auto-loop on a 0-point stage

def test_force_advance_shows_underfilled_caution():
    g = _game()
    g.quest["progress"] = 0        # nowhere near the 2 needed
    m = ResolutionModal(g, force_advance=True)
    assert m.step["kind"] in ("branch", "advance")
    if m.step["kind"] == "branch":
        _draw(m, g)
        m.on_button(next(b for b in m.buttons if b.id == ("pick_branch", 1)))
    assert m.step["kind"] == "advance" and m.step["underfilled"] is True

def test_victory_step_at_last_stage():
    g = _game(stage_idx=2, card_idx=0)
    g.quest.update({"points": 3, "progress": 3, "side": "B", "stage_n": 3})
    m = ResolutionModal(g)
    assert m.step["kind"] == "victory"
    _draw(m, g)
    b = next(x for x in m.buttons if x.id[0] == "declare_victory")
    assert m.on_button(b) == "close"
    assert g.game_over["result"] == "victory"

def test_side_quest_step_resolve_and_skip():
    g = _game()
    g.side_quests = [{"points": 2, "progress": 2, "name": "Gather Information"},
                      {"points": 3, "progress": 3, "name": "Scout Ahead"}]
    m = ResolutionModal(g)
    assert m.step["kind"] == "side_quest" and m.step["idx"] == 0
    _draw(m, g)
    skip = next(b for b in m.buttons if b.id[0] == "skip_side_quest")
    m.on_button(skip)
    assert m.step["kind"] == "side_quest" and m.step["idx"] == 1   # moved past the skipped one
    _draw(m, g)
    done = next(b for b in m.buttons if b.id[0] == "resolve_side_quest")
    m.on_button(done)
    assert len(g.side_quests) == 1                                 # only the resolved one popped
    assert m.step is None

def test_interrupted_reveal_resumes_first():
    g = _game()
    g.stage_idx = 1
    g.quest.update({"side": "A", "points": 0, "progress": 0, "stage_n": 2})
    g.active_location = {"points": 2, "progress": 2}   # a fresh overflow too
    m = ResolutionModal(g)
    assert m.step["kind"] == "reveal"     # finishes the interrupted flip before the location
