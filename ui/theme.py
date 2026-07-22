"""Palette derived from the Revised Core box art (bark, moss, parchment,
ember) + bevel pens for the video-game chrome. Pens are created lazily from a
PicoGraphics display."""


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
        self.muted = d.create_pen(146, 132, 96)
        self.dim = d.create_pen(100, 90, 62)
        # semantics
        self.green = d.create_pen(136, 168, 92)
        self.amber = d.create_pen(214, 164, 70)
        self.red = d.create_pen(206, 84, 52)
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
        # leadership purple (action-window notifications)
        self.purple = d.create_pen(166, 122, 196)
        # true black-ish ink (staging threat value/icon, shadows)
        self.outline = d.create_pen(0, 0, 0)
        # inset value well
        self.well = d.create_pen(24, 20, 12)

    def threat_pen(self, threat):
        if threat >= 35:
            return self.red
        if threat >= 20:
            return self.amber
        return self.green
