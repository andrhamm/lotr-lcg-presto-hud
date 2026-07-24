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
