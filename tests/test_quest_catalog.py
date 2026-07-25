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


def test_nightmare_named_variants_excluded():
    """Some Nightmare decks ship replacement quest cards, so their sets land as
    kind=="quest". They must still stay out of the picker (Mode toggle only)."""
    scns = [
        {"slug": "base", "name": "Conflict at the Carrock", "cycle": "Shadows of Mirkwood",
         "source": "official", "kind": "quest", "stageCount": 3, "releaseDate": None},
        {"slug": "nm", "name": "Conflict at the Carrock - Nightmare",
         "cycle": "Shadows of Mirkwood", "source": "official", "kind": "quest",
         "stageCount": 1, "releaseDate": None},
    ]
    groups = qc.group_by_cycle(scns, "official")
    names = [s["name"] for g in groups for s in g["scenarios"]]
    assert names == ["Conflict at the Carrock"]


# Side-quest picker (M4-B sidequest, Task 1) - two packs' worth of player
# cards["sideQuest"] plus a pack with no side quests at all (must not raise).
# "Protect the Innocent" has a null questPoints on its only face (variable
# "X" quest, matches the real Angmar Awakened Campaign Expansion data) to
# exercise the null -> 0 default.
SQ_PACKS = [
    {"pack": "The Lost Realm", "cards": {"sideQuest": [
        {"id": "a", "name": "Gather Information", "sphere": "Neutral", "traits": "",
         "faces": [{"side": "", "questPoints": 4, "text": "..."}]}]}},
    {"pack": "Angmar Awakened Campaign Expansion", "cards": {"sideQuest": [
        {"id": "b", "name": "Protect the Innocent", "sphere": None, "traits": "",
         "faces": [{"side": "", "questPoints": None, "text": "..."}]},
        {"id": "c", "name": "Fend Off Despair", "sphere": None, "traits": "",
         "faces": [{"side": "", "questPoints": 8, "text": "..."}]}]}},
    {"pack": "Empty Pack", "cards": {"hero": [{"id": "h", "name": "Aragorn", "faces": []}]}},
]


def test_side_quests_flattens_sorts_and_defaults_null_points():
    out = qc.side_quests(SQ_PACKS)
    assert [s["name"] for s in out] == ["Fend Off Despair", "Gather Information",
                                        "Protect the Innocent"]
    assert [s["points"] for s in out] == [8, 4, 0]      # null -> 0
    assert out[1]["pack"] == "The Lost Realm"
    assert out[1]["sphere"] == "Neutral"


def test_side_quests_handles_packs_without_side_quests():
    assert qc.side_quests([{"pack": "x", "cards": {}}]) == []


def test_side_quests_accepts_dict_of_packs():
    # player_db may be a dict keyed by slug instead of a bare list - both
    # shapes flatten the same way.
    out = qc.side_quests({"lost-realm": SQ_PACKS[0], "angmar": SQ_PACKS[1]})
    assert [s["name"] for s in out] == ["Fend Off Despair", "Gather Information",
                                        "Protect the Innocent"]


# Icon matcher (M4-B icons, Task 2) - maps a catalog encounterSet slug to a
# rasterized mask from docs/data/icons.json via quest_catalog.load_icons().
ICONS = {"passage-through-mirkwood": [1] * 24, "stewards-fear": [2] * 24}


def test_icon_for_exact_and_nightmare_fallback():
    assert qc.icon_for("passage-through-mirkwood", ICONS) == [1] * 24
    assert qc.icon_for("passage-through-mirkwood-nightmare", ICONS) == [1] * 24


def test_icon_for_possessive_normalization():
    assert qc.icon_for("the-steward-s-fear", ICONS) == [2] * 24


def test_icon_for_unknown_returns_none():
    assert qc.icon_for("no-such-set", ICONS) is None


def test_icon_for_normalizes_both_sides():
    # Neither side is a raw match: the catalog slug keeps "the-", the icon
    # key doesn't (or vice versa) - only matches once BOTH are normalized.
    icons = {"the-lost-realm": [3] * 24}
    assert qc.icon_for("lost-realm", icons) == [3] * 24


def test_icon_for_never_raises_on_empty_inputs():
    assert qc.icon_for("", ICONS) is None
    assert qc.icon_for("passage-through-mirkwood", {}) is None
    assert qc.icon_for(None, ICONS) is None


def test_normalize_icon_key_collapses_repeated_hyphens():
    assert qc.normalize_icon_key("shadows--of--mirkwood") == "shadows-of-mirkwood"


def test_normalize_icon_key_is_idempotent_on_already_normalized_input():
    assert qc.normalize_icon_key("stewards-fear") == "stewards-fear"


# slugify() turns a display name (e.g. a gather-row label) into the same
# slug shape tools/build_card_data.py's own slugify() would have produced
# for it - mirrored here (not imported: tools/ is host-only build tooling,
# quest_catalog.py ships to the device/browser runtime) so ScenarioOptions
# Screen can look up an icon for a set it only has a name for.
def test_slugify_matches_build_card_data_convention():
    assert qc.slugify("Passage Through Mirkwood") == "passage-through-mirkwood"
    # the exact apostrophe -> "-s-" shape normalize_icon_key expects
    assert qc.slugify("The Steward's Fear") == "the-steward-s-fear"


def test_slugify_handles_empty_and_none():
    assert qc.slugify("") == ""
    assert qc.slugify(None) == ""


# Strategy tips (M4-B tips, Task 2) - tips_for() merges a loaded tips.json
# "scenarios" map's per-scenario general notes with that stage's own notes.
TIPS = {"passage-through-mirkwood": {
    "attribution": {"name": "Vision of the Palantir", "url": "http://example/p"},
    "general": ["watch threat"],
    "stages": {"3": ["branch note"]},
}}


def test_tips_for_merges_stage_specific_first():
    got = qc.tips_for("passage-through-mirkwood", 3, TIPS)
    assert got["tips"] == ["branch note", "watch threat"]
    assert got["attribution"] == {"name": "Vision of the Palantir", "url": "http://example/p"}


def test_tips_for_accepts_int_or_str_stage():
    assert qc.tips_for("passage-through-mirkwood", 3, TIPS) == \
        qc.tips_for("passage-through-mirkwood", "3", TIPS)


def test_tips_for_general_only_when_stage_has_no_entry():
    got = qc.tips_for("passage-through-mirkwood", 1, TIPS)
    assert got["tips"] == ["watch threat"]


def test_tips_for_returns_none_when_slug_absent():
    assert qc.tips_for("no-such-quest", 1, TIPS) is None


def test_tips_for_returns_none_on_empty_tips():
    assert qc.tips_for("passage-through-mirkwood", 1, {}) is None
    assert qc.tips_for("passage-through-mirkwood", 1, None) is None


def test_tips_for_returns_none_when_entry_has_no_content():
    tips = {"empty-quest": {"attribution": {"name": "X", "url": "http://x"},
                             "general": [], "stages": {}}}
    assert qc.tips_for("empty-quest", 1, tips) is None
