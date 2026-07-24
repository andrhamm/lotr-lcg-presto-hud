import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import quest_catalog as qc

# Small in-memory index.scenarios[] slice: two official Core Set quests (out
# of alpha order, to exercise the within-cycle name sort), one official
# Shadows of Mirkwood quest (with a releaseDate, to exercise group date), one
# official nightmare deck (must be excluded from both sources), one ALeP
# quest (must appear only under source="alep"). All quest entries have
# stageCount > 0; encounter/campaign entries (if present) have stageCount <= 0.
SCENARIOS = [
    {"slug": "passage-through-mirkwood", "name": "Passage Through Mirkwood",
     "cycle": "Core Set", "source": "official", "kind": "quest", "stageCount": 3, "releaseDate": None},
    {"slug": "conflict-at-the-carrock", "name": "Conflict at the Carrock",
     "cycle": "Core Set", "source": "official", "kind": "quest", "stageCount": 3, "releaseDate": None},
    {"slug": "a-journey-to-rhosgobel", "name": "A Journey to Rhosgobel",
     "cycle": "Shadows of Mirkwood", "source": "official", "kind": "quest", "stageCount": 2,
     "releaseDate": "2012-01"},
    {"slug": "passage-through-mirkwood-nightmare", "name": "Passage Through Mirkwood",
     "cycle": "Core Set", "source": "official", "kind": "nightmare", "stageCount": 3, "releaseDate": None},
    {"slug": "some-alep-quest", "name": "Some ALeP Quest",
     "cycle": "Oaths of the Rohirrim", "source": "alep", "kind": "quest", "stageCount": 4,
     "releaseDate": None},
]


def test_cycle_order_constant():
    # Pin the exact order agreed in the plan (progress.md / Task 2 findings),
    # including the "Ered Mithrin" addition and the "Other" catch-all tail.
    assert qc.CYCLE_ORDER == [
        "Core Set", "Shadows of Mirkwood", "The Dwarrowdelf", "Against the Shadow",
        "The Ring-maker", "The Angmar Awakened", "The Dream-chaser", "The Haradrim",
        "Ered Mithrin", "The Vengeance of Mordor", "Hobbit Saga", "LotR Saga",
        "Standalone/PoD", "Other",
    ]


def test_group_by_cycle_excludes_nightmare():
    groups = qc.group_by_cycle(SCENARIOS, "official")
    slugs = [s["slug"] for g in groups for s in g["scenarios"]]
    assert "passage-through-mirkwood-nightmare" not in slugs
    # the non-nightmare sibling with the same name IS present
    assert "passage-through-mirkwood" in slugs


def test_group_by_cycle_alep_only_under_alep_source():
    official = qc.group_by_cycle(SCENARIOS, "official")
    official_slugs = [s["slug"] for g in official for s in g["scenarios"]]
    assert "some-alep-quest" not in official_slugs

    alep = qc.group_by_cycle(SCENARIOS, "alep")
    alep_slugs = [s["slug"] for g in alep for s in g["scenarios"]]
    assert alep_slugs == ["some-alep-quest"]


def test_group_by_cycle_order_follows_cycle_order():
    groups = qc.group_by_cycle(SCENARIOS, "official")
    # Core Set precedes Shadows of Mirkwood in CYCLE_ORDER, regardless of
    # input list order (input above lists Mirkwood's quest first).
    assert [g["cycle"] for g in groups] == ["Core Set", "Shadows of Mirkwood"]


def test_group_by_cycle_sorts_scenarios_by_name_within_group():
    groups = qc.group_by_cycle(SCENARIOS, "official")
    core = next(g for g in groups if g["cycle"] == "Core Set")
    assert [s["name"] for s in core["scenarios"]] == [
        "Conflict at the Carrock", "Passage Through Mirkwood",
    ]


def test_group_by_cycle_date_is_earliest_non_null_release_date():
    groups = qc.group_by_cycle(SCENARIOS, "official")
    core = next(g for g in groups if g["cycle"] == "Core Set")
    assert core["date"] is None  # both Core Set entries have a null releaseDate
    mirkwood = next(g for g in groups if g["cycle"] == "Shadows of Mirkwood")
    assert mirkwood["date"] == "2012-01"


def test_group_by_cycle_unrecognized_cycle_sorts_before_other():
    scns = SCENARIOS + [
        {"slug": "future-quest", "name": "Future Quest", "cycle": "Some Future Cycle",
         "source": "official", "kind": "quest", "stageCount": 2, "releaseDate": None},
        {"slug": "other-quest", "name": "Other Quest", "cycle": "Other",
         "source": "official", "kind": "quest", "stageCount": 2, "releaseDate": None},
    ]
    groups = qc.group_by_cycle(scns, "official")
    cycles = [g["cycle"] for g in groups]
    assert cycles[-1] == "Other"
    assert cycles.index("Some Future Cycle") < cycles.index("Other")


def test_cycles_for_counts_and_shape():
    index = {"scenarios": SCENARIOS}
    assert qc.cycles_for(index, "official") == [
        {"cycle": "Core Set", "date": None, "count": 2},
        {"cycle": "Shadows of Mirkwood", "date": "2012-01", "count": 1},
    ]


def test_cycles_for_alep():
    index = {"scenarios": SCENARIOS}
    assert qc.cycles_for(index, "alep") == [
        {"cycle": "Oaths of the Rohirrim", "date": None, "count": 1},
    ]


def test_non_quest_sets_excluded():
    """Encounter and campaign sets with stageCount <= 0 must be excluded."""
    scns = [
        {"slug": "real", "name": "Real Quest", "cycle": "Core Set",
         "source": "official", "kind": "quest", "stageCount": 3, "releaseDate": None},
        {"slug": "enc", "name": "Shared Encounter Set", "cycle": "Core Set",
         "source": "official", "kind": "encounter", "stageCount": 0, "releaseDate": None},
        {"slug": "camp", "name": "Campaign Set", "cycle": "Core Set",
         "source": "official", "kind": "campaign", "stageCount": 0, "releaseDate": None},
    ]
    groups = qc.group_by_cycle(scns, "official")
    names = [s["name"] for g in groups for s in g["scenarios"]]
    assert names == ["Real Quest"]
    # Verify cycles_for also reflects the correct count (only 1, not 3)
    index = {"scenarios": scns}
    cycles = qc.cycles_for(index, "official")
    assert cycles == [{"cycle": "Core Set", "date": None, "count": 1}]
