import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.modal_counter import CounterModal
from ui import modals
from gamestate import GameState


def _find(m, id):
    return [b for b in m.buttons if b.id == id][0]


def _btn(id):
    """A bare button stand-in for handler tests that don't need a draw()."""
    return type("B", (), {"id": id})()


def test_all_modals_draw_without_error():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_locations = [{"points": 3, "progress": 1}]
    game.side_quests = [{"points": 5, "progress": 2}]
    for modal in (
        modals.PlayerSettingsModal(game, 0),
        modals.QuestConfigModal(game),
        modals.LocationConfigModal(game),
        modals.SideQuestsModal(game),
        modals.LocationPickModal(game, mode="change"),
        modals.QuestingProgressModal(game),
        CounterModal("t", 3, icon="willpower"),
    ):
        modal.draw(hw, game, pal)
        assert len(modal.buttons) > 0


def test_player_settings_saves_elimination():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    m = modals.PlayerSettingsModal(game, 1)
    m.draw(hw, game, pal)
    for _ in range(3):
        m.on_button(_find(m, ("el", 1)))
    m.on_button(_find(m, ("save",)))
    assert game.players[1].elimination == 53


def test_elimination_modal_confirm_keeps_eliminated_and_logs():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.adjust_threat(2, 51)
    m = modals.EliminationModal(game, 2)
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("elim",))) == "close"
    assert game.players[2].eliminated is True
    assert game.pending_elim is None
    assert any("eliminated" in e["text"] for e in game.log)


def test_elimination_modal_avert_restores_player():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.adjust_threat(2, 51)
    m = modals.EliminationModal(game, 2)
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("avert",)))
    assert game.players[2].eliminated is False
    assert game.players[2].threat == 45
    assert game.pending_elim is None


def test_elimination_modal_raised_level_uneliminates():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.adjust_threat(2, 51)  # crossed 50
    m = modals.EliminationModal(game, 2)
    m.draw(hw, game, pal)
    for _ in range(10):  # 50 -> 60
        m.on_button(_find(m, ("lvl", 1)))
    assert m.on_button(_find(m, ("setlvl",))) == "close"
    assert game.players[2].elimination == 60
    assert game.players[2].eliminated is False
    assert game.pending_elim is None


def test_led_modal_edits_prefs_and_previews():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    prefs = {"brightness": 100, "scene": "phase"}
    m = modals.LedModal(prefs, game)
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("bri", 50)))
    m.on_button(_find(m, ("scene", "torch")))
    assert prefs == {"brightness": 50, "scene": "torch"}
    m.draw(hw, game, pal)                       # live preview at 50%
    assert all(max(c) <= 130 for c in hw.leds)  # scaled down
    assert m.on_button(_find(m, ("save",))) == "close"


def test_settings_led_tile_opens_modal():
    from ui.screen_settings import ScreenSettings
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    s = ScreenSettings({"brightness": 100, "scene": "phase"})
    s.draw(hw, game, pal)
    led = [b for b in s.buttons if b.id == ("led",)][0]
    result = s.on_button(led, game)
    assert result[0] == "modal"
    assert isinstance(result[1], modals.LedModal)


def test_quest_config_save_persists_points():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    m = modals.QuestConfigModal(game)
    m.draw(hw, game, pal)
    for _ in range(8):
        m.on_button(_find(m, ("pts", 1)))
        m.draw(hw, game, pal)
    m.on_button(_find(m, ("save",)))
    assert game.quest["points"] == 8


def test_reminders_modal_toggles_and_persists():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    m = modals.RemindersModal(game)
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("tog", "archery")))
    assert game.reminders["archery"] is True
    restored = GameState.from_dict(game.to_dict())
    assert restored.reminders["archery"] is True
    assert m.on_button(_find(m, ("close",))) == "close"


def test_reminders_modal_done_header_button_geometry():
    # modal_header's DONE button: round id upper-left, DONE upper-right,
    # no leftover "X" — shared by every full-screen modal via modal_header.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    m = modals.RemindersModal(game)
    m.draw(hw, game, pal)
    close = _find(m, ("close",))
    assert (close.x, close.y, close.w, close.h) == (408, 4, 64, 32)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "DONE" in texts and "X" not in texts
    assert "R%d %s" % (game.round, game.step) in texts


def test_sailing_modal_done_header_dismisses_without_applying():
    # The header DONE button (id ("close",), from modal_header) must dismiss
    # like Cancel, not commit — only the footer Apply button shifts heading.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.sailing = True
    game.heading = 2
    m = modals.SailingModal(game)
    m.draw(hw, game, pal)
    close = _find(m, ("close",))
    assert (close.x, close.y, close.w, close.h) == (408, 4, 64, 32)
    m.on_button(_find(m, ("d", 1)))         # dial in a pending wheel (+1)
    assert m.on_button(close) == "cancel"
    assert game.heading == 2                # unchanged — DONE discards the pending delta


def test_sailing_modal_apply_still_commits_heading_shift():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.sailing = True
    game.heading = 2
    m = modals.SailingModal(game)
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("d", 1)))
    assert m.on_button(_find(m, ("apply",))) == "close"
    assert game.heading == 1                 # shifted on-course by the found wheel


def test_players_detail_modal_grid_has_editor_buttons_for_each_player():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    m = modals.PlayersDetailModal(game)
    m.draw(hw, game, pal)
    assert len(m.buttons) > 0
    for i in range(len(game.players)):
        for key in ("t", "w"):
            for action in (-1, 1, "edit"):
                assert any(b.id == (key, i, action) for b in m.buttons), (key, i, action)
    close = _find(m, ("close",))
    assert (close.x, close.y, close.w, close.h) == (408, 4, 64, 32)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "Players" in texts
    # The column headers are now the threat helm and willpower star ICONS,
    # matching the play screen, rather than ALL-CAPS LABEL text.
    assert "THREAT" not in texts and "WILLPOWER" not in texts
    from ui.modals import PlayersDetailModal as _M
    for b in m.buttons:
        if b.id[0] in ("t", "w"):
            assert b.w >= _M.HIT and b.h >= _M.HIT, (b.id, b.w, b.h)


def test_players_detail_modal_threat_step_adjusts_and_logs():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    m = modals.PlayersDetailModal(game)
    m.draw(hw, game, pal)
    before = game.players[0].threat
    assert m.on_button(_find(m, ("t", 0, 1))) is None
    assert game.players[0].threat == before + 1
    assert any("P1 threat %d -> %d" % (before, before + 1) in e["text"] for e in game.log)


def test_players_detail_modal_willpower_step_sets_the_commit_and_logs():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    m = modals.PlayersDetailModal(game)
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("w", 1, 1))) is None
    assert game.players[1].commit == 1
    # a per-player edit makes the sum authoritative again
    assert game.willpower_detached is False
    assert any("P2 committed 1 willpower" in e["text"] for e in game.log)


def test_opening_the_players_modal_resyncs_a_detached_total():
    """The two sources must never quietly disagree. While the total was set
    directly the per-player values were still stored - just no longer what the
    total said - so opening the view that shows them adopts them again."""
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.set_commit(0, 4)
    game.set_willpower(11)
    assert game.willpower_detached is True

    modals.PlayersDetailModal(game)          # opening it is the resync
    assert game.willpower == 4
    assert game.willpower_detached is False
    assert game.players[0].commit == 4       # the stored value was never lost


def test_players_detail_modal_inline_edit_pad_commits_on_ok_and_returns_to_grid():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.set_commit(2, 3)
    m = modals.PlayersDetailModal(game)
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("w", 2, "edit"))) is None
    assert m.edit is not None
    m.draw(hw, game, pal)                       # edit-mode redraw (grid replaced)
    m.on_button(_find(m, ("step", 5)))
    assert m.on_button(_find(m, ("ok",))) is None      # never closes the outer modal
    assert m.edit is None                              # back to the grid
    assert game.players[2].commit == 8
    assert any("P3 committed 8 willpower" in e["text"] for e in game.log)


def test_players_detail_modal_inline_edit_pad_preserves_value_above_99():
    # CounterState's default max=99 is a cosmetic pad ceiling, not a game
    # rule (adjust_threat has no upper bound - a spammed-past-99 threat is
    # reachable, e.g. on an eliminated player). Opening the pad must not
    # silently clamp an already-high value down to 99 on an untouched OK tap.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.adjust_threat(0, 150)
    m = modals.PlayersDetailModal(game)
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("t", 0, "edit")))
    assert m.edit[2].preview == 150
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("ok",))) is None
    assert game.players[0].threat == 150           # untouched - no silent clamp to 99


def test_players_detail_modal_inline_edit_pad_back_discards():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.adjust_threat(0, 20)
    m = modals.PlayersDetailModal(game)
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("t", 0, "edit")))
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("step", -5)))
    assert m.on_button(_find(m, ("back",))) is None
    assert m.edit is None
    assert game.players[0].threat == 20            # unchanged - back discards


def test_questing_progress_modal_header_geometry_and_title():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    close = _find(m, ("close",))
    assert (close.x, close.y, close.w, close.h) == (408, 4, 64, 32)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "Progress" in texts and "DONE" in texts


def test_questing_progress_modal_main_quest_row_has_no_complete_or_remove():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    assert not any(b.id == ("qdone", None) for b in m.buttons)
    assert not any(b.id[0] == "qX" for b in m.buttons)


def test_questing_progress_modal_quest_editors_adjust_and_log_on_close():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.quest = {"stage_n": 1, "side": "A", "points": 10, "progress": 3}
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("qP+", None))) is None
    assert game.quest["progress"] == 4
    assert m.on_button(_find(m, ("qT-", None))) is None
    assert game.quest["points"] == 9
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("close",))) == "close"
    assert any("Quest 1A set 4/9 (progress view)" in e["text"] for e in game.log)


_QPM_STAGES = [{"stage": 1, "cards": [{"questPoints": 8, "victory": None, "sailing": False,
    "faces": [{"side": "A", "name": "x", "text": None}, {"side": "B", "name": "x", "text": None}]}]}]


def test_questing_progress_modal_quest_row_always_has_a_detail_chevron():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()   # no preload_scenario: game.stages == [] (custom game)
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    assert not any(b.id == ("detail", "q", None) for b in m.buttons)

    game.preload_scenario({"slug": "p", "name": "P", "pack": "Core Set", "cycle": "Core Set",
                           "source": "official", "kind": "quest", "nightmare": False,
                           "mode": "Standard"}, _QPM_STAGES)
    m2 = modals.QuestingProgressModal(game)
    m2.draw(hw, game, pal)
    assert any(b.id == ("detail", "q", None) for b in m2.buttons)


def test_questing_progress_modal_quest_row_opens_the_editor():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.preload_scenario({"slug": "p", "name": "P", "pack": "Core Set", "cycle": "Core Set",
                           "source": "official", "kind": "quest", "nightmare": False,
                           "mode": "Standard"}, _QPM_STAGES)
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    assert game.pending_quest_card is False
    assert m.on_button(_find(m, ("detail", "q", None))) == "close"
    assert game.pending_quest_config is True


def test_questing_progress_modal_quest_card_button_does_not_overlap_current_editor():
    # Hit-test order: buttons are matched in array order, so the Current/
    # Target editors (pushed first) must win on any overlap. The quest_card
    # button is sized to sit left of the Current editor's leftmost hit-box
    # by construction - assert that geometrically, not just by push order.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.preload_scenario({"slug": "p", "name": "P", "pack": "Core Set", "cycle": "Core Set",
                           "source": "official", "kind": "quest", "nightmare": False,
                           "mode": "Standard"}, _QPM_STAGES)
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    qc = _find(m, ("detail", "q", None))
    cur_minus = _find(m, ("qP-", None))
    assert qc.x + qc.w <= cur_minus.x
    # and editors were pushed first, so they'd win on overlap regardless
    ids = [b.id for b in m.buttons]
    assert ids.index(("qP-", None)) < ids.index(("detail", "q", None))
    assert ids.index(("qP+", None)) < ids.index(("detail", "q", None))
    assert ids.index(("qT-", None)) < ids.index(("detail", "q", None))
    assert ids.index(("qT+", None)) < ids.index(("detail", "q", None))


def test_questing_progress_modal_location_current_bump_explores_when_done():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_locations = [{"points": 3, "progress": 2}]
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("lP+", 0))) is None
    assert not game.active_locations
    assert any("Explored" in e["text"] for e in game.log)


def test_questing_progress_modal_complete_location_logs_and_clears():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_locations = [{"points": 5, "progress": 1}]
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("ldone", None))) is None
    assert not game.active_locations
    assert game.log[-1]["text"] == "Active location Explored"


def test_questing_progress_modal_complete_side_quest_logs_and_pops():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.side_quests = [{"points": 5, "progress": 5}]
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("sdone", 0))) is None
    assert game.side_quests == []
    assert game.log[-1]["text"] == "Side quest 1 completed"


def test_questing_progress_modal_remove_side_quest_logs_and_pops():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.side_quests = [{"points": 5, "progress": 1}]
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("sX", 0))) is None
    assert game.side_quests == []
    assert game.log[-1]["text"] == "Side quest 1 removed"


def test_questing_progress_modal_remove_location_opens_prompt_without_clearing():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_locations = [{"points": 4, "progress": 2}]
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("lX", None))) is None
    assert m.loc_prompt == {"stage": "choose"}
    assert game.active_locations[0] == {"points": 4, "progress": 2}   # untouched
    m.draw(hw, game, pal)                                         # re-render the prompt
    assert not any(b.id == ("close",) for b in m.buttons)         # header suppressed


def test_questing_progress_modal_loc_prompt_cancel_leaves_location_untouched():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_locations = [{"points": 4, "progress": 2}]
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("lX", None)))
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("lp_cancel",))) is None
    assert m.loc_prompt is None
    assert game.active_locations[0] == {"points": 4, "progress": 2}


def test_questing_progress_modal_loc_prompt_discard_clears_and_logs():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_locations = [{"points": 4, "progress": 2}]
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("lX", None)))
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("lp_discard",))) is None
    assert not game.active_locations
    assert m.loc_prompt is None
    assert game.log[-1]["text"] == "Active location removed"


def test_questing_progress_modal_loc_prompt_replaced_sets_new_location():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_locations = [{"points": 4, "progress": 2}]
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("lX", None)))
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("lp_replaced",)))
    assert m.loc_prompt["stage"] == "pts"
    m.draw(hw, game, pal)
    for _ in range(3):
        m.on_button(_find(m, ("lp_pts", 1)))
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("save",))) is None
    assert game.active_locations[0] == {"points": 6, "progress": 0}
    assert m.loc_prompt is None
    assert any("Changed active location" in e["text"] for e in game.log)


def test_questing_progress_modal_loc_prompt_pts_cancel_returns_to_choose():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_locations = [{"points": 4, "progress": 1}]
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("lX", None)))
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("lp_replaced",)))
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("cancel",))) is None
    assert m.loc_prompt == {"stage": "choose"}
    assert game.active_locations[0] == {"points": 4, "progress": 1}   # untouched


def test_questing_progress_modal_loc_prompt_to_staging_adds_threat_and_clears():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_locations = [{"points": 4, "progress": 2}]
    game.staging = 5
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("lX", None)))
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("lp_staging",)))
    assert m.loc_prompt["stage"] == "contrib"
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("lp_ctr", 1)))
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("save",))) is None
    assert game.staging == 8      # 5 + (default 2 + 1 tap)
    assert not game.active_locations
    assert m.loc_prompt is None
    assert any("Active location to staging (+3 threat)" in e["text"] for e in game.log)


def test_questing_progress_modal_add_location_opens_the_picker():
    # Was a blind append of a guessed 3 quest points. Now it closes and flags
    # the picker (the router holds one modal at a time), with back="progress"
    # so the picker's exit reopens this modal.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_locations = []
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    # "+ Add" asks which first - it used to silently mean "side quest".
    assert m.on_button(_find(m, ("add",))) == "redraw"
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("add_loc",))) == "close"
    assert game.pending_location_pick == {"mode": "new", "back": "progress"}
    assert not game.active_locations      # nothing seated until you pick
    assert not [e for e in game.log if "location" in e["text"]]


def test_questing_progress_history_heading_radio_sets_heading_and_logs():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.sailing = True
    game.heading = 0
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("hd_set", 2))) is None
    assert game.heading == 2
    assert any("Sailing: heading" in e["text"] for e in game.log)
    n_before = len(game.log)
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("hd_set", 2))) is None   # already active - no-op
    assert len(game.log) == n_before


def test_questing_progress_modal_chart_shows_heading_row_when_sailing():
    # Spec: the by-round chart's WHEEL/heading row only appears when sailing.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.sailing = True
    game.resolve_quest(14, 10)
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "WILLPOWER / STAGING / RESULT / HEADING" in texts


def test_questing_progress_modal_chart_hides_heading_row_when_not_sailing():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.sailing = False
    game.resolve_quest(14, 10)
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "WILLPOWER / STAGING / RESULT" in texts
    assert "WILLPOWER / STAGING / RESULT / HEADING" not in texts
    assert not any(b.id[0] == "hd_set" for b in m.buttons)


# -- "+ Side quest" -> SideQuestPickModal wiring (M4-B sidequest, Task 2) ----

def test_questing_progress_modal_add_side_quest_flags_pending_and_closes():
    # Mirrors test_questing_progress_modal_quest_card_tap_flags_pending_and_
    # closes' pattern: the router only holds one modal at a time, so tapping
    # "+ Side quest" can no longer append directly (that would skip the
    # catalog-backed picker) - it flags pending_side_quest_pick and closes,
    # same as the pre-existing quest-card second-entry-point.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    assert game.pending_side_quest_pick is False
    # "+ Add" asks which first; the side-quest branch is what flags the picker.
    assert m.on_button(_find(m, ("add",))) == "redraw"
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("add_sq",))) == "close"
    assert game.pending_side_quest_pick is True
    assert game.side_quests == []          # nothing appended yet - picker does that


def test_questing_progress_modal_side_quest_row_prefers_name_when_present():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.side_quests = [{"points": 6, "progress": 1, "name": "Keep Watch"},
                        {"points": 4, "progress": 0}]      # old-save shape, no name
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "Keep Watch" in texts
    assert "Side Quest 2" in texts
    assert "Side Quest 1" not in texts


def test_side_quest_pick_adds_selected_with_points():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    entries = [{"id": "a", "name": "Scout Ahead", "points": 4, "sphere": "Lore", "pack": "p"},
               {"id": "b", "name": "Keep Watch", "points": 6, "sphere": "Tactics", "pack": "p"}]
    m = modals.SideQuestPickModal(game, entries)
    m.draw(hw, game, pal)
    # Step 1 is spheres, not quests - there is no row to tap yet.
    assert not any(b.id[0] == "row" for b in m.buttons)
    assert m.on_button(_find(m, ("sphere", "Tactics"))) == "redraw"
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("row", "b"))) == "redraw"     # select "Keep Watch"
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("add",))) == "close"
    assert game.side_quests[-1]["points"] == 6
    assert game.side_quests[-1]["name"] == "Keep Watch"
    assert game.side_quests[-1]["progress"] == 0
    # and we go back to the Progress modal we came from, not the play screen
    assert game.pending_progress_detail is True


def test_side_quest_pick_manual_falls_back_to_blank_entry():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    entries = [{"id": "a", "name": "Scout Ahead", "points": 4, "sphere": "Lore", "pack": "p"}]
    m = modals.SideQuestPickModal(game, entries)
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("manual",))) == "close"
    assert game.side_quests[-1]["points"] == 0 and game.side_quests[-1]["progress"] == 0
    assert game.pending_progress_detail is True    # Manual returns there too


def test_side_quest_pick_empty_entries_renders_and_offers_manual():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    m = modals.SideQuestPickModal(game, [])
    m.draw(hw, game, pal)          # must not raise
    assert any(b.id[0] == "manual" for b in m.buttons)
    assert not any(b.id[0] == "add" for b in m.buttons)   # nothing to add yet
    assert m.on_button(_find(m, ("manual",))) == "close"
    assert game.side_quests[-1]["points"] == 0 and game.side_quests[-1]["progress"] == 0


def test_side_quest_pick_null_points_default_to_zero_and_pager_pages():
    # 8 entries at PER_PAGE=6 exercises the Up/Down pager; one entry with
    # points=0 (the modal's already-normalized shape for a variable "X"
    # quest, per side_quests()'s null -> 0 contract) must never crash and
    # must still be selectable/addable.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    entries = [{"id": "x0", "name": "Protect the Innocent", "points": 0,
               "sphere": None, "pack": "p"}] + \
              [{"id": "e%d" % i, "name": "Quest %d" % i, "points": i + 1,
               "sphere": "Lore", "pack": "p"} for i in range(7)]
    m = modals.SideQuestPickModal(game, entries)
    m.draw(hw, game, pal)
    # A sphere-less card lands in its own group rather than being guessed
    # into one (the campaign side quests really have no sphere in the DB).
    assert m.on_button(_find(m, ("sphere", modals.SideQuestPickModal.NO_SPHERE))) == "redraw"
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("row", "x0"))) == "redraw"
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("add",))) == "close"
    assert game.side_quests[-1]["points"] == 0
    assert game.side_quests[-1]["name"] == "Protect the Innocent"


def test_side_quest_pick_groups_spheres_in_rulebook_order_unknown_last():
    """Rules Reference "Spheres of Influence": Leadership, Lore, Spirit,
    Tactics. Neutral follows, and anything the catalog has no sphere for is
    grouped last rather than guessed into a real sphere."""
    game = GameState()
    entries = [{"id": "n", "name": "N", "points": 1, "sphere": None, "pack": "p"},
               {"id": "t", "name": "T", "points": 1, "sphere": "Tactics", "pack": "p"},
               {"id": "l", "name": "L", "points": 1, "sphere": "Leadership", "pack": "p"},
               {"id": "u", "name": "U", "points": 1, "sphere": "Neutral", "pack": "p"},
               {"id": "o", "name": "O", "points": 1, "sphere": "Lore", "pack": "p"},
               {"id": "l2", "name": "L2", "points": 1, "sphere": "Leadership", "pack": "p"}]
    m = modals.SideQuestPickModal(game, entries)
    assert m.spheres() == [("Leadership", 2), ("Lore", 1), ("Tactics", 1),
                           ("Neutral", 1), (modals.SideQuestPickModal.NO_SPHERE, 1)]


def test_side_quest_pick_back_returns_to_the_sphere_list():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    entries = [{"id": "a", "name": "Scout Ahead", "points": 4, "sphere": "Lore", "pack": "p"}]
    m = modals.SideQuestPickModal(game, entries)
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("sphere", "Lore")))
    m.draw(hw, game, pal)
    assert m.selected == "a"                       # first in the sphere preselected
    assert m.on_button(_find(m, ("back",))) == "redraw"
    assert m.sphere is None and m.selected is None
    m.draw(hw, game, pal)
    assert any(b.id[0] == "sphere" for b in m.buttons)
    assert not any(b.id[0] == "add" for b in m.buttons)   # nothing picked yet


# --- Scenario Options: difficulty is data-driven ---------------------------
# "Hard" is not a general difficulty in this game - it is a printed Mode card
# that exactly one scenario of 349 ships (The Hunt for the Dreadnaught).
# Easy IS general (drop the gold-ring cards), so it always applies.

def _opts_screen(modes=None, mode_cards=None, nightmare=False):
    from ui.screen_quest import ScenarioOptionsScreen
    entry = {"slug": "s", "name": "A Quest", "pack": "P", "modes": modes or [],
             "hasNightmare": nightmare}
    data = {"name": "A Quest", "modes": mode_cards or []}
    return ScenarioOptionsScreen(entry, data)


def test_plain_scenario_offers_only_easy_and_standard():
    s = _opts_screen()
    assert s.difficulty_options() == ("Easy", "Standard")


def test_hard_offered_only_when_the_scenario_prints_a_hard_mode_card():
    s = _opts_screen(modes=["Easy Mode", "Standard Mode", "Hard Mode"])
    assert "Hard" in s.difficulty_options()


def test_epic_multiplayer_offered_when_printed():
    s = _opts_screen(modes=["Standard Game Mode", "Epic Multiplayer Mode"])
    opts = s.difficulty_options()
    assert "Epic Multiplayer" in opts
    assert "Standard" in opts and "Hard" not in opts


def test_mode_tip_uses_the_cards_own_printed_text():
    s = _opts_screen(
        modes=["Hard Mode"],
        mode_cards=[{"name": "Hard Mode",
                     "faces": [{"side": "A", "text": "Add 3 Tolfalas Landing locations."}]}])
    s.difficulty = "Hard"
    assert any("Tolfalas Landing" in m for m in s._tip_messages())


def test_easy_keeps_the_general_rule_copy():
    """Easy is a general rule, so it uses the authored copy even on a scenario
    that prints its own Mode cards - it never falls through to card text."""
    s = _opts_screen(modes=["Easy Mode", "Hard Mode"],
                     mode_cards=[{"name": "Easy Mode",
                                  "faces": [{"side": "A", "text": "Some printed text."}]}])
    s.difficulty = "Easy"
    assert any("gold-bordered" in m for m in s._tip_messages())


def test_standard_shows_no_tip():
    s = _opts_screen()
    assert s._tip_messages() == []


# --- Nightmare is a rung on the same ladder, not a second dropdown ---------
# It is also per-scenario: a Nightmare deck is a separately sold product and
# only 68 of the 349 catalogued scenarios have one. The catalog says which
# (`hasNightmare`); offering it everywhere was the same bug as offering Hard
# everywhere.

def test_nightmare_offered_only_when_the_scenario_has_a_nightmare_deck():
    assert "Nightmare" not in _opts_screen().difficulty_options()
    assert "Nightmare" in _opts_screen(nightmare=True).difficulty_options()


def test_nightmare_sits_last_on_the_ladder():
    s = _opts_screen(modes=["Hard Mode"], nightmare=True)
    assert s.difficulty_options() == ("Easy", "Standard", "Hard", "Nightmare")


def test_only_one_tip_can_ever_show():
    """The panel renders at a single fixed scale, so it must never be handed
    two messages - that is what used to make the tip shrink."""
    s = _opts_screen(modes=["Hard Mode"], nightmare=True)
    for d in s.difficulty_options():
        s.difficulty = d
        assert len(s._tip_messages()) <= 1, d


def test_authored_tip_copy_is_never_clipped_in_the_tightest_layout():
    """These tips state rules, so a truncated one is a wrong one. The panel is
    shortest when the scenario fills all four sets-to-gather rows - assert the
    copy still survives _clip_to_height there, rather than asserting some line
    count I picked. Lengthen the copy past what fits and this fails."""
    from ui.screen_quest import ScenarioOptionsScreen as S
    hw = FakeHardware()
    worst_dd_y = S.GATHER_Y0 + S.MAX_GATHER_ROWS * S.GATHER_ROW_H + 6
    avail = S.CTA_Y - 10 - (worst_dd_y + 62)          # exactly what draw() computes
    s = _opts_screen()
    for label, text in S.TIP_TEXT.items():
        kept = s._clip_to_height(hw.display, [text], 2, avail)
        assert kept == [text], "%s tip gets clipped: %r" % (label, kept)


def test_quest_card_button_previews_the_picked_scenario_before_it_is_loaded():
    """Scenario Options opens the card reference BEFORE preload_scenario, so
    the modal has to read the stages it is handed rather than the game's
    (which are still empty at that point)."""
    from ui.modals import QuestCardModal
    stages = [{"stage": 1, "cards": [{"questPoints": 8, "faces": [
        {"side": "A", "name": "Flies and Spiders", "text": "Setup text."},
        {"side": "B", "name": "Flies and Spiders", "text": "8 quest points."}]}]}]
    s = _opts_screen()
    s.data = {"name": "A Quest", "quest": {"stages": stages}}
    game = GameState()
    assert not game.stages, "precondition: nothing preloaded yet"
    result = s.on_button(_btn(("open_card_modal",)), game)
    assert result[0] == "modal" and isinstance(result[1], QuestCardModal)
    m = result[1]
    assert m.stages == stages
    hw = FakeHardware()
    m.draw(hw, game, Palette(hw.display))
    joined = " ".join(str(c[1]) for c in hw.display.calls if c[0] == "text")
    assert "Flies and Spiders" in joined
    assert "No quest loaded" not in joined


def test_quest_card_button_does_nothing_without_stages():
    s = _opts_screen()
    s.data = {"name": "A Quest"}
    assert s.on_button(_btn(("open_card_modal",)), GameState()) is None


def test_easy_tip_states_both_halves_of_the_rule():
    """Easy mode is two steps (Learn to Play p.28): add a resource to each
    hero AND remove the gold-bordered cards. Shipping only the removal - which
    this did - is half a rule, which is a wrong rule."""
    s = _opts_screen()
    s.difficulty = "Easy"
    tip = s._tip_messages()[0].lower()
    assert "resource" in tip and "hero" in tip, "missing the +1 resource step"
    assert "gold" in tip and "border" in tip, "missing the card-removal step"


# -- LocationPickModal: the catalog-backed list step ------------------------
#
# Entries are the real compiled values for Passage Through Mirkwood's six
# locations (docs/data, verified 2026-07-25) - see test_quest_catalog.py's
# gate test, which proves quest_catalog.locations_for() produces exactly
# this from the scenario's gather list.
PASSAGE_LOCS = [
    {"id": "a", "name": "Enchanted Stream", "points": 2, "threat": 2, "set": "Dol Guldur Orcs"},
    {"id": "b", "name": "Forest Gate", "points": 4, "threat": 2, "set": "Passage Through Mirkwood"},
    {"id": "c", "name": "Great Forest Web", "points": 2, "threat": 2, "set": "Spiders of Mirkwood"},
    {"id": "d", "name": "Mountains of Mirkwood", "points": 3, "threat": 2, "set": "Spiders of Mirkwood"},
    {"id": "e", "name": "Necromancer's Pass", "points": 2, "threat": 3, "set": "Dol Guldur Orcs"},
    {"id": "f", "name": "Old Forest Road", "points": 3, "threat": 1, "set": "Passage Through Mirkwood"},
]


def _pick(entries=PASSAGE_LOCS, mode="new", back="play", game=None):
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = game or GameState()
    m = modals.LocationPickModal(game, mode=mode, entries=entries, back=back)
    m.draw(hw, game, pal)
    return hw, pal, game, m


def _texts(hw):
    return [str(c[1]) for c in hw.display.calls if c[0] == "text"]


def test_location_pick_lists_the_catalog_with_both_numbers():
    hw, pal, game, m = _pick()
    assert m.step == "list"
    joined = " ".join(_texts(hw))
    assert "Old Forest Road" in joined
    assert "3 qp" in joined      # its printed quest points
    assert "1" in joined         # its printed threat


def test_location_pick_travel_commits_the_card_numbers_and_name():
    # THE point of the feature: no hand-entered guesses. Old Forest Road is
    # 3 quest points / 1 threat, and travelling removes that threat from the
    # staging area.
    hw, pal, game, m = _pick()
    game.staging = 6
    m.on_button(_find(m, ("row", "f")))
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("travel",))) == "close"
    # The record now KEEPS the card's threat, not just spends it on the staging
    # total: putting the location back into staging has to add the same number
    # again, and by then the caller no longer has it.
    assert game.active_locations[0] == {"points": 3, "progress": 0,
                                    "name": "Old Forest Road", "threat": 1}
    assert game.staging == 5
    assert "Traveled to Old Forest Road" in game.log[-2]["text"]


def test_progress_location_row_opens_the_detail_sheet():
    # LocationConfigModal was unreachable dead code: nothing constructed it.
    # The Location row's title is now its entry point, using the same
    # close-and-flag dance as the quest row (a modal cannot open another).
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_locations = [{"points": 3, "progress": 1, "name": "Tangled Grove"}]
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("detail", "l", 0))) == "close"
    assert game.pending_location_detail is True


def test_location_config_edit_keeps_the_card_metadata():
    # The commit used to REPLACE the record with {points, progress}, dropping
    # the card name, its threat and the *Kind/*Formula keys the picker had just
    # filled in - so editing progress silently cost you the threat that
    # "Back to staging" needs. It now merges onto the existing record instead.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_locations = [{
        "points": 3, "progress": 1, "name": "Tangled Grove", "threat": 4,
        "threatKind": "x",
        "threatX": {"text": "the number of locations in the staging area",
                    "target": "locations_in_staging"}}]
    m = modals.LocationConfigModal(game)
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("prog", 1)))
    assert not any(b.id[0] in ("save", "cancel") for b in m.buttons)
    loc = game.active_locations[0]
    assert loc["progress"] == 2
    assert loc["name"] == "Tangled Grove"
    assert loc["threat"] == 4
    assert loc["threatKind"] == "x"
    assert loc["threatX"]["target"] == "locations_in_staging"


def test_travel_from_the_travel_view_logs_a_travel():
    hw, pal, game, m = _pick()          # back defaults to the play screen
    m.on_button(_find(m, ("row", "f")))
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("travel",)))
    assert any("Traveled to Old Forest Road" in e["text"] for e in game.log)


def test_adding_a_location_from_progress_is_not_a_travel():
    # Travelling is only travelling when the players pay the travel cost. "+ Add
    # location" is not the Travel phase, and the log is the game's record - it
    # must not invent a travel. The MECHANICS are the same either way (RR: "the
    # active location acts as a buffer", so the threat leaves staging regardless).
    hw, pal, game, m = _pick(back="progress")
    m.on_button(_find(m, ("row", "f")))
    hw.display.calls.clear()                   # _pick already drew the header
    m.draw(hw, game, pal)
    texts = " ".join(_texts(hw))
    assert "Add Location" in texts and "Travel" not in texts
    m.on_button(_find(m, ("travel",)))
    assert any("Placed as active location" in e["text"] for e in game.log)
    assert not any("Traveled to" in e["text"] for e in game.log)


def test_manual_card_effect_choice_retitles_and_relogs():
    hw, pal, game, m = _pick(entries=[])       # opens straight on manual
    m.on_button(_find(m, ("arr", "effect")))
    hw.display.calls.clear()                   # _pick already drew the default
    m.draw(hw, game, pal)
    texts = " ".join(_texts(hw))
    assert "New active location" in texts
    assert "Travel to new location" not in texts
    m.on_button(_find(m, ("save",)))
    assert any("Placed as active location" in e["text"] for e in game.log)


def test_manual_defaults_to_travel():
    hw, pal, game, m = _pick(entries=[])
    m.draw(hw, game, pal)
    assert m.arrival == "travel"
    assert "Travel to new location" in " ".join(_texts(hw))


def test_staging_threat_is_drawn_black_not_red():
    # design/stat-system.md: staging and enemy threat is never red - red is the
    # player's own threat track. The picker's rows and its manual step were both
    # using pal.red.
    hw, pal, game, m = _pick()
    m.draw(hw, game, pal)
    # Icon masks are drawn as rects, so the pen is the call's last element.
    pens = {c[-1] for c in hw.display.calls if c[0] == "rect"}
    assert pal.red not in pens, "picker rows still draw threat in red"
    assert pal.outline in pens


def test_progress_cannot_exceed_the_target():
    # RR p.22: excess progress beyond a stage's quest points is DISCARDED on
    # advance, not carried, and a location explores the moment it is full - so a
    # bar reading 12/3 describes a state the game cannot be in. This used to run
    # to 99 on every row.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.quest["points"] = 3
    game.active_locations = [{"points": 2, "progress": 0}]
    game.side_quests = [{"points": 4, "progress": 0}]
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    for _ in range(8):
        m.on_button(_find(m, ("qP+", None)))
        m.on_button(_find(m, ("sP+", 0)))
    assert game.quest["progress"] == 3
    assert game.side_quests[0]["progress"] == 4
    # The location caps the same way, but a custom game auto-explores at the cap
    # so the row clears rather than pinning at 2/2 - redraw between taps, as the
    # real loop does, or the button outlives its record.
    for _ in range(8):
        m.draw(hw, game, pal)
        btn = [b for b in m.buttons if b.id == ("lP+", 0)]
        if not btn:
            break
        m.on_button(btn[0])
    assert not game.active_locations


def test_a_condition_stage_has_no_cap_to_hit():
    # No quest points means no target to clamp against, and the player may be
    # counting resource tokens or defeated enemies - leave it free.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.quest["points"] = 0
    game.quest["mode"] = "condition"
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    for _ in range(8):
        m.on_button(_find(m, ("qP+", None)))
    assert game.quest["progress"] == 8


def test_quest_sheet_shows_the_loss_condition_too():
    # 11 stages state BOTH. Return to Rhosgobel is won if Wilyador is healed and
    # lost otherwise; showing only the win is showing half the rule.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.quest["mode"] = "condition"
    game.quest["advance"] = "The players win if Wilyador is fully healed."
    game.quest["lose"] = "Otherwise the players lose the game."
    m = modals.QuestConfigModal(game)
    m.draw(hw, game, pal)
    texts = " ".join(_texts(hw))
    assert "Wilyador" in texts
    assert "Otherwise" in texts


def test_location_sheet_says_staging_keeps_progress():
    # RR: progress is NOT lost when a location returns to staging - Impassable
    # Chasm has to SAY "remove all progress tokens", which it would not need to
    # if returning did it. The note was in the approved mock and got dropped.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_locations = [{"points": 3, "progress": 1, "name": "Old Forest Road"}]
    m = modals.LocationConfigModal(game)
    m.draw(hw, game, pal)
    assert "Back to staging keeps its progress." in " ".join(_texts(hw))


def _loc_x(threat_x, count=None, **extra):
    # Seats it the way the picker does rather than assigning the list: an auto
    # target resolves in _seat_location, so a direct assignment would test a
    # record the app can never actually produce.
    game = GameState()
    meta = {"threatKind": "x", "threatX": threat_x}
    if count is not None:
        meta["threatCount"] = count
    meta.update(extra)
    game.travel_to(3, 0, "A Location", meta)
    return game


def test_threat_count_control_does_the_arithmetic():
    # THE point of the coded X: the player answers "how many enemies are in
    # play?" - a question they can settle by looking at the table - and the app
    # applies the +1. They never do it in their head.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = _loc_x({"text": "1 more than the number of enemies in play",
                   "target": "enemies_in_play", "add": 1}, count=3)
    m = modals.LocationConfigModal(game)
    m.draw(hw, game, pal)
    assert m.threat_shape == "count"
    assert m.threat_label == "Enemies in play"
    texts = " ".join(_texts(hw))
    assert "Enemies in play" in texts        # the stepper is labelled by what it counts
    assert "Threat" in texts and "= X" in texts
    # 3 enemies -> threat 4, and one tap makes it 4 -> 5.
    m.on_button(_find(m, ("count", 1)))
    # No save tap: the sheet has no Save, so the tap itself is the commit.
    # Stores the COUNT, not just the result: storing only the result would go
    # stale the moment the board changes.
    assert game.active_locations[0]["threatCount"] == 4
    assert game.active_locations[0]["threat"] == 5


def test_threat_auto_target_needs_no_control_at_all():
    # 16 of the 58 formulas are answerable from the player count we already
    # track, so there is nothing to ask - and a stale count must not be able to
    # override it.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = _loc_x({"text": "the number of players in the game",
                   "target": "players"}, count=99)
    m = modals.LocationConfigModal(game)
    m.draw(hw, game, pal)
    assert m.threat_shape == "auto"
    assert not any(b.id[0] == "count" for b in m.buttons)
    # Nothing to tap and no Save to press, so the number cannot come from this
    # sheet at all - _seat_location resolves it when the card is placed.
    assert game.active_locations[0]["threat"] == len(game.players)


def test_threat_bare_count_keeps_one_stepper_and_no_second_number():
    # 19 of the 40 are a bare count, where the count IS the value - so the row
    # must NOT grow a read-only duplicate above its own stepper.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = _loc_x({"text": "the number of locations in the staging area",
                   "target": "locations_in_staging"})
    m = modals.LocationConfigModal(game)
    m.draw(hw, game, pal)
    assert m.threat_shape == "bare"
    assert not any(b.id[0] == "count" for b in m.buttons)
    assert any(b.id[0] == "threat" for b in m.buttons)


def test_coded_x_suppresses_the_defined_elsewhere_note():
    # The note contradicts the formula line directly above it, and used to fire
    # whenever threat happened to be 0.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = _loc_x({"text": "1 more than the number of enemies in play",
                   "target": "enemies_in_play", "add": 1})
    m = modals.LocationConfigModal(game)
    m.draw(hw, game, pal)
    assert "defines it elsewhere" not in " ".join(_texts(hw))


def test_location_config_threat_starts_blank_when_x_is_undefined():
    # 18 X-printing faces define X nowhere we can read. The value slot stays
    # empty rather than claiming 0 - for threat especially, a wrong 0
    # under-reports the staging total the player compares willpower against.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_locations = [{"points": 5, "progress": 0, "name": "Amon Hen",
                              "threatKind": "x"}]
    m = modals.LocationConfigModal(game)
    m.draw(hw, game, pal)
    assert m.threat_blank is True
    assert "the card prints X and defines it elsewhere" in " ".join(_texts(hw))
    # One tap makes it a real value, and the tap IS the commit - there is no
    # Save on this sheet.
    m.on_button(_find(m, ("threat", 1)))
    assert m.threat_blank is False
    assert game.active_locations[0]["threat"] == 1


def test_location_pick_carries_the_x_metadata_onto_the_location():
    # A location printing X for its threat must reach the location record with
    # the marker AND the card's own definition of X, or the Progress screen has
    # nothing to show but a 0 the card never printed.
    entries = [{"id": "x", "name": "Tangled Grove", "points": 3, "threat": 0,
                "set": "The Oath", "threatKind": "x",
                "threatX": {"text": "the number of locations in the staging area",
                            "target": "locations_in_staging"}}]
    hw, pal, game, m = _pick(entries=entries)
    m.on_button(_find(m, ("row", "x")))
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("travel",)))
    loc = game.active_locations[0]
    assert loc["threatKind"] == "x"
    assert loc["threatX"]["target"] == "locations_in_staging"
    # points printed a real 3, so it carries no marker at all
    assert "pointsKind" not in loc and "pointsX" not in loc


def test_location_pick_manual_entry_stays_a_two_key_record():
    # The manual stepper has no card behind it, so it must not gain any of the
    # optional keys - old saves and hand-entered locations stay identical.
    hw, pal, game, m = _pick(entries=[])
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("save",)))
    assert game.active_locations[0] == {"points": m.pts, "progress": 0}


def test_location_pick_hides_travel_until_a_row_is_picked():
    # Hidden, not disabled (the pager arrows set the precedent) - in "change"
    # mode a stray tap on a preselected row would discard real progress.
    hw, pal, game, m = _pick()
    assert m.selected is None
    assert not [b for b in m.buttons if b.id == ("travel",)]
    m.on_button(_find(m, ("row", "a")))
    m.draw(hw, game, pal)
    assert [b for b in m.buttons if b.id == ("travel",)]


def test_location_pick_manual_step_is_the_old_stepper_and_can_return():
    hw, pal, game, m = _pick()
    assert m.on_button(_find(m, ("manual",))) == "redraw"
    m.draw(hw, game, pal)
    assert m.step == "manual"
    assert [b for b in m.buttons if b.id == ("pts", 1)]
    assert [b for b in m.buttons if b.id == ("ctr", 1)]
    assert m.on_button(_find(m, ("back",))) == "redraw"
    assert m.step == "list"


def test_location_pick_without_catalog_opens_straight_on_the_stepper():
    # ~290 quest scenarios have no gather list, 3 gather no locations at all,
    # and a manual game has no scenario - all land here, byte-identical to
    # the pre-catalog modal (no Locations back button to return to).
    hw, pal, game, m = _pick(entries=[])
    assert m.step == "manual"
    assert not [b for b in m.buttons if b.id == ("back",)]
    m.on_button(_find(m, ("save",)))
    assert game.active_locations[0] == {"points": 3, "progress": 0}
    assert "Traveled to new location" in game.log[-1]["text"]


def test_location_pick_manual_save_carries_no_name():
    hw, pal, game, m = _pick()
    m.on_button(_find(m, ("manual",)))
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("save",)))
    assert "name" not in game.active_locations[0]


def test_location_pick_change_mode_replaces_and_warns():
    game = GameState()
    game.active_locations = [{"points": 5, "progress": 2}]
    hw, pal, game, m = _pick(mode="change", game=game)
    assert "Replaces the current location (2/5 discarded)." in " ".join(_texts(hw))
    m.on_button(_find(m, ("row", "b")))
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("travel",)))
    assert game.active_locations[0] == {"points": 4, "progress": 0,
                                    "name": "Forest Gate", "threat": 2}


def test_location_pick_pages_a_long_union():
    # Mount Gundabad gathers 14 locations, the catalog's worst case.
    entries = [{"id": str(i), "name": "Loc %d" % i, "points": 2, "threat": 1, "set": "S"}
               for i in range(14)]
    hw, pal, game, m = _pick(entries=entries)
    assert m._pages() == 3
    assert len([b for b in m.buttons if b.id[0] == "row"]) == 6
    m.on_button(_find(m, ("newer",)))
    m.on_button(_find(m, ("newer",)))
    m.draw(hw, game, pal)
    assert m.page == 2
    assert len([b for b in m.buttons if b.id[0] == "row"]) == 2


def test_location_pick_every_exit_returns_to_the_progress_modal():
    # back="progress" is how "+ Add location" gets you back where you were;
    # Travel, manual Save, the header's DONE and Cancel must all honour it.
    hw, pal, game, m = _pick(back="progress")
    m.on_button(_find(m, ("close",)))          # header DONE, from the list
    assert game.pending_progress_detail is True

    hw, pal, game, m = _pick(back="progress")
    m.on_button(_find(m, ("manual",)))
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("cancel",))) == "cancel"
    assert game.pending_progress_detail is True

    hw, pal, game, m = _pick(back="progress")
    m.on_button(_find(m, ("row", "a")))
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("travel",)))
    assert game.pending_progress_detail is True

    hw, pal, game, m = _pick(back="progress")
    m.on_button(_find(m, ("manual",)))
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("save",)))
    assert game.pending_progress_detail is True


def test_location_pick_from_travel_does_not_reopen_the_progress_modal():
    hw, pal, game, m = _pick(back="play")
    m.on_button(_find(m, ("row", "a")))
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("travel",)))
    assert game.pending_progress_detail is False


def test_progress_modal_row_shows_the_picked_location_name():
    # The row's title column is capped at 118px (the Current editor's hit-box
    # starts at x=136), so most real names truncate - same cap the catalog
    # side-quest names already live with. Assert the card, not the pixels.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_locations = [{"points": 3, "progress": 0, "name": "Old Forest Road"}]
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    texts = _texts(hw)
    assert any(t.startswith("Old Forest") for t in texts)
    assert "Location" not in texts


def test_progress_modal_row_falls_back_to_location_without_a_name():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_locations = [{"points": 3, "progress": 0}]
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    assert "Location" in _texts(hw)


# --------------------------------------------------------------------------
# Every modal and every new-game page must have a way out (2026-07-28)
# --------------------------------------------------------------------------

def _pal():
    from tests.fake_hardware import FakeHardware
    from ui.theme import Palette
    return Palette(FakeHardware().display)


def test_every_modal_state_can_be_dismissed():
    """No modal may be a trap.

    A "way out" means a button whose handler returns close or cancel, or one
    that returns to a parent state which has one. Nested pages (the players
    editor, the location sub-pages) count via their back button.
    """
    from tests.scenes import SCENES
    stuck = []
    for name in sorted(SCENES):
        try:
            hw, obj = SCENES[name]()
        except Exception:
            continue
        if "Modal" not in type(obj).__name__:
            continue
        ways = 0
        for b in list(obj.buttons):
            try:
                _hw2, probe = SCENES[name]()
            except Exception:
                continue
            tgt = next((x for x in probe.buttons if x.id == b.id), None)
            if tgt is None:
                continue
            try:
                r = probe.on_button(tgt)
            except Exception:
                continue
            if b.id[0] not in ("close", "cancel", "back", "no", "not_yet",
                               "lp_cancel", "done", "ok", "save", "go", "win",
                               "avert", "elim"):
                continue
            if r in ("close", "cancel", "redraw"):
                ways += 1
                continue
            # A sub-page's back button navigates by mutating modal state and
            # returns None; main redraws every tap regardless. That still
            # leaves the sub-page, so it counts - detect it by the button set
            # changing after the tap.
            try:
                before = {x.id for x in probe.buttons}
                probe.draw(_hw2, getattr(probe, "game", None), _pal())
                if {x.id for x in probe.buttons} != before:
                    ways += 1
            except Exception:
                pass
        if not ways:
            stuck.append((name, sorted({b.id[0] for b in obj.buttons})))
    assert not stuck, "modal states with no way out: %s" % stuck


def test_every_new_game_page_can_be_backed_out_of():
    """The new-game flow is a funnel, and every page of it must be
    reversible - a mis-picked scenario should never mean restarting.

    Dispatch the way main.py:437 does, by tapping the middle of the back
    button and taking the FIRST hit. Picking the button out of the list by id
    passed on two screens whose back button was buried under draw_header's
    own, so "< Menu" opened the Game Log.
    """
    from tests.fake_hardware import FakeHardware
    from ui.theme import Palette
    from ui.screen_quest import (ScenarioSourceScreen, PickCycleScreen,
                                 ChooseScenarioScreen, ScenarioOptionsScreen)
    from gamestate import GameState

    pages = [
        (ScenarioSourceScreen(), "boot"),
        (PickCycleScreen("official", []), "scenario_source"),
        (ChooseScenarioScreen("official", "c", []), None),
        (ScenarioOptionsScreen({"slug": "x", "source": "official",
                                "cycle": "c"}, {}), None),
    ]
    for screen, expect in pages:
        hw = FakeHardware()
        pal = Palette(hw.display)
        g = GameState(4, 25)
        screen.draw(hw, g, pal)
        back = [b for b in screen.buttons if b.id[0] == "back"]
        assert back, "%s has no back button" % type(screen).__name__
        x, y = back[0].x + back[0].w // 2, back[0].y + back[0].h // 2
        hit = next(b for b in screen.buttons if b.hit(x, y))
        assert hit.id[0] == "back", (
            "%s: tapping back at (%d,%d) hits %s instead"
            % (type(screen).__name__, x, y, hit.id))
        result = screen.on_button(hit, g)
        assert result is not None, type(screen).__name__
        if expect:
            assert result == ("goto", expect), (type(screen).__name__, result)


# --------------------------------------------------------------------------
# Twin parity, executed rather than eyeballed
# --------------------------------------------------------------------------

_JS_BACK_PROBE = """\
const m = await import("./screens_other.js");
const out = {};
out.ScenarioSourceScreen = new m.ScenarioSourceScreen().onButton({id: ["back"]});
out.PickCycleScreen = new m.PickCycleScreen("official", []).onButton({id: ["back"]});
out.ChooseScenarioScreen =
  new m.ChooseScenarioScreen("official", "c", []).onButton({id: ["back"]});
out.ScenarioOptionsScreen =
  new m.ScenarioOptionsScreen({slug: "x", source: "official", cycle: "c"}, {})
    .onButton({id: ["back"]}, null);
console.log(JSON.stringify(out));
"""


def test_the_web_twin_backs_out_of_the_new_game_flow_the_same_way():
    """Run the twin's own handlers and compare routes with the firmware's.

    Reading the two files side by side is what the iron rule asks for and it
    is not enough: the JS ScenarioSourceScreen shipped with no "back" case at
    all while its firmware sibling had one, and the missing line sat a few
    hundred lines away inside ScenarioOptionsScreen where it was unreachable.
    Nothing failed, because nothing executed the twin.

    The modules import under plain node with no DOM, so this costs a
    subprocess and settles the question instead of arguing it.
    """
    import json
    import shutil
    import subprocess
    import tempfile

    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")

    from ui.screen_quest import (ScenarioSourceScreen, PickCycleScreen,
                                 ChooseScenarioScreen, ScenarioOptionsScreen)

    py = {
        "ScenarioSourceScreen": ScenarioSourceScreen(),
        "PickCycleScreen": PickCycleScreen("official", []),
        "ChooseScenarioScreen": ChooseScenarioScreen("official", "c", []),
        "ScenarioOptionsScreen": ScenarioOptionsScreen(
            {"slug": "x", "source": "official", "cycle": "c"}, {}),
    }
    expect = {name: list(s.on_button(_btn(("back",)), None))
              for name, s in py.items()}

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with tempfile.TemporaryDirectory() as tmp:
        # docs/js has no package.json, so node reads its .js as CommonJS.
        # Copying beside a type:module marker is the least invasive fix - the
        # alternative puts a package.json into the deployed Pages site.
        for f in os.listdir(os.path.join(root, "docs", "js")):
            if f.endswith(".js"):
                shutil.copy(os.path.join(root, "docs", "js", f),
                            os.path.join(tmp, f))
        with open(os.path.join(tmp, "package.json"), "w") as f:
            f.write('{"type":"module"}')
        probe = os.path.join(tmp, "probe.mjs")
        with open(probe, "w") as f:
            f.write(_JS_BACK_PROBE)
        r = subprocess.run([node, probe], cwd=tmp, capture_output=True, text=True)
        assert r.returncode == 0, "web twin failed to load:\n%s" % r.stderr
        got = json.loads(r.stdout)

    for name in expect:
        assert got[name] == expect[name], (
            "%s: web twin backs out to %s, firmware to %s"
            % (name, got[name], expect[name]))
