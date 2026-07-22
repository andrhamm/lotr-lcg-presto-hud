"""Host layout previewer — rasterizes a scene's draw calls to a PNG.

Scenes come from tests/scenes.py (same builders the layout lint uses), so what
you preview is exactly what the lint checks and what the device draws.

Usage:  python3 tools/preview.py <scene> [out.png]
        python3 tools/preview.py --list
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFont

from tests.scenes import SCENES
from tests.fake_hardware import BITMAP8_W

MONO = "/System/Library/Fonts/Menlo.ttc"


def _font(scale):
    # sized to the bitmap8 glyph height (8px * scale)
    return ImageFont.truetype(MONO, max(7, int(7.6 * scale)))


def render(calls, path):
    img = Image.new("RGB", (480, 480), (0, 0, 0))
    dr = ImageDraw.Draw(img)
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
            f = _font(scale)
            cx = x
            for ch in str(s):
                dr.text((cx, y), ch, font=f, fill=pen)
                cx += (BITMAP8_W.get(ch, 4) + 1) * scale
    img.save(path)
    return path


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        print("\n".join(sorted(SCENES)))
        raise SystemExit
    scene = sys.argv[1] if len(sys.argv) > 1 else "play_resource_planning"
    if scene not in SCENES:
        raise SystemExit("unknown scene %r; try --list" % scene)
    out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/preview_%s.png" % scene
    hw, _ = SCENES[scene]()
    render(hw.display.calls, out)
    print(out)
