"""Log screen — newest-first timeline, paged. Reached by tapping Round in the
header. Entries are tagged R<round>.<step>.
"""

from ui.header import draw_header, HEADER_H
from ui.theme import DISPLAY, BODY, LABEL
from ui.widgets import Button, panel, bevel, text_center, text_left, truncate_text

PER_PAGE = 11
ROW_H = 26
REPLAY_Y = 348
REPLAY_H = 46
REPLAY_BTN_W = 56


class ScreenLog:
    def __init__(self):
        self.buttons = []
        self.page = 0  # 0 = newest

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        draw_header(d, pal, game, self.buttons, title="Game Log", close=True)

        entries = list(reversed(game.log))
        pages = max(1, (len(entries) + PER_PAGE - 1) // PER_PAGE)
        self.page = min(self.page, pages - 1)
        chunk = entries[self.page * PER_PAGE:(self.page + 1) * PER_PAGE]

        y = HEADER_H + 10
        if not chunk:
            text_center(d, pal, "no activity yet", 240, 200, BODY, pal.dim)
        # The feed stays LABEL by design: it is dense tabular metadata with
        # its own pager, and the row count is the point (see the design-system
        # spec and tests/test_typography.py's DENSE_SCENES).
        for e in chunk:
            tag = "R%d.%s" % (e["round"], e["step"])
            text_left(d, pal, tag, 12, y, LABEL, pal.dim)
            t = e.get("t")
            if t is not None:
                s = t // 1000
                text_left(d, pal, "%d:%02d" % (s // 60, s % 60), 76, y, LABEL, pal.dim)
            body = truncate_text(e["text"], LABEL, 480 - 122 - 12, d.measure_text)
            text_left(d, pal, body, 122, y, LABEL, pal.tan)
            di = e.get("delta_i")
            if di is not None and 0 <= di < len(getattr(game, "deltas", [])):
                self.buttons.append(Button(("replay_jump", di), 12, y,
                                           480 - 24, ROW_H))
            y += ROW_H

        self._replay_transport(d, pal, game)

        # pager
        if pages > 1:
            up = Button(("older",), 12, 420, 150, 46)
            dn = Button(("newer",), 318, 420, 150, 46)
            bevel(d, pal, up.x, up.y, up.w, up.h, pal.btn)
            text_center(d, pal, "Older", up.x + 75, up.y + 14, BODY, pal.tan)
            bevel(d, pal, dn.x, dn.y, dn.w, dn.h, pal.btn)
            text_center(d, pal, "Newer", dn.x + 75, dn.y + 14, BODY, pal.tan)
            text_center(d, pal, "%d/%d" % (self.page + 1, pages), 240, 434, BODY, pal.muted)
            self.buttons.append(up)
            self.buttons.append(dn)

    def _replay_transport(self, d, pal, game):
        """Cursor transport. Parity: frontend/src/features/messages/
        LogButtons.js - the same five controls and the same n/total readout,
        plus the round-granularity step the reference binds to Shift+Arrow
        (useDragnHotkeys.js) and never gives a button, because the Presto has
        no keyboard.

        Always drawn, even with no history, so the row does not appear and
        disappear under the log and shift the pager. "Step" prefixes the
        readout so it cannot be misread as the pager's own "%d/%d" below it.
        """
        back_on, fwd_on = game.can_undo(), game.can_redo()
        specs = (
            (("replay", "first"),      "|<", 12,  back_on),
            (("replay", "round_back"), "<<", 74,  back_on),
            (("replay", "undo"),       "<",  136, back_on),
            (("replay", "redo"),       ">",  350, fwd_on),
            (("replay", "last"),       ">|", 412, fwd_on),
        )
        for bid, label, x, on in specs:
            b = Button(bid, x, REPLAY_Y, REPLAY_BTN_W, REPLAY_H)
            bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn if on else pal.card)
            text_center(d, pal, label, b.x + REPLAY_BTN_W // 2, REPLAY_Y + 14,
                        BODY, pal.tan if on else pal.dim)
            self.buttons.append(b)
        text_center(d, pal,
                    "Step %d/%d" % (game.replay_step + 1, len(game.deltas)),
                    271, REPLAY_Y + 14, BODY, pal.muted)

    def on_button(self, btn, game):
        k = btn.id[0]
        if k == "nav":
            return ("goto", btn.id[1])
        if k == "older":
            self.page += 1
            return True
        # `or None` turns the dispatcher's False into this file's existing
        # "nothing happened, do not save" convention.
        if k == "replay":
            which = btn.id[1]
            if which == "first":
                return game.step_through({"size": "index", "index": -1}) or None
            if which == "last":
                return game.step_through(
                    {"size": "index", "index": len(game.deltas) - 1}) or None
            if which == "round_back":
                return game.step_through(
                    {"size": "round", "direction": "undo"}) or None
            return game.step_through(
                {"size": "single", "direction": which}) or None
        if k == "replay_jump":
            return game.step_through({"size": "index", "index": btn.id[1]}) or None
        if k == "newer":
            self.page = max(0, self.page - 1)
            return True
        return None
