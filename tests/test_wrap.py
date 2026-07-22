import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_hardware import FakeDisplay
from ui.widgets import wrap_text


def _measure(s, scale):
    return len(s) * 6 * scale


def test_short_text_stays_one_line():
    assert wrap_text("hello", 2, 200, _measure) == ["hello"]


def test_wraps_at_word_boundaries():
    lines = wrap_text("alpha beta gamma delta", 2, 130, _measure)
    assert all(_measure(l, 2) <= 130 for l in lines)
    assert " ".join(lines) == "alpha beta gamma delta"


def test_long_word_is_hard_broken():
    lines = wrap_text("abcdefghijklmnopqrstuvwxyz", 2, 120, _measure)
    assert all(_measure(l, 2) <= 120 for l in lines)
    assert "".join(lines) == "abcdefghijklmnopqrstuvwxyz"


def test_empty_string_gives_one_empty_line():
    assert wrap_text("", 2, 100, _measure) == [""]


def test_truncate_with_ellipsis():
    from ui.widgets import truncate_text
    s = truncate_text("a very long line of text that will not fit", 1, 60, _measure)
    assert _measure(s, 1) <= 60
    assert s.endswith("..")
