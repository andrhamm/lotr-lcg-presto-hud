"""tools/alep.py — the errata merge and pack metadata for the fan-made
A Long Extended Party packs, plus their integration into build_card_data.

Everything here is pure: no test touches the network or the pinned TSVs.
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import alep
import build_card_data as b

HEADER = b.HEADER


def row(**kw):
    r = {c: "" for c in HEADER}
    r.update(kw)
    return r


# -- apply_errata ------------------------------------------------------------

def test_errata_replaces_matching_card_and_keeps_base_identity():
    base = row(databaseId="base-1", name="Gálmód’s Escort", type="Enemy",
               packName="ALeP - The Gap of Rohan", encounterSet="The Gap of Rohan",
               numberInPack="7", unique="")
    err = row(databaseId="errata-1", name="Gálmód’s Escort", type="Enemy",
              packName=alep.ERRATA_PACK, encounterSet="The Gap of Rohan",
              numberInPack="14", unique="1")
    out, orphans = alep.apply_errata([base, err])

    assert orphans == 0
    assert len(out) == 1, "the errata row must not survive as a second card"
    got = out[0]
    # corrected content...
    assert got["unique"] == "1"
    # ...but the base card's identity, so grouping keeps it as the same card
    assert got["databaseId"] == "base-1"
    assert got["numberInPack"] == "7"
    assert got["packName"] == "ALeP - The Gap of Rohan"


def test_errata_key_includes_traits_so_difficulty_faces_dont_collide():
    """`Eastern Assault` is multi_sided with Normal./Easy. faces and an EMPTY
    `side` column on both. Keyed without traits, the Easy erratum would
    overwrite the Normal face."""
    common = dict(name="Eastern Assault", type="Objective", side="",
                  encounterSet="The Siege of Erebor")
    normal = row(databaseId="b-n", packName="ALeP - The Siege of Erebor",
                 traits="Normal.", text="old normal", **common)
    easy = row(databaseId="b-e", packName="ALeP - The Siege of Erebor",
               traits="Easy.", text="old easy", **common)
    e_normal = row(databaseId="x", packName=alep.ERRATA_PACK,
                   traits="Normal.", text="new normal", **common)
    e_easy = row(databaseId="y", packName=alep.ERRATA_PACK,
                 traits="Easy.", text="new easy", **common)

    out, orphans = alep.apply_errata([normal, easy, e_normal, e_easy])
    assert orphans == 0
    by_traits = {r["traits"]: r for r in out}
    assert by_traits["Normal."]["text"] == "new normal"
    assert by_traits["Easy."]["text"] == "new easy"
    assert by_traits["Normal."]["databaseId"] == "b-n"
    assert by_traits["Easy."]["databaseId"] == "b-e"


def test_errata_rules_rows_are_dropped_not_matched():
    """Multi-page rules inserts repeat a name across pages, so the key is
    ambiguous by construction; they are never part of a scenario."""
    page1 = row(databaseId="r1", name="Children of Eorl Rules 2", type="Rules",
                packName="ALeP - Children of Eorl", cornerText="Page 2/18",
                text="real text")
    err = row(databaseId="r2", name="Children of Eorl Rules 2", type="Rules",
              packName=alep.ERRATA_PACK, text="")
    out, orphans = alep.apply_errata([page1, err])
    assert orphans == 0, "a dropped Rules erratum is not an orphan"
    assert out == [page1], "the base rules row must pass through untouched"


def test_errata_replaces_every_identical_duplicate():
    """`Roused Hobbits` matches 7 byte-identical base rows; replacing all of
    them is well-defined."""
    dupes = [row(databaseId="d%d" % i, name="Roused Hobbits", type="Objective",
                 packName="ALeP - The Scouring of the Shire",
                 encounterSet="The Scouring of the Shire", text="old")
             for i in range(7)]
    err = row(databaseId="e", name="Roused Hobbits", type="Objective",
              packName=alep.ERRATA_PACK,
              encounterSet="The Scouring of the Shire", text="new")
    out, orphans = alep.apply_errata(dupes + [err])
    assert orphans == 0
    assert len(out) == 7
    assert {r["text"] for r in out} == {"new"}


def test_unmatched_errata_is_dropped_and_counted():
    """A row matching nothing means the join key shifted upstream. Inventing
    a card from it would be worse than reporting it."""
    base = row(databaseId="b", name="Some Card", packName="ALeP - Whatever",
               encounterSet="Set A")
    err = row(databaseId="e", name="Ghost Card", packName=alep.ERRATA_PACK,
              encounterSet="Set Z")
    out, orphans = alep.apply_errata([base, err])
    assert out == [base]
    assert orphans == 1


def test_apply_errata_leaves_non_alep_rows_alone_and_in_order():
    rows = [row(databaseId=str(i), name="C%d" % i, packName="Core Set")
            for i in range(4)]
    out, orphans = alep.apply_errata(rows)
    assert out == rows and orphans == 0


# -- pack metadata -----------------------------------------------------------

def test_pack_meta_cycles_and_source():
    assert alep.pack_meta("ALeP - Children of Eorl") == {
        "cycle": alep.CYCLE_EORL, "source": "alep", "date": None}
    assert alep.pack_meta("ALeP - The Brandywine Pursuit")["cycle"] == alep.CYCLE_SHIRE
    assert alep.pack_meta("ALeP - The Siege of Erebor")["cycle"] == alep.CYCLE_POD
    # An ALeP pack upstream added since we last looked must still be usable,
    # just uncategorised - never silently filed under an official cycle.
    meta = alep.pack_meta("ALeP - Something Brand New")
    assert meta == {"cycle": alep.CYCLE_OTHER, "source": "alep", "date": None}


def test_is_nightmare_pack():
    assert alep.is_nightmare_pack("ALeP - The Withered Heath Nightmare")
    assert alep.is_nightmare_pack("ALeP - Mount Doom Nightmare")
    assert not alep.is_nightmare_pack("ALeP - Children of Eorl")
    assert not alep.is_nightmare_pack("")
    assert not alep.is_nightmare_pack(None)


# -- integration through build_outputs ---------------------------------------

def _tsv(rows):
    out = io.StringIO()
    out.write("\t".join(HEADER) + "\n")
    for r in rows:
        out.write("\t".join((r.get(c) or "") for c in HEADER) + "\n")
    out.seek(0)
    return out


def _quest(**kw):
    return row(type="Quest", cardBack="encounter", **kw)


def test_alep_scenario_gets_alep_source_and_cycle():
    rows = [
        _quest(databaseId="q1", name="Ambush at Erelas", side="A",
               packName="ALeP - Children of Eorl", encounterSet="Ambush at Erelas"),
        _quest(databaseId="q1", name="Ambush at Erelas", side="B",
               packName="ALeP - Children of Eorl", encounterSet="Ambush at Erelas",
               questPoints="8"),
    ]
    out = b.build_outputs(_tsv([]), extra_rows=rows)
    entry = out["index"]["scenarios"][0]
    assert entry["name"] == "Ambush at Erelas"
    assert entry["source"] == "alep"
    assert entry["cycle"] == alep.CYCLE_EORL
    assert entry["releaseDate"] is None


def test_cycle_resolves_over_all_packs_in_the_set_not_just_the_first_card():
    """A supplementary pack ("ALeP - Backup") can own the first card of a set
    whose real pack is elsewhere; the cycle must still come from the pack we
    actually know about."""
    rows = [
        _quest(databaseId="q1", name="The Brandywine Pursuit", side="A",
               packName="ALeP - Backup", encounterSet="The Brandywine Pursuit"),
        _quest(databaseId="q2", name="The Brandywine Pursuit", side="A",
               packName="ALeP - The Brandywine Pursuit",
               encounterSet="The Brandywine Pursuit", questPoints="5"),
    ]
    entry = b.build_outputs(_tsv([]), extra_rows=rows)["index"]["scenarios"][0]
    assert entry["cycle"] == alep.CYCLE_SHIRE
    assert entry["pack"] == "ALeP - The Brandywine Pursuit"


def test_alep_nightmare_set_is_kind_nightmare_not_a_pickable_quest():
    rows = [
        _quest(databaseId="q1", name="The Withered Heath Nightmare", side="A",
               packName="ALeP - The Withered Heath Nightmare",
               encounterSet="The Withered Heath Nightmare", questPoints="3"),
    ]
    entry = b.build_outputs(_tsv([]), extra_rows=rows)["index"]["scenarios"][0]
    assert entry["kind"] == "nightmare"


def test_has_nightmare_does_not_cross_sources():
    """ALeP's "The Withered Heath Nightmare" slugifies identically to the
    official "The Withered Heath - Nightmare". An official scenario must not
    advertise a Nightmare mode that would load community cards."""
    official = _quest(databaseId="o1", name="The Withered Heath", side="A",
                      packName="The Withered Heath",
                      encounterSet="The Withered Heath", questPoints="4")
    fan = _quest(databaseId="a1", name="The Withered Heath Nightmare", side="A",
                 packName="ALeP - The Withered Heath Nightmare",
                 encounterSet="The Withered Heath Nightmare", questPoints="3")
    out = b.build_outputs(_tsv([official]), extra_rows=[fan])
    by_name = {s["name"]: s for s in out["index"]["scenarios"]}
    assert by_name["The Withered Heath"]["source"] == "official"
    assert by_name["The Withered Heath"]["hasNightmare"] is False


def test_official_scenario_with_official_nightmare_still_reports_it():
    """The same-source rule must not break the ordinary official case."""
    base = _quest(databaseId="o1", name="Passage", side="A",
                  packName="Core Set", encounterSet="Passage", questPoints="8")
    nm = row(databaseId="n1", name="Passage", type="Nightmare",
             packName="Core Set - Nightmare", encounterSet="Passage - Nightmare")
    out = b.build_outputs(_tsv([base, nm]))
    by_name = {s["name"]: s for s in out["index"]["scenarios"]}
    assert by_name["Passage"]["hasNightmare"] is True


def test_excluded_packs_are_not_content():
    assert "Seastan Scratch Set" in alep.EXCLUDED_PACKS
    assert "ALeP - Shire Cycle 6 Placeholder" in alep.EXCLUDED_PACKS
