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
when it matters. Seven of the eight fall inside this walk - only the Staging window is
skipped, because a successful resolve jumps straight to the resolution view.

The round boundary then split in two (2026-07-28): 7.3 and 7.4 apply on
ARRIVAL at the refresh view, where RR's chart puts them, and the round turns
on a new round_end view at step 0.1. That is +1 tap and removes the End Round
CTA, which had been doing two jobs at once. Total: 33.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.screen_play import ScreenPlay
from gamestate import GameState

TAP_BUDGET = 33


def test_common_round_hits_tap_budget():
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    for i, c in enumerate((3, 4, 2, 2)):          # last round's persisted commits
        game.set_commit(i, c)
    for p in game.players:
        p.commit_touched = False                  # fresh round: nobody reviewed yet
    game.active_locations = [{"points": 6, "progress": 2}]
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
    tap(("advance",))                               # -> the Commit window
    assert game.view == "aw_quest_commit"
    tap(("advance",))                               # -> quest_staging
    assert game.view == "quest_staging"
    assert game.willpower == 10                     # 3+4+1+2
    # the total is the players' own sum, so nothing is detached
    assert game.willpower_detached is False

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

    tap(("advance",))                               # -> combat_enemy
    tap(("advance",))                               # -> combat_player
    tap(("advance",))                               # -> refresh (7.3/7.4 apply)
    assert game.first_player == 1                   # token passed on arrival
    tap(("advance",))                               # -> the Refresh window
    tap(("advance",))                               # -> round_end (0.1)
    assert game.view == "round_end"
    assert game.round == 1                          # 0.1 is still this round
    tap(("endround",))                              # turn the round

    assert game.round == 2
    assert state["taps"] <= TAP_BUDGET, \
        "common round took %d taps (budget %d)" % (state["taps"], TAP_BUDGET)
