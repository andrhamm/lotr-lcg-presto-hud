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


def _done_button(d, pal, label="DONE", ready=False):
    """Upper-right commit-and-dismiss bevel button, shared by draw_header's
    close case and modal_header (same geometry, same pens).

    Widens for a longer label the same way draw_header's round stamp does -
    "RESOLVE" does not fit DONE's 64px. Returns (x, y, w, h) so the caller
    registers a hit-box that matches what was drawn; a fixed 64 would have left
    the wider button's left third dead.

    `ready` swaps the ink to amber: the Progress screen relabels this RESOLVE
    when something is sitting at its target, and the colour is the same
    at-target signal its value tokens already use.
    """
    w = max(64, d.measure_text(label, BODY) + 20)
    x = 472 - w
    bevel(d, pal, x, 4, w, 32, pal.btn_ok)
    text_center(d, pal, label, x + w // 2, 12, BODY,
                pal.amber if ready else pal.ok_fg)
    return x, 4, w, 32


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


def modal_header(d, pal, game, title, buttons, cta="DONE", cta_ready=False,
                 back=None):
    """Shared header for full-screen modals: round id upper-left, centred
    title, and a DONE button upper-right that pushes id ("close",) (each
    modal's on_button maps "close" to its own commit-and-dismiss / dismiss
    semantics).

    back: (label, button_id) puts a way back in the round-stamp slot instead
    of the stamp. A sub-view that drew its own back button somewhere else
    landed on its own content (the History chart is bottom-anchored), and
    drawing one OVER the stamp printed the two on top of each other. Same
    affordance draw_header's round_id gives the pre-game screens, and for the
    same reason: the slot and its tap target are one thing."""
    if back:
        label, bid = back
        text_left(d, pal, label, 10, 12, BODY, pal.tan)
        buttons.append(Button(bid, 0, 0, 150, HEADER_H))
    else:
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
    # cta=None suppresses the DONE button entirely. A sheet with nothing to
    # commit and a "< Progress" already in the left slot had two controls
    # doing one job, and both pushed the same ("close",) id.
    if cta is not None:
        x, y, w, h = _done_button(d, pal, cta, cta_ready)
        buttons.append(Button(("close",), x, y, w, h))
