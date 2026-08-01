"""Full-screen pending counter editor with large touch targets.

Backed by the tested CounterState: taps accumulate a pending delta, the value
shown does not commit until the user taps the check. Returns "commit"/"cancel"
to the caller, which reads .state.value.
"""

from ui.counter import CounterState
from ui.widgets import Button, panel, bevel, text_center
from ui import icons

STEPS = [(-5, "-5"), (-1, "-1"), (1, "+1"), (5, "+5")]

# icon name -> (mask attr, palette pen attr, ground pen attr or None)
#
# "threat" and "staging" are the SAME glyph in two different inks, and that is
# the point: red is the player's threat, black is the staging area's. Sharing
# one key made the staging counter wear the player-threat colour, so the only
# editor for that number contradicted every readout of it (the totals row and
# willpower_staging_meter both ink it pal.outline, per design/stat-system.md's
# staging/enemy-threat rule).
#
# Black ink needs a ground. pal.bg is (16, 12, 9) and pal.outline is (0, 0, 0),
# so an unbacked staging icon is a black shape on near-black - the same reason
# the by-round chart stripes its staging row (ui/theme.py: row_stripe).
ICONS = {"threat": ("THREAT", "red", None),
         "staging": ("THREAT", "outline", "row_stripe"),
         "willpower": ("WILLPOWER", "gold", None)}
ICON_PAD = 4


class CounterModal:
    def __init__(self, title, value, on_commit=None, minimum=0, maximum=99,
                 big_color=None, icon=None, subtext=None):
        self.title = title
        self.state = CounterState(value, minimum, maximum)
        self.on_commit = on_commit   # called with the committed value
        self.big_color = big_color
        self.icon = icon             # "threat" | "willpower" | None
        self.subtext = subtext       # small line under the value (e.g. elim level)
        self.buttons = []

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()

        if self.icon in ICONS:
            mask_name, pen_name, ground = ICONS[self.icon]
            mask = getattr(icons, mask_name)
            w = d.measure_text(self.title, 3)
            ix = int(240 - w / 2 - 30)
            if ground:
                s = len(mask) + 2 * ICON_PAD
                d.set_pen(getattr(pal, ground))
                d.rectangle(ix - ICON_PAD, 30 - ICON_PAD, s, s)
            icons.draw(d, mask, ix, 30, getattr(pal, pen_name))
            text_center(d, pal, self.title, 240 + 12, 28, 3, pal.gold)
        else:
            text_center(d, pal, self.title, 240, 28, 3, pal.gold)

        # big value (preview target if pending, else the committed value)
        val = self.state.preview
        color = self.big_color or pal.gold
        text_center(d, pal, str(val), 240, 90, 9, color)

        if self.subtext:
            text_center(d, pal, self.subtext, 240, 168, 2, pal.muted)

        if self.state.pending:
            dlt = self.state.delta
            sign = "+" if dlt >= 0 else ""
            text_center(d, pal, "%d  ->  %d" % (self.state.value, val), 240, 190, 2, pal.muted)
            text_center(d, pal, "%s%d" % (sign, dlt), 240, 216, 3,
                        pal.green if dlt >= 0 else pal.red)

        # step buttons row
        bw, bh, gap = 104, 76, 8
        total = len(STEPS) * bw + (len(STEPS) - 1) * gap
        x0 = (480 - total) // 2
        by = 250
        for i, (step, label) in enumerate(STEPS):
            b = Button(("step", step), x0 + i * (bw + gap), by, bw, bh)
            bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn, t=3)
            text_center(d, pal, label, b.x + b.w / 2, b.y + 26, 3, pal.tan)
            self.buttons.append(b)

        # confirm / cancel
        no = Button(("no",), 24, 360, 200, 92)
        ok = Button(("ok",), 256, 360, 200, 92)
        bevel(d, pal, no.x, no.y, no.w, no.h, pal.btn_no, t=3)
        text_center(d, pal, "X", no.x + no.w / 2, no.y + 28, 4, pal.no_fg)
        bevel(d, pal, ok.x, ok.y, ok.w, ok.h, pal.btn_ok, t=3)
        text_center(d, pal, "OK", ok.x + ok.w / 2, ok.y + 28, 4, pal.ok_fg)
        self.buttons.append(no)
        self.buttons.append(ok)

    def on_button(self, btn):
        """Return 'close' (committed), 'cancel', or None (stay open, redraw)."""
        kind = btn.id[0]
        if kind == "step":
            self.state.tap(btn.id[1])
            return None
        if kind == "ok":
            self.state.confirm()
            if self.on_commit is not None:
                self.on_commit(self.state.value)
            return "close"
        if kind == "no":
            self.state.cancel()
            return "cancel"
        return None
