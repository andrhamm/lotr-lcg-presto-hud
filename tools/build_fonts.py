"""Compile the upstream PicoGraphics bitmap fonts into glyph masks.

WHY THIS EXISTS
---------------
Every host mockup this project has ever produced lied about type.
`tools/preview.py` draws text in Menlo and `docs/js/ui.js` draws it in Courier
New; both take per-character advances from BITMAP8_W, so they are
metric-faithful and glyph-substituted. Three retheme attempts were rejected,
and one stated reason - "the bitmap font read as a toy" - was a judgment about
letterforms no mockup has ever displayed.

The device's fonts are published as plain data, so the fix is mechanical:
parse the upstream headers into 1-bit masks and let the host renderers draw
glyphs as rectangles. That is exactly what the device does, so a mock becomes
pixel-exact rather than merely well-spaced.

The output also VERIFIES `BITMAP8_W` - the hand-probed width table that every
layout test depends on - against its source. See `--verify`.

SOURCE OF TRUTH
---------------
`tools/data/fonts.SOURCE.txt` pins the upstream repo and a commit sha, the
same pattern `build_icons.py` and `build_card_data.py` use. A plain run
fetches NOTHING: with the output present it prints a one-line no-op and exits
0. Refresh the pin explicitly with `--refresh`.

Upstream is MIT, Copyright (c) 2021 Pimoroni Ltd - see NOTICE. The derived
masks are committed (data-policy decision, 2026-08-11): they are small, the
licence permits redistribution, and the alternative is a network fetch in CI,
which the data policy calls a smell.

Hershey (vector) fonts are deliberately NOT handled here. They ship under
Pimoroni's MIT licence but the Hershey glyph set carries its own upstream
provenance, which is unresolved. Nothing derived from it is committed until
that clears.

THE DATA FORMAT, AND THE ONE GOTCHA
-----------------------------------
Upstream stores each glyph COLUMN-major: `max_width` bytes per column-set, one
byte per column, LSB = top row (`bitmap_fonts.cpp::character`).

For fonts TALLER than 8px there are two bytes per column, and their order is
not the obvious one. The renderer does:

    uint32_t data = *d << 8;                              // byte0
    if(two_bytes_per_column) { d++; data <<= 8; data |= *d << 8; }   // byte1

leaving byte1 at bits 8..15 and byte0 at bits 16..23, while row r is read from
bit (8 + r). So **byte0 holds the BOTTOM eight rows and byte1 the top eight** -
reversed from how you would guess. Getting this backwards produces glyphs that
look plausible at a glance and are vertically swapped.

We emit ROW-major masks instead, because that is what `ui/icons.py` already
speaks: a row is an int whose bit (width - 1 - col) is set. The host renderers
decode those to rectangle runs exactly like an icon mask, so one cached-run
code path serves both.
"""
import argparse
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
SOURCE = os.path.join(DATA, "fonts.SOURCE.txt")
CACHE = os.path.join(DATA, "fonts_cache")
OUT = os.path.join(DATA, "fonts.json")

REPO = "pimoroni/pimoroni-pico"
FONT_DIR = "libraries/bitmap_fonts"
FONTS = ("font6", "font8", "font14_outline")

# 96 printable ASCII (32..127) + 9 remapped extras, per bitmap_fonts.hpp.
BASE_CHARS = 96
EXTRA_CHARS = 9
FIRST_CH = 32


def _read_pin():
    """The pinned (sha, files) from SOURCE, or (None, []) when unpinned."""
    if not os.path.exists(SOURCE):
        return None, []
    sha, files = None, []
    with open(SOURCE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("sha:"):
                sha = line.split(":", 1)[1].strip()
            elif line.startswith("file:"):
                files.append(line.split(":", 1)[1].strip())
    return sha, files


def _write_pin(sha, files):
    os.makedirs(DATA, exist_ok=True)
    with open(SOURCE, "w") as f:
        f.write("# Upstream source for the device bitmap fonts.\n")
        f.write("# %s, MIT (Copyright (c) 2021 Pimoroni Ltd) - see NOTICE.\n" % REPO)
        f.write("# Refresh with: python3 tools/build_fonts.py --refresh\n")
        f.write("repo: %s\n" % REPO)
        f.write("sha: %s\n" % sha)
        for p in files:
            f.write("file: %s\n" % p)


def _resolve_head():
    url = "https://api.github.com/repos/%s/commits/main" % REPO
    req = urllib.request.Request(url, headers={"User-Agent": "lotr-lcg-presto-hud"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["sha"]


def _fetch(sha, path):
    """Fetch one pinned file, caching the raw response."""
    os.makedirs(CACHE, exist_ok=True)
    local = os.path.join(CACHE, "%s-%s" % (sha[:12], os.path.basename(path)))
    if os.path.exists(local):
        with open(local) as f:
            return f.read()
    url = "https://raw.githubusercontent.com/%s/%s/%s" % (REPO, sha, path)
    req = urllib.request.Request(url, headers={"User-Agent": "lotr-lcg-presto-hud"})
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode("utf-8")
    with open(local, "w") as f:
        f.write(text)
    return text


# -- parsing ---------------------------------------------------------------

def _ints(block):
    """Every integer literal in a brace block, decimal or hex.

    Comments MUST be stripped first. Upstream labels each data row with the
    character it encodes (`0x3e,0x51,... // 0`), so the ten digit glyphs
    contribute ten stray literals - which shifts every later glyph by exactly
    two positions and renders "Questing" as "Oscqrcle". Plausible-looking
    text, entirely wrong letters.
    """
    block = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
    block = re.sub(r"//[^\n]*", "", block)
    return [int(t, 0) for t in re.findall(r"0x[0-9a-fA-F]+|\d+", block)]


def _field(src, name):
    """The brace block of a designated initializer `.name = { ... }`."""
    m = re.search(r"\.%s\s*=\s*\{" % re.escape(name), src)
    if not m:
        raise SystemExit("build_fonts: no .%s in font header" % name)
    i = m.end()
    depth = 1
    start = i
    while i < len(src) and depth:
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
        i += 1
    return src[start:i - 1]


def _scalar(src, name):
    m = re.search(r"\.%s\s*=\s*(\d+)" % re.escape(name), src)
    if not m:
        raise SystemExit("build_fonts: no .%s in font header" % name)
    return int(m.group(1))


def parse_font(src):
    """Header text -> {"height", "max_width", "glyphs": {ch: {"w", "rows"}}}.

    Only the 96 printable ASCII glyphs are emitted. The 9 remapped extras and
    the trailing accent table are parsed past but dropped: the app's copy is
    ASCII-only by design-system rule, and an accent we cannot type is an
    accent we cannot test.
    """
    height = _scalar(src, "height")
    max_width = _scalar(src, "max_width")
    widths = _ints(_field(src, "widths"))
    data = _ints(_field(src, "data"))

    want = BASE_CHARS + EXTRA_CHARS
    if len(widths) != want:
        raise SystemExit(
            "build_fonts: expected %d widths, got %d" % (want, len(widths)))

    two_byte = height > 8
    bpc = max_width * (2 if two_byte else 1)
    if len(data) < want * bpc:
        raise SystemExit(
            "build_fonts: data holds %d bytes, need at least %d"
            % (len(data), want * bpc))

    glyphs = {}
    for idx in range(BASE_CHARS):
        w = widths[idx]
        base = idx * bpc
        # Column-major -> row-major. See the module docstring for the
        # two-byte ordering, which is byte1-then-byte0 top to bottom.
        rows = [0] * height
        for col in range(w):
            if two_byte:
                b0 = data[base + col * 2]
                b1 = data[base + col * 2 + 1]
                column = b1 | (b0 << 8)
            else:
                column = data[base + col]
            for row in range(height):
                if column & (1 << row):
                    rows[row] |= 1 << (w - 1 - col)
        glyphs[chr(FIRST_CH + idx)] = {"w": w, "rows": rows}

    return {"height": height, "max_width": max_width, "glyphs": glyphs}


# -- verification ----------------------------------------------------------

def verify_widths(font8):
    """Compare the probed BITMAP8_W against upstream. Returns a report dict.

    BITMAP8_W is hand-probed and every layout test measures through it, so a
    disagreement means the linter has been passing on wrong numbers.
    """
    sys.path.insert(0, os.path.dirname(HERE))
    from tests.fake_hardware import BITMAP8_W

    mismatched, missing = {}, {}
    for ch, g in sorted(font8["glyphs"].items()):
        if ch in BITMAP8_W:
            if BITMAP8_W[ch] != g["w"]:
                mismatched[ch] = (BITMAP8_W[ch], g["w"])
        else:
            # Absent keys fall back to 4 in measure_bitmap8/measureText.
            if g["w"] != 4:
                missing[ch] = (4, g["w"])
    extra = sorted(set(BITMAP8_W) - set(font8["glyphs"]))
    return {"mismatched": mismatched, "missing": missing, "extra": extra}


def _report(rep):
    if rep["mismatched"]:
        print("MISMATCH - probed table disagrees with upstream:")
        for ch, (got, want) in sorted(rep["mismatched"].items()):
            print("  %-4r probed %d, upstream %d" % (ch, got, want))
    if rep["missing"]:
        print("MISSING - absent from the table, so measured as the 4px fallback:")
        for ch, (got, want) in sorted(rep["missing"].items()):
            print("  %-4r falls back to %d, upstream %d" % (ch, got, want))
    if rep["extra"]:
        print("EXTRA - in the table but not in the font: %s" % rep["extra"])
    if not any((rep["mismatched"], rep["missing"], rep["extra"])):
        print("BITMAP8_W agrees with upstream on every glyph.")


# -- main ------------------------------------------------------------------

def build(refresh=False):
    sha, files = _read_pin()
    if refresh or not sha:
        sha = _resolve_head()
        files = ["%s/%s_data.hpp" % (FONT_DIR, n) for n in FONTS]
        _write_pin(sha, files)
        print("pinned %s @ %s" % (REPO, sha[:12]))

    out = {"_source": {"repo": REPO, "sha": sha, "licence": "MIT"}, "fonts": {}}
    for name, path in zip(FONTS, files):
        out["fonts"][name] = parse_font(_fetch(sha, path))
        print("parsed %-16s height %d, %d glyphs"
              % (name, out["fonts"][name]["height"],
                 len(out["fonts"][name]["glyphs"])))

    os.makedirs(DATA, exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"), sort_keys=True)
    print("wrote %s (%d bytes)" % (OUT, os.path.getsize(OUT)))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refresh", action="store_true",
                    help="re-resolve the upstream pin and rebuild")
    ap.add_argument("--verify", action="store_true",
                    help="report BITMAP8_W against upstream widths")
    args = ap.parse_args()

    if os.path.exists(OUT) and not args.refresh and not args.verify:
        print("fonts.json present; nothing to do (use --refresh to rebuild)")
        return

    data = build(refresh=args.refresh)
    if args.verify:
        print()
        _report(verify_widths(data["fonts"]["font8"]))


if __name__ == "__main__":
    main()
