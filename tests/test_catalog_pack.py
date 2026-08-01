"""catalog.bin must answer exactly what index.json answers.

Parsing index.json cost 429 ms on the device, ~87% of it decode and object
allocation rather than I/O. The pack drops the 242 unpickable rows and the
fields nothing reads, and encodes the rest fixed-width so a screen decodes only
what it displays. None of that is worth anything if it disagrees with the JSON,
so these tests compare the two directly.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quest_catalog import CatalogPack  # noqa: E402
from tools.build_catalog_pack import build, pickable  # noqa: E402


def _index():
    return {
        "scenarios": [
            {"slug": "passage-through-mirkwood", "name": "Passage Through Mirkwood",
             "pack": "Core Set", "cycle": "Core Set (Mirkwood Paths)",
             "source": "official", "kind": "quest", "stageCount": 3,
             "order": 1, "maxCardThreat": 4, "hasNightmare": True,
             "hasXThreat": False, "sailing": False},
            {"slug": "the-oath", "name": "The Oath", "pack": "The Land of Sorrow",
             "cycle": "The Haradrim", "source": "official", "kind": "quest",
             "stageCount": 3, "order": 77, "maxCardThreat": 5,
             "hasNightmare": False, "hasXThreat": True, "sailing": False},
            {"slug": "a-storm-on-cobas-haven", "name": "A Storm on Cobas Haven",
             "pack": "Sands", "cycle": "The Dream-chaser", "source": "official",
             "kind": "quest", "stageCount": 2, "order": None,
             "maxCardThreat": 3, "hasNightmare": False, "hasXThreat": False,
             "sailing": True},
            {"slug": "the-horse-lord-s-ire", "name": "The Horse Lord's Ire",
             "pack": "ALeP", "cycle": "ALeP - Other", "source": "alep",
             "kind": "quest", "stageCount": 3, "order": 5, "maxCardThreat": 6,
             "hasNightmare": False, "hasXThreat": False, "sailing": False},
            # unpickable: no stages. Must not reach the pack at all.
            {"slug": "dol-guldur-orcs", "name": "Dol Guldur Orcs", "pack": "Core Set",
             "cycle": "Core Set (Mirkwood Paths)", "source": "official",
             "kind": "encounter", "stageCount": 0, "order": None,
             "maxCardThreat": 0, "hasNightmare": False, "hasXThreat": False,
             "sailing": False},
        ],
        "packs": [{"slug": "core-set", "name": "Core Set", "cardCount": 1}],
    }


@pytest.fixture
def pack():
    blob, _, _ = build(_index())
    return CatalogPack(blob)


def test_unpickable_rows_never_reach_the_pack(pack):
    """242 of 396 real rows are parsed and discarded on device today."""
    assert pack.count == 4
    assert pack.find("dol-guldur-orcs") is None


def test_every_pickable_row_round_trips_field_for_field(pack):
    for src in _index()["scenarios"]:
        if not pickable(src):
            continue
        got = pack.find(src["slug"])
        assert got is not None, src["slug"]
        for field in ("slug", "name", "pack", "cycle", "source", "kind",
                      "stageCount", "order", "maxCardThreat",
                      "hasNightmare", "hasXThreat", "sailing"):
            assert got[field] == src[field], "%s.%s" % (src["slug"], field)


def test_a_null_order_survives_as_none_not_as_a_number(pack):
    """`order` absent means "sorts last" - 0xFFFF is the wire form, not a rank."""
    assert pack.find("a-storm-on-cobas-haven")["order"] is None
    assert pack.find("passage-through-mirkwood")["order"] == 1


def test_cycles_are_per_source(pack):
    official = pack.cycle_names("official")
    assert "Core Set (Mirkwood Paths)" in official
    assert "ALeP - Other" not in official
    assert pack.cycle_names("alep") == ["ALeP - Other"]


def test_rows_filter_by_source_and_cycle(pack):
    assert [e["slug"] for e in pack.rows(source="alep")] == ["the-horse-lord-s-ire"]
    rows = pack.rows(source="official", cycle="The Haradrim")
    assert [e["slug"] for e in rows] == ["the-oath"]


def test_find_is_a_binary_search_over_slug_sorted_records(pack):
    slugs = [pack.entry(i)["slug"] for i in range(pack.count)]
    assert slugs == sorted(slugs)
    for s in slugs:
        assert pack.find(s)["slug"] == s
    assert pack.find("no-such-scenario") is None


def test_unicode_names_survive_the_string_table():
    idx = _index()
    idx["scenarios"][0]["name"] = "The Caves of Nibin-Dûm"
    blob, _, _ = build(idx)
    assert CatalogPack(blob).find("passage-through-mirkwood")["name"] \
        == "The Caves of Nibin-Dûm"


def test_a_bad_blob_is_rejected_rather_than_misread():
    with pytest.raises(ValueError):
        CatalogPack(b"NOPE" + b"\x00" * 32)


def test_the_pack_is_much_smaller_than_the_json_it_replaces():
    import json
    blob, nrec, _ = build(_index())
    assert nrec == 4
    assert len(blob) < len(json.dumps(_index()).encode())
