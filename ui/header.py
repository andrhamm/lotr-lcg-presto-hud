"""Shared top header: Round (tap -> Log) | Current phase (tap -> Phases) |
Settings (tap -> Settings). Nav buttons get ids ("nav", target).

**Every title bar is DISPLAY, and no title bar is ALL CAPS.** The header used
to pick its scale from the title's character count (`BODY if len > 12`), so
the same element changed tier as a round advanced - Planning and Travel at
DISPLAY, Questing: Staging and Combat: Shadow Cards at BODY. Measurement
killed the rule rather than argument: the narrowest span a title has (a
two-digit round stamp beside "Set.") is 360px, and every title fits inside it
at DISPLAY. Only `ACTION WINDOW - ENCOUNTER` did not, by 6px, and its
separator was off-convention anyway.

ALL CAPS went with it. The design system spends casing on demoting `LABEL`
chrome ("the casing carries the demotion"), so a title bar wearing it says
the opposite of what a title bar is for - and the new-game funnel flipped
convention twice in four screens.
"""

import phases
from ui.theme import DISPLAY, BODY, LABEL
from ui.widgets import Button, bevel, text_center, text_left

HEADER_H = 40
# A subtitle rides under the title, so the bar grows: DISPLAY title at y=8
# (24px tall), LABEL subtitle at y=36, rule at 52, 8px of air top and bottom.
SUBTITLE_HEADER_H = 52

from gamestate import VIEW_LABELS as VIEW_LABEL


def _done_button(d, pal):
    """Upper-right DONE bevel button: the universal "commit and dismiss"
    affordance shared by draw_header's close case and modal_header (same
    geometry, same pens)."""
    bevel(d, pal, 408, 4, 64, 32, pal.btn_ok)
    text_center(d, pal, "DONE", 440, 12, BODY, pal.ok_fg)


def draw_header(d, pal, game, buttons, highlight=None, title=None,
                close=False, close_left=False, round_label=None,
                title_pen=None, round_id=None, subtitle=None):
    """Standard header. Default: R# (tap -> log) | view label (tap -> phases)
    | Set. (tap -> settings).
    title: static center text instead of the view label.
    subtitle: a LABEL line under the title, which grows the bar to
    SUBTITLE_HEADER_H. Only the scenario chooser uses it ("Cycle: X"), and it
    stays LABEL because the user specified that subtitle small when they
    designed that screen (allow-listed in tests/test_typography.py).
    title_pen: override the title colour (the action-window screen uses
    pal.purple, the established accent for action windows).
    close: DONE on the right closes the screen (Settings).
    close_left: the R# label is highlighted and tapping it again closes
    (Game Log — toggle behavior).
    round_id: retarget the round-stamp slot's tap. The label and its tap
    target are one affordance, so a screen that puts "< Menu" there must be
    able to say where it goes. Appending a second button over the slot does
    not work: the dispatcher takes the first hit (main.py:437) and the
    header's own button is already in the list, which is exactly how the
    pre-game back buttons ended up opening the Game Log."""
    # DragnCards-style step decimal beside the round (e.g. R2 3.4, R1 6.E)
    # round_label overrides it entirely (pre-game setup screens show "R0").
    round_lbl = round_label if round_label else "R%d %s" % (game.round, game.step)
    text_left(d, pal, round_lbl, 10, 12, BODY,
              pal.gold if (close_left or highlight == "log") else pal.muted)

    center = title if title is not None else VIEW_LABEL.get(
        getattr(game, "view", None), phases.step(game.step)["phase"])
    text_center(d, pal, center, 240, 8, DISPLAY,
                title_pen if title_pen is not None else pal.gold)

    h = SUBTITLE_HEADER_H if subtitle else HEADER_H
    if subtitle:
        text_center(d, pal, subtitle, 240, 36, LABEL, pal.dim)

    if close:
        _done_button(d, pal)
    else:
        gear = "Set."
        w = d.measure_text(gear, BODY)
        text_left(d, pal, gear, 480 - 10 - w, 12, BODY,
                  pal.gold if highlight == "settings" else pal.muted)
    d.set_pen(pal.border)
    d.rectangle(0, h, 480, 1)

    if close:
        # Settings: DONE is the only nav
        buttons.append(Button(("nav", "close"), 408, 4, 64, 32))
    elif close_left:
        # Game Log: R# toggles closed; Set. still reachable
        buttons.append(Button(("nav", "close"), 0, 0, 150, h))
        buttons.append(Button(("nav", "settings"), 330, 0, 150, h))
    else:
        buttons.append(Button(round_id or ("nav", "log"), 0, 0, 150, h))
        buttons.append(Button(("nav", "phases"), 150, 0, 180, h))
        buttons.append(Button(("nav", "settings"), 330, 0, 150, h))


def modal_header(d, pal, game, title, buttons):
    """Shared header for full-screen modals: round id upper-left, centred
    title, and a DONE button upper-right that pushes id ("close",) (each
    modal's on_button maps "close" to its own commit-and-dismiss / dismiss
    semantics)."""
    round_lbl = "R%d %s" % (game.round, game.step)
    text_left(d, pal, round_lbl, 10, 12, BODY, pal.muted)
    # DISPLAY, like every screen title. This was BODY, so opening a modal from
    # Settings stepped its title DOWN a tier - the spec's "screen and modal
    # titles" is one row of the table, not two. The span here is narrower (the
    # DONE button starts at x=408, not "Set." at 436), so it was measured too:
    # the widest modal title is "Encounter Reminders" at 279 of 332px.
    text_center(d, pal, title, 240, 8, DISPLAY, pal.gold)
    d.set_pen(pal.border)
    d.rectangle(0, HEADER_H, 480, 1)
    _done_button(d, pal)
    buttons.append(Button(("close",), 408, 4, 64, 32))
