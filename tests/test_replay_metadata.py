"""A delta remembers the view and round it landed on, and truncating the redo
future truncates the log rows it orphaned (with a tombstone the fold applies).
Both twins."""
import json, os, shutil, subprocess, sys, tempfile
import pytest
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
