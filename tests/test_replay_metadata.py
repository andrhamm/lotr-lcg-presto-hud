"""A delta remembers the view and round it landed on, and truncating the redo
future truncates the log rows it orphaned (with a tombstone the fold applies).
Both twins."""
import json
import os, sys
import gamestate
from gamestate import GameState, fold_log

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _tap(g, fn):
    snap = g.begin_action()
    fn()
    return g.add_delta(snap)


def _two_view_game():
    # WINDOW_POLICY_BANDS (the tablet's policy) so advance_view() steps
    # resource -> planning directly instead of through the aw_resource
    # window screen - the default WINDOW_POLICY_VIEWS keeps windows in the
    # flow, which is a real client behaviour but not what this fixture is
    # about. conftest.py's autouse fixture resets this after the test.
    gamestate.set_window_policy(gamestate.WINDOW_POLICY_BANDS)
    g = GameState(2)
    g.view = "resource"
    _tap(g, lambda: g.set_staging(1))                 # delta 0, view resource
    _tap(g, lambda: g.advance_view())                 # delta 1, lands on planning
    _tap(g, lambda: g.set_staging(2))                 # delta 2, view planning
    return g


def test_delta_metadata_carries_view_and_round():
    g = _two_view_game()
    md = [d["_delta_metadata"] for d in g.deltas]
    assert [m["view"] for m in md] == ["resource", "planning", "planning"]
    assert all(m["round"] == g.round for m in md)


def test_delta_index_for_view_is_the_entry_delta_or_minus_one():
    g = _two_view_game()
    assert g.delta_index_for_view(g.round, "planning") == 1
    assert g.delta_index_for_view(g.round, "resource") == 0
    assert g.delta_index_for_view(g.round, "combat_shadow") == -1
    assert g.delta_index_for_view(g.round + 1, "planning") == -1


def test_an_edit_after_undo_drops_the_orphaned_rows_and_tombstones_them():
    g = _two_view_game()
    g.take_log_appends()                               # clear the queue
    orphan = [e for e in g.log if e.get("delta_i") == 2]
    assert orphan and orphan[0]["text"] == "Staging area threat 2"
    assert g.undo()                                    # back to delta 1
    _tap(g, lambda: g.set_willpower(3))                # truncates the future
    assert all(e.get("delta_i") != 2 or e["text"] != "Staging area threat 2"
               for e in g.log if "delta_i" in e and e["delta_i"] <= g.replay_step)
    assert not any(e["text"] == "Staging area threat 2" for e in g.log)
    ops = [r for r in g.take_log_appends() if r.get("op") == "lt"]
    assert len(ops) == 1
    assert ops[0]["lo"] == orphan[0]["seq"] == ops[0]["hi"]


def test_fold_log_applies_the_tombstone():
    rows = [{"seq": 1, "round": 1, "step": "1.1", "text": "a"},
            {"seq": 2, "round": 1, "step": "1.1", "text": "b"},
            {"seq": 3, "round": 1, "step": "1.1", "text": "c"},
            {"op": "lt", "lo": 2, "hi": 2},
            {"seq": 4, "round": 1, "step": "1.1", "text": "d"}]
    assert [e["text"] for e in fold_log(rows)] == ["a", "c", "d"]


def test_fold_reproduces_the_live_log_after_undo_and_edit():
    g = _two_view_game()
    appends = list(g.take_log_appends())
    g.undo()
    _tap(g, lambda: g.set_willpower(3))
    appends += g.take_log_appends()
    assert fold_log(appends) == g.log


def test_undo_alone_keeps_the_rows_and_writes_no_tombstone():
    g = _two_view_game()
    g.take_log_appends()
    g.undo()
    assert any(e["text"] == "Staging area threat 2" for e in g.log)
    assert not any(r.get("op") == "lt" for r in g.take_log_appends())


def test_a_fresh_tally_after_undo_never_coalesces_onto_an_orphaned_row():
    """logEvent/log_event coalesces a keyed tally onto the last log row when
    (key, round, step) match - but after an undo, the last row can be an
    ORPHANED row (its delta_i is in the discarded redo future). Rewriting an
    orphan in place used to mean a subsequent addDelta/add_delta truncation
    swallowed it, along with the only line the fresh action ever wrote:

        tap(set_staging(1))   # delta 0, row A (key stg)
        tap(set_willpower(5)) # delta 1, row B
        tap(set_staging(2))   # delta 2, row C (key stg)
        undo(); undo()        # replay_step -> 0
        tap(set_staging(9))   # used to coalesce onto row C, then get
                               # truncated along with it - the tap vanished

    log_event/logEvent must refuse to coalesce onto a row whose delta_i is
    past replay_step and start a fresh row instead."""
    gamestate.set_window_policy(gamestate.WINDOW_POLICY_BANDS)
    g = GameState(2)
    appends = []

    _tap(g, lambda: g.set_staging(1))                   # delta 0, row A (key stg)
    appends += g.take_log_appends()
    _tap(g, lambda: g.set_willpower(5))                 # delta 1, row B
    appends += g.take_log_appends()
    _tap(g, lambda: g.set_staging(2))                   # delta 2, row C (key stg)
    appends += g.take_log_appends()
    row_b_seq = next(e["seq"] for e in g.log
                      if e["text"] == "Players committed 5 willpower to the quest")
    row_c_seq = next(e["seq"] for e in g.log if e["text"] == "Staging area threat 2")

    assert g.undo() and g.undo()                        # replay_step -> 0
    appends += g.take_log_appends()                     # undo alone appends nothing

    _tap(g, lambda: g.set_staging(9))                   # fresh tally after undo
    new_appends = g.take_log_appends()
    appends += new_appends

    # The fresh tap gets its own row - it did not overwrite (and so did not
    # go down with) the orphaned row C.
    assert [e["text"] for e in g.log] == [
        "Staging area threat 1", "Staging area threat 9"]
    assert not any(e["seq"] == row_c_seq for e in g.log)
    new_row = next(r for r in new_appends if r.get("op") != "lt")
    assert new_row["text"] == "Staging area threat 9"
    assert new_row["delta_i"] == 1

    # Both orphaned rows (B and C - the whole discarded stretch) are
    # tombstoned in one contiguous range; the new row is untouched by it.
    tombstones = [r for r in new_appends if r.get("op") == "lt"]
    assert len(tombstones) == 1
    assert tombstones[0]["lo"] == row_b_seq
    assert tombstones[0]["hi"] == row_c_seq

    assert fold_log(appends) == g.log


def _drain(g):
    """The records the store would have written, frozen at drain time.

    db.py serializes each record as it leaves take_log_appends(); the live row
    dicts keep being edited afterwards (a later tally rewrites one, the front
    trim renumbers them all), so a test that kept references would be folding
    over history that had quietly rewritten itself. Freeze, and the fold has
    to earn its result from the ops.
    """
    return [json.loads(json.dumps(r)) for r in g.take_log_appends()]


def _tally_game(n=5):
    """`n` separate taps on the same stepper - one coalesced row, `n` deltas."""
    gamestate.set_window_policy(gamestate.WINDOW_POLICY_BANDS)
    g = GameState(2)
    appends = []
    for v in range(1, n + 1):
        _tap(g, lambda v=v: g.set_staging(v))
        appends += _drain(g)
    return g, appends


def test_a_coalesced_tally_row_belongs_to_the_tap_that_last_wrote_it():
    """Five taps on one stepper are one log row - and that row is the FIFTH
    tap's, not the first's. The coalesce path rewrites the row in place, so it
    has to join _action_entries too or add_delta's stamp loop never sees it:
    the row kept delta_i 0, so it stayed ungreyed until four undos, and a
    rewind to it landed on "staging 1" while the row said "staging 5"."""
    g, _ = _tally_game()
    rows = [e for e in g.log if e.get("key") == "stg"]
    assert len(rows) == 1 and rows[0]["text"] == "Staging area threat 5"
    assert rows[0]["delta_i"] == 4                  # the fifth tap, not the first

    assert g.undo() and g.undo() and g.undo()
    assert g.replay_step == 1 and g.staging == 2
    assert rows[0]["delta_i"] > g.replay_step       # greyed: it describes the future

    assert g.step_through({"size": "index", "index": rows[0]["delta_i"]})
    assert g.staging == 5                           # the row's own tap, not tap one


def test_fold_reproduces_the_live_log_across_the_coalesce_and_undo_corners():
    """Four walks that each put the restamped row and the truncation
    tombstone in a different order. The fold has no replay_step, so it
    coalesces where the live log_event would have refused - it comes out
    right anyway because `seq` is monotonic (see fold_log)."""
    # undo / edit / undo / edit
    g, appends = _tally_game(3)
    g.undo(); appends += _drain(g)
    _tap(g, lambda: g.set_willpower(3)); appends += _drain(g)
    g.undo(); appends += _drain(g)
    _tap(g, lambda: g.set_staging(8)); appends += _drain(g)
    assert fold_log(appends) == g.log

    # two undos, then a tally edit that lands on an orphaned tally row
    g, appends = _tally_game(3)
    g.undo(); g.undo(); appends += _drain(g)
    _tap(g, lambda: g.set_staging(9)); appends += _drain(g)
    assert fold_log(appends) == g.log

    # a tally run, an undo INTO it, then an edit
    g, appends = _tally_game(5)
    _tap(g, lambda: g.set_willpower(2)); appends += _drain(g)
    g.undo(); g.undo(); appends += _drain(g)
    _tap(g, lambda: g.set_staging(7)); appends += _drain(g)
    assert fold_log(appends) == g.log

    # all the way back to -1, then an edit
    g, appends = _tally_game(3)
    while g.undo():
        pass
    assert g.replay_step == -1
    appends += _drain(g)
    _tap(g, lambda: g.set_staging(6)); appends += _drain(g)
    assert fold_log(appends) == g.log


def test_the_front_trim_shifts_delta_i_in_the_store_too():
    """MAX_SAVED_DELTAS taps and one more. The trim drops the oldest delta and
    renumbers every row's delta_i in RAM; the store hears about it as
    {"op":"lx","n":drop}, or a resumed game comes back with every row pointing
    one delta too high - a rewind target off by one, for good."""
    gamestate.set_window_policy(gamestate.WINDOW_POLICY_BANDS)
    g = GameState(2)
    appends = []
    for i in range(gamestate.MAX_SAVED_DELTAS + 1):
        # Alternate two steppers so no tap coalesces onto the previous row:
        # one row per delta is what makes the shift visible.
        _tap(g, (lambda i=i: g.set_staging(i % 9 + 1)) if i % 2
                else (lambda i=i: g.set_willpower(i % 9 + 1)))
        appends += _drain(g)

    trims = [r for r in appends if r.get("op") == "lx"]
    assert len(trims) == 1 and trims[0]["n"] == 1
    assert len(g.deltas) == gamestate.MAX_SAVED_DELTAS
    stamped = [e["delta_i"] for e in g.log if "delta_i" in e]
    assert stamped[0] == -1                 # the dropped delta: no longer a target
    assert stamped[-1] == g.replay_step == gamestate.MAX_SAVED_DELTAS - 1
    assert fold_log(appends) == g.log


def test_take_log_appends_hands_out_frozen_rows():
    """take_log_appends() must hand out copies, not the live row dicts.

    db.py's Session.record() calls take_log_appends() on every tap and queues
    whatever it returns; the durable write only serializes that queue later,
    in tick(). Two things mutate a row IN PLACE after it has already been
    handed out: a keyed-tally coalesce rewrites text/seq/t on the same dict
    (log_event), and the MAX_SAVED_DELTAS front trim decrements delta_i on
    every row still live (covered by the next test). A queued reference would
    silently pick up either edit; a queued copy can't."""
    gamestate.set_window_policy(gamestate.WINDOW_POLICY_BANDS)
    g = GameState(2)
    _tap(g, lambda: g.set_staging(1))                   # delta 0, keyed row
    taken = g.take_log_appends()
    assert len(taken) == 1
    assert taken[0]["text"] == "Staging area threat 1"

    # Mutate the live row directly.
    g.log[-1]["text"] = "changed"
    assert taken[0]["text"] == "Staging area threat 1"

    # Re-tally onto the same (key, round, step) - log_event's coalesce path
    # rewrites the live dict in place rather than appending a new one.
    _tap(g, lambda: g.set_staging(2))
    g.take_log_appends()
    assert taken[0]["text"] == "Staging area threat 1"  # still untouched


def test_front_trim_never_shifts_a_queued_row_twice():
    """A row already handed to the durability queue must not be shifted
    twice when the MAX_SAVED_DELTAS front trim lands on a later tap.

    This mirrors db.py's Session.record(): every tap extracts its rows via
    take_log_appends() immediately, but the queue is only SERIALIZED later,
    in tick() - so a row can sit "in flight", still referenced, across many
    more taps, including the one that triggers the trim. The trim shifts
    every LIVE row's delta_i down by `drop` directly (gamestate.py, add_delta)
    and separately journals {"op": "lx", "n": drop} for fold_log to replay
    against whatever is already durable. If take_log_appends() hands out the
    live dict instead of a copy, a row still in the queue gets the direct
    shift AND the replayed "lx" shift - double-counted - the exact hazard
    take_log_appends()'s copy fixes.

    Confirmed to fail on pre-fix code (took_log_appends returning the live
    dicts): folded delta_i came back -2 where the live row's is -1.
    """
    gamestate.set_window_policy(gamestate.WINDOW_POLICY_BANDS)
    g = GameState(2)
    taken = []  # stand-in for db.py's Session._queue, never drained/ticked
    for i in range(gamestate.MAX_SAVED_DELTAS + 1):
        # Alternate two steppers so no tap coalesces onto the previous row.
        _tap(g, (lambda i=i: g.set_staging(i % 9 + 1)) if i % 2
                else (lambda i=i: g.set_willpower(i % 9 + 1)))
        taken += g.take_log_appends()          # extracted every tap, like record()

    assert any(r.get("op") == "lx" for r in taken)
    assert fold_log(taken) == g.log
