"""The replay store's append-only journal must fold back to the live pair.

replay.json was rewritten in full on every tap - 42 KB and 875 ms by round 10.
The journal appends instead, which means the two operations that are NOT
appends (undo discarding the redo future, and the MAX_SAVED_DELTAS front-trim)
have to survive as tombstones.

The invariant under test is the one the plan named as load-bearing:

    fold_replay(journal) == (game.deltas, game.replay_step)

for any tap sequence, INCLUDING after an undo-truncation and after a
front-trim. A silent wrong-undo is worse than a crash (see _migrate_delta's
note in gamestate.py), so this is checked exhaustively rather than by example.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gamestate  # noqa: E402
from gamestate import GameState, fold_replay  # noqa: E402


def _game():
    g = GameState(2, 25)
    g.clock = lambda: 0
    g.quest.update({"points": 8})
    return g


def _tap(g, fn):
    prev = g.begin_action()
    fn()
    return g.add_delta(prev)


def _check(g, journal):
    """The invariant."""
    deltas, step = fold_replay(journal)
    assert step == g.replay_step, "cursor drifted: %r vs %r" % (step, g.replay_step)
    assert len(deltas) == len(g.deltas), (
        "delta count drifted: %d vs %d" % (len(deltas), len(g.deltas)))
    assert deltas == g.deltas


def test_plain_run_of_taps_folds_back():
    g = _game()
    journal = []
    for n in range(1, 12):
        _tap(g, lambda n=n: g.set_staging(n))
        journal.extend(g.take_replay_appends())
    _check(g, journal)


def test_undo_then_act_truncates_the_redo_future():
    g = _game()
    journal = []
    for n in range(1, 8):
        _tap(g, lambda n=n: g.set_staging(n))
        journal.extend(g.take_replay_appends())
    # walk the cursor back, which must be journalled too
    g.step_through({"size": "single", "direction": "undo"})
    g.step_through({"size": "single", "direction": "undo"})
    journal.extend(g.take_replay_appends())
    _check(g, journal)
    # a fresh action now discards the redo future
    _tap(g, lambda: g.set_staging(99))
    journal.extend(g.take_replay_appends())
    _check(g, journal)


def test_cursor_moves_alone_are_journalled():
    g = _game()
    journal = []
    for n in range(1, 6):
        _tap(g, lambda n=n: g.set_staging(n))
        journal.extend(g.take_replay_appends())
    g.step_through({"size": "index", "index": 1})
    journal.extend(g.take_replay_appends())
    _check(g, journal)
    g.step_through({"size": "index", "index": len(g.deltas) - 1})
    journal.extend(g.take_replay_appends())
    _check(g, journal)


def test_front_trim_at_the_delta_cap_survives_as_a_tombstone():
    """MAX_SAVED_DELTAS drops from the front; the journal must record it or a
    reload comes back with more history than the game has."""
    g = _game()
    journal = []
    cap = gamestate.MAX_SAVED_DELTAS
    for n in range(cap + 25):
        _tap(g, lambda n=n: g.set_staging(n % 50 + 1))
        journal.extend(g.take_replay_appends())
    assert len(g.deltas) == cap, "precondition: the cap actually engaged"
    _check(g, journal)


def test_interleaved_undo_and_action_over_a_long_session():
    g = _game()
    journal = []
    for rnd in range(40):
        for n in range(1, 5):
            _tap(g, lambda n=n: g.set_staging(n))
            journal.extend(g.take_replay_appends())
        if rnd % 3 == 0:
            g.step_through({"size": "single", "direction": "undo"})
            journal.extend(g.take_replay_appends())
        if rnd % 7 == 0:
            _tap(g, lambda: g.set_staging(42))
            journal.extend(g.take_replay_appends())
        _check(g, journal)


def test_seed_rebuilds_an_existing_history_from_empty():
    """Upgrading a game that already has deltas from the whole-file store."""
    g = _game()
    for n in range(1, 10):
        _tap(g, lambda n=n: g.set_staging(n))
    g.take_replay_appends()          # discard; simulate a pre-journal game
    _check(g, g.seed_replay_journal())


def test_take_replay_appends_clears():
    g = _game()
    _tap(g, lambda: g.set_staging(3))
    assert g.take_replay_appends()
    assert g.take_replay_appends() == []


def test_fold_of_an_empty_journal_is_an_empty_history():
    assert fold_replay([]) == ([], -1)


def test_fold_clamps_a_cursor_past_the_end():
    """A torn journal can leave a cursor op with no delta behind it."""
    deltas, step = fold_replay([{"op": "d", "d": {"a": [1, 2]}},
                                {"op": "s", "i": 99}])
    assert len(deltas) == 1
    assert step == 0
