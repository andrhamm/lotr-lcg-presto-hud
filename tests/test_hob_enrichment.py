import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import build_hob_enrichment as hob

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "hob_passage.json")

def test_included_sets_unions_and_normalizes():
    cards = json.load(open(FIXTURE, encoding="utf-8"))
    sets = hob.included_sets(cards)
    assert sets == ["Dol Guldur Orcs", "Passage Through Mirkwood", "Spiders of Mirkwood"]
    assert not any("(" in s for s in sets)          # qualifiers stripped

def test_included_sets_handles_missing_encounter_info():
    assert hob.included_sets([{"Title": "x"}, {"EncounterInfo": {}}]) == []

def test_included_sets_strips_qualifiers_and_dedupes():
    # Synthetic case exercising the qualifier-stripping rule the real
    # Passage fixture doesn't happen to contain: " (Campaign)"/" (Nightmare)"
    # suffixes (and any other trailing parenthetical) must be stripped
    # before union/de-dup, per the plan's Verified facts example:
    #   "EncounterSet": "Passage Through Mirkwood (Campaign)"
    #   "IncludedEncounterSets": ["Dol Guldur Orcs (Campaign)", "Spiders of Mirkwood"]
    cards = [
        {"EncounterInfo": {"EncounterSet": "Passage Through Mirkwood (Campaign)",
                           "IncludedEncounterSets": ["Dol Guldur Orcs (Campaign)",
                                                      "Spiders of Mirkwood"]}},
        {"EncounterInfo": {"EncounterSet": "Passage Through Mirkwood",
                           "IncludedEncounterSets": ["Dol Guldur Orcs (Nightmare)"]}},
        {"EncounterInfo": {"EncounterSet": "", "IncludedEncounterSets": [""]}},
    ]
    sets = hob.included_sets(cards)
    assert sets == ["Dol Guldur Orcs", "Passage Through Mirkwood", "Spiders of Mirkwood"]

def test_included_sets_sorted_and_deduplicated():
    cards = [
        {"EncounterInfo": {"EncounterSet": "Zeta Set", "IncludedEncounterSets": ["Alpha Set"]}},
        {"EncounterInfo": {"EncounterSet": "Alpha Set", "IncludedEncounterSets": ["Zeta Set"]}},
    ]
    assert hob.included_sets(cards) == ["Alpha Set", "Zeta Set"]
