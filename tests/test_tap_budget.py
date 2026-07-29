"""Task 4 of docs/superpowers/plans/2026-07-25-m3-speed.md: encodes the
"common round" tap walk from that plan's Context section and gates it at the
milestone's tap budget. If this ever needs to change, update the plan's
before/after table in the same commit - the two must stay in sync.

Before this milestone the identical scenario took 29 taps. M3 got it to 22,
2 of which came from inline threat +/- in the players zone.

Those were REVERTED (2026-07-28): the players-zone tokens are read-only
status, not controls - 24px halves were too small to hit deliberately and too
easy to hit by accident. Threat now goes through the Players modal, which
costs an open and a close, so the same round became 24 taps.

Then Resource and Planning were split into their own views (2.P was the only
action-window step with no view of its own), which adds one more advance:
25. Both increases are recorded here rather than hidden by relaxing the walk.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.screen_play import ScreenPlay
from gamestate import GameState

TAP_BUDGET = 25


def test_common_round_hits_tap_budget():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    for i, c in enumerate((3, 4, 2, 2)):          # last round's persisted commits
        game.set_commit(i, c)
    for p in game.players:
        p.commit_touched = False                  # fresh round: nobody reviewed yet
    game.active_location = {"points": 6, "progress": 2}
    game.view = "resource"
    game.step = "1.R"
    screen = ScreenPlay()
    state = {"modal": None, "taps": 0}

    def tap(btn_id):
        state["taps"] += 1
        target = state["modal"] or screen
        target.draw(hw, game, pal)
        btn = next(b for b in target.buttons if b.id == btn_id)
        result = screen.on_button(btn, game) if target is screen else target.on_button(btn)
        if isinstance(result, tuple) and result[0] == "modal":
            state["modal"] = result[1]
        elif result in ("close", "cancel"):
            state["modal"] = None
        return result

    tap(("advance",))                              # 1: resource -> planning
    assert game.view == "planning"
    tap(("advance",))                              # 2: planning -> quest_commit
    assert game.view == "quest_commit"

    tap(("players_detail",))                       # 2: open PlayersDetailModal
    tap(("w", 2, -1))                               # 3: P3 commit 2 -> 1
    tap(("close",))                                 # 4: close modal
    tap(("confirm_all",))                           # 5: mark P1/P2/P4 reviewed too
    tap(("advance",))                               # 6: -> quest_staging
    assert game.view == "quest_staging"
    assert game.willpower == 10                     # 3+4+1+2
    assert all(p.commit_touched for p in game.players)

    tap(("stg+",)); tap(("stg+",)); tap(("stg+",))  # 7,8,9: +3 staging
    tap(("stage_advance",))                         # 10: -> quest_resolution
    assert game.view == "quest_resolution"
    assert game.quest_outcome == "success"

    tap(("apply_alloc",))                           # 11: accept auto-split -> travel
    assert game.view == "travel"

    tap(("advance",))                               # 12: -> enc_optional
    tap(("advance",))                               # 13: -> enc_checks
    tap(("advance",))                               # 14: -> combat_shadow
    assert game.view == "combat_shadow"

    # shadow effect, +1 threat each. The players zone is read-only, so this
    # is a modal round-trip: open, four taps, close.
    tap(("players_detail",))                        # 15: open PlayersDetailModal
    for i in range(4):                              # 16-19: +1 threat each
        tap(("t", i, 1))
    tap(("close",))                                 # 20: close modal
    assert [p.threat for p in game.players] == [1, 1, 1, 1]

    tap(("advance",))                               # 21: -> combat_enemy
    tap(("advance",))                               # 22: -> combat_player
    tap(("advance",))                               # 23: -> refresh
    tap(("endround",))                              # 24: end round

    assert game.round == 2
    assert state["taps"] <= TAP_BUDGET, \
        "common round took %d taps (budget %d)" % (state["taps"], TAP_BUDGET)
