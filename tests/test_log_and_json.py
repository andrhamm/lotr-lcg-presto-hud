import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gamestate import GameState


# -- log -------------------------------------------------------------------

def test_log_event_tags_round_and_step():
    g = GameState()
    g.step = "3.4"
    g.log_event("Placed 4 progress")
    entry = g.log[-1]
    assert entry["round"] == 1
    assert entry["step"] == "3.4"
    assert entry["text"] == "Placed 4 progress"


def test_log_entries_have_increasing_seq():
    g = GameState()
    g.log_event("a")
    g.log_event("b")
    assert g.log[0]["seq"] < g.log[1]["seq"]


def test_end_round_writes_round_and_phase_entries():
    g = GameState()
    before = len(g.log)
    g.end_round()
    assert len(g.log) > before
    texts = [e["text"] for e in g.log[before:]]
    assert any("New round" in t for t in texts)
    assert any(t.startswith("Phase:") for t in texts)


def test_resolve_quest_fail_logs_threat_increase():
    g = GameState()
    g.resolve_quest(willpower=2, staging=7)
    assert any("threat" in e["text"].lower() for e in g.log)


# -- json ------------------------------------------------------------------

def test_to_dict_from_dict_round_trip():
    g = GameState()
    g.adjust_threat(0, 14)
    g.players[1].threat_per_round = 2
    g.step = "6.P"
    g.quest = {"stage_n": 2, "side": "B", "points": 8, "progress": 5}
    g.active_locations = [{"points": 3, "progress": 1}]
    g.side_quests = [{"points": 5, "progress": 2}]
    g.first_player = 2
    g.round = 4
    g.log_event("hello")

    restored = GameState.from_dict(g.to_dict())
    assert restored.to_dict() == g.to_dict()


def test_from_dict_migrates_a_pre_list_save():
    # Saves written before active_locations existed hold a single
    # "active_location" dict (or null). They must still load - a player mid-
    # campaign should not lose the location they travelled to because the HUD
    # learned to hold two.
    d = GameState().to_dict()
    del d["active_locations"]                 # as an old save actually looks
    d["active_location"] = {"points": 3, "progress": 1}
    assert GameState.from_dict(d).active_locations == [{"points": 3, "progress": 1}]


def test_from_dict_migrates_a_pre_list_save_with_no_location():
    d = GameState().to_dict()
    del d["active_locations"]
    d["active_location"] = None
    assert GameState.from_dict(d).active_locations == []


def test_two_active_locations_survive_a_round_trip():
    # Five printed cards allow a second active location, which is the whole
    # reason for the list - see gamestate.active_locations for the list.
    g = GameState()
    g.active_locations = [{"points": 3, "progress": 1, "name": "A"},
                          {"points": 2, "progress": 0, "name": "B"}]
    restored = GameState.from_dict(g.to_dict())
    assert restored.active_locations == g.active_locations
    assert restored.to_dict() == g.to_dict()


def test_new_game_has_zero_questing_inputs():
    g = GameState()
    assert g.willpower == 0
    assert g.staging == 0


def test_questing_inputs_survive_round_trip():
    g = GameState()
    g.willpower = 11
    g.staging = 7
    restored = GameState.from_dict(g.to_dict())
    assert restored.willpower == 11
    assert restored.staging == 7


def test_from_dict_restores_player_and_progress_state():
    g = GameState()
    g.adjust_threat(3, 41)
    g.active_locations = [{"points": 4, "progress": 2}]
    restored = GameState.from_dict(g.to_dict())
    assert restored.players[3].threat == 41
    assert restored.players[3].eliminated is False
    assert restored.active_locations[0] == {"points": 4, "progress": 2}


# --------------------------------------------------------------------------
# Log completeness
# --------------------------------------------------------------------------

def _game_fingerprint(g):
    """Everything a player would expect to see accounted for in the log."""
    return (tuple((p.threat, p.commit, p.elimination, p.threat_per_round,
                   p.starting_threat, p.eliminated) for p in g.players),
            dict(g.quest),
            tuple(dict(l) for l in g.active_locations),
            [dict(s) for s in g.side_quests],
            g.willpower, g.staging, g.sailing, g.heading, g.round,
            g.first_player)


def _fresh_game():
    from gamestate import GameState
    g = GameState(4, 25)
    g.active_locations = [{"points": 3, "progress": 1}]
    g.side_quests = [{"points": 5, "progress": 2}]
    g.sailing = True
    return g


# Controls that change state but deliberately do not log, with the reason.
_SILENT = {
    # Navigation and view flow log their own "Phase: X" line on arrival, so a
    # second entry for the same tap would double up.
    ("play", "advance"), ("play", "back"),
}


def test_every_play_screen_control_that_changes_state_logs_it():
    """The log is the game's audit trail, and it had holes.

    Willpower and staging were assigned straight to the attribute from three
    places, so committing willpower - the single most-repeated action in a
    round - left no trace. This walks every control on every play view and
    asserts that a tap which moves the game also says so.
    """
    from tests.fake_hardware import FakeHardware
    from ui.theme import Palette
    from ui.screen_play import ScreenPlay
    from gamestate import VIEW_STEP, VIEW_ORDER

    skip = ("nav", "advance", "back", "players_detail", "progress_detail",
            "open_card_modal", "setup_back", "banner")
    offenders = []
    for view in VIEW_ORDER:
        def build():
            hw = FakeHardware()
            g = _fresh_game()
            g.view = view
            g.step = VIEW_STEP.get(view, g.step)
            s = ScreenPlay()
            try:
                s.draw(hw, g, Palette(hw.display))
            except Exception:
                return None, None, None
            return hw, g, s
        _, _, probe = build()
        if probe is None:
            continue                      # view needs scenario data; covered by scenes
        for bid in sorted({b.id for b in probe.buttons}, key=str):
            if bid[0] in skip or ("play", bid[0]) in _SILENT:
                continue
            _, g, s = build()
            hit = [b for b in s.buttons if b.id == bid]
            if not hit:
                continue
            before, n = _game_fingerprint(g), len(g.log)
            try:
                s.on_button(hit[0], g)
            except Exception:
                continue                  # opens a modal / needs catalog data
            if _game_fingerprint(g) != before and len(g.log) == n:
                offenders.append("%s: %s" % (view, bid))
    assert not offenders, (
        "these controls change the game without logging it:\n  %s"
        % "\n  ".join(offenders))


def test_every_modal_control_that_changes_state_logs_it():
    """Same rule for the modals.

    Some commit on Save and some edit live, so this taps and then closes by
    whichever affordance the modal offers - which is also what caught that the
    progress modal was fine, flushing one summary on close.
    """
    from tests.fake_hardware import FakeHardware
    from ui.theme import Palette
    from ui import modals

    cases = [
        (modals.QuestConfigModal, lambda g: modals.QuestConfigModal(g)),
        (modals.LocationConfigModal, lambda g: modals.LocationConfigModal(g)),
        (modals.SideQuestsModal, lambda g: modals.SideQuestsModal(g)),
        (modals.QuestingProgressModal, lambda g: modals.QuestingProgressModal(g)),
        (modals.SailingModal, lambda g: modals.SailingModal(g)),
        (modals.PlayersDetailModal, lambda g: modals.PlayersDetailModal(g)),
        (modals.PlayerSettingsModal, lambda g: modals.PlayerSettingsModal(g, 1)),
    ]
    offenders = []
    for cls, make in cases:
        hw = FakeHardware()
        g = _fresh_game()
        probe = make(g)
        probe.draw(hw, g, Palette(hw.display))
        for bid in sorted({b.id for b in probe.buttons}, key=str):
            if bid[0] in ("cancel", "close", "save", "apply"):
                continue
            hw2 = FakeHardware()
            g2 = _fresh_game()
            m = make(g2)
            pal2 = Palette(hw2.display)
            m.draw(hw2, g2, pal2)
            hit = [b for b in m.buttons if b.id == bid]
            if not hit:
                continue
            before, n = _game_fingerprint(g2), len(g2.log)
            try:
                m.on_button(hit[0])
                m.draw(hw2, g2, pal2)
                for sid in (("save",), ("apply",), ("close",)):
                    exits = [b for b in m.buttons if b.id == sid]
                    if exits:
                        m.on_button(exits[0])
                        break
            except Exception:
                continue
            if _game_fingerprint(g2) != before and len(g2.log) == n:
                offenders.append("%s: %s" % (cls.__name__, bid))
    assert not offenders, (
        "these modal controls change the game without logging it:\n  %s"
        % "\n  ".join(offenders))
