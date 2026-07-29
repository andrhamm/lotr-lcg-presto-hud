"""Drawing helpers + a Button hit-region. Take a PicoGraphics-like display.

NOWRAP: PicoGraphics text() word-wraps at its wordwrap argument — passing 0
stacks every word vertically. All text here is pre-wrapped by wrap_text, so
every draw passes NOWRAP (a width no string can reach) to disable it.
"""
import math

from ui.theme import DISPLAY, BODY, LABEL

NOWRAP = 10000


class Button:
    """A rectangular tap target with an id, plus optional payload."""

    def __init__(self, id, x, y, w, h, data=None):
        self.id = id
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.data = data

    def hit(self, px, py):
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h


def panel(d, pal, x, y, w, h, fill=None, border=None):
    """Filled rect with a 1px inner border (PicoGraphics has no outline)."""
    d.set_pen(border if border is not None else pal.border)
    d.rectangle(x, y, w, h)
    d.set_pen(fill if fill is not None else pal.card)
    d.rectangle(x + 1, y + 1, w - 2, h - 2)


def bevel(d, pal, x, y, w, h, fill, pressed=False, t=2):
    """Video-game chrome: raised face (light top-left, dark bottom-right);
    pressed inverts the bevel."""
    lo, hi = (pal.bevel_l, pal.bevel_d) if pressed else (pal.bevel_d, pal.bevel_l)
    d.set_pen(fill)
    d.rectangle(x, y, w, h)
    d.set_pen(hi)
    d.rectangle(x, y, w, t)
    d.rectangle(x, y, t, h)
    d.set_pen(lo)
    d.rectangle(x, y + h - t, w, t)
    d.rectangle(x + w - t, y, t, h)


def _arrow(d, pal, cx, cy, size, pen, left, shadow=True):
    """Solid triangular arrow, drawn with d.triangle (device-safe - the same
    primitive draw_notif_pie uses). size is the full width/height."""
    h = size // 2
    tip, base = (cx - h, cx + h) if left else (cx + h, cx - h)
    if shadow:
        d.set_pen(pal.shadow)
        d.triangle(tip + 2, cy + 2, base + 2, cy - h + 2, base + 2, cy + h + 2)
    d.set_pen(pen)
    d.triangle(tip, cy, base, cy - h, base, cy + h)


def arrow_left(d, pal, cx, cy, size, pen, shadow=True):
    _arrow(d, pal, cx, cy, size, pen, True, shadow)


def arrow_right(d, pal, cx, cy, size, pen, shadow=True):
    _arrow(d, pal, cx, cy, size, pen, False, shadow)


def text_left(d, pal, s, x, y, scale, pen, shadow=True):
    if shadow:
        off = 1 if scale == LABEL else 2
        d.set_pen(pal.shadow)
        d.text(s, x + off, y + off, NOWRAP, scale)
    d.set_pen(pen)
    d.text(s, x, y, NOWRAP, scale)


def text_center(d, pal, s, cx, y, scale, pen, shadow=True):
    w = d.measure_text(s, scale)
    x = int(cx - w / 2)
    if shadow:
        off = 1 if scale == LABEL else 2
        d.set_pen(pal.shadow)
        d.text(s, x + off, y + off, NOWRAP, scale)
    d.set_pen(pen)
    d.text(s, x, y, NOWRAP, scale)


def button(d, pal, btn, label, scale=BODY, fill=None, fg=None, pressed=False):
    bevel(d, pal, btn.x, btn.y, btn.w, btn.h,
          fill if fill is not None else pal.btn, pressed=pressed)
    ch = 8 * scale
    off = 1 if pressed else 0
    text_center(d, pal, label, btn.x + btn.w / 2 + off,
                int(btn.y + (btn.h - ch) / 2) + off,
                scale, fg if fg is not None else pal.tan)


def stepper(d, pal, buttons, id_minus, id_plus, x, y, value_str, w=200, h=56):
    """Draw [ - ][ value ][ + ] within width w; append the two Buttons."""
    bw = h
    minus = Button(id_minus, x, y, bw, h)
    plus = Button(id_plus, x + w - bw, y, bw, h)
    button(d, pal, minus, "-", DISPLAY)
    button(d, pal, plus, "+", DISPLAY)
    text_center(d, pal, value_str, x + w / 2, int(y + (h - 24) / 2), DISPLAY, pal.gold)
    buttons.append(minus)
    buttons.append(plus)


def row_label(d, pal, s, x, y, scale=BODY, pen=None):
    text_left(d, pal, s, x, y, scale, pen if pen is not None else pal.tan)


def wrap_text(s, scale, max_w, measure):
    """Word-wrap s to fit max_w pixels at scale. measure(s, scale) -> px.
    Long words are hard-broken. Always returns at least one line."""
    if measure(s, scale) <= max_w:
        return [s]
    lines = []
    cur = ""
    for word in s.split(" "):
        cand = (cur + " " + word) if cur else word
        if measure(cand, scale) <= max_w:
            cur = cand
            continue
        if cur:
            lines.append(cur)
            cur = ""
        # hard-break a word that alone exceeds the width
        while measure(word, scale) > max_w:
            i = len(word)
            while i > 1 and measure(word[:i], scale) > max_w:
                i -= 1
            lines.append(word[:i])
            word = word[i:]
        cur = word
    if cur or not lines:
        lines.append(cur)
    return lines


def truncate_text(s, scale, max_w, measure):
    """Truncate s with '..' to fit max_w pixels at scale."""
    if measure(s, scale) <= max_w:
        return s
    while s and measure(s + "..", scale) > max_w:
        s = s[:-1]
    return s + ".."


def ribbon(d, pal, x, y, w=12, h=22):
    """Book-ribbon first-player marker hanging from a card's top edge."""
    d.set_pen(pal.gold)
    d.rectangle(x, y, w, h)
    # V-notch at the bottom (cut out with the card fill color)
    d.set_pen(pal.card)
    d.triangle(x, y + h, x + w, y + h, x + w // 2, y + h - 7)


def ribbon_h(d, pal, y, w, h, notch=10, fill=None):
    """First-player ribbon running in from the LEFT SCREEN EDGE, with a V-notch
    bitten out of its right end - the horizontal banner reading of the same
    marker `ribbon` hangs vertically. The label sits INSIDE it, so the marker
    and the name it marks are one object rather than two things side by side."""
    d.set_pen(fill if fill is not None else pal.gold)
    d.rectangle(0, y, w, h)
    d.set_pen(pal.bg)
    d.triangle(w, y, w, y + h, w - notch, y + h // 2)


# Guidance-band metrics, shared by note_panel and phase_block.
#
# These were two sets of numbers for one visual element. phase_block padded 6
# and stepped 24; note_panel padded 8 and stepped 26, and two hand-rolled
# copies of note_panel in screen_play inlined its 8/26 again. So the same band
# drawn on two adjacent views had different leading, which is exactly the kind
# of drift nobody sees in one screenshot and everybody feels walking a round.
BAND_PAD = 6                       # top and bottom padding inside the band


def band_line_h(scale=BODY):
    """Line pitch inside a guidance band. 24px at BODY, which is what every
    phase view already used."""
    return 10 * scale + 4


def note_panel(d, pal, x, y, w, text, scale=BODY, reserve_right=0, icon=None,
               accent=None):
    """Distinct style for phase reminder messages: dark panel, gold edge,
    muted text, and (by default) the hobbit-pipe hint medallion on the left.
    Accepts a string or list of paragraphs; each is word-wrapped to the usable
    width (minus icon gutter and reserve_right). Returns the panel height.

    `accent` overrides the left bar's colour, because the BAR is the
    vocabulary - red happens anyway, green is your window, gold is a hint -
    and it belongs to the meaning of the content, not to the widget that
    happens to draw it. phase_block owns red/green for phase copy; this lets a
    band keep note_panel's paragraph wrapping while still saying green.""" 
    from ui import icons as _icons
    if icon is None:
        icon = _icons.PIPE
    isz = len(icon) if icon else 0
    gutter = isz + 14 if icon is not False else 0
    paras = [text] if isinstance(text, str) else list(text)
    usable = w - 16 - 12 - gutter - reserve_right
    lines = []
    for p in paras:
        lines.extend(wrap_text(p, scale, usable, d.measure_text))
    lh = band_line_h(scale)
    h = max(len(lines) * lh + 2 * BAND_PAD, isz + 14 if gutter else 0)
    d.set_pen(pal.card_hi)
    d.rectangle(x, y, w, h)
    d.set_pen(accent if accent is not None else pal.border_gold)
    d.rectangle(x, y, 4, h)
    if gutter:
        _icons.draw(d, icon, x + 10, y + BAND_PAD, pal.gold)  # top-left, not centered
    ty = y + BAND_PAD
    for s in lines:
        text_left(d, pal, s, x + 12 + gutter, ty, scale, pal.muted)
        ty += lh
    return h


def phase_block(d, pal, x, y, w, sections, reserve_right=0):
    """Phase-guidance panel - the semantic sibling of note_panel(). One box;
    each section is a run of BODY lines with a coloured bar down its left
    edge. `sections` is an ordered list of (kind, text) tuples (kind is
    "framework" or "window"; text is a string or list of paragraphs). A phase
    with no mandatory framework step just omits that entry.

    The bar is the whole vocabulary: red = happens whether or not you act,
    green = your window to act (the rulebook's own turn-sequence colour code,
    design/design-review.md). It used to also print FRAMEWORK / YOUR WINDOW
    label rows; those were dropped - the colour already says it, the terms
    were jargon, and the two label rows cost ~20px on every phase screen.
    Settings -> Help teaches the pairing. Returns the panel height."""
    usable = w - 14 - 12 - reserve_right
    laid = []
    for kind, text in sections:
        body = " ".join(text) if isinstance(text, (list, tuple)) else text
        lines = wrap_text(body, BODY, usable, d.measure_text)
        laid.append((kind, lines, len(lines) * band_line_h()))
    h = 2 * BAND_PAD + sum(sec_h for _, _, sec_h in laid) \
        + BAND_PAD * (len(laid) - 1)
    d.set_pen(pal.card_hi)
    d.rectangle(x, y, w, h)
    ty = y + BAND_PAD
    for kind, lines, sec_h in laid:
        # The accent bar alone says which kind this is - no label row. Red =
        # happens whether or not you act; green = your window to act. That
        # pairing is taught in Settings -> Help, and dropping the words buys
        # back ~20px on every phase screen, which is the space that used to
        # get taken out of the type.
        d.set_pen(pal.red if kind == "framework" else pal.green)
        d.rectangle(x, ty, 4, sec_h)
        ly = ty
        for s in lines:
            text_left(d, pal, s, x + 14, ly, BODY, pal.tan)
            ly += band_line_h()
        ty += sec_h + BAND_PAD
    return h


def willpower_staging_meter(d, pal, x, y, w, willpower, staging):
    """Live head-to-head bar: willpower (gold, left) vs staging threat
    (dark pal.outline, right - staging threat is never red, per
    design/stat-system.md's staging/enemy-threat rule) - the "willpower
    vs staging, live" stat from design/design-review.md's Quest-Staging
    row. Draws straight from the passed-in numbers, so it reflects every
    -/+ stepper tap immediately, no separate commit step. Reuses the
    existing outcome-sentence wording verbatim. Fixed height: 64."""
    from ui import icons as _icons
    icons_draw = _icons.draw
    icons_draw(d, _icons.WILLPOWER, x, y, pal.gold)
    icons_draw(d, _icons.THREAT, x + w - len(_icons.THREAT), y, pal.outline)
    bx, bw, bar_y, bar_h = x + 26, w - 52, y + 5, 10
    d.set_pen(pal.well)
    d.rectangle(bx, bar_y, bw, bar_h)
    total = willpower + staging
    left_w = round(bw * willpower / total) if total > 0 else round(bw / 2)
    if left_w > 0:
        d.set_pen(pal.gold)
        d.rectangle(bx, bar_y, left_w, bar_h)
    if bw - left_w > 0:
        d.set_pen(pal.outline)
        d.rectangle(bx + left_w, bar_y, bw - left_w, bar_h)
    d.set_pen(pal.dim)
    d.rectangle(x + round(w / 2) - 1, bar_y - 3, 2, bar_h + 6)   # tie marker
    ly = bar_y + bar_h + 14
    diff = willpower - staging
    if diff != 0:
        pre = "%s will gain %d " % ("You" if diff > 0 else "Each player", abs(diff))
        pre_w = d.measure_text(pre, BODY)
        ic = _icons.TRAIL if diff > 0 else _icons.THREAT_SM
        tail = "at resolution."
        total_w = pre_w + len(ic) + 6 + d.measure_text(tail, BODY)
        lx = x + round((w - total_w) / 2)
        text_left(d, pal, pre, lx, ly, BODY, pal.muted)
        icons_draw(d, ic, lx + pre_w, ly - 1, pal.gold if diff > 0 else pal.red)
        text_left(d, pal, tail, lx + pre_w + len(ic) + 6, ly, BODY, pal.muted)
    else:
        text_center(d, pal, "Tied - no change at resolution.", x + w / 2, ly, BODY, pal.dim)
    return 64


def draw_flag(d, x, y, h, pen):
    """Small pennant flag (a target reached its max). rect pole + triangle."""
    d.set_pen(pen)
    d.rectangle(x, y, max(2, int(h * 0.14)), h)
    d.triangle(int(x + h * 0.14), y,
               int(x + h * 0.95), int(y + h * 0.18),
               int(x + h * 0.14), int(y + h * 0.4))


def draw_heart(d, pal, cx, cy, r, broken, pen):
    """Small heart (quest-outcome marker); `broken` carves a jagged notch.
    Blocky rect+triangle build - PicoGraphics has no bezier, and the two lobes
    read as a heart above the downward point."""
    lobe_h = max(2, int(r * 0.75))
    lobe_w = max(2, int(r))
    top = int(cy - r * 0.7)
    d.set_pen(pen)
    d.rectangle(cx - lobe_w, top, lobe_w, lobe_h)          # left lobe
    d.rectangle(cx, top, lobe_w, lobe_h)                   # right lobe
    d.triangle(cx - lobe_w, int(cy - r * 0.2),             # bottom point
               cx + lobe_w, int(cy - r * 0.2),
               cx, int(cy + r))
    if broken:
        w = max(1, int(r * 0.22))
        d.set_pen(pal.bg)
        d.rectangle(cx - w // 2, top, w, lobe_h + 2)                    # upper crack
        d.rectangle(int(cx - r * 0.35), int(cy - r * 0.1), w, int(r * 0.7))  # lower (offset)


def disc(d, cx, cy, rad, pen):
    """Filled circle via per-scanline rect runs (device has no circle prim)."""
    d.set_pen(pen)
    for py in range(int(cy - rad), int(cy + rad) + 1):
        h2 = rad * rad - (py - cy) ** 2
        if h2 < 0:
            continue
        hx = int(math.sqrt(h2))
        d.rectangle(int(cx - hx), py, 2 * hx + 1, 1)


def arc_runs(d, cx, cy, R, r, a0, a1, pen):
    """Ring/arc band between radii r..R and angles a0..a1 (0deg=top, cw)."""
    d.set_pen(pen)
    for py in range(int(cy - R), int(cy + R) + 1):
        run = False
        x0 = 0
        for px in range(int(cx - R), int(cx + R) + 2):
            dx, dy = px - cx, py - cy
            dd = math.sqrt(dx * dx + dy * dy)
            on = r <= dd <= R
            if on and a1 is not None:
                ang = math.degrees(math.atan2(dx, -dy)) % 360.0
                on = a0 <= ang <= a1
            if on and not run:
                run, x0 = True, px
            elif not on and run:
                d.rectangle(x0, py, px - x0, 1)
                run = False


def ring(d, cx, cy, R, w, frac, fill, track):
    """Thin ring of width w at radius R: full track pen + a frac-of-360 fill
    arc clockwise from the top (0deg)."""
    arc_runs(d, cx, cy, R, R - w, 0, 360, track)
    if frac > 0:
        arc_runs(d, cx, cy, R, R - w, 0, frac * 360.0, fill)


def token(d, pal, cx, cy, R, w, value, vpen, frac, fill, track, vscale=2):
    """Circular stat widget: inset well disc + progress ring + centred value."""
    disc(d, cx, cy, R, pal.well)
    ring(d, cx, cy, R, w, frac, fill, track)
    if value is not None:
        text_center(d, pal, str(value), cx, int(cy - 4 * vscale), vscale, vpen)


def circ_btn(d, pal, cx, cy, r, glyph, pen=None):
    """Circular -/+ (or similar single-glyph) button: btn disc + light
    affordance ring + centred glyph. The drawn circle is small (r~10-11);
    callers push a >=24px Button separately for the actual tap target,
    centred on the same (cx, cy)."""
    disc(d, cx, cy, r, pal.btn)
    arc_runs(d, cx, cy, r, r - 2, 0, 360, pal.bevel_l)
    text_center(d, pal, glyph, cx, int(cy - 8), BODY, pen if pen is not None else pal.tan)


def wx_small(d, pal, idx, cx, cy, r, pen=None):
    """Tiny weather glyph from rect/tri/disc (the 24px icon masks are too big
    for the small heading tokens). idx 0 sun / 1 cloud / 2 rain / 3 storm.
    `pen` forces one colour (e.g. dim for an inactive radio); None = natural."""
    if idx == 0:
        disc(d, cx, cy, r, pen if pen is not None else pal.amber)
        disc(d, cx - 1, cy - 1, max(1, r // 2), pen if pen is not None else pal.gold)
        d.set_pen(pen if pen is not None else pal.amber)
        for dx, dy in ((0, -r - 3), (0, r + 1), (-r - 3, 0), (r + 1, 0)):
            d.rectangle(cx + dx, cy + dy, 2, 2)
        return
    cloud = pen if pen is not None else pal.muted
    disc(d, cx - 3, cy, r - 1, cloud)
    disc(d, cx + 3, cy - 1, r - 2, cloud)
    disc(d, cx, cy - 2, r - 1, cloud)
    d.set_pen(cloud)
    d.rectangle(cx - 6, cy, 12, r - 1)
    if idx == 2:
        d.set_pen(pen if pen is not None else pal.dim)
        for k in (-3, 1, 5):
            d.rectangle(cx + k, cy + r - 1, 1, 3)
    elif idx == 3:
        d.set_pen(pen if pen is not None else pal.gold)
        d.triangle(cx, cy + r - 2, cx - 3, cy + r + 3, cx + 2, cy + r)


# heading facing -> (icon mask name, pen attr). Masks live in ui/icons.py.
_WEATHER = [("SUN", "amber"), ("CLOUD", "cloud"), ("RAIN", "sky"), ("STORM", "dim")]


def draw_weather(d, pal, idx, cx, cy, r):
    """Heading facing glyph via the shared icon masks (SUN/CLOUD/RAIN/STORM),
    tinted. Centred on (cx, cy). The masks are 24px = 2*r at the card's r=12."""
    from ui import icons as _icons
    name, pen_attr = _WEATHER[idx]
    mask = getattr(_icons, name)
    size = len(mask)
    _icons.draw(d, mask, int(cx - size / 2), int(cy - size / 2), getattr(pal, pen_attr))
