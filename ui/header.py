"""Shared top header: Round (tap -> Log) | Current phase (tap -> Phases) |
Settings (tap -> Settings). Nav buttons get ids ("nav", target).
"""

import phases
from ui.widgets import Button, bevel, text_center, text_left

HEADER_H = 40

from gamestate import VIEW_LABELS as VIEW_LABEL


def _done_button(d, pal):
    """Upper-right DONE bevel button: the universal "commit and dismiss"
    affordance shared by draw_header's close case and modal_header (same
    geometry, same pens)."""
    bevel(d, pal, 408, 4, 64, 32, pal.btn_ok)
    text_center(d, pal, "DONE", 440, 12, 2, pal.ok_fg)


def draw_header(d, pal, game, buttons, highlight=None, title=None,
                close=False, close_left=False, round_label=None):
    """Standard header. Default: R# (tap -> log) | view label (tap -> phases)
    | Set. (tap -> settings).
    title: static center text instead of the view label.
    close: DONE on the right closes the screen (Settings).
    close_left: the R# label is highlighted and tapping it again closes
    (Game Log — toggle behavior)."""
    # DragnCards-style step decimal beside the round (e.g. R2 3.4, R1 6.E)
    # round_label overrides it entirely (pre-game setup screens show "R0").
    round_lbl = round_label if round_label else "R%d %s" % (game.round, game.step)
    text_left(d, pal, round_lbl, 10, 12, 2,
              pal.gold if (close_left or highlight == "log") else pal.muted)

    center = title if title is not None else VIEW_LABEL.get(
        getattr(game, "view", None), phases.step(game.step)["phase"])
    scale = 2 if len(center) > 12 else 3
    text_center(d, pal, center, 240, 12 if scale == 2 else 8, scale, pal.gold)

    if close:
        _done_button(d, pal)
    else:
        gear = "Set."
        w = d.measure_text(gear, 2)
        text_left(d, pal, gear, 480 - 10 - w, 12, 2,
                  pal.gold if highlight == "settings" else pal.muted)
    d.set_pen(pal.border)
    d.rectangle(0, HEADER_H, 480, 1)

    if close:
        # Settings: DONE is the only nav
        buttons.append(Button(("nav", "close"), 408, 4, 64, 32))
    elif close_left:
        # Game Log: R# toggles closed; Set. still reachable
        buttons.append(Button(("nav", "close"), 0, 0, 150, HEADER_H))
        buttons.append(Button(("nav", "settings"), 330, 0, 150, HEADER_H))
    else:
        buttons.append(Button(("nav", "log"), 0, 0, 150, HEADER_H))
        buttons.append(Button(("nav", "phases"), 150, 0, 180, HEADER_H))
        buttons.append(Button(("nav", "settings"), 330, 0, 150, HEADER_H))


def modal_header(d, pal, game, title, buttons):
    """Shared header for full-screen modals: round id upper-left, centred
    title, and a DONE button upper-right that pushes id ("close",) (each
    modal's on_button maps "close" to its own commit-and-dismiss / dismiss
    semantics)."""
    round_lbl = "R%d %s" % (game.round, game.step)
    text_left(d, pal, round_lbl, 10, 12, 2, pal.muted)
    text_center(d, pal, title, 240, 12, 2, pal.gold)
    d.set_pen(pal.border)
    d.rectangle(0, HEADER_H, 480, 1)
    _done_button(d, pal)
    buttons.append(Button(("close",), 408, 4, 64, 32))
