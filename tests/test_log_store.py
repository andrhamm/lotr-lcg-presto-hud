"""The game log's append-only store: the fold must reproduce game.log exactly.

The log moved out of state.json (it was 96% of a save rewritten on every tap)
into a store that records log EVENTS. Because log_event coalesces a keyed
tally by rewriting its own row in place, replaying those events has to apply
the identical rule or a run of eight stepper taps comes back as eight rows.

Nothing asserted the log's persistence round-trip before this file existed.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gamestate import GameState, fold_log  # noqa: E402


def _game():
    g = GameState(2, 25)
    g.clock = lambda: 0
    return g


def _drain(g):
    """What the store would have appended, then folded back."""
    return fold_log(g.take_log_appends())


def test_fold_reproduces_a_plain_append_run():
    g = _game()
    g.log_event("one")
    g.log_event("two")
    g.log_event("three")
    assert [e["text"] for e in _drain(g)] == ["one", "two", "three"]
    assert [e["text"] for e in g.log] == ["one", "two", "three"]


def test_a_keyed_run_folds_to_one_row_like_log_event_does():
    g = _game()
    for n in range(1, 9):
        g.log_event("Players committed %d willpower" % n, cat="tally", key="wp")
    # log_event coalesced in memory...
    assert len(g.log) == 1
    assert g.log[0]["text"] == "Players committed 8 willpower"
    # ...and the fold must agree, from 8 recorded events.
    folded = _drain(g)
    assert len(folded) == 1
    assert folded[0]["text"] == "Players committed 8 willpower"


def test_reopening_a_stepper_later_starts_a_new_row():
    """Coalescing is bounded by (key, round, step) on purpose - when each
    change happened is the point of a log."""
    g = _game()
    g.log_event("committed 3", cat="tally", key="wp")
    g.step = "4.2"                       # a different step
    g.log_event("committed 5", cat="tally", key="wp")
    assert len(g.log) == 2
    assert len(_drain(g)) == 2


def test_an_unkeyed_row_between_two_keyed_ones_breaks_the_run():
    g = _game()
    g.log_event("committed 1", cat="tally", key="wp")
    g.log_event("something else happened")
    g.log_event("committed 2", cat="tally", key="wp")
    assert [e["text"] for e in g.log] == [
        "committed 1", "something else happened", "committed 2"]
    assert [e["text"] for e in _drain(g)] == [e["text"] for e in g.log]


def test_fold_matches_game_log_over_a_mixed_session():
    """The real invariant: fold(events) == game.log, whatever was logged."""
    g = _game()
    events = []
    for rnd in range(1, 4):
        g.round = rnd
        g.log_event("Round %d begins" % rnd, cat="phase")
        for n in range(1, 6):
            g.log_event("threat %d" % n, cat="tally", key="threat")
        g.log_event("Travelled somewhere")
        for n in range(1, 4):
            g.log_event("staging %d" % n, cat="tally", key="stg")
        events.extend([])
    folded = fold_log(g.take_log_appends())
    assert len(folded) == len(g.log)
    for a, b in zip(folded, g.log):
        assert a["text"] == b["text"]
        assert a["seq"] == b["seq"]
        assert a.get("cat") == b.get("cat")
        assert a.get("key") == b.get("key")


def test_state_no_longer_carries_the_log():
    """It is 96% of the save and rewritten on every tap - that is the point."""
    g = _game()
    for n in range(50):
        g.log_event("entry %d" % n)
    assert "log" not in g.to_dict()


def test_from_dict_still_loads_a_pre_split_save():
    """Saves written before the split embed `log`; loading one must keep it."""
    g = _game()
    g.log_event("historic entry")
    d = g.to_dict()
    d["log"] = [dict(e) for e in g.log]      # what an old save looked like
    back = GameState.from_dict(d)
    assert [e["text"] for e in back.log] == ["historic entry"]


def test_from_dict_tolerates_a_save_with_neither_log_nor_seq():
    """seq used to be a bare subscript here and raised KeyError on the device
    while the web twin's `?? 0` sailed through - one of the latent twin
    divergences. Both are tolerant now."""
    g = _game()
    d = g.to_dict()
    d.pop("seq", None)
    back = GameState.from_dict(d)
    assert back.log == []
    assert back._seq == 0


def test_take_log_appends_clears_so_a_tap_writes_only_its_own_rows():
    g = _game()
    g.log_event("first")
    assert len(g.take_log_appends()) == 1
    assert g.take_log_appends() == []
    g.log_event("second")
    assert [e["text"] for e in g.take_log_appends()] == ["second"]
