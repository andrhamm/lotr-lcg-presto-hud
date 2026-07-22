"""Shared top header: Round (tap -> Log) | Current phase (tap -> Phases) |
Settings (tap -> Settings). Nav buttons get ids ("nav", target).
"""

import phases
from ui.widgets import Button, text_center, text_left

HEADER_H = 40

from gamestate import VIEW_LABELS as VIEW_LABEL


def draw_header(d, pal, game, buttons, highlight=None, title=None,
                close=False, close_left=False):
    """Standard header. Default: R# (tap -> log) | view label (tap -> phases)
    | Set. (tap -> settings).
    title: static center text instead of the view label.
    close: X on the right closes the screen (Settings).
    close_left: the R# label is highlighted and tapping it again closes
    (Game Log — toggle behavior)."""
    # DragnCards-style step decimal beside the round (e.g. R2 3.4, R1 6.E)
    round_lbl = "R%d %s" % (game.round, game.step)
    text_left(d, pal, round_lbl, 10, 12, 2,
              pal.gold if (close_left or highlight == "log") else pal.muted)

    center = title if title is not None else VIEW_LABEL.get(
        getattr(game, "view", None), phases.step(game.step)["phase"])
    scale = 2 if len(center) > 12 else 3
    text_center(d, pal, center, 240, 12 if scale == 2 else 8, scale, pal.gold)

    if close:
        w = d.measure_text("X", 3)
        text_left(d, pal, "X", 480 - 16 - w, 8, 3, pal.no_fg)
    else:
        gear = "Set."
        w = d.measure_text(gear, 2)
        text_left(d, pal, gear, 480 - 10 - w, 12, 2,
                  pal.gold if highlight == "settings" else pal.muted)
    d.set_pen(pal.border)
    d.rectangle(0, HEADER_H, 480, 1)

    if close:
        # Settings: X is the only nav
        buttons.append(Button(("nav", "close"), 330, 0, 150, HEADER_H))
    elif close_left:
        # Game Log: R# toggles closed; Set. still reachable
        buttons.append(Button(("nav", "close"), 0, 0, 150, HEADER_H))
        buttons.append(Button(("nav", "settings"), 330, 0, 150, HEADER_H))
    else:
        buttons.append(Button(("nav", "log"), 0, 0, 150, HEADER_H))
        buttons.append(Button(("nav", "phases"), 150, 0, 180, HEADER_H))
        buttons.append(Button(("nav", "settings"), 330, 0, 150, HEADER_H))
