"""The LONG form of the distilled tips - tools/data/tips_long.json, and the
tablet-only docs/tablet/data/tips_full.json that build_tips.py compiles it to.

The short tips exist at the length the Presto's 240x240 screen allows: one
clause, 140 chars, no connective tissue. That was a trade, and the tablet does
not have to pay it, so the same advice is written twice - once terse, once at
the length it wants - and this file guards the seams between them.
"""
import json, os, sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import build_tips

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LONG_SRC = os.path.join(ROOT, "tools", "data", "tips_long.json")
DISTILLED = os.path.join(ROOT, "tools", "data", "tips_distilled.json")

_LONG = ("Two numbers matter more here than staying low in general, because the "
         "two worst enemies in this encounter deck both have high engagement "
         "costs and stay in the staging area until your threat reaches them.")


def _write(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    return str(path)


def _index(*slugs):
    return {"scenarios": [
        {"slug": s, "name": s.replace("-", " ").title(), "kind": "quest",
         "stageCount": 2} for s in slugs]}


def _distilled(**scenarios):
    return {"generated": "2026-07-25", "source": "test", "scenarios": scenarios}


def _entry(general, stages=None, url="https://example.invalid/a"):
    return {"attribution": {"name": build_tips.SOURCE_NAME, "url": url},
            "general": list(general), "stages": dict(stages or {})}


# -- the gate ---------------------------------------------------------------

def test_a_long_tip_has_to_earn_the_name():
    """is_valid_long_tip is is_valid_distilled_tip with the ceiling raised and
    a floor added. The ceiling is the point: 140 chars is the Presto's screen
    talking, not the advice's natural length. The floor is the trap - a "long"
    tip that is one clause is the short one pasted into the wrong file, and
    pairing it would ship the terse version twice under two names."""
    assert build_tips.is_valid_long_tip(_LONG)
    # Over the short form's 140 but well under the long ceiling - the whole
    # reason this gate is separate.
    assert len(_LONG) > build_tips.MAX_LEN
    assert not build_tips.is_valid_distilled_tip(_LONG)

    assert not build_tips.is_valid_long_tip("Have a defender.")   # too few words
    assert not build_tips.is_valid_long_tip("x" * 400)            # over ceiling
    assert not build_tips.is_valid_long_tip(_LONG.rstrip(".") )   # not a sentence
    assert not build_tips.is_valid_long_tip("")
    assert not build_tips.is_valid_long_tip(None)


def test_the_long_file_is_optional_and_never_fatal():
    """Same contract as load_distillation: absent or corrupt degrades to "no
    long form", which the client already handles tip by tip. That is what lets
    this land scenario by scenario instead of as a flag day."""
    assert build_tips.load_long("does-not-exist.json") == {}


def test_an_invalid_long_tip_is_dropped_not_fatal(tmp_path):
    """Dropping one is safe here in a way it would not be under positional
    pairing: the key is the short tip's own text, so removing an entry cannot
    shift any other."""
    path = _write(tmp_path / "long.json", {"scenarios": {"s": {
        "general": {"Short one.": "too short", "Keeper.": _LONG}}}})
    loaded = build_tips.load_long(path)
    assert loaded["s"]["general"] == {"Keeper.": _LONG}


# -- pairing ----------------------------------------------------------------

def test_the_output_is_positional_with_null_where_there_is_no_long_form():
    """The SOURCE is keyed by short text - that is what a human edits, and it
    survives a reorder. The OUTPUT is positional, because that is what a client
    wants: index into it beside the tips array it already has, and take the
    short tip wherever the slot is null. The two shapes cannot drift, because
    one build writes both from the same source in one pass."""
    entry = {"general": ["The first short one.", "The second short one."],
             "stages": {"1": ["A stage tip here."]}}
    long_entry = {"general": {"The second short one.": _LONG}, "stages": {}}
    orphans = []
    out = build_tips._long_arrays(entry, long_entry, orphans, "s")
    assert out["general"] == [None, _LONG]
    assert out["stages"] == {"1": [None]}
    assert orphans == []


def test_a_long_tip_whose_short_tip_moved_on_is_reported_as_an_orphan():
    """An orphan means the short tip was reworded or removed, so its long form
    now describes something that is not on screen. Reported, never fatal: it
    costs that one tip its long form, which is the degrade the whole path is
    built to survive."""
    entry = {"general": ["The current wording of it."], "stages": {}}
    long_entry = {"general": {"An older wording of it.": _LONG}, "stages": {}}
    orphans = []
    out = build_tips._long_arrays(entry, long_entry, orphans, "s")
    assert out is None                      # nothing paired, so nothing to emit
    assert orphans == [("s", "general", "An older wording of it.")]


def test_a_scenario_with_no_long_form_at_all_is_absent_from_the_output():
    entry = {"general": ["Only the short one."], "stages": {}}
    assert build_tips._long_arrays(entry, None, [], "s") is None


# -- build ------------------------------------------------------------------

def test_build_writes_the_long_file_only_when_asked(tmp_path):
    """REGRESSION: build() used to default long_out_path to the real
    docs/tablet/data/tips_full.json. Every test that calls build() passes a tmp
    `out_path` - and each of those runs was overwriting the repo's own
    committed long file with whatever fixture it happened to be using. The long
    output is opt-in at the call site now; main() passes the real path."""
    index_path = _write(tmp_path / "index.json", _index("s"))
    dist_path = _write(tmp_path / "d.json",
                       _distilled(**{"s": _entry(["Only the short one here."])}))
    out_path = tmp_path / "tips.json"
    stray = tmp_path / "tips_full.json"

    build_tips.build(index_path, str(out_path), distilled_path=dist_path,
                     notes_dir=str(tmp_path / "none"))
    assert not stray.exists(), "build() must not write a long file unasked"


def test_the_long_form_does_not_change_tips_json(tmp_path):
    """The device's file is the contract this must not touch: same scenarios,
    same terse strings, whether or not a long form exists for any of them."""
    index_path = _write(tmp_path / "index.json", _index("s"))
    dist_path = _write(tmp_path / "d.json", _distilled(**{
        "s": _entry(["The first short one.", "The second short one."],
                    {"1": ["A stage tip here."]})}))
    long_path = _write(tmp_path / "long.json", {"scenarios": {
        "s": {"general": {"The second short one.": _LONG}, "stages": {}}}})
    notes = str(tmp_path / "none")

    without = tmp_path / "a.json"
    build_tips.build(index_path, str(without), distilled_path=dist_path,
                     notes_dir=notes)
    with_long = tmp_path / "b.json"
    build_tips.build(index_path, str(with_long), distilled_path=dist_path,
                     notes_dir=notes, long_path=long_path,
                     long_out_path=str(tmp_path / "full.json"))

    a = json.loads(without.read_text(encoding="utf-8"))
    b = json.loads(with_long.read_text(encoding="utf-8"))
    assert a["scenarios"] == b["scenarios"]

    full = json.loads((tmp_path / "full.json").read_text(encoding="utf-8"))
    assert full["scenarios"]["s"]["general"] == [None, _LONG]


# -- the committed corpus ---------------------------------------------------

def test_every_committed_long_tip_pairs_with_a_short_one():
    """No orphans in the repo. A key here that matches no distilled tip is a
    long form describing advice the app no longer gives."""
    if not os.path.exists(LONG_SRC):
        return                                  # not authored yet - fine
    long_src = json.load(open(LONG_SRC, encoding="utf-8"))["scenarios"]
    distilled = json.load(open(DISTILLED, encoding="utf-8"))["scenarios"]

    orphans = []
    for slug, entry in long_src.items():
        short = distilled.get(slug)
        assert short, "long tips for a scenario the distillation has never heard of: %s" % slug
        for key in (entry.get("general") or {}):
            if key not in (short.get("general") or []):
                orphans.append((slug, "general", key))
        for stage, pairs in (entry.get("stages") or {}).items():
            have = (short.get("stages") or {}).get(str(stage)) or []
            for key in pairs:
                if key not in have:
                    orphans.append((slug, "stage " + str(stage), key))
    assert not orphans, "orphaned long tips: %r" % (orphans[:5],)


def test_every_committed_long_tip_passes_its_own_gate():
    """Authored, fact-checked, and still has to clear the gate - the same rule
    the distillation lives under."""
    if not os.path.exists(LONG_SRC):
        return
    long_src = json.load(open(LONG_SRC, encoding="utf-8"))["scenarios"]
    bad = []
    for slug, entry in long_src.items():
        scopes = [("general", entry.get("general") or {})]
        scopes += [("stage " + k, v) for k, v in (entry.get("stages") or {}).items()]
        for scope, pairs in scopes:
            for short, long_text in pairs.items():
                if not build_tips.is_valid_long_tip(long_text):
                    bad.append((slug, scope, long_text[:60]))
    assert not bad, "long tips failing is_valid_long_tip: %r" % (bad[:5],)
