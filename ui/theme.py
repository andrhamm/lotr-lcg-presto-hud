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


# Colour now lives in ui/skin.py, so a look is a value rather than a diff
# against these modules. RGB stays as the module-level view of the ACTIVE
# skin's colours - a pen is an opaque handle, it cannot be dimmed, only
# replaced, so anything wanting "the same colour, turned down" has to start
# from the numbers (see Palette.shaded()).
from ui.skin import DEFAULT as DEFAULT_SKIN

RGB = DEFAULT_SKIN.colors
SLATE = RGB["slate"]
DIM_FACTOR = 0.55      # an eliminated stat pill: low enough to recede, high
                       # enough to still read what the player finished on


class Palette:
    """Pens for one skin.

    Every pen is built from the skin's colour map, so the pen NAMES - which
    are the design system's documented vocabulary (ink / semantic / ground /
    controls) - stay fixed while the colours behind them vary. A draw site
    asks for `pal.gold` and never learns which skin it got.
    """

    def __init__(self, d, skin=None):
        self.skin = skin or DEFAULT_SKIN
        self._d = d
        self._shaded = {}

        for name, rgb in self.skin.colors.items():
            setattr(self, name, d.create_pen(*rgb))
        for alias, target in self.skin.aliases.items():
            setattr(self, alias, getattr(self, target))

    # -- chrome ------------------------------------------------------------
    def __getattr__(self, key):
        """Chrome parameters read through the palette: `pal.bevel_t`.

        Widgets already receive `pal` everywhere they draw, so routing chrome
        through it avoids threading a second argument through every call
        site. Only reached when normal lookup fails.
        """
        try:
            return self.__dict__["skin"].chrome[key]
        except KeyError:
            raise AttributeError("palette has no attribute %r" % (key,))

    # -- shading -----------------------------------------------------------
    def shaded(self, name, factor=DIM_FACTOR):
        """A pen's own colour at `factor` brightness.

        Needed because a pen is an opaque handle - it cannot be dimmed, only
        replaced - so anything that wants "the same thing, turned down" has to
        go back to the RGB. Eliminated stat pills shade every colour they use
        through here, which is what makes them read as the same object turned
        off rather than as a different object drawn in one flat grey.
        """
        key = (name, factor)
        if key not in self._shaded:
            r, g, b = self.skin.colors[name]
            self._shaded[key] = self._d.create_pen(
                int(r * factor), int(g * factor), int(b * factor))
        return self._shaded[key]

    def threat_pen(self, threat):
        """Where threat turns amber then red - a skin decision, not a rule.

        Elimination is at 50 regardless of how the ramp is coloured.
        """
        for floor, pen in self.skin.threat_bands:
            if threat >= floor:
                return getattr(self, pen)
        return self.green
