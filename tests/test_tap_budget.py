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

Then the eight action-window screens were wired into the flow (2026-07-28).
They were a non-functional prototype before: nothing could enter or leave one.
Always-in-flow was chosen deliberately over "once per game" - a checklist that
only appears when the app is confident it is needed goes missing precisely
when it matters. Six of the eight fall inside this walk (the Resource,
Commit, Resolution, Travel, Opt. Engage and Checks windows), taking it to 31.
The Staging window is skipped because a successful resolve jumps straight to
the resolution view, and the Refresh window sits after End Round.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.screen_play import ScreenPlay
from gamestate import GameState

TAP_BUDGET = 31


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

    tap(("advance",))                              # 1: resource -> its window
    assert game.view == "aw_resource"
    tap(("advance",))                              # 2: -> planning
    assert game.view == "planning"
    tap(("advance",))                              # 3: planning -> quest_commit
    assert game.view == "quest_commit"             # Planning has no window

    tap(("players_detail",))                       # 2: open PlayersDetailModal
    tap(("w", 2, -1))                               # 3: P3 commit 2 -> 1
    tap(("close",))                                 # 4: close modal
    tap(("confirm_all",))                           # 5: mark P1/P2/P4 reviewed too
    tap(("advance",))                               # -> the Commit window
    assert game.view == "aw_quest_commit"
    tap(("advance",))                               # -> quest_staging
    assert game.view == "quest_staging"
    assert game.willpower == 10                     # 3+4+1+2
    assert all(p.commit_touched for p in game.players)

    tap(("stg+",)); tap(("stg+",)); tap(("stg+",))  # 7,8,9: +3 staging
    tap(("stage_advance",))                         # 10: -> quest_resolution
    assert game.view == "quest_resolution"
    assert game.quest_outcome == "success"

    tap(("apply_alloc",))                           # accept auto-split
    assert game.view == "aw_quest_resolution"       # lands on 3.4's window
    tap(("advance",))                               # -> travel
    assert game.view == "travel"

    tap(("advance",))                               # -> the Travel window
    tap(("advance",))                               # -> enc_optional
    tap(("advance",))                               # -> its window
    tap(("advance",))                               # -> enc_checks
    tap(("advance",))                               # -> its window
    tap(("advance",))                               # -> combat_shadow
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
