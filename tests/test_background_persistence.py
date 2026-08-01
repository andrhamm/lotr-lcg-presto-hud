"""Gameplay writes RAM only; durable work happens in the background.

The tap path must not touch storage. This is an explicit product requirement,
not an optimisation: a tap costs a dict append and returns, and the ~50 ms
writes are drained by tick() on frames with nothing to draw.

The subtle part is the ownership rule. main.py rebinds `game` on new-game and
end-game, and a queued write derived from a different game is garbage - the
same hazard `pending[1] is game` already guards for deltas. A rebind must drop
the queue, never apply it, or an ended game gets resurrected by a late write.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import db as dbmod  # noqa: E402
from gamestate import GameState  # noqa: E402


@pytest.fixture
def store(tmp_path, monkeypatch):
    for name, fn in [("STATE_PATH", "state.json"), ("STATE_TMP", "state.tmp"),
                     ("LOG_PATH", "log.bin"), ("REPLAY_JOURNAL", "replay.bin"),
                     ("REPLAY_LEGACY", "replay.json")]:
        monkeypatch.setattr(dbmod, name, str(tmp_path / fn))
    return tmp_path


def _game():
    g = GameState(2, 25)
    g.clock = lambda: 0
    g.quest.update({"points": 8})
    return g


def _tap(sess, g, n):
    prev = g.begin_action()
    g.set_staging(n)
    g.add_delta(prev)
    sess.commit(g)


def test_a_tap_writes_nothing_to_storage(store):
    sess = dbmod.Session()
    g = _game()
    for n in range(1, 6):
        _tap(sess, g, n)
    assert os.listdir(store) == [], "a tap must not touch storage"
    assert sess.pending() > 0, "but it must have queued the work"


def test_tick_drains_the_journal_before_the_checkpoint(store):
    """Journal first: it is cheap, and it is what reconstructs the state."""
    sess = dbmod.Session()
    g = _game()
    for n in range(1, 6):
        _tap(sess, g, n)
    for _ in range(dbmod.Session.QUIET_FRAMES + 1):
        sess.tick(g)      # nothing until the screen has been still a while
    assert os.path.exists(dbmod.LOG_PATH) or os.path.exists(dbmod.REPLAY_JOURNAL)
    assert sess.pending() == 0


def test_the_checkpoint_waits_for_the_player_to_pause(store):
    """The ~89 ms state rewrite is the one expensive operation, so it must not
    land on the frame after every tap - it waits for a real gap."""
    sess = dbmod.Session()
    g = _game()
    _tap(sess, g, 3)
    for _ in range(dbmod.Session.QUIET_FRAMES + 2):
        sess.tick(g)                   # drains the journal
    assert not os.path.exists(dbmod.STATE_PATH), "checkpoint came too early"
    for _ in range(dbmod.Session.QUIET_FRAMES + dbmod.Session.IDLE_BEFORE_STATE + 2):
        sess.tick(g)
    assert os.path.exists(dbmod.STATE_PATH), "checkpoint never arrived"


def test_a_tap_during_the_wait_restarts_it(store):
    """A player mid-run must not pay for a checkpoint between taps."""
    sess = dbmod.Session()
    g = _game()
    for n in range(1, 20):
        _tap(sess, g, n % 8 + 1)
        sess.tick(g)                   # one idle frame between taps
    assert not os.path.exists(dbmod.STATE_PATH), (
        "a continuous run of taps must never trigger the checkpoint")
    sess.flush(g)
    assert os.path.exists(dbmod.STATE_PATH)


def test_flush_takes_the_checkpoint_without_waiting(store):
    sess = dbmod.Session()
    g = _game()
    _tap(sess, g, 3)
    sess.flush(g)
    assert os.path.exists(dbmod.STATE_PATH)
    assert sess.pending() == 0


def test_tick_does_at_most_one_unit_so_no_idle_frame_stalls(store):
    sess = dbmod.Session()
    g = _game()
    for n in range(1, 60):
        _tap(sess, g, n % 8 + 1)
    before = sess.pending()
    assert before > dbmod.Session.BATCH, "precondition: more than one batch"
    for _ in range(dbmod.Session.QUIET_FRAMES - 1):
        sess.tick(g)
    assert sess.tick(g) is True
    assert 0 < sess.pending() < before, "one tick must not drain everything"


def test_a_tick_writes_at_most_one_file(store):
    """The loop polls touch once per iteration, so two appends in one tick is
    ~110 ms of unresponsive screen - which is what the lag report was."""
    sess = dbmod.Session()
    g = _game()
    for n in range(1, 6):
        _tap(sess, g, n)
    for _ in range(dbmod.Session.QUIET_FRAMES - 1):
        assert sess.tick(g) is False, "wrote before the screen went quiet"
    assert sess.tick(g) is True          # the first tick that may write
    wrote = [p for p in (dbmod.LOG_PATH, dbmod.REPLAY_JOURNAL) if os.path.exists(p)]
    assert len(wrote) == 1, "a single tick wrote %d files" % len(wrote)


def test_writes_do_not_start_while_the_player_is_tapping(store):
    """A run of taps with a redraw between them must never trigger a write."""
    sess = dbmod.Session()
    g = _game()
    for n in range(1, 15):
        _tap(sess, g, n % 8 + 1)
        sess.tick(g)          # the one idle frame a fast tapper leaves
        sess.tick(g)
    assert os.listdir(store) == [], "wrote during an active run"


def test_tick_reports_false_once_there_is_nothing_left(store):
    sess = dbmod.Session()
    g = _game()
    _tap(sess, g, 3)
    sess.flush(g)
    assert sess.tick(g) is False


def test_a_game_rebind_drops_the_queue_rather_than_applying_it(store):
    """The resurrection bug: a queued write landing after end-game would
    recreate a save the player explicitly ended."""
    sess = dbmod.Session()
    g = _game()
    for n in range(1, 6):
        _tap(sess, g, n)
    assert sess.pending() > 0
    g2 = _game()                     # main.py rebinds `game`
    sess.record(g2)                  # first tap of the new game
    # nothing from the old game may survive into the new queue
    sess.flush(g2)
    from gamestate import fold_replay
    ops = dbmod._read(dbmod.REPLAY_JOURNAL)
    deltas, _ = fold_replay(ops)
    assert len(deltas) == 0, "old game's deltas leaked into the new one"


def test_tick_for_a_game_that_no_longer_owns_the_queue_is_a_no_op(store):
    sess = dbmod.Session()
    g = _game()
    _tap(sess, g, 3)
    other = _game()
    assert sess.tick(other) is False
    assert os.listdir(store) == []


def test_flush_makes_everything_durable_for_save_and_quit(store):
    sess = dbmod.Session()
    g = _game()
    for n in range(1, 30):
        _tap(sess, g, n % 8 + 1)
    sess.flush(g)
    assert sess.pending() == 0
    g2 = GameState.from_dict(sess.load_state()["state"])
    sess.load_log(g2)
    sess.load_replay(g2)
    assert g2.deltas == g.deltas
    assert g2.replay_step == g.replay_step
    assert [e["text"] for e in g2.log] == [e["text"] for e in g.log]


def test_the_queue_survives_being_ticked_between_taps(store):
    """The realistic loop: tap, idle, tap, idle - nothing lost either way."""
    sess = dbmod.Session()
    g = _game()
    for n in range(1, 40):
        _tap(sess, g, n % 8 + 1)
        sess.tick(g)
    sess.flush(g)
    g2 = GameState.from_dict(sess.load_state()["state"])
    sess.load_log(g2)
    sess.load_replay(g2)
    assert g2.deltas == g.deltas
    assert [e["text"] for e in g2.log] == [e["text"] for e in g.log]
