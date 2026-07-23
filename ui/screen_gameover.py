"""Game-over screen: victory or defeat, final stats, finish (clear save) or
back to the table. Mirror of the web GameOverScreen (docs/js/screens_other.js).
"""

from ui.widgets import Button, bevel, text_center, text_left


class GameOverScreen:
    def __init__(self):
        self.buttons = []

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        go = game.game_over or {}
        win = go.get("result") == "victory"
        text_center(d, pal, "VICTORY!" if win else "DEFEAT", 240, 64, 5,
                    pal.gold if win else pal.red)
        text_center(d, pal, "The final quest stage is complete." if win
                    else "All players have been eliminated.", 240, 132, 2, pal.tan)
        y = [190]

        def line(label, val):
            text_left(d, pal, label, 120, y[0], 2, pal.muted)
            text_left(d, pal, str(val), 300, y[0], 2, pal.gold)
            y[0] += 30

        line("Rounds", go.get("round", game.round))
        if go.get("duration"):
            line("Duration", go["duration"])
        for i, p in enumerate(game.players):
            line("P%d threat" % (i + 1),
                 ("%d (out)" % p.threat) if p.eliminated else p.threat)

        fin = Button(("finish",), 100, 396, 280, 58)
        bevel(d, pal, fin.x, fin.y, fin.w, fin.h, pal.btn_ok, t=3)
        text_center(d, pal, "Finish - clear save", 240, 414, 2, pal.ok_fg)
        self.buttons.append(fin)
        back = Button(("back",), 150, 358, 180, 34)
        bevel(d, pal, back.x, back.y, back.w, back.h, pal.card, t=2)
        text_center(d, pal, "back to game", 240, back.y + 9, 2, pal.tan)
        self.buttons.append(back)

    def on_button(self, btn, game):
        k = btn.id[0]
        if k == "finish":
            return ("end_game",)
        if k == "back":
            game.game_over = None
            game.log_event("Game over dismissed - back to the table")
            return ("goto", "play")
        return None
