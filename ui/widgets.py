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


def front_face(card):
    """A card's front face, by POSITION - never by side letter.

    Quest stage cards are not all ("A","B"). Measured over the 514 stage cards
    in docs/data: 16 are ("C","D"), 5 are ("E","F"), 1 is ("G","H") and 4 are
    ("A","A"), with 6 more running ("A","C") through ("A","H"). Looking the
    front up as `side == "A"` therefore returned {} for 22 cards outright, so
    the stage-advance panel drew an empty title AND claimed the stage had no
    setup instructions - on cards that print plenty. faces[0] is the front on
    every card in the catalog. Found in the 2026-07-30 playtest of The Oath.
    """
    faces = (card or {}).get("faces") or []
    return faces[0] if faces else {}


def back_face(card):
    """A card's back face, by position. Same reason as front_face: the branch
    preview looked its alternatives up as `side == "B"` and drew "?" for every
    card whose faces are lettered anything else."""
    faces = (card or {}).get("faces") or []
    return faces[1] if len(faces) > 1 else {}


MORE_MARKER = " [...] more"


def fit_lines(measure, lines, max_lines, usable, more, marker=MORE_MARKER):
    """Trim lines to max_lines, marking the cut with "[...] more" so a
    truncated block never looks like the whole thing.

    The marker has to be made room for, not appended and truncated - appending
    then truncating cuts the marker itself down to "[...." and the affordance
    silently disappears. Was a private method on QuestCardModal until the
    stage-advance panel needed the same rule; one implementation, not two.
    """
    if len(lines) <= max_lines and not more:
        return lines, False
    keep = lines[:max_lines] or [""]
    mw = measure(marker, BODY)
    last = keep[-1]
    while last and measure(last, BODY) + mw > usable:
        last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
    keep[-1] = last + marker
    return keep, True


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
               accent=None, pen=None):
    """Distinct style for phase reminder messages: dark panel, gold edge,
    muted text, and (by default) the hobbit-pipe hint medallion on the left.
    Accepts a string or list of paragraphs; each is word-wrapped to the usable
    width (minus icon gutter and reserve_right). Returns the panel height.

    `accent` overrides the left bar's colour, because the BAR is the
    vocabulary - red happens anyway, green is your window, gold is a hint -
    and it belongs to the meaning of the content, not to the widget that
    happens to draw it. phase_block owns red/green for phase copy; this lets a
    band keep note_panel's paragraph wrapping while still saying green.

    `pen` overrides the ink. The default is `muted`, which suits a hint;
    guidance copy is body text and reads `tan`, the same as phase_block's, so
    a band that is guidance passes it rather than looking like a second
    tier of importance.""" 
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
        # x + 14, matching phase_block. These sat 2px apart for no reason.
        text_left(d, pal, s, x + 14 + gutter, ty, scale,
                  pen if pen is not None else pal.muted)
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
    # The bars TILE the left edge: together they cover the box's full height,
    # and the seam between them is where framework ends and window begins.
    # They used to span only their own text run, so they floated with 6px of
    # background above and below - which read as a different element from
    # note_panel's full-height bar, on screens a player sees one after the
    # other. A section's bar owns its share of the padding, not just its type.
    ty = y + BAND_PAD
    for i, (kind, lines, sec_h) in enumerate(laid):
        bar_top = y if i == 0 else ty - BAND_PAD // 2
        bar_bot = (y + h if i == len(laid) - 1
                   else ty + sec_h + BAND_PAD - BAND_PAD // 2)
        # The accent bar alone says which kind this is - no label row. Red =
        # happens whether or not you act; green = your window to act. That
        # pairing is taught in Settings -> Help, and dropping the words buys
        # back ~20px on every phase screen, which is the space that used to
        # get taken out of the type.
        d.set_pen(pal.red if kind == "framework" else pal.green)
        d.rectangle(x, bar_top, 4, bar_bot - bar_top)
        ly = ty
        for s in lines:
            text_left(d, pal, s, x + 14, ly, BODY, pal.tan)
            ly += band_line_h()
        ty += sec_h + BAND_PAD
    return h


def stat_pill(d, pal, x, y, threat, points, h=24, label="QP",
              measure_only=False):
    """Two-segment capsule: [threat icon + value | points + label].

    The horizontal sibling of token(), the main screen's circular stat widget -
    same idea (a value on its own ground) laid out for a list row.

    The LEFT segment carries a light fill so the threat can be BLACK, which
    design/stat-system.md requires (staging threat is never red; red is the
    player's own track). That is the only reason the fill exists: the screen
    ground is (16,12,9) and black on it is invisible. A bare 1px "shadow" did
    nothing for a 16px glyph, and a plain light box behind the icon read as an
    artefact rather than a widget - hence a real two-part pill.

    The RIGHT segment stays on the card ground with the points in gold, so the
    two numbers never read as the same kind of thing: one is threat the location
    adds to staging, the other is what it takes to explore.

    Corners are chamfered a pixel rather than rounded - PicoGraphics has no
    rounded rect, and at 24px tall one pixel is all a capsule needs.
    """
    from ui import icons as _icons
    mask = _icons.THREAT_SM
    iw = len(mask)
    ts = str(threat if threat is not None else 0)
    ps = str(points if points is not None else 0)
    wa = 6 + iw + 4 + d.measure_text(ts, BODY) + 6
    wb = 6 + d.measure_text(ps, BODY) + 4 + d.measure_text(label, LABEL) + 6
    w = wa + wb
    # Callers that right-align the pill need its width BEFORE they can place
    # it. Measuring by drawing off-screen (which is what the picker did, at
    # y=-99) puts rects outside the panel and stacks every row's numbers at one
    # point - 8 layout-linter failures, and invisible on a real screen because
    # the device just clips them.
    if measure_only:
        return w
    # body (right segment's ground), then the light left segment over it
    d.set_pen(pal.card_hi)
    d.rectangle(x, y, w, h)
    d.set_pen(pal.dim)
    d.rectangle(x, y, wa, h)
    # chamfer: bite one pixel out of each corner so it reads as a capsule
    d.set_pen(pal.bg)
    for cx in (x, x + w - 1):
        d.rectangle(cx, y, 1, 1)
        d.rectangle(cx, y + h - 1, 1, 1)
    # segment divider
    d.set_pen(pal.bg)
    d.rectangle(x + wa, y + 2, 1, h - 4)
    # left: black on the light ground
    _icons.draw(d, mask, x + 6, y + (h - iw) // 2, pal.outline)
    text_left(d, pal, ts, x + 6 + iw + 4, y + (h - 16) // 2 + 2, BODY,
              pal.outline, shadow=False)
    # right: the number the player acts on, in the app's value gold
    px = x + wa + 6
    text_left(d, pal, ps, px, y + (h - 16) // 2 + 2, BODY, pal.gold)
    # LABEL is the smaller tier, so it needs MORE top offset than the BODY
    # number to share a baseline with it, not less.
    text_left(d, pal, label, px + d.measure_text(ps, BODY) + 4,
              y + (h - 16) // 2 + 8, LABEL, pal.muted)
    return w


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
    """Ring/arc band between radii r..R and angles a0..a1 (0deg=top, cw).

    The original walked every pixel of the bounding box calling math.sqrt AND
    math.atan2 on each - ~2,070 pixels and ~4,100 trig calls for one r=22
    token, 119 ms, and PlayersDetailModal draws four of them, so a tap inside
    it cost 963 ms.

    Two changes, both of which reproduce the original's pixels exactly (there
    is a test that diffs them):

    * A FULL ring needs no angle test, so each row is two spans computed from
      integer arithmetic - the same shape `disc` above already uses. Comparing
      SQUARED distances keeps it exact: dd <= R is dx*dx + dy*dy <= R*R.
    * A PARTIAL arc still needs the angle, but only across the annulus this
      row actually covers, not the whole bounding box.
    """
    d.set_pen(pen)
    full = a1 is None or (a0 <= 0 and a1 >= 360)
    R2 = R * R
    r2 = r * r
    for py in range(int(cy - R), int(cy + R) + 1):
        dy = py - cy
        outer = R2 - dy * dy
        if outer < 0:
            continue
        hi = int(math.sqrt(outer))
        while (hi + 1) * (hi + 1) <= outer:      # exact floor
            hi += 1
        while hi * hi > outer:
            hi -= 1
        inner = r2 - dy * dy
        if inner <= 0:
            lo = 0                                # row misses the hole
        else:
            lo = int(math.sqrt(inner))
            while lo * lo < inner:                # exact ceil
                lo += 1
        if full:
            if lo == 0:
                d.rectangle(int(cx - hi), py, 2 * hi + 1, 1)
            elif lo <= hi:
                d.rectangle(int(cx - hi), py, hi - lo + 1, 1)
                d.rectangle(int(cx + lo), py, hi - lo + 1, 1)
            continue
        run = False
        x0 = 0
        for px in range(int(cx - hi), int(cx + hi) + 2):
            dx = px - cx
            dd2 = dx * dx + dy * dy
            on = r2 <= dd2 <= R2
            if on:
                ang = math.degrees(math.atan2(dx, -dy)) % 360.0
                on = a0 <= ang <= a1
            if on and not run:
                run, x0 = True, px
            elif not on and run:
                d.rectangle(x0, py, px - x0, 1)
                run = False
        if run:
            d.rectangle(x0, py, int(cx + hi) + 2 - x0, 1)


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


# --------------------------------------------------------------------------
# Stat pills
# --------------------------------------------------------------------------
#
# The play screen's top zone: a flowing row of segmented pills, one per player
# and one per progress track, replacing the two fixed 90px matrices.
#
#     [ P > (threat) | (willpower) ]  [ 1 < 25 | 3 ]  [ 2 > 28 | 2 ]  [ Q > 6 ]
#
# Segment 0 is the pill's HEADER - "P", the player number, "Q"/"L"/"S1". It has
# its own darker ground, a slate label, and a notched right edge, so it reads
# as a label FOR the segments after it rather than as a peer of them. The
# legend pill's two value segments carry the threat helm and willpower star;
# every player pill then drops the icons and lets the NUMBERS wear those same
# colours.
#
# Segments are FIXED width, not content width, so every player pill is the
# same size and the wrap is predictable instead of shifting as numbers change.
#
# Two shapes, one geometry, inverted:
#   * a plain header pushes its notch OUT to a point
#   * the FIRST PLAYER's header takes the notch IN - the same V-notch bitten
#     out of the right end that ribbon_h uses - and fills gold with its number
#     knocked out. Subtractive and rare, against additive and universal.
PILL_H = 28            # fits the 20px icon masks plus 4px of air
PILL_CAP = 3           # chamfer at each end; the device has no rounded rect,
                       # so a "pill" is a rect with its end columns drawn short
PILL_NOTCH = 6
PILL_GAP = 6
PILL_ROW_GAP = 5
# Sized from the widest real content: header "S2" is 18px, and the widest
# thing in a value slot is the 24px weather glyph ("100" is 26px, so a
# three-digit threat still fits).
PILL_HEAD_W = 28
PILL_VAL_W = 30


def _pill_shape(d, x, y, w, h, pen):
    """A rect with both ends chamfered - as close to a pill as rectangle and
    triangle get at this resolution."""
    d.set_pen(pen)
    c = PILL_CAP
    d.rectangle(x + c, y, w - 2 * c, h)
    d.rectangle(x, y + c, c, h - 2 * c)
    d.rectangle(x + w - c, y + c, c, h - 2 * c)
    d.rectangle(x + 1, y + 1, c - 1, c - 1)
    d.rectangle(x + w - c, y + 1, c - 1, c - 1)
    d.rectangle(x + 1, y + h - c, c - 1, c - 1)
    d.rectangle(x + w - c, y + h - c, c - 1, c - 1)


def _cap_left_fill(d, x, y, w, h, pen, c=PILL_CAP):
    """Fill a rect whose LEFT end is chamfered like _pill_shape's, right end
    square.

    The first-player ribbon used a plain rectangle here, which painted over the
    pill's left chamfer and left that end looking square while the right end
    stayed rounded. The ribbon is the pill's own ground, so it has to take the
    pill's shape.
    """
    d.set_pen(pen)
    d.rectangle(x + c, y, w - c, h)
    d.rectangle(x, y + c, c, h - 2 * c)
    d.rectangle(x + 1, y + 1, c - 1, c - 1)
    d.rectangle(x + 1, y + h - c, c - 1, c - 1)


def _pill_slash(d, x, y, w, h, pen, t=3):
    """A diagonal strike, stepped out of 1px rects - the device has no line
    primitive, and a triangle this thin renders as a wedge."""
    d.set_pen(pen)
    for i in range(max(1, w)):
        py = y + h - 1 - int(i * (h - 1) / float(max(1, w - 1)))
        d.rectangle(x + i, max(y, py - t // 2), 1, t)


def pill_width(segs):
    """Fixed width by role: segment 0 is the header, the rest are values."""
    return (PILL_HEAD_W + PILL_NOTCH + (len(segs) - 1) * PILL_VAL_W
            + (len(segs) - 2))


def pill(d, pal, x, y, segs, border=None, ribbon=False, dead=False):
    """Draw one pill. `segs` is [(kind, value, colour_name), ...] where kind is
    "text" or "icon" and colour_name indexes theme.RGB, so an eliminated pill
    can shade every colour it uses through Palette.shaded()."""
    def ink(name):
        return pal.shaded(name) if dead else getattr(pal, name)

    w = pill_width(segs)
    # The border is never shaded - it is the pill's own outline - and a dead
    # pill drops the red elimination warning back to the standard border: that
    # warning is about a threat ABOUT to end the player, and once they are out
    # the slash is the statement.
    edge = ink("border") if dead else (border if border is not None else pal.border)
    _pill_shape(d, x, y, w, PILL_H, edge)
    _pill_shape(d, x + 1, y + 1, w - 2, PILL_H - 2, ink("card"))

    hw = PILL_HEAD_W
    d.set_pen(ink("gold") if ribbon else ink("well"))
    if ribbon:
        # the ribbon takes the bite: ground through the notch column, then a
        # wedge of the pill's own fill cut back out of its right end. The
        # ground is left-capped so the ribbon end stays as round as the far
        # end of the pill - a square left edge here read as a rendering bug.
        _cap_left_fill(d, x + 1, y + 1, hw + PILL_NOTCH - 1, PILL_H - 2,
                       ink("gold"))
        d.set_pen(ink("card"))
        d.triangle(x + hw + PILL_NOTCH, y + 1,
                   x + hw + PILL_NOTCH, y + PILL_H - 1,
                   x + hw, y + PILL_H // 2)
    else:
        # a plain header inverts it: ground stops at the segment edge and the
        # point extends past it
        d.rectangle(x + 1, y + 1, hw - 1, PILL_H - 2)
        d.triangle(x + hw, y + 1, x + hw, y + PILL_H - 1,
                   x + hw + PILL_NOTCH, y + PILL_H // 2)

    _pill_seg(d, pal, segs[0], x + 1, hw, y, ink("bg" if ribbon else "slate"))
    cx = x + hw + PILL_NOTCH
    for i, seg in enumerate(segs[1:]):
        if i > 0:
            d.set_pen(ink("border"))
            d.rectangle(cx, y + 1, 1, PILL_H - 2)
            cx += 1
        _pill_seg(d, pal, seg, cx, PILL_VAL_W, y, ink(seg[2]))
        cx += PILL_VAL_W

    if dead:
        # the one thing NOT shaded - it is the mark that says why
        _pill_slash(d, x + 5, y + 6, w - 10, PILL_H - 12, pal.red)
    return w


def _pill_seg(d, pal, seg, cx, sw, y, pen):
    from ui import icons as _icons
    if seg[0] == "icon":
        mask = seg[1]
        _icons.draw(d, mask, cx + (sw - len(mask)) // 2,
                    y + (PILL_H - len(mask)) // 2, pen)
    else:
        tw = d.measure_text(seg[1], BODY)
        text_left(d, pal, seg[1], cx + (sw - tw) // 2,
                  y + (PILL_H - 8 * BODY) // 2, BODY, pen, shadow=False)


# -- progress rows ---------------------------------------------------------
# Shared by the Progress screen's rows and their detail sheets. These lived as
# private methods on QuestingProgressModal, where the web twin could not reach
# them - which is exactly how the two drew different rows for a month. Anything
# a row needs is here, in both twins, or it is not a row widget.

# The stepper geometry is PlayersDetailModal's, and deliberately so: a 40px
# disc inside a 52px tap target is the size the rest of the app already uses
# for a value the player nudges repeatedly.
STEP_R = 20           # drawn radius
STEP_HIT = 52         # tap target, both axes

# Row heights. The compact one is for a page carrying more than one location.
ROW_H = 76
ROW_H_COMPACT = 54


def prog_row_card(d, pal, x, y, w, h, accent):
    """The row's card: a panel with a 4px accent stripe down its left edge.
    Green for a location, gold for the quest and side quests - the stripe is
    what makes the sections scannable without reading their headers."""
    panel(d, pal, x, y, w, h, fill=pal.card, border=pal.border)
    d.set_pen(accent)
    d.rectangle(x, y, 4, h)


def fill_bar(d, pal, x, y, w, h, prog, pts, accent, at_target):
    """Well plus fill. AMBER at target, not the row's accent: at-target is the
    one state the player has to notice, and it is the same amber the value
    token uses for it."""
    if w <= 0:
        return
    d.set_pen(pal.well)
    d.rectangle(x, y, w, h)
    fw = int(w * min(1.0, (prog / pts) if pts else 0))
    if fw > 0:
        d.set_pen(pal.amber if at_target else accent)
        d.rectangle(x, y, fw, h)


def glyph(d, pal, kind, x, y, pen):
    """Entity mark: "l" a signpost, "q" a quest card, anything else a side
    quest card. 16-18px, drawn rather than an icon mask so it inherits the
    row's accent pen."""
    d.set_pen(pen)
    if kind == "l":
        d.rectangle(x + 7, y + 2, 2, 16)
        d.rectangle(x, y + 4, 11, 6)
        d.triangle(x + 11, y + 4, x + 11, y + 10, x + 16, y + 7)
        d.rectangle(x + 4, y + 17, 8, 2)
    elif kind == "q":
        d.rectangle(x + 1, y + 1, 14, 18)
        d.set_pen(pal.card)
        d.rectangle(x + 3, y + 3, 10, 14)
        d.set_pen(pen)
        for dy in (6, 9):
            d.rectangle(x + 5, y + dy, 6, 1)
        d.rectangle(x + 5, y + 12, 4, 1)
    else:
        d.rectangle(x, y + 3, 18, 14)
        d.set_pen(pal.card)
        d.rectangle(x + 2, y + 5, 14, 10)
        d.set_pen(pen)
        d.rectangle(x + 4, y + 8, 8, 1)
        d.rectangle(x + 4, y + 11, 5, 1)


def stepper_cluster(d, pal, buttons, cx_plus, cy, prog, pts, at_target,
                    id_minus, id_plus, r=STEP_R, hit=STEP_HIT):
    """"progress / target" between one big - and one big +.

    The value carries its own denominator, so the row needs no second editor
    for the target. Both discs go dead at their limit and stop registering a
    button: - at 0, and + at the target, because RR p.22 discards excess on
    advance, so there is nothing past it to record.

    Returns the cluster's left edge, so the caller can size the bar and the
    row's tap band against whatever this took.
    """
    val = "%d / %d" % (prog, pts)
    vw = d.measure_text(val, DISPLAY)
    cx_minus = cx_plus - (vw + 2 * r + 26)
    vx = cx_minus + r + 13
    h = hit // 2
    for cx, mark, on, bid in ((cx_minus, "-", prog > 0, id_minus),
                              (cx_plus, "+", not at_target, id_plus)):
        disc(d, cx, cy, r, pal.btn if on else pal.card_hi)
        arc_runs(d, cx, cy, r, r - 2, 0, 360,
                 pal.bevel_l if on else pal.border)
        text_center(d, pal, mark, cx, cy - 8, DISPLAY,
                    pal.tan if on else pal.dim)
        if on:
            buttons.append(Button(bid, cx - h, cy - h, hit, hit))
    text_left(d, pal, val, vx, cy - 12, DISPLAY,
              pal.amber if at_target else pal.gold)
    return cx_minus - r
