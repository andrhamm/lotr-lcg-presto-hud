"""Layout lint: runs every wireframe scene and asserts pixel-level rules.

Rules:
  L1  every draw call stays inside the 480x480 screen
  L2  no two text runs overlap (catches label/value/icon-text collisions)
  L3  touch targets are at least MIN_TARGET px in each dimension
  L4  touch targets stay on-screen
  L5  on play screens, no drawn rectangle crosses into the bottom nav band
  L6  ...and neither does content TEXT
  L7  every touch target is reachable by some tap

L5 exists because L1-L4 all reason about TEXT. setup_game's sailing toggle
ran 2px past its CTA for as long as that view has existed and nothing caught
it - it is a panel, not a label. The nav rule made it visible; this rule keeps
it from coming back.

L7 exists because a button can be drawn, sized and on-screen and still be
dead: the dispatcher takes the FIRST hit in the list (main.py:437), so an
earlier button lying over it wins every tap. Both pre-game back buttons were
added on top of draw_header's own round-stamp button, so "< Menu" opened the
Game Log. Containment alone would not have caught it - the wider of the two
was shadowed jointly by the log and phases buttons - so the rule asks the
real question: is there any point this button answers?
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


@pytest.mark.parametrize("name", sorted(SCENES))
def test_l7_every_touch_target_is_reachable(name):
    """No button may be buried under earlier ones.

    Dispatch is first-hit-wins over the list in draw order (main.py:418/437,
    docs/js/main.js:208/226), so a button appended over an existing one is
    dead on arrival however correct its handler is. Sampling is exact rather
    than approximate: with axis-aligned rects, one point per cell of the grid
    formed by every button edge decides the whole layout.
    """
    _, obj = SCENES[name]()
    btns = getattr(obj, "buttons", [])
    xs = sorted({v for b in btns for v in (b.x, b.x + b.w)})
    ys = sorted({v for b in btns for v in (b.y, b.y + b.h)})
    probes = [((a + b) // 2, (c + d) // 2)
              for a, b in zip(xs, xs[1:]) for c, d in zip(ys, ys[1:])]
    reached = set()
    for x, y in probes:
        for i, b in enumerate(btns):
            if b.hit(x, y):
                reached.add(i)
                break
    dead = [(i, b.id) for i, b in enumerate(btns) if i not in reached]
    assert not dead, (
        "%s: no tap reaches %s - an earlier button covers it"
        % (name, [d[1] for d in dead]))


# Views whose content area is not a guidance band under the stat strip, with
# the reason each one is exempt.
_NOT_A_BAND_VIEW = {
    "play_quest_resolution": "the placement table - it drops the stat strip "
                             "entirely and starts its rows higher",
    "play_setup": "pre-game, so there is no stat strip to sit under",
    "play_setup_sailing": "pre-game, so there is no stat strip to sit under",
}


@pytest.mark.parametrize("scene", PLAY_SCENES)
def test_l8_content_bands_start_on_the_content_line(scene):
    """Every guidance band top-anchors at CONTENT_Y.

    The action-window band used to be CENTRED in the space between the stat
    strip and the nav rule, so its top edge moved with the copy length: 195 on
    a five-line window, 234 on a two-line one, against a flat 150 on every
    phase view. Walking a round, the band jumped up and down underneath a stat
    strip that never moved - which is the "odd spacing" a player notices
    without being able to name it.

    Anchoring is the rule; how tall the band grows is the copy's business.
    """
    from ui.screen_play import NAV_RULE_Y
    if scene in _NOT_A_BAND_VIEW:
        return
    hw, obj = SCENES[scene]()
    # The anchor is per-draw now: the stat pills take only the room they need,
    # so a 3-player game starts its content ~66px higher than a 4-player one.
    # Ask the screen where it put the line rather than assuming 150.
    cy = obj.content_y
    tops = [c[2] for c in hw.display.calls
            if c[0] == "rect" and c[4] >= 40 and c[3] > 300
            and cy - 6 <= c[2] < NAV_RULE_Y]
    if not tops:
        return                      # a loop-diagram view draws no band at all
    assert min(tops) == cy, (
        "%s: content band starts at y=%d, not the content line %d"
        % (scene, min(tops), cy))


# --------------------------------------------------------------------------
# Treatment vocabulary
# --------------------------------------------------------------------------

# Play views allowed to draw the gold hint bar, with the reason. Gold is the
# weakest of the three and says "a hint, not a rule", so it has to earn its
# place on a screen that is otherwise telling you what the game does.
_GOLD_OK = {
    "play_quest_sailing": "genuinely a hint about a control - this quest has "
                          "no sailing keyword, here is where to enable it",
    # Closing notes that are strategy rather than rules. Their siblings
    # (planning, combat_enemy) state what the game does to you and take the
    # red bar instead, which is the distinction this allow-list exists to
    # keep honest - gold has to mean "you may act on this", not "leftover".
    "play_enc_checks": "the closing note is strategy - 'higher threat pulls "
                       "bigger enemies' is nowhere in the rules",
    "play_combat_player": "the closing note is advice - lower threat now or "
                          "refresh may eliminate",
}


@pytest.mark.parametrize("scene", PLAY_SCENES)
def test_accent_bars_follow_the_colour_vocabulary(scene):
    """Red happens anyway, green is your window, gold is a hint.

    That pairing is the one piece of colour vocabulary a player has to learn,
    and it was applied loosely: all eight action-window screens drew the GOLD
    hint bar, even though an action window is the literal definition of the
    green one - and the phase view immediately before each of them drew the
    same idea in green. The resolution-failure band was gold too, reporting a
    threat raise that had already happened.
    """
    from ui.screen_play import NAV_RULE_Y
    from ui.theme import Palette
    from tests.fake_hardware import FakeHardware
    pal = Palette(FakeHardware().display)
    hw, obj = SCENES[scene]()
    cy = obj.content_y
    gold = [c for c in hw.display.calls
            if c[0] == "rect" and c[3] == 4 and c[4] >= 12
            and cy - 6 <= c[2] < NAV_RULE_Y and c[5] == pal.border_gold]
    if gold and scene not in _GOLD_OK:
        raise AssertionError(
            "%s draws the gold hint bar. Gold means 'a hint, not a rule' - if "
            "this content says what the game does, it is red (happens anyway) "
            "or green (your window)." % scene)


@pytest.mark.parametrize("scene", sorted(s for s in SCENES if s.startswith("play_aw_")))
def test_action_windows_wear_the_green_window_bar(scene):
    """An action window IS "your window to act" - the thing green means."""
    from ui.screen_play import NAV_RULE_Y
    from ui.theme import Palette
    from tests.fake_hardware import FakeHardware
    pal = Palette(FakeHardware().display)
    hw, obj = SCENES[scene]()
    cy = obj.content_y
    bars = {c[5] for c in hw.display.calls
            if c[0] == "rect" and c[3] == 4 and c[4] >= 12
            and cy - 6 <= c[2] < NAV_RULE_Y}
    assert pal.green in bars, "%s: action-window band is not green" % scene


def test_the_legend_teaches_all_three_bars():
    """A treatment the player is never taught reads as decoration, and gold
    was in the UI from the start with no legend row."""
    hw, _ = SCENES["legend"]()
    text = " ".join(str(c[1]) for c in hw.display.calls if c[0] == "text")
    assert "red = happens anyway" in text and "green = your window" in text
    assert "gold" in text, "the legend never explains the gold hint bar"


# Play views with no accent bar, and why each is exempt.
_NO_BAR_OK = {
    "play_quest_resolution": "the placement table - it drops the stat strip "
                             "and every row is a control, not guidance",
    "play_setup": "pre-game: no phase yet, so nothing to call framework or window",
    "play_setup_sailing": "pre-game, same as play_setup",
}


@pytest.mark.parametrize("scene", PLAY_SCENES)
def test_every_phase_view_states_framework_or_window(scene):
    """A view that guides the player says which kind of guidance it is.

    The four loop views - Planning, Encounter: Checks, and both halves of
    Combat - used to state their framing sentence as bare text, so a player
    who had learned red = happens anyway and green = your window met four
    screens that simply stopped saying it. Planning was among them, which is
    the phase that is nothing BUT your window.
    """
    from ui.screen_play import NAV_RULE_Y
    from ui.theme import Palette
    from tests.fake_hardware import FakeHardware
    pal = Palette(FakeHardware().display)
    if scene in _NO_BAR_OK:
        return
    hw, obj = SCENES[scene]()
    cy = obj.content_y
    bars = {c[5] for c in hw.display.calls
            if c[0] == "rect" and c[3] == 4 and c[4] >= 12
            and cy - 6 <= c[2] < NAV_RULE_Y}
    assert bars & {pal.red, pal.green, pal.border_gold}, (
        "%s guides the player but draws no accent bar, so it never says "
        "whether this happens anyway or is the player's window" % scene)


def test_the_two_band_widgets_draw_the_same_element():
    """note_panel and phase_block call themselves semantic siblings, and a
    player meets them one screen after the other - a phase view then its
    action window. They disagreed three ways at once: the bar spanned the full
    box in one and floated 6px inset in the other, the ink was tan in one and
    muted in the other, and the text sat 2px apart.
    """
    from tests.fake_hardware import FakeHardware
    from ui.theme import Palette, BODY
    from ui.widgets import note_panel, phase_block

    def draw(fn):
        hw = FakeHardware()
        pal = Palette(hw.display)
        fn(hw.display, pal)
        return hw.display.calls

    note = draw(lambda d, pal: note_panel(d, pal, 8, 150, 464, ["One line here."],
                                          BODY, 0, False, pal.green, pal.tan))
    block = draw(lambda d, pal: phase_block(d, pal, 8, 150, 464,
                                            [("window", "One line here.")]))

    def bar(calls):
        return next((c[2], c[4]) for c in calls if c[0] == "rect" and c[3] == 4)

    def body(calls):
        return next((c[2], c[5]) for c in calls if c[0] == "text" and str(c[1]).strip()
                    and c[5] != (34, 30, 24))          # skip the drop shadow

    assert bar(note) == bar(block), (
        "the accent bar sits differently: note_panel %s vs phase_block %s"
        % (bar(note), bar(block)))
    assert body(note) == body(block), (
        "body text differs in x or ink: note_panel %s vs phase_block %s"
        % (body(note), body(block)))


@pytest.mark.parametrize("scene", PLAY_SCENES)
def test_accent_bars_cover_their_box(scene):
    """A bar marks the box it is in, so the bars tile its full height.

    Half-height bars floating in a filled box is what made the same element
    look like two different ones from view to view.
    """
    from ui.screen_play import CONTENT_Y, NAV_RULE_Y
    from ui.theme import Palette
    from tests.fake_hardware import FakeHardware
    pal = Palette(FakeHardware().display)
    accents = {pal.red, pal.green, pal.border_gold}
    hw, _ = SCENES[scene]()
    boxes = [(c[2], c[4]) for c in hw.display.calls
             if c[0] == "rect" and c[3] > 300 and c[4] >= 24
             and CONTENT_Y - 6 <= c[2] < NAV_RULE_Y and c[5] == pal.card_hi]
    bars = [(c[2], c[4]) for c in hw.display.calls
            if c[0] == "rect" and c[3] == 4 and c[5] in accents
            and CONTENT_Y - 6 <= c[2] < NAV_RULE_Y]
    for by, bh in boxes:
        inside = sorted((y, h) for y, h in bars if by <= y < by + bh)
        if not inside:
            continue                      # a box with no bar is another rule
        assert inside[0][0] == by, (
            "%s: box at y=%d starts before its first bar (y=%d)"
            % (scene, by, inside[0][0]))
        assert inside[-1][0] + inside[-1][1] == by + bh, (
            "%s: box at y=%d..%d, bars stop at %d"
            % (scene, by, by + bh, inside[-1][0] + inside[-1][1]))
