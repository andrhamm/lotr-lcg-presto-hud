"""Type-scale gate: prose must never render at LABEL size.

The device font is a bitmap8, so there are exactly three sizes (ui/theme.py:
DISPLAY 3, BODY 2, LABEL 1). Nothing in the codebase stopped a draw site from
passing a bare `1`, and the pattern that kept emerging was: lay something out,
run out of room, drop the text to LABEL to make it fit. That shipped
unreadable prose more than once - most recently the Quest Cards detail view,
whose entire purpose is to give text room, rendering at LABEL so it would fit
on one page.

The rule this enforces: **if a player reads it as a sentence or a name, it is
BODY.** Running out of room is not a reason to shrink it - page it, truncate
it with a "more" affordance, or say less.

LABEL survives for two things, both of which are read as *chrome* rather than
as content:

  1. ALL-CAPS section labels ("SETS TO GATHER", "SIDE A", "TIPS").
  2. Dense tabular metadata where the row count is the point - the log's
     timestamped feed, list-row counts, dates.

Both are allow-listed explicitly below. An entry needs a reason, and adding
one should feel like a decision, not a shortcut.
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.scenes import SCENES
from ui.theme import DISPLAY, BODY, LABEL

# Scenes that ARE a dense tabular readout: the log's whole job is to fit many
# timestamped rows on one screen with its own pager. Prose does not live here.
DENSE_SCENES = {"log", "log_page2", "log_empty"}

# Metadata shapes that stay LABEL wherever they appear: they are scanned, not
# read, and they sit in the margins of a row rather than carrying meaning on
# their own.
METADATA = (
    re.compile(r"^R\d+[ .]"),                 # round/step stamps: "R1 0.0"
    re.compile(r"^\d+/\d+$"),                 # pagers: "2/3"
    re.compile(r"^\d{4}-\d{2}$"),             # release dates: "2011-04"
    re.compile(r"^\d+ (quest|quests|card|cards|note|notes)$"),
    re.compile(r"^Source: "),                 # tip attribution
    re.compile(r"^https?://"),                # attribution URL
    re.compile(r"^\+\d+ more$"),              # overflow row
)

# Deliberate exceptions, each with the reason it is not a bug.
ALLOWED_EXACT = {
    # The user specified this subtitle as small when they designed the
    # scenario chooser header ("Choose Scenario / <small>Cycle: X</small>").
    "Cycle: Shadows of Mirkwood": "user-specified small subtitle",
}


def _is_label(s):
    """ALL-CAPS chrome: no lowercase letters anywhere."""
    return not any(c.islower() for c in s)


def _exempt(scene, s):
    s = s.strip()
    if not s or _is_label(s):
        return True
    if scene in DENSE_SCENES:
        return True
    if s in ALLOWED_EXACT:
        return True
    return any(p.match(s) for p in METADATA)


@pytest.mark.parametrize("scene", sorted(SCENES))
def test_prose_is_never_drawn_at_label_size(scene):
    hw, _ = SCENES[scene]()
    offenders = sorted({c[1] for c in hw.display.calls
                        if c[0] == "text" and c[4] == LABEL and not _exempt(scene, c[1])})
    assert not offenders, (
        "%s draws prose at LABEL size - use BODY (see ui/theme.py):\n  %s"
        % (scene, "\n  ".join(repr(o) for o in offenders)))


@pytest.mark.parametrize("scene", sorted(SCENES))
def test_above_display_is_numerals_and_wordmarks_only(scene):
    """There is no reading tier above DISPLAY - the big sizes belong to stat
    numerals and wordmarks ("19", "LOTR LCG", "VICTORY!"). A sentence drawn
    that large is a layout accident, not a heading."""
    hw, _ = SCENES[scene]()
    offenders = sorted({c[1] for c in hw.display.calls
                        if c[0] == "text" and c[4] > DISPLAY
                        and not (len(c[1].strip()) <= 12 and _is_label(c[1]))})
    assert not offenders, (
        "%s draws prose above DISPLAY size: %s" % (scene, offenders))


def test_the_scale_is_ordered_and_named():
    assert LABEL < BODY < DISPLAY, "the type scale inverted"
