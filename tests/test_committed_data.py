"""The derived-data-in-git policy, as tests.

CLAUDE.md's "What may be committed" draws the line at **verbatim vs derived**:
the compiled card DB is verbatim third-party card text and stays generated +
gitignored, while `tools/data/enrichment.json` (aggregated encounter-set names)
and `docs/data/tips.json` (summaries this project wrote itself) are committed
so no build ever has to re-scrape a slow third-party site. These tests are the
guard on both halves of that: the .gitignore split still classifies each path
correctly, the two committed artifacts really do contain only derived data
(structurally - they have no room for card text), and neither fetcher touches
the network when its output is already there.

Everything here is host-only and offline: the fetcher checks deliberately
exercise the early-exit path, which returns before any URL is opened.
"""
import json, os, shutil, subprocess, sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build_card_data
import build_hob_enrichment
import build_tips

ENRICHMENT = os.path.join(ROOT, "tools", "data", "enrichment.json")
TIPS = os.path.join(ROOT, "docs", "data", "tips.json")


def _check_ignore(rel_path):
    """True if git ignores `rel_path`, False if it doesn't; skips the test
    when git isn't usable here (`git check-ignore` exits 0 for ignored, 1 for
    not-ignored, and anything else means it couldn't answer)."""
    if shutil.which("git") is None:
        pytest.skip("git not available")
    proc = subprocess.run(["git", "check-ignore", "-q", "--no-index", rel_path],
                          cwd=ROOT, capture_output=True)
    if proc.returncode not in (0, 1):
        pytest.skip("git check-ignore unavailable: %s" % proc.stderr.decode()[:200])
    return proc.returncode == 0


# --- the .gitignore split ---------------------------------------------------

def test_derived_data_is_not_ignored():
    """The two committed derived artifacts must stay trackable. If a future
    edit restores a blanket `docs/data/` ignore, tips.json silently vanishes
    from the Pages artifact and the Tips button goes dead everywhere."""
    assert not _check_ignore("docs/data/tips.json")
    assert not _check_ignore("tools/data/enrichment.json")
    # The pin file is a URL + sha, not card data - CI needs it in the checkout
    # (build_card_data.py exits with "No pin file" without it).
    assert not _check_ignore("tools/data/cardDb.SOURCE.txt")


def test_verbatim_data_is_still_ignored():
    """The allow-list must stay a list, not a hole: everything verbatim -
    the compiled card DB, the rasterized icon masks, and both raw
    third-party response caches - stays out of git."""
    for path in ("docs/data/index.json",
                 "docs/data/rules.json",
                 "docs/data/icons.json",
                 "docs/data/scenarios/passage-through-mirkwood.json",
                 "docs/data/players/index.json",
                 "tools/data/hob_cache/passage-through-mirkwood.json",
                 "tools/data/tips_cache/passage-through-mirkwood.html"):
        assert _check_ignore(path), path


# --- tools/data/enrichment.json: aggregated set names, nothing else ---------

def test_committed_enrichment_holds_only_set_names():
    """Structural proof that the committed enrichment carries no printed card
    text: the only per-scenario key is "includedSets", and every value in it
    is a bare encounter-set NAME - short, single-line, no sentence
    punctuation. Card text could not survive this shape."""
    with open(ENRICHMENT, encoding="utf-8") as f:
        data = json.load(f)
    assert set(data) == {"generated", "source", "scenarios"}
    assert data["scenarios"], "committed enrichment is empty"
    for slug, entry in data["scenarios"].items():
        assert set(entry) == {"includedSets"}, (slug, sorted(entry))
        assert entry["includedSets"], slug
        for name in entry["includedSets"]:
            assert isinstance(name, str) and name.strip() == name, (slug, name)
            assert 0 < len(name) <= 60, (slug, name)
            assert "\n" not in name and not name.endswith((".", "!", "?")), (slug, name)


def test_committed_enrichment_loads_and_merges_without_network():
    """build_card_data's single CI pass reads the committed file straight off
    disk (this is the whole reason the Hall of Beorn fetch step could leave
    the workflow) and merges it into the catalog it compiles."""
    loaded = build_card_data._load_enrichment(ENRICHMENT)
    assert loaded is not None and loaded["scenarios"]

    slug, entry = sorted(loaded["scenarios"].items())[0]
    with open(os.path.join(os.path.dirname(__file__), "fixtures",
                           "cardDb_sample.tsv"), encoding="utf-8") as f:
        out = build_card_data.build_outputs(
            f, enrichment={"scenarios": {"passage-through-mirkwood": entry}})
    merged = out["scenarios"]["passage-through-mirkwood"]
    assert merged["includedSets"] == entry["includedSets"]
    idx = {s["slug"]: s for s in out["index"]["scenarios"]}
    assert idx["passage-through-mirkwood"]["gatherCount"] == len(entry["includedSets"])
    assert "hallofbeorn.com" in out["index"]["source"]


# --- docs/data/tips.json: our own words, already through the quality gate ---

def test_committed_tips_pass_the_same_gate_as_a_fresh_build():
    """Every tip actually in git must still satisfy the gate its source was
    held to, plus the length/count caps - the copyright + quality posture is
    enforced on the committed artifact, not just on the build that produced
    it (the file outlives the run, and a hand-edit would otherwise go
    unchecked).

    The gate is is_valid_distilled_tip, not is_useful_tip: everything shipped
    today comes from the committed distillation, which is authored prose
    rather than sentences lifted out of an article. is_useful_tip stays the
    gate for the quests/*.md path (see build_tips.build) and is exercised by
    its own tests - see is_valid_distilled_tip's docstring for why running it
    over authored tips rejects a third of them for no good reason."""
    with open(TIPS, encoding="utf-8") as f:
        data = json.load(f)
    assert set(data) == {"generated", "source", "scenarios"}
    assert data["scenarios"], "committed tips file is empty"
    for slug, entry in data["scenarios"].items():
        assert set(entry) == {"attribution", "general", "stages"}, (slug, sorted(entry))
        assert entry["attribution"].get("name"), slug
        tips = list(entry["general"])
        for stage_tips in entry["stages"].values():
            tips.extend(stage_tips)
        assert tips, slug
        assert len(entry["general"]) <= build_tips.MAX_TIPS, slug
        for tip in tips:
            assert build_tips.is_valid_distilled_tip(tip), (slug, tip)
            assert len(tip) <= build_tips.MAX_LEN, (slug, tip)
            # The device's bitmap8 glyph table is printable ASCII only.
            assert all(32 <= ord(c) < 127 for c in tip), (slug, tip)


# --- neither fetcher touches the network when its output exists -------------

@pytest.mark.parametrize("module, out_name", [
    (build_hob_enrichment, "enrichment.json"),
    (build_tips, "tips.json"),
])
def test_fetcher_is_a_noop_when_output_already_exists(module, out_name, tmp_path):
    """A plain run with the committed file present must exit 0 having fetched
    nothing and rewritten nothing - the guard that keeps a clean checkout (or
    a Pages build) from re-scraping. --index deliberately points at a path
    that does NOT exist: reaching the fetch would raise SystemExit there, so
    a clean 0 proves the early exit fired first."""
    out = tmp_path / out_name
    out.write_text('{"scenarios": {}}', encoding="utf-8")
    before = out.read_text(encoding="utf-8")

    assert module.main(["--out", str(out), "--index", str(tmp_path / "absent.json")]) == 0
    assert out.read_text(encoding="utf-8") == before


@pytest.mark.parametrize("module", [build_hob_enrichment, build_tips])
def test_refresh_bypasses_the_guard(module, tmp_path):
    """--refresh is the documented way back to a real rebuild, so it must get
    past the early exit - here it reaches (and trips) the missing-index
    SystemExit that the no-op path returns before."""
    out = tmp_path / "out.json"
    out.write_text('{"scenarios": {}}', encoding="utf-8")
    with pytest.raises(SystemExit):
        module.main(["--out", str(out), "--refresh",
                     "--index", str(tmp_path / "absent.json")])


def test_every_shipped_string_is_device_renderable():
    """The device font (bitmap8) has 82 glyphs and no accented characters, and
    BITMAP8_W.get(c, 4) returns 4 for anything absent - so a curly quote or a
    circumflex passes every host layout test and only breaks on hardware.

    Before tools/corrections.py's fold, 75 of 145 pickable scenarios carried
    non-ASCII in strings the HUD renders, including the pickable ALeP scenario
    "The Horse Lord's Ire" and the pack name shown on Scenario Options.
    Guards the whole emitted catalog, not just scenario names.
    """
    import glob
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files = (glob.glob(os.path.join(root, "docs", "data", "*.json"))
             + glob.glob(os.path.join(root, "docs", "data", "scenarios", "*.json"))
             + glob.glob(os.path.join(root, "docs", "data", "players", "*.json")))
    if not files:
        return          # generated catalog absent on a bare tree
    offenders = []

    def walk(obj, where):
        if isinstance(obj, str):
            for ch in obj:
                if ord(ch) > 126 or (ord(ch) < 32 and ch not in "\n"):
                    offenders.append((where, ch, obj[:60]))
                    return
        elif isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, where)
        elif isinstance(obj, list):
            for v in obj:
                walk(v, where)

    for path in files:
        with open(path, encoding="utf-8") as fh:
            walk(json.load(fh), os.path.basename(path))
    assert not offenders, ("non-renderable characters in docs/data: %s"
                           % offenders[:6])


def test_the_two_upstream_split_scenarios_are_merged():
    """Upstream attached each scenario's Quest cards to a misspelled encounter
    set, leaving the correct spelling as a 0-stage stub the picker hides. The
    committed corrections table unifies them.

    The Anduin case also fixed a live bug: _has_nightmare probes
    slugify(encounterSet + " - Nightmare"), so before the Nightmare set was
    renamed too, the PICKABLE Core Set quest advertised no Nightmare mode while
    the invisible stub claimed one.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    idx_path = os.path.join(root, "docs", "data", "index.json")
    if not os.path.exists(idx_path):
        return
    with open(idx_path, encoding="utf-8") as fh:
        scns = json.load(fh)["scenarios"]
    names = [s["name"] for s in scns]
    assert "Journey Along the Anduin" not in names
    assert "The Caves of Nibin-Dum" in names
    anduin = [s for s in scns if s["name"] == "Journey Down the Anduin"]
    assert len(anduin) == 1
    assert anduin[0]["stageCount"] == 3
    assert anduin[0]["hasNightmare"] is True
    caves = [s for s in scns if s["slug"] == "the-caves-of-nibin-dum"]
    assert len(caves) == 1 and caves[0]["stageCount"] == 4
