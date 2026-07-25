import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build_card_data as b
import json as _json

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "cardDb_sample.tsv")

def load_cards():
    with open(FIXTURE, encoding="utf-8") as f:
        return b.group_cards(b.parse_tsv(f))

def test_parse_int_and_tags():
    assert b.parse_int("8") == 8
    assert b.parse_int("") is None
    assert b.parse_int("X") is None
    obj, raw = b.parse_tags('{"firstPlayerControls": true}')
    assert obj == {"firstPlayerControls": True} and raw is None
    obj, raw = b.parse_tags("not json")
    assert obj is None and raw == "not json"

def test_group_faces_by_id():
    cards = {c["id"]: c for c in load_cards()}
    # stage 1 quest: one card, two faces
    q1 = cards["p-9119"]
    assert q1["type"] == "Quest" and len(q1["faces"]) == 2
    sides = [f["side"] for f in q1["faces"]]
    assert sides == ["A", "B"]
    assert q1["faces"][1]["questPoints"] == 8
    # branch stage: two distinct ids, each one card
    assert cards["p-9123"]["faces"][1]["name"] == "Don't Leave the Path!"
    assert cards["p-9125"]["faces"][1]["questPoints"] == 10

def test_slugify():
    assert b.slugify("Passage Through Mirkwood") == "passage-through-mirkwood"
    assert b.slugify("Passage Through Mirkwood - Nightmare") == "passage-through-mirkwood-nightmare"

def test_blank_side_is_none():
    cards = {c["id"]: c for c in load_cards()}
    # non-quest card (blank side column) -> None
    assert cards["e-spawn"]["faces"][0]["side"] is None
    # quest cards keep explicit sides
    assert [f["side"] for f in cards["p-9119"]["faces"]] == ["A", "B"]

def quest_cards_for(enc):
    return [c for c in load_cards() if c["type"] == "Quest" and c["encounterSet"] == enc]

def test_shape_quest_stages_and_branch():
    q = b.shape_quest(quest_cards_for("Passage Through Mirkwood"))
    assert q["skipped"] == 1  # the malformed 'X' cost row
    stages = q["stages"]
    assert [s["stage"] for s in stages] == [1, 2, 3]
    assert stages[0]["cards"][0]["questPoints"] == 8
    assert stages[1]["cards"][0]["questPoints"] == 2
    s3 = stages[2]
    assert s3.get("branch") == "random"
    assert sorted(c["questPoints"] for c in s3["cards"]) == [0, 10]
    # non-branch stages have no 'branch' key
    assert "branch" not in stages[0]
    # faces trimmed to side/name/text
    assert set(stages[0]["cards"][0]["faces"][0].keys()) == {"side", "name", "text"}

def test_is_sailing():
    cards = {c["id"]: c for c in load_cards()}
    assert b.is_sailing(cards["f-1"]) is True
    assert b.is_sailing(cards["p-9119"]) is False

def test_branch_kind_reads_b_side_only():
    def card(a_text, b_text):
        return {"faces": [{"side": "A", "name": "x", "text": a_text},
                          {"side": "B", "name": "y", "text": b_text}]}
    # B-side 'at random' -> random
    assert b._branch_kind([card("", "proceed to one of the 2 stages at random"), card("", "")]) == "random"
    # B-side 'first player chooses' -> choice
    assert b._branch_kind([card("", "the first player chooses a stage"), card("", "")]) == "choice"
    # A-side keyword must be ignored -> default random
    assert b._branch_kind([card("the players choose their path", "resolve as normal"), card("", "")]) == "random"

def build():
    with open(FIXTURE, encoding="utf-8") as f:
        return b.build_outputs(f, meta={"generated": "2026-07-24", "source": "fixture"})

def build_with_enrichment(enrichment):
    with open(FIXTURE, encoding="utf-8") as f:
        return b.build_outputs(f, meta={"generated": "2026-07-24", "source": "fixture"},
                                enrichment=enrichment)

def test_scenario_assembly_and_index():
    out = build()
    scn = out["scenarios"]["passage-through-mirkwood"]
    assert scn["kind"] == "quest"
    assert [s["stage"] for s in scn["quest"]["stages"]] == [1, 2, 3]
    assert len(scn["encounter"]["enemy"]) == 1
    assert len(scn["encounter"]["location"]) == 1
    assert len(scn["encounter"]["treachery"]) == 1
    # quest cards not duplicated into encounter
    assert "quest" not in scn["encounter"]
    idx = {s["slug"]: s for s in out["index"]["scenarios"]}
    assert idx["passage-through-mirkwood"]["stageCount"] == 3
    assert idx["passage-through-mirkwood"]["hasNightmare"] is True
    assert idx["flight-of-the-stormcaller"]["sailing"] is True

def test_index_has_cycle_source_date():
    out = build()
    passage = next(s for s in out["index"]["scenarios"] if s["slug"] == "passage-through-mirkwood")
    assert passage["cycle"] == "Core Set" and passage["source"] == "official"
    assert "releaseDate" in passage

def test_index_release_dates_known_and_unknown():
    # B-data (catalog-enrichment plan, Task 2): PACK_META's per-pack dates
    # flow through to index entries. Core Set's date is independently
    # verified against Fantasy Flight's own release announcement (see
    # RELEASE_DATES' sourcing comment in build_card_data.py) - "2011-04".
    out = build()
    idx = {s["slug"]: s for s in out["index"]["scenarios"]}
    assert idx["passage-through-mirkwood"]["releaseDate"] == "2011-04"
    # "The Flight of the Stormcaller" (the fixture's pack name) doesn't
    # match any PACK_META key (the real pack is "Flight of the Stormcaller",
    # no "The") - PACK_META.get(pack, {}) must fall back cleanly to a null
    # date (and "Other"/"official") rather than raising.
    unknown = idx["flight-of-the-stormcaller"]
    assert unknown["releaseDate"] is None
    assert unknown["cycle"] == "Other" and unknown["source"] == "official"

def test_modes_campaign_players_rules():
    out = build()
    assert out["scenarios"]["the-hunt-for-the-dreadnaught"]["modes"][0]["name"] == "Easy Mode"
    assert out["scenarios"]["the-old-forest"]["kind"] == "campaign"
    core = out["players"]["packs"]["core-set"]
    assert any(c["name"] == "Aragorn" for c in core["cards"]["hero"])
    assert any(c["name"] == "Gandalf" for c in core["cards"]["ally"])
    assert any(c["name"] == "Questing" for c in out["rules"])
    # index carries disclaimer + source
    assert "Fantasy Flight" in out["index"]["disclaimer"]
    assert out["index"]["source"] == "fixture"

def test_kind_branches_and_packs():
    out = build()
    scn = {s["slug"]: s for s in out["index"]["scenarios"]}
    # nightmare set (nm-1 row) -> kind "nightmare"
    assert out["scenarios"]["passage-through-mirkwood-nightmare"]["kind"] == "nightmare"
    # encounter-only set (the new Objective Ally row, no quest/nightmare/campaign) -> kind "encounter"
    tos = out["scenarios"]["test-objective-set"]
    assert tos["kind"] == "encounter"
    # multi-word type camelCased into its bucket
    assert len(tos["encounter"]["objectiveAlly"]) == 1
    # index packs sorted by name, and present
    packs = out["index"]["packs"]
    names = [p["name"] for p in packs]
    assert names == sorted(names)
    assert any(p["slug"] == "core-set" for p in packs)

def test_emit_writes_files(tmp_path):
    out = build()
    b.emit(out, str(tmp_path))
    idx = _json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert any(s["slug"] == "passage-through-mirkwood" for s in idx["scenarios"])
    scn = _json.loads((tmp_path / "scenarios" / "passage-through-mirkwood.json").read_text(encoding="utf-8"))
    assert scn["quest"]["stages"][0]["cards"][0]["questPoints"] == 8
    assert (tmp_path / "players" / "core-set.json").exists()
    assert (tmp_path / "rules.json").exists()

def test_emit_deterministic(tmp_path):
    out = build()
    b.emit(out, str(tmp_path / "a"))
    b.emit(out, str(tmp_path / "b"))
    a = (tmp_path / "a" / "index.json").read_bytes()
    c = (tmp_path / "b" / "index.json").read_bytes()
    assert a == c

def test_emit_prunes_stale(tmp_path):
    out = build()
    b.emit(out, str(tmp_path))
    stale = tmp_path / "scenarios" / "zzz-old-scenario.json"
    stale.write_text("{}", encoding="utf-8")
    assert stale.exists()
    b.emit(out, str(tmp_path))  # re-emit should drop the stale file
    assert not stale.exists()
    assert (tmp_path / "scenarios" / "passage-through-mirkwood.json").exists()

def test_slug_collision_merges_and_index_matches_files():
    out = build()
    # the two case-variant encounterSets merge into one scenario
    cs = out["scenarios"]["casing-test"]
    assert len(cs["encounter"]["enemy"]) == 2
    # invariant: every index scenario has a written-file entry, and no orphans
    index_slugs = {s["slug"] for s in out["index"]["scenarios"]}
    assert index_slugs == set(out["scenarios"].keys())
    assert len(out["index"]["scenarios"]) == len(out["scenarios"])

def test_extra_columns_captured():
    cards = {c["id"]: c for c in load_cards()}
    c = cards["col-test"]
    assert c["cardBack"] == "encounter"
    assert c["quantity"] == 3
    assert c["setUuid"] == "uuid-xyz"

# --- B-data Task 3: enrichment merge (optional, absent-tolerant) ----------

ENRICHMENT = {"scenarios": {
    "passage-through-mirkwood": {
        "includedSets": ["Dol Guldur Orcs", "Passage Through Mirkwood", "Spiders of Mirkwood"]},
}}

def test_enrichment_merges_included_sets_and_gather_count():
    out = build_with_enrichment(ENRICHMENT)
    scn = out["scenarios"]["passage-through-mirkwood"]
    assert scn["includedSets"] == ["Dol Guldur Orcs", "Passage Through Mirkwood", "Spiders of Mirkwood"]
    idx = {s["slug"]: s for s in out["index"]["scenarios"]}
    assert idx["passage-through-mirkwood"]["gatherCount"] == 3
    # a scenario absent from the enrichment map is untouched - no key, not null
    other = out["scenarios"]["flight-of-the-stormcaller"]
    assert "includedSets" not in other
    assert "gatherCount" not in idx["flight-of-the-stormcaller"]
    # provenance: Hall of Beorn only credited when enrichment was actually used
    assert "hallofbeorn.com" in out["index"]["source"]

def test_enrichment_absent_omits_fields_and_source_unchanged():
    out = build()  # no enrichment kwarg -> None, same as a build with no enrichment file
    scn = out["scenarios"]["passage-through-mirkwood"]
    assert "includedSets" not in scn
    idx = {s["slug"]: s for s in out["index"]["scenarios"]}
    assert "gatherCount" not in idx["passage-through-mirkwood"]
    assert out["index"]["source"] == "fixture"
    assert "hallofbeorn" not in out["index"]["source"].lower()

def test_enrichment_scenario_with_empty_included_sets_is_omitted():
    # A scenario present in the enrichment map but with no resolved sets
    # (shouldn't happen from build_hob_enrichment.build(), which never
    # writes an empty list - see its own tests - but defend the merge
    # itself too) must not add either field.
    out = build_with_enrichment({"scenarios": {"passage-through-mirkwood": {"includedSets": []}}})
    scn = out["scenarios"]["passage-through-mirkwood"]
    assert "includedSets" not in scn
    idx = {s["slug"]: s for s in out["index"]["scenarios"]}
    assert "gatherCount" not in idx["passage-through-mirkwood"]

def test_load_enrichment_missing_corrupt_and_good(tmp_path):
    assert b._load_enrichment(str(tmp_path / "nope.json")) is None
    corrupt = tmp_path / "bad.json"
    corrupt.write_text("not json", encoding="utf-8")
    assert b._load_enrichment(str(corrupt)) is None
    wrong_shape = tmp_path / "shape.json"
    wrong_shape.write_text('{"scenarios": "not a dict"}', encoding="utf-8")
    assert b._load_enrichment(str(wrong_shape)) is None
    good = tmp_path / "good.json"
    good.write_text('{"scenarios": {"x": {"includedSets": ["A"]}}}', encoding="utf-8")
    loaded = b._load_enrichment(str(good))
    assert loaded["scenarios"]["x"]["includedSets"] == ["A"]

# --- needs_refresh: the committed-derived-data guard ----------------------
# Shared by tools/build_hob_enrichment.py and tools/build_tips.py, whose
# outputs are committed (see CLAUDE.md's "What may be committed") - so the
# default has to be "don't fetch", not "fetch again".

def test_needs_refresh_only_when_absent_or_asked_for(tmp_path):
    present = tmp_path / "enrichment.json"
    present.write_text("{}", encoding="utf-8")
    absent = tmp_path / "nope.json"
    # An existing output is left alone unless --refresh says otherwise...
    assert b.needs_refresh(str(present), False) is False
    assert b.needs_refresh(str(present), True) is True
    # ...and a missing one is always built, --refresh or not (a fresh clone
    # that somehow lacks the file, or a --out pointed somewhere new).
    assert b.needs_refresh(str(absent), False) is True
    assert b.needs_refresh(str(absent), True) is True
