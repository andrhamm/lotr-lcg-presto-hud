"""Log screen — newest-first timeline, paged. Reached by tapping Round in the
header. Entries are tagged R<round>.<step>.
"""

from ui.header import draw_header, HEADER_H
from ui.widgets import Button, panel, bevel, text_center, text_left, truncate_text

PER_PAGE = 13
ROW_H = 26


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
            text_center(d, pal, "no activity yet", 240, 200, 2, pal.dim)
        for e in chunk:
            tag = "R%d.%s" % (e["round"], e["step"])
            text_left(d, pal, tag, 12, y, 1, pal.dim)
            t = e.get("t")
            if t is not None:
                s = t // 1000
                text_left(d, pal, "%d:%02d" % (s // 60, s % 60), 76, y, 1, pal.dim)
            body = truncate_text(e["text"], 1, 480 - 122 - 12, d.measure_text)
            text_left(d, pal, body, 122, y, 1, pal.tan)
            y += ROW_H

        # pager
        if pages > 1:
            up = Button(("older",), 12, 420, 150, 46)
            dn = Button(("newer",), 318, 420, 150, 46)
            bevel(d, pal, up.x, up.y, up.w, up.h, pal.btn)
            text_center(d, pal, "Older", up.x + 75, up.y + 14, 2, pal.tan)
            bevel(d, pal, dn.x, dn.y, dn.w, dn.h, pal.btn)
            text_center(d, pal, "Newer", dn.x + 75, dn.y + 14, 2, pal.tan)
            text_center(d, pal, "%d/%d" % (self.page + 1, pages), 240, 434, 2, pal.muted)
            self.buttons.append(up)
            self.buttons.append(dn)

    def on_button(self, btn, game):
        k = btn.id[0]
        if k == "nav":
            return ("goto", btn.id[1])
        if k == "older":
            self.page += 1
            return True
        if k == "newer":
            self.page = max(0, self.page - 1)
            return True
        return None
