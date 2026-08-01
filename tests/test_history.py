"""The history collection: append-once records plus an O(1) rolling aggregate.

Append is O(1) forever (~63 ms regardless of how many games are stored), but
reading them ALL is not - 4000 games took 15.9 s on device, and a second sort
over them took 50 s once ~875 KB was live and GC began thrashing. So the stats
screens must read the rollup, and the rollup must be maintained incrementally.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import db as dbmod  # noqa: E402
from gamestate import GameState  # noqa: E402


@pytest.fixture
def hist(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "HISTORY_PATH", str(tmp_path / "history.bin"))
    monkeypatch.setattr(dbmod, "ROLLUP_PATH", str(tmp_path / "stats.json"))
    return dbmod.History()


def _rec(i, won=True, rounds=8, scn="the-oath"):
    return {"scn": scn, "name": "The Oath", "players": 2, "won": won,
            "rounds": rounds, "duration": 1000 * i, "threats": [30, 31],
            "eliminated": 0}


def test_an_empty_store_reports_an_empty_rollup(hist):
    assert hist.scan() == []
    assert hist.rollup()["games"] == 0


def test_records_append_and_read_back_in_order(hist):
    for i in range(5):
        hist.append(_rec(i))
    got = hist.scan()
    assert len(got) == 5
    assert [g["duration"] for g in got] == [0, 1000, 2000, 3000, 4000]


def test_the_rollup_is_maintained_incrementally(hist):
    hist.append(_rec(1, won=True, rounds=8))
    hist.append(_rec(2, won=False, rounds=12))
    hist.append(_rec(3, won=True, rounds=6, scn="passage-through-mirkwood"))
    r = hist.rollup()
    assert r["games"] == 3
    assert r["wins"] == 2
    assert r["rounds"] == 26
    assert r["by_scenario"]["the-oath"] == {"played": 2, "won": 1}
    assert r["by_scenario"]["passage-through-mirkwood"] == {"played": 1, "won": 1}


def test_best_tracks_the_fastest_win_only(hist):
    hist.append(_rec(1, won=True, rounds=9))
    hist.append(_rec(2, won=False, rounds=2))     # a fast LOSS is not a best
    assert hist.rollup()["best"]["rounds"] == 9
    hist.append(_rec(3, won=True, rounds=5))
    assert hist.rollup()["best"]["rounds"] == 5


def test_the_rollup_answers_without_scanning(hist):
    """The whole point: stats never depend on reading every game back."""
    for i in range(50):
        hist.append(_rec(i, won=(i % 3 != 0)))
    r = hist.rollup()
    assert r["games"] == 50
    # agrees with the expensive path it exists to avoid
    scanned = hist.scan()
    assert r["games"] == len(scanned)
    assert r["wins"] == sum(1 for g in scanned if g["won"])


def test_clear_removes_records_and_rollup(hist):
    hist.append(_rec(1))
    hist.clear()
    assert hist.scan() == []
    assert hist.rollup()["games"] == 0


def test_history_record_summarises_a_finished_game():
    g = GameState(2, 25)
    g.clock = lambda: 0
    g.scenario = {"slug": "the-oath", "name": "The Oath", "mode": "Nightmare",
                  "source": "official"}
    g.round = 9
    g.set_game_over("victory")
    rec = g.history_record()
    assert rec["scn"] == "the-oath"
    assert rec["mode"] == "Nightmare"
    assert rec["won"] is True
    assert rec["rounds"] == 9
    assert rec["players"] == 2


def test_a_defeat_is_recorded_as_not_won():
    g = GameState(2, 25)
    g.clock = lambda: 0
    g.scenario = {"slug": "the-oath"}
    g.set_game_over("defeat")
    assert g.history_record()["won"] is False


def test_the_record_is_small_enough_to_append_forever():
    """~220 B is what makes one append per game free regardless of history."""
    import json
    g = GameState(4, 25)
    g.clock = lambda: 0
    g.scenario = {"slug": "the-battle-of-carn-dum", "name": "The Battle of Carn Dum",
                  "mode": "Nightmare", "source": "official"}
    g.set_game_over("victory")
    assert len(json.dumps(g.history_record())) < 400
