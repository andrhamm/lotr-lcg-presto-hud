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


def test_quest_config_edits_land_without_a_save():
    # The sheet has no Save and no Cancel - every tap has already landed on
    # the game, the way PlayersDetailModal and the location sheet work.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    m = modals.QuestConfigModal(game)
    m.draw(hw, game, pal)
    assert not any(b.id[0] in ("save", "cancel") for b in m.buttons)
    for _ in range(8):
        m.on_button(_find(m, ("pts", 1)))
        m.draw(hw, game, pal)
    assert game.quest["points"] == 8       # no commit tap in between


def test_quest_config_logs_one_summary_line_on_the_way_out():
    # A log entry per stepper tap would bury the round.
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    m = modals.QuestConfigModal(game)
    m.draw(hw, game, pal)
    for _ in range(3):
        m.on_button(_find(m, ("pts", 1)))
        m.draw(hw, game, pal)
    before = len(game.log)
    assert m.on_button(_find(m, ("close",))) == "close"
    assert len(game.log) == before + 1


