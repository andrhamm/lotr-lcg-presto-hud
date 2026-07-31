import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.screen_log import ScreenLog
from gamestate import GameState


def _draw():
    hw = FakeHardware()
    pal = Palette(hw.display)
    s = ScreenLog()
    s.draw(hw, GameState(), pal)
    return hw, s


def test_header_shows_game_log_title():
    hw, s = _draw()
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "Game Log" in texts


def test_done_is_the_only_nav_and_round_is_not_a_link():
    hw, s = _draw()
    navs = [b.id for b in s.buttons if b.id[0] == "nav"]
    assert navs == [("nav", "close")]      # DONE only — R# and Set. are not links
    close = [b for b in s.buttons if b.id == ("nav", "close")][0]
    assert (close.x, close.y, close.w, close.h) == (408, 4, 64, 32)  # upper-right DONE button
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "DONE" in texts and "X" not in texts


def test_close_returns_goto_close():
    hw, s = _draw()
    close = [b for b in s.buttons if b.id == ("nav", "close")][0]
    assert s.on_button(close, GameState()) == ("goto", "close")


# -- replay transport (Task 5) ----------------------------------------------
# Parity: frontend/src/features/messages/LogButtons.js and LogMessageDiv.js,
# where the log IS the delta list and every row is a jump target. Ours keeps a
# separate append-only log and rides the delta_i stamp add_delta writes.

def _draw_with(g):
    """_draw(), but over a caller-supplied game."""
    hw = FakeHardware()
    pal = Palette(hw.display)
    s = ScreenLog()
    s.draw(hw, g, pal)
    return hw, pal, s


def _history(n=3):
    """A round-1 game with n recorded deltas, each raising P1's threat by 1
    AND logging a line - so each delta has both a state change to assert on
    and a log row that can carry its delta_i jump stamp."""
    g = GameState(2, 25)
    g.advance_view()
    for i in range(n):
        snap = g.begin_action()
        g.adjust_threat(0, 1)
        g.log_event("P1 threat +1 (%d)" % i)
        g.add_delta(snap)
    return g


def _btn(s, id):
    return [b for b in s.buttons if b.id == id][0]


def _texts(hw):
    return [str(c[1]) for c in hw.display.calls if c[0] == "text"]


def test_transport_shows_the_cursor_position():
    g = _history(3)
    hw, pal, s = _draw_with(g)
    assert "Step 3/3" in _texts(hw)


def test_transport_undo_moves_the_cursor_and_the_game():
    g = _history(3)
    hw, pal, s = _draw_with(g)
    assert g.players[0].threat == 28
    assert s.on_button(_btn(s, ("replay", "undo")), g) is True
    assert g.replay_step == 1
    assert g.players[0].threat == 27


def test_transport_first_and_last_rewind_and_fast_forward():
    g = _history(3)
    hw, pal, s = _draw_with(g)
    s.on_button(_btn(s, ("replay", "first")), g)
    assert g.replay_step == -1
    assert g.players[0].threat == 25
    hw, pal, s = _draw_with(g)
    s.on_button(_btn(s, ("replay", "last")), g)
    assert g.replay_step == 2
    assert g.players[0].threat == 28


def test_transport_is_a_noop_at_the_ends():
    g = _history(0)
    hw, pal, s = _draw_with(g)
    assert s.on_button(_btn(s, ("replay", "undo")), g) is None
    assert s.on_button(_btn(s, ("replay", "redo")), g) is None


def test_transport_draws_even_with_no_history_so_the_layout_is_stable():
    g = _history(0)
    hw, pal, s = _draw_with(g)
    assert "Step 0/0" in _texts(hw)
    for which in ("first", "round_back", "undo", "redo", "last"):
        assert _btn(s, ("replay", which)) is not None


def test_tapping_a_delta_row_jumps_to_it():
    g = _history(3)
    hw, pal, s = _draw_with(g)
    assert s.on_button(_btn(s, ("replay_jump", 0)), g) is True
    assert g.replay_step == 0
    assert g.players[0].threat == 26


def test_rows_without_a_delta_get_no_jump_button():
    """Setup entries are logged before any delta exists, so they are not jump
    targets - only the rows a recorded action produced are."""
    g = _history(2)
    hw, pal, s = _draw_with(g)
    jumps = sorted(b.id[1] for b in s.buttons if b.id[0] == "replay_jump")
    assert jumps == [0, 1]              # not one per log row
    assert len(g.log) > len(jumps)      # setup lines exist and are inert


def test_an_action_that_logs_nothing_gets_no_jump_row():
    """A delta with no log messages has no row to attach to. It is still
    reachable through the transport - just not by tapping the log."""
    g = GameState(2, 25)
    g.advance_view()
    snap = g.begin_action()
    g.adjust_threat(0, 1)               # adjust_threat logs nothing
    assert g.add_delta(snap) is True
    hw, pal, s = _draw_with(g)
    assert not [b for b in s.buttons if b.id[0] == "replay_jump"]
    assert g.can_undo() is True


def test_round_back_halts_at_the_round_boundary():
    g = GameState(2, 25)
    g.advance_view()
    snap = g.begin_action(); g.adjust_threat(0, 1); g.add_delta(snap)
    g.view = "refresh"
    snap = g.begin_action(); g.end_round(); g.add_delta(snap)
    snap = g.begin_action(); g.enter_view("quest_commit"); g.add_delta(snap)
    assert g.round == 2
    hw, pal, s = _draw_with(g)
    assert s.on_button(_btn(s, ("replay", "round_back")), g) is True
    assert g.round == 1


def test_per_page_shrank_to_make_room_for_the_transport():
    from ui.screen_log import PER_PAGE, REPLAY_Y, ROW_H
    from ui.header import HEADER_H
    assert PER_PAGE == 11
    assert HEADER_H + 10 + PER_PAGE * ROW_H <= REPLAY_Y


class _Btn:
    """Bare button stand-in for handler tests that skip draw(). Distinct from
    the _btn() lookup helper above, which finds a drawn button by id."""
    def __init__(self, id_):
        self.id = id_


def _log_game():
    return GameState(1, 29)


def test_story_filter_hides_phase_rows_and_all_shows_them():
    """The log recorded keystrokes, not the game: 73 rows over two rounds in
    the 2026-07-30 playtest, ~11 of them meaningful. Phase transitions are
    identical every round and carry no game state, and every row already shows
    its own R<round>.<step>, so they are hidden by default and one tap away."""
    g = _log_game()
    g.log_event("Phase: Travel", cat="phase")
    g.log_event("Traveled to Forest Gate (4 quest points)")
    g.log_event("Phase: Encounter", cat="phase")
    s = ScreenLog()
    hw = FakeHardware()
    s.draw(hw, g, Palette(hw.display))
    shown = " ".join(str(c[1]) for c in hw.display.calls if c[0] == "text")
    assert "Traveled to Forest Gate" in shown
    assert "Phase: Travel" not in shown
    assert "Story" in shown            # the toggle names the current filter

    # Registered as a real tap target, not just drawn. draw_header honoured
    # round_id on its default branch only, so with close=True the filter label
    # rendered and nothing could tap it - caught in the browser, not by a test
    # that called on_button directly.
    filt = [b for b in s.buttons if b.id == ("filter",)]
    assert filt, "the Story/All label is not a tap target"
    s.on_button(filt[0], g)
    assert s.show_all is True
    hw2 = FakeHardware()
    s.draw(hw2, g, Palette(hw2.display))
    shown2 = " ".join(str(c[1]) for c in hw2.display.calls if c[0] == "text")
    assert "Phase: Travel" in shown2
    assert "All" in shown2


def test_a_run_of_stepper_taps_is_one_row_not_eight():
    """Committing 8 willpower wrote eight rows, one per tap. It is one
    decision, so it is one row - naming the settled value."""
    g = _log_game()
    before = len(g.log)
    for n in range(1, 9):
        g.set_willpower(n)
    rows = g.log[before:]
    assert len(rows) == 1, [r["text"] for r in rows]
    assert "8" in rows[0]["text"]


def test_reopening_a_stepper_later_starts_a_new_row():
    """The collapse must not span: seeing WHEN each change happened is the
    point of a log, so an intervening entry breaks the run."""
    g = _log_game()
    g.set_willpower(3)
    g.log_event("Traveled to Forest Gate (4 quest points)")
    g.set_willpower(9)
    tallies = [e for e in g.log if e.get("key") == "wp"]
    assert len(tallies) == 2
    assert "3" in tallies[0]["text"] and "9" in tallies[1]["text"]
