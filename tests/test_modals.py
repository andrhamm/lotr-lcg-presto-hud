import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.modal_counter import CounterModal
from ui import modals
from gamestate import GameState


def _find(m, id):
    return [b for b in m.buttons if b.id == id][0]


def test_all_modals_draw_without_error():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_location = {"points": 3, "progress": 1}
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


def test_commit_modal_cycles_from_tapped_player():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    m = modals.CommitModal(game, 2)  # started at P3
    assert [i + 1 for i in m.order] == [3, 4, 1, 2]
    assert m.final is False
    m.draw(hw, game, pal)
    m.state.tap(3)
    m.on_button(_find(m, ("next",)))
    assert game.players[2].commit == 3
    assert m.idx == 3                      # P4
    m.on_button(_find(m, ("next",)))       # P4 commits 0 (unchanged)
    m.on_button(_find(m, ("next",)))       # P1
    assert m.final is True
    # Next inert on final player
    assert m.on_button(_find(m, ("next",))) is None
    assert m.idx == 1                      # still P2
    m.state.tap(4)
    assert m.on_button(_find(m, ("done",))) == "close"
    assert game.players[1].commit == 4
    assert game.willpower == 7


def test_commit_modal_skips_eliminated():
    game = GameState()
    game.adjust_threat(1, 50)
    game.pending_elim = None
    m = modals.CommitModal(game, 0)
    assert [i + 1 for i in m.order] == [1, 3, 4]


def test_commit_modal_reset_button_zeroes():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.set_commit(0, 5)
    m = modals.CommitModal(game, 0)
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("step", "zero")))
    assert m.state.preview == 0
    m.on_button(_find(m, ("done",)))
    assert game.players[0].commit == 0


def test_commit_modal_shows_value_without_party_labels():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    for i, c in enumerate((3, 4, 2, 2)):
        game.set_commit(i, c)
    m = modals.CommitModal(game, 2)   # P3 current (2)
    m.state.tap(2)                    # preview 4
    m.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "4" in texts               # big willpower value shown
    # committed/uncommitted party totals were dropped (web parity)
    assert not any(t.startswith("committed") for t in texts)
    assert not any(t.startswith("uncommitted") for t in texts)


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
    assert "Players" in texts and "Threat" in texts and "Willpower" in texts


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


def test_players_detail_modal_willpower_step_touches_commit_and_logs():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    m = modals.PlayersDetailModal(game)
    m.draw(hw, game, pal)
    game.players[1].commit_touched = False
    assert m.on_button(_find(m, ("w", 1, 1))) is None
    assert game.players[1].commit == 1
    assert game.players[1].commit_touched is True
    assert any("P2 committed 1 willpower" in e["text"] for e in game.log)


def test_players_detail_modal_inline_edit_pad_commits_on_ok_and_returns_to_grid():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.set_commit(2, 3)
    game.players[2].commit_touched = False
    m = modals.PlayersDetailModal(game)
    m.draw(hw, game, pal)
    # opening the willpower editor (token tap) touches the commit immediately
    assert m.on_button(_find(m, ("w", 2, "edit"))) is None
    assert m.edit is not None
    assert game.players[2].commit_touched is True
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


def test_questing_progress_modal_quest_card_button_present_only_with_stages():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()   # no preload_scenario: game.stages == [] (custom game)
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    assert not any(b.id == ("quest_card",) for b in m.buttons)

    game.preload_scenario({"slug": "p", "name": "P", "pack": "Core Set", "cycle": "Core Set",
                           "source": "official", "kind": "quest", "nightmare": False,
                           "mode": "Standard"}, _QPM_STAGES)
    m2 = modals.QuestingProgressModal(game)
    m2.draw(hw, game, pal)
    assert any(b.id == ("quest_card",) for b in m2.buttons)


def test_questing_progress_modal_quest_card_tap_flags_pending_and_closes():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.preload_scenario({"slug": "p", "name": "P", "pack": "Core Set", "cycle": "Core Set",
                           "source": "official", "kind": "quest", "nightmare": False,
                           "mode": "Standard"}, _QPM_STAGES)
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    assert game.pending_quest_card is False
    assert m.on_button(_find(m, ("quest_card",))) == "close"
    assert game.pending_quest_card is True


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
    qc = _find(m, ("quest_card",))
    cur_minus = _find(m, ("qP-", None))
    assert qc.x + qc.w <= cur_minus.x
    # and editors were pushed first, so they'd win on overlap regardless
    ids = [b.id for b in m.buttons]
    assert ids.index(("qP-", None)) < ids.index(("quest_card",))
    assert ids.index(("qP+", None)) < ids.index(("quest_card",))
    assert ids.index(("qT-", None)) < ids.index(("quest_card",))
    assert ids.index(("qT+", None)) < ids.index(("quest_card",))


def test_questing_progress_modal_location_current_bump_explores_when_done():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_location = {"points": 3, "progress": 2}
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("lP+", None))) is None
    assert game.active_location is None
    assert any("Explored" in e["text"] for e in game.log)


def test_questing_progress_modal_complete_location_logs_and_clears():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_location = {"points": 5, "progress": 1}
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("ldone", None))) is None
    assert game.active_location is None
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
    game.active_location = {"points": 4, "progress": 2}
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("lX", None))) is None
    assert m.loc_prompt == {"stage": "choose"}
    assert game.active_location == {"points": 4, "progress": 2}   # untouched
    m.draw(hw, game, pal)                                         # re-render the prompt
    assert not any(b.id == ("close",) for b in m.buttons)         # header suppressed


def test_questing_progress_modal_loc_prompt_cancel_leaves_location_untouched():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_location = {"points": 4, "progress": 2}
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("lX", None)))
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("lp_cancel",))) is None
    assert m.loc_prompt is None
    assert game.active_location == {"points": 4, "progress": 2}


def test_questing_progress_modal_loc_prompt_discard_clears_and_logs():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_location = {"points": 4, "progress": 2}
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("lX", None)))
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("lp_discard",))) is None
    assert game.active_location is None
    assert m.loc_prompt is None
    assert game.log[-1]["text"] == "Active location removed"


def test_questing_progress_modal_loc_prompt_replaced_sets_new_location():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_location = {"points": 4, "progress": 2}
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
    assert game.active_location == {"points": 6, "progress": 0}
    assert m.loc_prompt is None
    assert any("Changed active location" in e["text"] for e in game.log)


def test_questing_progress_modal_loc_prompt_pts_cancel_returns_to_choose():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_location = {"points": 4, "progress": 1}
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("lX", None)))
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("lp_replaced",)))
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("cancel",))) is None
    assert m.loc_prompt == {"stage": "choose"}
    assert game.active_location == {"points": 4, "progress": 1}   # untouched


def test_questing_progress_modal_loc_prompt_to_staging_adds_threat_and_clears():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_location = {"points": 4, "progress": 2}
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
    assert game.active_location is None
    assert m.loc_prompt is None
    assert any("Active location to staging (+3 threat)" in e["text"] for e in game.log)


def test_questing_progress_modal_add_location_when_none():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_location = None
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("addloc",))) is None
    assert game.active_location == {"points": 3, "progress": 0}
    assert game.log[-1]["text"] == "Active location added (card effect)"


def test_questing_progress_modal_add_location_then_close_does_not_double_log():
    # Regression: _snap must refresh after any already-logged mutation, or
    # the closing summary would also emit a spurious "set 0/3" line on top
    # of the explicit "added" line.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.active_location = None
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("addloc",)))
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("close",))) == "close"
    loc_logs = [e["text"] for e in game.log if "Active location" in e["text"]]
    assert loc_logs == ["Active location added (card effect)"]


def test_questing_progress_modal_heading_radio_sets_heading_and_logs():
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
    assert "willpower / staging / result / heading" in texts


def test_questing_progress_modal_chart_hides_heading_row_when_not_sailing():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.sailing = False
    game.resolve_quest(14, 10)
    m = modals.QuestingProgressModal(game)
    m.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "willpower / staging / result" in texts
    assert "willpower / staging / result / heading" not in texts
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
    assert m.on_button(_find(m, ("add",))) == "close"
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
    assert m.on_button(_find(m, ("row", "b"))) == "redraw"     # select "Keep Watch"
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("add",))) == "close"
    assert game.side_quests[-1]["points"] == 6
    assert game.side_quests[-1]["name"] == "Keep Watch"
    assert game.side_quests[-1]["progress"] == 0


def test_side_quest_pick_manual_falls_back_to_blank_entry():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    entries = [{"id": "a", "name": "Scout Ahead", "points": 4, "sphere": "Lore", "pack": "p"}]
    m = modals.SideQuestPickModal(game, entries)
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("manual",))) == "close"
    assert game.side_quests[-1]["points"] == 0 and game.side_quests[-1]["progress"] == 0


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
    assert any(b.id == ("older",) for b in m.buttons) or any(b.id == ("newer",) for b in m.buttons)
    assert m.on_button(_find(m, ("row", "x0"))) == "redraw"
    m.draw(hw, game, pal)
    assert m.on_button(_find(m, ("add",))) == "close"
    assert game.side_quests[-1]["points"] == 0
    assert game.side_quests[-1]["name"] == "Protect the Innocent"
