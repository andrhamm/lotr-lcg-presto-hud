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


def test_questing_for_modal_adjusts_and_logs_on_save():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.set_commit(0, 2)
    game.adjust_threat(3, 50)          # eliminated -> no row
    game.pending_elim = None
    m = modals.QuestingForModal(game)
    m.draw(hw, game, pal)
    assert not any(b.id == ("wpm", 3, 1) for b in m.buttons)
    plus1 = _find(m, ("wpm", 1, 1))
    m.on_button(plus1)
    m.on_button(plus1)
    assert m.on_button(_find(m, ("save",))) == "close"
    assert game.players[1].commit == 2
    assert game.willpower == 4
    assert any("P2 committed 2" in e["text"] for e in game.log)


def test_questing_for_modal_cancel_discards():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    m = modals.QuestingForModal(game)
    m.draw(hw, game, pal)
    m.on_button(_find(m, ("wpm", 0, 1)))
    m.on_button(_find(m, ("cancel",)))
    assert game.players[0].commit == 0
