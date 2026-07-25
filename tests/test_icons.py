import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import build_icons

SQUARE = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">
<rect x="0" y="0" width="10" height="10" fill="black"/></svg>'''
HALF = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">
<rect x="0" y="0" width="5" height="10" fill="black"/></svg>'''
# Non-square viewBox (2:1), fully black - exercises the "fit and centre"
# requirement (Task 1 interface note). At size=8, scale = min(8/20, 8/10) =
# 0.4 -> an 8x4 black band centred vertically (rows 2-5 ink, rows 0-1/6-7
# blank), same as cairosvg's own preserveAspectRatio="xMidYMid meet" default.
WIDE = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 10">
<rect x="0" y="0" width="20" height="10" fill="black"/></svg>'''


def test_full_square_sets_every_bit():
    mask = build_icons.svg_to_mask(SQUARE, size=8)
    assert len(mask) == 8
    assert all(row == 0b11111111 for row in mask)


def test_left_half_sets_only_high_bits():
    mask = build_icons.svg_to_mask(HALF, size=8)
    assert all(row == 0b11110000 for row in mask), [bin(r) for r in mask]


def test_blank_svg_is_all_zero():
    blank = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>'
    assert build_icons.svg_to_mask(blank, size=8) == [0] * 8


def test_non_square_viewbox_is_fit_and_centered():
    mask = build_icons.svg_to_mask(WIDE, size=8)
    assert mask == [
        0b00000000, 0b00000000,
        0b11111111, 0b11111111, 0b11111111, 0b11111111,
        0b00000000, 0b00000000,
    ], [bin(r) for r in mask]


def test_build_writes_expected_shape(tmp_path):
    assets = tmp_path / "assets"
    (assets / "encounter sets" / "core").mkdir(parents=True)
    (assets / "expansion symbols").mkdir(parents=True)
    (assets / "encounter sets" / "core" / "passage_through_mirkwood.svg").write_bytes(SQUARE)
    (assets / "expansion symbols" / "core_set.svg").write_bytes(HALF)
    out = tmp_path / "icons.json"

    summary = build_icons.build(str(assets), str(out))

    assert summary["count"] == 2
    assert out.exists()
    import json
    data = json.loads(out.read_text())
    assert data["size"] == 24
    assert set(data["icons"]) == {"passage-through-mirkwood", "core-set"}
    assert len(data["icons"]["passage-through-mirkwood"]) == 24
    assert isinstance(data["source"], str) and data["source"]
    assert isinstance(data["generated"], str) and data["generated"]


def test_build_encounter_set_wins_collision(tmp_path, capsys):
    assets = tmp_path / "assets"
    (assets / "encounter sets" / "core").mkdir(parents=True)
    (assets / "expansion symbols").mkdir(parents=True)
    # Same slug ("clash") in both namespaces: full-black square in the
    # expansion-symbols copy, left-half in the encounter-sets copy - if
    # encounter sets win, the emitted mask must be the HALF pattern.
    (assets / "encounter sets" / "core" / "clash.svg").write_bytes(HALF)
    (assets / "expansion symbols" / "clash.svg").write_bytes(SQUARE)
    out = tmp_path / "icons.json"

    summary = build_icons.build(str(assets), str(out), size=8)

    assert summary["collisions"] == 1
    import json
    data = json.loads(out.read_text())
    assert data["icons"]["clash"] == [0b11110000] * 8
    assert "clash" in capsys.readouterr().out.lower()


def test_build_degrades_gracefully_when_assets_missing(tmp_path, capsys):
    out = tmp_path / "icons.json"
    summary = build_icons.build(str(tmp_path / "no-such-pack"), str(out))
    assert summary["count"] == 0
    import json
    data = json.loads(out.read_text())
    assert data["icons"] == {}
    assert "not found" in capsys.readouterr().out.lower()


# --- pinned-fetch path: tarball member filtering (no network) ---------

def _make_tarball(members):
    """Build an in-memory gzip tarball (bytes) with a single top-level
    "<repo>-<sha>/" directory component, matching GitHub codeload's layout
    - members is {relative_path_under_that_prefix: content_bytes}."""
    import io as _io
    import tarfile as _tarfile
    buf = _io.BytesIO()
    with _tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel, content in members.items():
            info = _tarfile.TarInfo(name="lotr-lcg-assets-deadbeef/" + rel)
            info.size = len(content)
            tar.addfile(info, _io.BytesIO(content))
    return buf.getvalue()


def test_iter_tarball_svgs_filters_to_icon_subtrees_only():
    tar_bytes = _make_tarball({
        "icons/encounter sets/core/passage_through_mirkwood.svg": SQUARE,
        "icons/expansion symbols/core_set.svg": HALF,
        "icons/game icons/willpower.svg": SQUARE,  # excluded category
        "fonts/some-font.svg": SQUARE,              # excluded top-level dir
        "README.md": b"not an svg",                 # wrong extension
    })
    found = list(build_icons._iter_tarball_svgs(tar_bytes))
    names = [name for _category, name, _bytes in found]
    assert names == [
        "icons/expansion symbols/core_set.svg",
        "icons/encounter sets/core/passage_through_mirkwood.svg",
    ], names


def test_iter_tarball_svgs_orders_expansion_symbols_before_encounter_sets():
    # Deliberately constructed so naive tar order would put encounter sets
    # first - _iter_tarball_svgs must still yield expansion symbols first
    # so _assemble()'s "encounter sets win" collision rule holds for the
    # pinned-fetch path exactly as it does for the local-pack path.
    tar_bytes = _make_tarball({
        "icons/encounter sets/core/clash.svg": HALF,
        "icons/expansion symbols/clash.svg": SQUARE,
    })
    categories = [category for category, _name, _bytes in build_icons._iter_tarball_svgs(tar_bytes)]
    assert categories == ["expansion_symbols", "encounter_sets"]


def test_fetch_and_build_style_assembly_matches_local_pack_build(tmp_path):
    # Same two SVGs, once via a local directory (the --assets path) and once
    # via an equivalent in-memory tarball (the pinned-fetch path) - both
    # must produce the identical icons dict (slugs + masks + collision
    # count), which is the property tools/build_icons.py's real pinned
    # fetch was verified against (see .superpowers/sdd/bicons-fix-report.md).
    assets = tmp_path / "assets"
    (assets / "encounter sets" / "core").mkdir(parents=True)
    (assets / "expansion symbols").mkdir(parents=True)
    (assets / "encounter sets" / "core" / "passage_through_mirkwood.svg").write_bytes(SQUARE)
    (assets / "expansion symbols" / "core_set.svg").write_bytes(HALF)
    local_icons, local_counts = build_icons._assemble(
        build_icons._iter_local_svgs(str(assets)), size=8)

    tar_bytes = _make_tarball({
        "icons/encounter sets/core/passage_through_mirkwood.svg": SQUARE,
        "icons/expansion symbols/core_set.svg": HALF,
    })
    tar_icons, tar_counts = build_icons._assemble(
        build_icons._iter_tarball_svgs(tar_bytes), size=8)

    assert local_icons == tar_icons
    assert local_counts == tar_counts


def test_fetch_and_build_writes_source_naming_repo_and_sha(tmp_path, monkeypatch):
    tar_bytes = _make_tarball({
        "icons/expansion symbols/core_set.svg": HALF,
    })

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return tar_bytes

    monkeypatch.setattr(build_icons.urllib.request, "urlopen", lambda url: _FakeResponse())
    out = tmp_path / "icons.json"

    summary = build_icons.fetch_and_build("deadbeef" * 5, out_path=str(out), size=8)

    assert summary["count"] == 1
    import json
    data = json.loads(out.read_text())
    assert build_icons.REPO in data["source"]
    assert "deadbeef" * 5 in data["source"]


def test_fetch_and_build_raises_clean_systemexit_on_fetch_failure(tmp_path, monkeypatch):
    import urllib.error

    def _boom(url):
        raise urllib.error.URLError("simulated network failure")

    monkeypatch.setattr(build_icons.urllib.request, "urlopen", _boom)
    out = tmp_path / "icons.json"

    try:
        build_icons.fetch_and_build("badsha", out_path=str(out))
        assert False, "expected SystemExit"
    except SystemExit as e:
        assert "badsha" in str(e.code)
    assert not out.exists()
