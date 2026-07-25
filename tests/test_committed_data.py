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
    """Every tip actually in git must still satisfy is_useful_tip and the
    length/count caps - the copyright + quality posture is enforced on the
    committed artifact, not just on the build that produced it (the file
    outlives the run, and a hand-edit would otherwise go unchecked)."""
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
            assert build_tips.is_useful_tip(tip), (slug, tip)
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
