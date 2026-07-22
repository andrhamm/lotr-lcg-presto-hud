"""Layout lint: runs every wireframe scene and asserts pixel-level rules.

Rules:
  L1  every draw call stays inside the 480x480 screen
  L2  no two text runs overlap (catches label/value/icon-text collisions)
  L3  touch targets are at least MIN_TARGET px in each dimension
  L4  touch targets stay on-screen
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.scenes import SCENES
from tests.fake_hardware import measure_bitmap8

W = H = 480
MIN_TARGET = 24


def _text_rect(call):
    s, x, y, scale = call[1], call[2], call[3], call[4]
    return (x, y, measure_bitmap8(s, scale), 8 * scale)


def _overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


@pytest.mark.parametrize("name", sorted(SCENES))
def test_all_draws_inside_screen(name):
    hw, _ = SCENES[name]()
    for c in hw.display.calls:
        if c[0] == "rect":
            _, x, y, w, h, _pen = c
            assert x >= 0 and y >= 0 and x + w <= W and y + h <= H, \
                "%s: rect out of bounds %s" % (name, c)
        elif c[0] == "text":
            x, y, w, h = _text_rect(c)
            assert x >= 0 and y >= 0 and x + w <= W and y + h <= H, \
                "%s: text out of bounds %r" % (name, c[1])


@pytest.mark.parametrize("name", sorted(SCENES))
def test_no_device_side_wrapping(name):
    """PicoGraphics wraps words at the wordwrap width; wrap=0 stacks every
    word vertically. We pre-wrap all text ourselves, so every text call must
    pass a wrap width the string can never exceed."""
    hw, _ = SCENES[name]()
    for c in hw.display.calls:
        if c[0] == "text" and " " in str(c[1]).strip():
            wrap = c[6]
            need = measure_bitmap8(c[1], c[4])
            assert wrap > need, \
                "%s: %r would word-stack on device (wrap=%d < width=%d)" % \
                (name, c[1], wrap, need)


@pytest.mark.parametrize("name", sorted(SCENES))
def test_no_text_collisions(name):
    hw, _ = SCENES[name]()
    texts = [c for c in hw.display.calls if c[0] == "text" and str(c[1]).strip()]
    rects = [_text_rect(c) for c in texts]
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            # drop-shadow pairs: same string within 2px is intentional
            if (str(texts[i][1]) == str(texts[j][1])
                    and abs(texts[i][2] - texts[j][2]) <= 2
                    and abs(texts[i][3] - texts[j][3]) <= 2):
                continue
            assert not _overlap(rects[i], rects[j]), \
                "%s: text collision %r vs %r" % (name, texts[i][1], texts[j][1])


@pytest.mark.parametrize("name", sorted(SCENES))
def test_touch_targets_min_size_and_on_screen(name):
    _, obj = SCENES[name]()
    for b in obj.buttons:
        assert b.w >= MIN_TARGET and b.h >= MIN_TARGET, \
            "%s: target %s too small (%dx%d)" % (name, b.id, b.w, b.h)
        assert b.x >= 0 and b.y >= 0 and b.x + b.w <= W and b.y + b.h <= H, \
            "%s: target %s off-screen" % (name, b.id)
