"""Palette derived from the Revised Core box art (bark, moss, parchment,
ember) + bevel pens for the video-game chrome. Pens are created lazily from a
PicoGraphics display.

Also the home of the **type scale** - see docs/superpowers/specs/
2026-07-25-design-system.md for the rules these names encode, and
tests/test_typography.py for the gate that enforces them.
"""

# -- type scale ---------------------------------------------------------
# The device font is a bitmap8, so "size" is an integer multiplier and there
# are only three of them. Use the NAMES, not the numbers: a bare `1` at a
# draw site is how prose keeps ending up unreadably small, which has been
# reported more than once.
#
#   BODY is the default. If a player READS it as a sentence - card text,
#   tips, rules captions, empty states, option names - it is BODY. "It did
#   not fit" is not a reason to drop to LABEL; page it, truncate it with a
#   "more" affordance, or give it less to say.
DISPLAY = 3   # screen + modal titles, the primary CTA
BODY = 2      # DEFAULT: anything read as a sentence or a name
LABEL = 1     # ALL-CAPS section labels + dense tabular metadata ONLY
#
# Above DISPLAY there is no reading tier - only numerals and wordmarks: the
# threat/willpower counters, the sailing dial, "LOTR LCG" on boot, "VICTORY!".
# Those sizes are chosen by the widget that owns the numeral, not at a call
# site, and a sentence may never use them.


class Palette:
    def __init__(self, d):
        # ground
        self.bg = d.create_pen(16, 12, 9)
        self.card = d.create_pen(36, 32, 21)
        self.card_hi = d.create_pen(48, 44, 29)
        self.border = d.create_pen(60, 54, 35)
        self.border_gold = d.create_pen(150, 118, 48)
        # ink
        self.gold = d.create_pen(214, 180, 110)
        self.tan = d.create_pen(200, 186, 144)
        self.muted = d.create_pen(180, 162, 118)
        # stat-value ink (threat / willpower / progress) - one constant colour
        self.value = self.gold
        self.dim = d.create_pen(162, 146, 100)
        # semantics
        self.green = d.create_pen(136, 168, 92)
        self.amber = d.create_pen(214, 164, 70)
        self.red = d.create_pen(247, 101, 62)
        # weather (heading facing glyphs)
        self.cloud = d.create_pen(185, 188, 198)
        self.sky = d.create_pen(95, 168, 230)
        # progress-token brown (dropshadow behind the green ranger/trail icon)
        self.brown = d.create_pen(104, 70, 34)
        # controls
        self.btn = d.create_pen(52, 42, 26)
        self.btn_ok = d.create_pen(40, 50, 26)
        self.ok_fg = d.create_pen(158, 196, 104)
        self.btn_no = d.create_pen(56, 26, 18)
        self.no_fg = d.create_pen(224, 112, 80)
        self.tab_active = d.create_pen(30, 24, 15)
        # bevels (video-game chrome: light top-left, dark bottom-right)
        self.bevel_l = d.create_pen(96, 86, 54)
        self.bevel_d = d.create_pen(7, 5, 3)
        self.shadow = d.create_pen(34, 30, 24)
        # leadership purple (action-window notifications)
        self.purple = d.create_pen(166, 122, 196)
        # true black-ish ink (staging threat value/icon, shadows)
        self.outline = d.create_pen(0, 0, 0)
        # inset value well
        self.well = d.create_pen(24, 20, 12)
        # lighter row-stripe background (by-round chart: makes black ink read)
        self.row_stripe = d.create_pen(66, 60, 42)
        # placeholder fill for undrawn scenario/set icons (Scenario Options -
        # real icons land in a later sub-project)
        self.iconslot = d.create_pen(44, 40, 28)
        # parchment fill for the Quest Setup scroll-style tip (deliberately
        # distinct from the standard note-panel card_hi background)
        self.scroll = d.create_pen(30, 26, 17)

    def threat_pen(self, threat):
        if threat >= 35:
            return self.red
        if threat >= 20:
            return self.amber
        return self.green
