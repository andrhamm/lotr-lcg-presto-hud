"""The counts the tablet tracks: enemies engaged with each player, enemies
and locations in the staging area. Simple steppers on the tablet; the Presto
draws none of them. They feed skip offers and printed-X targets, and a later
computer-vision pass may fill the same fields."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gamestate import GameState


def _live():
    g = GameState(2, 25)
    g.advance_view()          # past setup, into round 1
    return g


def test_counts_default_to_zero():
    g = GameState(2, 25)
    assert [p.engaged for p in g.players] == [0, 0]
    assert g.staging_enemies == 0
    assert g.staging_locations == 0


def test_counts_round_trip_through_a_save():
    g = _live()
    g.set_engaged(1, 2)
    g.set_staging_enemies(1)
    g.set_staging_locations(3)
    r = GameState.from_dict(g.to_dict())
    assert r.players[1].engaged == 2
    assert r.players[0].engaged == 0
    assert r.staging_enemies == 1
    assert r.staging_locations == 3


def test_a_save_without_the_fields_still_loads():
    d = GameState(2, 25).to_dict()
    for pd in d["players"]:
        del pd["engaged"]
    del d["staging_enemies"]
    del d["staging_locations"]
    r = GameState.from_dict(d)
    assert r.players[0].engaged == 0
    assert r.staging_enemies == 0
    assert r.staging_locations == 0


def test_setters_clamp_at_zero():
    g = _live()
    assert g.set_engaged(0, -4) == 0
    assert g.set_staging_enemies(-1) == 0
    assert g.set_staging_locations(-1) == 0


def test_a_run_of_stepper_taps_is_one_log_row():
    g = _live()
    n = len(g.log)
    g.set_engaged(0, 1)
    g.set_engaged(0, 2)
    g.set_engaged(0, 3)
    assert g.players[0].engaged == 3
    assert len(g.log) == n + 1, "keyed tally rewrites the row"
    assert g.log[-1]["text"] == "P1 engaged enemies 3"
    g.set_staging_enemies(2)
    assert g.log[-1]["text"] == "Staging enemies 2"
    g.set_staging_locations(1)
    assert g.log[-1]["text"] == "Staging locations 1"


def test_setting_the_same_value_logs_nothing():
    g = _live()
    n = len(g.log)
    g.set_engaged(0, 0)
    g.set_staging_enemies(0)
    assert len(g.log) == n


def test_totals():
    g = _live()
    g.set_engaged(0, 2)
    g.set_engaged(1, 1)
    g.set_staging_enemies(1)
    assert g.engaged_total() == 3
    assert g.enemies_in_play() == 4


def test_the_counts_are_in_the_replay_snapshot():
    g = _live()
    g.set_engaged(1, 2)
    g.set_staging_enemies(1)
    g.set_staging_locations(2)
    s = g.snapshot()
    assert s["players"]["1"]["engaged"] == 2
    assert s["staging_enemies"] == 1
    assert s["staging_locations"] == 2


def test_a_snapshot_without_the_counts_loads_as_zero():
    g = _live()
    g.set_engaged(1, 2)
    s = g.snapshot()
    del s["players"]["1"]["engaged"]
    del s["staging_enemies"]
    del s["staging_locations"]
    g.load_snapshot(s)
    assert g.players[1].engaged == 0
    assert g.staging_enemies == 0
    assert g.staging_locations == 0


def test_undo_restores_the_counts():
    g = _live()
    before = g.begin_action()
    g.set_engaged(0, 2)
    g.set_staging_enemies(1)
    g.set_staging_locations(1)
    g.add_delta(before)
    g.undo()
    assert g.players[0].engaged == 0
    assert g.staging_enemies == 0
    assert g.staging_locations == 0


def test_x_context_feeds_resolve_with_the_tracked_values():
    import gamestate
    import xtargets
    gamestate.set_board_tracking(True)
    g = _live()
    g.set_engaged(0, 2)
    g.set_staging_enemies(1)
    g.set_staging_locations(2)
    ctx = g.x_context()
    assert ctx == {"players": 2, "stage": g.quest["stage_n"],
                   "highest_threat": max(p.threat for p in g.players),
                   "enemies": 3, "staging_locations": 2}
    assert xtargets.resolve({"target": "enemies_in_play"}, **ctx) == 3
    assert xtargets.resolve({"target": "players", "mul": 4}, count=None, **ctx) == 8


def test_x_context_omits_the_counts_until_the_client_tracks_them():
    # The Presto never calls set_board_tracking, so its x_context must not
    # carry a tracked value a device that doesn't track the board can't
    # actually answer for - the player supplies the count as before.
    import xtargets
    g = _live()
    ctx = g.x_context()
    assert set(ctx) == {"players", "stage", "highest_threat"}
    assert xtargets.resolve({"target": "enemies_in_play"}, count=3, **ctx) == 3
