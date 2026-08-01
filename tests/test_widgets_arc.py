"""arc_runs must paint exactly the pixels the original per-pixel version did.

The original walked every pixel of the bounding box calling math.sqrt AND
math.atan2 on each one - ~4,100 trig calls for a single r=22 token, 119 ms, and
PlayersDetailModal draws four of them, so a tap inside it cost 963 ms.

The rewrite computes integer scanline spans for a full ring and only scans the
annulus for a partial arc. That is a drawing optimisation, which means the ONLY
thing that makes it safe is proving it is pixel-identical - a ring that is one
pixel thinner on some rows is exactly the kind of regression nobody notices in
a test but everybody notices on the device.

The reference implementation below is the original code, kept verbatim.
"""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui import widgets  # noqa: E402


class Recorder:
    """Collects the pixels a draw would set, ignoring pen colour."""

    def __init__(self):
        self.px = set()

    def set_pen(self, pen):
        pass

    def rectangle(self, x, y, w, h):
        for i in range(w):
            for j in range(h):
                self.px.add((x + i, y + j))


def reference_arc_runs(d, cx, cy, R, r, a0, a1, pen):
    """The original implementation, unchanged."""
    d.set_pen(pen)
    for py in range(int(cy - R), int(cy + R) + 1):
        run = False
        x0 = 0
        for px in range(int(cx - R), int(cx + R) + 2):
            dx, dy = px - cx, py - cy
            dd = math.sqrt(dx * dx + dy * dy)
            on = r <= dd <= R
            if on and a1 is not None:
                ang = math.degrees(math.atan2(dx, -dy)) % 360.0
                on = a0 <= ang <= a1
            if on and not run:
                run, x0 = True, px
            elif not on and run:
                d.rectangle(x0, py, px - x0, 1)
                run = False


# (R, r) pairs actually used: token 22/19, circ_btn 20/18 and 11/9, plus
# wider/narrower bands to catch span arithmetic that only works at one width.
RADII = [(22, 19), (20, 18), (12, 9), (11, 9), (30, 24), (8, 6)]
# 0.0 and 1.0 are the degenerate ends; the rest include both sides of 180deg,
# which is where the wedge stops being convex.
FRACTIONS = [0.0, 0.01, 0.05, 0.17, 0.25, 0.33, 0.4, 0.5,
             0.6, 0.75, 0.9, 0.99, 1.0]


def _both(R, r, a0, a1):
    ref, got = Recorder(), Recorder()
    reference_arc_runs(ref, 100, 100, R, r, a0, a1, 1)
    widgets.arc_runs(got, 100, 100, R, r, a0, a1, 1)
    return ref.px, got.px


@pytest.mark.parametrize("R,r", RADII)
@pytest.mark.parametrize("frac", FRACTIONS)
def test_partial_arc_is_pixel_identical(R, r, frac):
    ref, got = _both(R, r, 0, frac * 360.0)
    assert got == ref, (
        "R=%d r=%d frac=%.2f: %d missing, %d extra"
        % (R, r, frac, len(ref - got), len(got - ref)))


@pytest.mark.parametrize("R,r", RADII)
def test_full_ring_is_pixel_identical(R, r):
    """The analytic span path - the one that skips the angle test entirely."""
    ref, got = _both(R, r, 0, 360)
    assert got == ref, "R=%d r=%d: %d missing, %d extra" % (
        R, r, len(ref - got), len(got - ref))


@pytest.mark.parametrize("R,r", RADII)
def test_a_none_angle_means_the_whole_ring(R, r):
    ref, got = _both(R, r, 0, None)
    assert got == ref


def test_a_ring_actually_has_a_hole():
    """Guards the inner-radius arithmetic: an off-by-one that filled the
    middle would still be 'identical' if the reference were also wrong."""
    _, got = _both(22, 19, 0, 360)
    assert (100, 100) not in got, "the ring's centre must be empty"
    assert (100, 100 - 20) in got, "the band itself must be painted"


def test_a_zero_fraction_paints_almost_nothing():
    """frac=0 is the empty progress ring - it must not paint a half circle."""
    _, got = _both(22, 19, 0, 0.0)
    assert len(got) < 8, "frac=0 painted %d pixels" % len(got)
