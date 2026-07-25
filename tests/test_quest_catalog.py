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
    # The ALeP cycles follow the official ones and precede "Other"; their
    # names and order come from the DragnCards plugin's own menu files (see
    # tools/alep.py). They never interleave with the official cycles because
    # group_by_cycle filters on `source` before it ever sorts.
    assert qc.CYCLE_ORDER == [
        "Core Set", "Shadows of Mirkwood", "The Dwarrowdelf", "Against the Shadow",
        "The Ring-maker", "The Angmar Awakened", "The Dream-chaser", "The Haradrim",
        "Ered Mithrin", "The Vengeance of Mordor", "Hobbit Saga", "LotR Saga",
        "Standalone/PoD",
        "ALeP - Children of Eorl & Oaths of the Rohirrim",
        "ALeP - The Shire's Reckoning & Fell Summer",
        "ALeP - Print on Demand",
        "ALeP - Other",
        "Other",
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


# Location picker - the union across a scenario's "sets to gather".
#
# A scenario's own scenarios/<slug>.json only carries cards whose
# encounterSet IS that scenario's set, so its own file holds 2 of Passage
# Through Mirkwood's 6 locations; the other 4 live in the two sets it
# gathers. The fixture below is the REAL compiled data for those three sets
# (docs/data/scenarios/{passage-through-mirkwood,dol-guldur-orcs,spiders-of-
# mirkwood}.json, verified 2026-07-25), trimmed to the fields locations_for
# reads - so the numbers this file asserts are the printed card values, not
# invented ones.
def _loc(name, qp, threat, encounter_set, card_id=None):
    return {"id": card_id or qc.slugify(name), "name": name,
            "encounterSet": encounter_set,
            "faces": [{"name": name, "questPoints": qp, "threat": threat}]}


PASSAGE = {"slug": "passage-through-mirkwood", "name": "Passage Through Mirkwood",
           "includedSets": ["Dol Guldur Orcs", "Passage Through Mirkwood",
                            "Spiders of Mirkwood"]}

LOC_PACKS = {
    "passage-through-mirkwood": {"encounter": {"location": [
        _loc("Old Forest Road", 3, 1, "Passage Through Mirkwood"),
        _loc("Forest Gate", 4, 2, "Passage Through Mirkwood"),
    ]}},
    "dol-guldur-orcs": {"encounter": {"location": [
        _loc("Enchanted Stream", 2, 2, "Dol Guldur Orcs"),
        _loc("Necromancer's Pass", 2, 3, "Dol Guldur Orcs"),
    ]}},
    "spiders-of-mirkwood": {"encounter": {"location": [
        _loc("Great Forest Web", 2, 2, "Spiders of Mirkwood"),
        _loc("Mountains of Mirkwood", 3, 2, "Spiders of Mirkwood"),
    ]}},
    # present in `packs` but NOT in Passage's gather list - must not leak in
    "escape-from-dol-guldur": {"encounter": {"location": [
        _loc("Dungeons of Dol Guldur", 3, 1, "Escape from Dol Guldur"),
    ]}},
}


def test_location_set_slugs_is_the_gather_list_slugified():
    assert qc.location_set_slugs(PASSAGE) == [
        "dol-guldur-orcs", "passage-through-mirkwood", "spiders-of-mirkwood"]


def test_location_set_slugs_falls_back_to_the_scenario_own_set():
    # ~2/3 of quest scenarios have no gather list (the committed Hall of
    # Beorn enrichment covers 108) - they still get their own set's cards.
    assert qc.location_set_slugs({"slug": "some-quest"}) == ["some-quest"]
    assert qc.location_set_slugs({"slug": "some-quest", "includedSets": []}) == ["some-quest"]


def test_location_set_slugs_never_raises_on_junk():
    assert qc.location_set_slugs(None) == []
    assert qc.location_set_slugs({}) == []


def test_locations_for_unions_across_the_gather_list():
    # THE GATE for this feature: Passage resolves to its six real locations
    # with the printed quest points and threat. A build regression that drops
    # the union collapses this to the two cards in Passage's own file.
    out = qc.locations_for(PASSAGE, LOC_PACKS)
    assert [(l["name"], l["points"], l["threat"]) for l in out] == [
        ("Enchanted Stream", 2, 2),
        ("Forest Gate", 4, 2),
        ("Great Forest Web", 2, 2),
        ("Mountains of Mirkwood", 3, 2),
        ("Necromancer's Pass", 2, 3),
        ("Old Forest Road", 3, 1),
    ]
    assert out[0]["set"] == "Dol Guldur Orcs"


def test_locations_for_ignores_packs_outside_the_gather_list():
    names = [l["name"] for l in qc.locations_for(PASSAGE, LOC_PACKS)]
    assert "Dungeons of Dol Guldur" not in names


def test_locations_for_skips_gather_names_with_no_card_file():
    # 14 of 309 gather-list entries resolve to no scenarios/<slug>.json -
    # they drop out silently rather than raising or emitting a blank row.
    scn = dict(PASSAGE, includedSets=PASSAGE["includedSets"] + ["No Such Set"])
    assert len(qc.locations_for(scn, LOC_PACKS)) == 6


def test_locations_for_dedupes_by_name_and_set():
    packs = dict(LOC_PACKS)
    packs["spiders-of-mirkwood"] = {"encounter": {"location": [
        _loc("Great Forest Web", 2, 2, "Spiders of Mirkwood", card_id="a"),
        _loc("Great Forest Web", 2, 2, "Spiders of Mirkwood", card_id="b"),
    ]}}
    names = [l["name"] for l in qc.locations_for(PASSAGE, packs)]
    assert names.count("Great Forest Web") == 1


def test_locations_for_defaults_null_points_and_threat_to_zero():
    # 15 catalog locations carry a null questPoints on every face (variable
    # or condition-explored cards) - they show 0 and the player edits it,
    # same rule side_quests() uses for the variable "X" side quests.
    packs = {"q": {"encounter": {"location": [_loc("Blind Alley", None, None, "Q")]}}}
    out = qc.locations_for({"slug": "q"}, packs)
    assert (out[0]["points"], out[0]["threat"]) == (0, 0)


def test_locations_for_takes_the_first_non_null_face():
    # 21 locations are multi-face; read the same way side_quests() does.
    packs = {"q": {"encounter": {"location": [{
        "id": "x", "name": "Two-sided", "encounterSet": "Q",
        "faces": [{"questPoints": None, "threat": None},
                  {"questPoints": 5, "threat": 4}]}]}}}
    out = qc.locations_for({"slug": "q"}, packs)
    assert (out[0]["points"], out[0]["threat"]) == (5, 4)


def test_locations_for_returns_empty_when_there_are_no_locations():
    # 3 of 154 quest scenarios gather no locations at all; the picker shows
    # its manual stepper rather than an empty list.
    assert qc.locations_for(PASSAGE, {}) == []
    assert qc.locations_for({"slug": "q"}, {"q": {"encounter": {}}}) == []
    assert qc.locations_for(None, LOC_PACKS) == []
