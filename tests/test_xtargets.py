"""What a printed X counts, as an enum rather than a sentence to re-parse.

The gate here is the LAST line of these tests: every coded X in both committed
distillations must name a target this table knows. An unknown target would draw
a stepper with no label, and there is no runtime parser to fall back on - which
is the point.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xtargets as X

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTIFACTS = (
    (os.path.join(ROOT, "tools", "data", "location_dynamic_distilled.json"),
     ("quest_points", "threat")),
    (os.path.join(ROOT, "tools", "data", "advancement_distilled.json"),
     ("quest_points",)),
)


def _coded():
    """Every coded X across both artifacts, as (key, field, spec)."""
    out = []
    for path, fields in ARTIFACTS:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for key, entry in data.items():
            for field in fields:
                v = entry.get(field)
                if isinstance(v, dict):
                    out.append((key, field, v))
    return out


def test_value_is_mul_times_count_plus_add():
    # The four observed shapes, and the only arithmetic there is: a bare count,
    # "1 more than", "twice", and "2, plus 2 for each".
    assert X.value_of(4) == 4
    assert X.value_of(3, 1, 1) == 4
    assert X.value_of(3, 2, 0) == 6
    assert X.value_of(3, 2, 2) == 8


def test_value_never_goes_negative():
    assert X.value_of(0, 1, -5) == 0


def test_auto_targets_ignore_the_supplied_count():
    # The whole reason these three are tagged separately: "X is 4 per player"
    # has to follow the player count without anyone touching a stepper, so a
    # stale count must not be able to override it.
    assert X.resolve({"target": "players", "mul": 4}, count=99, players=3) == 12
    assert X.resolve({"target": "stage_number", "add": 1}, count=99, stage=2) == 3
    assert X.resolve({"target": "highest_threat"}, count=99,
                     highest_threat=31) == 31


def test_a_player_target_needs_a_count_first():
    # nazgul_in_play is a subset of enemies_in_play the tracker doesn't
    # break out, so it stays player-supplied.
    spec = {"target": "nazgul_in_play", "add": 1}
    assert X.resolve(spec) is None          # nothing on screen yet
    assert X.resolve(spec, count=3) == 4


def test_resolve_is_none_for_no_spec():
    assert X.resolve(None, count=3) is None


def test_every_target_has_a_label():
    for name, t in X.TARGETS.items():
        assert t["label"], name
        # The label names the thing to COUNT, not the stat being computed - the
        # row already says "Threat". So it must not restate one.
        assert not t["label"].lower().startswith(("threat", "quest points")), name


def test_only_tracked_values_are_auto():
    # Five, and only five: what the HUD actually models. Anything else marked
    # auto would silently invent a number.
    autos = {n for n, t in X.TARGETS.items() if t["auto"]}
    assert autos == {"players", "stage_number", "highest_threat",
                     "enemies_in_play", "locations_in_staging"}


def test_enemies_and_staging_locations_are_answered_by_the_tracker():
    # The two counts the tablet tracks. Like the other auto targets, a stale
    # supplied count must not override the tracked value.
    assert X.auto_for("enemies_in_play") == X.AUTO_ENEMIES
    assert X.auto_for("locations_in_staging") == X.AUTO_STAGING_LOCATIONS
    assert X.resolve({"target": "enemies_in_play"}, count=99, enemies=3) == 3
    assert X.resolve({"target": "enemies_in_play", "mul": 2, "add": 1},
                     count=99, enemies=3) == 7
    assert X.resolve({"target": "locations_in_staging"}, count=99,
                     staging_locations=2) == 2


def test_the_auto_set_is_exactly_the_five_tracked_values():
    auto = sorted(k for k, t in X.TARGETS.items() if t["auto"])
    assert auto == ["enemies_in_play", "highest_threat", "locations_in_staging",
                    "players", "stage_number"]


@pytest.mark.parametrize("key,field,spec", _coded())
def test_every_coded_formula_names_a_known_target(key, field, spec):
    assert spec.get("target") in X.TARGETS, (key, field, spec.get("target"))
    assert spec.get("text"), (key, field)
    for k in ("mul", "add"):
        if k in spec:
            assert isinstance(spec[k], int), (key, field, k)


def test_the_artifacts_are_fully_coded():
    # No formula may still be a bare string: a sentence is only good for
    # showing, and anything left unconverted would silently lose its control.
    for path, fields in ARTIFACTS:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for key, entry in data.items():
            for field in fields:
                v = entry.get(field)
                assert not isinstance(v, str), (path, key, field, v)
    assert len(_coded()) == 54
