import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.screen_play import ScreenPlay
from ui.modals import LocationPickModal
from gamestate import GameState


def _setup(view="resource"):
    hw = FakeHardware()
    pal = Palette(hw.display)
    game = GameState()
    game.view = view
    screen = ScreenPlay()
    return hw, pal, game, screen


def _find(screen, id):
    return [b for b in screen.buttons if b.id == id][0]


def _ids(screen):
    return [b.id[0] for b in screen.buttons]


# The phase block no longer prints FRAMEWORK / YOUR WINDOW label rows - the
# 4px accent bar down each section's left edge is the whole vocabulary now
# (red = happens anyway, green = your window). These helpers assert the bar,
# which is the thing that actually carries the meaning.

def _bars(hw, pal):
    """Accent-bar colours drawn by phase_block, top to bottom."""
    kinds = {pal.red: "framework", pal.green: "window"}
    return [kinds[c[5]] for c in hw.display.calls
            if c[0] == "rect" and c[3] == 4 and c[5] in kinds]


def _has_framework(hw, pal):
    return "framework" in _bars(hw, pal)


def _has_window(hw, pal):
    return "window" in _bars(hw, pal)


def test_resource_advances_to_planning():
    """Resource and Planning are separate phases with separate action windows,
    so they are separate views - 2.P used to be the only action-window step
    with no view of its own."""
    hw, pal, game, screen = _setup("resource")
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("advance",)), game)
    # The Resource action window sits between them, so reaching Planning takes
    # two taps now. The CTA reads "Next: Planning" on both, because a window
    # announces the phase it hands off to rather than itself.
    assert game.view == "aw_resource"
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("advance",)), game)
    assert game.view == "planning"


def test_planning_advances_to_commit():
    hw, pal, game, screen = _setup("planning")
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("advance",)), game)
    assert game.view == "quest_commit"


def test_unrecognised_view_ctas_the_plain_word_next():
    """A save from a future build can carry a view id neither twin
    recognises. The catch-all draw branch labels its CTA from
    next_phase_view(), which has no next phase for an unknown view - the
    button must fall back to the plain word "Next", not crash on a raw
    VIEW_LABELS[None] lookup or print the literal "Next: None"."""
    hw, pal, game, screen = _setup("some_legacy_view")
    screen.draw(hw, game, pal)
    texts = [c[1] for c in hw.display.calls if c[0] == "text"]
    assert "Next" in texts
    assert not any(isinstance(t, str) and t.startswith("Next:") for t in texts)


def test_resource_and_planning_each_show_only_their_own_copy():
    hw, pal, game, screen = _setup("resource")
    screen.draw(hw, game, pal)
    t = " ".join(str(c[1]) for c in hw.display.calls if c[0] == "text")
    assert "gains a resource" in t
    assert "allies and attachments" not in t     # that is Planning's step

    hw, pal, game, screen = _setup("planning")
    screen.draw(hw, game, pal)
    t = " ".join(str(c[1]) for c in hw.display.calls if c[0] == "text")
    assert "allies and attachments" in t
    assert "gains a resource" not in t


def _texts(hw):
    return [str(c[1]) for c in hw.display.calls if c[0] == "text"]


def test_commit_view_shows_each_players_willpower_in_their_stat_pill():
    """Willpower is the third segment of a player's pill, not a per-player
    "commit" button. One tap target per pill, all routing to the same detail
    modal - the pills are status, and the tap only opens the editor."""
    hw, pal, game, screen = _setup("quest_commit")
    for i, c in enumerate((7, 8, 5, 6)):
        game.set_commit(i, c)
    screen.draw(hw, game, pal)
    ids = _ids(screen)
    assert "commit" not in ids
    # the legend pill plus one per player
    assert ids.count("players_detail") == len(game.players) + 1
    texts = _texts(hw)
    for c in (7, 8, 5, 6):
        assert str(c) in texts


def test_players_detail_tap_opens_players_detail_modal():
    from ui.modals import PlayersDetailModal
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    result = screen.on_button(_find(screen, ("players_detail",)), game)
    assert isinstance(result[1], PlayersDetailModal)


def test_players_zone_tokens_are_read_only():
    """The threat and willpower tokens are STATUS READOUTS, not controls.

    77f2e11 split each threat token into two 24px tap-halves (-1 / +1) to
    skip a modal round-trip. Reverted: at 24px they were too small to hit
    deliberately and too easy to hit by accident, and accommodating them cost
    the zone 36px of width. Editing threat is the Players modal's job."""
    hw, pal, game, screen = _setup("combat_shadow")
    screen.draw(hw, game, pal)
    ids = [b.id for b in screen.buttons]
    assert not [i for i in ids if i[0] == "threat"], (
        "players zone must expose no threat controls, got %s"
        % [i for i in ids if i[0] == "threat"])
    # the whole zone is one target, and it opens the modal
    assert ("players_detail",) in ids


def test_stat_pills_are_read_only_status():
    """Each pill is a tap target only so it can open the detail modal that
    already edits these values. Nothing edits a stat inline: 77f2e11 tried
    that with 24px tap-halves on the threat token and it was both too small
    to hit and too easy to hit by accident while holding the device."""
    hw, pal, game, screen = _setup("combat_shadow")
    screen.draw(hw, game, pal)
    zone = [b for b in screen.buttons
            if b.id[0] in ("players_detail", "progress_detail")]
    assert zone, "the stat zone has no tap targets at all"
    inline = [b.id for b in screen.buttons
              if b.id[0] in ("threat", "willpower", "commit")]
    assert not inline, "stats are edited in the modal, never inline: %s" % inline


def test_staging_view_has_direct_steppers():
    hw, pal, game, screen = _setup("quest_staging")
    screen.draw(hw, game, pal)
    ids = _ids(screen)
    for k in ("wp-", "wp+", "stg-", "stg+"):
        assert k in ids


def test_both_totals_rows_expose_the_same_three_targets_per_panel():
    """A panel is one control with three parts: - | editor | +.

    The two rows were built from different branches and only one of them
    registered the centre editor for both keys: quest_commit (tappable) gave
    "wp" and "stg" one each, quest_staging (steppers) gave it to "wp" only.
    So the Staging panel's centre was dead on the one screen the player stares
    at it, and the staging-threat counter had no way in from there at all.
    """
    for view in ("quest_commit", "quest_staging"):
        hw, pal, game, screen = _setup(view)
        screen.draw(hw, game, pal)
        ids = _ids(screen)
        for k in ("wp", "wp-", "wp+", "stg", "stg-", "stg+"):
            assert k in ids, "%s is missing %r" % (view, k)


def test_staging_counter_wears_the_black_threat_icon():
    """Staging threat is never red.

    widgets.willpower_staging_meter and _totals_row both ink it pal.outline,
    per design/stat-system.md's staging/enemy-threat rule - red is the PLAYER
    threat colour. The counter shared the player-threat icon, so the one
    editor for the number contradicted every readout of it.
    """
    hw, pal, game, screen = _setup("quest_staging")
    screen.draw(hw, game, pal)
    modal = screen.on_button(_find(screen, ("stg",)), game)[1]
    hw.display.calls = []
    modal.draw(hw, game, pal)
    pens = {c[5] for c in hw.display.calls if c[0] == "rect"}
    assert pal.outline in pens, "the staging counter must ink its icon black"
    assert pal.red not in pens, "staging threat is never red"
    # Black ink needs a lighter ground or it is invisible on pal.bg (16,12,9)
    # - the same reason the by-round chart stripes its staging row.
    assert pal.row_stripe in pens, "the black icon needs a ground to read on"


# -- the Back arrow is navigation, not undo --------------------------------
#
# It used to call game.undo() straight out, so one tap of Back rewound one
# DELTA - i.e. one tap of anything else. Undo/redo already has a home (the
# Game Log's < > replay controls, ui/screen_log.py), and a bottom-bar arrow
# next to a forward arrow reads as "the screen before this one" to everybody.

def _advance(screen, hw, pal, game, n=1):
    for _ in range(n):
        screen.draw(hw, game, pal)
        screen.on_button(_find(screen, ("advance",)), game)


def test_back_returns_to_the_view_you_came_from():
    hw, pal, game, screen = _setup("resource")
    _advance(screen, hw, pal, game, 2)
    assert game.view == "planning"
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("back",)), game)
    assert game.view == "aw_resource"
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("back",)), game)
    assert game.view == "resource"


def test_a_phase_owns_the_amount_it_changed_not_the_value_it_left():
    """The original TODO card, verbatim: "the next page always bases stat
    changes relative to the final values from the previous phase."

    Commit ends on 4. Staging bumps it to 6, so Staging is worth +2. Back up,
    correct Commit to 2, and coming forward must land on 4 - Staging still
    contributed +2, applied to the corrected base. It used to land on 2: the
    later phase's contribution was simply lost.
    """
    hw, pal, game, screen = _setup("quest_commit")
    game.set_willpower(4)
    _advance(screen, hw, pal, game, 2)
    assert game.view == "quest_staging"
    game.set_willpower(6)                       # this phase is worth +2

    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("back",)), game)
    assert game.view == "aw_quest_commit"
    assert game.willpower == 4, "back lands on the previous phase's final value"

    game.set_willpower(2)                       # the miscount, corrected
    _advance(screen, hw, pal, game)
    assert game.view == "quest_staging"
    assert game.willpower == 4, "2 + Staging's own +2"


def test_a_phase_delta_rebases_every_field_that_moved():
    """Not just willpower - whatever a phase changed, it owns the amount of.
    Threat is the one that matters most at the table."""
    hw, pal, game, screen = _setup("quest_commit")
    start = game.players[0].threat
    _advance(screen, hw, pal, game, 2)
    game.adjust_threat(0, 3)                    # +3 on Staging
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("back",)), game)
    assert game.players[0].threat == start
    game.adjust_threat(0, 10)                   # a correction upstream
    _advance(screen, hw, pal, game)
    assert game.players[0].threat == start + 10 + 3


def test_going_back_and_forward_with_no_edit_changes_nothing():
    """The delta round-trips exactly, so a stray Back/Forward is inert."""
    hw, pal, game, screen = _setup("quest_commit")
    game.set_willpower(4)
    _advance(screen, hw, pal, game, 2)
    game.set_willpower(6)
    before = game.snapshot()
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("back",)), game)
    _advance(screen, hw, pal, game)
    assert game.snapshot() == before


def test_an_edit_made_after_going_back_flows_forward():
    """Downstream views compute from live state, so a value corrected on an
    earlier screen is what the later screen resolves against."""
    hw, pal, game, screen = _setup("quest_commit")
    game.set_willpower(5)
    game.set_staging(4)
    _advance(screen, hw, pal, game, 2)
    assert game.view == "quest_staging"
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("back",)), game)     # -> aw_quest_commit
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("back",)), game)     # -> quest_commit
    assert game.view == "quest_commit"
    game.set_willpower(9)
    _advance(screen, hw, pal, game, 2)
    assert game.view == "quest_staging"
    outcome, n, _room = game.quest_preview()
    assert (outcome, n) == ("success", 5), "9 vs 4, not the pre-Back 5 vs 4"


def test_back_never_crosses_a_round_boundary():
    """A closed round is a hard floor. Backing into it would offer to re-enter
    a round whose end_round() has already banked its stats, bumped the counter
    and re-derived the willpower total."""
    hw, pal, game, screen = _setup("resource")
    _advance(screen, hw, pal, game, 2)
    game.end_round()
    assert game.view == "resource" and game.round == 2
    assert game.can_go_back() is False
    screen.draw(hw, game, pal)
    assert ("back",) not in [b.id for b in screen.buttons]


def test_backing_out_of_a_resolved_quest_reopens_it():
    """resolve_quest() latches quest_resolved, and stage_advance only resolves
    `if not game.quest_resolved` - so without this the staging number could be
    corrected and the resolution would still report the old comparison."""
    hw, pal, game, screen = _setup("quest_staging")
    game.willpower, game.staging = 11, 7
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("stage_advance",)), game)
    assert game.view == "quest_resolution" and game.pending_budget == 4
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("back",)), game)
    assert game.view == "quest_staging"
    assert game.quest_resolved is False and game.pending_budget == 0
    assert game.quest_history == []          # the row it appended went with it
    game.set_staging(3)
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("stage_advance",)), game)
    assert game.pending_budget == 8          # recomputed, not the stale 4


def test_backing_out_of_a_failed_quest_takes_the_threat_raise_back():
    """This is a TRACKER, not a referee. A fail is the one resolution that
    changes something on its own - it raises every living player's threat - and
    that is exactly the count a player is most likely to have got wrong. So
    Back reverses it rather than refusing to move.
    """
    hw, pal, game, screen = _setup("quest_staging")
    game.willpower, game.staging = 3, 8
    before = [p.threat for p in game.players]
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("stage_advance",)), game)
    assert game.view == "quest_resolution" and game.quest_outcome == "fail"
    assert [p.threat for p in game.players] == [t + 5 for t in before]

    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("back",)), game)
    assert game.view == "quest_staging"
    assert [p.threat for p in game.players] == before, "the raise must come back"
    assert game.quest_resolved is False and game.quest_history == []

    game.set_staging(3)                       # the miscount, corrected
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("stage_advance",)), game)
    assert game.quest_outcome == "tie"
    assert [p.threat for p in game.players] == before


def test_backing_out_of_a_fail_that_eliminated_a_player_brings_them_back():
    """The case the user named: an elimination happened, then the count turned
    out to be wrong. p.eliminated is derived from threat >= elimination, so
    lowering the threat un-eliminates on its own - what needs saying is that
    the pending prompt goes with it."""
    hw, pal, game, screen = _setup("quest_staging")
    game.players[0].elimination = game.players[0].threat + 3
    game.willpower, game.staging = 0, 5
    before = [p.threat for p in game.players]
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("stage_advance",)), game)
    assert game.players[0].eliminated is True
    assert game.pending_elim == 0

    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("back",)), game)
    assert [p.threat for p in game.players] == before
    assert game.players[0].eliminated is False
    assert game.pending_elim is None, "the elimination prompt must go too"


def test_a_fail_only_takes_back_the_threat_it_actually_raised():
    """resolve_quest raises LIVING players only. A player already eliminated
    when the quest failed took no raise, so reversing must not lower them -
    which is why the indices are recorded rather than re-derived from who
    happens to be eliminated now."""
    hw, pal, game, screen = _setup("quest_staging")
    game.players[1].eliminated = True
    dead_threat = game.players[1].threat
    game.willpower, game.staging = 2, 6
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("stage_advance",)), game)
    assert game.players[1].threat == dead_threat
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("back",)), game)
    assert game.players[1].threat == dead_threat


def test_back_works_on_a_resumed_game_with_nothing_recorded():
    """Back is derived from the phase sequence, so it needs no session state
    and works on the frame a save is resumed. An earlier draft kept a
    visited-screens stack, which left a resumed game with no Back at all."""
    from gamestate import GameState
    hw, pal, game, screen = _setup("resource")
    _advance(screen, hw, pal, game, 2)
    assert game.view == "planning"
    g2 = GameState.from_dict(game.to_dict())
    assert g2.can_go_back() is True
    assert g2.back_view() is True
    assert g2.view == "aw_resource"


def test_prev_view_is_the_inverse_of_next_view():
    """The two must agree, or Back and Forward describe different sequences.
    Checked over every view either function is total on, including the two
    that are not plain neighbours in VIEW_ORDER (the sailing detour, and
    resolution being entered by resolving rather than by advancing)."""
    from gamestate import GameState, VIEW_ORDER
    for sailing in (False, True):
        for v in list(VIEW_ORDER) + ["quest_sailing"]:
            # travel has two forward predecessors on paper - aw_quest_staging
            # and aw_quest_resolution - so prev_view has to pick one. The
            # staging window is unreachable in the catalog flow (quest_staging
            # advances through stage_advance, straight to resolution), so
            # travel's real predecessor is the resolution window.
            if v == "aw_quest_staging":
                continue
            # round_end -> resource is the one forward step that is not a
            # phase move but a ROUND move: end_round() bumps the counter,
            # re-derives the willpower total and re-arms the per-round flags.
            # Back stops there - see test_back_never_crosses_a_round_boundary.
            if v == "round_end":
                continue
            # You cannot be standing on the sailing view in a game that has no
            # sailing test - forcing it makes an unreachable state.
            if v == "quest_sailing" and not sailing:
                continue
            g = GameState()
            g.sailing = sailing
            g.view = v
            nxt = g.next_view()
            g.view = nxt
            assert g.prev_view() == v, (
                "%s -> %s -> %s (sailing=%s)"
                % (v, nxt, g.prev_view(), sailing))


def test_backing_into_sailing_does_not_shift_the_heading_twice():
    """advance_view() shifts one step off-course on the way INTO the sailing
    test (rulebook p.6). That is an arrival effect, not a per-tap one."""
    hw, pal, game, screen = _setup("planning")
    game.sailing = True
    _advance(screen, hw, pal, game)
    assert game.view == "quest_sailing"
    heading = game.heading
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("back",)), game)
    assert game.view == "planning"
    _advance(screen, hw, pal, game)
    assert game.view == "quest_sailing"
    assert game.heading == heading, "the winds shifted twice for one arrival"


def _twin(name):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return open(os.path.join(root, "docs", "js", name)).read()


def test_the_twins_totals_row_registers_the_same_centre_editors():
    """Source check on the twin, the way test_gamestate.py checks endRound.

    The JS branch was left as two nested ifs by a half-applied edit -
    `if (key === "stg") if (key === "wp") ...` - which parses, imports, and
    passes the structural parity probe while registering NO centre editor at
    all. Only reading the line finds it.
    """
    js = _twin("screen_play.js")
    body = js[js.index("  _totalsRow("):]
    body = body[:body.index("\n  }")]
    assert 'new Button([key], x + 64, y, half - 128, 84)' in body, (
        "docs/js/screen_play.js _totalsRow must push a centre editor for both "
        "keys, mirroring ui/screen_play.py _totals_row")
    assert 'if (key === "wp") this.buttons.push' not in body


def test_the_twins_staging_counter_asks_for_the_staging_icon():
    js = _twin("screen_play.js")
    body = js[js.index('if (k === "stg") {'):]
    # to the end of the returned ["modal", ...] tuple - NOT the first "}",
    # which closes the on-commit arrow function well before the icon argument.
    body = body[:body.index("];")]
    assert '"staging"' in body, (
        'docs/js/screen_play.js must open the staging counter with the '
        '"staging" icon (black), not "threat" (the player-threat red)')


def test_resolve_success_enters_resolution_view_with_budget():
    hw, pal, game, screen = _setup("quest_staging")
    game.willpower = 11
    game.staging = 7
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("stage_advance",)), game)
    assert game.view == "quest_resolution"
    assert game.pending_budget == 4
    assert game.quest_outcome == "success"


