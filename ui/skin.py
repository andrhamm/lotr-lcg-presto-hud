"""A skin: every visual literal in the app, as data.

WHY
---
The look has been reworked several times, and each time the numbers behind it
lived at their draw sites -- a bevel thickness here, a chamfer there, a pen
built inline in Palette. That makes a direction impossible to state: you
cannot compare two looks when each exists only as a diff against the widgets.

A skin makes a look a value. `Palette(display, skin)` builds every pen from
it, widgets read their chrome parameters off it, and rendering the same scene
under two skins is a loop rather than a branch.

WHAT BELONGS HERE
-----------------
Colour and style. NOT layout, and NOT touch geometry: `STEP_HIT`, `ROW_H` and
friends stay in `ui/widgets.py`, because a skin that could shrink a tap target
would let a visual choice break the >=24px rule the layout linter enforces.

The chrome field list is deliberately small. It covers what the current
elements are actually built from, and it grows when a direction needs
something -- a missing field is a real finding about the vocabulary, not an
oversight to paper over. Anything a skin genuinely cannot express is a hero
cut: a hand-built variant of one screen.

THE DEFAULT IS THE CURRENT LOOK, VERBATIM
-----------------------------------------
`DEFAULT` is an extraction, not a redesign. Every value here was read out of
the previous `ui/theme.py` and `ui/widgets.py`. `tests/test_skin_identity.py`
renders all 118 scenes under it and compares against recorded draw calls, so
the extraction is only correct if not one pixel moved.
"""

# -- colour ----------------------------------------------------------------
# Every pen the app draws with, by name. Palette turns these into pens; the
# names are the vocabulary the design system documents (ink / semantic /
# ground / controls), so renaming one is a design-system change.
DEFAULT_COLORS = {
    # ground: a depth ramp, darkest first
    "bg":          (16, 12, 9),
    "card":        (36, 32, 21),
    "card_hi":     (48, 44, 29),
    "well":        (24, 20, 12),
    "border":      (60, 54, 35),
    "border_gold": (150, 118, 48),
    # ink: dim < muted < tan is a deliberate ramp, asserted by test_contrast
    "gold":        (214, 180, 110),
    "tan":         (200, 186, 144),
    "muted":       (180, 162, 118),
    "dim":         (162, 146, 100),
    # semantics
    "green":       (136, 168, 92),
    "amber":       (214, 164, 70),
    "red":         (247, 101, 62),
    # weather glyphs
    "cloud":       (185, 188, 198),
    "sky":         (95, 168, 230),
    # dropshadow behind the green ranger/trail progress icon
    "brown":       (104, 70, 34),
    # controls
    "btn":         (52, 42, 26),
    "btn_ok":      (40, 50, 26),
    "ok_fg":       (158, 196, 104),
    "btn_no":      (56, 26, 18),
    "no_fg":       (224, 112, 80),
    "tab_active":  (30, 24, 15),
    # bevels: light top-left, dark bottom-right
    "bevel_l":     (96, 86, 54),
    "bevel_d":     (7, 5, 3),
    "shadow":      (34, 30, 24),
    # spheres
    "purple":      (166, 122, 196),
    # true black-ish ink (staging threat value/icon, shadows)
    "outline":     (0, 0, 0),
    # lighter row stripe: makes black ink read on the by-round chart
    "row_stripe":  (66, 60, 42),
    # placeholder fill for an unmatched scenario/set icon
    "iconslot":    (44, 40, 28),
    # parchment fill for the Quest Setup scroll, deliberately distinct from
    # the standard note-panel card_hi
    "scroll":      (30, 26, 17),
    # The one deliberately COOL ink, reserved for labels that NAME a value
    # rather than being one. Every other pen is the same warm hue at a
    # different lightness, so a label beside a gold stat value could only
    # differ from it by brightness -- which at BODY on a dark ground reads as
    # the same colour.
    "slate":       (124, 138, 152),
}

# Pens that are aliases of another, not colours in their own right.
# `value` is an alias of `gold` so every stat numeral reads as one family;
# a skin that wants stat values to diverge from headings changes it here.
DEFAULT_ALIASES = {"value": "gold"}

# -- chrome ----------------------------------------------------------------
# Style parameters lifted from their draw sites. Each names the element it
# shapes, because that is how a direction talks about them.
DEFAULT_CHROME = {
    # panel: 1px inner border (PicoGraphics has no outline primitive, so a
    # border is a filled rect with a smaller filled rect on top)
    "panel_border": 1,
    # bevel: how thick the raised edge is. 0 renders flat, which is a whole
    # visual direction on its own -- the honest critique called the current
    # bevels "dated".
    "bevel_t": 2,
    # stat pills
    "pill_h": 28,          # fits the 20px icon masks plus 4px of air
    "pill_cap": 3,         # chamfer at each end; no rounded-rect primitive
    "pill_notch": 6,
    "pill_slash": 3,
    # guidance bands (note_panel + phase_block, one padding and one pitch)
    "band_pad": 6,
    "band_lead": 4,        # added to 10*scale for the line pitch
    # first-player ribbon
    "ribbon_notch": 7,
    # progress rings
    "ring_w": 6,
}

# Threat colour thresholds. Where a stat turns amber and then red is a visual
# decision about how alarming to be, not a rule of the game -- elimination is
# at 50 regardless.
DEFAULT_THREAT_BANDS = ((35, "red"), (20, "amber"), (0, "green"))

# Which font and multiplier each type tier resolves to. bitmap8 across the
# board, an 8/16/24px ladder. Round 1 of the visual overhaul measured the
# alternatives and kept this: font14_outline has no size below 14px so it
# cannot supply a LABEL that reads smaller than its own BODY, and font6 is
# uppercase-only, which the design system disqualifies outright.
DEFAULT_TYPE = {1: ("font8", 1), 2: ("font8", 2), 3: ("font8", 3)}


class Skin:
    """A named look. Everything visual, nothing structural."""

    def __init__(self, name, colors=None, aliases=None, chrome=None,
                 threat_bands=None, type_binding=None, note=""):
        self.name = name
        self.note = note
        self.colors = dict(DEFAULT_COLORS)
        self.colors.update(colors or {})
        self.aliases = dict(DEFAULT_ALIASES)
        self.aliases.update(aliases or {})
        self.chrome = dict(DEFAULT_CHROME)
        self.chrome.update(chrome or {})
        self.threat_bands = threat_bands or DEFAULT_THREAT_BANDS
        self.type_binding = dict(type_binding or DEFAULT_TYPE)

    def __getattr__(self, key):
        """Chrome fields read as attributes: `skin.bevel_t`.

        Only reached when normal lookup fails, so it never shadows a real
        attribute. Raises AttributeError (not KeyError) for an unknown field,
        so a typo fails the way a typo should.
        """
        try:
            return self.__dict__["chrome"][key]
        except KeyError:
            raise AttributeError(
                "%r skin has no chrome field %r" % (self.__dict__.get("name"), key))

    def derive(self, name, note="", **kw):
        """A variant of this skin. Colours and chrome merge over the parent's,
        so a direction states only what it changes."""
        colors = dict(self.colors)
        colors.update(kw.pop("colors", None) or {})
        chrome = dict(self.chrome)
        chrome.update(kw.pop("chrome", None) or {})
        return Skin(name, colors=colors, aliases=dict(self.aliases),
                    chrome=chrome,
                    threat_bands=kw.pop("threat_bands", self.threat_bands),
                    type_binding=kw.pop("type_binding", self.type_binding),
                    note=note)


DEFAULT = Skin(
    "default",
    note="The current look, extracted verbatim. Not a candidate - the control.")

SKINS = {DEFAULT.name: DEFAULT}


def register(skin):
    SKINS[skin.name] = skin
    return skin


def get(name):
    if name not in SKINS:
        raise SystemExit("unknown skin %r; have %s"
                         % (name, ", ".join(sorted(SKINS))))
    return SKINS[name]
