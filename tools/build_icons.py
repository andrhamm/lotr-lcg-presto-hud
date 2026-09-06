"""Rasterize the community LOTR-LCG SVG icon pack (encounter-set + expansion
symbols) into 24x24 1-bit bitmasks, emitted as generated data at
docs/data/icons.json - never committed, same posture as build_card_data.py's
output. See docs/superpowers/plans/2026-07-24-set-icons.md, Task 1.

The pack is fetched from its pinned upstream (KevBelisle/lotr-lcg-assets,
see tools/data/icons.SOURCE.txt) the same way build_card_data.py fetches the
DragnCards TSV: a normal run downloads the repo tarball at the pinned commit
sha and reads the SVGs straight out of it in memory with tarfile - the pack
also ships fonts/ and product-images/ we never want on disk, so the whole
archive is never extracted. --refresh re-resolves upstream HEAD via the
GitHub API and rewrites the pin, mirroring build_card_data.py exactly.

--assets PATH is an override that reads a local directory instead (useful
offline); it degrades gracefully - logs and writes an empty icons.json -
when that path doesn't exist, so every icon_slot() falls back to its
placeholder glyph rather than erroring. A pinned-fetch failure (no network,
a bad sha) or a rasterization failure (neither Pillow nor a usable SVG
backend installed) raises a friendly SystemExit instead of a traceback; the
Pages workflow marks that build step continue-on-error since icons are
optional (card data is the critical artifact - see CLAUDE.md's Card data
section).

The same pass over the source (tarball or --assets dir) also writes every
SVG to --svg-out (default docs/data/icons/svg/<slug>.svg, same
gitignored/regenerated posture, same collision rule as icons.json) for
consumers that want the vector art directly instead of the rasterized
mask; --svg-out "" disables the export. Each exported SVG is recoloured
(see _recolor_svg) from the pack's fill="currentColor" - meant for an
inline SVG that inherits the surrounding page's text color, which an <img>
cannot do - to the palette gold both twins use for set icons, otherwise
byte-identical to the source."""
import argparse
import datetime
import glob
import io
import json
import os
import re
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.request

try:
    import cairosvg
except ImportError:  # pragma: no cover - exercised only where cairosvg is absent
    cairosvg = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover - exercised only where Pillow is absent
    Image = None

DEFAULT_OUT = os.path.join("docs", "data", "icons.json")
DEFAULT_SVG_OUT = os.path.join("docs", "data", "icons", "svg")
SIZE = 24

# Palette gold both twins use for set icons (pal.gold = [214, 180, 110],
# docs/js/ui.js) - see _recolor_svg.
SVG_FILL = "rgb(214,180,110)"
_CURRENT_COLOR_RE = re.compile(rb"currentColor")

REPO = "KevBelisle/lotr-lcg-assets"
TARBALL = "https://codeload.github.com/KevBelisle/lotr-lcg-assets/tar.gz/{sha}"
API = "https://api.github.com/repos/KevBelisle/lotr-lcg-assets/commits/main"
SOURCE_FILE = os.path.join(os.path.dirname(__file__), "data", "icons.SOURCE.txt")

# Only these two subtrees of the pack are ever read; icons/game icons/,
# fonts/, product-images/, etc. are ignored (see module docstring).
CATEGORY_DIRS = (("expansion_symbols", "icons/expansion symbols/"),
                  ("encounter_sets", "icons/encounter sets/"))

# Community-recreated FFG symbols - same posture as card text (see
# tools/build_card_data.py's DISCLAIMER): generated-only, never tracked.
DISCLAIMER = ("Unofficial companion. Not affiliated with or endorsed by Fantasy "
              "Flight Games. The Lord of the Rings is a trademark of Middle-earth "
              "Enterprises. Icons are community recreations of FFG symbols.")


def _rasterize_cairosvg(svg_bytes, size):
    return cairosvg.svg2png(bytestring=svg_bytes, output_width=size,
                             output_height=size, background_color="white")


def _rasterize_rsvg(svg_bytes, size):
    """Fallback when cairosvg isn't importable: shell out to rsvg-convert.
    -a/--keep-aspect-ratio makes rsvg-convert pick its own output canvas size
    (the "fit within size x size" computation) rather than stretching to
    size x size, so the result is pasted centred onto a size x size white
    canvas here - replicating cairosvg's built-in preserveAspectRatio
    centring (verified empirically: both back ends produce the identical
    fit-and-centre result for a non-square viewBox)."""
    with tempfile.TemporaryDirectory() as td:
        svg_path = os.path.join(td, "in.svg")
        png_path = os.path.join(td, "out.png")
        with open(svg_path, "wb") as f:
            f.write(svg_bytes)
        try:
            subprocess.run(
                ["rsvg-convert", "-w", str(size), "-h", str(size), "-a",
                 "-o", png_path, svg_path],
                check=True, capture_output=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            raise RuntimeError(
                "svg_to_mask: neither cairosvg nor rsvg-convert is usable (%r)"
                % (e,))
        rendered = Image.open(png_path).convert("RGBA")
        canvas = Image.new("RGBA", (size, size), (255, 255, 255, 255))
        ox = (size - rendered.width) // 2
        oy = (size - rendered.height) // 2
        canvas.paste(rendered, (ox, oy), rendered)
        buf = io.BytesIO()
        canvas.convert("RGB").save(buf, format="PNG")
        return buf.getvalue()


def svg_to_mask(svg_bytes, size=24, threshold=128):
    """Rasterize one SVG to a size x size 1-bit mask: [int, ...] of length
    `size`, MSB-first left-to-right per row - the exact format ui/icons.py's
    stat icons already use, so icons.draw()/drawIcon() work unmodified on
    these masks too.

    Fits the SVG's viewBox within the square and centres it (a non-square
    viewBox is letterboxed, never stretched): cairosvg does this itself via
    the SVG default preserveAspectRatio="xMidYMid meet" when asked for a
    fixed output_width/output_height; the rsvg-convert fallback replicates
    it by hand (see _rasterize_rsvg). Composited on a white background,
    greyscaled, then thresholded - a pixel darker than `threshold` is ink.

    Only raises when there's actually an SVG to rasterize and no usable
    backend exists (Pillow is required either way, for the greyscale/
    threshold step) - build()'s "asset pack absent" path never reaches
    here, so a host with neither Pillow nor cairosvg still builds an empty
    icons.json cleanly (see the module docstring)."""
    if Image is None:
        raise RuntimeError(
            "svg_to_mask: Pillow is not installed (required to rasterize "
            "any SVG, regardless of backend)")
    png_bytes = (_rasterize_cairosvg(svg_bytes, size) if cairosvg is not None
                 else _rasterize_rsvg(svg_bytes, size))
    img = Image.open(io.BytesIO(png_bytes)).convert("L")
    if img.size != (size, size):
        img = img.resize((size, size))
    px = img.load()
    mask = []
    for y in range(size):
        bits = 0
        for x in range(size):
            bits = (bits << 1) | (1 if px[x, y] < threshold else 0)
        mask.append(bits)
    return mask


def _recolor_svg(svg_bytes):
    """Recolor an exported SVG's `currentColor` references to SVG_FILL, for
    the verbatim svg_out copy only (see _assemble) - NOT for the
    icons.json mask (svg_to_mask composites onto a white background and
    thresholds on darkness, so currentColor's default-black resolution
    there is already correct regardless of what color the export ends up
    painted).

    The pack's SVGs use fill="currentColor" so the source repo's own demo
    page can recolor them by inheriting the surrounding text color: an
    inline <svg> can do that, but a tablet <img> can't inherit anything
    from the page, so left alone every exported icon renders black on the
    tablet's near-black ground (Task 5b review, "Important").

    `currentColor` is the literal SVG/CSS keyword and appears as that exact
    token in every shape the pack uses it in - a bare attribute value
    (fill="currentColor"), inside a style="" attribute
    (style="fill:currentColor"), and inside a <style> block's declarations
    (.a{fill:currentColor;stroke:currentColor}) - so one case-sensitive
    byte-level regex substitution over the whole file catches all of them
    without parsing the markup. Everything else about the file - structure,
    whitespace, every other attribute/declaration - stays byte-identical."""
    return _CURRENT_COLOR_RE.sub(SVG_FILL.encode("ascii"), svg_bytes)


def _slug(path):
    """Filename (no directory, no .svg) lowercased with underscores turned
    to hyphens - e.g. "passage_through_mirkwood.svg" -> "passage-through-
    mirkwood", matching the catalog's encounterSet slug style. `path` may be
    a local filesystem path or a tarball member name; both use "/" and
    os.path.basename handles either on the POSIX hosts this runs on (dev
    machines, ubuntu-latest CI)."""
    base = os.path.splitext(os.path.basename(path))[0]
    return base.lower().replace("_", "-")


def _iter_local_svgs(assets_root):
    """Yield (category, path, svg_bytes) for every SVG under assets_root's
    'expansion symbols/' then 'encounter sets/' subdirectories, sorted by
    path within each category. Expansion symbols first so _assemble()'s
    collision rule lets encounter sets win (matches _iter_tarball_svgs's
    ordering). Callers check os.path.isdir(assets_root) themselves first,
    so they can print their own "pack not found" message before this runs."""
    for category, subdir in (("expansion_symbols", "expansion symbols"),
                              ("encounter_sets", "encounter sets")):
        root = os.path.join(assets_root, subdir)
        for path in sorted(glob.glob(os.path.join(root, "**", "*.svg"), recursive=True)):
            with open(path, "rb") as f:
                yield category, path, f.read()


def _iter_tarball_svgs(tar_bytes):
    """Yield (category, member_name, svg_bytes) for every SVG inside the
    in-memory tarball `tar_bytes` that lives under icons/encounter sets/ or
    icons/expansion symbols/ - matched by suffix since GitHub codeload
    tarballs wrap every path in a single top-level <repo>-<sha>/ directory.
    Nothing is written to disk and nothing outside those two subtrees
    (fonts/, product-images/, icons/game icons/, ...) is ever read.
    Expansion symbols are yielded before encounter sets, sorted by path
    within each category, matching _iter_local_svgs's ordering exactly so a
    pinned-fetch build and an equivalent local-pack build agree on
    collisions too."""
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tar:
        matched = []
        for member in tar.getmembers():
            if not member.isfile():
                continue
            parts = member.name.split("/", 1)
            if len(parts) != 2:
                continue
            rel = parts[1]
            if not rel.lower().endswith(".svg"):
                continue
            for category, subdir in CATEGORY_DIRS:
                if rel.startswith(subdir):
                    matched.append((category, rel, member))
                    break
        order = {cat: i for i, (cat, _) in enumerate(CATEGORY_DIRS)}
        matched.sort(key=lambda t: (order[t[0]], t[1]))
        for category, rel, member in matched:
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            yield category, rel, extracted.read()


def _assemble(svg_sources, size, svg_out=None):
    """Consume a (category, name, svg_bytes) iterable - see
    _iter_local_svgs / _iter_tarball_svgs - into an icons dict + counts.
    Encounter-set and expansion-symbol icons share one flat slug namespace;
    whichever source is iterated second for a given slug wins a collision
    (logged either way) - both iterators order expansion symbols first so
    encounter sets always win, matching the pre-existing behavior.

    `svg_out`, when given, is a directory that also receives each source
    SVG as `<slug>.svg` - recoloured by _recolor_svg (currentColor ->
    SVG_FILL) but otherwise verbatim - written in this same single pass
    over `svg_sources`, so a collision resolves to the identical winner as
    the icons.json mask (the later source for a slug overwrites both the
    dict entry and the file). Never iterates svg_sources twice."""
    icons = {}
    counts = {"encounter_sets": 0, "expansion_symbols": 0, "collisions": 0}
    if svg_out:
        try:
            os.makedirs(svg_out, exist_ok=True)
        except OSError as e:
            raise SystemExit("Failed to create SVG output directory %r: %s" % (svg_out, e))
    for category, name, svg_bytes in svg_sources:
        slug = _slug(name)
        if slug in icons:
            counts["collisions"] += 1
            print("build_icons: slug %r collides across icon "
                  "namespaces (%s wins)" % (slug, category))
        icons[slug] = svg_to_mask(svg_bytes, size=size)
        counts[category] += 1
        if svg_out:
            try:
                with open(os.path.join(svg_out, slug + ".svg"), "wb") as f:
                    f.write(_recolor_svg(svg_bytes))
            except OSError as e:
                raise SystemExit("Failed to write SVG %r to %r: %s" % (slug, svg_out, e))
    return icons, counts


def _write(out_path, icons, size, source):
    out = {
        "generated": datetime.date.today().isoformat(),
        "source": source,
        "disclaimer": DISCLAIMER,
        "size": size,
        "icons": icons,
    }
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build(assets_root, out_path=DEFAULT_OUT, size=SIZE, source=None, svg_out=None):
    """Rasterize every encounter-set + expansion-symbol SVG under the local
    directory `assets_root` into a docs/data/icons.json-shaped dict, write
    it to `out_path`, and return a summary dict (counts). Never raises on a
    missing/unreadable asset pack - see the module docstring. This is the
    --assets PATH override path; the normal (no --assets) run instead goes
    through fetch_and_build().

    `svg_out`, when truthy, also writes each source SVG verbatim to
    `svg_out/<slug>.svg` in the same pass (see _assemble) - falsy (None or
    "") disables the export entirely, and nothing is written when
    `assets_root` doesn't exist (there's nothing to export)."""
    if source is None:
        source = ("local pack at %s (icons/encounter sets + icons/expansion symbols)"
                   % assets_root)
    if not os.path.isdir(assets_root):
        print("build_icons: asset pack not found at %r - writing an empty "
              "icons.json (icon slots stay placeholders)" % (assets_root,))
        icons, counts = {}, {"encounter_sets": 0, "expansion_symbols": 0, "collisions": 0}
    else:
        try:
            icons, counts = _assemble(_iter_local_svgs(assets_root), size, svg_out=svg_out)
        except RuntimeError as e:
            raise SystemExit("Failed to rasterize icon pack at %r: %s" % (assets_root, e))
    _write(out_path, icons, size, source)
    return {"count": len(icons), **counts}


def fetch_and_build(sha, out_path=DEFAULT_OUT, size=SIZE, svg_out=None):
    """Download the pinned upstream tarball at `sha` and rasterize its SVGs
    straight out of memory (_iter_tarball_svgs) into docs/data/icons.json.
    Mirrors tools/build_card_data.py's fetch convention exactly: a failed
    download or an unreadable archive raises SystemExit with a friendly
    one-line message (no traceback) rather than crashing; the Pages workflow
    marks this build step continue-on-error since icons are optional.

    `svg_out`, when truthy, also writes each source SVG verbatim to
    `svg_out/<slug>.svg` in the same pass over the tarball (see _assemble) -
    the tarball is never iterated twice."""
    url = TARBALL.format(sha=sha)
    print("Fetching icon pack at %s ..." % sha)
    try:
        with urllib.request.urlopen(url) as resp:
            tar_bytes = resp.read()
    except urllib.error.URLError as e:
        raise SystemExit("Failed to fetch icon pack at sha %s: %s\nTry --refresh to "
                          "re-pin, or pass --assets for a local copy." % (sha, e))
    try:
        icons, counts = _assemble(_iter_tarball_svgs(tar_bytes), size, svg_out=svg_out)
    except tarfile.TarError as e:
        raise SystemExit("Failed to read icon pack tarball at sha %s: %s" % (sha, e))
    except RuntimeError as e:
        raise SystemExit("Failed to rasterize icon pack at sha %s: %s" % (sha, e))
    _write(out_path, icons, size,
           "%s@%s icons/{encounter sets,expansion symbols}" % (REPO, sha))
    return {"count": len(icons), **counts}


def _read_pin():
    with open(SOURCE_FILE, encoding="utf-8") as f:
        for line in f:
            if line.startswith("sha="):
                return line.strip().split("=", 1)[1]
    raise SystemExit("No sha in %s — run with --refresh once." % SOURCE_FILE)


def _refresh_pin():
    req = urllib.request.Request(API, headers={"Accept": "application/vnd.github.sha"})
    try:
        with urllib.request.urlopen(req) as resp:
            sha = resp.read().decode().strip()
    except urllib.error.URLError as e:
        raise SystemExit("Failed to resolve upstream sha from %s: %s" % (API, e))
    os.makedirs(os.path.dirname(SOURCE_FILE), exist_ok=True)
    with open(SOURCE_FILE, "w", encoding="utf-8") as f:
        f.write("url=%s\nsha=%s\n" % (TARBALL, sha))
    return sha


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Rasterize the community SVG icon pack to docs/data/icons.json.")
    ap.add_argument("--assets", default=None,
                     help="root of a local SVG pack override (contains 'encounter "
                          "sets/' and 'expansion symbols/' subdirectories) - reads "
                          "this directory instead of fetching; when omitted, fetches "
                          "the pinned upstream tarball (tools/data/icons.SOURCE.txt)")
    ap.add_argument("--refresh", action="store_true", help="re-pin to upstream HEAD sha")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--svg-out", default=DEFAULT_SVG_OUT,
                     help="directory to also write each source SVG verbatim as "
                          "<slug>.svg, same run and same collision rule as "
                          "icons.json (encounter sets win); pass an empty string "
                          "to disable the export entirely")
    args = ap.parse_args(argv)

    if args.refresh:
        _refresh_pin()

    svg_out = args.svg_out or None

    if args.assets:
        summary = build(args.assets, args.out, svg_out=svg_out)
    else:
        if not os.path.exists(SOURCE_FILE):
            raise SystemExit("No pin file — run once with --refresh.")
        sha = _read_pin()
        summary = fetch_and_build(sha, args.out, svg_out=svg_out)

    print("Wrote %d icons (%d encounter sets, %d expansion symbols, %d collisions) to %s"
          % (summary["count"], summary["encounter_sets"], summary["expansion_symbols"],
             summary["collisions"], args.out))
    if svg_out:
        print("Wrote SVGs to %s" % svg_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
