import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build_card_data as b
import json as _json
import pytest

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
    assert passage["cycle"] == "Core Set (Mirkwood Paths)" and passage["source"] == "official"
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


def test_emit_writes_a_precomputed_side_quest_list(tmp_path):
    """The device used to find 15 side quests by opening and parsing all 105
    player packs - 1.6 MB and 6.4 SECONDS of flash reads on the Presto, every
    time you tapped "+ Side quest". The build knows the answer, so it emits
    it: one small file, one read."""
    import quest_catalog as qc
    out = build()
    b.emit(out, str(tmp_path))
    p = tmp_path / "players" / "side_quests.json"
    assert p.exists(), "build must precompute players/side_quests.json"
    emitted = _json.loads(p.read_text(encoding="utf-8"))
    # identical to what the old full scan produced, so behaviour is unchanged
    assert emitted == qc.side_quests(out["players"]["packs"])
    for e in emitted:
        assert set(e) >= {"id", "name", "points", "sphere", "pack"}


def test_emitted_side_quests_are_a_tiny_fraction_of_the_pack_bytes(tmp_path):
    """Guards the reason this file exists: if it ever stopped being much
    smaller than the packs it replaces, the read would be back to slow."""
    out = build()
    b.emit(out, str(tmp_path))
    sq = (tmp_path / "players" / "side_quests.json").stat().st_size
    packs = sum(f.stat().st_size for f in (tmp_path / "players").glob("*.json")
                if f.name not in ("side_quests.json", "index.json"))
    assert sq * 20 < packs, "side_quests.json is not buying enough (%d vs %d)" % (sq, packs)


# -- upstream defect: side B carrying side A's text -------------------------

def test_unsmear_strips_a_duplicated_a_side_prefix_from_b():
    # 15 of the TSV's 505 quest pairs have B = A's text + B's own, so the
    # Quest Cards screen showed side B repeating side A. The seam is usually
    # visible as a missing space ("...staging area.This stage cannot...").
    faces = [{"side": "A", "text": "Setup: Do a thing."},
             {"side": "B", "text": "Setup: Do a thing.This stage cannot be "
                                   "defeated while Goblin Troop is in play."}]
    out = b._unsmear_quest_faces("Quest", faces)
    assert out[0]["text"] == "Setup: Do a thing."
    assert out[1]["text"] == ("This stage cannot be defeated while Goblin "
                              "Troop is in play.")


def test_unsmear_leaves_b_empty_when_it_only_repeated_a():
    # The Oath's stage 1: side B prints no effect at all, it is just the nine
    # quest points, so the two faces read identically before this.
    faces = [{"side": "A", "text": "Setup: Search the encounter deck."},
             {"side": "B", "text": "Setup: Search the encounter deck."}]
    out = b._unsmear_quest_faces("Quest", faces)
    assert out[1]["text"] is None


def test_unsmear_leaves_a_normal_two_sided_card_alone():
    faces = [{"side": "A", "text": "Story on the front."},
             {"side": "B", "text": "When Revealed: something else entirely."}]
    out = b._unsmear_quest_faces("Quest", faces)
    assert out[1]["text"] == "When Revealed: something else entirely."


def test_unsmear_only_touches_quest_cards():
    # A location or enemy has one face; nothing else in the data shows this
    # defect, so the rule is scoped rather than global.
    faces = [{"side": "A", "text": "Same."}, {"side": "B", "text": "Same."}]
    out = b._unsmear_quest_faces("Location", faces)
    assert out[1]["text"] == "Same."


def test_the_oath_stage_one_faces_are_no_longer_identical():
    # The bug as reported: the Quest Cards screen showed the same paragraph
    # for Stage 1A and Stage 1B.
    import json, os
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "docs", "data", "scenarios", "the-oath.json")
    if not os.path.exists(path):
        return                                  # generated; skip on a bare tree
    with open(path, encoding="utf-8") as f:
        stages = (json.load(f).get("quest") or {}).get("stages") or []
    faces = stages[0]["cards"][0]["faces"]
    a = next(f["text"] for f in faces if f["side"] == "A")
    b = next(f["text"] for f in faces if f["side"] == "B")
    assert a and "Setup:" in a
    assert b is None, "side B should print no text, got %r" % (b,)



# --------------------------------------------------------------------------
# Corrections + ASCII folding (tools/corrections.py) - 2026-07-30 playtest
# --------------------------------------------------------------------------

import corrections as _corr


def _row(**kw):
    base = {"databaseId": "1", "name": "", "encounterSet": "", "text": "",
            "shadow": "", "traits": "", "packName": "", "side": "A", "type": "Enemy"}
    base.update(kw)
    return base


def test_set_rename_rewrites_the_encounter_set_on_every_row():
    """An encounterSet rewrite is what makes an upstream-split scenario
    slug-collide back into one, so it has to happen at ROW level - before
    build_outputs buckets rows by slugify(encounterSet)."""
    rows = [_row(encounterSet="Journey Along the Anduin", name="A"),
            _row(encounterSet="Journey Along the Anduin", name="B"),
            _row(encounterSet="Something Else", name="C")]
    out, unmatched = _corr.apply_corrections(
        rows, {"sets": [{"from": "Journey Along the Anduin",
                         "to": "Journey Down the Anduin"}]})
    assert [r["encounterSet"] for r in out] == [
        "Journey Down the Anduin", "Journey Down the Anduin", "Something Else"]
    assert unmatched == []


def test_a_correction_that_matches_nothing_is_reported_not_raised():
    """Upstream fixing a typo must show up as a printed line, not as a crash
    and not as silent divergence."""
    _, unmatched = _corr.apply_corrections(
        [_row(text="all correct here")],
        {"text": [{"find": "Gret Spider", "replace": "Great Spider"}],
         "sets": [{"from": "Nonexistent Set", "to": "X"}]})
    assert len(unmatched) == 2
    assert any("Gret Spider" in u for u in unmatched)
    assert any("Nonexistent Set" in u for u in unmatched)


def test_absent_or_corrupt_corrections_degrade_to_a_no_op(tmp_path):
    """Same posture as _load_enrichment: never fail a catalog build."""
    assert b._load_corrections(str(tmp_path / "absent.json")) == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert b._load_corrections(str(bad)) == {}
    rows = [_row(text="untouched")]
    out, unmatched = _corr.apply_corrections(rows, {})
    assert out[0]["text"] == "untouched" and unmatched == []


def test_only_possessive_backticks_become_apostrophes():
    """~half the backticks in the catalog are quote DELIMITERS wrapping nested
    card text, not apostrophes. A blanket replace would be a new error, so the
    delimiter case is deliberately left alone."""
    rows = [_row(text="each player`s deck"),
            _row(text="his heroes` resource pool"),
            _row(text="it gains: `Response: When...`")]
    out, _ = _corr.apply_corrections(rows, {"global": ["possessive_backtick"]})
    assert out[0]["text"] == "each player's deck"
    assert out[1]["text"] == "his heroes' resource pool"
    assert out[2]["text"] == "it gains: `Response: When...`"   # untouched


def test_fold_ascii_covers_every_glyph_the_device_font_lacks():
    """BITMAP8_W has 82 entries and returns 4px for anything absent, so a
    circumflex passes every host layout test and only breaks on hardware."""
    assert _corr.fold_ascii("The Caves of Nibin-Dûm") == "The Caves of Nibin-Dum"
    assert _corr.fold_ascii("The Horse Lord’s Ire") == "The Horse Lord's Ire"
    assert _corr.fold_ascii("Nazgûl") == "Nazgul"
    assert _corr.fold_ascii("look‐outs") == "look-outs"
    assert _corr.fold_ascii("Card text © FFG") == "Card text (c) FFG"
    assert _corr.fold_ascii(None) is None


def test_fold_payload_catches_strings_merged_in_after_the_row_pass():
    """includedSets and the per-stage advance conditions arrive from committed
    distillations AFTER grouping, so the row pass never sees them - they were
    15 of the 16 non-ASCII characters left in docs/data."""
    payload = {"scenarios": {"s": {"includedSets": ["Morgul Nazgûl"],
                                   "quest": {"stages": [{"advance": "no Nazgûl"}]}}}}
    out = _corr.fold_payload(payload)
    assert out["scenarios"]["s"]["includedSets"] == ["Morgul Nazgul"]
    assert out["scenarios"]["s"]["quest"]["stages"][0]["advance"] == "no Nazgul"


# --- Task 6/R5: the card-image URL prefix is pinned beside the card TSV ----

def test_build_outputs_writes_image_prefix_from_meta():
    """build_card_data.py's main() reads image_prefix from the pin file and
    passes it through `meta`; build_outputs() copies it into index.json as
    imagePrefix, top level beside source/generated (see quest_catalog.py's
    image_prefix() / quest_catalog.js's imagePrefix(), which read this key
    back)."""
    with open(FIXTURE, encoding="utf-8") as f:
        out = b.build_outputs(f, meta={
            "generated": "2026-07-24", "source": "fixture",
            "imagePrefix": "https://dragncards-lotrlcg.s3.amazonaws.com/cards/English/"})
    assert (out["index"]["imagePrefix"]
            == "https://dragncards-lotrlcg.s3.amazonaws.com/cards/English/")


def test_build_outputs_image_prefix_defaults_to_none_without_meta():
    """A caller that doesn't pass imagePrefix (existing fixtures, a legacy
    pin file with no image_prefix= line) gets None rather than a missing key
    or a crash - same absent-tolerant posture as every other optional field
    build_outputs merges in."""
    out = build()
    assert out["index"]["imagePrefix"] is None
    out2 = b.build_outputs(open(FIXTURE, encoding="utf-8"))
    assert out2["index"]["imagePrefix"] is None


def test_read_pin_parses_sha_and_image_prefix(tmp_path, monkeypatch):
    pin = tmp_path / "cardDb.SOURCE.txt"
    pin.write_text(
        "url=https://raw.githubusercontent.com/seastan/dragncards-lotrlcg-plugin/{sha}/tsvs/cardDb.tsv\n"
        "sha=deadbeef\n"
        "image_prefix=https://dragncards-lotrlcg.s3.amazonaws.com/cards/English/\n",
        encoding="utf-8")
    monkeypatch.setattr(b, "SOURCE_FILE", str(pin))
    assert b._read_pin() == (
        "deadbeef", "https://dragncards-lotrlcg.s3.amazonaws.com/cards/English/")


def test_read_pin_tolerates_a_legacy_file_with_no_image_prefix_line(tmp_path, monkeypatch):
    pin = tmp_path / "cardDb.SOURCE.txt"
    pin.write_text("url=https://example.com/{sha}\nsha=deadbeef\n", encoding="utf-8")
    monkeypatch.setattr(b, "SOURCE_FILE", str(pin))
    assert b._read_pin() == ("deadbeef", None)


def test_read_pin_still_raises_when_sha_is_missing(tmp_path, monkeypatch):
    pin = tmp_path / "cardDb.SOURCE.txt"
    pin.write_text("url=https://example.com/{sha}\n", encoding="utf-8")
    monkeypatch.setattr(b, "SOURCE_FILE", str(pin))
    with pytest.raises(SystemExit):
        b._read_pin()


class _FakeResponse:
    """Same shape as test_icons.py's fake urlopen response: a context
    manager whose .read() returns the scripted bytes."""
    def __init__(self, data):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._data


def test_fetch_image_prefix_picks_english_over_default(monkeypatch):
    payload = _json.dumps({"imageUrlPrefix": {
        "Default": "https://example.com/cards/Default/",
        "English": "https://example.com/cards/English/",
    }}).encode("utf-8")
    monkeypatch.setattr(b.urllib.request, "urlopen", lambda req: _FakeResponse(payload))
    assert b._fetch_image_prefix("deadbeef") == "https://example.com/cards/English/"


def test_fetch_image_prefix_falls_back_to_default_when_english_absent(monkeypatch):
    payload = _json.dumps({"imageUrlPrefix": {
        "Default": "https://example.com/cards/Default/",
    }}).encode("utf-8")
    monkeypatch.setattr(b.urllib.request, "urlopen", lambda req: _FakeResponse(payload))
    assert b._fetch_image_prefix("deadbeef") == "https://example.com/cards/Default/"


def test_fetch_image_prefix_raises_clean_systemexit_on_fetch_failure(monkeypatch):
    def _boom(req):
        raise b.urllib.error.URLError("no network")
    monkeypatch.setattr(b.urllib.request, "urlopen", _boom)
    with pytest.raises(SystemExit):
        b._fetch_image_prefix("deadbeef")


def test_fetch_image_prefix_raises_when_payload_has_neither_key(monkeypatch):
    payload = _json.dumps({"imageUrlPrefix": {}}).encode("utf-8")
    monkeypatch.setattr(b.urllib.request, "urlopen", lambda req: _FakeResponse(payload))
    with pytest.raises(SystemExit):
        b._fetch_image_prefix("deadbeef")


def test_refresh_pin_writes_sha_and_image_prefix_and_read_pin_round_trips(tmp_path, monkeypatch):
    """--refresh rewrites BOTH the sha= and image_prefix= lines in one pass -
    the pin's plain (non-refresh) read makes no network call at all, only
    --refresh does the two fetches (HEAD sha, then that sha's
    imageUrlPrefix.json)."""
    pin = tmp_path / "cardDb.SOURCE.txt"
    monkeypatch.setattr(b, "SOURCE_FILE", str(pin))

    def fake_urlopen(req):
        url = req.full_url if hasattr(req, "full_url") else req
        if "commits/main" in url:
            return _FakeResponse(b"c0ffee" * 6)
        if "imageUrlPrefix.json" in url:
            return _FakeResponse(_json.dumps({"imageUrlPrefix": {
                "Default": "https://example.com/cards/Default/",
                "English": "https://example.com/cards/English/",
            }}).encode("utf-8"))
        raise AssertionError("unexpected URL: %s" % url)

    monkeypatch.setattr(b.urllib.request, "urlopen", fake_urlopen)

    sha, image_prefix = b._refresh_pin()

    assert sha == "c0ffee" * 6
    assert image_prefix == "https://example.com/cards/English/"
    content = pin.read_text(encoding="utf-8")
    assert ("sha=%s" % sha) in content
    assert ("image_prefix=%s" % image_prefix) in content
    # And the file it just wrote round-trips through the plain reader.
    assert b._read_pin() == (sha, image_prefix)
