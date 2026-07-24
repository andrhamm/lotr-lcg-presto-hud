"""Quest catalog: cycle/source grouping over the M4-A card-data index, for
the quest-picker screens (Pick Cycle / Choose Scenario) — M4-B, Task 3.

`group_by_cycle`/`cycles_for` are pure and host-tested (tests/test_quest_
catalog.py). `load_index`/`load_scenario` are thin flash-read wrappers and
are NOT host-tested — there is no /data/ directory on the dev host, only on
the device flash filesystem (see docs/js/quest_catalog.js for the web twin,
which fetches the same paths relative to the Pages root instead).
"""

import json

# Verified product/cycle order (see docs/superpowers/plans/
# 2026-07-24-quest-picker-bcore.md Task-2 findings — includes the "Ered
# Mithrin" cycle the original brief omitted). Cycle names not in this list
# sort immediately before "Other" (see _cycle_rank) rather than raising.
CYCLE_ORDER = [
    "Core Set", "Shadows of Mirkwood", "The Dwarrowdelf", "Against the Shadow",
    "The Ring-maker", "The Angmar Awakened", "The Dream-chaser", "The Haradrim",
    "Ered Mithrin", "The Vengeance of Mordor", "Hobbit Saga", "LotR Saga",
    "Standalone/PoD", "Other",
]

INDEX_PATH = "/data/index.json"
SCENARIO_PATH = "/data/scenarios/%s.json"


def _cycle_rank(cycle):
    """Sort key: CYCLE_ORDER position. A cycle name absent from the list
    (shouldn't happen given build_card_data.py's own "Other" fallback, but
    kept defensive) ranks just before "Other" rather than falling off the
    end or raising."""
    if cycle in CYCLE_ORDER:
        return CYCLE_ORDER.index(cycle)
    return CYCLE_ORDER.index("Other") - 0.5


def _earliest_date(scenarios):
    """The group's display date: the earliest non-null releaseDate among its
    scenarios (YYYY-MM strings sort lexicographically = chronologically), or
    None if every scenario's releaseDate is null (true for all scenarios as
    of Task 2 — B-data is expected to fill these in)."""
    dates = [s["releaseDate"] for s in scenarios if s.get("releaseDate")]
    return min(dates) if dates else None


def group_by_cycle(scenarios, source):
    """Group `scenarios` (index.json `scenarios[]` entries) by cycle for one
    picker source ("official"/"alep"), for the Pick Cycle / Choose Scenario
    screens.

    - Keeps only playable quests (stageCount > 0), excluding `kind=="nightmare"`
      and non-quest sets (encounter, campaign).
    - Groups ordered by CYCLE_ORDER (stable: ties keep first-seen order).
    - Scenarios within a group ordered by `name`.

    Returns [{"cycle": str, "date": str|None, "scenarios": [entry, ...]}].
    """
    groups = {}
    for scn in scenarios:
        if (scn.get("source") != source or scn.get("kind") == "nightmare"
                or scn.get("stageCount", 0) <= 0):
            continue
        groups.setdefault(scn.get("cycle", "Other"), []).append(scn)

    out = []
    for cycle in sorted(groups, key=_cycle_rank):
        scns = sorted(groups[cycle], key=lambda s: s.get("name", ""))
        out.append({"cycle": cycle, "date": _earliest_date(scns), "scenarios": scns})
    return out


def cycles_for(index, source):
    """[{"cycle", "date", "count"}] for the Pick Cycle screen — same
    filtering/order as group_by_cycle, over a whole loaded index.json dict
    (as returned by load_index())."""
    groups = group_by_cycle(index.get("scenarios", []), source)
    return [{"cycle": g["cycle"], "date": g["date"], "count": len(g["scenarios"])}
            for g in groups]


def load_index():
    """Read the whole catalog index from flash. Thin wrapper, not host-tested."""
    with open(INDEX_PATH) as f:
        return json.load(f)


def load_scenario(slug):
    """Read one scenario's full stage/card data from flash. Thin wrapper,
    not host-tested."""
    with open(SCENARIO_PATH % slug) as f:
        return json.load(f)
