"""Round-2 candidate directions.

Exploration artifacts, deliberately OUTSIDE `ui/` so they never reach device
flash. A direction that wins gets folded into `ui/skin.py` as a named skin;
until then these are proposals, not shipping code.

Each answers a specific line from the honest critique in
`design/design-review.md`, so it can be judged against a claim rather than a
mood:

  "gold on everything so gold means nothing"
  "heavy bevels read dated"
  "no hierarchy ... dead vertical space"
  "the nav CTA borrows the green confirm colour"

Every direction inherits from DEFAULT and states only what it changes. Colour
choices stay inside the constraints that are not up for debate: dark ground
(the device is read at close range mid-game), the warm bark/moss/parchment
family from the Revised Core box art, and WCAG AA on every ink/ground pair -
which `tests/test_contrast_skins.py` enforces per skin, so a direction that
fails is rejected mechanically rather than by eye.
"""
from ui.skin import DEFAULT

# -- 1. Flat ---------------------------------------------------------------
# Answers: "heavy bevels read dated".
#
# Removes the video-game chrome entirely and rebuilds depth out of VALUE
# instead of edges: the ground ramp widens (a darker bg, a lighter card) so a
# panel reads as a lit surface rather than as a bordered box. Nothing moves;
# only the edges go. This is the cheapest possible answer to the complaint and
# therefore the honest control for the more elaborate ones.
FLAT = DEFAULT.derive(
    "flat",
    note="No bevels. Depth from tonal separation rather than edges.",
    chrome={"bevel_t": 0, "panel_border": 1},
    colors={
        "bg":         (12, 10, 8),
        "card":       (34, 30, 22),
        "card_hi":    (46, 41, 30),
        "well":       (22, 19, 13),
        "border":     (56, 50, 36),
        "btn":        (58, 50, 34),
        "btn_ok":     (44, 56, 30),
        "btn_no":     (62, 30, 21),
        # bevel pens still exist (other widgets reference them); with bevel_t
        # at 0 they are simply never drawn.
    })


# -- 2. Ration -------------------------------------------------------------
# Answers: "gold on everything so gold means nothing".
#
# Gold stops being the default ink and becomes the focal marker: exactly one
# element per screen earns it. Body text moves up to a brighter parchment so
# it reads as the primary content it is, and the secondary ramp cools slightly
# so metadata recedes without dropping below AA. The border ramp dims so a
# gold edge means "this one matters" instead of competing with every panel.
RATION = DEFAULT.derive(
    "ration",
    note="Gold reserved for one focal element. Parchment carries the body.",
    colors={
        "tan":         (214, 203, 172),   # body ink, brighter: it is the content
        "muted":       (172, 160, 132),
        # 153 not 146: at 146 this fell to 4.23:1 on card_hi, below AA.
        # The per-skin contrast gate caught it before the pane did.
        "dim":         (153, 143, 120),
        "gold":        (226, 188, 104),   # rarer, so it can be louder
        "border":      (48, 44, 32),      # ordinary edges recede
        "border_gold": (168, 128, 48),    # and the one that matters does not
        "card":        (33, 30, 22),
        "card_hi":     (44, 40, 30),
    })


# -- 3. Ember --------------------------------------------------------------
# Answers: "no hierarchy" and "the nav CTA borrows the green confirm colour".
#
# Pushes the semantic trio apart so red/green/amber stop reading as three
# warm neighbours, and darkens the ground beneath them so they carry more of
# the hierarchy. The CTA green shifts cooler than the "your window" green, so
# navigation and permission stop sharing a colour - the one piece of colour
# vocabulary a player has to learn.
EMBER = DEFAULT.derive(
    "ember",
    note="Semantics pushed apart; navigation stops borrowing the window green.",
    colors={
        "bg":       (14, 11, 10),
        "card":     (38, 32, 24),
        "card_hi":  (52, 44, 32),
        "green":    (124, 176, 96),      # "your window"
        "ok_fg":    (150, 200, 168),     # navigation: cooler, distinct
        "btn_ok":   (32, 52, 44),
        # nudged up from (240, 96, 64), which read 4.23:1 on this
        # skin's lighter card_hi - below the body threshold
        "red":      (243, 106, 72),
        "dim":      (165, 148, 102),
        "amber":    (226, 168, 62),
        "gold":     (218, 182, 112),
        "border":   (66, 58, 38),
    })


# -- 4. Stark (evidence, not a candidate) ----------------------------------
# Nobody would ship this. It exists to answer a question the three candidates
# above raised by looking so similar to the control: is that because they are
# timid, or because colour cannot carry this overhaul at all?
#
# So it takes every colour and chrome lever to its limit - gold retired
# outright, cards nearly twice as light, every border and bevel removed - and
# still clears AA on every ink/ground pair. Rendered, it is unmistakably the
# same screen.
#
# THE FINDING: what makes this design look the way it does is its GEOMETRY,
# not its palette. The header bar, the eight-pill strip, the band with its
# red/green edge, two equal counter boxes, the bottom nav trio - that
# silhouette survives any repaint. Which is exactly what the honest critique
# said in structural terms: "every screen is the same template (header,
# numbered cards, tip, big button). No hierarchy ... dead vertical space."
#
# A palette-and-chrome round therefore cannot answer the complaint that
# started this work. Element vocabulary and composition have to move.
STARK = DEFAULT.derive(
    "stark",
    note="Evidence probe, not a candidate: every colour lever at its limit, "
         "and still the same screen. Colour cannot carry this overhaul.",
    chrome={"bevel_t": 0, "panel_border": 0},
    colors={
        "bg":      (8, 8, 9),
        "card":    (58, 54, 44),
        "card_hi": (72, 66, 54),
        "well":    (40, 37, 30),
        "border":  (58, 54, 44),
        "gold":    (236, 228, 210),
        "tan":     (236, 228, 210),
        "muted":   (206, 198, 182),
        "dim":     (186, 178, 162),
        "btn":     (86, 80, 66),
        "btn_ok":  (54, 74, 44),
    })


# Shippable directions, all gated by tests/test_contrast_skins.py.
CANDIDATES = [DEFAULT, FLAT, RATION, EMBER]

# STARK is deliberately NOT in CANDIDATES. It fails the accessibility gate,
# and that failure is the second finding: its light card ground cannot carry
# the semantic red. Red's luminance ceiling is low, so no brightening reaches
# 4.5:1 on a light warm panel without turning it pink and destroying what the
# colour means. The brightest card_hi that keeps red at AA is (47, 43, 35) -
# and the shipped value, (48, 44, 29), is already sitting on that ceiling.
#
# So the ground ramp has nowhere to go. Between a floor set by AA on the ink
# and a ceiling set by AA on the red, a direction has almost no room to move
# in colour alone. That, not timidity, is why FLAT / RATION / EMBER all read
# as the same screen.
EVIDENCE = [STARK]

ROUND2 = CANDIDATES + EVIDENCE
