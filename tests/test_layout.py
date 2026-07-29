"""Layout lint: runs every wireframe scene and asserts pixel-level rules.

Rules:
  L1  every draw call stays inside the 480x480 screen
  L2  no two text runs overlap (catches label/value/icon-text collisions)
  L3  touch targets are at least MIN_TARGET px in each dimension
  L4  touch targets stay on-screen
  L5  on play screens, no drawn rectangle crosses into the bottom nav band
  L6  ...and neither does content TEXT

L5 exists because L1-L4 all reason about TEXT. setup_game's sailing toggle
ran 2px past its CTA for as long as that view has existed and nothing caught
it - it is a panel, not a label. The nav rule made it visible; this rule keeps
it from coming back.
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


PLAY_SCENES = tuple(sorted(s for s in SCENES if s.startswith("play_")))


@pytest.mark.parametrize("scene", PLAY_SCENES)
def test_l5_play_content_clears_the_nav_rule(scene):
    from ui.screen_play import NAV_RULE_Y
    hw, _ = SCENES[scene]()
    for c in hw.display.calls:
        if c[0] != "rect":
            continue
        _, x, y, w, h, _pen = c
        if w >= W and y == NAV_RULE_Y:
            continue                      # the rule itself
        if y < NAV_RULE_Y:
            assert y + h <= NAV_RULE_Y, (
                "%s: rect at y=%d h=%d crosses the nav rule at %d"
                % (scene, y, h, NAV_RULE_Y))


@pytest.mark.parametrize("scene", PLAY_SCENES)
def test_l6_play_text_clears_the_nav_rule(scene):
    """L5's sibling for text.

    L5 only inspects rects, so a rebuilt combat flow ran its closing note
    across the rule and passed - the collision check did not fire either,
    because the CTA label happened to sit 4px lower. The rule exists to keep
    content out of the nav band; text belongs to that rule as much as panels
    do.
    """
    from ui.screen_play import NAV_RULE_Y, CONTENT_Y, CTA_Y
    hw, _ = SCENES[scene]()
    for c in hw.display.calls:
        if c[0] != "text":
            continue
        s, x, y, scale = str(c[1]), c[2], c[3], c[4]
        if not s.strip() or y < CONTENT_Y or y >= CTA_Y:
            continue          # header chrome and the CTA itself live outside
        assert y + 8 * scale <= NAV_RULE_Y, (
            "%s: content text %r ends at y=%d, past the nav rule at %d"
            % (scene, s[:40], y + 8 * scale, NAV_RULE_Y))
