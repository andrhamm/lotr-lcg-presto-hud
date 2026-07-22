"""Drawing helpers + a Button hit-region. Take a PicoGraphics-like display.

NOWRAP: PicoGraphics text() word-wraps at its wordwrap argument — passing 0
stacks every word vertically. All text here is pre-wrapped by wrap_text, so
every draw passes NOWRAP (a width no string can reach) to disable it.
"""

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


def text_left(d, pal, s, x, y, scale, pen, shadow=True):
    if shadow:
        off = 1 if scale == 1 else 2
        d.set_pen(pal.bevel_d)
        d.text(s, x + off, y + off, NOWRAP, scale)
    d.set_pen(pen)
    d.text(s, x, y, NOWRAP, scale)


def text_center(d, pal, s, cx, y, scale, pen, shadow=True):
    w = d.measure_text(s, scale)
    x = int(cx - w / 2)
    if shadow:
        off = 1 if scale == 1 else 2
        d.set_pen(pal.bevel_d)
        d.text(s, x + off, y + off, NOWRAP, scale)
    d.set_pen(pen)
    d.text(s, x, y, NOWRAP, scale)


def button(d, pal, btn, label, scale=2, fill=None, fg=None, pressed=False):
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
    button(d, pal, minus, "-", 3)
    button(d, pal, plus, "+", 3)
    text_center(d, pal, value_str, x + w / 2, int(y + (h - 24) / 2), 3, pal.gold)
    buttons.append(minus)
    buttons.append(plus)


def row_label(d, pal, s, x, y, scale=2, pen=None):
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


def note_panel(d, pal, x, y, w, text, scale=2, reserve_right=0, icon=None):
    """Distinct style for phase reminder messages: dark panel, gold edge,
    muted text, and (by default) the hobbit-pipe hint medallion on the left.
    Accepts a string or list of paragraphs; each is word-wrapped to the usable
    width (minus icon gutter and reserve_right). Returns the panel height."""
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
    lh = 10 * scale + 6
    h = max(len(lines) * lh + 16, isz + 14 if gutter else 0)
    d.set_pen(pal.card_hi)
    d.rectangle(x, y, w, h)
    d.set_pen(pal.border_gold)
    d.rectangle(x, y, 4, h)
    if gutter:
        _icons.draw(d, icon, x + 10, y + (h - isz) // 2, pal.gold)
    ty = y + 8
    for s in lines:
        text_left(d, pal, s, x + 12 + gutter, ty, scale, pal.muted)
        ty += lh
    return h
