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


def test_commit_view_shows_willpower_tokens_in_players_matrix():
    # Willpower now lives inside the flipped players zone (one shared tap
    # target) rather than a per-player row of "commit" buttons.
    hw, pal, game, screen = _setup("quest_commit")
    for i, c in enumerate((7, 8, 5, 6)):
        game.set_commit(i, c)
    screen.draw(hw, game, pal)
    ids = _ids(screen)
    assert ids.count("players_detail") == 1
    assert "commit" not in ids
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


def test_players_zone_is_a_single_tap_target_over_the_whole_zone():
    hw, pal, game, screen = _setup("combat_shadow")
    screen.draw(hw, game, pal)
    zone = [b for b in screen.buttons if b.id == ("players_detail",)]
    assert len(zone) == 1
    others = [b for b in screen.buttons
              if b.id[0] in ("threat", "willpower", "commit")
              and b.x < zone[0].x + zone[0].w and b.y < zone[0].y + zone[0].h]
    assert not others, "nothing may sit on top of the players zone: %s" % [b.id for b in others]


def test_staging_view_has_direct_steppers():
    hw, pal, game, screen = _setup("quest_staging")
    screen.draw(hw, game, pal)
    ids = _ids(screen)
    for k in ("wp-", "wp+", "stg-", "stg+"):
        assert k in ids


def test_resolve_success_enters_resolution_view_with_budget():
    hw, pal, game, screen = _setup("quest_staging")
    game.willpower = 11
    game.staging = 7
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("stage_advance",)), game)
    assert game.view == "quest_resolution"
    assert game.pending_budget == 4
    assert game.quest_outcome == "success"


def test_resolve_failure_enters_resolution_with_outcome_toast():
    hw, pal, game, screen = _setup("quest_staging")
    game.willpower = 2
    game.staging = 7
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("stage_advance",)), game)
    assert game.view == "quest_resolution"     # outcome shown on the resolution view
    assert game.players[0].threat == 5         # shortfall applied to all
    assert game.quest_outcome == "fail"
    assert screen.toast is not None            # picked up by the main loop
    screen.draw(hw, game, pal)                 # fail resolution -> Travel CTA
    ids = [b.id[0] for b in screen.buttons]
    assert "advance" in ids


def test_banner_does_not_leak_to_other_views():
    hw, pal, game, screen = _setup("quest_staging")
    screen.banner = ("Quest failed. +5", "bad", "quest_staging")
    game.view = "travel"
    screen.draw(hw, game, pal)
    texts = [c[1] for c in hw.display.calls if c[0] == "text"]
    assert not any("failed" in str(t) for t in texts)


def test_commit_view_wp_and_stg_have_inline_thirds():
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    ids = [b.id[0] for b in screen.buttons]
    assert "wp" in ids and "wp-" in ids and "wp+" in ids
    assert "stg" in ids and "stg-" in ids and "stg+" in ids


def test_commit_wp_thirds_geometry_flanks_centre():
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    minus = _find(screen, ("wp-",))
    centre = _find(screen, ("wp",))
    plus = _find(screen, ("wp+",))
    for b in (minus, centre, plus):
        assert b.h == 84 and b.w >= 24
    assert minus.x < centre.x < plus.x
    assert minus.x + minus.w == centre.x
    assert centre.x + centre.w == plus.x
    assert minus.w == plus.w


def test_commit_wp_thirds_step_and_floor_at_zero():
    hw, pal, game, screen = _setup("quest_commit")
    game.willpower = 0
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("wp-",)), game)
    assert game.willpower == 0
    screen.on_button(_find(screen, ("wp+",)), game)
    assert game.willpower == 1


def test_commit_staging_thirds_geometry_flanks_centre():
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    minus = _find(screen, ("stg-",))
    centre = _find(screen, ("stg",))
    plus = _find(screen, ("stg+",))
    for b in (minus, centre, plus):
        assert b.h == 84 and b.w >= 24           # layout linter's MIN_TARGET
    assert minus.x < centre.x < plus.x           # left / centre / right order
    assert minus.x + minus.w == centre.x         # thirds tile with no gaps
    assert centre.x + centre.w == plus.x
    assert minus.w == plus.w                     # outer thirds are symmetric


def test_commit_staging_thirds_step_and_floor_at_zero():
    hw, pal, game, screen = _setup("quest_commit")
    game.staging = 0
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("stg-",)), game)
    assert game.staging == 0                     # floored, never negative
    screen.on_button(_find(screen, ("stg+",)), game)
    assert game.staging == 1


def test_commit_staging_caption_reads_reveal_estimate():
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    assert ("+%d reveal estimate" % game.staging_reveal_estimate()) in _texts(hw)


def test_commit_staging_tap_opens_counter():
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    result = screen.on_button(_find(screen, ("stg",)), game)
    assert result[0] == "modal"
    modal = result[1]
    modal.state.tap(5)
    modal.state.confirm()
    modal.on_commit(modal.state.value)
    assert game.staging == 5


def test_resolution_apply_places_and_goes_to_travel():
    hw, pal, game, screen = _setup("quest_resolution")
    game.quest = {"stage_n": 1, "side": "B", "points": 8, "progress": 0}
    game.quest_outcome = "success"
    game.quest_outcome_n = 4
    game.pending_budget = 4
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("apply_alloc",)), game)
    assert game.quest["progress"] == 4
    # Applying progress IS step 3.4, so it hands off to 3.4's action window
    # rather than skipping past it to travel. That window is where a
    # just-revealed location can still be dealt with before travel.
    assert game.view == "aw_quest_resolution"
    assert game.next_phase_view() == "travel"
    assert game.pending_budget == 0


def test_travel_buttons_flag_the_location_picker():
    # The picker needs the scenario's gather-list union read out of the
    # catalog first, so the screen raises a flag and main.py's loop builds
    # the modal - it no longer returns one directly.
    hw, pal, game, screen = _setup("travel")
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("travel_new",)), game)
    assert game.pending_location_pick == {"mode": "new", "back": "play"}

    game.active_location = {"points": 3, "progress": 1}
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("travel_change",)), game)
    assert game.pending_location_pick == {"mode": "change", "back": "play"}


def test_travel_new_logs_precisely():
    g = GameState()
    m = LocationPickModal(g, mode="new")
    hw = FakeHardware()
    pal = Palette(hw.display)
    m.draw(hw, g, pal)
    save = [b for b in m.buttons if b.id == ("save",)][0]
    m.on_button(save)
    assert g.active_location == {"points": 3, "progress": 0}
    assert "Traveled to new location" in g.log[-1]["text"]


def _texts(hw):
    return [str(c[1]) for c in hw.display.calls if c[0] == "text"]


def test_progress_zone_shows_quest_loc_side_labels_and_remaining_values():
    hw, pal, game, screen = _setup("enc_optional")
    game.quest = {"stage_n": 2, "side": "B", "points": 8, "progress": 1}
    game.active_location = {"points": 9, "progress": 4}
    game.side_quests = [{"points": 9, "progress": 3}]
    screen.draw(hw, game, pal)
    texts = _texts(hw)
    for t in ("Q", "L", "S1"):                       # flipped zone: short headers
        assert t in texts
    for remaining in ("7", "5", "6"):                # points - progress each
        assert remaining in texts


def test_progress_zone_tap_present_and_sq_add_card_dropped():
    # The +SQ placeholder card is gone; every play view routes progress edits
    # (incl. adding side quests) through the Questing Progress view.
    for view in ("resource", "quest_commit", "quest_staging",
                 "enc_optional", "refresh", "travel"):
        hw, pal, game, screen = _setup(view)
        screen.draw(hw, game, pal)
        ids = [b.id[0] for b in screen.buttons]
        assert "progress_detail" in ids, view
        assert "sq_add" not in ids, view


def test_progress_detail_opens_questing_progress_modal():
    from ui.modals import QuestingProgressModal
    hw, pal, game, screen = _setup("resource")
    screen.draw(hw, game, pal)
    result = screen.on_button(_find(screen, ("progress_detail",)), game)
    assert isinstance(result[1], QuestingProgressModal)


def test_commit_view_shows_zones_then_note_at_content_y():
    from ui.screen_play import ZONE_TOP, CONTENT_Y
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    assert "Q" in _texts(hw)                         # progress zone quest column
    players = _find(screen, ("players_detail",))
    progress = _find(screen, ("progress_detail",))
    assert players.y == ZONE_TOP - 2 and progress.y == ZONE_TOP - 2
    assert players.x == 8 and progress.x == 174
    # RR 3.2 p.23: commitment is in player order - not simultaneous and not
    # secret - so the copy has to say so. Joined: the line wraps.
    assert "In player order, exhaust characters to commit" in " ".join(_texts(hw))
    assert "commit_tip" not in [b.id[0] for b in screen.buttons]


def test_zone_geometry_is_the_narrow_read_only_layout():
    """Back to 32px threat columns / 9 progress columns. The 48px columns
    only existed to make room for inline threat taps, which are gone."""
    from ui.screen_play import ZONE_TOP
    hw, pal, game, screen = _setup("refresh")
    game.active_location = None
    game.side_quests = []
    screen.draw(hw, game, pal)
    players = _find(screen, ("players_detail",))
    progress = _find(screen, ("progress_detail",))
    assert (players.x, players.y, players.w, players.h) == (8, ZONE_TOP - 2, 156, 90)
    assert (progress.x, progress.y, progress.w, progress.h) == (174, ZONE_TOP - 2, 298, 90)


def test_progress_zone_caps_columns_keeping_oldest_side_quests_and_sailing():
    hw, pal, game, screen = _setup("resource")
    game.active_location = {"points": 5, "progress": 0}
    game.sailing = True
    game.side_quests = [{"points": 5, "progress": 0} for _ in range(10)]
    screen.draw(hw, game, pal)
    texts = _texts(hw)
    # maxCols = (472-174)//32 = 9; fixed = Q + L + sailing = 3 -> 6 sides kept
    for lab in ("Q", "L", "S1", "S2", "S3", "S4", "S5", "S6"):
        assert lab in texts
    for lab in ("S7", "S8", "S9", "S10"):
        assert lab not in texts                      # newest sides dropped


def test_progress_zone_shows_sailing_column_regardless_of_view():
    # Old behaviour gated the heading card to specific views via a
    # show_heading flag; the flipped zone shows it whenever game.sailing is
    # true, on every view - this scene never rendered a heading card before.
    from ui.screen_play import ZONE_TOP
    hw, pal, game, screen = _setup("travel")
    game.sailing = True
    game.heading = 2
    screen.draw(hw, game, pal)
    scx = 190 + 32                                   # Q is the only other column
    well_disc_row = ("rect", scx - 14, ZONE_TOP + 40, 29, 1, pal.well)
    assert well_disc_row in hw.display.calls


def test_round_end_view_turns_the_round():
    """The round turns on 0.1's CTA, not on the refresh view.

    RR keeps them separate (7.5 Refresh phase ends, THEN 0.1 Round ends), and
    refresh is an ordinary phase view now: its CTA is a plain phase handoff
    like every other."""
    hw, pal, game, screen = _setup("round_end")
    screen.draw(hw, game, pal)
    assert game.round == 1                       # 0.1 belongs to THIS round
    screen.on_button(_find(screen, ("endround",)), game)
    assert game.round == 2
    assert game.view == "resource"


def test_refresh_applies_7_3_and_7_4_on_entry():
    hw, pal, game, screen = _setup("combat_player")
    screen.draw(hw, game, pal)
    before = [p.threat for p in game.players]
    game.enter_view("refresh")
    assert [p.threat for p in game.players] == [t + 1 for t in before]
    assert game.first_player == 1
    assert game.round == 1                       # still this round


def test_totals_cards_renamed_with_currency_icons():
    hw, pal, game, screen = _setup("quest_staging")
    screen.draw(hw, game, pal)
    texts = _texts(hw)
    assert "Questing for" in texts and "Staging area" in texts
    assert "Willpower" not in texts and "Staging threat" not in texts


def test_staging_center_tap_opens_reminders():
    from ui.modals import RemindersModal
    hw, pal, game, screen = _setup("quest_staging")
    screen.draw(hw, game, pal)
    result = screen.on_button(_find(screen, ("enc_rem",)), game)
    assert isinstance(result[1], RemindersModal)


def test_staging_shows_framework_window_and_meter():
    hw, pal, game, screen = _setup("quest_staging")
    game.willpower, game.staging = 11, 7
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert _has_framework(hw, pal) and _has_window(hw, pal)
    fills = [c for c in hw.display.calls if c[0] == "rect" and c[4] == 10
             and c[5] in (pal.gold, pal.outline)]
    assert len(fills) == 2


def test_staging_meter_and_totals_row_both_clear_of_cta():
    from ui.screen_play import CTA_Y
    hw, pal, game, screen = _setup("quest_staging")
    screen.draw(hw, game, pal)
    ids = _ids(screen)
    assert "stg-" in ids and "wp-" in ids     # totals_row steppers still present
    stepper = _find(screen, ("stg-",))
    assert stepper.y + stepper.h <= CTA_Y


def test_staging_tied_shows_dim_tie_message():
    hw, pal, game, screen = _setup("quest_staging")
    game.willpower = game.staging = 7
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert any("Tied" in t for t in texts)


def test_commit_tip_button_is_gone():
    hw, pal, game, screen = _setup("quest_commit")
    screen.draw(hw, game, pal)
    assert "commit_tip" not in [b.id[0] for b in screen.buttons]


def test_confirm_all_button_marks_every_living_player_touched():
    hw, pal, game, screen = _setup("quest_commit")
    game.adjust_threat(1, 50)                  # P2 eliminated
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("confirm_all",)), game)
    assert game.players[0].commit_touched is True
    assert game.players[1].commit_touched is False
    assert game.players[2].commit_touched is True
    assert game.players[3].commit_touched is True


def test_confirm_all_button_caption_reflects_progress():
    hw, pal, game, screen = _setup("quest_commit")
    game.players[0].commit_touched = True
    game.players[1].commit_touched = True
    screen.draw(hw, game, pal)
    assert "Confirm all commits (2/4)" in _texts(hw)
    for p in game.players:
        p.commit_touched = True
    screen.draw(hw, game, pal)
    assert "All players confirmed" in _texts(hw)


def test_notification_overlay_draws_with_pie_and_dismiss():
    hw, pal, game, screen = _setup("combat_shadow")
    screen.notif = ["Archery: deal damage now"]
    screen.notif_frac = 0.5
    screen.draw(hw, game, pal)
    assert any("Archery" in str(c[1]) for c in hw.display.calls if c[0] == "text")
    assert any(c[0] == "tri" for c in hw.display.calls)   # pie fan drawn
    assert screen.notif_pie is not None
    screen.on_button(_find(screen, ("notif_dismiss",)), game)
    assert screen.notif is None


def test_notification_pie_fraction_controls_fan_size():
    from ui.screen_play import draw_notif_pie
    hw = FakeHardware()
    pal = Palette(hw.display)
    draw_notif_pie(hw.display, pal, 100, 100, 11, 1.0)
    full = sum(1 for c in hw.display.calls if c[0] == "tri")
    hw.display.calls.clear()
    draw_notif_pie(hw.display, pal, 100, 100, 11, 0.25)
    quarter = sum(1 for c in hw.display.calls if c[0] == "tri")
    assert full == 24 and quarter == 6


def test_resolution_apply_always_enabled_and_shows_discard():
    hw, pal, game, screen = _setup("quest_resolution")
    game.quest = {"stage_n": 1, "side": "B", "points": 8, "progress": 0}
    game.active_location = None
    game.quest_outcome = "success"
    game.pending_budget = 4
    screen.draw(hw, game, pal)          # auto-split places all 4
    assert any(b.id == ("apply_alloc",) for b in screen.buttons)
    screen.on_button(_find(screen, ("areset",)), game)   # clear allocation
    screen.draw(hw, game, pal)
    ids = [b.id for b in screen.buttons]
    assert ("apply_alloc",) in ids       # always enabled (no gating)
    assert "Unplaced (discarded)" in _texts(hw)


def test_travel_modal_passes_contribution():
    hw, pal, game, screen = _setup("travel")
    game.active_location = None
    game.staging = 6
    screen.draw(hw, game, pal)
    screen.on_button(_find(screen, ("travel_new",)), game)
    # main.py's loop builds the modal from the flag; with no catalog entries
    # it opens straight on the manual stepper, exactly as before.
    m = LocationPickModal(game, mode=game.pending_location_pick["mode"])
    m.draw(hw, game, pal)
    ctr_plus = [b for b in m.buttons if b.id == ("ctr", 1)][0]
    m.on_button(ctr_plus)   # 2 -> 3
    save = [b for b in m.buttons if b.id == ("save",)][0]
    m.on_button(save)
    assert game.staging == 3


def test_header_shows_round_and_step_decimal():
    hw, pal, game, screen = _setup("quest_resolution")
    game.round = 2
    game.step = "3.4"
    screen.draw(hw, game, pal)
    assert "R2 3.4" in _texts(hw)


def test_setup_view_tip_and_quest_points_then_begin():
    hw, pal, game, screen = _setup("setup_game")
    screen.draw(hw, game, pal)
    assert any("mulligan" in str(c[1]) for c in hw.display.calls if c[0] == "text")
    for _ in range(8):
        screen.on_button(_find(screen, ("qp", 1)), game)
        screen.draw(hw, game, pal)
    assert game.quest["points"] == 8
    screen.on_button(_find(screen, ("advance",)), game)
    assert game.view == "resource"
    assert any("needs 8" in e["text"] for e in game.log)


def test_progress_detail_edits_quest_and_logs_on_close():
    hw, pal, game, screen = _setup("travel")
    game.active_location = {"points": 3, "progress": 1}
    game.side_quests = [{"points": 5, "progress": 2}]
    screen.draw(hw, game, pal)
    m = screen.on_button(_find(screen, ("progress_detail",)), game)[1]
    m.draw(hw, game, pal)
    # bump quest progress via its stepper, bump the side quest, then close
    m.on_button([b for b in m.buttons if b.id == ("qP+", None)][0])
    m.on_button([b for b in m.buttons if b.id == ("sP+", 0)][0])
    m.on_button([b for b in m.buttons if b.id == ("close",)][0])
    assert game.quest["progress"] == 1
    assert game.side_quests[0]["progress"] == 3
    assert any("(progress view)" in e["text"] for e in game.log)


def test_questing_for_card_taps_open_direct_total_editor_on_both_views():
    for view in ("quest_commit", "quest_staging"):
        hw, pal, game, screen = _setup(view)
        game.willpower = 5
        screen.draw(hw, game, pal)
        result = screen.on_button(_find(screen, ("wp",)), game)
        assert result[0] == "modal", view
        modal = result[1]
        modal.state.tap(1)
        modal.state.confirm()
        modal.on_commit(modal.state.value)
        assert game.willpower == 6, view


# -- Task 8: Quest Setup (R0 pre-round-1) ----------------------------------

_QS_SCN = {"slug": "p", "name": "P", "pack": "Core Set", "cycle": "Core Set",
           "source": "official", "kind": "quest", "nightmare": False, "mode": "Standard"}
_QS_STAGES = [{"stage": 1, "cards": [{"questPoints": 8, "victory": None, "sailing": False,
    "faces": [{"side": "A", "name": "Flies and Spiders", "text": "Setup: do the thing."},
              {"side": "B", "name": "Flies and Spiders", "text": None}]}]}]


def test_quest_setup_flip_to_b_enters_round_1():
    hw, pal, game, screen = _setup("quest_setup")
    game.preload_scenario(_QS_SCN, _QS_STAGES)
    for p in game.players:
        p.commit_touched = True
    screen.draw(hw, game, pal)
    result = screen.on_button(_find(screen, ("flip_to_b",)), game)
    assert result is True
    assert game.quest["side"] == "B" and game.quest["points"] == 8
    assert game.view == "resource"        # VIEW_ORDER[0]
    assert all(not p.commit_touched for p in game.players)
    assert game._round_snap is not None
    messages = [e["text"] for e in game.log]
    assert any("Setup complete" in m and "1B" in m and "8" in m for m in messages)


def test_quest_setup_card_modal_button_opens_quest_card_modal():
    from ui.modals import QuestCardModal
    hw, pal, game, screen = _setup("quest_setup")
    game.preload_scenario(_QS_SCN, _QS_STAGES)
    screen.draw(hw, game, pal)
    result = screen.on_button(_find(screen, ("open_card_modal",)), game)
    assert isinstance(result, tuple) and result[0] == "modal"
    assert isinstance(result[1], QuestCardModal)


def test_quest_setup_card_modal_button_is_null_for_custom_game():
    # No preload_scenario call: game.stages == [] (custom/manual quest). The
    # quest_setup view itself assumes a loaded scenario elsewhere in its draw
    # path (not reachable via normal nav without one), so exercise on_button
    # directly with a synthetic button rather than via draw()+_find().
    from ui.widgets import Button
    hw, pal, game, screen = _setup("quest_setup")
    result = screen.on_button(Button(("open_card_modal",), 0, 0, 1, 1), game)
    assert result is None


def test_quest_setup_shows_stage_and_setup_text():
    hw, pal, game, screen = _setup("quest_setup")
    game.preload_scenario(_QS_SCN, _QS_STAGES)
    screen.draw(hw, game, pal)
    texts = _texts(hw)
    joined = " ".join(texts)
    # No bespoke title block: the stage and the card name are named IN the
    # instruction. A centred amber stage label over a DISPLAY-gold card name
    # was this view's own invention, and presenting the card is not the
    # tracker's job - saying what to do in the phase is.
    assert "STAGE 1A" not in texts
    # Learn to Play's own words (setup step 7), not a paraphrase.
    assert "Perform the Setup instructions on Stage 1A, Flies and Spiders." in joined
    assert "flip the card to its Stage 1B side" in joined
    # The card's Setup text is NOT printed here. This screen says what to DO;
    # the text lives one tap away on the card that prints it.
    assert not any("Setup: do the thing." in t for t in texts)
    assert "View quest card" in joined
    # Quest setup happens once per game and hands straight to the resource
    # phase, so the button says what completing it does. Same label the
    # custom-quest path uses on setup_game: both routes into round 1 end with
    # the same button. An ACTION cta - single line, no NEXT PHASE kicker.
    assert "Begin Round 1" in texts
    assert "NEXT PHASE" not in texts
    assert not any("qp" in t for t in texts)      # no fact crammed into a label


def test_quest_setup_no_setup_text_shows_fallback():
    hw, pal, game, screen = _setup("quest_setup")
    stages = [{"stage": 1, "cards": [{"questPoints": 8, "victory": None, "sailing": False,
        "faces": [{"side": "A", "name": "x", "text": None},
                  {"side": "B", "name": "x", "text": None}]}]}]
    game.preload_scenario(_QS_SCN, stages)
    screen.draw(hw, game, pal)
    assert any("Stage 1A has no Setup instructions." in t for t in _texts(hw))
    # Still offers the card: a player may want to read side A's story even
    # when it carries no Setup instructions.
    assert any("View quest card" in t for t in _texts(hw))


def test_travel_no_location_shows_framework_and_travel_button():
    hw, pal, game, screen = _setup("travel")
    game.active_location = None
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert _has_framework(hw, pal)
    assert "travel_new" in _ids(screen)


def test_travel_with_location_says_travel_is_blocked():
    """"Explore it first" was CUT, not reworded.

    A location is explored when progress on it reaches its quest points, and
    progress lands at 3.4 - already over by the time this screen appears.
    Exploring during travel needs a card effect placing progress out of
    sequence, so the old copy advised something the player generally cannot
    do at that moment."""
    hw, pal, game, screen = _setup("travel")
    game.active_location = {"points": 3, "progress": 1}
    screen.draw(hw, game, pal)
    assert "travel_change" in _ids(screen)
    texts = " ".join(str(c[1]) for c in hw.display.calls if c[0] == "text")
    assert "no travel this phase" in texts.lower()
    assert "explore" not in texts.lower()


def test_enc_optional_has_no_framework_block_and_says_why_to_engage():
    """The threat caption was CUT, not reworded.

    It duplicated the following window screen, which says the same thing on
    the screen where a player can still act on it, and it was the last
    second-person line on this view ("your threat... engage you") - meaningless
    on a device four players share.

    What this view owes the player is why anyone would engage VOLUNTARILY,
    and that needs no strategy claim: 5.2 ignores engagement cost where 5.3
    requires it to be at or below the player's threat.
    """
    hw, pal, game, screen = _setup("enc_optional")
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert not _has_framework(hw, pal) and _has_window(hw, pal)
    joined = " ".join(texts)
    assert "engagement cost is ignored" in joined.lower()
    assert "staging area" in joined.lower()
    assert "engage you" not in joined


def test_enc_checks_shows_the_loop_and_the_engagement_rule():
    """Engagement checks are a LOOP, so the view is a flow diagram now rather
    than a framework band.

    RR 5.3 has two nested loops: each player engages one enemy in player
    order, then the whole rotation runs again, "until there are no enemies
    remaining in the staging area that can engage any of the players"."""
    hw, pal, game, screen = _setup("enc_checks")
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert any("Repeat until" in t for t in texts), "the loop must show its exit"
    # FFG's own term - Rules Reference p.10 glossary "In Player Order" - not
    # "clockwise", and not the non-existent "turn order". Joined because the
    # phrase wraps across drawn lines.
    joined = " ".join(texts).lower()
    assert "in player order" in joined
    # RR 5.3: ONE enemy engages per player at a time, the highest engagement
    # cost at or below that player's threat - not several in descending order.
    # "check" itself is gone from the body: it is RR's name for one player
    # comparing their threat against staging, and nothing on screen defines
    # it, so every later reference inherited the debt.
    assert "highest engagement cost" in joined
    assert "not optional" in joined     # 5.2 was optional; 5.3 is not
    assert "one check engages" not in joined


def test_combat_shadow_shows_framework_only_ordering_text():
    hw, pal, game, screen = _setup("combat_shadow")
    screen.draw(hw, game, pal)
    texts = " ".join(str(c[1]) for c in hw.display.calls if c[0] == "text")
    assert _has_framework(hw, pal)
    # RR 6.2 p.24: dealt in player order, and within one player's enemies the
    # highest ENGAGEMENT cost first. Both halves must reach the screen.
    joined = texts.lower()          # the phrase now LEADS the sentence
    assert "in player order" in joined
    assert "highest engagement cost" in joined
    # The two orderings are NESTED, and "that player's" is the word that says
    # so: player order picks WHOSE enemies, engagement cost orders WITHIN one
    # player's. Side by side with no link they read as a contradiction.
    assert "that player's" in joined


def test_combat_enemy_sailing_appends_ship_note_to_framework():
    hw, pal, game, screen = _setup("combat_enemy")
    game.sailing = True
    screen.draw(hw, game, pal)
    texts = " ".join(str(c[1]) for c in hw.display.calls if c[0] == "text")
    assert "ship-enemy" in texts.lower()


def test_combat_enemy_flavor_icon_still_drawn():
    hw, pal, game, screen = _setup("combat_enemy")
    screen.draw(hw, game, pal)
    icon_rows = [c for c in hw.display.calls if c[0] == "rect" and c[4] == 1
                 and c[1] >= 480 - 8 - 34]
    assert icon_rows


def test_combat_player_names_both_ranged_rules():
    """CUT: "1 attack per engaged enemy".

    RR 6.7 and 6.8a say only that the active player "may declare an attack
    against one of their enemies", repeated - no per-enemy cap anywhere. The
    cap IS stated on the enemy side (6.3: each engaged enemy "will have one
    opportunity to make an attack"), which is what made the omission easy to
    miss. Uncited, so it does not ship.

    What replaces it is the thing that WAS missing: Ranged appears twice in
    this flow, one step apart, and the old copy had only one of them."""
    hw, pal, game, screen = _setup("combat_player")
    screen.draw(hw, game, pal)
    joined = " ".join(str(c[1]) for c in hw.display.calls if c[0] == "text")
    assert "1 attack per engaged enemy" not in joined
    # 6.8b: an all-Ranged attack may target any enemy engaged with any player
    assert "every attacker has Ranged" in joined
    # 6.8.1: other players' ranged characters may exhaust to join
    assert "Other players' Ranged" in joined
    # 6.8b also requires exhausting the attackers, which was never on screen
    assert "exhausts characters" in joined

def test_refresh_shows_framework_window_and_threat_preview():
    hw, pal, game, screen = _setup("refresh")
    for i, p in enumerate(game.players):
        p.threat = 20 + i
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert _has_framework(hw, pal) and _has_window(hw, pal)
    assert any(t.startswith("P1 20->21") for t in texts)


def test_refresh_flags_projected_danger_even_if_not_yet_flagged():
    hw, pal, game, screen = _setup("refresh")
    game.players[1].threat = 39   # not yet danger (39 < 50-10=40); +1 crosses it
    screen.draw(hw, game, pal)
    danger_texts = [c for c in hw.display.calls
                    if c[0] == "text" and str(c[1]).startswith("P2") and c[5] == pal.red]
    assert danger_texts
    assert danger_texts[0][1].endswith("!")


def test_refresh_skips_eliminated_players_in_preview():
    hw, pal, game, screen = _setup("refresh")
    game.players[2].eliminated = True
    game.players[2].threat = 50
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert not any(t.startswith("P3 ") for t in texts)


# --- the CTA earns DISPLAY by staying short --------------------------------
# The primary CTA renders at DISPLAY, which only fits because its labels were
# cut for it ("Next Phase:" -> "Next:", "End round (raise threat, pass token)"
# -> "End Round"). A longer label would overflow the button silently, and the
# design system forbids the obvious "fix" of shrinking it back down - so the
# ceiling is asserted here instead.

def test_every_label_fits_between_the_nav_squares():
    """Replaces the old full-width CTA ceiling. Dropping the "Next: " prefix
    took the longest label from 408px to 330px, and the label now lives in the
    fixed span between the two nav squares - the same frame whether or not
    Back is drawn."""
    import gamestate
    from ui.screen_play import MARGIN, NAV_W, NAV_PAD
    from ui.theme import DISPLAY
    hw = FakeHardware()
    lx = MARGIN + NAV_W + NAV_PAD
    usable = (480 - MARGIN - NAV_W - NAV_PAD) - lx
    labels = ["Begin Round 1", "End Round", "Confirm all commits",
              "Flip to Side B  ->  10 qp"] + [
        # Window views are excluded on purpose: their label never reaches a
        # CTA. A phase view's button names the next PHASE, and a window's own
        # button does too, so "Action Window: Questing: Resolution" is a log
        # string, not something that has to fit between the nav squares.
        v for k, v in gamestate.VIEW_LABELS.items()
        if not gamestate.is_window_view(k)]
    over = [(s, hw.display.measure_text(s, DISPLAY)) for s in labels
            if hw.display.measure_text(s, DISPLAY) > usable]
    assert not over, "nav labels overflow %dpx at DISPLAY: %s" % (usable, over)


def test_nav_rule_is_drawn_full_width():
    from ui.screen_play import NAV_RULE_Y
    hw, pal, game, screen = _setup("resource")
    screen.draw(hw, game, pal)
    rules = [c for c in hw.display.calls
             if c[0] == "rect" and c[2] == NAV_RULE_Y and c[3] == 480 and c[4] == 1]
    assert len(rules) == 1


def test_back_square_absent_with_no_history():
    hw, pal, game, screen = _setup("resource")
    screen.draw(hw, game, pal)
    assert "back" not in _ids(screen)


def test_back_square_appears_with_history_and_undoes():
    from ui.screen_play import NAV_W, CTA_H, CTA_Y, MARGIN
    hw, pal, game, screen = _setup("resource")
    screen.draw(hw, game, pal)
    snap = game.begin_action()
    screen.on_button(_find(screen, ("advance",)), game)
    game.add_delta(snap)
    screen.draw(hw, game, pal)
    back = _find(screen, ("back",))
    assert (back.x, back.y, back.w, back.h) == (MARGIN, CTA_Y, NAV_W, CTA_H)
    assert back.w == back.h == CTA_H          # square by construction
    assert screen.on_button(back, game) is True
    assert game.view == "resource"


def test_forward_hit_area_spans_label_and_arrow():
    """The most-tapped control keeps a large target even though only the arrow
    square is drawn as a button."""
    from ui.screen_play import NAV_W, MARGIN, NAV_PAD, CTA_Y, CTA_H
    hw, pal, game, screen = _setup("travel")
    screen.draw(hw, game, pal)
    fwd = _find(screen, ("advance",))
    assert fwd.x == MARGIN + NAV_W + NAV_PAD
    assert fwd.x + fwd.w == 480 - MARGIN
    assert (fwd.y, fwd.h) == (CTA_Y, CTA_H)


def test_label_frame_does_not_move_when_back_appears():
    hw, pal, game, screen = _setup("travel")
    screen.draw(hw, game, pal)
    before = [c[2] for c in hw.display.calls
              if c[0] == "text" and str(c[1]) == "Encounter: Opt. Engage"]
    snap = game.begin_action()
    game.adjust_threat(0, 1)
    game.add_delta(snap)
    hw.display.calls.clear()
    screen.draw(hw, game, pal)
    after = [c[2] for c in hw.display.calls
             if c[0] == "text" and str(c[1]) == "Encounter: Opt. Engage"]
    assert before and before == after


def test_phase_advance_uses_a_kicker_and_the_bare_phase_name():
    hw, pal, game, screen = _setup("combat_enemy")
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "NEXT PHASE" in texts
    assert "Combat: Player Attacks" in texts
    assert "Next: Combat: Player Attacks" not in texts


def test_action_ctas_are_a_single_line_with_no_kicker():
    """Setup's CTA is an action, not a phase handoff, so it gets no kicker.

    Refresh used to be the other example, with "End Round". It is not any
    more: refresh is an ordinary phase now, and the round turns on round_end
    (0.1). That removed the last CTA doing two jobs at once - End Round both
    applied 7.3 and crossed the round boundary."""
    hw, pal, game, screen = _setup("setup_game")
    screen.draw(hw, game, pal)
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "Begin Round 1" in texts
    assert "NEXT PHASE" not in texts


def test_back_is_a_noop_when_history_is_empty():
    from ui.widgets import Button
    hw, pal, game, screen = _setup("resource")
    screen.draw(hw, game, pal)
    assert screen.on_button(Button(("back",), 0, 0, 1, 1), game) is None


def test_back_clears_screen_local_allocation_and_banner():
    hw, pal, game, screen = _setup("quest_staging")
    game.willpower, game.staging = 11, 7
    screen.draw(hw, game, pal)
    snap = game.begin_action()
    screen.on_button(_find(screen, ("stage_advance",)), game)
    game.add_delta(snap)
    screen.draw(hw, game, pal)
    assert screen.alloc is not None
    screen.on_button(_find(screen, ("back",)), game)
    assert screen.alloc is None
    assert screen.banner is None
    assert game.view == "quest_staging"
