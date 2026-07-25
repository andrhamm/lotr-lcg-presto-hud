import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gamestate
from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.modals import QuestCardModal

STAGES = [
    {"stage": 1, "cards": [{"questPoints": 8, "victory": None, "sailing": False,
        "faces": [{"side": "A", "name": "Flies and Spiders", "text": "Setup: Search the encounter deck..."},
                  {"side": "B", "name": "Flies and Spiders", "text": None}]}]},
    {"stage": 2, "cards": [{"questPoints": 2, "victory": None, "sailing": False,
        "faces": [{"side": "A", "name": "A Fork in the Road", "text": None},
                  {"side": "B", "name": "A Fork in the Road", "text": "Forced: ... at random."}]}]},
    {"stage": 3, "branch": "random", "cards": [
        {"questPoints": 0, "victory": None, "sailing": False,
         "faces": [{"side": "A", "name": "A Chosen Path", "text": None},
                   {"side": "B", "name": "Don't Leave the Path!", "text": "When Revealed: ..."}]},
        {"questPoints": 10, "victory": None, "sailing": False,
         "faces": [{"side": "A", "name": "A Chosen Path", "text": None},
                   {"side": "B", "name": "Beorn's Path", "text": "Players cannot defeat..."}]}]},
]

def _game(stage_idx=0):
    g = gamestate.GameState(2, 25)
    g.preload_scenario({"slug": "p", "name": "Passage", "pack": "Core Set", "cycle": "Core Set",
                        "source": "official", "kind": "quest", "nightmare": False, "mode": "Standard"}, STAGES)
    g.stage_idx = stage_idx
    return g

def _draw(m, g):
    hw = FakeHardware()
    m.draw(hw, g, Palette(hw.display))
    return hw

def test_opens_on_current_stage():
    g = _game(stage_idx=1)
    m = QuestCardModal(g)
    assert m.idx == 1

def test_paging_moves_and_clamps():
    g = _game(stage_idx=0)
    m = QuestCardModal(g)
    _draw(m, g)
    nxt = next(b for b in m.buttons if b.id[0] == "next")
    assert m.on_button(nxt) == "redraw" and m.idx == 1
    m.idx = len(STAGES) - 1
    _draw(m, g)
    assert not any(b.id[0] == "next" for b in m.buttons)   # no Next at the end

def test_branch_switch_changes_displayed_card():
    g = _game(stage_idx=2)
    m = QuestCardModal(g)
    _draw(m, g)
    assert m.card == 0
    alt = next(b for b in m.buttons if b.id[0] == "alt")
    m.on_button(alt)
    assert m.card == 1

def test_tips_button_disabled_and_inert():
    g = _game()
    m = QuestCardModal(g)
    _draw(m, g)
    tips = next(b for b in m.buttons if b.id[0] == "tips")
    assert m.on_button(tips) is None


# Strategy tips (M4-B tips, Task 2). Slug "p" matches _game()'s
# preload_scenario fixture above. Stage 3 (STAGES[2]) exercises the
# stage-specific-first merge; stage 1 (the _game() default) only has
# "general" tips, exercising the "general even without a stage entry" path.
TIPS = {"p": {"attribution": {"name": "Src", "url": "http://x"},
              "general": ["watch threat"], "stages": {"3": ["branch note"]}}}


def test_tips_button_enabled_when_tips_exist():
    g = _game()
    m = QuestCardModal(g, tips=TIPS)          # slug "p" per the fixture
    _draw(m, g)
    tips = next(b for b in m.buttons if b.id[0] == "tips")
    assert m.on_button(tips) == "redraw"      # opens the tips view, no longer inert


def test_tips_view_shows_attribution_and_stage_specific_first():
    g = _game(stage_idx=2)
    m = QuestCardModal(g, tips=TIPS)
    _draw(m, g)
    tips_btn = next(b for b in m.buttons if b.id[0] == "tips")
    m.on_button(tips_btn)
    hw = _draw(m, g)
    drawn = " ".join(c[1] for c in hw.display.calls if c[0] == "text")
    assert "branch note" in drawn and "watch threat" in drawn and "Src" in drawn


def test_tips_view_orders_stage_specific_before_general():
    g = _game(stage_idx=2)
    m = QuestCardModal(g, tips=TIPS)
    _draw(m, g)
    m.on_button(next(b for b in m.buttons if b.id[0] == "tips"))
    hw = _draw(m, g)
    drawn = " ".join(c[1] for c in hw.display.calls if c[0] == "text")
    assert drawn.index("branch note") < drawn.index("watch threat")


def test_tips_button_stays_disabled_without_tips():
    g = _game()
    m = QuestCardModal(g, tips={})
    _draw(m, g)
    assert m.on_button(next(b for b in m.buttons if b.id[0] == "tips")) is None


def test_tips_back_toggle_returns_to_card_view():
    g = _game()
    m = QuestCardModal(g, tips=TIPS)
    _draw(m, g)
    tips_btn = next(b for b in m.buttons if b.id[0] == "tips")
    assert m.on_button(tips_btn) == "redraw"
    hw = _draw(m, g)
    drawn = " ".join(c[1] for c in hw.display.calls if c[0] == "text")
    assert "watch threat" in drawn and "SIDE A" not in drawn   # tips view, not card view

    back_btn = next(b for b in m.buttons if b.id[0] == "tips")
    assert m.on_button(back_btn) == "redraw"
    hw2 = _draw(m, g)
    drawn2 = " ".join(c[1] for c in hw2.display.calls if c[0] == "text")
    assert "SIDE A" in drawn2 and "watch threat" not in drawn2  # back to the card view


def test_tips_default_kwarg_keeps_existing_call_sites_working():
    # QuestCardModal(g) with no tips kwarg at all must behave exactly like
    # tips={} (existing call sites in main.py/ui/screen_play.py predate the
    # tips arg and must keep compiling/working unmodified).
    g = _game()
    m = QuestCardModal(g)
    assert m.tips == {}

def test_modal_never_mutates_game():
    g = _game()
    before = g.to_dict()
    m = QuestCardModal(g)
    _draw(m, g)
    for b in list(m.buttons):
        if b.id[0] != "close":
            m.on_button(b)
    assert g.to_dict() == before

def test_empty_stages_renders_placeholder():
    g = gamestate.GameState(2, 25)      # custom game: no scenario, no stages
    m = QuestCardModal(g)
    _draw(m, g)                          # must not raise
    assert any(b.id[0] == "close" for b in m.buttons)


def test_epic_variant_backs_are_not_blank():
    """Epic multiplayer stages share one A front with backs C..H (e.g. Mount
    Gundabad stage 2 has 7 alternatives). Matching side "B" literally blanked
    every alternative but the first."""
    stages = [{"stage": 2, "branch": "choice", "cards": [
        {"questPoints": 3, "victory": None, "sailing": False,
         "faces": [{"side": "A", "name": "Exploring Gundabad", "text": "front"},
                   {"side": "B", "name": "Gundabad B", "text": "back B"}]},
        {"questPoints": 7, "victory": None, "sailing": False,
         "faces": [{"side": "A", "name": "Exploring Gundabad", "text": "front"},
                   {"side": "E", "name": "Gundabad E", "text": "back E"}]},
    ]}]
    g = gamestate.GameState(2, 25)
    g.preload_scenario({"slug": "mg", "name": "Mount Gundabad", "pack": "x", "cycle": "x",
                        "source": "official", "kind": "quest", "nightmare": False,
                        "mode": "Standard"}, stages)
    m = QuestCardModal(g)
    m.card = 1                       # the C..H-backed alternative
    hw = _draw(m, g)
    drawn = " ".join(c[1] for c in hw.display.calls if c[0] == "text")
    assert "back E" in drawn, "non-B back face must still render its text"
