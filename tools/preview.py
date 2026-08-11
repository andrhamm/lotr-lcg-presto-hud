"""Host layout previewer — rasterizes a scene's draw calls to a PNG.

Scenes come from tests/scenes.py (same builders the layout lint uses), so what
you preview is exactly what the lint checks and what the device draws.

Text is drawn from the DEVICE'S OWN glyph masks (tools/hostfont.py, compiled
by tools/build_fonts.py), so a preview is pixel-exact rather than merely
well-spaced. It used to substitute Menlo at an approximated size, which meant
every mockup this project ever produced showed letterforms the device does not
have - and a retheme was rejected partly on that basis. `--substitute` restores
the old behaviour for comparison.

Usage:  python3 tools/preview.py <scene> [out.png]
        python3 tools/preview.py --list
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFont

from tests.scenes import SCENES
from tests.fake_hardware import BITMAP8_W
from tools import hostfont

MONO = "/System/Library/Fonts/Menlo.ttc"


def _font(scale):
    # sized to the bitmap8 glyph height (8px * scale)
    return ImageFont.truetype(MONO, max(7, int(7.6 * scale)))


def _draw_substituted(dr, s, x, y, scale, pen):
    """The old Menlo stand-in: right advances, wrong letters."""
    f = _font(scale)
    cx = x
    for ch in str(s):
        dr.text((cx, y), ch, font=f, fill=pen)
        cx += (BITMAP8_W.get(ch, 4) + 1) * scale


def render(calls, path, font="font8", substitute=False):
    img = Image.new("RGB", (480, 480), (0, 0, 0))
    dr = ImageDraw.Draw(img)
    real = hostfont.available() and not substitute
    for c in calls:
        if c[0] == "clear":
            dr.rectangle([0, 0, 479, 479], fill=c[1])
        elif c[0] == "rect":
            _, x, y, w, h, pen = c
            dr.rectangle([x, y, x + w - 1, y + h - 1], fill=pen)
        elif c[0] == "tri":
            _, x1, y1, x2, y2, x3, y3, pen = c
            dr.polygon([(x1, y1), (x2, y2), (x3, y3)], fill=pen)
        elif c[0] == "text":
            s, x, y, scale, pen = c[1], c[2], c[3], c[4], c[5]
            # The scene records which font each string resolved to, so a
            # mixed binding (font14 body over a font8 label, say) renders
            # correctly without the previewer guessing.
            glyphs = c[7] if len(c) > 7 else font
            if real:
                hostfont.draw(
                    lambda rx, ry, rw, rh: dr.rectangle(
                        [rx, ry, rx + rw - 1, ry + rh - 1], fill=pen),
                    s, x, y, scale, glyphs)
            else:
                _draw_substituted(dr, s, x, y, scale, pen)
    img.save(path)
    return path


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    substitute = "--substitute" in args
    if substitute:
        args.remove("--substitute")
    font = "font8"
    for a in list(args):
        if a.startswith("--font="):
            font = a.split("=", 1)[1]
            args.remove(a)

    if args and args[0] == "--list":
        print("\n".join(sorted(SCENES)))
        raise SystemExit
    scene = args[0] if args else "play_resource_planning"
    if scene not in SCENES:
        raise SystemExit("unknown scene %r; try --list" % scene)
    out = args[1] if len(args) > 1 else "/tmp/preview_%s.png" % scene
    hw, _ = SCENES[scene]()
    render(hw.display.calls, out, font=font, substitute=substitute)
    print(out)
