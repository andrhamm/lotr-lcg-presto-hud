"""Settings screen — game actions + an app-icon grid for Network/Tunes
(M2/M3; dimmed until they land). Header: static title + X to close."""

from ui.header import draw_header, HEADER_H
from ui.widgets import Button, panel, bevel, text_center, text_left
from ui import icons

TILE = 100
TILE_GAP = 16


class ScreenSettings:
    def __init__(self, prefs=None):
        self.prefs = prefs if prefs is not None else {"brightness": 100, "scene": "phase"}
        self.buttons = []
        self.confirm_end = False

    def _app_tile(self, d, pal, x, y, icon, label, enabled=False):
        bevel(d, pal, x, y, TILE, TILE, pal.card)
        pen = pal.gold if enabled else pal.dim
        icons.draw(d, icon, x + (TILE - 40) // 2, y + 14, pen, scale=2)
        text_center(d, pal, label, x + TILE / 2, y + TILE - 22, 1,
                    pal.tan if enabled else pal.dim)

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        draw_header(d, pal, game, self.buttons, title="Settings", close=True)

        y = HEADER_H + 16
        text_left(d, pal, "GAME", 16, y, 1, pal.dim)
        y += 18
        sq = Button(("save_quit",), 16, y, 452, 56)
        bevel(d, pal, sq.x, sq.y, sq.w, sq.h, pal.btn, t=3)
        text_center(d, pal, "Save & Quit", 240, y + 18, 2, pal.tan)
        self.buttons.append(sq)
        y += 66
        if self.confirm_end:
            b = Button(("end_game2",), 16, y, 452, 56)
            bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn_no, t=3)
            text_center(d, pal, "Really end? Save will be deleted", 240, y + 18, 2, pal.no_fg)
        else:
            b = Button(("end_game",), 16, y, 452, 56)
            bevel(d, pal, b.x, b.y, b.w, b.h, pal.card, t=3)
            text_center(d, pal, "End Game", 240, y + 18, 2, pal.no_fg)
        self.buttons.append(b)

        y += 76
        text_left(d, pal, "DEVICE", 16, y, 1, pal.dim)
        y += 18
        self._app_tile(d, pal, 16, y, icons.LED, "LEDs", enabled=True)
        self.buttons.append(Button(("led",), 16, y, TILE, TILE))

        y += TILE + 24
        text_left(d, pal, "APPS  (coming soon)", 16, y, 1, pal.dim)
        y += 18
        x = 16
        for icon, label in ((icons.WIFI, "Network"), (icons.MUSIC, "Tunes")):
            self._app_tile(d, pal, x, y, icon, label, enabled=False)
            x += TILE + TILE_GAP

    def on_button(self, btn, game):
        k = btn.id[0]
        if k == "nav":
            self.confirm_end = False
            return ("goto", btn.id[1])
        if k == "led":
            from ui.modals import LedModal
            return ("modal", LedModal(self.prefs, game))
        if k == "save_quit":
            self.confirm_end = False
            return ("save_quit",)
        if k == "end_game":
            self.confirm_end = True
            return True
        if k == "end_game2":
            self.confirm_end = False
            return ("end_game",)
        return None
