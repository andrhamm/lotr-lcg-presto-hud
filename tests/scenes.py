"""Scene builders shared by tools/preview.py and the layout lint tests.

Each builder returns (hw, obj) where hw.display.calls holds the draw calls and
obj (screen or modal) exposes .buttons. Covers every wireframe state.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from gamestate import GameState, VIEW_STEP


def _game():
    g = GameState()
    for i, t in enumerate((14, 28, 41, 19)):
        g.adjust_threat(i, t)
    g.quest = {"stage_n": 2, "side": "B", "points": 8, "progress": 6}
    g.active_location = {"points": 3, "progress": 2}
    g.side_quests = [{"points": 5, "progress": 3}]
    g.willpower = 11
    g.staging = 7
    return g


def _play(view, mutate=None):
    def build():
        from ui.screen_play import ScreenPlay
        hw = FakeHardware()
        pal = Palette(hw.display)
        g = _game()
        g.view = view
        g.step = VIEW_STEP[view]
        if view == "quest_commit":
            for i, c in enumerate((3, 4, 2, 2)):
                g.set_commit(i, c)
        if view == "quest_resolution":
            g.pending_budget = 4
        if mutate:
            mutate(g)
        s = ScreenPlay()
        s.draw(hw, g, pal)
        return hw, s
    return build


def _boot(saved):
    def build():
        from ui.screen_boot import BootScreen
        hw = FakeHardware()
        pal = Palette(hw.display)
        s = BootScreen(saved)
        s.draw(hw, _game(), pal)
        return hw, s
    return build


def _setup(threats, first=0):
    def build():
        from ui.screen_setup import SetupScreen
        hw = FakeHardware()
        pal = Palette(hw.display)
        s = SetupScreen()
        s.threats = list(threats)
        s.first = first
        s.draw(hw, _game(), pal)
        return hw, s
    return build


def _screen(mod, cls, prep=None):
    def build():
        import importlib
        m = importlib.import_module(mod)
        hw = FakeHardware()
        pal = Palette(hw.display)
        g = _game()
        if prep:
            prep(g)
        s = getattr(m, cls)()
        s.draw(hw, g, pal)
        return hw, s
    return build


def _elim_modal():
    from ui.modals import EliminationModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    g.adjust_threat(2, 20)  # 41 + 20 -> crosses 50
    m = EliminationModal(g, 2)
    m.draw(hw, g, pal)
    return hw, m


def _led_modal():
    from ui.modals import LedModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    m = LedModal({"brightness": 70, "scene": "torch"}, g)
    m.draw(hw, g, pal)
    return hw, m


def _commit_modal():
    from ui.modals import CommitModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    for i, c in enumerate((3, 4, 2, 2)):
        g.set_commit(i, c)
    m = CommitModal(g, 2)
    m.state.tap(2)
    m.draw(hw, g, pal)
    return hw, m


def _reminders_modal():
    from ui.modals import RemindersModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    g.reminders["archery"] = True
    g.reminders["shadow"] = True
    m = RemindersModal(g)
    m.draw(hw, g, pal)
    return hw, m


def _questing_for():
    from ui.modals import QuestingForModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = _game()
    for i, c in enumerate((3, 4, 2, 2)):
        g.set_commit(i, c)
    m = QuestingForModal(g)
    m.draw(hw, g, pal)
    return hw, m


def _counter():
    from ui.modal_counter import CounterModal
    hw = FakeHardware()
    pal = Palette(hw.display)
    m = CounterModal("P1 threat", 14, icon="threat")
    m.state.tap(5)
    m.draw(hw, None, pal)
    return hw, m


def _log_prep(g):
    for i in range(30):
        g.log_event("P%d threat %d -> %d after a fairly long explanation" % ((i % 4) + 1, 20 + i, 21 + i))


SCENES = {
    "boot": _boot({"round": 3, "phase": "Combat (Enemy Attacks)", "saved_at": "2026-07-21 19:04"}),
    "boot_fresh": _boot(None),
    "setup": _setup([25]),
    "setup3": _setup([25, 27, 29], first=1),
    "setup4": _setup([25, 27, 29, 31], first=3),
    "play_setup": _play("setup_game"),
    "play_resource_planning": _play("resource_planning"),
    "play_quest_commit": _play("quest_commit"),
    "play_quest_staging": _play("quest_staging"),
    "play_quest_resolution": _play("quest_resolution"),
    "play_travel": _play("travel"),
    "play_travel_none": _play("travel", mutate=lambda g: setattr(g, "active_location", None)),
    "play_enc_optional": _play("enc_optional"),
    "play_enc_checks": _play("enc_checks"),
    "play_combat_shadow": _play("combat_shadow"),
    "play_combat_enemy": _play("combat_enemy"),
    "play_combat_player": _play("combat_player"),
    "play_refresh": _play("refresh"),
    "phases_screen": _screen("ui.screen_phases", "ScreenPhases"),
    "log": _screen("ui.screen_log", "ScreenLog", prep=_log_prep),
    "settings": _screen("ui.screen_settings", "ScreenSettings"),
    "counter": _counter,
    "elim_modal": _elim_modal,
    "commit_modal": _commit_modal,
    "questing_for_modal": _questing_for,
    "reminders_modal": _reminders_modal,
    "led_modal": _led_modal,
}
