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

# One page per card SIDE, flat across every stage and every alternative:
# STAGES is 1A,1B,2A,2B, then stage 3's two alternatives 3A,3B,3A,3B = 8.
PAGES = 8


def test_pages_are_one_per_card_side():
    g = _game()
    assert len(QuestCardModal(g)._pages()) == PAGES


def test_opens_on_the_live_card_side():
    """stage_idx=1 with the game on side B is page 3 (1A,1B,2A,2B)."""
    g = _game(stage_idx=1)
    g.quest["side"] = "B"
    assert QuestCardModal(g).page == 3
    g.quest["side"] = "A"
    assert QuestCardModal(g).page == 2


def test_paging_moves_and_hides_nav_at_each_end():
    g = _game(stage_idx=0)
    m = QuestCardModal(g)
    _draw(m, g)
    assert not any(b.id[0] == "prev" for b in m.buttons)   # no Prev at the start
    assert m.on_button(next(b for b in m.buttons if b.id[0] == "next")) == "redraw"
    assert m.page == 1
    m.page = PAGES - 1
    _draw(m, g)
    assert not any(b.id[0] == "next" for b in m.buttons)   # no Next at the end
    assert m.on_button(next(b for b in m.buttons if b.id[0] == "prev")) == "redraw"


def test_nav_buttons_name_the_page_they_lead_to():
    g = _game()
    m = QuestCardModal(g)
    _draw(m, g)
    m.on_button(next(b for b in m.buttons if b.id[0] == "next"))
    hw = _draw(m, g)
    drawn = " ".join(c[1] for c in hw.display.calls if c[0] == "text")
    assert "< Stage 1A" in drawn and "Stage 2A >" in drawn


def test_branch_alternatives_are_just_more_pages():
    """It is a reference, not a game view - both of stage 3's alternatives are
    reachable by paging, and there is no branch toggle to find."""
    g = _game()
    m = QuestCardModal(g)
    seen = []
    for p in range(PAGES):
        m.page = p
        hw = _draw(m, g)
        seen.append(" ".join(c[1] for c in hw.display.calls if c[0] == "text"))
        assert not any(b.id[0] == "alt" for b in m.buttons), "no branch toggle any more"
    joined = " ".join(seen)
    assert "Don't Leave the Path!" in joined and "Beorn's Path" in joined


def test_quest_points_sit_in_the_identity_row_not_their_own_block():
    g = _game()
    m = QuestCardModal(g)
    hw = _draw(m, g)
    texts = [c for c in hw.display.calls if c[0] == "text"]
    pts = [c for c in texts if c[1] == "8 pts"]
    assert pts, "quest points must show on the card side"
    stage_row = [c for c in texts if c[1] == "Stage 1A"][0]
    assert pts[0][3] == stage_row[3], "points belong on the stage row's baseline"


def test_no_tips_block_at_all_when_a_stage_has_none():
    g = _game()
    m = QuestCardModal(g)
    hw = _draw(m, g)
    assert not any(b.id[0] == "tips" for b in m.buttons)
    drawn = " ".join(c[1] for c in hw.display.calls if c[0] == "text")
    assert "TIPS" not in drawn


def test_long_text_is_marked_truncated_and_opens_a_detail_view():
    stages = [{"stage": 1, "cards": [{"questPoints": 1, "victory": None, "sailing": False,
        "faces": [{"side": "A", "name": "Wordy", "text": "lorem ipsum dolor " * 40}]}]}]
    g = gamestate.GameState(2, 25)
    m = QuestCardModal(g, stages=stages, scenario={"slug": "x"})
    hw = _draw(m, g)
    drawn = " ".join(c[1] for c in hw.display.calls if c[0] == "text")
    assert "more" in drawn, "a clipped card must say so"
    more = next(b for b in m.buttons if b.id[0] == "more_text")
    assert m.on_button(more) == "redraw" and m.detail == "text"
    hw2 = _draw(m, g)
    full = " ".join(c[1] for c in hw2.display.calls if c[0] == "text")
    assert full.count("lorem") > drawn.count("lorem"), "detail view shows more of it"
    assert m.on_button(next(b for b in m.buttons if b.id[0] == "back")) == "redraw"
    assert m.detail is None


# Strategy tips (M4-B tips, Task 2). Slug "p" matches _game()'s
# preload_scenario fixture above. Stage 3 (STAGES[2]) exercises the
# stage-specific-first merge; stage 1 (the _game() default) only has
# "general" tips, exercising the "general even without a stage entry" path.
TIPS = {"p": {"attribution": {"name": "Src", "url": "http://x"},
              "general": ["watch threat"], "stages": {"3": ["branch note"]}}}


def test_tips_show_inline_and_open_a_detail_view():
    g = _game()
    m = QuestCardModal(g, tips=TIPS)          # slug "p" per the fixture
    hw = _draw(m, g)
    drawn = " ".join(c[1] for c in hw.display.calls if c[0] == "text")
    assert "TIPS" in drawn and "watch threat" in drawn, "tips render inline, not behind a tap"
    tips = next(b for b in m.buttons if b.id[0] == "tips")
    assert m.on_button(tips) == "redraw" and m.detail == "tips"


def test_tips_view_shows_attribution_and_stage_specific_first():
    g = _game(stage_idx=2)
    m = QuestCardModal(g, tips=TIPS)
    _draw(m, g)
    m.on_button(next(b for b in m.buttons if b.id[0] == "tips"))
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


def test_no_tips_block_without_tips_data():
    g = _game()
    m = QuestCardModal(g, tips={})
    _draw(m, g)
    assert not any(b.id[0] == "tips" for b in m.buttons)


def test_tips_detail_back_returns_to_the_card():
    g = _game()
    m = QuestCardModal(g, tips=TIPS)
    _draw(m, g)
    assert m.on_button(next(b for b in m.buttons if b.id[0] == "tips")) == "redraw"
    hw = _draw(m, g)
    drawn = " ".join(c[1] for c in hw.display.calls if c[0] == "text")
    assert "watch threat" in drawn and "SETUP / STORY" not in drawn   # detail, not card

    assert m.on_button(next(b for b in m.buttons if b.id[0] == "back")) == "redraw"
    hw2 = _draw(m, g)
    drawn2 = " ".join(c[1] for c in hw2.display.calls if c[0] == "text")
    assert "SETUP / STORY" in drawn2


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
    seen = []
    for p in range(len(m._pages())):
        m.page = p
        hw = _draw(m, g)
        seen.append(" ".join(c[1] for c in hw.display.calls if c[0] == "text"))
    joined = " ".join(seen)
    assert "back E" in joined, "non-B back face must still get its own page"
    assert "Stage 2E" in joined, "the page is labelled with the face's real side"
