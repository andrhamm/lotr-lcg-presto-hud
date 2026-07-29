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
    # A card with no number on any face still reports 0 so every caller can
    # keep doing arithmetic - but it now also says WHY there is no number,
    # which is what stops the UI drawing that 0 as if the card printed it.
    packs = {"q": {"encounter": {"location": [_loc("Blind Alley", None, None, "Q")]}}}
    out = qc.locations_for({"slug": "q"}, packs)
    assert (out[0]["points"], out[0]["threat"]) == (0, 0)
    # No marker at all upstream -> treated as X's poor cousin, not as a real 0.
    assert out[0]["pointsKind"] == "x" and out[0]["threatKind"] == "x"


def test_locations_for_reports_which_non_number_the_card_printed():
    # THE gate for the X work. build_card_data emits threatKind/questPointsKind
    # because upstream stores four different things in these columns and
    # parse_int flattened them all to None:
    #   "X"  the card prints a literal X   -> show the formula, or ask
    #   "-"  the stat does not apply       -> draw nothing at all
    # Collapsing them put a 0 on screen for both, and for threat a wrong 0
    # silently under-reports the staging total.
    packs = {"q": {"encounter": {"location": [{
        "id": "x", "name": "Tangled Grove", "encounterSet": "Q",
        "faces": [{"questPoints": None, "questPointsKind": "na",
                   "threat": None, "threatKind": "x",
                   "threatFormula": "the number of locations in the staging area"}]}]}}}
    out = qc.locations_for({"slug": "q"}, packs)[0]
    assert out["pointsKind"] == "na"
    assert "pointsFormula" not in out          # nothing to define; the stat is N/A
    assert out["threatKind"] == "x"
    assert out["threatFormula"] == "the number of locations in the staging area"


def test_locations_for_omits_the_marker_when_the_card_prints_a_number():
    # The common case must stay exactly as it was - no marker, no formula, so
    # nothing downstream has to special-case an ordinary location.
    out = qc.locations_for(PASSAGE, LOC_PACKS)[0]
    assert not any(k.endswith(("Kind", "Formula")) for k in out)


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


# --------------------------------------------------------------------------
# Resume: rebuilding the picker screens from a saved game
# --------------------------------------------------------------------------

def test_resume_picker_state_resolves_a_saved_scenario():
    """The picker screens are router-held, not game state, so a resume left
    them as empty placeholders and backing out of Quest Setup bounced the
    player to Scenario Source to pick their scenario over again. Nothing was
    missing from the save - this is the read-back that never existed."""
    st = qc.resume_picker_state(
        {"scenarios": SCENARIOS},
        {"slug": "conflict-at-the-carrock", "source": "official",
         "cycle": "Core Set", "mode": "Nightmare"})
    assert st["entry"]["name"] == "Conflict at the Carrock"
    assert st["source"] == "official" and st["cycle"] == "Core Set"
    assert st["difficulty"] == "Nightmare"
    # the two list screens behind it get real contents, not empty lists
    assert [c["cycle"] for c in st["cycles"]] == ["Core Set", "Shadows of Mirkwood"]
    assert "conflict-at-the-carrock" in [s["slug"] for s in st["siblings"]]


def test_resume_picker_state_defaults_a_missing_mode_to_standard():
    """A game saved before begin_setup stamped `mode` must still resolve."""
    st = qc.resume_picker_state(
        {"scenarios": SCENARIOS},
        {"slug": "passage-through-mirkwood", "source": "official",
         "cycle": "Core Set"})
    assert st["difficulty"] == "Standard"


def test_resume_picker_state_gives_up_quietly_on_what_it_cannot_resolve():
    """Both misses are legitimate, and neither may raise: a custom game has no
    scenario at all, and a slug can vanish from a catalog rebuilt without ALeP
    or against a newer card DB. The router falls back to the source page."""
    idx = {"scenarios": SCENARIOS}
    assert qc.resume_picker_state(idx, None) is None
    assert qc.resume_picker_state(idx, {}) is None
    assert qc.resume_picker_state(idx, {"name": "no slug"}) is None
    assert qc.resume_picker_state(idx, {"slug": "was-removed-from-the-catalog"}) is None
    assert qc.resume_picker_state({}, {"slug": "passage-through-mirkwood"}) is None


def test_resume_picker_state_falls_back_to_the_entry_for_source_and_cycle():
    """The stamp is preferred because it is what the player navigated, but an
    early save may carry only the slug."""
    st = qc.resume_picker_state({"scenarios": SCENARIOS},
                                {"slug": "a-journey-to-rhosgobel"})
    assert st["source"] == "official"
    assert st["cycle"] == "Shadows of Mirkwood"
    assert [s["slug"] for s in st["siblings"]] == ["a-journey-to-rhosgobel"]


def test_screens_rebuilt_from_resume_state_actually_render_populated():
    """The end of the chain: a saved stamp goes in, three drawn screens come
    out with real contents.

    Testing resume_picker_state alone would not have caught the symptom the
    player reported - empty pages behind the Back button - because the screens
    are what render, and the placeholder ones draw a perfectly valid *blank*
    list. So this asserts what is actually on the glass.
    """
    from tests.fake_hardware import FakeHardware
    from ui.theme import Palette
    from ui.screen_quest import (PickCycleScreen, ChooseScenarioScreen,
                                 ScenarioOptionsScreen)
    from gamestate import GameState

    index = {"scenarios": SCENARIOS}
    # what to_dict() stores for a game part-way through Passage
    st = qc.resume_picker_state(index, {
        "slug": "passage-through-mirkwood", "name": "Passage Through Mirkwood",
        "pack": "Core Set", "cycle": "Core Set", "source": "official",
        "kind": "quest", "nightmare": False, "mode": "Easy"})

    def texts(screen):
        hw = FakeHardware()
        screen.draw(hw, GameState(2, 25), Palette(hw.display))
        return " ".join(str(c[1]) for c in hw.display.calls if c[0] == "text")

    cycles = texts(PickCycleScreen(st["source"], st["cycles"]))
    assert "Core Set" in cycles and "Shadows of Mirkwood" in cycles

    chooser = ChooseScenarioScreen(st["source"], st["cycle"], st["siblings"])
    chooser.selected = st["entry"]["slug"]
    listing = texts(chooser)
    assert "Passage Through Mirkwood" in listing
    assert "Conflict at the Carrock" in listing
    assert chooser.selected == "passage-through-mirkwood", \
        "resume must land on the scenario being played, not the first row"

    opts = ScenarioOptionsScreen(st["entry"], {"slug": st["entry"]["slug"],
                                               "name": st["entry"]["name"]},
                                 {}, st["difficulty"])
    body = texts(opts)
    assert "Passage Through Mirkwood" in body
    assert "Easy" in body, "the difficulty the player chose must come back too"


def test_both_routers_rehydrate_before_sending_the_player_back_to_the_picker():
    """The routers are hand-mirrored and neither is importable on the host
    (main.py runs its loop at module scope, main.js needs a DOM), so this
    checks the wiring at the source, in the style of
    tests/test_firstrun.py's nav-trail gate.

    The bounce to scenario_source must stay a LAST resort. Before this, it was
    the whole handler: a resumed game's Back button threw the player's picked
    scenario away and made them choose it again.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cases = (
        ("main.py", "_rehydrate_pickers",
         'if target == "scenario_options" and not ('),
        ("docs/js/main.js", "rehydratePickers",
         'if (target === "scenario_options" && !screens.scenario_options?.scenario?.slug)'),
    )
    for rel, rehydrate, marker in cases:
        with open(os.path.join(root, rel), encoding="utf-8") as f:
            src = f.read()
        assert marker in src, "%s: the resumed-picker guard moved" % rel
        # generous: the firmware indents this ~32 columns deep
        window = src[src.index(marker):][:1600]
        assert rehydrate in window, \
            "%s: bounces to the source page without rebuilding first" % rel
        assert window.index(rehydrate) < window.index("scenario_source"), \
            "%s: falls back before it tries to rebuild" % rel
        assert "resume_picker_state" in src or "resumePickerState" in src, \
            "%s: never reads the saved scenario back" % rel
        # The emptiness check must test the SLUG, not truthiness. The
        # placeholder is built as ScenarioOptionsScreen({}, {}), and `{}` is
        # truthy in JS while `not {}` is True in Python - so a truthiness
        # check made the twins behave differently: the firmware bounced to the
        # source page and the web twin rendered "Unknown scenario".
        assert "scenario?.slug" in window or '"slug"' in window, \
            "%s: emptiness check must look at the slug, not truthiness" % rel


def test_both_routers_keep_the_picked_scenario_selected_when_relisting():
    """`choose_scenario_list` rebuilds the chooser from scratch, so without
    this the radio silently snapped back to row 1 every time you backed out of
    Scenario Options - resumed or not. Source-level for the same reason as the
    gate above."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for rel in ("main.py", "docs/js/main.js"):
        with open(os.path.join(root, rel), encoding="utf-8") as f:
            src = f.read()
        i = src.index("choose_scenario_list")
        window = src[i:i + 1800]
        assert "selected" in window, \
            "%s: relisting drops the player's current pick" % rel
